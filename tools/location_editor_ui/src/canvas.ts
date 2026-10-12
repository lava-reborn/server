// The location canvas: a plain TS module, no React inside, so it can move
// into any page later as it is. It draws a model the way the client does:
// the art the server rendered (background and decals, one PNG) under the
// sprites and the inhabitants drawn here in the client's depth order
// (depth.ts), then the cell layers as vector hexes, the selection and the
// tool's marks. It reports pointer events in world pixels and cells; the
// page decides what they mean.
import { drawOrder, type SceneObj } from "./depth";
import { CELL_W, HEX, ROW_H, cellPx, frontCells, pxCell } from "./hex";
import type { Cell, Model, Sprite } from "./types";

export type Layer = "art" | "sprites" | "inhabitants" | "walls" | "exits" | "entries" | "wars" | "spawns" | "grid";
export const ALL_LAYERS: Layer[] = ["art", "sprites", "inhabitants", "walls", "exits", "entries", "wars", "spawns", "grid"];

export interface SpriteArt {
  url: string;
  ox: number;
  oy: number;
}

export interface PointerInfo {
  kind: "down" | "move" | "up";
  cell: Cell;
  px: [number, number];
  shift: boolean;
  alt: boolean;
  ctrl: boolean;
}

export interface Mark {
  cells: Cell[];
  fill?: string;
  stroke?: string;
  width?: number;
  /** a circle of this many screen pixels round each cell, seen at any zoom */
  ring?: number;
}

export interface Ghost {
  url: string;
  x: number;
  y: number;
}

interface Handlers {
  pointer?: (p: PointerInfo) => void;
  hover?: (cell: Cell | null, px: [number, number] | null) => void;
  view?: (zoom: number) => void;
}

export const ZOOM_MIN = 0.25;
export const ZOOM_MAX = 2;

export const WALL_COLOURS: Record<string, string> = {
  f: "rgba(226,64,48,0.3)",
  "1": "rgba(240,210,40,0.42)",
  "3": "rgba(240,140,30,0.42)",
  "7": "rgba(170,90,255,0.42)",
};
export const EXIT_COLOURS: Record<string, string> = {
  W: "rgba(70,150,255,0.55)",
  N: "rgba(70,200,255,0.55)",
  E: "rgba(110,120,255,0.55)",
  S: "rgba(40,110,220,0.55)",
  a: "rgba(0,230,230,0.62)",
  b: "rgba(255,70,210,0.6)",
};
export const ENTRY_COLOUR = "rgba(80,230,110,0.55)";
export const WAR_COLOUR = "rgba(20,140,60,0.7)";

// pictures, shared by every canvas of the page
const images = new Map<string, HTMLImageElement>();
const waiting = new Set<() => void>();
let epoch = 0; // counts the pictures that came in: a kept scene is drawn again
export const onImage = (fn: () => void) => waiting.add(fn);
export const offImage = (fn: () => void) => waiting.delete(fn);
export function image(url: string): HTMLImageElement | null {
  let img = images.get(url);
  if (!img) {
    img = new Image();
    img.decoding = "async";
    img.onload = img.onerror = () => {
      epoch++;
      waiting.forEach((fn) => fn());
    };
    img.src = url;
    images.set(url, img);
  }
  return img.complete && img.naturalWidth > 0 ? img : null;
}

function hexPath(ctx: CanvasRenderingContext2D, x: number, y: number) {
  const [cx, cy] = cellPx(x, y);
  ctx.moveTo(cx + HEX[0][0], cy + HEX[0][1]);
  for (let i = 1; i < 6; i++) ctx.lineTo(cx + HEX[i][0], cy + HEX[i][1]);
  ctx.closePath();
}

