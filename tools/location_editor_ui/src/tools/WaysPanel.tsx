import { useEffect, useState } from "react";
import LocInput from "../components/LocInput";
import { getLocations } from "../store";
import type { Door, LocRow, Model } from "../types";

// «Проходы»: where the doors a and b lead (data/passages.json doors), the
// cells of other locations a player walks in here from (walk_in; their
// files stay as they are), and whether the place is left onto the map.
export default function WaysPanel(props: {
  model: Model;
  readOnly: boolean;
  onDoor: (side: "a" | "b", d: Door | null) => void;
  onWalkIn: (i: number, patch: { why?: string } | null) => void;
  onPickWalkIn: (from: number, i: number | null) => void;
  onNoMap: (v: { why: string } | null) => void;
}) {
  const m = props.model;
  const ro = props.readOnly;
  const [from, setFrom] = useState<number | null>(null);
  const [rows, setRows] = useState<LocRow[]>([]);
  useEffect(() => {
    getLocations().then(setRows, () => undefined);
  }, []);
  const title = (id: number) => rows.find((r) => r.id === id)?.title || "";
  const doorCells = (s: string) => m.exits.filter((e) => e[2] === s).length;
  return (
    <div className="tool-panel">
      <h4>Двери</h4>
      <p className="hint">Дверь — выход a или b внутри локации (его рисуют в «Выходах»). Здесь — куда она ведёт.</p>
      {(["a", "b"] as const).map((s) => {
        const d = m.doors[s] || null;
        const n = doorCells(s);
        return (
          <div key={s} className="door-box">
            <div className="row">
              <b>Дверь {s}</b>
              <span className={`small ${n ? "muted" : "warn-text"}`}>{n ? `клеток: ${n}` : "клеток с этой дверью нет"}</span>
              <span className="grow" />
              {d && !ro && (
                <button className="ghost" onClick={() => props.onDoor(s, null)}>
                  Не вести
                </button>
              )}
            </div>
            <label className="field-row">
              <span className="field-label">Ведёт в</span>
              <LocInput
                value={d?.target ?? null}
                exclude={m.id}
                label={`Дверь ${s} ведёт в`}
                onChange={(id) => !ro && props.onDoor(s, id === null ? null : { ...(d || {}), target: id, why: d?.why || "" })}
              />
            </label>
            {d && (
              <label className="field-row">
                <span className="field-label">Почему</span>
                <input value={d.why || ""} disabled={ro} placeholder="Пусто: редактор напишет сам" onChange={(e) => props.onDoor(s, { ...d, why: e.target.value })} />
              </label>
            )}
          </div>
        );
      })}

      <h4>Проходы из готовых локаций</h4>
      <p className="hint">
        Игрок, дошедший до отмеченных клеток другой локации, оказывается здесь. Файл той локации не меняется, окна выхода нет.
      </p>
      {m.walk_ins.map((w, i) => (
        <div key={i} className="door-box">
          <div className="row">
            <b>
              из #{w.from} {title(w.from) && `«${title(w.from)}»`}
            </b>
            <span className="small muted">клеток: {w.cells.length}</span>
            <span className="grow" />
            <button onClick={() => props.onPickWalkIn(w.from, i)}>Клетки…</button>
            {!ro && (
              <button className="ghost" onClick={() => props.onWalkIn(i, null)}>
                Убрать
              </button>
            )}
          </div>
          <label className="field-row">
            <span className="field-label">Почему</span>
            <input value={w.why || ""} disabled={ro} placeholder="Пусто: редактор напишет сам" onChange={(e) => props.onWalkIn(i, { why: e.target.value })} />
          </label>
        </div>
      ))}
      {!ro && (
        <div className="row add-walkin">
          <LocInput value={from} onChange={setFrom} exclude={m.id} label="Проход из локации" placeholder="из какой локации" />
          <button disabled={from === null} onClick={() => from !== null && props.onPickWalkIn(from, null)}>
            Выбрать клетки…
          </button>
        </div>
      )}

      <h4>Выход на карту</h4>
      <label className="check">
        <input
          type="checkbox"
          checked={!!m.no_map}
          disabled={ro}
          onChange={(e) => props.onNoMap(e.target.checked ? { why: "" } : null)}
        />
        Без выхода на карту: место покидают только своими дверями и проходами
      </label>
      {m.no_map && (
        <label className="field-row">
          <span className="field-label">Почему</span>
          <input value={m.no_map.why || ""} disabled={ro} placeholder="Пусто: редактор напишет сам" onChange={(e) => props.onNoMap({ why: e.target.value })} />
        </label>
      )}
    </div>
  );
}
