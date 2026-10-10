// The client's text markup, drawn the way its quest window draws it
// (lol/core/quests/Quest.as): <br>/<Br> breaks, <b>, <i>, <u>, <hint> for the
// highlighted line, %имя% for the character's name and %sex?male:female% for a
// sex-dependent word. Everything else is shown as written, escaped.

function esc(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export function renderMarkup(src: string | undefined, name = "Странник"): string {
  let s = esc(src || "");
  s = s.replace(/&lt;\/?br\s*\/?&gt;/gi, "<br>");
  s = s.replace(/&lt;(b|i|u)&gt;/gi, (_m, t: string) => `<${t.toLowerCase()}>`);
  s = s.replace(/&lt;\/(b|i|u)&gt;/gi, (_m, t: string) => `</${t.toLowerCase()}>`);
  s = s.replace(/&lt;hint&gt;/gi, '<span class="hint">').replace(/&lt;\/hint&gt;/gi, "</span>");
  s = s.replace(/%имя%/g, `<span class="macro" title="%имя%">${esc(name)}</span>`);
  // Both forms, the man's first: «удивил/а», «голый/ая».
  s = s.replace(
    /%sex\?([^:%]*):([^%]*)%/g,
    (_m, male: string, female: string) =>
      `<span class="sex" title="мужчине: «${male}», женщине: «${female}»">${male}<span class="sexalt">/${female}</span></span>`,
  );
  return s;
}

// Plain text for a card: markup stripped, breaks as spaces.
export function plain(src: string | undefined): string {
  return (src || "")
    .replace(/<\/?br\s*\/?>/gi, " ")
    .replace(/<[^>]+>/g, "")
    .replace(/%имя%/g, "Странник")
    .replace(/%sex\?([^:%]*):([^%]*)%/g, "$1")
    .replace(/\s+/g, " ")
    .trim();
}
