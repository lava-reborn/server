// What the page reads once and keeps: the editor's info, the list of
// locations, the creatures' names, the palettes by library, the map.
import { api } from "./api";
import type { Info, LocRow, MapInfo, Mob, Palette } from "./types";

let info: Promise<Info> | null = null;
export const getInfo = () => (info ||= api.info());

let rows: Promise<LocRow[]> | null = null;
export const getLocations = (fresh = false) => {
  if (fresh || !rows) {
    rows = api.locations();
    rows.catch(() => (rows = null));
  }
  return rows;
};

let mapInfo: Promise<MapInfo> | null = null;
export const getMap = (fresh = false) => {
  if (fresh || !mapInfo) {
    mapInfo = api.map();
    mapInfo.catch(() => (mapInfo = null));
  }
  return mapInfo;
};

const palettes = new Map<string, Promise<Palette>>();
export function getPalette(library: string, fresh = false): Promise<Palette> {
  let p = palettes.get(library);
  if (fresh || !p) {
    p = api.palette(library);
    palettes.set(library, p);
    p.catch(() => palettes.delete(library));
  }
  return p;
}
export const forgetPalettes = () => palettes.clear();

// creatures by type: filled by every search, asked for by type when missing
const mobs = new Map<number, Mob>();
const asked = new Map<number, Promise<Mob | null>>();
export function remember(list: Mob[]) {
  for (const m of list) mobs.set(m.type, m);
}
export const mobOf = (t: number) => mobs.get(t) || null;
export function lookupMob(t: number): Promise<Mob | null> {
  const known = mobs.get(t);
  if (known) return Promise.resolve(known);
  let p = asked.get(t);
  if (!p) {
    p = api
      .mobs(String(t), 200)
      .then((list) => {
        remember(list);
        return mobs.get(t) || null;
      })
      .catch(() => null);
    asked.set(t, p);
  }
  return p;
}
export const mobName = (t: number) => mobs.get(t)?.name || `существо ${t}`;
export const mobIcon = (t: number) => `/api/mobicon/${t}.webp`;
