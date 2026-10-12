// The shapes tools/location_editor.py answers with (its header, THE MODEL
// and THE API). The page keeps the model as the server gave it and sends
// it back whole: fields it does not edit (raw, decals, background) go back
// as they came.

export type Cell = [number, number];
export type Wall = [number, number, string];
export type Exit = [number, number, string];

export interface Sprite {
  id: string;
  type: "lib" | "ext" | null;
  dx: number;
  dy: number;
  front: string | null;
  anchors: Cell[];
}

export interface Decal {
  id: string;
  type: string | null;
  dx: number;
  dy: number;
}

export interface Inhabitant {
  type: number;
  cell: Cell;
  why?: string;
  escort?: boolean;
  [k: string]: unknown;
}

export interface Door {
  target: number | null;
  why?: string;
  confidence?: string;
  source?: string;
  own_cell?: unknown;
}

export interface WalkIn {
  from: number;
  cells: Cell[];
  why?: string;
}

export interface MapPlace {
  cell: Cell;
  label: string;
  square: string | null;
  why?: string;
}

export interface IndexRow {
  title: string;
  from: number | null;
  author: string;
  created: string;
  why: string;
}

export type State = "new" | "ours" | "original";

export interface Model {
  // a number, or in publish mode "new:<uuid>" for a new place until it is published
  id: number | string;
  state: State;
  from: number | null;
  attrs: Record<string, string>;
  width: number;
  height: number;
  background: { type: string; id: string; fx: string } | null;
  sprites: Sprite[];
  decals: Decal[];
  walls: Wall[];
  exits: Exit[];
  entries: Cell[];
  war_entries: Cell[];
  spawns: [number, number, number][];
  raw: unknown;
  inhabitants: Inhabitant[];
  doors: Record<string, Door>;
  walk_ins: WalkIn[];
  no_map: { why: string } | null;
  map: MapPlace | null;
  index: IndexRow | null;
  etag: string;
  closed?: boolean;
}

export interface Problem {
  level: "error" | "warning";
  what: string;
  text: string;
  cells: Cell[];
  loc: number | string | null;
}

export interface Info {
  mode: string;
  data: string;
  objects: string;
  res: string;
  res_original: boolean;
  pictures: boolean;
  first_new_id: number;
  id_limit: number;
  sizes: [number, number][];
  tracks: string[];
  codes: Record<string, string>;
  sides: Record<string, string>;
  edge_band: Record<string, number>;
  colours: string[];
  layers: string[];
  today: string;
  // publish mode (the admin panel)
  commit?: string;
  branch?: string;
  web?: string;
  head?: { sha: string; date: string; author: string; subject: string };
  stale?: string;
  pending_objects?: PendingObject[];
  restart_minutes?: number;
  warn_seconds?: number;
}

export interface PendingObject {
  id: string;
  kind: "new" | "update" | "delete";
  title: string;
  at?: string;
}

export interface PublishState {
  state: "running" | "done" | "failed";
  step?: string;
  step_text?: string;
  code?: number;
  started?: string;
  finished?: string;
  login?: string;
  note?: string;
  result?: PublishResult;
}

export interface SuiteResult {
  suite: string;
  ok: boolean;
  code: number | null;
  seconds: number;
  known: boolean;
  tail: string;
}

export interface PublishResult {
  commit?: string;
  url?: string;
  id?: number | null;
  renumbered?: Record<string, number>;
  summary?: string[];
  files?: string[];
  objects?: PendingObject[];
  suites?: SuiteResult[];
  suite_notes?: string[];
  nothing?: boolean;
  error?: string;
  git?: string;
  problems?: Problem[];
  stale?: boolean;
  restarting?: boolean;
  // the push had no answer and origin could not be looked at: the commit may be in main
  maybe?: boolean;
  // the commit was found in main by the draft's trailer (a push whose answer was lost)
  landed?: boolean;
}

export interface DraftRow {
  uuid: string;
  id: number | string | null;
  title: string;
  state: State | null;
  from: number | null;
  base: string;
  rev: number;
  created: string;
  created_by: string;
  updated: string;
  login: string;
  stale: string | null;
  publish: PublishState | null;
}

export interface Draft {
  uuid: string;
  rev: number;
  base: string;
  id: number | string | null;
  title: string;
  created: string;
  created_by: string;
  updated: string;
  login: string;
  model: Model | null;
  publish: PublishState | null;
  stale: string | null;
}

export interface DiffReply {
  uuid: string;
  rev: number;
  base: string;
  branch: string;
  head: { sha: string; date: string; author: string; subject: string };
  id: number | string | null;
  assign: number | null;
  summary: string[];
  files: string[];
  objects: PendingObject[];
  problems: Problem[];
  stale: string | null;
  occupancy_id?: number | null;
  restart_minutes: number;
  warn_seconds: number;
}

export interface Occupancy {
  saved: number;
  online: number | null;
  homes: number | null;
}

export interface LocRow {
  id: number;
  title: string;
  fn: string;
  size: [number, number];
  library: string;
  war: string;
  pvp: string;
  state: "ours" | "original";
  cell: Cell | null;
  from: number | null;
  inhabitants: number;
  doors: string[];
  sides: string[];
  closed: boolean;
}

export interface PaletteItem {
  name: string;
  type: "lib" | "ext";
  origin?: "object";
  title?: string;
  w?: number;
  h?: number;
  ox?: number;
  oy?: number;
  frames?: number;
  fps?: number;
  thumb?: string;
  picture?: string;
  default?: { dx: number; dy: number; front: string; footprint: [number, number, string][]; uses?: number };
}

export interface Palette {
  library: string;
  items: PaletteItem[];
  warming: boolean;
}

export interface Mob {
  type: number;
  name: string;
  sub: string;
  level: number;
  root: number;
  role: string;
  known: boolean;
  retired: boolean;
  icon: string;
}

export interface MapInfo {
  bounds: { x: [number, number]; y: [number, number] };
  cell: number;
  tile: number;
  tiles: { n: number; x: number; y: number; url: string }[];
  settlements: Record<string, number>;
  titles: Record<string, string>;
  ours: Record<string, Cell | null>;
  retired: Record<string, number>;
  cut: Record<string, string>;
  patrols: Record<string, number>;
  labels: [number, number, string][];
  starts: Cell[];
  blocked: string;
  reachable: string | null;
  colours: string[];
}

export interface ObjectEntry {
  title: string;
  frames: string[];
  fps?: number | null;
  anchor?: Cell;
  front?: Cell[];
  footprint?: Cell[];
  kind?: string;
  note?: string;
  problem: string | null;
  pictures: string[];
  used_in: number[];
}

export interface EditReply {
  model: Model;
  cells: Cell[];
  sprite?: [number, number];
}

export interface SaveReply {
  id?: number;
  written?: string[];
  model?: Model;
  problems?: Problem[];
  error?: string;
  next_id?: number;
  seconds?: number;
}
