import type {
  DiffReply,
  Draft,
  DraftRow,
  EditReply,
  Info,
  LocRow,
  MapInfo,
  Mob,
  Model,
  ObjectEntry,
  Occupancy,
  Palette,
  PendingObject,
  Problem,
  PublishState,
  SaveReply,
} from "./types";

// The editor's own server (tools/location_editor.py): GET for reading, POST
// with a JSON body for everything else (the server refuses any other body,
// so a page of another site cannot post here).
//
// Where it is. Standalone the API is /api and the art cache /art on the same
// origin. Inside the admin panel (/admin/locations) the mount element names
// them (data-api, data-img: see main.tsx), the panel's form token goes with
// every POST as X-Lava-Token, and the panel answers some questions itself
// (occupancy). The server writes its own links (/api/..., /art/...) into
// what it answers; href() moves them under the configured places.
export interface Config {
  api: string;
  img: string;
  token: string;
  who: string;
  panel: boolean;
}

export const config: Config = { api: "/api", img: "/art", token: "", who: "", panel: false };

export function configure(c: Partial<Config>) {
  Object.assign(config, c);
  config.api = config.api.replace(/\/+$/, "");
  config.img = config.img.replace(/\/+$/, "");
}

/** A link the server wrote (/api/..., /art/...) as this page reaches it. */
export function href(u: string): string;
export function href(u: string | undefined): string | undefined;
export function href(u: string | undefined): string | undefined {
  if (!u) return u;
  if (u.startsWith("/api/")) return config.api + u.slice(4);
  if (u.startsWith("/art/")) return config.img + u.slice(4);
  return u;
}

export class ApiError extends Error {
  status: number;
  data: Record<string, unknown>;
  constructor(message: string, status: number, data: Record<string, unknown> = {}) {
    super(message);
    this.status = status;
    this.data = data;
  }
}

export interface Reply<T> {
  status: number;
  data: T;
}

// What the page shows above everything when the API says so: the admin's
// session is over (401), or the editor is restarting onto a fresh main (503).
export type Notice = "session" | "restarting" | null;
let notify: (n: Notice) => void = () => undefined;
let shown: Notice = null;
export function onNotice(fn: (n: Notice) => void) {
  notify = fn;
}
function tell(n: Notice) {
  if (n === shown) return;
  shown = n;
  notify(n);
}

const sleep = (ms: number) => new Promise((res) => window.setTimeout(res, ms));

async function raw(method: "GET" | "POST", ep: string, body?: unknown, retried = false): Promise<Response> {
  const headers: Record<string, string> = {};
  const sent = method === "POST" ? config.token : "";
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (sent) headers["X-Lava-Token"] = sent;
  let r: Response;
  try {
    r = await fetch(href(ep), {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      credentials: "same-origin",
    });
  } catch {
    throw new ApiError(
      config.panel ? "панель не отвечает" : "редактор не отвечает: запущен ли tools/location_editor.py?",
      0,
    );
  }
  // The panel's token is tied to its cookie, which the panel signs anew now
  // and then (a password for a ban in another tab, a new login): the page's
  // token then gets 403, and the panel hands out the one for the cookie the
  // browser has now.
  if (r.status === 403 && sent && !retried && (config.token !== sent || (await freshToken()))) {
    return raw(method, ep, body, true);
  }
  if (r.status === 401 && config.panel) tell("session");
  else if (shown === "session") tell(null);
  return r;
}

async function freshToken(): Promise<boolean> {
  try {
    const r = await fetch(`${config.api}/token`, { credentials: "same-origin" });
    if (r.status !== 200) return false;
    const d = (await r.json()) as { token?: string };
    if (!d.token || d.token === config.token) return false;
    config.token = d.token;
    return true;
  } catch {
    return false;
  }
}

async function request<T>(method: "GET" | "POST", ep: string, body?: unknown): Promise<Reply<T>> {
  const r = await raw(method, ep, body);
  const text = await r.text();
  let data: unknown;
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = { error: text.slice(0, 300) || `${r.status} ${r.statusText}` };
  }
  return { status: r.status, data: data as T };
}

const restarting = (r: { status: number; data: unknown }) =>
  r.status === 503 && !!r.data && typeof r.data === "object" && !!(r.data as { restarting?: boolean }).restarting;

// A read waits out the editor restarting onto a fresh main (publish mode):
// between its exit and its start the panel answers 503 for it. tries times,
// two seconds apart; the notice says so above the page.
async function patient<T>(method: "GET" | "POST", ep: string, body: unknown, tries = 30): Promise<Reply<T>> {
  for (let i = 1; ; i++) {
    const r = await request<T>(method, ep, body);
    if (r.status === 503 && i < tries) {
      if (restarting(r) || config.panel) tell("restarting");
      await sleep(2000);
      continue;
    }
    if (shown === "restarting") tell(null);
    return r;
  }
}

function ok<T>(r: Reply<T>, what: string): T {
  if (r.status !== 200) {
    const d = (r.data || {}) as Record<string, unknown>;
    throw new ApiError(String(d.error || `${what}: ответ ${r.status}`), r.status, d);
  }
  return r.data;
}

const get = async <T>(ep: string) => ok(await patient<T>("GET", ep, undefined), ep);
const post = async <T>(ep: string, body: unknown) => ok(await request<T>("POST", ep, body), ep);

