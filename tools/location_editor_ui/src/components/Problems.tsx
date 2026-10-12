import type { Problem } from "../types";
import { Spinner } from "./ui";

const WHAT: Record<string, string> = {
  id: "номер",
  size: "размер",
  title: "название",
  fn: "fn",
  pvp: "pvp",
  war: "war",
  bgsound: "музыка",
  library: "библиотека",
  why: "почему",
  art: "графика",
  walls: "стены",
  exits: "выходы",
  entries: "входы",
  war_entries: "военные входы",
  sprites: "объекты",
  spawns: "существа файла",
  inhabitants: "жители",
  doors: "двери",
  ways: "пути",
  walk_in: "проход",
  map: "карта",
  zones: "zones",
  walk: "обход",
  model: "модель",
  server: "сервер",
};

// «Проблемы»: what the checks say, errors first; a click shows the place.
export default function Problems(props: {
  problems: Problem[];
  checking: boolean;
  full: boolean;
  seconds: number | null;
  selected: number | null;
  onPick: (p: Problem, i: number) => void;
}) {
  const list = props.problems
    .map((p, i) => ({ p, i }))
    .sort((a, b) => (a.p.level === b.p.level ? a.i - b.i : a.p.level === "error" ? -1 : 1));
  const errors = props.problems.filter((p) => p.level === "error").length;
  const warnings = props.problems.length - errors;
  return (
    <section className="problems">
      <header>
        <h3>Проблемы</h3>
        {errors > 0 && <span className="count err">{errors} ошиб.</span>}
        {warnings > 0 && <span className="count warn">{warnings} предупр.</span>}
        {!props.checking && !props.problems.length && <span className="count good">всё в порядке</span>}
        <span className="grow" />
        {props.checking ? (
          <span className="small muted">
            <Spinner /> проверяю
          </span>
        ) : (
          <span className="small muted" title={props.full ? "с проверками сервера" : "быстрая проверка на каждую правку"}>
            {props.full ? "полная" : "быстрая"}
            {props.seconds !== null ? ` · ${props.seconds} с` : ""}
          </span>
        )}
      </header>
      <ul>
        {list.map(({ p, i }) => (
          <li
            key={i}
            className={`${p.level}${props.selected === i ? " sel" : ""}${p.cells.length || p.loc !== null || p.what === "map" ? " jump" : ""}`}
            onClick={() => props.onPick(p, i)}
            title={p.cells.length ? "Показать на карте локации" : undefined}
          >
            <span className={`lvl ${p.level}`}>{p.level === "error" ? "ошибка" : "внимание"}</span>
            <span className="what">{WHAT[p.what] || p.what}</span>
            <span className="text">
              {p.text}
              {p.loc !== null && p.loc !== undefined && <em> (в локации {p.loc})</em>}
              {p.cells.length > 0 && (
                <span className="cells">
                  {" "}
                  {p.cells
                    .slice(0, 4)
                    .map((c) => `${c[0]}:${c[1]}`)
                    .join(" ")}
                  {p.cells.length > 4 ? ` и ещё ${p.cells.length - 4}` : ""}
                </span>
              )}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
