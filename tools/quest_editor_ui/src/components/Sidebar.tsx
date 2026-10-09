import { useMemo } from "react";
import type { Kind, Row } from "../types";
import { KIND_LABEL } from "../types";
import { creatureName, useLookup } from "../refs";
import { plain } from "../markup";

export interface Filters {
  text: string;
  kind: "" | Kind;
  generated: boolean;
  onlyProblems: boolean;
  off: "all" | "on" | "off";
}

export const NO_FILTERS: Filters = { text: "", kind: "", generated: false, onlyProblems: false, off: "all" };

export function matches(row: Row, f: Filters, lk: ReturnType<typeof useLookup>, hasProblem: (t: number) => boolean): boolean {
  if (f.kind && row.kind !== f.kind) return false;
  if (f.onlyProblems && !hasProblem(row.type)) return false;
  const off = !(row.give || []).length;
  if (f.off === "on" && off) return false;
  if (f.off === "off" && !off) return false;
  const s = f.text.trim().toLowerCase();
  if (!s) return true;
  if (String(row.type) === s || `#${row.type}` === s) return true;
  const hay = [
    plain(row.name),
    ...(row.give || []).map((t) => creatureName(lk, t)),
    ...(row.take || []).map((t) => creatureName(lk, t)),
    ...(row.give || []).flatMap((t) => lk.where(t).map((l) => l.title)),
  ]
    .join(" ")
    .toLowerCase();
  return hay.includes(s);
}

interface Props {
  rows: Row[];
  visible: Row[];
  filters: Filters;
  setFilters: (f: Filters) => void;
  selected: number | null;
  onSelect: (t: number) => void;
  errorsOf: (t: number) => number;
  warnsOf: (t: number) => number;
  generatedCount: number;
}

export function Sidebar({ visible, filters, setFilters, selected, onSelect, errorsOf, warnsOf, generatedCount, rows }: Props) {
  const sorted = useMemo(() => [...visible].sort((a, b) => a.type - b.type), [visible]);
  return (
    <aside className="sidebar">
      <input
        className="wide"
        placeholder="Поиск: название, номер, NPC, локация…"
        value={filters.text}
        onChange={(e) => setFilters({ ...filters, text: e.target.value })}
      />
      <div className="filters">
        <select value={filters.kind} onChange={(e) => setFilters({ ...filters, kind: e.target.value as Filters["kind"] })}>
          <option value="">Все виды</option>
          {(Object.keys(KIND_LABEL) as Kind[]).map((k) => (
            <option key={k} value={k}>
              {KIND_LABEL[k]}
            </option>
          ))}
        </select>
        <select value={filters.off} onChange={(e) => setFilters({ ...filters, off: e.target.value as Filters["off"] })}>
          <option value="all">Включённые и выключенные</option>
          <option value="on">Только включённые</option>
          <option value="off">Только выключенные</option>
        </select>
        <label className="check">
          <input type="checkbox" checked={filters.onlyProblems} onChange={(e) => setFilters({ ...filters, onlyProblems: e.target.checked })} />{" "}
          только с проблемами
        </label>
        <label className="check" title="Ремесло, сеты, производство: их пишут сборщики в data/, здесь только просмотр">
          <input type="checkbox" checked={filters.generated} onChange={(e) => setFilters({ ...filters, generated: e.target.checked })} />{" "}
          сгенерированные ({generatedCount})
        </label>
      </div>
      <div className="muted small">
        Показано {visible.length} из {rows.length + (filters.generated ? generatedCount : 0)}
      </div>
      <div className="qlist">
        {sorted.map((r) => {
          const e = errorsOf(r.type);
          const w = warnsOf(r.type);
          return (
            <div key={r.type} className={"qitem" + (r.type === selected ? " sel" : "")} onClick={() => onSelect(r.type)}>
              <span className={`qdot kind-${r.kind}`} />
              <span className="muted">#{r.type}</span>
              <span className="grow ellipsis">{plain(r.name) || "без названия"}</span>
              {e > 0 && <span className="qbadge err">{e}</span>}
              {!e && w > 0 && <span className="qbadge warn">{w}</span>}
            </div>
          );
        })}
      </div>
    </aside>
  );
}