async function png(ep: string, body?: unknown): Promise<Blob> {
  let r = await raw(body === undefined ? "GET" : "POST", ep, body);
  for (let i = 0; r.status === 503 && i < 10; i++) {
    await sleep(2000);
    r = await raw(body === undefined ? "GET" : "POST", ep, body);
  }
  if (r.status !== 200) {
    let msg = `картинка: ответ ${r.status}`;
    try {
      msg = ((await r.json()) as { error?: string }).error || msg;
    } catch {
      /* not JSON */
    }
    throw new ApiError(msg, r.status);
  }
  return r.blob();
}

// the server's links in what it answers, as this page reaches them
const fixPalette = (p: Palette): Palette => ({
  ...p,
  items: p.items.map((it) => ({ ...it, thumb: href(it.thumb), picture: href(it.picture) })),
});
const fixMap = (m: MapInfo): MapInfo => ({ ...m, tiles: m.tiles.map((t) => ({ ...t, url: href(t.url) })) });
const fixObjects = (o: Record<string, ObjectEntry>) => {
  const out: Record<string, ObjectEntry> = {};
  for (const [k, e] of Object.entries(o)) out[k] = { ...e, pictures: (e.pictures || []).map((u) => href(u)) };
  return out;
};

export const api = {
  info: () => get<Info>("/api/info"),
  locations: async () => (await get<{ locations: LocRow[] }>("/api/locations")).locations,
  location: (id: number) => get<Model>(`/api/location/${id}`),
  palette: async (library: string) => fixPalette(await get<Palette>(`/api/palette?library=${encodeURIComponent(library)}`)),
  mobs: async (q: string, limit = 60) =>
    (await get<{ mobs: Mob[] }>(`/api/mobs?q=${encodeURIComponent(q)}&limit=${limit}`)).mobs.map((m) => ({
      ...m,
      icon: href(m.icon),
    })),
  map: async () => fixMap(await get<MapInfo>("/api/map")),
  objects: async () => fixObjects((await get<{ objects: Record<string, ObjectEntry> }>("/api/objects")).objects),
  objectsPending: async () => (await get<{ pending?: Record<string, string> }>("/api/objects")).pending || {},
  newModel: (body: Record<string, unknown>) =>
    post<{ model: Model; dropped: DroppedRow[]; notes?: string[]; draft?: { uuid: string; rev: number } }>(
      "/api/new",
      body,
    ),
  edit: (model: Model, op: Record<string, unknown>) => post<EditReply>("/api/edit", { model, op }),
  check: (model: Model, quick: boolean) =>
    post<{ problems: Problem[]; seconds: number }>("/api/check", { model, quick }),
  // 200, 409 and 422 all carry a body the page shows: the caller reads the status
  save: (model: Model) => request<SaveReply>("POST", "/api/save", { model, etag: model.etag }),
  renderSaved: (id: number, layers: string, scale: number) =>
    png(`/api/render/${id}.png?layers=${encodeURIComponent(layers)}&scale=${scale}`),
  render: (model: Model, layers: string, scale: number) => png("/api/render", { model, layers, scale }),
  objectNew: (body: Record<string, unknown>) => post<{ id: string; entry: ObjectEntry }>("/api/object", body),
  objectUpdate: (body: Record<string, unknown>) => post<{ id: string; entry: ObjectEntry }>("/api/object/update", body),
  objectDelete: (id: string) => post<{ id: string; deleted: boolean }>("/api/object/delete", { id }),

  // publish mode: drafts and «Опубликовать»
  drafts: () => get<{ drafts: DraftRow[]; objects: PendingObject[] }>("/api/drafts"),
  draft: (uuid: string) => get<Draft>(`/api/draft/${uuid}`),
  diff: (uuid: string) => get<DiffReply>(`/api/diff/${uuid}`),
  // 200 and 409 carry a body the page shows: the caller reads the status
  saveDraft: (body: { uuid?: string; rev?: number; base?: string; model: Model }) =>
    request<{ uuid?: string; rev?: number; updated?: string; error?: string; login?: string }>("POST", "/api/draft", body),
  deleteDraft: (uuid: string) => post<{ uuid: string; deleted: boolean }>("/api/draftdel", { uuid }),
  // main's engine moved on: the editor restarts on it first (503 restarting),
  // then answers; a publish refused so started nothing and is sent again
  publish: async (body: { uuid?: string; rev?: number; message: string }) => {
    for (let i = 1; ; i++) {
      const r = await request<{ uuid?: string; publish?: PublishState; error?: string; restarting?: boolean }>(
        "POST",
        "/api/publish",
        body,
      );
      if (restarting(r) && i < 30) {
        tell("restarting");
        await sleep(2000);
        continue;
      }
      if (shown === "restarting") tell(null);
      return r;
    }
  },
  // the panel's own answer (the game's database): who is saved in that location
  occupancy: async (id: number): Promise<Occupancy | null> => {
    for (const ep of [`/api/occupancy/${id}`, `/api/occupancy?id=${id}`]) {
      try {
        const r = await request<Record<string, unknown>>("GET", ep);
        if (r.status !== 200 || !r.data || typeof r.data !== "object") continue;
        const d = r.data;
        const num = (...ks: string[]) => {
          for (const k of ks) if (typeof d[k] === "number") return d[k] as number;
          return null;
        };
        const saved = num("saved", "characters", "count");
        if (saved === null) continue;
        return { saved, online: num("online", "players") };
      } catch {
        /* not there: local mode, or a panel without it */
      }
    }
    return null;
  },
};

export interface DroppedRow {
  type: number;
  cell: [number, number];
  name: string;
  why: string;
}

export const errText = (e: unknown) => (e instanceof Error ? e.message : String(e));
