// The global map as a picker of one cell: the release's tiles, the places
// on it (settlements.json), the retired cells, the camp patrols, the
// starts, and a shade over what cannot be walked or reached. A plain TS
// module like canvas.ts. A click picks a cell; a drag pans; the wheel zooms.
import { image, offImage, onImage } from "./canvas";
import type { Cell, MapInfo } from "./types";

export interface MapHover {
  cell: Cell;
  place: number | null;
  retired: number | null;
  patrol: number | null;
  blocked: boolean;
  reachable: boolean | null;
  labels: string[];
}

function bits(b64: string | null): Uint8Array | null {
  if (!b64) return null;
  const s = atob(b64);
  const out = new Uint8Array(s.length);
  for (let i = 0; i < s.length; i++) out[i] = s.charCodeAt(i);
  return out;
}

export class MapCanvas {
  readonly el: HTMLCanvasElement;
  private host: HTMLElement;
  private ctx: CanvasRenderingContext2D;
  private info: MapInfo;
  private cs: number;
  private x0: number;
  private y0: number;
  private w: number;
  private h: number;
  private blocked: Uint8Array | null;
  private reach: Uint8Array | null;
  private shade: HTMLCanvasElement;
  private labels = new Map<string, string[]>();
  zoom = 0.5;
  panX = 0;
  panY = 0;
  showShade = true;
  private chosen: Cell | null = null;
  private ours: Cell[] = [];
  private hover: Cell | null = null;
  private press: { x: number; y: number; px: number; py: number; moved: boolean } | null = null;
  private frame = 0;
  private ro: ResizeObserver;
  private onPick: (c: Cell) => void;
  private onHover: (h: MapHover | null) => void;
  private redraw = () => this.request();

  constructor(host: HTMLElement, info: MapInfo, onPick: (c: Cell) => void, onHover: (h: MapHover | null) => void) {
    this.host = host;
    this.info = info;
    this.onPick = onPick;
    this.onHover = onHover;
    this.cs = info.cell;
    this.x0 = info.bounds.x[0];
    this.y0 = info.bounds.y[0];
    this.w = info.bounds.x[1] - this.x0 + 1;
    this.h = info.bounds.y[1] - this.y0 + 1;
    this.blocked = bits(info.blocked);
    this.reach = bits(info.reachable);
    for (const [x, y, t] of info.labels) {
      const k = `${x},${y}`;
      const list = this.labels.get(k) || [];
      list.push(t.replace(/<br\s*\/?>/gi, " "));
      this.labels.set(k, list);
    }
    this.shade = document.createElement("canvas");
    this.buildShade();
    this.el = document.createElement("canvas");
    this.el.className = "loc-canvas";
    host.appendChild(this.el);
    this.ctx = this.el.getContext("2d")!;
    this.ro = new ResizeObserver(() => this.resize());
    this.ro.observe(host);
    this.el.addEventListener("pointerdown", this.down);
    this.el.addEventListener("pointermove", this.move);
    this.el.addEventListener("pointerup", this.up);
    this.el.addEventListener("pointerleave", () => {
      this.hover = null;
      this.onHover(null);
      this.request();
    });
    this.el.addEventListener("wheel", this.wheel, { passive: false });
    this.el.addEventListener("contextmenu", (e) => e.preventDefault());
    onImage(this.redraw);
    this.resize();
  }

  destroy() {
    offImage(this.redraw);
    this.ro.disconnect();
    cancelAnimationFrame(this.frame);
    this.el.remove();
  }

  private bit(arr: Uint8Array | null, x: number, y: number): boolean | null {
    if (!arr) return null;
    const n = (y - this.y0) * this.w + (x - this.x0);
    if (n < 0 || n >= this.w * this.h) return null;
    return (arr[n >> 3] & (0x80 >> (n & 7))) !== 0;
  }

