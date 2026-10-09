import type { Layout, Problem, Refs, Row, TableResp, TextsResp } from "./types";

async function getJson<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url}: ${r.status}`);
  return (await r.json()) as T;
}

async function postJson<T>(url: string, body: unknown): Promise<{ status: number; data: T }> {
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = (await r.json()) as T;
  return { status: r.status, data };
}

export const api = {
  table: () => getJson<TableResp>("/api/table"),
  refs: () => getJson<Refs>("/api/refs"),
  diff: () => getJson<{ diff: string }>("/api/diff"),
  check: async (rows: Row[]) =>
    (await postJson<{ problems: Problem[] }>("/api/check", { rows })).data.problems,
  texts: async (row: Row) => (await postJson<TextsResp>("/api/texts", { row })).data,
  newRow: async (kind: string, rows: Row[]) => {
    const { status, data } = await postJson<{ row?: Row; error?: string }>("/api/new", {
      kind,
      rows,
    });
    if (status !== 200 || !data.row) throw new Error(data.error || "не удалось");
    return data.row;
  },
  save: (rows: Row[], layout: Layout, sha: string, force = false) =>
    postJson<{ ok?: boolean; sha?: string; error?: string; ru?: string; problems?: Problem[] }>(
      "/api/save",
      { rows, layout, sha, force },
    ),
};
