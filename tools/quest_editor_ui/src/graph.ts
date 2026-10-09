import dagre from "@dagrejs/dagre";
import type { Pos, Row } from "./types";

export const NODE_W = 270;
export const NODE_H = 132;

export type LinkKind = "need" | "any" | "excl";

export interface Link {
  id: string;
  kind: LinkKind;
  // need/any: from the prerequisite to the quest that needs it.
  // excl: between the two quests that exclude each other (drawn once).
  source: number;
  target: number;
}

// --- the row's chain keys -----------------------------------------------------

export function needs(row: Row): number[] {
  const v = row.need_quest;
  if (v === undefined || v === null || v === 0) return [];
  return (Array.isArray(v) ? v : [v]).map(Number).filter(Boolean);
}

export function anyOf(row: Row): number[] {
  return (row.need_any || []).map(Number).filter(Boolean);
}

export function excludes(row: Row): number[] {
  return (row.excludes || []).map(Number).filter(Boolean);
}

// need_quest is a number when it is one quest, a list when it is more (the
// table's own habit), and absent when it is none.
export function withNeeds(row: Row, list: number[]): Row {
  const r: Row = { ...row };
  const uniq = Array.from(new Set(list));
  if (!uniq.length) delete r.need_quest;
  else r.need_quest = uniq.length === 1 ? uniq[0] : uniq;
  return r;
}

export function withList(row: Row, key: "need_any" | "excludes" | "stay_in", list: number[]): Row {
  const r: Row = { ...row };
  const uniq = Array.from(new Set(list));
  if (!uniq.length) delete r[key];
  else r[key] = uniq;
  return r;
}

export function links(rows: Row[]): Link[] {
  const present = new Set(rows.map((r) => r.type));
  const out: Link[] = [];
  const seenExcl = new Set<string>();
  for (const r of rows) {
    for (const t of needs(r))
      if (present.has(t)) out.push({ id: `need:${t}>${r.type}`, kind: "need", source: t, target: r.type });
    for (const t of anyOf(r))
      if (present.has(t)) out.push({ id: `any:${t}>${r.type}`, kind: "any", source: t, target: r.type });
    for (const t of excludes(r)) {
      if (!present.has(t)) continue;
      const a = Math.min(t, r.type);
      const b = Math.max(t, r.type);
      const key = `${a}~${b}`;
      if (seenExcl.has(key)) continue;
      seenExcl.add(key);
      out.push({ id: `excl:${key}`, kind: "excl", source: a, target: b });
    }
  }
  return out;
}

// Would "target needs source" close a ring? It does when source already needs
// target, however far back.
export function wouldCycle(rows: Row[], source: number, target: number): boolean {
  if (source === target) return true;
  const byType = new Map(rows.map((r) => [r.type, r]));
  const todo = [source];
  const seen = new Set<number>();
  while (todo.length) {
    const t = todo.pop()!;
    if (t === target) return true;
    if (seen.has(t)) continue;
    seen.add(t);
    const r = byType.get(t);
    if (r) todo.push(...needs(r), ...anyOf(r));
  }
  return false;
}

// Remove a quest's type from every chain key of the other rows.
export function forget(rows: Row[], gone: number): Row[] {
  return rows.map((r) => {
    let out = r;
    if (needs(r).includes(gone)) out = withNeeds(out, needs(out).filter((t) => t !== gone));
    if (anyOf(r).includes(gone)) out = withList(out, "need_any", anyOf(out).filter((t) => t !== gone));
    if (excludes(r).includes(gone)) out = withList(out, "excludes", excludes(out).filter((t) => t !== gone));
    return out;
  });
}

// --- layout -----------------------------------------------------------------------