  private buildShade() {
    const c = this.shade;
    c.width = this.w;
    c.height = this.h;
    const g = c.getContext("2d")!;
    const img = g.createImageData(this.w, this.h);
    for (let y = 0; y < this.h; y++) {
      for (let x = 0; x < this.w; x++) {
        const i = (y * this.w + x) * 4;
        const blocked = this.bit(this.blocked, x + this.x0, y + this.y0);
        const reach = this.bit(this.reach, x + this.x0, y + this.y0);
        if (blocked) {
          img.data[i] = 8;
          img.data[i + 1] = 6;
          img.data[i + 2] = 5;
          img.data[i + 3] = 150;
        } else if (reach === false) {
          img.data[i] = 226;
          img.data[i + 1] = 84;
          img.data[i + 2] = 58;
          img.data[i + 3] = 70;
        }
      }
    }
    g.putImageData(img, 0, 0);
  }

  setChosen(c: Cell | null) {
    this.chosen = c;
    this.request();
  }
  setOurs(cells: Cell[]) {
    this.ours = cells;
    this.request();
  }
  setShade(on: boolean) {
    this.showShade = on;
    this.request();
  }
  centerOn(c: Cell, zoom?: number) {
    if (zoom) this.zoom = zoom;
    const [w, h] = [this.host.clientWidth, this.host.clientHeight];
    this.panX = w / 2 - ((c[0] - this.x0) * this.cs + this.cs / 2) * this.zoom;
    this.panY = h / 2 - ((c[1] - this.y0) * this.cs + this.cs / 2) * this.zoom;
    this.request();
  }
  zoomBy(f: number, at?: [number, number]) {
    const [w, h] = [this.host.clientWidth, this.host.clientHeight];
    const [sx, sy] = at || [w / 2, h / 2];
    const nz = Math.min(4, Math.max(0.08, this.zoom * f));
    const wx = (sx - this.panX) / this.zoom;
    const wy = (sy - this.panY) / this.zoom;
    this.zoom = nz;
    this.panX = sx - wx * nz;
    this.panY = sy - wy * nz;
    this.request();
  }

  hoverAt(c: Cell): MapHover {
    const k = `${c[0]},${c[1]}`;
    return {
      cell: c,
      place: this.info.settlements[k] ?? null,
      retired: this.info.retired[k] ?? null,
      patrol: this.info.patrols[k] ?? null,
      blocked: !!this.bit(this.blocked, c[0], c[1]),
      reachable: this.bit(this.reach, c[0], c[1]),
      labels: this.labels.get(k) || [],
    };
  }

  private resize() {
    const dpr = window.devicePixelRatio || 1;
    const w = this.host.clientWidth;
    const h = this.host.clientHeight;
    this.el.width = Math.max(1, Math.round(w * dpr));
    this.el.height = Math.max(1, Math.round(h * dpr));
    this.el.style.width = `${w}px`;
    this.el.style.height = `${h}px`;
    this.request();
  }
  private cellAt(e: PointerEvent | WheelEvent): Cell {
    const r = this.el.getBoundingClientRect();
    const wx = (e.clientX - r.left - this.panX) / this.zoom;
    const wy = (e.clientY - r.top - this.panY) / this.zoom;
    return [Math.floor(wx / this.cs) + this.x0, Math.floor(wy / this.cs) + this.y0];
  }
  private down = (e: PointerEvent) => {
    this.press = { x: e.clientX, y: e.clientY, px: this.panX, py: this.panY, moved: false };
    this.el.setPointerCapture(e.pointerId);
  };
  private move = (e: PointerEvent) => {
    if (this.press) {
      const dx = e.clientX - this.press.x;
      const dy = e.clientY - this.press.y;
      if (Math.abs(dx) + Math.abs(dy) > 4) this.press.moved = true;
      if (this.press.moved) {
        this.panX = this.press.px + dx;
        this.panY = this.press.py + dy;
        this.el.style.cursor = "grabbing";
        this.request();
        return;
      }
    }
    const c = this.cellAt(e);
    if (!this.hover || this.hover[0] !== c[0] || this.hover[1] !== c[1]) {
      this.hover = c;
      this.onHover(this.hoverAt(c));
      this.request();
    }
  };
  private up = (e: PointerEvent) => {
    const p = this.press;
    this.press = null;
    this.el.style.cursor = "";
    if (p && !p.moved && e.button === 0) this.onPick(this.cellAt(e));
  };
  private wheel = (e: WheelEvent) => {
    e.preventDefault();
    const r = this.el.getBoundingClientRect();
    this.zoomBy(Math.exp(-Math.sign(e.deltaY) * Math.min(Math.abs(e.deltaY), 120) * 0.002), [
      e.clientX - r.left,
      e.clientY - r.top,
    ]);
  };