export class LocCanvas {
  readonly el: HTMLCanvasElement;
  private host: HTMLElement;
  private ctx: CanvasRenderingContext2D;
  private h: Handlers;
  private model: Model | null = null;
  private bgUrl: string | null = null;
  private bgScale = 1;
  private art: (sp: Sprite) => SpriteArt | null = () => null;
  private icon: (type: number) => string | null = () => null;
  layers = new Set<Layer>(ALL_LAYERS);
  /** a left drag pans (for tools that do nothing on the canvas) */
  panLeft = false;
  zoom = 0.5;
  panX = 0;
  panY = 0;
  private selSprite: [number, number] | null = null;
  private selInhabitant: number | null = null;
  private marks: Mark[] = [];
  private ghost: Ghost | null = null;
  private drag: { sprite: [number, number]; dx: number; dy: number } | null = null;
  private hoverCell: Cell | null = null;
  private order: SceneObj[] = [];
  private orderOf: [unknown, unknown] = [null, null];
  private scene: HTMLCanvasElement | null = null;
  private sceneKey: unknown[] | null = null;
  private overlay: HTMLCanvasElement | null = null;
  private overlayKey: unknown[] | null = null;
  private frame = 0;
  private panning: { x: number; y: number; px: number; py: number } | null = null;
  private down = false;
  private space = false;
  private ro: ResizeObserver;
  private redraw = () => this.request();
  private probe = document.createElement("canvas");

  constructor(host: HTMLElement, handlers: Handlers = {}) {
    this.host = host;
    this.h = handlers;
    this.el = document.createElement("canvas");
    this.el.className = "loc-canvas";
    this.el.tabIndex = 0;
    host.appendChild(this.el);
    this.ctx = this.el.getContext("2d")!;
    this.probe.width = this.probe.height = 1;
    waiting.add(this.redraw);
    this.ro = new ResizeObserver(() => this.resize());
    this.ro.observe(host);
    this.el.addEventListener("pointerdown", this.onDown);
    this.el.addEventListener("pointermove", this.onMove);
    this.el.addEventListener("pointerup", this.onUp);
    this.el.addEventListener("pointercancel", this.onUp);
    this.el.addEventListener("pointerleave", this.onLeave);
    this.el.addEventListener("wheel", this.onWheel, { passive: false });
    this.el.addEventListener("contextmenu", (e) => e.preventDefault());
    window.addEventListener("keydown", this.onKey);
    window.addEventListener("keyup", this.onKey);
    this.resize();
  }

  destroy() {
    waiting.delete(this.redraw);
    this.ro.disconnect();
    window.removeEventListener("keydown", this.onKey);
    window.removeEventListener("keyup", this.onKey);
    cancelAnimationFrame(this.frame);
    this.el.remove();
  }

  // --- what is drawn ------------------------------------------------------------
  setModel(m: Model | null) {
    this.model = m;
    this.request();
  }
  setBackground(url: string | null, scale = 1) {
    this.bgUrl = url;
    this.bgScale = scale;
    this.request();
  }
  setArt(fn: (sp: Sprite) => SpriteArt | null) {
    this.art = fn;
    this.request();
  }
  setIcons(fn: (type: number) => string | null) {
    this.icon = fn;
    this.request();
  }
  setLayers(l: Set<Layer>) {
    this.layers = new Set(l);
    this.request();
  }
  setSelection(sprite: [number, number] | null, inhabitant: number | null = null) {
    this.selSprite = sprite;
    this.selInhabitant = inhabitant;
    this.request();
  }
  setMarks(marks: Mark[]) {
    this.marks = marks;
    this.request();
  }
  setGhost(g: Ghost | null) {
    this.ghost = g;
    this.request();
  }
  setDrag(d: { sprite: [number, number]; dx: number; dy: number } | null) {
    this.drag = d;
    this.request();
  }
  setCursor(c: string) {
    this.el.style.cursor = c;
  }

