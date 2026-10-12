// The location grid, as tools/lavaloc.py has it (the client's own rules):
// "odd-r" hexes, a cell's centre at (40*gx + 20*(gy&1), 15*gy), the canvas
// W*40 x H*15 pixels. Offsets from an anchor are written for an anchor on
// an even row; on an odd anchor row a cell on an odd relative row moves one
// to the right (LDParser.getHexCoord).
import type { Cell } from "./types";

export const CELL_W = 40;
export const ROW_H = 15;
export const HEX: Cell[] = [
  [0, -10],
  [20, -5],
  [20, 5],
  [0, 10],
  [-20, 5],
  [-20, -5],
];

const odd = (n: number) => (n & 1) === 1;

export function cellPx(gx: number, gy: number): [number, number] {
  return [CELL_W * gx + (odd(gy) ? CELL_W / 2 : 0), ROW_H * gy];
}

/** The cell under a pixel: LocDeclaration.realToGrid, verbatim. */
export function pxCell(x: number, y: number): Cell {
  const cellH = 15;
  const row = Math.floor(y / cellH);
  const d = y - row * cellH - 0.5 * cellH;
  let a: number;
  if (Math.abs(d) > cellH / 6) {
    a = d >= 0 ? 1 : 0;
  } else {
    const x4 = x - 40 * 0.5 * (((row % 2) + 2) % 2);
    const t = 40 * 0.5 - Math.abs(x4 - Math.floor((x4 + 20) / 40) * 40);
    const y9 = y - row * cellH - cellH / 3;
    a = y9 <= Math.abs(t / 4) ? 0 : 1;
  }
  const gy = row + a;
  const gx = Math.floor(x / 40 - 0.5 * (((gy % 2) + 2) % 2) + 0.5);
  return [gx, gy];
}

export function neighbours(gx: number, gy: number): Cell[] {
  const s = odd(gy) ? 1 : -1;
  return [
    [gx - 1, gy],
    [gx + 1, gy],
    [gx, gy - 1],
    [gx, gy + 1],
    [gx + s, gy - 1],
    [gx + s, gy + 1],
  ];
}

/** Offsets (even-row convention) -> absolute cells for an anchor. */
export function offsetsCells(offsets: Cell[], ax: number, ay: number): Cell[] {
  return offsets.map(([dx, dy]) => [ax + dx + (odd(ay) && odd(dy) ? 1 : 0), ay + dy] as Cell);
}

/** A sprite's front template -> absolute cells (lavaloc.front_cells). */
export function frontCells(front: string | null | undefined, ax: number, ay: number): Cell[] {
  const out: Cell[] = [];
  const f = front || "";
  for (let i = 0; i + 3 < f.length; i += 4) {
    const bx = parseInt(f.slice(i, i + 2), 16);
    const by = parseInt(f.slice(i + 2, i + 4), 16);
    const par = odd(ay) && odd(by) ? 1 : 0;
    out.push([bx + ax - 128 + par, by + ay - 128]);
  }
  return out;
}

/** The pixel of a cell relative to the anchor cell's centre, for an anchor
 * on an even row (the objects' own picture grid). */
export function offsetPx(dx: number, dy: number): [number, number] {
  return [CELL_W * dx + (odd(dy) ? CELL_W / 2 : 0), ROW_H * dy];
}

export const key = (x: number, y: number) => `${x},${y}`;

export function inGrid(c: Cell, w: number, h: number) {
  return c[0] >= 0 && c[0] < w && c[1] >= 0 && c[1] < h;
}

/** Cells within `r` steps of a cell (a round brush). */
export function disc(c: Cell, r: number): Cell[] {
  const seen = new Set<string>([key(c[0], c[1])]);
  let ring: Cell[] = [c];
  const out: Cell[] = [c];
  for (let i = 0; i < r; i++) {
    const next: Cell[] = [];
    for (const [x, y] of ring) {
      for (const n of neighbours(x, y)) {
        const k = key(n[0], n[1]);
        if (!seen.has(k)) {
          seen.add(k);
          next.push(n);
          out.push(n);
        }
      }
    }
    ring = next;
  }
  return out;
}

/** The cells whose centres lie in the pixel box spanned by two cells. */
export function rectCells(a: Cell, b: Cell, w: number, h: number): Cell[] {
  const [ax, ay] = cellPx(a[0], a[1]);
  const [bx, by] = cellPx(b[0], b[1]);
  const x0 = Math.min(ax, bx) - 1;
  const x1 = Math.max(ax, bx) + 1;
  const y0 = Math.min(ay, by);
  const y1 = Math.max(ay, by);
  const out: Cell[] = [];
  for (let gy = Math.max(0, Math.min(a[1], b[1])); gy <= Math.min(h - 1, Math.max(a[1], b[1])); gy++) {
    for (let gx = 0; gx < w; gx++) {
      const [px, py] = cellPx(gx, gy);
      if (px >= x0 && px <= x1 && py >= y0 && py <= y1) out.push([gx, gy]);
    }
  }
  return out;
}
