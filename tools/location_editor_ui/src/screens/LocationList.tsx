import { useEffect, useMemo, useState } from "react";
import { api, errText, type DroppedRow } from "../api";
import PublishDialog from "../components/PublishDialog";
import { Field, Modal, Spinner, ask, toast } from "../components/ui";
import { getInfo, getLocations, getPalette } from "../store";
import type { DraftRow, Info, LocRow, Model, PendingObject } from "../types";

type Made = (m: Model, d: DroppedRow[], draft?: { uuid: string; rev: number }) => void;
const KIND_RU: Record<string, string> = { new: "новый", update: "правка", delete: "удалён" };
const when = (iso: string) => {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleString("ru-RU", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
};

const SIDE_RU: Record<string, string> = { W: "З", N: "С", E: "В", S: "Ю", a: "a", b: "b" };
const LIMIT = 300;

// «Локации»: every location the editor knows, the original's and ours,
// with a search, filters and a picture of the one picked.
export default function LocationList(props: {
  publish: boolean;
  onOpen: (id: number) => void;
  onOpenDraft: (uuid: string) => void;
  onNew: Made;
  onObjects: () => void;
}) {
  const [rows, setRows] = useState<LocRow[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [info, setInfo] = useState<Info | null>(null);
  const [q, setQ] = useState("");
  const [who, setWho] = useState("all");
  const [lib, setLib] = useState("");
  const [size, setSize] = useState("");
  const [war, setWar] = useState("");
  const [more, setMore] = useState(false);
  const [sel, setSel] = useState<number | null>(null);
  const [dialog, setDialog] = useState<"copy" | "empty" | null>(null);
  // publish mode: the drafts on the server, the objects waiting for a publish
  const [drafts, setDrafts] = useState<DraftRow[] | null>(null);
  const [pending, setPending] = useState<PendingObject[]>([]);
  const [publishObjects, setPublishObjects] = useState(false);

  const loadDrafts = () =>
    api.drafts().then(
      (d) => {
        setDrafts(d.drafts);
        setPending(d.objects || []);
      },
      () => setDrafts((x) => x || []),
    );

  useEffect(() => {
    getLocations()
      .then(setRows)
      .catch((e) => setErr(errText(e)));
    getInfo().then(setInfo, () => undefined);
    if (props.publish) {
      loadDrafts();
      const t = window.setInterval(loadDrafts, 20000);
      return () => window.clearInterval(t);
    }
  }, [props.publish]);

  const dropDraft = async (d: DraftRow) => {
    const go = await ask({
      title: "Удалить черновик?",
      text: `Черновик «${d.title || "без названия"}» пропадёт со всеми правками. В main он не попадал.`,
      ok: "Удалить",
      danger: true,
    });
    if (!go) return;
    try {
      await api.deleteDraft(d.uuid);
      loadDrafts();
    } catch (e) {
      toast("err", errText(e));
    }
  };

  const libraries = useMemo(() => [...new Set((rows || []).map((r) => r.library))].sort((a, b) => a.localeCompare(b)), [rows]);

  const shown = useMemo(() => {
    if (!rows) return [];
    const words = q.trim().toLowerCase().split(/\s+/).filter(Boolean);
    return rows.filter((r) => {
      if (who !== "all" && r.state !== who) return false;
      if (lib && r.library !== lib) return false;
      if (size && r.size.join("x") !== size) return false;
      if (war && r.war !== war) return false;
      if (!words.length) return true;
      const hay = `${r.id} ${r.title} ${r.fn} ${r.library}`.toLowerCase();
      return words.every((w) => hay.includes(w));
    });
  }, [rows, q, who, lib, size, war]);

  const picked = rows?.find((r) => r.id === sel) || null;
  const ours = rows ? rows.filter((r) => r.state === "ours").length : 0;

  return (
    <div className="screen list-screen">
      <header className="topbar">
        <span className="le-brand">LAVA · Локации</span>
        <span className="muted small">
          {rows ? `${rows.length} локаций, наших ${ours}` : "читаю список…"}
          {info && !info.res_original && " · внимание: RES не оригинальный, пересчёт карты может сдвинуть места"}
        </span>
        <span className="grow" />
        <button onClick={props.onObjects}>Мои объекты</button>
        <button onClick={() => setDialog("empty")}>Новая пустая</button>
        <button className="primary" disabled={!picked || picked.closed} onClick={() => setDialog("copy")}>
          Новая из копии{picked ? ` #${picked.id}` : ""}
        </button>
        <button disabled={!picked} onClick={() => picked && props.onOpen(picked.id)}>
          Открыть
        </button>
      </header>
      <div className="list-body">
        <section className="list-main">
          <div className="filters-row">
            <input
              className="search"
              placeholder="Поиск: номер, название, fn, библиотека"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              autoFocus
            />
            <select value={who} onChange={(e) => setWho(e.target.value)} aria-label="Чьи">
              <option value="all">Все</option>
              <option value="ours">Наши</option>
              <option value="original">Оригинал</option>
            </select>
            <select value={lib} onChange={(e) => setLib(e.target.value)} aria-label="Библиотека">
              <option value="">Любая библиотека</option>
              {libraries.map((l) => (
                <option key={l}>{l}</option>
              ))}
            </select>
            <select value={size} onChange={(e) => setSize(e.target.value)} aria-label="Размер">
              <option value="">Любой размер</option>
              <option value="64x128">64×128</option>
              <option value="32x64">32×64</option>
            </select>
            <select value={war} onChange={(e) => setWar(e.target.value)} aria-label="Мир или война">
              <option value="">Мир и война</option>
              <option value="0">Мирные</option>
              <option value="1">Военные</option>
            </select>
          </div>
          {props.publish && drafts && drafts.length > 0 && (
            <div className="drafts">
              <h3>Черновики</h3>
              <table className="loc-table draft-table">
                <tbody>
                  {drafts.map((d) => (
                    <tr key={d.uuid} onDoubleClick={() => props.onOpenDraft(d.uuid)}>
                      <td className="num">{typeof d.id === "number" ? d.id : d.id ? "новое" : ""}</td>
                      <td>
                        {d.title || <span className="muted">без названия</span>}
                        {d.stale && (
                          <span className="tag war" title={d.stale}>
                            устарел
                          </span>
                        )}
                        {d.publish?.state === "running" && <span className="tag ours">публикуется</span>}
                        {d.publish?.state === "failed" && (
                          <span className="tag war" title={d.publish.result?.error}>
                            не опубликован
                          </span>
                        )}
                      </td>
                      <td className="small muted">
                        {d.login}
                        {d.created_by && d.created_by !== d.login ? ` (начал ${d.created_by})` : ""}, {when(d.updated)}
                      </td>
                      <td className="actions-cell">
                        <button className="small" onClick={() => props.onOpenDraft(d.uuid)}>
                          Открыть
                        </button>
                        <button className="small ghost" onClick={() => dropDraft(d)} disabled={d.publish?.state === "running"}>
                          Удалить
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {props.publish && pending.length > 0 && (
            <div className="banner">
              Мои объекты ждут публикации:{" "}
              {pending.map((o) => `${o.id} «${o.title}» (${KIND_RU[o.kind] || o.kind})`).join(", ")}. Они уйдут в main с ближайшей
              публикацией.{" "}
              <button className="small" onClick={() => setPublishObjects(true)}>
                Опубликовать только объекты
              </button>
            </div>
          )}
          {err && <div className="banner err">Список не прочитан: {err}</div>}
          {!rows && !err && (
            <div className="loading">
              <Spinner /> Читаю локации…
            </div>
          )}
          {rows && (
            <div className="table-wrap">
              <table className="loc-table">
                <thead>
                  <tr>
                    <th>№</th>
                    <th>Название</th>
                    <th>fn</th>
                    <th>Размер</th>
                    <th>Библиотека</th>
                    <th>Чья</th>
                    <th>Карта</th>
                    <th>Жители</th>
                    <th>Выходы</th>
                  </tr>
                </thead>
                <tbody>
                  {(more ? shown : shown.slice(0, LIMIT)).map((r) => (
                    <tr
                      key={r.id}
                      className={`${r.id === sel ? "sel" : ""}${r.closed ? " closed" : ""}`}
                      onClick={() => setSel(r.id)}
                      onDoubleClick={() => props.onOpen(r.id)}
                    >
                      <td className="num">{r.id}</td>
                      <td>
                        {r.title || <span className="muted">без названия</span>}
                        {r.war === "1" && <span className="tag war">война</span>}
                      </td>
                      <td className="mono small">{r.fn}</td>
                      <td className="small">{r.size.join("×")}</td>
                      <td className="small">{r.library}</td>
                      <td>{r.state === "ours" ? <span className="tag ours">наша</span> : <span className="muted small">оригинал</span>}</td>
                      <td className="mono small">{r.cell ? r.cell.join(",") : ""}</td>
                      <td className="num">{r.inhabitants || ""}</td>
                      <td className="small">{r.sides.map((s) => SIDE_RU[s] || s).join(" ")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!more && shown.length > LIMIT && (
                <button className="more" onClick={() => setMore(true)}>
                  Показать ещё {shown.length - LIMIT}
                </button>
              )}
              {!shown.length && <p className="muted pad">Ничего не нашлось.</p>}
            </div>
          )}
        </section>
        <aside className="list-side">{picked ? <Preview row={picked} /> : <Help publish={props.publish} />}</aside>
      </div>
      {dialog === "copy" && picked && (
        <NewFromCopy row={picked} publish={props.publish} onClose={() => setDialog(null)} onMade={props.onNew} />
      )}
      {dialog === "empty" && info && (
        <NewEmpty info={info} libraries={libraries} publish={props.publish} onClose={() => setDialog(null)} onMade={props.onNew} />
      )}
      {publishObjects && (
        <PublishDialog
          uuid={null}
          model={null}
          title="мои объекты"
          objects={pending}
          onClose={() => {
            setPublishObjects(false);
            loadDrafts();
          }}
          onDone={() => {
            setPublishObjects(false);
            toast("ok", "Объекты опубликованы", 8000);
            loadDrafts();
          }}
        />
      )}
    </div>
  );
}

function Help({ publish }: { publish: boolean }) {
  return (
    <div className="pad help">
      <h3>Как сделать новое место</h3>
      <ol>
        <li>Найдите похожую локацию и выберите её в списке.</li>
        <li>«Новая из копии»: место получит её картинку, стены, выходы и входы, а существа станут жителями.</li>
        <li>Или «Новая пустая»: ровное поле 64×128 или 32×64 с выходами по краям.</li>
        {publish ? (
          <li>
            В редакторе расставьте объекты, стены, выходы, жителей, путь сюда и клетку на карте. Правки сами сохраняются в черновик;
            в игру место уходит кнопкой «Опубликовать».
          </li>
        ) : (
          <li>В редакторе расставьте объекты, стены, выходы, жителей, путь сюда и клетку на карте, затем «Сохранить».</li>
        )}
      </ol>
      <p className="muted">Локации оригинала открываются только для просмотра. Свои картинки добавляются в «Мои объекты».</p>
    </div>
  );
}

const previews = new Map<number, string>();

function Preview({ row }: { row: LocRow }) {
  const [url, setUrl] = useState<string | null>(previews.get(row.id) || null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    setErr(null);
    const have = previews.get(row.id);
    setUrl(have || null);
    if (!have) {
      const scale = row.size[0] > 32 ? 0.14 : 0.28;
      api
        .renderSaved(row.id, "art,obstacles,exits,entries", scale)
        .then((b) => {
          const u = URL.createObjectURL(b);
          previews.set(row.id, u);
          if (live) setUrl(u);
        })
        .catch((e) => live && setErr(errText(e)));
    }
    return () => {
      live = false;
    };
  }, [row.id]);
  return (
    <div className="pad le-preview">
      <h3>
        #{row.id} {row.title}
      </h3>
      <div className="preview-img">
        {url ? <img src={url} alt={`локация ${row.id}`} /> : err ? <span className="err-text">{err}</span> : <Spinner />}
      </div>
      <p className="legend small">
        <i className="sw wall" /> стены <i className="sw exit" /> выходы <i className="sw entry" /> входы
      </p>
      <dl className="facts">
        <dt>fn</dt>
        <dd className="mono">{row.fn}</dd>
        <dt>Библиотека</dt>
        <dd>{row.library}</dd>
        <dt>Размер</dt>
        <dd>{row.size.join(" × ")}</dd>
        <dt>Режим</dt>
        <dd>
          {row.war === "1" ? "военная" : "мирная"}, pvp {row.pvp === "1" ? "да" : "нет"}
        </dd>
        <dt>Выходы</dt>
        <dd>{row.sides.map((s) => SIDE_RU[s] || s).join(" ") || "нет"}</dd>
        <dt>Карта</dt>
        <dd>{row.cell ? row.cell.join(", ") : "не на карте"}</dd>
        <dt>Жители</dt>
        <dd>{row.inhabitants}</dd>
        {row.from !== null && (
          <>
            <dt>Копия</dt>
            <dd>#{row.from}</dd>
          </>
        )}
      </dl>
      {row.closed && <p className="warn-text">262 «Тотем» закрыт для редактора.</p>}
    </div>
  );
}

export function NewFromCopy(props: {
  row: { id: number; title: string };
  publish?: boolean;
  onClose: () => void;
  onMade: Made;
}) {
  const [title, setTitle] = useState("");
  const [why, setWhy] = useState("");
  const [id, setId] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const make = async () => {
    setBusy(true);
    setErr(null);
    try {
      const body: Record<string, unknown> = { from: props.row.id, title, why };
      if (id.trim() && !props.publish) body.id = Number(id);
      const got = await api.newModel(body);
      for (const n of got.notes || []) toast("info", n, 12000);
      props.onMade(got.model, got.dropped || [], got.draft);
    } catch (e) {
      setErr(errText(e));
      setBusy(false);
    }
  };
  return (
    <Modal
      title={`Новая из копии #${props.row.id} «${props.row.title}»`}
      onClose={props.onClose}
      footer={
        <>
          <button onClick={props.onClose}>Отмена</button>
          <button
            className="primary"
            disabled={busy || !title.trim() || !why.trim()}
            title={!title.trim() || !why.trim() ? "Нужны название и «Почему это место есть»" : undefined}
            onClick={make}
          >
            {busy ? "Делаю…" : "Сделать"}
          </button>
        </>
      }
    >
      <p className="muted">
        Новое место возьмёт картинку, стены, выходы и входы этой локации. Её существа станут жителями.{" "}
        {props.publish
          ? "Оно сразу станет черновиком; в игру уйдёт, когда вы нажмёте «Опубликовать»."
          : "Пока вы не нажмёте «Сохранить» в редакторе, ничего не записывается."}
      </p>
      <Field label="Название (обязательно)">
        <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Например: Старый склад" autoFocus />
      </Field>
      <Field label="Почему это место есть (обязательно)" hint="Ваше слово: попадёт в data/locations/index.json. Без него «Сделать» не нажимается">
        <textarea rows={3} value={why} onChange={(e) => setWhy(e.target.value)} placeholder="Зачем это место в игре" />
      </Field>
      {!props.publish && (
        <Field label="Номер" hint="Пусто: первый свободный от 1381">
          <input value={id} onChange={(e) => setId(e.target.value.replace(/\D/g, ""))} placeholder="авто" inputMode="numeric" />
        </Field>
      )}
      {err && <p className="err-text">{err}</p>}
    </Modal>
  );
}

function NewEmpty(props: {
  info: Info;
  libraries: string[];
  publish?: boolean;
  onClose: () => void;
  onMade: Made;
}) {
  const [title, setTitle] = useState("");
  const [why, setWhy] = useState("");
  const [size, setSize] = useState("64x128");
  const [library, setLibrary] = useState("Desert");
  const [bg, setBg] = useState("bg_desert1.jpg");
  const [bgs, setBgs] = useState<string[] | null>(null);
  const [ring, setRing] = useState(true);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    setBgs(null);
    getPalette(library)
      .then((p) => {
        if (!live) return;
        const names = p.items.filter((i) => i.type === "lib").map((i) => i.name);
        const bgFirst = [...names.filter((n) => /bg|back|fon|ground|sand|floor/i.test(n)), ...names.filter((n) => !/bg|back|fon|ground|sand|floor/i.test(n))];
        setBgs(bgFirst);
        if (!bgFirst.includes(bg)) setBg(bgFirst[0] || "");
      })
      .catch(() => live && setBgs([]));
    return () => {
      live = false;
    };
  }, [library]);

  const make = async () => {
    setBusy(true);
    setErr(null);
    try {
      const [w, h] = size.split("x").map(Number);
      const got = await api.newModel({
        empty: { w, h, library, background: { type: "lib", id: bg, fx: "" }, ring },
        title,
        why,
      });
      for (const n of got.notes || []) toast("info", n, 12000);
      props.onMade(got.model, got.dropped || [], got.draft);
    } catch (e) {
      setErr(errText(e));
      setBusy(false);
    }
  };
  return (
    <Modal
      title="Новая пустая локация"
      onClose={props.onClose}
      footer={
        <>
          <button onClick={props.onClose}>Отмена</button>
          <button
            className="primary"
            disabled={busy || !title.trim() || !why.trim()}
            title={!title.trim() || !why.trim() ? "Нужны название и «Почему это место есть»" : undefined}
            onClick={make}
          >
            {busy ? "Делаю…" : "Сделать"}
          </button>
        </>
      }
    >
      <Field label="Название (обязательно)">
        <input value={title} onChange={(e) => setTitle(e.target.value)} autoFocus />
      </Field>
      <Field label="Почему это место есть (обязательно)" hint="Ваше слово: попадёт в data/locations/index.json. Без него «Сделать» не нажимается">
        <textarea rows={3} value={why} onChange={(e) => setWhy(e.target.value)} placeholder="Зачем это место в игре" />
      </Field>
      <Field label="Размер">
        <select value={size} onChange={(e) => setSize(e.target.value)}>
          {props.info.sizes.map(([w, h]) => (
            <option key={`${w}x${h}`} value={`${w}x${h}`}>
              {w} × {h} клеток
            </option>
          ))}
        </select>
      </Field>
      <Field label="Библиотека картинок" hint="У локации одна библиотека: её картинки ставятся на клетки">
        <select value={library} onChange={(e) => setLibrary(e.target.value)}>
          {props.libraries.map((l) => (
            <option key={l}>{l}</option>
          ))}
        </select>
      </Field>
      <Field label="Фон">
        {bgs === null ? (
          <span className="muted">
            <Spinner /> читаю библиотеку…
          </span>
        ) : (
          <select value={bg} onChange={(e) => setBg(e.target.value)}>
            {bgs.map((n) => (
              <option key={n}>{n}</option>
            ))}
          </select>
        )}
      </Field>
      <label className="check">
        <input type="checkbox" checked={ring} onChange={(e) => setRing(e.target.checked)} /> Выходы по краям и кольцо входов, как в
        шаблонах пустыни
      </label>
      {err && <p className="err-text">{err}</p>}
    </Modal>
  );
}
