import { useEffect, useRef, useState } from "react";
import { api, errText } from "../api";
import type { DiffReply, Model, Occupancy, PendingObject, Problem, PublishResult, PublishState } from "../types";
import { Modal, Spinner } from "./ui";

// «Опубликовать» in the admin panel: what publishing the draft changes (the
// server's own words), the checks, what it means for the players, a note for
// the commit, then the publish itself, which runs on the server in the
// background (fetch main, save the place there, the suites, the push) while
// this dialog follows the draft.

const KIND_RU: Record<string, string> = { new: "новый", update: "правка", delete: "удалён" };

type Phase = "prepare" | "ready" | "running" | "done" | "failed";

export default function PublishDialog(props: {
  uuid: string | null; // null: only the owner's pending objects
  model: Model | null;
  title: string;
  flush?: () => Promise<{ uuid: string; rev: number } | null>;
  watch?: PublishState | null; // a publish already under way (or over) for this draft
  objects?: PendingObject[];
  onClose: () => void;
  onDone: (result: PublishResult) => void;
  onProblem?: (p: Problem) => void;
}) {
  const [phase, setPhase] = useState<Phase>(props.watch ? (props.watch.state === "running" ? "running" : props.watch.state) : "prepare");
  const [uuid, setUuid] = useState<string | null>(props.uuid);
  const [rev, setRev] = useState<number | undefined>(undefined);
  const [diff, setDiff] = useState<DiffReply | null>(null);
  const [diffErr, setDiffErr] = useState<string | null>(null);
  const [full, setFull] = useState<{ problems: Problem[]; seconds: number } | null>(null);
  const [fullErr, setFullErr] = useState<string | null>(null);
  const [occ, setOcc] = useState<Occupancy | null | "unknown">(null);
  const [note, setNote] = useState("");
  const [state, setState] = useState<PublishState | null>(props.watch || null);
  const [startErr, setStartErr] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const alive = useRef(true);
  const t0 = useRef(Date.now());

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  // prepare: the draft saved now, what it changes, the full check, who is there
  useEffect(() => {
    if (phase !== "prepare") return;
    (async () => {
      let id = props.uuid;
      if (props.flush) {
        try {
          const d = await props.flush();
          if (d) {
            id = d.uuid;
            setUuid(d.uuid);
            setRev(d.rev);
          }
        } catch (e) {
          if (alive.current) setDiffErr(`черновик не сохранён: ${errText(e)}`);
          return;
        }
      }
      if (!alive.current) return;
      if (props.model && typeof props.model.id === "number") {
        api.occupancy(props.model.id).then((o) => alive.current && setOcc(o || "unknown"));
      }
      if (props.model) {
        api.check(props.model, false).then(
          (r) => alive.current && setFull(r),
          (e) => alive.current && setFullErr(errText(e)),
        );
      }
      if (id) {
        try {
          const d = await api.diff(id);
          if (!alive.current) return;
          setDiff(d);
          setRev(d.rev);
        } catch (e) {
          if (alive.current) setDiffErr(errText(e));
          return;
        }
      }
      if (alive.current) setPhase("ready");
    })();
  }, [phase]);

  // following a publish: the draft says how far it got
  useEffect(() => {
    if (phase !== "running" || !uuid) return;
    let timer = 0;
    const tick = window.setInterval(() => setElapsed(Math.round((Date.now() - t0.current) / 1000)), 1000);
    const poll = async () => {
      try {
        const d = await api.draft(uuid);
        if (!alive.current) return;
        const p = d.publish;
        if (p) setState(p);
        if (p && p.state !== "running") {
          setPhase(p.state === "done" ? "done" : "failed");
          return;
        }
      } catch {
        /* the editor restarting: ask again */
      }
      timer = window.setTimeout(poll, 2000);
    };
    poll();
    return () => {
      window.clearTimeout(timer);
      window.clearInterval(tick);
    };
  }, [phase, uuid]);

  const start = async () => {
    setStartErr(null);
    t0.current = Date.now();
    setElapsed(0);
    try {
      const r = await api.publish({ uuid: uuid || undefined, rev, message: note });
      if (!alive.current) return;
      if (r.status === 202 && r.data.publish) {
        if (r.data.uuid) setUuid(r.data.uuid);
        setState(r.data.publish);
        setPhase("running");
        return;
      }
      setStartErr(r.data.error || `ответ ${r.status}`);
    } catch (e) {
      setStartErr(errText(e));
    }
  };

  const result: PublishResult = state?.result || {};
  const quickErrors = (diff?.problems || []).filter((p) => p.level === "error");
  const fullErrors = (full?.problems || []).filter((p) => p.level === "error");
  const blocked = quickErrors.length > 0 || fullErrors.length > 0 || !!diff?.stale;
  const objects = diff?.objects || props.objects || [];
  const isNew = !!props.model && typeof props.model.id === "string";
  const minutes = diff?.restart_minutes || 20;
  const warn = diff?.warn_seconds || 180;

  let footer;
  if (phase === "ready") {
    footer = (
      <>
        <button onClick={props.onClose}>Отмена</button>
        <button
          className="primary"
          onClick={start}
          disabled={blocked}
          title={blocked ? "Сначала исправьте ошибки" : "Полную проверку и наборы публикация пройдёт сама, на свежем main"}
        >
          Опубликовать в {diff?.branch || "main"}
        </button>
      </>
    );
  } else if (phase === "done") {
    footer = (
      <button className="primary" onClick={() => props.onDone(result)}>
        Готово
      </button>
    );
  } else if (phase === "failed") {
    footer = (
      <>
        <button onClick={props.onClose}>Закрыть</button>
        <button
          onClick={() => {
            setDiff(null);
            setDiffErr(null);
            setFull(null);
            setFullErr(null);
            setState(null);
            setPhase("prepare");
          }}
        >
          Проверить и повторить
        </button>
      </>
    );
  } else {
    footer = <button onClick={props.onClose}>{phase === "running" ? "Скрыть (публикация идёт)" : "Закрыть"}</button>;
  }

  return (
    <Modal title={`Опубликовать: ${props.title}`} onClose={props.onClose} wide footer={footer}>
      {phase === "prepare" && !diffErr && (
        <p>
          <Spinner /> Сохраняю черновик и смотрю, что изменится…
        </p>
      )}
      {diffErr && <p className="err-text">Не вышло: {diffErr}</p>}

      {(phase === "ready" || phase === "prepare") && diff && (
        <div className="publish-body">
          {diff.stale && <div className="banner err">Черновик устарел: {diff.stale}. Публикация будет отклонена.</div>}
          <h4>Что изменится</h4>
          {diff.summary.length ? (
            <ul className="pub-list">
              {diff.summary.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ul>
          ) : (
            <p className="muted">{props.model ? "Правок места нет." : "Только объекты."}</p>
          )}
          {objects.length > 0 && (
            <>
              <h4>Мои объекты, которые уйдут вместе с этим</h4>
              <ul className="pub-list">
                {objects.map((o) => (
                  <li key={o.id}>
                    <span className="mono">{o.id}</span> «{o.title}» — {KIND_RU[o.kind] || o.kind}
                  </li>
                ))}
              </ul>
            </>
          )}
          {diff.files.length > 0 && (
            <details>
              <summary>Файлы ({diff.files.length})</summary>
              <ul className="pub-files mono">
                {diff.files.map((f) => (
                  <li key={f}>{f}</li>
                ))}
              </ul>
              {isNew && <p className="hint">N — номер, который место получит при публикации.</p>}
            </details>
          )}
          <h4>Проверки</h4>
          <CheckList title="Быстрая" problems={diff.problems} onProblem={props.onProblem} />
          {props.model &&
            (full ? (
              <CheckList title={`Полная, как сервер (${full.seconds} с)`} problems={full.problems} onProblem={props.onProblem} />
            ) : fullErr ? (
              <p className="err-text">Полная проверка не удалась: {fullErr}</p>
            ) : (
              <p className="muted">
                <Spinner /> Полная проверка, как сервер: если менялись название, стороны, фон или клетка на карте, около минуты…
              </p>
            ))}
          <h4>Что это значит для игры</h4>
          <ul className="pub-warn">
            {isNew && (
              <li>
                Номер месту дадут при публикации: первый свободный в {diff.branch}
                {diff.assign ? ` (сейчас это ${diff.assign})` : ""}.
              </li>
            )}
            {props.model && !isNew && (
              <li>
                {occ === null ? (
                  <>
                    <Spinner /> смотрю, кто сохранён в этой локации…
                  </>
                ) : occ === "unknown" ? (
                  "Сколько персонажей сохранено в этой локации, панель не сказала."
                ) : (
                  <>
                    В локации сохранено персонажей: <b>{occ.saved}</b>
                    {occ.online !== null ? `, сейчас в игре там ${occ.online}` : ""}.
                    {occ.saved > 0 && " Тот, кто окажется на новой стене, после перезапуска встанет на вход."}
                  </>
                )}
              </li>
            )}
            <li>
              Сервер перезапустится примерно через {minutes} минут: CI проверит коммит и выкатит его, игроков предупредят за{" "}
              {Math.round(warn / 60)} минуты.
            </li>
            <li>Картинки и само место придут игрокам при следующем запуске лаунчера; до этого их клиент покажет на месте пустыню.</li>
          </ul>
          <label className="field-row">
            <span className="field-label">Что и зачем (уйдёт в описание коммита)</span>
            <textarea rows={3} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Например: подвал для квеста Сета" />
          </label>
          {startErr && <p className="err-text">Публикация не началась: {startErr}</p>}
        </div>
      )}
      {phase === "ready" && !diff && !props.uuid && (
        <div className="publish-body">
          <h4>Мои объекты</h4>
          <ul className="pub-list">
            {objects.map((o) => (
              <li key={o.id}>
                <span className="mono">{o.id}</span> «{o.title}» — {KIND_RU[o.kind] || o.kind}
              </li>
            ))}
          </ul>
          <ul className="pub-warn">
            <li>Сервер перезапустится примерно через {minutes} минут, игроков предупредят за 3 минуты.</li>
            <li>Картинки придут игрокам при следующем запуске лаунчера.</li>
          </ul>
          <label className="field-row">
            <span className="field-label">Что и зачем (уйдёт в описание коммита)</span>
            <textarea rows={2} value={note} onChange={(e) => setNote(e.target.value)} />
          </label>
          {startErr && <p className="err-text">Публикация не началась: {startErr}</p>}
        </div>
      )}

      {phase === "running" && (
        <div className="publish-body">
          <p>
            <Spinner /> {state?.step_text || "публикую"}… {elapsed > 0 && <span className="muted">{elapsed} с</span>}
          </p>
          <p className="muted small">
            Место сохраняется в свежий main его же кодом, потом на этом коммите идут наборы проверок, и только зелёный коммит
            уходит в main. Это несколько минут; окно можно скрыть, публикация не прервётся.
          </p>
        </div>
      )}
      {phase === "done" && (
        <div className="publish-body">
          {result.nothing ? (
            <p>Публиковать нечего: в {diff?.branch || "main"} уже то же самое.</p>
          ) : (
            <>
              <p className="ok-text">
                Опубликовано: коммит{" "}
                {result.url ? (
                  <a href={result.url} target="_blank" rel="noreferrer" className="mono">
                    {(result.commit || "").slice(0, 10)}
                  </a>
                ) : (
                  <span className="mono">{(result.commit || "").slice(0, 10)}</span>
                )}
                {result.id ? `, место #${result.id}` : ""}.
              </p>
              <p className="muted">CI проверит коммит и выкатит его; сервер перезапустится примерно через {minutes} минут.</p>
              {result.summary && result.summary.length > 0 && (
                <ul className="pub-list">
                  {result.summary.map((s, i) => (
                    <li key={i}>{s}</li>
                  ))}
                </ul>
              )}
              <Suites result={result} />
            </>
          )}
        </div>
      )}
      {phase === "failed" && (
        <div className="publish-body">
          <p className="err-text">{result.error || "Публикация не удалась"}</p>
          {result.stale && (
            <p className="muted">
              Эту локацию тем временем изменили в main. Откройте её заново из списка и повторите правки: черновик остаётся, его
              можно открыть рядом.
            </p>
          )}
          {result.git && <pre className="pub-git">{result.git}</pre>}
          {result.problems && result.problems.length > 0 && (
            <CheckList title="Что не так" problems={result.problems} onProblem={props.onProblem} />
          )}
          <Suites result={result} />
          <p className="muted small">В main ничего не ушло.</p>
        </div>
      )}
    </Modal>
  );
}

function CheckList(props: { title: string; problems: Problem[]; onProblem?: (p: Problem) => void }) {
  const errors = props.problems.filter((p) => p.level === "error");
  const warnings = props.problems.filter((p) => p.level !== "error");
  return (
    <div className="pub-check">
      <div>
        {props.title}:{" "}
        {errors.length ? <span className="err-text">ошибок {errors.length}</span> : <span className="ok-text">без ошибок</span>}
        {warnings.length > 0 && <span className="warn-text">, предупреждений {warnings.length}</span>}
      </div>
      {props.problems.length > 0 && (
        <ul className="pub-list">
          {[...errors, ...warnings].slice(0, 30).map((p, i) => (
            <li key={i} className={p.level === "error" ? "err-text" : "warn-text"}>
              {props.onProblem && p.cells.length ? (
                <button className="ghost small" onClick={() => props.onProblem!(p)}>
                  {p.text}
                </button>
              ) : (
                p.text
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Suites({ result }: { result: PublishResult }) {
  if (!result.suites || !result.suites.length) return null;
  const red = result.suites.filter((s) => !s.ok);
  return (
    <details open={red.length > 0}>
      <summary>
        Наборы проверок на коммите: {red.length ? <span className="err-text">красных {red.length}</span> : "все зелёные"} (
        {result.suites.length})
      </summary>
      <ul className="pub-files">
        {result.suites.map((s) => (
          <li key={s.suite}>
            <span className={s.ok ? "ok-text" : "err-text"}>{s.ok ? (s.known ? "известный сбой" : "зелёный") : "красный"}</span>{" "}
            <span className="mono">{s.suite}</span> <span className="muted">{s.seconds} с</span>
            {!s.ok && s.tail && <pre className="pub-git">{s.tail}</pre>}
          </li>
        ))}
      </ul>
      {(result.suite_notes || []).map((n, i) => (
        <p key={i} className="hint">
          {n}
        </p>
      ))}
    </details>
  );
}
