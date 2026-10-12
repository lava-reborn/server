// One row of data/quests.json, as server/quests.py reads it (the module's
// docstring lists every key). Unknown keys are kept as they are.
export type Kind = "kill_mobs" | "bring_l_obj" | "del_obj";

export interface Slot {
  obj: number;
  num?: number;
  mobs?: number[];
  drop?: number;
  one_of?: string;
  [key: string]: unknown;
}

export interface Piece {
  obj: number;
  num?: number;
  w?: number;
  lent?: boolean;
  [key: string]: unknown;
}

export interface Way {
  at?: number;
  target_loc_id?: number;
  driver?: number;
  [key: string]: unknown;
}

export interface Row {
  type: number;
  kind: Kind;
  name: string;
  start?: string;
  notfinish?: string;
  finish?: string;
  give: number[];
  take: number[];
  rew_obj?: number[];
  num_rew_obj?: number[];
  rew_afro: number;
  rew_gold: number;
  repeatable: number;
  level: number;
  q_type: number;
  loc?: number;
  finish_loc?: number;
  rew_loc?: number;
  need_quest?: number | number[];
  need_any?: number[];
  excludes?: number[];
  obj?: number;
  objs?: Slot[];
  mobs_kill?: number[];
  num_kill?: number[];
  kill_also?: Record<string, number>;
  rew_xp?: Record<string, number>;
  rew_spec_xp?: Record<string, number>;
  requires_spec?: string | string[];
  complete_skills?: Record<string, number>;
  service?: boolean;
  per_day?: number;
  cooldown?: number;
  cost_afro?: number;
  cost_gold?: number;
  start_obj?: Piece[];
  lent?: boolean;
  stay_in?: number[];
  rew_random?: Piece[];
  rew_also?: Piece[];
  max_level?: number | null;
  party_size?: number;
  own_texts?: string[];
  way?: Way;
  collection?: boolean;
  why?: string;
  [key: string]: unknown;
}

export interface ItemRef {
  t: number;
  n: string;
  r: number;
  i: string;
  q: number;
  c: number;
}

export interface CreatureRef {
  t: number;
  n: string;
  sub?: string;
  l: number;
  role: string;
  root: number;
}

export interface LocRef {
  id: number;
  title: string;
}

export interface Refs {
  items: ItemRef[];
  creatures: CreatureRef[];
  locations: LocRef[];
  where: Record<string, number[]> | null;
  skills: string[];
  specs: string[];
  kinds: string[];
}

export interface Problem {
  type: number | null;
  level: "error" | "warn";
  text: string;
  ru: string;
}

export interface Pos {
  x: number;
  y: number;
}

export interface Layout {
  positions?: Record<string, Pos>;
  [key: string]: unknown;
}

export interface Generated {
  source: string;
  rows: Row[];
}

export interface CommitInfo {
  sha: string;
  date: string;
  author: string;
  subject: string;
}

export interface TableResp {
  rows: Row[];
  sha: string;
  generated: Generated[];
  layout: Layout;
  order: string[];
  new_types: [number, number];
  // Types data/passages.json makes rides: not the day's tasks (Sidebar isDaily).
  ways?: number[];
  // "publish": the admin panel's editor, which pushes to the branch;
  // "local": a checkout's data/quests.json, saved on disk.
  mode?: "publish" | "local";
  commit?: string;
  branch?: string;
  web?: string;
  head?: CommitInfo;
  stale?: string;
}

export interface Conflict {
  type: number;
  name: string;
  ru?: string;
}

// What the page becomes if it takes main's version of the quests in
// conflict and keeps the rest of its edits: main's commit as the new base.
export interface Rebase {
  commit: string;
  head: CommitInfo;
  rows: Row[];
  layout: Layout;
  // whether anything is left to publish against that commit
  changed: boolean;
}

export interface PreviewResp {
  head?: string;
  summary?: string[];
  conflicts?: Conflict[];
  problems?: Problem[];
  diff?: string;
  layout_changed?: boolean;
  nothing?: boolean;
  // new quests whose numbers main took meanwhile: old -> the one they go out as
  renumbered?: Record<string, number>;
  rebase?: Rebase;
  error?: string;
  // a 502: git's own words, under error's
  git?: string;
}

export interface PublishResp {
  commit?: string;
  head?: CommitInfo;
  url?: string;
  nothing?: boolean;
  summary?: string[];
  rows?: Row[];
  layout?: Layout;
  renumbered?: Record<string, number>;
  conflicts?: Conflict[];
  rebase?: Rebase;
  problems?: Problem[];
  error?: string;
  git?: string;
}

export interface TextsResp {
  shown: Record<string, string> | null;
  original: Record<string, string>;
  error: string | null;
}

export const TEXT_KEYS = ["name", "start", "notfinish", "finish"] as const;
export type TextKey = (typeof TEXT_KEYS)[number];

export const KIND_LABEL: Record<Kind, string> = {
  kill_mobs: "Убить",
  bring_l_obj: "Принести",
  del_obj: "Доставить / поговорить",
};

export const SKILL_LABEL: Record<string, string> = {
  melee: "Ближний бой",
  shooting: "Стрельба",
  medicine: "Медицина",
  industry: "Промышленность",
};

export const SPEC_LABEL: Record<string, string> = {
  unarmed: "Рукопашный бой",
  blades: "Холодное оружие",
  pistols: "Пистолеты",
  shotguns: "Дробовики",
  assault: "Автоматы",
  rifles: "Винтовки",
  machineguns: "Пулемёты",
  smg: "Пистолеты-пулемёты",
  surgery: "Хирургия",
  first_aid: "Первая помощь",
  mining: "Добыча",
  recycling: "Переработка",
};

export const ITEM_ROOT_LABEL: Record<number, string> = {
  0: "огнестрел",
  1: "одежда",
  2: "лечение",
  3: "патроны",
  4: "прочее",
  5: "холодное",
  6: "трофей",
};

export const NPC_ROOT_LABEL: Record<number, string> = {
  0: "моб",
  1: "торговец",
  4: "житель",
  5: "лекарь",
};
