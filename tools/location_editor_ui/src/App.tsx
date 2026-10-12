import { useCallback, useEffect, useState } from "react";
import { api, errText, type DroppedRow } from "./api";
import { AskHost, Toasts } from "./components/ui";
import Editor from "./screens/Editor";
import LocationList from "./screens/LocationList";
import Objects from "./screens/Objects";
import { getLocations } from "./store";
import type { Model } from "./types";

// Three screens by the address: #/ the list, #/loc/<id> a location,
// #/new the new place not saved yet, #/objects the owner's objects.
type Route = { kind: "list" } | { kind: "loc"; id: number } | { kind: "new" } | { kind: "objects" };

function parse(hash: string): Route {
  const m = hash.match(/^#\/loc\/(\d+)$/);
  if (m) return { kind: "loc", id: Number(m[1]) };
  if (hash === "#/new") return { kind: "new" };
  if (hash === "#/objects") return { kind: "objects" };
  return { kind: "list" };
}

export default function App() {
  const [route, setRoute] = useState<Route>(() => parse(window.location.hash));
  const [draft, setDraft] = useState<{ model: Model; dropped: DroppedRow[] } | null>(null);
  const [loaded, setLoaded] = useState<{ id: number; model: Model } | null>(null);
  const [loadErr, setLoadErr] = useState<string | null>(null);

  useEffect(() => {
    const f = () => setRoute(parse(window.location.hash));
    window.addEventListener("hashchange", f);
    return () => window.removeEventListener("hashchange", f);
  }, []);

  const go = useCallback((hash: string) => {
    if (window.location.hash === hash) setRoute(parse(hash));
    else window.location.hash = hash;
  }, []);

  // a location opened by its address
  useEffect(() => {
    if (route.kind !== "loc") return;
    if (loaded && loaded.id === route.id) return;
    let live = true;
    setLoadErr(null);
    api
      .location(route.id)
      .then((model) => live && setLoaded({ id: route.id, model }))
      .catch((e) => live && setLoadErr(errText(e)));
    return () => {
      live = false;
    };
  }, [route, loaded]);

  const openNew = (model: Model, dropped: DroppedRow[]) => {
    setDraft({ model, dropped });
    go("#/new");
  };

  const saved = (model: Model) => {
    setLoaded({ id: model.id, model });
    setDraft(null);
    getLocations(true);
    go(`#/loc/${model.id}`);
  };

  let body;
  if (route.kind === "objects") {
    body = <Objects onBack={() => go("#/")} />;
  } else if (route.kind === "new") {
    body = draft ? (
      <Editor key={`new-${draft.model.id}`} initial={draft.model} dropped={draft.dropped} onBack={() => go("#/")} onSaved={saved} onCopy={openNew} />
    ) : (
      <Gone onBack={() => go("#/")} />
    );
  } else if (route.kind === "loc") {
    if (loaded && loaded.id === route.id) {
      body = (
        <Editor
          key={`loc-${route.id}-${loaded.model.etag}`}
          initial={loaded.model}
          dropped={[]}
          onBack={() => go("#/")}
          onSaved={saved}
          onCopy={openNew}
          onReload={() => setLoaded(null)}
        />
      );
    } else if (loadErr) {
      body = (
        <div className="fatal">
          <p>Локацию {route.id} открыть не удалось: {loadErr}</p>
          <button onClick={() => go("#/")}>← К списку</button>
        </div>
      );
    } else {
      body = <div className="loading">Открываю локацию {route.id}…</div>;
    }
  } else {
    body = <LocationList onOpen={(id) => go(`#/loc/${id}`)} onNew={openNew} onObjects={() => go("#/objects")} />;
  }

  return (
    <>
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
