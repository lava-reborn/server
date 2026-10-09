import { useState } from "react";
import type { Problem } from "../types";
import { count } from "../words";

export function Problems({ problems, onSelect }: { problems: Problem[]; onSelect: (t: number) => void }) {
  const errors = problems.filter((p) => p.level === "error");
  const warns = problems.filter((p) => p.level === "warn");
  // Open by itself when there is an error; warnings wait to be asked for.
  const [wanted, setOpen] = useState<boolean | null>(null);
  const open = wanted === null ? errors.length > 0 : wanted;
  if (!problems.length) return null;
  return (
    <div className={"problems" + (open ? " open" : "")}>
      <div className="problems-head" onClick={() => setOpen(!open)}>
        <b>Проверка</b>
        {errors.length > 0 && <span className="qbadge err">{count(errors.length, "ошибка", "ошибки", "ошибок")}</span>}
        {warns.length > 0 && (
          <span className="qbadge warn">{count(warns.length, "предупреждение", "предупреждения", "предупреждений")}</span>
        )}
        <span className="grow" />
        <span className="muted">{open ? "свернуть" : "развернуть"}</span>
      </div>
      {open && (
        <div className="problems-list">
          {[...errors, ...warns].map((p, i) => (
            <div
              key={i}
              className={"problem " + p.level}
              title={p.text}
              onClick={() => p.type !== null && onSelect(p.type)}
            >
              <span>{p.level === "error" ? "✖" : "⚠"}</span>
              {p.type !== null && <span className="muted">#{p.type}</span>}
              <span>{p.ru}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function DiffModal({ text, onClose }: { text: string; onClose: () => void }) {
  return (
    <div className="modal-back" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <b>Изменения data/quests.json против последнего коммита</b>
          <span className="grow" />
          <button onClick={onClose}>Закрыть</button>
        </div>
        <DiffText text={text} empty="Изменений нет: файл совпадает с коммитом." />
      </div>
    </div>
  );
}

// A unified diff, coloured: the "--- a" / "+++ b" lines before the first
// hunk name the files, and are drawn as such.
export function DiffText({ text, empty }: { text: string; empty: string }) {
  let hunks = false;
  return (
    <pre className="diff">
      {text
        ? text.split("\n").map((l, i) => {
            if (l.startsWith("@@")) hunks = true;
            const cls = !hunks ? "dhead" : l.startsWith("@@") ? "hunk" : l.startsWith("+") ? "add" : l.startsWith("-") ? "del" : "";
            return (
              <div key={i} className={cls}>
                {l || " "}
              </div>
            );
          })
        : empty}
    </pre>
  );
}
