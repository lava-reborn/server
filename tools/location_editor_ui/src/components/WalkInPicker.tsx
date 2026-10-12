import { useEffect, useRef, useState } from "react";
import { api, errText } from "../api";
import { LocCanvas, type Layer } from "../canvas";
import { inGrid, key } from "../hex";
import type { Cell, Model } from "../types";
import { Modal, Spinner } from "./ui";

// The cells of another location where a player walks into this place: that
// location drawn as it is (its file is never changed), a click toggles a
// cell. Walls and exits are no place for it: the check says so too.
export default function WalkInPicker(props: {
  from: number;
  cells: Cell[];
  focus?: Cell[];
  target: string;
  onDone: (cells: Cell[]) => void;
  onClose: () => void;
}) {
  const host = useRef<HTMLDivElement>(null);
  const canvas = useRef<LocCanvas | null>(null);
  const [model, setModel] = useState<Model | null>(null);
  const [cells, setCells] = useState<Cell[]>(props.cells);
  const [err, setErr] = useState<string | null>(null);
  const [hover, setHover] = useState<string>("");
  const cellsRef = useRef(cells);
  cellsRef.current = cells;
  const modelRef = useRef<Model | null>(null);
  modelRef.current = model;

  useEffect(() => {
    let live = true;
    api.location(props.from).then(
      (m) => live && setModel(m),
      (e) => live && setErr(errText(e)),
    );
    return () => {
      live = false;
    };
  }, [props.from]);

  useEffect(() => {
    if (!host.current || !model) return;
    const c = new LocCanvas(host.current, {
      pointer: (p) => {
        if (p.kind !== "down") return;
        const m = modelRef.current!;
        if (!inGrid(p.cell, m.width, m.height)) return;
        const k = key(p.cell[0], p.cell[1]);
        const have = cellsRef.current.some((x) => key(x[0], x[1]) === k);
        setCells(have ? cellsRef.current.filter((x) => key(x[0], x[1]) !== k) : [...cellsRef.current, p.cell]);
      },
      hover: (cell) => {
        if (!cell) return setHover("");
        const m = modelRef.current!;
        const wall = m.walls.find((w) => w[0] === cell[0] && w[1] === cell[1]);
        const exit = m.exits.find((w) => w[0] === cell[0] && w[1] === cell[1]);
        const entry = m.entries.some((w) => w[0] === cell[0] && w[1] === cell[1]);
        setHover(
          `${cell[0]}:${cell[1]}${wall ? ` · стена ${wall[2]}` : ""}${exit ? ` · выход ${exit[2]}` : ""}${entry ? " · вход" : ""}`,
        );
      },
    });
    c.layers = new Set<Layer>(["art", "walls", "exits", "entries", "grid"]);
    c.setModel(model);
    canvas.current = c;
    let url: string | null = null;
    const scale = model.width > 32 ? 0.5 : 1;
    api
      .renderSaved(model.id, "art", scale)
      .then((b) => {
        url = URL.createObjectURL(b);
        c.setBackground(url, scale);
      })
      .catch((e) => setErr(errText(e)));
    const focus = props.focus && props.focus.length ? props.focus : props.cells;
    requestAnimationFrame(() => (focus.length ? c.centerOn(focus[0], 1) : c.fit()));
    return () => {
      c.destroy();
      canvas.current = null;
      if (url) URL.revokeObjectURL(url);
    };
  }, [model]);

  useEffect(() => {
    canvas.current?.setMarks([
      ...(props.focus && props.focus.length ? [{ cells: props.focus, stroke: "#e2543a", width: 3, ring: 18 }] : []),
      { cells, fill: "rgba(217,164,65,0.75)", stroke: "#f0c46a", width: 2, ring: 14 },
    ]);
  }, [cells, model, props.focus]);

  return (
    <Modal
      full
      title={`Проход из #${props.from}${model ? ` «${model.attrs.title}»` : ""} в ${props.target}`}
      onClose={props.onClose}
      footer={
        <>
          <span className="small muted grow">
            Клик по клетке добавляет её или убирает. Колёсико — масштаб, правая кнопка — сдвиг. Выбрано клеток: {cells.length}.
            {hover && <span className="mono"> {hover}</span>}
          </span>
          <button onClick={props.onClose}>Отмена</button>
          <button className="primary" disabled={!cells.length} onClick={() => props.onDone(cells)}>
            Готово
          </button>
        </>
      }
    >
      {err && <p className="err-text">{err}</p>}
      {!model && !err && (
        <p className="muted">
          <Spinner /> Открываю локацию {props.from}…
        </p>
      )}
      <p className="small muted legend">
        <i className="sw wall" /> стены <i className="sw exit" /> выходы <i className="sw entry" /> входы{" "}
        <i className="sw pick" /> клетки прохода. Игрок, дошедший до такой клетки, оказывается в новом месте; окна выхода клиент
        не показывает.
      </p>
      <div className="picker-canvas" ref={host} />
    </Modal>
  );
}
