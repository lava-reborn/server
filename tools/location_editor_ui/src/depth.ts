// The order the client draws sprites in: tools/lavaloc.py depth_sort and
// walker_index, ported line by line (LDepthManager.zSort, getCollision and
// listZSort; Array.sortOn as AVM1 does it). The Python side was checked
// against the real Flash Player 32; this is the same arithmetic in the
// same doubles.
import { frontCells } from "./hex";
import type { Cell, Sprite } from "./types";

export function avm1Sort<T>(items: T[], key: (t: T) => number): T[] {
  const a = items.slice();
  const stack: [number, number][] = [[0, a.length - 1]];
  while (stack.length) {
    const [lo, hi] = stack.pop()!;
    if (lo >= hi) continue;
    const p = key(a[lo]);
    let i = lo;
    let j = hi + 1;
    for (;;) {
      i += 1;
      while (i <= hi && key(a[i]) < p) i += 1;
      j -= 1;
      while (j > lo && key(a[j]) >= p) j -= 1;
      if (j < i) break;
      const t = a[i];
      a[i] = a[j];
      a[j] = t;
    }
    const t = a[lo];
    a[lo] = a[j];
    a[j] = t;
    stack.push([j + 1, hi]);
    stack.push([lo, j - 1]);
  }
  return a;
}

export interface SceneObj {
  sprite: number | null; // null: a walker (an inhabitant)
  anchor: number;
  point: Cell;
  front: Cell[];
  left: Cell | null;
  right: Cell | null;
  minD: number;
  turned: boolean;
}

function sceneObj(sprite: number | null, anchor: number, point: Cell, front: Cell[]): SceneObj {
  let f = front;
  if (f.length > 1) f = avm1Sort(f, (c) => c[0]);
  if (f.length === 1) f = [point];
  return {
    sprite,
    anchor,
    point,
    front: f,
    left: f.length ? f[0] : null,
    right: f.length ? f[f.length - 1] : null,
    minD: 1,
    turned: false,
  };
}

/** The sprite instances in the displayList order of the client (its
 * for..in walk runs the <sprite> elements from the last to the first). */
export function sceneObjects(sprites: Sprite[]): SceneObj[] {
  const out: SceneObj[] = [];
  for (let si = sprites.length - 1; si >= 0; si--) {
    const sp = sprites[si];
    sp.anchors.forEach(([ax, ay], ai) => {
      out.push(sceneObj(si, ai, [ax, ay], frontCells(sp.front, ax, ay)));
    });
  }
  return out;
}

function firstY(front: Cell[], x: number): number | null {
  for (const c of front) if (c[0] === x) return c[1];
  return null;
}

function collision(obj: SceneObj, other: SceneObj): number {
  const L = obj.left;
  const R = obj.right;
  const L2 = other.left;
  const R2 = other.right;
  if (!L || !L2 || !R || !R2) return 0;
  if (L2[0] > R[0] || R2[0] < L[0]) return 0;
  if (L2[0] <= L[0] && L[0] <= R2[0]) {
    const y = firstY(other.front, L[0]);
    return y !== null && L[1] > y ? 1 : -1;
  }
  if (L[0] <= L2[0] && L2[0] <= R[0]) {
    const y = firstY(obj.front, L2[0]);
    return y !== null && y > L2[1] ? 1 : -1;
  }
  return 0;
}

/** LDepthManager.zSort: the objects in drawing order, the last on top. */
export function depthSort(objs: SceneObj[]): SceneObj[] {
  const n = objs.length;
  for (const start of objs) {
    if (start.minD !== 1 || start.turned) continue;
    start.turned = true;
    const stack: [SceneObj, number, SceneObj | null][] = [[start, 0, null]];
    while (stack.length) {
      const fr = stack[stack.length - 1];
      const o = fr[0];
      if (fr[2] !== null) {
        o.minD += fr[2].minD;
        fr[2] = null;
      }
      if (fr[1] >= n) {
        stack.pop();
        continue;
      }
      const other = objs[fr[1]];
      fr[1] += 1;
      if (other === o || collision(o, other) <= 0) continue;
      if (other.minD === 1 && !other.turned) {
        other.turned = true;
        fr[2] = other;
        stack.push([other, 0, null]);
      } else {
        o.minD += other.minD;
      }
    }
  }
  return avm1Sort(objs, (o) => o.minD);
}

/** Where a walker standing on (gx, gy) goes among objects in drawing order. */
export function walkerIndex(drawn: SceneObj[], gx: number, gy: number): number {
  for (let i = drawn.length - 1; i >= 0; i--) {
    const o = drawn[i];
    if (!o.left || !o.right) continue;
    if (o.left[0] > gx || o.right[0] < gx) continue;
    const y = firstY(o.front, gx);
    if (y !== null && gy > y) return i + 1;
  }
  return 0;
}

/** The sprites and the walkers (inhabitants, by index) in drawing order. */
export function drawOrder(sprites: Sprite[], walkers: Cell[]): SceneObj[] {
  const drawn = depthSort(sceneObjects(sprites));
  walkers.forEach((c, i) => {
    const w: SceneObj = { sprite: null, anchor: i, point: c, front: [c], left: c, right: c, minD: 0, turned: false };
    drawn.splice(walkerIndex(drawn, c[0], c[1]), 0, w);
  });
  return drawn;
}
