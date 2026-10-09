import type { Layout, PreviewResp, Problem, PublishResp, Refs, Row, TableResp, TextsResp } from "./types";

// Where the page talks to. Standalone (tools/quest_editor.py) the API is
// /api on the same origin; inside the admin panel the mount element names
// it (data-api, data-icons, data-token, data-who: see main.tsx).
export interface Config {
  api: string;
  icons: string;
  token: string;
  who: string;
}

export const config: Config = { api: "/api", icons: "/icon/", token: "", who: "" };

export function configure(c: Partial<Config>) {
  Object.assign(config, c);
  config.api = config.api.replace(/\/+$/, "");
}

export const iconUrl = (hash: string) => `${config.icons}${hash}.png`;

// What the page shows above the editor when the API says so: the admin's
// session is over (401), or the editor is restarting onto a fresh main (503).
export type Notice = "session" | "restarting" | null;
let notify: (n: Notice) => void = () => undefined;
let shown: Notice = null;
export function onNotice(fn: (n: Notice) => void) {
  notify = fn;
}
function tell(n: Notice) {
  shown = n;
  notify(n);
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

interface Reply<T> {
  status: number;
  data: T;
}

async function request<T>(method: "GET" | "POST", ep: string, body?: unknown, retried = false): Promise<Reply<T>> {
  const headers: Record<string, string> = {};
  const sent = method === "POST" ? config.token : "";
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (sent) headers["X-Lava-Token"] = sent;
  const r = await fetch(`${config.api}/${ep}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
    credentials: "same-origin",
  });
  const text = await r.text();
  let data: unknown;
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = { error: text.slice(0, 300) || `${r.status} ${r.statusText}` };
  }
  // (a request sent beside the one that fetched the fresh token finds it in place)
  if (r.status === 403 && sent && !retried && (config.token !== sent || (await freshToken()))) {
    return request<T>(method, ep, body, true);
  }
  if (r.status === 401) tell("session");
  else if (shown === "session") tell(null);
  return { status: r.status, data: data as T };
}

// The panel's token is tied to its cookie, and the panel signs the cookie
// anew now and then: a password asked for a ban in another tab, a new
// login after the session ran out. The page's token then gets 403, and the
// panel hands out the one for the cookie the browser has now (GET token).
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

const sleep = (ms: number) => new Promise((res) => window.setTimeout(res, ms));

const restarting = (r: Reply<unknown>) =>
  r.status === 503 && !!r.data && typeof r.data === "object" && !!(r.data as { restarting?: boolean }).restarting;

// A request that waits out an editor restarting onto a fresh main: tries
// times, two seconds apart; loud ones say so above the editor. Between the
// editor's exit and its start from the new checkout the panel answers for
// it ("не отвечает"), without the restarting flag: reads wait out any 503;
// a preview or a publish (anyDown false) only once the editor has said it
// is restarting, since a publish that timed out may have pushed already.
async function patient<T>(
  method: "GET" | "POST",
  ep: string,
  body: unknown,
  tries: number,
  loud: boolean,
  anyDown = true,
): Promise<Reply<T>> {
  let seen = false;
  for (let i = 1; ; i++) {
    const r = await request<T>(method, ep, body);
    seen = seen || restarting(r);
    if (r.status === 503 && i < tries && (anyDown || seen)) {
      if (loud && seen) tell("restarting");
      await sleep(2000);
      continue;
    }
    if (loud && r.status !== 401) tell(null);
    return r;
  }
}

function ok<T>(ep: string, r: Reply<T>): T {
  if (r.status !== 200) {
    const err = (r.data as { error?: string } | null)?.error;
    throw new ApiError(err || `${ep}: ${r.status}`, r.status);
  }
  return r.data;
}

export const api = {
  table: async () => ok("table", await patient<TableResp>("GET", "table", undefined, 10, true)),
  refs: async () => ok("refs", await patient<Refs>("GET", "refs", undefined, 10, false)),
  diff: async () => ok("diff", await request<{ diff: string }>("GET", "diff")),
  check: async (rows: Row[]) =>
    ok("check", await patient<{ problems: Problem[] }>("POST", "check", { rows }, 10, false)).problems,
  texts: async (row: Row) => ok("texts", await patient<TextsResp>("POST", "texts", { row }, 10, false)),
  newRow: async (kind: string, rows: Row[]) => {
    const r = await patient<{ row?: Row; error?: string }>("POST", "new", { kind, rows }, 10, false);
    if (r.status !== 200 || !r.data.row) throw new ApiError(r.data.error || "не удалось", r.status);
    return r.data.row;
  },
  save: (rows: Row[], layout: Layout, sha: string, force = false) =>
    request<{ ok?: boolean; sha?: string; error?: string; ru?: string; problems?: Problem[] }>("POST", "save", {
      rows,
      layout,
      sha,
      force,
    }),
  // main's engine moved on: the editor restarts on it first (503), then
  // answers; a publish refused that way pushed nothing and is sent again
  preview: (rows: Row[], layout: Layout, base: string) =>
    patient<PreviewResp>("POST", "preview", { rows, layout, base }, 15, false, false),
  publish: (rows: Row[], layout: Layout, base: string, message: string) =>
    patient<PublishResp>("POST", "publish", { rows, layout, base, message }, 15, false, false),
};
