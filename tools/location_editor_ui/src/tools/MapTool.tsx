import { useEffect, useRef, useState } from "react";
import { errText } from "../api";
import { Field, Spinner } from "../components/ui";
import { MapCanvas, type MapHover } from "../mapcanvas";
import { getMap } from "../store";
import type { Cell, MapInfo, MapPlace, Model } from "../types";

const COLOUR_RU: Record<string, string> = {
  black: "чёрный",
  blue: "синий",
  green: "зелёный",
  orange: "оранжевый",
  red: "красный",
  tan: "песочный",
  white: "белый",
  yellow: "жёлтый",
};

// The global map in the middle of the editor while «Карта» is the tool.
export function MapView(props: { model: Model; onPick: (c: Cell) => void }) {
  const host = useRef<HTMLDivElement>(null);
  const canvas = useRef<MapCanvas | null>(null);
  const [info, setInfo] = useState<MapInfo | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [hover, setHover] = useState<MapHover | null>(null);
  const [shade, setShade] = useState(true);
  const pick = useRef(props.onPick);
  pick.current = props.onPick;

  useEffect(() => {
    getMap().then(setInfo, (e) => setErr(errText(e)));
  }, []);

  useEffect(() => {
    if (!info || !host.current) return;
    const c = new MapCanvas(host.current, info, (cell) => pick.current(cell), setHover);
    canvas.current = c;
    const ours = Object.entries(info.ours)
      .filter(([id, cell]) => cell && Number(id) !== props.model.id)
      .map(([, cell]) => cell as Cell);
    c.setOurs(ours);
    const at = props.model.map?.cell || info.starts[0] || [Math.round((info.bounds.x[0] + info.bounds.x[1]) / 2), Math.round((info.bounds.y[0] + info.bounds.y[1]) / 2)];
    requestAnimationFrame(() => c.centerOn(at as Cell, 1.5));
    return () => {
      c.destroy();
      canvas.current = null;
    };
    // the map is made once; the chosen cell follows below
    // eslint-disable-next-line
  }, [info]);

  useEffect(() => {
    canvas.current?.setChosen(props.model.map?.cell || null);
  }, [props.model.map, info]);

  useEffect(() => {
    canvas.current?.setShade(shade);
  }, [shade]);

  const title = (id: number | null) => (id !== null && info ? info.titles[String(id)] || "" : "");
  return (
    <div className="map-view">
      <div className="canvas-tools">
        <button onClick={() => canvas.current?.zoomBy(1 / 1.3)} aria-label="Мельче">
          −
        </button>
        <button onClick={() => canvas.current?.zoomBy(1.3)} aria-label="Крупнее">
          +
        </button>
        <button onClick={() => props.model.map && canvas.current?.centerOn(props.model.map.cell)}>К выбранной клетке</button>
        <label className="check">
          <input type="checkbox" checked={shade} onChange={(e) => setShade(e.target.checked)} /> Тень: горы и вода, недостижимое
        </label>
        <span className="legend small">
          <i className="sw place" /> места <i className="sw ours" /> наши <i className="sw start" /> старт <i className="sw retired" />{" "}
          выведенные <i className="sw patrol" /> патрули
        </span>
      </div>
      <div className="canvas-host" ref={host}>
        {err && <p className="err-text pad">Карта не прочитана: {err}</p>}
        {!info && !err && (
          <p className="muted pad">
            <Spinner /> Читаю карту…
          </p>
        )}
      </div>
      <div className="statusbar">
        {hover ? (
          <span>
            <b className="mono">
              {hover.cell[0]},{hover.cell[1]}
            </b>
            {hover.place !== null && ` · место #${hover.place} «${title(hover.place)}»`}
            {hover.retired !== null && ` · клетка выведенного места #${hover.retired}`}
            {hover.patrol !== null && ` · патруль лагеря #${hover.patrol}`}
            {hover.blocked && " · горы или вода"}
            {hover.reachable === false && !hover.blocked && " · не дойти от старта и из долины"}
            {hover.labels.length > 0 && ` · подпись: ${hover.labels.join(" / ").slice(0, 160)}`}
          </span>
        ) : (
          <span className="muted">Щелчок выбирает клетку места. Перетаскивание двигает карту, колёсико меняет масштаб.</span>
        )}
      </div>
    </div>
  );
}

// The right panel of «Карта»: the chosen cell, its label and square.
export function MapPanel(props: {
  model: Model;
  colours: string[];
  readOnly: boolean;
  onChange: (m: MapPlace | null) => void;
}) {
  const mp = props.model.map;
  const ro = props.readOnly;
  return (
    <div className="tool-panel">
      {!mp ? (
        <p className="hint">
          Место пока не на карте. Щёлкните по клетке глобальной карты: она должна быть проходимой, ничьей и достижимой. В место
          можно попасть и без карты — проходом из готовой локации («Проходы»).
        </p>
      ) : (
        <>
          <p>
            Клетка{" "}
            <b className="mono">
              {mp.cell[0]},{mp.cell[1]}
            </b>
          </p>
          <Field label="Подпись на карте" hint="Её видит игрок, наведя мышь на клетку">
            <input value={mp.label} disabled={ro} onChange={(e) => props.onChange({ ...mp, label: e.target.value })} />
          </Field>
          <Field label="Квадрат на клетке">
            <select value={mp.square || ""} disabled={ro} onChange={(e) => props.onChange({ ...mp, square: e.target.value || null })}>
              <option value="">без квадрата</option>
              {props.colours.map((c) => (
                <option key={c} value={c}>
                  {COLOUR_RU[c] || c}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Почему здесь">
            <input value={mp.why || ""} disabled={ro} placeholder="Пусто: редактор напишет сам" onChange={(e) => props.onChange({ ...mp, why: e.target.value })} />
          </Field>
          {!ro && (
            <button className="danger" onClick={() => props.onChange(null)}>
              Убрать с карты
            </button>
          )}
          <p className="small muted">
            Клетку проверяет «Проверить»: сервер пересчитывает карту (около минуты) и не даёт сдвинуть другие места.
          </p>
        </>
      )}
    </div>
  );
}
