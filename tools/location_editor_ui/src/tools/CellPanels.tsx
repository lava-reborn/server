import { EXIT_COLOURS, WALL_COLOURS } from "../canvas";
import type { Info, Model } from "../types";

export type WallMode = "brush" | "rect" | "fill" | "erase";
export type ExitSide = "auto" | "W" | "N" | "E" | "S" | "a" | "b";

const MODES: { id: WallMode; label: string; hint: string }[] = [
  { id: "brush", label: "Кисть", hint: "Ведите мышью с нажатой кнопкой" },
  { id: "rect", label: "Прямоугольник", hint: "Растяните рамку; с Shift рамка стирает" },
  { id: "fill", label: "Заливка", hint: "Щелчок по пустой клетке заливает всю область до стен" },
  { id: "erase", label: "Ластик", hint: "Стирает стены под кистью" },
];

export function WallsPanel(props: {
  info: Info | null;
  model: Model;
  mode: WallMode;
  onMode: (m: WallMode) => void;
  code: string;
  onCode: (c: string) => void;
  size: number;
  onSize: (n: number) => void;
}) {
  const codes = props.info?.codes || { f: "стена" };
  const counts: Record<string, number> = {};
  for (const w of props.model.walls) counts[w[2]] = (counts[w[2]] || 0) + 1;
  return (
    <div className="tool-panel">
      <div className="seg">
        {MODES.map((m) => (
          <button key={m.id} className={props.mode === m.id ? "on" : ""} onClick={() => props.onMode(m.id)} title={m.hint}>
            {m.label}
          </button>
        ))}
      </div>
      <p className="hint">{MODES.find((m) => m.id === props.mode)?.hint}</p>
      {(props.mode === "brush" || props.mode === "erase") && (
        <div className="row">
          <span className="small muted">Кисть:</span>
          <div className="seg small">
            {[0, 1, 2].map((n) => (
              <button key={n} className={props.size === n ? "on" : ""} onClick={() => props.onSize(n)}>
                {n === 0 ? "1 клетка" : n === 1 ? "7 клеток" : "19 клеток"}
              </button>
            ))}
          </div>
        </div>
      )}
      <h4>Код препятствия</h4>
      <div className="codes">
        {Object.entries(codes)
          .sort(([a], [b]) => (a === "f" ? -1 : b === "f" ? 1 : a.localeCompare(b)))
          .map(([c, text]) => (
          <label key={c} className="check">
            <input type="radio" name="wallcode" checked={props.code === c} onChange={() => props.onCode(c)} />
            <i className="sw" style={{ background: WALL_COLOURS[c] || "rgba(150,150,150,.5)" }} />
            <b className="mono">{c}</b> {text}
            {counts[c] ? <span className="muted small"> · {counts[c]}</span> : null}
          </label>
        ))}
      </div>
      <p className="small muted">Новые стены — код f. Остальные коды оригинала сохраняются как есть.</p>
    </div>
  );
}

const SIDES: { id: ExitSide; label: string }[] = [
  { id: "auto", label: "По краю (сама)" },
  { id: "W", label: "Запад" },
  { id: "N", label: "Север" },
  { id: "E", label: "Восток" },
  { id: "S", label: "Юг" },
  { id: "a", label: "Дверь a" },
  { id: "b", label: "Дверь b" },
];

export function ExitsPanel(props: {
  model: Model;
  side: ExitSide;
  onSide: (s: ExitSide) => void;
  erase: boolean;
  onErase: (v: boolean) => void;
  onRing: () => void;
  readOnly: boolean;
}) {
  const counts: Record<string, number> = {};
  for (const e of props.model.exits) counts[e[2]] = (counts[e[2]] || 0) + 1;
  return (
    <div className="tool-panel">
      <div className="seg">
        <button className={!props.erase ? "on" : ""} onClick={() => props.onErase(false)}>
          Кисть
        </button>
        <button className={props.erase ? "on" : ""} onClick={() => props.onErase(true)}>
          Ластик
        </button>
      </div>
      <h4>Куда выводит</h4>
      <div className="codes">
        {SIDES.map((s) => (
          <label key={s.id} className="check">
            <input type="radio" name="exitside" checked={props.side === s.id} onChange={() => props.onSide(s.id)} />
            {s.id !== "auto" && <i className="sw" style={{ background: EXIT_COLOURS[s.id] }} />}
            {s.label}
            {s.id !== "auto" && counts[s.id] ? <span className="muted small"> · {counts[s.id]}</span> : null}
          </label>
        ))}
      </div>
      <p className="hint">
        Выход у края ведёт на соседнюю клетку карты: «по краю» сама берёт сторону от ближайшего края. В глубине локации выход —
        дверь a или b; куда она ведёт, задаётся в «Проходах».
      </p>
      <button disabled={props.readOnly} onClick={props.onRing}>
        Кольцо выходов и входов по краям
      </button>
    </div>
  );
}

export function EntriesPanel(props: { model: Model; war: boolean }) {
  const n = props.war ? props.model.war_entries.length : props.model.entries.length;
  return (
    <div className="tool-panel">
      <p className="hint">
        {props.war
          ? "Военные входы: где появляется игрок, когда локация военная (war). Щелчок по клетке ставит вход или убирает его; можно вести мышью."
          : "Входы: клетки, где появляется пришедший в локацию. Щелчок по клетке ставит вход или убирает его; можно вести мышью. Нужен хотя бы один свободный."}
      </p>
      <p>
        {props.war ? "Военных входов" : "Входов"}: <b>{n}</b>
      </p>
      {props.war && props.model.attrs.war !== "1" && (
        <p className="small muted">Локация мирная (war = 0): военные входы сервер не использует.</p>
      )}
    </div>
  );
}