  request() {
    if (this.frame) return;
    this.frame = requestAnimationFrame(() => {
      this.frame = 0;
      this.draw();
    });
  }

  private draw() {
    const ctx = this.ctx;
    const dpr = window.devicePixelRatio || 1;
    const W = this.host.clientWidth;
    const H = this.host.clientHeight;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.fillStyle = "#0f0d0b";
    ctx.fillRect(0, 0, W, H);
    const z = this.zoom;
    ctx.setTransform(dpr * z, 0, 0, dpr * z, dpr * this.panX, dpr * this.panY);
    const cs = this.cs;
    const ox = this.x0 * cs;
    const oy = this.y0 * cs;
    const vx0 = -this.panX / z;
    const vy0 = -this.panY / z;
    const vx1 = (W - this.panX) / z;
    const vy1 = (H - this.panY) / z;
    const t = this.info.tile;
    for (const tile of this.info.tiles) {
      const x = tile.x - ox;
      const y = tile.y - oy;
      if (x > vx1 || y > vy1 || x + t < vx0 || y + t < vy0) continue;
      const img = image(tile.url);
      if (img) ctx.drawImage(img, x, y, t, t);
      else {
        ctx.fillStyle = "#1c1815";
        ctx.fillRect(x, y, t, t);
      }
    }
    if (this.showShade) {
      ctx.imageSmoothingEnabled = false;
      ctx.drawImage(this.shade, 0, 0, this.w * cs, this.h * cs);
      ctx.imageSmoothingEnabled = true;
    }
    const sq = (x: number, y: number, fill: string | null, stroke: string | null, lw = 1.5) => {
      const px = (x - this.x0) * cs;
      const py = (y - this.y0) * cs;
      if (fill) {
        ctx.fillStyle = fill;
        ctx.fillRect(px, py, cs, cs);
      }
      if (stroke) {
        ctx.strokeStyle = stroke;
        ctx.lineWidth = lw / z;
        ctx.strokeRect(px + 0.5 / z, py + 0.5 / z, cs - 1 / z, cs - 1 / z);
      }
    };
    for (const k of Object.keys(this.info.patrols)) {
      const [x, y] = k.split(",").map(Number);
      sq(x, y, "rgba(240,140,30,0.35)", null);
    }
    for (const k of Object.keys(this.info.retired)) {
      const [x, y] = k.split(",").map(Number);
      sq(x, y, "rgba(120,110,100,0.6)", null);
    }
    for (const k of Object.keys(this.info.settlements)) {
      const [x, y] = k.split(",").map(Number);
      sq(x, y, "rgba(239,232,217,0.35)", "rgba(239,232,217,0.9)", 1);
    }
    for (const [x, y] of this.ours) sq(x, y, "rgba(217,164,65,0.55)", "#d9a441", 1.5);
    for (const [x, y] of this.info.starts) sq(x, y, "rgba(139,183,90,0.6)", "#8bb75a", 1.5);
    if (this.hover) sq(this.hover[0], this.hover[1], null, "rgba(255,255,255,0.9)", 1.5);
    if (this.chosen) {
      sq(this.chosen[0], this.chosen[1], "rgba(240,196,106,0.5)", "#f0c46a", 3);
      const px = (this.chosen[0] - this.x0) * cs + cs / 2;
      const py = (this.chosen[1] - this.y0) * cs + cs / 2;
      ctx.beginPath();
      ctx.arc(px, py, Math.max(cs * 1.6, 14 / z), 0, Math.PI * 2);
      ctx.strokeStyle = "#f0c46a";
      ctx.lineWidth = 2 / z;
      ctx.stroke();
    }
  }
}
