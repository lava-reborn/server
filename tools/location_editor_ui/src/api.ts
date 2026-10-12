import type {
  EditReply,
  Info,
  LocRow,
  MapInfo,
  Mob,
  Model,
  ObjectEntry,
  Palette,
  Problem,
  SaveReply,
} from "./types";

// The editor's own server (tools/location_editor.py) on the same origin:
// GET for reading, POST with a JSON body for everything else (the server
// refuses any other body, so a page of another site cannot post here).

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

async function request<T>(method: "GET" | "POST", url: string, body?: unknown): Promise<Reply<T>> {
  let r: Response;
  try {
    r = await fetch(url, {
      method,
      headers: body === undefined ? {} : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError("редактор не отвечает: запущен ли tools/location_editor.py?", 0);
  }
  const text = await r.text();
  let data: unknown;
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = { error: text.slice(0, 300) || `${r.status} ${r.statusText}` };
  }
  return { status: r.status, data: data as T };
}

function ok<T>(r: Reply<T>, what: string): T {
  if (r.status !== 200) {
    const d = (r.data || {}) as Record<string, unknown>;
    throw new ApiError(String(d.error || `${what}: ответ ${r.status}`), r.status, d);
  }
  return r.data;
}

const get = async <T>(url: string) => ok(await request<T>("GET", url), url);
const post = async <T>(url: string, body: unknown) => ok(await request<T>("POST", url, body), url);

async function png(url: string, body?: unknown): Promise<Blob> {
  let r: Response;
  try {
    r = await fetch(url, {
      method: body === undefined ? "GET" : "POST",
      headers: body === undefined ? {} : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError("редактор не отвечает", 0);
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

export const api = {
  info: () => get<Info>("/api/info"),
  locations: async () => (await get<{ locations: LocRow[] }>("/api/locations")).locations,
  location: (id: number) => get<Model>(`/api/location/${id}`),
  palette: (library: string) => get<Palette>(`/api/palette?library=${encodeURIComponent(library)}`),
  mobs: async (q: string, limit = 60) =>
    (await get<{ mobs: Mob[] }>(`/api/mobs?q=${encodeURIComponent(q)}&limit=${limit}`)).mobs,
  map: () => get<MapInfo>("/api/map"),
  objects: async () => (await get<{ objects: Record<string, ObjectEntry> }>("/api/objects")).objects,
  newModel: (body: Record<string, unknown>) =>
    post<{ model: Model; dropped: DroppedRow[]; notes?: string[] }>("/api/new", body),
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
};

export interface DroppedRow {
  type: number;
  cell: [number, number];
  name: string;
  why: string;
}

export const errText = (e: unknown) => (e instanceof Error ? e.message : String(e));
