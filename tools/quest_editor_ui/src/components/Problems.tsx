import { useState } from "react";
import type { Problem } from "../types";

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
        {errors.length > 0 && <span className="badge err">{errors.length} ошибок</span>}
        {warns.length > 0 && <span className="badge warn">{warns.length} предупреждений</span>}
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
        <pre className="diff">
          {text
            ? text.split("\n").map((l, i) => (
                <div key={i} className={l.startsWith("+") ? "add" : l.startsWith("-") ? "del" : l.startsWith("@@") ? "hunk" : ""}>
                  {l || " "}
                </div>
              ))
            : "Изменений нет: файл совпадает с коммитом."}
        </pre>
      </div>
    </div>
  );
}