  // --- the view -------------------------------------------------------------------
  private size(): [number, number] {
    return [this.host.clientWidth, this.host.clientHeight];
  }
  private world(): [number, number] {
    const m = this.model;
    return m ? [m.width * CELL_W, m.height * ROW_H] : [CELL_W * 32, ROW_H * 64];
  }
  zoomTo(z: number, around?: [number, number]) {
    const [w, h] = this.size();
    const [sx, sy] = around || [w / 2, h / 2];
    const nz = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, z));
    const wx = (sx - this.panX) / this.zoom;
    const wy = (sy - this.panY) / this.zoom;
    this.zoom = nz;
    this.panX = sx - wx * nz;
    this.panY = sy - wy * nz;
    this.h.view?.(nz);
    this.request();
  }
  fit() {
    const [w, h] = this.size();
    const [ww, wh] = this.world();
    const z = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, Math.min((w - 24) / ww, (h - 24) / wh)));
    this.zoom = z;
    this.panX = (w - ww * z) / 2;
    this.panY = (h - wh * z) / 2;
    this.h.view?.(z);
    this.request();
  }
  centerOn(c: Cell, zoom?: number) {
    if (zoom) this.zoom = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, zoom));
    const [w, h] = this.size();
    const [x, y] = cellPx(c[0], c[1]);
    this.panX = w / 2 - x * this.zoom;
    this.panY = h / 2 - y * this.zoom;
    this.h.view?.(this.zoom);
    this.request();
  }
  private resize() {
    const dpr = window.devicePixelRatio || 1;
    const [w, h] = this.size();
    this.el.width = Math.max(1, Math.round(w * dpr));
    this.el.height = Math.max(1, Math.round(h * dpr));
    this.el.style.width = `${w}px`;
    this.el.style.height = `${h}px`;
    this.request();
  }
  toWorld(sx: number, sy: number): [number, number] {
    return [(sx - this.panX) / this.zoom, (sy - this.panY) / this.zoom];
  }

  // --- pointer --------------------------------------------------------------------
  private info(e: PointerEvent, kind: PointerInfo["kind"]): PointerInfo {
    const r = this.el.getBoundingClientRect();
    const px = this.toWorld(e.clientX - r.left, e.clientY - r.top);
    return { kind, px, cell: pxCell(px[0], px[1]), shift: e.shiftKey, alt: e.altKey, ctrl: e.ctrlKey || e.metaKey };
  }
  private onKey = (e: KeyboardEvent) => {
    if (e.code !== "Space") return;
    const t = e.target as HTMLElement | null;
    if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT")) return;
    this.space = e.type === "keydown";
    if (this.space && document.activeElement === this.el) e.preventDefault();
  };
  private onDown = (e: PointerEvent) => {
    this.el.focus({ preventScroll: true });
    if (e.button === 1 || e.button === 2 || (e.button === 0 && (this.space || this.panLeft))) {
      this.panning = { x: e.clientX, y: e.clientY, px: this.panX, py: this.panY };
      this.el.setPointerCapture(e.pointerId);
      this.el.style.cursor = "grabbing";
      e.preventDefault();
      return;
    }
    if (e.button !== 0) return;
    this.down = true;
    this.el.setPointerCapture(e.pointerId);
    this.h.pointer?.(this.info(e, "down"));
  };
  private onMove = (e: PointerEvent) => {
    if (this.panning) {
      this.panX = this.panning.px + (e.clientX - this.panning.x);
      this.panY = this.panning.py + (e.clientY - this.panning.y);
      this.request();
      return;
    }
    const p = this.info(e, "move");
    const c = p.cell;
    if (!this.hoverCell || this.hoverCell[0] !== c[0] || this.hoverCell[1] !== c[1]) {
      this.hoverCell = c;
      this.request();
    }
    this.h.hover?.(c, p.px);
    if (this.down) this.h.pointer?.(p);
  };
  private onUp = (e: PointerEvent) => {
    if (this.panning) {
      this.panning = null;
      this.el.style.cursor = "";
      return;
    }
    if (!this.down) return;
    this.down = false;
    this.h.pointer?.(this.info(e, "up"));
  };
  private onLeave = () => {
    if (this.down || this.panning) return;
    this.hoverCell = null;
    this.h.hover?.(null, null);
    this.request();
  };
  private onWheel = (e: WheelEvent) => {
    e.preventDefault();
    const r = this.el.getBoundingClientRect();
    const f = Math.exp(-Math.sign(e.deltaY) * Math.min(Math.abs(e.deltaY), 120) * 0.0016);
    this.zoomTo(this.zoom * f, [e.clientX - r.left, e.clientY - r.top]);
  };

  // --- hit testing ----------------------------------------------------------------
  private spriteBox(si: number, ai: number): { x: number; y: number; img: HTMLImageElement | null; w: number; h: number } {
    const m = this.model!;
    const sp = m.sprites[si];
    const [ax, ay] = sp.anchors[ai];
    // An anchor off the client's grid (the extra row y == H) has no cell
    // there: the client sets no position and adds dx, dy to the location's
    // top-left corner (LocBuilder, LocationGrid.getCellFromGrid undefined).
    const onGrid = ax >= 0 && ay >= 0 && ax < m.width && ay < m.height;
    const [cx, cy] = onGrid ? cellPx(ax, ay) : [0, 0];
    const a = this.art(sp);
    let x = cx + Number(sp.dx || 0);
    let y = cy + Number(sp.dy || 0);
    if (a && sp.type === "ext") {
      x += a.ox;
      y += a.oy;
    }
    const img = a ? image(a.url) : null;
    if (this.drag && this.drag.sprite[0] === si && this.drag.sprite[1] === ai) {
      x += this.drag.dx;
      y += this.drag.dy;
    }
    if (!img) return { x: cx - 14, y: cy - 34, img: null, w: 28, h: 38 };
    return { x: Math.round(x), y: Math.round(y), img, w: img.naturalWidth, h: img.naturalHeight };
  }
  /** The topmost sprite instance whose picture has a pixel under px. */
  hitSprite(px: [number, number]): [number, number] | null {
    if (!this.model || !this.layers.has("sprites")) return null;
    const pctx = this.probe.getContext("2d", { willReadFrequently: true })!;
    for (let i = this.order.length - 1; i >= 0; i--) {
      const o = this.order[i];
      if (o.sprite === null) continue;
      if (!this.model.sprites[o.sprite] || !this.model.sprites[o.sprite].anchors[o.anchor]) continue;
      const b = this.spriteBox(o.sprite, o.anchor);
      if (px[0] < b.x || px[1] < b.y || px[0] >= b.x + b.w || px[1] >= b.y + b.h) continue;
      if (!b.img) return [o.sprite, o.anchor];
      pctx.clearRect(0, 0, 1, 1);
      pctx.drawImage(b.img, Math.floor(b.x - px[0]), Math.floor(b.y - px[1]));
      try {
        if (pctx.getImageData(0, 0, 1, 1).data[3] > 24) return [o.sprite, o.anchor];
      } catch {
        return [o.sprite, o.anchor];
      }
    }
    return null;
  }

  // --- drawing --------------------------------------------------------------------
  // Two pictures at the location's own size are kept between frames and
  // drawn whole, so that a pan or a zoom costs two drawImage calls: the
  // scene (the ground, the sprites and the walkers in depth order) and the
  // cell layers. The scene is made again when the sprites, the walkers,
  // the art or a picture that came in change; the cell layers when their
  // lists change. Zoomed in to 100 % and more the cell layers are drawn as
  // vectors instead, crisp, and only the cells in view.
  request() {
    if (this.frame) return;
    this.frame = requestAnimationFrame(() => {
      this.frame = 0;
      this.draw();
    });
  }

  private ensureOrder() {
    const m = this.model!;
    if (this.orderOf[0] === m.sprites && this.orderOf[1] === m.inhabitants) return;
    const walkers = (m.inhabitants || []).map((r) => [Number(r.cell[0]), Number(r.cell[1])] as Cell);
    this.order = drawOrder(m.sprites || [], walkers);
    this.orderOf = [m.sprites, m.inhabitants];
  }

  private sized(c: HTMLCanvasElement | null): HTMLCanvasElement {
    const [ww, wh] = this.world();
    const out = c || document.createElement("canvas");
    if (out.width !== ww || out.height !== wh) {
      out.width = ww;
      out.height = wh;
    }
    return out;
  }

  private same(a: unknown[], b: unknown[] | null) {
    return !!b && a.length === b.length && a.every((v, i) => v === b[i]);
  }

  private sceneCanvas(): HTMLCanvasElement {
    const m = this.model!;
    const L = this.layers;
    const dragged = this.drag ? this.drag.sprite.join(":") : "";
    const k = [m.sprites, m.inhabitants, this.bgUrl, this.bgScale, this.art, this.icon, epoch, dragged,
      L.has("art"), L.has("sprites"), L.has("inhabitants"), this.selInhabitant];
    if (this.scene && this.same(k, this.sceneKey)) return this.scene;
    this.sceneKey = k;
    const c = (this.scene = this.sized(this.scene));
    const ctx = c.getContext("2d")!;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    const [ww, wh] = this.world();
    const bg = L.has("art") && this.bgUrl ? image(this.bgUrl) : null;
    if (bg) {
      ctx.clearRect(0, 0, ww, wh);
      ctx.drawImage(bg, 0, 0, bg.naturalWidth / this.bgScale, bg.naturalHeight / this.bgScale);
    } else {
      ctx.fillStyle = "#26211c";
      ctx.fillRect(0, 0, ww, wh);
    }
    if (L.has("sprites") || L.has("inhabitants")) {
      this.ensureOrder();
      for (const o of this.order) {
        if (o.sprite === null) {
          if (!L.has("inhabitants")) continue;
          const r = m.inhabitants[o.anchor];
          if (r) this.drawWalker(ctx, Number(r.type), o.point, o.anchor === this.selInhabitant, 1);
          continue;
        }
        if (!L.has("sprites")) continue;
        if (!m.sprites[o.sprite] || !m.sprites[o.sprite].anchors[o.anchor]) continue;
        if (`${o.sprite}:${o.anchor}` === dragged) continue;
        this.drawSprite(ctx, o.sprite, o.anchor, 1);
      }
    }
    return c;
  }

  private drawSprite(ctx: CanvasRenderingContext2D, si: number, ai: number, z: number) {
    const b = this.spriteBox(si, ai);
    if (b.img) {
      ctx.drawImage(b.img, b.x, b.y);
      return;
    }
    ctx.fillStyle = "rgba(127,160,176,0.35)";
    ctx.strokeStyle = "rgba(127,160,176,0.9)";
    ctx.lineWidth = 1 / z;
    ctx.fillRect(b.x, b.y, b.w, b.h);
    ctx.strokeRect(b.x, b.y, b.w, b.h);
  }

  private overlayCanvas(): HTMLCanvasElement {
    const m = this.model!;
    const L = this.layers;
    const k = [m.walls, m.exits, m.entries, m.war_entries, m.spawns, m.width, m.height,
      L.has("walls"), L.has("exits"), L.has("entries"), L.has("wars"), L.has("spawns"), L.has("grid")];
    if (this.overlay && this.same(k, this.overlayKey)) return this.overlay;
    this.overlayKey = k;
    const c = (this.overlay = this.sized(this.overlay));
    const ctx = c.getContext("2d")!;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, c.width, c.height);
    this.drawCells(ctx, 1, [0, m.width - 1, 0, m.height]);
    return c;
  }

  /** The cell layers within [gx0, gx1, gy0, gy1], line widths for zoom z. */
  private drawCells(ctx: CanvasRenderingContext2D, z: number, r: [number, number, number, number]) {
    const m = this.model!;
    const L = this.layers;
    const [gx0, gx1, gy0, gy1] = r;
    const vis = (x: number, y: number) => x >= gx0 && x <= gx1 && y >= gy0 && y <= gy1;
    const fillCells = (cells: Iterable<[number, number, ...unknown[]]>, colour: (c: [number, number, ...unknown[]]) => string) => {
      const groups = new Map<string, Path2D>();
      for (const c of cells) {
        const x = Number(c[0]);
        const y = Number(c[1]);
        if (!vis(x, y)) continue;
        const col = colour(c);
        let p = groups.get(col);
        if (!p) groups.set(col, (p = new Path2D()));
        const [cx, cy] = cellPx(x, y);
        p.moveTo(cx + HEX[0][0], cy + HEX[0][1]);
        for (let i = 1; i < 6; i++) p.lineTo(cx + HEX[i][0], cy + HEX[i][1]);
        p.closePath();
      }
      groups.forEach((p, col) => {
        ctx.fillStyle = col;
        ctx.fill(p);
      });
    };
    if (L.has("grid")) {
      ctx.beginPath();
      for (let y = Math.max(0, gy0); y <= Math.min(m.height - 1, gy1); y++)
        for (let x = Math.max(0, gx0); x <= Math.min(m.width - 1, gx1); x++) hexPath(ctx, x, y);
      ctx.strokeStyle = "rgba(255,255,255,0.13)";
      ctx.lineWidth = 1 / z;
      ctx.stroke();
    }
    if (L.has("walls")) fillCells(m.walls, (c) => WALL_COLOURS[String(c[2])] || "rgba(150,150,150,0.5)");
    if (L.has("exits")) fillCells(m.exits, (c) => EXIT_COLOURS[String(c[2])] || "rgba(0,120,255,0.5)");
    if (L.has("entries")) fillCells(m.entries as [number, number][], () => ENTRY_COLOUR);
    if (L.has("wars")) {
      ctx.beginPath();
      for (const [x, y] of m.war_entries) if (vis(x, y)) hexPath(ctx, x, y);
      ctx.strokeStyle = WAR_COLOUR;
      ctx.lineWidth = Math.max(2, 2 / z);
      ctx.stroke();
      ctx.fillStyle = "rgba(20,140,60,0.25)";
      ctx.fill();
    }
    if (L.has("spawns")) {
      ctx.beginPath();
      for (const [x, y, t] of m.spawns) if (t && vis(x, y)) hexPath(ctx, x, y);
      ctx.strokeStyle = "rgba(255,0,255,0.9)";
      ctx.lineWidth = Math.max(1.5, 1.5 / z);
      ctx.stroke();
    }
  }

  private draw() {
    const ctx = this.ctx;
    const dpr = window.devicePixelRatio || 1;
    const [w, h] = this.size();
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.fillStyle = "#0f0d0b";
    ctx.fillRect(0, 0, w, h);
    const m = this.model;
    if (!m) return;
    const z = this.zoom;
    ctx.setTransform(dpr * z, 0, 0, dpr * z, dpr * this.panX, dpr * this.panY);
    const [ww, wh] = this.world();
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = z < 1 ? "medium" : "low";

    ctx.drawImage(this.sceneCanvas(), 0, 0);
    ctx.strokeStyle = "rgba(239,232,217,0.35)";
    ctx.lineWidth = 1 / z;
    ctx.strokeRect(0, 0, ww, wh);
    if (this.drag && this.layers.has("sprites")) {
      ctx.globalAlpha = 0.8;
      this.drawSprite(ctx, this.drag.sprite[0], this.drag.sprite[1], z);
      ctx.globalAlpha = 1;
    }

    // the cells: the kept picture when zoomed out, vectors in view when in
    if (z < 1) {
      ctx.drawImage(this.overlayCanvas(), 0, 0);
    } else {
      const [x0, y0] = this.toWorld(0, 0);
      const [x1, y1] = this.toWorld(w, h);
      this.drawCells(ctx, z, [
        Math.floor(x0 / CELL_W) - 2,
        Math.ceil(x1 / CELL_W) + 2,
        Math.floor(y0 / ROW_H) - 2,
        Math.ceil(y1 / ROW_H) + 2,
      ]);
    }

    // the selection: the picture's box, its anchor cell and its depth line
    if (this.selSprite && m.sprites[this.selSprite[0]] && m.sprites[this.selSprite[0]].anchors[this.selSprite[1]]) {
      const [si, ai] = this.selSprite;
      const sp = m.sprites[si];
      const b = this.spriteBox(si, ai);
      ctx.setLineDash([6 / z, 4 / z]);
      ctx.strokeStyle = "#f0c46a";
      ctx.lineWidth = 1.5 / z;
      ctx.strokeRect(b.x, b.y, b.w, b.h);
      ctx.setLineDash([]);
      let [ax, ay] = sp.anchors[ai];
      if (this.drag) {
        const [cx, cy] = cellPx(ax, ay);
        [ax, ay] = pxCell(cx + this.drag.dx, cy + this.drag.dy);
      }
      ctx.beginPath();
      for (const [fx, fy] of frontCells(sp.front, ax, ay)) hexPath(ctx, fx, fy);
      ctx.strokeStyle = "rgba(240,196,106,0.9)";
      ctx.lineWidth = 1 / z;
      ctx.stroke();
      ctx.beginPath();
      hexPath(ctx, ax, ay);
      ctx.fillStyle = "rgba(240,196,106,0.55)";
      ctx.fill();
    }

    for (const mk of this.marks) {
      ctx.beginPath();
      for (const [x, y] of mk.cells) hexPath(ctx, x, y);
      if (mk.fill) {
        ctx.fillStyle = mk.fill;
        ctx.fill();
      }
      if (mk.stroke) {
        ctx.strokeStyle = mk.stroke;
        ctx.lineWidth = Math.max(1, (mk.width || 2) / z);
        ctx.stroke();
      }
      if (mk.ring && mk.ring / z > 24) {
        ctx.beginPath();
        for (const [x, y] of mk.cells) {
          const [cx, cy] = cellPx(x, y);
          ctx.moveTo(cx + mk.ring / z, cy);
          ctx.arc(cx, cy, mk.ring / z, 0, Math.PI * 2);
        }
        ctx.strokeStyle = mk.stroke || "#f0c46a";
        ctx.lineWidth = 2 / z;
        ctx.stroke();
      }
    }

    if (this.ghost) {
      const g = image(this.ghost.url);
      if (g) {
        ctx.globalAlpha = 0.6;
        ctx.drawImage(g, this.ghost.x, this.ghost.y);
        ctx.globalAlpha = 1;
      }
    }
    if (this.hoverCell) {
      ctx.beginPath();
      hexPath(ctx, this.hoverCell[0], this.hoverCell[1]);
      ctx.strokeStyle = "rgba(255,255,255,0.85)";
      ctx.lineWidth = 1.5 / z;
      ctx.stroke();
    }
  }

  private drawWalker(ctx: CanvasRenderingContext2D, type: number, c: Cell, selected: boolean, z: number) {
    const [cx, cy] = cellPx(c[0], c[1]);
    const url = this.icon(type);
    const img = url ? image(url) : null;
    if (selected) {
      ctx.beginPath();
      hexPath(ctx, c[0], c[1]);
      ctx.fillStyle = "rgba(240,196,106,0.6)";
      ctx.fill();
    }
    if (img) {
      const s = Math.min(1, 56 / Math.max(img.naturalWidth, img.naturalHeight));
      const iw = img.naturalWidth * s;
      const ih = img.naturalHeight * s;
      ctx.drawImage(img, cx - iw / 2, cy + 4 - ih, iw, ih);
    } else {
      ctx.beginPath();
      ctx.arc(cx, cy - 8, 8, 0, Math.PI * 2);
      ctx.fillStyle = "rgba(217,164,65,0.85)";
      ctx.fill();
    }
    if (selected) {
      ctx.strokeStyle = "#f0c46a";
      ctx.lineWidth = 2 / z;
      ctx.beginPath();
      hexPath(ctx, c[0], c[1]);
      ctx.stroke();
    }
  }
}
