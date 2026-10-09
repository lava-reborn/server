import { useEffect, useState } from "react";
import { api } from "../api";
import type { Conflict, Layout, PreviewResp, Problem, PublishResp, Rebase, Row } from "../types";
import { DiffText } from "./Problems";

interface Props {
  rows: Row[];
  layout: Layout;
  base: string;
  branch: string;
  who: string;
  // the admin's words for the commit, kept by the page: closing the dialog
  // and opening it again does not lose them
  note: string;
  setNote: (s: string) => void;
  onClose: () => void;
  onPublished: (r: PublishResp) => void;
  // the preview found nothing to publish: these rows are as good as published
  onNothing: (rows: Row[]) => void;
  onRebase: (r: Rebase, types: number[]) => void;
  onReload: () => void;
  onOpen: (t: number) => void;
}

interface Failure {
  text: string;
  // git's own words, when git is what failed
  git?: string;
}

// Publish mode's "Опубликовать": what the page's edits come to once merged
// onto a fresh main (POST preview), then the push itself (POST publish).
// What is published is what was previewed: the rows and the layout are
// taken once, when the dialog opens.
export function PublishDialog({ rows, layout, base, branch, who, note, setNote, onClose, onPublished, onNothing, onRebase, onReload, onOpen }: Props) {
  const [snap] = useState(() => ({ rows, layout, base }));
  const [preview, setPreview] = useState<PreviewResp | null>(null);
  const [error, setError] = useState<Failure | null>(null);
  const [conflicts, setConflicts] = useState<Conflict[]>([]);
  const [rebase, setRebase] = useState<Rebase | null>(null);
  const [problems, setProblems] = useState<Problem[]>([]);
  const [busy, setBusy] = useState<"preview" | "publish" | null>("preview");
  const [round, setRound] = useState(0);

  useEffect(() => {
    let live = true;
    setBusy("preview");
    setError(null);
    api
      .preview(snap.rows, snap.layout, snap.base)
      .then(({ status, data }) => {
        if (!live) return;
        setConflicts(data.conflicts || []);
        setRebase(data.rebase || null);
        if (status === 200) {
          setPreview(data);
          setProblems(data.problems || []);
          if (data.nothing && !(data.conflicts || []).length) onNothing(snap.rows);
        } else {
          setPreview(null);
          setError({ text: data.error || `Ошибка ${status}`, git: data.git });
        }
      })
      .catch((e) => live && setError({ text: String(e) }))
      .finally(() => live && setBusy(null));
    return () => {
      live = false;
    };
    // onNothing takes the rows it is given; a new one is no reason to preview again
  }, [snap, round]);

  // Escape closes it, as «Закрыть» does. A click beside it does nothing: a
  // stray one would close the dialog under a half-written note.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && busy !== "publish") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [busy, onClose]);

  const publish = async () => {
    setBusy("publish");
    setError(null);
    try {
      const { status, data } = await api.publish(snap.rows, snap.layout, snap.base, note);
      if (status === 200 && (data.commit || data.nothing)) {
        onPublished(data);
        return;
      }
      if (status === 409) {
        setConflicts(data.conflicts || []);
        setRebase(data.rebase || null);
        setError({ text: data.error || "Конфликт с main" });
      } else if (status === 422) {
        setProblems(data.problems || []);
        setError({ text: data.error || "В таблице ошибки" });
      } else {
        setError({ text: data.error || `Ошибка ${status}`, git: data.git });
      }
    } catch (e) {
      setError({ text: String(e) });
    } finally {
      setBusy(null);
    }
  };

  const errors = problems.filter((p) => p.level === "error");
  const warns = problems.filter((p) => p.level === "warn");
  const blocked = !!busy || !preview || !!preview.nothing || conflicts.length > 0 || errors.length > 0;
  const renumbered = Object.entries(preview?.renumbered || {});
  const reload = () => {
    if (window.confirm(`Все правки на этой странице пропадут: она загрузит свежий ${branch}. Продолжить?`)) onReload();
  };
  const takeMain = () => {
    if (!rebase) return;
    const list = conflicts.map((c) => "#" + c.type).join(", ");
    if (window.confirm(`Квесты ${list} возьмутся из ${branch}, ваши правки к ним пропадут. Остальные правки страницы останутся. Продолжить?`)) {
      onRebase(rebase, conflicts.map((c) => c.type));
    }
  };

  return (
    <div className="modal-back">
      <div className="modal publish" role="dialog" aria-label={`Публикация в ${branch}`}>
        <div className="modal-head">
          <b>Публикация в {branch}</b>
          <span className="grow" />
          <button onClick={onClose} disabled={busy === "publish"}>
            Закрыть
          </button>
        </div>
        <div className="publish-body">
          {busy === "preview" && <div className="muted">Сверяю правки со свежим {branch}…</div>}
          {error && (
            <div className="qmsg err">
              {error.text}
              {error.git && <pre className="qgit">{error.git}</pre>}
            </div>
          )}
          {!preview && !busy && error && (
            <div className="inline">
              <button onClick={() => setRound((n) => n + 1)}>Проверить ещё раз</button>
            </div>
          )}

          {conflicts.length > 0 && (
            <div className="qmsg warn col">
              <b>Эти квесты изменились в {branch} после загрузки страницы:</b>
              <ul className="plist">
                {conflicts.map((c) => (
                  <li key={c.type}>
                    <span className="link" onClick={() => onOpen(c.type)}>
                      #{c.type} «{c.name}»
                    </span>
                    {c.ru ? <span className="muted"> · {c.ru}</span> : null}
                  </li>
                ))}
              </ul>
              <div className="inline">
                {rebase && <button onClick={takeMain}>Взять эти квесты из {branch}</button>}
                <button onClick={reload}>Загрузить свежий {branch}</button>
              </div>
              <span className="muted small">
                {rebase
                  ? `Первая кнопка оставит остальные правки страницы, правки к этим квестам потом внесите заново; вторая сбросит все правки.`
                  : `Правки страницы пропадут; к этим квестам их потом внесите заново.`}
              </span>
            </div>
          )}

          {preview?.nothing && !conflicts.length && <div className="qmsg">Публиковать нечего: всё это уже есть в {branch}.</div>}

          {renumbered.length > 0 && (
            <div className="qmsg">
              Пока вы правили, в {branch} появились квесты с теми же номерами, что у ваших новых. Ваши уйдут под свободными:{" "}
              {renumbered.map(([a, b]) => `#${a} → #${b}`).join(", ")}.
            </div>
          )}

          {!!preview?.summary?.length && (
            <div className="pblock">
              <div className="qsub">Что уйдёт в {branch}</div>
              <ul className="plist">
                {preview.summary.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            </div>
          )}

          {errors.length > 0 && (
            <div className="insp-problems">
              {errors.map((p, i) => (
                <div key={i} className="err-text link" title={p.text} onClick={() => p.type !== null && onOpen(p.type)}>
                  ✖ {p.type !== null ? `#${p.type} ` : ""}
                  {p.ru}
                </div>
              ))}
            </div>
          )}
          {warns.length > 0 && (
            <details className="pdetails">
              <summary>Предупреждений: {warns.length} (публикации не мешают)</summary>
              <div className="plist-box">
                {warns.map((p, i) => (
                  <div key={i} className="warn-text">
                    ⚠ {p.type !== null ? `#${p.type} ` : ""}
                    {p.ru}
                  </div>
                ))}
              </div>
            </details>
          )}

          {preview && !!preview.diff && (
            <details className="pdetails">
              <summary>Дифф data/quests.json против свежего {branch}</summary>
              <DiffText text={preview.diff} empty="" />
            </details>
          )}
          {preview?.layout_changed && <div className="muted small">С правками уйдёт и раскладка графа (data/quest_layout.json).</div>}

          <label className="pnote">
            <span className="qsub">Что поменяли (необязательно)</span>
            <textarea rows={3} value={note} maxLength={2000} placeholder="Попадёт в описание коммита" onChange={(e) => setNote(e.target.value)} />
          </label>
        </div>
        <div className="modal-foot">
          <span className="muted small">
            После зелёных тестов выкатится сама, обычно минут через 20
            {who ? <> · автор коммита: {who} (админка)</> : null}
          </span>
          <span className="grow" />
          <button className="primary" disabled={blocked} onClick={publish}>
            {busy === "publish" ? "Публикую…" : `Опубликовать в ${branch}`}
          </button>
        </div>
      </div>
    </div>
  );
}
