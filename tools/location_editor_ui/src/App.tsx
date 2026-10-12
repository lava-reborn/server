import { useCallback, useEffect, useState } from "react";
import { api, config, errText, onNotice, type DroppedRow, type Notice } from "./api";
import { AskHost, Toasts } from "./components/ui";
import Editor, { type DraftRef } from "./screens/Editor";
import LocationList from "./screens/LocationList";
import Objects from "./screens/Objects";
import { getInfo, getLocations, isPublish } from "./store";
import type { Info, Model, PublishState } from "./types";

// The screens by the address: #/ the list, #/loc/<id> a location, #/new the
// new place not saved yet (standalone), #/draft/<uuid> a draft (publish
// mode, the admin panel), #/objects the owner's objects.
type Route =
  | { kind: "list" }
  | { kind: "loc"; id: number }
  | { kind: "new" }
  | { kind: "draft"; uuid: string }
  | { kind: "objects" };

function parse(hash: string): Route {
  let m = hash.match(/^#\/loc\/(\d+)$/);
  if (m) return { kind: "loc", id: Number(m[1]) };
  m = hash.match(/^#\/draft\/([0-9a-f]{32})$/);
  if (m) return { kind: "draft", uuid: m[1] };
  if (hash === "#/new") return { kind: "new" };
  if (hash === "#/objects") return { kind: "objects" };
  return { kind: "list" };
}

// What is open in the editor: one Editor per key, kept while the address
// moves from a location to the draft its first save made.
interface Open {
  key: string;
  model: Model;
  dropped: DroppedRow[];
  draft: DraftRef | null;
  published?: PublishState | null;
}

export default function App() {
  const [route, setRoute] = useState<Route>(() => parse(window.location.hash));
  const [info, setInfo] = useState<Info | null>(null);
  const [infoErr, setInfoErr] = useState<string | null>(null);
  const [notice, setNotice] = useState<Notice>(null);
  const [newDraft, setNewDraft] = useState<{ model: Model; dropped: DroppedRow[] } | null>(null);
  const [open, setOpen] = useState<Open | null>(null);
  const [loadErr, setLoadErr] = useState<string | null>(null);
  const publish = isPublish(info);

  useEffect(() => {
    onNotice(setNotice);
    getInfo().then(setInfo, (e) => setInfoErr(errText(e)));
  }, []);

  useEffect(() => {
    const f = () => setRoute(parse(window.location.hash));
    window.addEventListener("hashchange", f);
    return () => window.removeEventListener("hashchange", f);
  }, []);

  const go = useCallback((hash: string) => {
    if (window.location.hash === hash) setRoute(parse(hash));
    else window.location.hash = hash;
  }, []);
  // the address changes and the editor stays as it is (its history of edits with it)
  const moveTo = (hash: string) => {
    setRoute(parse(hash));
    if (window.location.hash !== hash) window.location.replace(hash);
  };

  // Leaving the editor (the list, the objects) lets go of what it had open:
  // its model is the one first loaded, its draft's revision the first save's,
  // and the Editor never hands its later ones back. A place or a draft opened
  // again is fetched again, as the server has it now.
  useEffect(() => {
    if (route.kind === "list" || route.kind === "objects") setOpen(null);
  }, [route]);

  // a location or a draft opened by its address
  useEffect(() => {
    if (!info) return;
    let live = true;
    if (route.kind === "loc") {
      if (open && (open.key === `loc:${route.id}` || open.model.id === route.id)) return;
      setLoadErr(null);
      api
        .location(route.id)
        .then((model) => live && setOpen({ key: `loc:${route.id}`, model, dropped: [], draft: null }))
        .catch((e) => live && setLoadErr(errText(e)));
    } else if (route.kind === "draft") {
      if (open && open.draft?.uuid === route.uuid) return;
      setLoadErr(null);
      api
        .draft(route.uuid)
        .then((d) => {
          if (!live) return;
          if (!d.model) {
            setLoadErr("в этом черновике нет места: только объекты");
            return;
          }
          setOpen({
            key: `draft:${d.uuid}`,
            model: d.model,
            dropped: [],
            draft: { uuid: d.uuid, rev: d.rev, base: d.base, updated: d.updated },
            published: d.publish,
          });
        })
        .catch((e) => live && setLoadErr(errText(e)));
    }
    return () => {
      live = false;
    };
  }, [route, open, info]);

  const openNew = (model: Model, dropped: DroppedRow[], draft?: { uuid: string; rev: number }) => {
    if (draft) {
      // publish mode: the new place is a draft from the start
      setOpen({ key: `draft:${draft.uuid}`, model, dropped, draft: { uuid: draft.uuid, rev: draft.rev, base: info?.commit || "" } });
      go(`#/draft/${draft.uuid}`);
      return;
    }
    setNewDraft({ model, dropped });
    go("#/new");
  };

  const saved = (model: Model) => {
    setOpen({ key: `loc:${model.id}`, model, dropped: [], draft: null });
    setNewDraft(null);
    getLocations(true);
    // The saved place's address takes the place of #/new in the history
    // (Back then goes where the owner came from, never to a new place that
    // is no more), and the route moves with it in this same render.
    moveTo(`#/loc/${model.id}`);
  };

  const drafted = (d: DraftRef) => {
    setOpen((o) => (o ? { ...o, draft: d } : o));
    if (route.kind !== "draft" || route.uuid !== d.uuid) moveTo(`#/draft/${d.uuid}`);
  };

  let body;
  if (!info) {
    body = infoErr ? (
      <div className="fatal">
        <p>Редактор не отвечает: {infoErr}</p>
        <button onClick={() => window.location.reload()}>Попробовать снова</button>
      </div>
    ) : (
      <div className="loading">Открываю редактор локаций…</div>
    );
  } else if (route.kind === "objects") {
    body = <Objects onBack={() => go("#/")} publish={publish} />;
  } else if (route.kind === "new") {
    body = newDraft ? (
      <Editor
        key={`ed-loc:${newDraft.model.id}`}
        initial={newDraft.model}
        dropped={newDraft.dropped}
        publish={false}
        draft={null}
        onBack={() => go("#/")}
        onSaved={saved}
        onCopy={openNew}
      />
    ) : (
      <Gone onBack={() => go("#/")} />
    );
  } else if (route.kind === "loc" || route.kind === "draft") {
    const mine =
      open &&
      (route.kind === "loc" ? open.key === `loc:${route.id}` || open.model.id === route.id : open.draft?.uuid === route.uuid);
    if (open && mine) {
      body = (
        <Editor
          key={`ed-${open.key}`}
          initial={open.model}
          dropped={open.dropped}
          publish={publish}
          draft={open.draft}
          published={open.published || null}
          onBack={() => go("#/")}
          onSaved={saved}
          onCopy={openNew}
          onDraft={drafted}
          onReload={(fromMain) => {
            // the draft as the server has it, or the place as main has it now
            setOpen(null);
            if (fromMain && open.model.state === "ours") go(`#/loc/${open.model.id}`);
          }}
        />
      );
    } else if (loadErr) {
      body = (
        <div className="fatal">
          <p>
            {route.kind === "loc" ? `Локацию ${route.id}` : "Черновик"} открыть не удалось: {loadErr}
          </p>
          <button onClick={() => go("#/")}>← К списку</button>
        </div>
      );
    } else {
      body = <div className="loading">{route.kind === "loc" ? `Открываю локацию ${route.id}…` : "Открываю черновик…"}</div>;
    }
  } else {
    body = (
      <LocationList
        publish={publish}
        onOpen={(id) => go(`#/loc/${id}`)}
        onOpenDraft={(uuid) => go(`#/draft/${uuid}`)}
        onNew={openNew}
        onObjects={() => go("#/objects")}
      />
    );
  }

  return (
    <>
      {notice && (
        <div className={`notice ${notice}`} role="status">
          {notice === "session" ? (
            <>
              Сессия панели закончилась:{" "}
              <a href="/admin/login" target="_blank" rel="noopener">
                войдите заново в новой вкладке
              </a>
              . Эта страница остаётся открытой и сама сохранит свои правки в черновик, как только панель снова ответит.
            </>
          ) : notice === "down" ? (
            <>Редактор локаций не отвечает, пробую снова…</>
          ) : (
            <>Редактор обновляется на свежий {info?.branch || "main"}, это несколько секунд…</>
          )}
        </div>
      )}
      {publish && info?.stale && (
        <div className="notice stale" role="status">
          Свежий {info.branch} получить не удалось ({info.stale}): список и проверки — по коммиту {info.commit?.slice(0, 8)}.
        </div>
      )}
      {body}
      <Toasts />
      <AskHost />
    </>
  );
}

function Gone({ onBack }: { onBack: () => void }) {
  return (
    <div className="fatal">
      <p>Несохранённое новое место пропало вместе со старой страницей: сделайте его ещё раз.</p>
      <button onClick={onBack}>← К списку</button>
    </div>
  );
}

export const inPanel = () => config.panel;
