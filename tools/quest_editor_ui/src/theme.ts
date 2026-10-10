// The admin panel's design tokens (lava-admin/static/admin.css, :root), read
// off the editor's element: inside the admin they come from the panel,
// standalone from styles.css (.qe-alone). SVG markers and the minimap want
// plain colours, so these are resolved once and handed over as values.
const FALLBACK: Record<string, string> = {
  "--steel": "#7fa0b0",
  "--brand": "#d9a441",
  "--danger": "#e2543a",
  "--success": "#8bb75a",
  "--ink": "#efe8d9",
  "--ink-faint": "#8a8071",
  "--bg-panel": "#1c1815",
  "--overlay": "rgba(10,9,8,.72)",
};

let host: HTMLElement | null = null;
const cache = new Map<string, string>();

export function setHost(el: HTMLElement) {
  host = el;
  cache.clear();
}

export function token(name: string): string {
  const known = cache.get(name);
  if (known) return known;
  const v = (host ? getComputedStyle(host).getPropertyValue(name) : "").trim() || FALLBACK[name] || "#888";
  cache.set(name, v);
  return v;
}