// Every chain laid out top to bottom by dagre, the chains packed in shelves
// from the largest, and the quests that stand alone in a grid below them,
// grouped by who hands them out.
export function autoLayout(rows: Row[], giverName: (row: Row) => string): Record<string, Pos> {
  const all = links(rows);
  const parent = new Map<number, number>();
  const find = (x: number): number => {
    let p = parent.get(x) ?? x;
    if (p !== x) {
      p = find(p);
      parent.set(x, p);
    }
    return p;
  };
  for (const r of rows) parent.set(r.type, r.type);
  for (const l of all) parent.set(find(l.source), find(l.target));
  const groups = new Map<number, Row[]>();
  for (const r of rows) {
    const g = find(r.type);
    if (!groups.has(g)) groups.set(g, []);
    groups.get(g)!.push(r);
  }

  const chains: { w: number; h: number; pos: Record<string, Pos> }[] = [];
  const alone: Row[] = [];
  for (const members of groups.values()) {
    if (members.length < 2) {
      alone.push(members[0]);
      continue;
    }
    const g = new dagre.graphlib.Graph();
    g.setGraph({ rankdir: "TB", nodesep: 40, ranksep: 70, marginx: 0, marginy: 0 });
    g.setDefaultEdgeLabel(() => ({}));
    const inside = new Set(members.map((m) => m.type));
    for (const m of members) g.setNode(String(m.type), { width: NODE_W, height: NODE_H });
    for (const l of all)
      if (l.kind !== "excl" && inside.has(l.source) && inside.has(l.target))
        g.setEdge(String(l.source), String(l.target));
    dagre.layout(g);
    const pos: Record<string, Pos> = {};
    let w = 0;
    let h = 0;
    for (const m of members) {
      const n = g.node(String(m.type));
      pos[String(m.type)] = { x: n.x - NODE_W / 2, y: n.y - NODE_H / 2 };
      w = Math.max(w, n.x + NODE_W / 2);
      h = Math.max(h, n.y + NODE_H / 2);
    }
    chains.push({ w, h, pos });
  }

  chains.sort((a, b) => b.w * b.h - a.w * a.h);
  const out: Record<string, Pos> = {};
  const shelfW = 5200;
  const gap = 120;
  let x = 0;
  let y = 0;
  let rowH = 0;
  for (const c of chains) {
    if (x > 0 && x + c.w > shelfW) {
      x = 0;
      y += rowH + gap;
      rowH = 0;
    }
    for (const [k, p] of Object.entries(c.pos)) out[k] = { x: p.x + x, y: p.y + y };
    x += c.w + gap;
    rowH = Math.max(rowH, c.h);
  }
  y += rowH + gap * 2;

  alone.sort((a, b) => giverName(a).localeCompare(giverName(b), "ru") || a.type - b.type);
  const cols = Math.max(1, Math.floor(shelfW / (NODE_W + 40)));
  alone.forEach((r, i) => {
    out[String(r.type)] = {
      x: (i % cols) * (NODE_W + 40),
      y: y + Math.floor(i / cols) * (NODE_H + 40),
    };
  });
  return out;
}

// Where a quest added now should stand: below the one it continues, or at the
// given point.
export function placeNear(positions: Record<string, Pos>, near: number | null, fallback: Pos): Pos {
  const p = near !== null ? positions[String(near)] : undefined;
  const all = Object.values(positions);
  const free = (c: Pos) =>
    !all.some((q) => Math.abs(q.x - c.x) < NODE_W + 20 && Math.abs(q.y - c.y) < NODE_H + 20);
  // Below the quest it continues, or where the view is; then sideways, then
  // a row further down, until nothing stands there.
  const start = p ? { x: p.x, y: p.y + NODE_H + 70 } : fallback;
  for (let row = 0; row < 12; row++) {
    for (let col = 0; col < 12; col++) {
      for (const sign of col === 0 ? [1] : [1, -1]) {
        const cand = { x: start.x + sign * col * (NODE_W + 40), y: start.y + row * (NODE_H + 50) };
        if (free(cand)) return cand;
      }
    }
  }
  return start;
}
