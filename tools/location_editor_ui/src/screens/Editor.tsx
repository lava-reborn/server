import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, ApiError, errText, type DroppedRow } from "../api";
import { ALL_LAYERS, LocCanvas, ZOOM_MAX, ZOOM_MIN, type Layer, type Mark, type PointerInfo } from "../canvas";
import Problems from "../components/Problems";
import PublishDialog from "../components/PublishDialog";
import { Modal, Spinner, ask, toast } from "../components/ui";
import WalkInPicker from "../components/WalkInPicker";
import { cellPx, disc, inGrid, key, neighbours, pxCell, rectCells } from "../hex";
import { forgetPalettes, getInfo, getLocations, getPalette, mobIcon, mobName } from "../store";
import { EntriesPanel, ExitsPanel, WallsPanel, type ExitSide, type WallMode } from "../tools/CellPanels";
import InhabitantsPanel from "../tools/InhabitantsPanel";
import { MapPanel, MapView } from "../tools/MapTool";
import ObjectsPanel from "../tools/ObjectsPanel";
import PropsPanel from "../tools/PropsPanel";
import WaysPanel from "../tools/WaysPanel";
import type { Cell, Info, Mob, Model, Palette, PaletteItem, Problem, PublishState } from "../types";
import { NewFromCopy } from "./LocationList";

type Tool = "props" | "objects" | "walls" | "exits" | "entries" | "wars" | "inhabitants" | "ways" | "map";
const TOOLS: { id: Tool; label: string; icon: string }[] = [
  { id: "props", label: "Свойства", icon: "⚙" },
  { id: "objects", label: "Объекты", icon: "▣" },
  { id: "walls", label: "Стены", icon: "▦" },
  { id: "exits", label: "Выходы", icon: "⇥" },
  { id: "entries", label: "Входы", icon: "⊕" },
  { id: "wars", label: "Военные входы", icon: "⚔" },
  { id: "inhabitants", label: "Жители", icon: "☺" },
  { id: "ways", label: "Проходы", icon: "⇄" },
  { id: "map", label: "Карта", icon: "◎" },
];
const LAYER_RU: Record<Layer, string> = {
  art: "Картинка",
  sprites: "Объекты",
  inhabitants: "Жители",
  walls: "Стены",
  exits: "Выходы",
  entries: "Входы",
  wars: "Военные входы",
  spawns: "Существа файла",
  grid: "Сетка",
};
const SIDE_RU: Record<string, string> = { W: "запад", N: "север", E: "восток", S: "юг", a: "дверь a", b: "дверь b" };
const STATE_RU = { new: "новая, не сохранена", ours: "наша", original: "оригинал: только просмотр" };
const STATE_RU_PUBLISH = { new: "новая, черновик", ours: "наша", original: "оригинал: только просмотр" };

// what the page remembers between the screens (not in the browser's storage)
const ui = { tool: "objects" as Tool, layers: new Set<Layer>(ALL_LAYERS) };
const views = new Map<number | string, { zoom: number; panX: number; panY: number }>();

// Publish mode (the admin panel): what the page edits is a draft on the
// server, saved after AUTOSAVE_MS of quiet; until it is, a copy waits in the
// browser (localStorage), which a page opened again takes back.
export interface DraftRef {
  uuid: string;
  rev: number;
  base: string;
  updated?: string;
}
const AUTOSAVE_MS = 3000;
const RETRY_MS = 10000;
const backupKey = (d: DraftRef | null, m: Model) => `lava-loc-draft:${d ? d.uuid : `loc:${m.id}`}`;
function readBackup(k: string): { model: Model; rev: number; at: number } | null {
  try {
    const t = window.localStorage.getItem(k);
    return t ? JSON.parse(t) : null;
  } catch {
    return null;
  }
}
function writeBackup(k: string, v: { model: Model; rev: number; at: number }) {
  try {
    window.localStorage.setItem(k, JSON.stringify(v));
  } catch {
    /* a private window or a full storage: the server's draft is the copy */
  }
}
function dropBackup(k: string) {
  try {
    window.localStorage.removeItem(k);
  } catch {
    /* nothing kept */
  }
}
const clock = (iso?: string) => {
  if (!iso) return "";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
};

interface Stroke {
  before: Model;
  draft: Model;
  start: Cell;
  last: Cell;
  erase: boolean;
  cells: Map<string, Cell>;
}

export default function Editor(props: {
  initial: Model;
  dropped: DroppedRow[];
  publish: boolean;
  draft: DraftRef | null;
  published?: PublishState | null;
  onBack: () => void;
  onSaved: (m: Model) => void;
  onCopy: (m: Model, d: DroppedRow[], draft?: { uuid: string; rev: number }) => void;
  onDraft?: (d: DraftRef) => void;
  onReload?: (fromMain: boolean) => void;
}) {
  const [model, setModelState] = useState<Model>(props.initial);
  const modelRef = useRef<Model>(props.initial);
  const [dirty, setDirty] = useState(props.initial.state === "new");
  const undo = useRef<Model[]>([]);
  const redo = useRef<Model[]>([]);
  const [, setHist] = useState(0);
  const [info, setInfo] = useState<Info | null>(null);
  const [tool, setToolState] = useState<Tool>(ui.tool);
  const [layers, setLayers] = useState<Set<Layer>>(new Set(ui.layers));
  const [zoom, setZoom] = useState(0.5);
  const [hover, setHover] = useState<Cell | null>(null);
  const [problems, setProblems] = useState<Problem[]>([]);
  const [checking, setChecking] = useState(false);
  const [fullCheck, setFullCheck] = useState(false);
  const [seconds, setSeconds] = useState<number | null>(null);
  const [selProblem, setSelProblem] = useState<number | null>(null);
  const [flash, setFlash] = useState<Cell[]>([]);
  const [selSprite, setSelSprite] = useState<[number, number] | null>(null);
  const [selInh, setSelInh] = useState<number | null>(null);
  const [palette, setPalette] = useState<Palette | null>(null);
  const [paletteErr, setPaletteErr] = useState<string | null>(null);
  const [armed, setArmed] = useState<PaletteItem | null>(null);
  const [stamp, setStamp] = useState(true);
  const [wallMode, setWallMode] = useState<WallMode>("brush");
  const [wallCode, setWallCode] = useState("f");
  const [brush, setBrush] = useState(0);
  const [exitSide, setExitSide] = useState<ExitSide>("auto");
  const [exitErase, setExitErase] = useState(false);
  const [armedMob, setArmedMob] = useState<Mob | null>(null);
  const [preview, setPreview] = useState<Cell[]>([]);
  const [saving, setSaving] = useState(false);
  const [conflict, setConflict] = useState<{ text: string; nextId?: number } | null>(null);
  const [picker, setPicker] = useState<{ from: number; index: number | null; focus?: Cell[] } | null>(null);
  const [copying, setCopying] = useState(false);
  const [dropped, setDropped] = useState<DroppedRow[]>(props.dropped);
  const [bgState, setBgState] = useState<"wait" | "ok" | string>("wait");

  const host = useRef<HTMLDivElement>(null);
  const canvas = useRef<LocCanvas | null>(null);
  const stroke = useRef<Stroke | null>(null);
  const drag = useRef<{ kind: "sprite" | "inh"; id: [number, number] | number; start: [number, number]; moved: boolean } | null>(null);
  const queue = useRef<Promise<unknown>>(Promise.resolve());

  const readOnly = model.state === "original" || !!model.closed || props.published?.state === "done";
  // While a save runs nothing is edited: the page is veiled, the keys wait,
  // and an edit that slipped through is refused here (its answer replaces
  // the model).
  const savingRef = useRef(false);
  const [saveSec, setSaveSec] = useState(0);
  const busySaving = () => {
    if (!savingRef.current) return false;
    toast("info", "Идёт сохранение: править можно будет после ответа.");
    return true;
  };

  // --- the model and its history -------------------------------------------------
  const setModel = useCallback((m: Model) => {
    modelRef.current = m;
    setModelState(m);
  }, []);
  // Edits of one text field one after another are one step of the history
  // (a title typed letter by letter is undone at once).
  const lastGroup = useRef<string | null>(null);
  const commit = useCallback(
    (next: Model, before?: Model, group?: string) => {
      if (savingRef.current) return;
      if (!(group && lastGroup.current === group && undo.current.length)) {
        undo.current.push(before || modelRef.current);
        if (undo.current.length > 100) undo.current.shift();
      }
      lastGroup.current = group || null;
      redo.current = [];
      setModel(next);
      setDirty(true);
      setHist((h) => h + 1);
    },
    [setModel],
  );
  // A step back or forward keeps what the disk says of the place (its id,
  // state and etag): a save in between does not make the history stale.
  const onDisk = (m: Model): Model => ({ ...m, id: modelRef.current.id, state: modelRef.current.state, etag: modelRef.current.etag });
  const doUndo = useCallback(() => {
    if (savingRef.current) return;
    const prev = undo.current.pop();
    if (!prev) return;
    lastGroup.current = null;
    redo.current.push(modelRef.current);
    setModel(onDisk(prev));
    setSelSprite(null);
    setSelInh(null);
    setDirty(true);
    setHist((h) => h + 1);
  }, [setModel]);
  const doRedo = useCallback(() => {
    if (savingRef.current) return;
    const next = redo.current.pop();
    if (!next) return;
    lastGroup.current = null;
    undo.current.push(modelRef.current);
    setModel(onDisk(next));
    setSelSprite(null);
    setSelInh(null);
    setDirty(true);
    setHist((h) => h + 1);
  }, [setModel]);
  const patch = useCallback(
    (fn: (m: Model) => Model, group?: string) => {
      if (readOnly) {
        toast("info", "Локация оригинала только для просмотра: сделайте копию, чтобы править.");
        return;
      }
      if (busySaving()) return;
      commit(fn(modelRef.current), undefined, group);
    },
    [commit, readOnly],
  );

  /** One edit the server works out (place, move, delete, nudge, exits, ring), one at a time. */
  const serverEdit = useCallback(
    (op: Record<string, unknown>) => {
      if (readOnly) {
        toast("info", "Локация оригинала только для просмотра: сделайте копию, чтобы править.");
        return Promise.resolve(null);
      }
      if (busySaving()) return Promise.resolve(null);
      const run = queue.current.then(async () => {
        try {
          const before = modelRef.current;
          const r = await api.edit(before, op);
          commit(r.model, before);
          return r;
        } catch (e) {
          toast("err", errText(e));
          return null;
        }
      });
      queue.current = run;
      return run;
    },
    [commit, readOnly],
  );

  const setTool = (t: Tool) => {
    ui.tool = t;
    setToolState(t);
    setArmed(null);
    setArmedMob(null);
    setPreview([]);
  };

  // --- the canvas ----------------------------------------------------------------
  const pointer = useRef<(p: PointerInfo) => void>(() => undefined);
  const hovered = useRef<(c: Cell | null, px: [number, number] | null) => void>(() => undefined);
  useEffect(() => {
    if (!host.current) return;
    const c = new LocCanvas(host.current, {
      pointer: (p) => pointer.current(p),
      hover: (cell, px) => hovered.current(cell, px),
      view: (z) => setZoom(z),
    });
    c.setModel(modelRef.current);
    c.setIcons((t) => mobIcon(t));
    c.layers = new Set(ui.layers);
    canvas.current = c;
    const v = views.get(modelRef.current.id);
    requestAnimationFrame(() => {
      if (v) {
        c.zoom = v.zoom;
        c.panX = v.panX;
        c.panY = v.panY;
        setZoom(v.zoom);
        c.request();
      } else c.fit();
    });
    return () => {
      views.set(modelRef.current.id, { zoom: c.zoom, panX: c.panX, panY: c.panY });
      c.destroy();
      canvas.current = null;
    };
    // the canvas lives as long as the editor (the map tool hides it)
  }, []);

  useEffect(() => {
    canvas.current?.setModel(model);
  }, [model]);
  useEffect(() => {
    ui.layers = new Set(layers);
    canvas.current?.setLayers(layers);
  }, [layers]);
  useEffect(() => {
    canvas.current?.setSelection(selSprite, selInh);
  }, [selSprite, selInh, model]);
  useEffect(() => {
    if (canvas.current) {
      canvas.current.panLeft = tool === "props" || tool === "ways";
      canvas.current.setCursor(tool === "props" || tool === "ways" ? "grab" : tool === "objects" && !armed ? "default" : "crosshair");
    }
  }, [tool, armed]);
  useEffect(() => {
    const marks: Mark[] = [];
    if (flash.length) marks.push({ cells: flash, stroke: "#ff5a3c", width: 3, fill: "rgba(226,84,58,0.25)", ring: 16 });
    if (preview.length) marks.push({ cells: preview, fill: "rgba(240,196,106,0.45)", stroke: "#f0c46a", width: 1 });
    if (tool === "ways") {
      for (const s of ["a", "b"]) {
        const cells = model.exits.filter((e) => e[2] === s).map((e) => [e[0], e[1]] as Cell);
        if (cells.length) marks.push({ cells, stroke: s === "a" ? "#00e6e6" : "#ff46d2", width: 3 });
      }
    }
    canvas.current?.setMarks(marks);
  }, [flash, preview, tool, model]);

  // the art under the sprites: background and decals, drawn by the server once
  const artKey = JSON.stringify([model.background, model.decals, model.attrs.library, model.attrs.bg, model.attrs.bgExt, model.width, model.height]);
  useEffect(() => {
    let url: string | null = null;
    let live = true;
    setBgState("wait");
    api
      .render(modelRef.current, "background,decals", 1)
      .then((b) => {
        url = URL.createObjectURL(b);
        if (!live) return URL.revokeObjectURL(url);
        canvas.current?.setBackground(url, 1);
        setBgState("ok");
      })
      .catch((e) => live && setBgState(errText(e)));
    return () => {
      live = false;
      if (url) URL.revokeObjectURL(url);
    };
  }, [artKey]);

  // the palette: what this location can place, and how each sprite is drawn
  useEffect(() => {
    let live = true;
    let tries = 0;
    let timer = 0;
    const load = (fresh: boolean) => {
      getPalette(model.attrs.library, fresh)
        .then((p) => {
          if (!live) return;
          setPalette(p);
          setPaletteErr(null);
          if (p.warming && tries++ < 30) timer = window.setTimeout(() => load(true), 5000);
        })
        .catch((e) => live && setPaletteErr(errText(e)));
    };
    load(false);
    return () => {
      live = false;
      window.clearTimeout(timer);
    };
  }, [model.attrs.library]);
  const artMap = useMemo(() => {
    const m = new Map<string, { url: string; ox: number; oy: number }>();
    for (const it of palette?.items || []) {
      if (!it.picture) continue;
      const k = it.type === "lib" ? `lib:${it.name}` : `ext:${it.name.toLowerCase()}`;
      m.set(k, { url: it.picture, ox: it.ox || 0, oy: it.oy || 0 });
    }
    return m;
  }, [palette]);
  useEffect(() => {
    canvas.current?.setArt((sp) => artMap.get(sp.type === "ext" ? `ext:${sp.id.toLowerCase()}` : `lib:${sp.id}`) || null);
  }, [artMap]);

  useEffect(() => {
    getInfo().then(setInfo, () => undefined);
  }, []);

  // --- the live check -------------------------------------------------------------
  const checkSeq = useRef(0);
  useEffect(() => {
    const seq = ++checkSeq.current;
    setFullCheck(false);
    const t = window.setTimeout(() => {
      setChecking(true);
      api
        .check(modelRef.current, true)
        .then((r) => {
          if (seq !== checkSeq.current) return;
          setProblems(r.problems);
          setSeconds(r.seconds);
          setSelProblem(null);
        })
        .catch((e) => seq === checkSeq.current && setProblems([{ level: "warning", what: "server", text: `проверка не удалась: ${errText(e)}`, cells: [], loc: null }]))
        .finally(() => seq === checkSeq.current && setChecking(false));
    }, 600);
    return () => window.clearTimeout(t);
  }, [model]);

  const runFullCheck = async () => {
    const seq = ++checkSeq.current;
    setChecking(true);
    try {
      const r = await api.check(modelRef.current, false);
      if (seq !== checkSeq.current) return;
      setProblems(r.problems);
      setSeconds(r.seconds);
      setFullCheck(true);
      setSelProblem(null);
      const errors = r.problems.filter((p) => p.level === "error").length;
      toast(errors ? "err" : "ok", errors ? `Проверка: ошибок ${errors}, список справа` : `Проверка пройдена за ${r.seconds} с`);
    } catch (e) {
      toast("err", errText(e));
    } finally {
      if (seq === checkSeq.current) setChecking(false);
    }
  };

  // --- save ---------------------------------------------------------------------
  const savePending = useRef(false);
  const save = async (given?: Model) => {
    if (readOnly || savePending.current) return;
    savePending.current = true;
    setSaving(true);
    setSaveSec(0);
    const t0 = Date.now();
    const tick = window.setInterval(() => setSaveSec(Math.round((Date.now() - t0) / 1000)), 1000);
    try {
      // an edit the server is still working out goes in first; from then
      // on nothing is edited until the answer
      await queue.current.catch(() => undefined);
      savingRef.current = true;
      const m = given || modelRef.current;
      const r = await api.save(m);
      const d = r.data;
      if (r.status === 200 && d.model) {
        const written = d.written || [];
        toast("ok", written.length ? `Сохранено: ${written.join(", ")}` : "Сохранять нечего: на диске то же самое", 9000);
        setDirty(false);
        forgetPalettes();
        // the place as the disk has it now (its etag, state "ours"); the
        // history of edits stays, a step back after the save included
        lastGroup.current = null;
        if (d.model.id === modelRef.current.id) setModel(d.model);
        props.onSaved(d.model);
        return;
      }
      if (r.status === 409) {
        setConflict({ text: d.error || "локация изменилась на диске", nextId: d.next_id });
        return;
      }
      if (r.status === 422) {
        const list = d.problems || [];
        setProblems(list);
        setFullCheck(true);
        toast("err", `Не сохранено: ${d.error || "есть ошибки"}. Что исправить — в «Проблемах».`);
        // the first error that has a place here is shown on the canvas
        const first = list.find((p) => p.level === "error" && p.cells.length && (p.loc === null || p.loc === m.id));
        if (first && tool !== "map") {
          setSelProblem(list.indexOf(first));
          setFlash(first.cells);
          canvas.current?.centerOn(first.cells[0], Math.max(canvas.current.zoom, 0.8));
        }
        return;
      }
      toast("err", `Не сохранено: ${d.error || `ответ ${r.status}`}`);
    } catch (e) {
      toast("err", `Не сохранено: ${errText(e)}`);
    } finally {
      window.clearInterval(tick);
      savingRef.current = false;
      savePending.current = false;
      setSaving(false);
    }
  };

  // --- the draft (publish mode) -------------------------------------------------------
  const draftRef = useRef<DraftRef | null>(props.draft);
  const savedText = useRef(JSON.stringify(props.initial));
  const [draftStatus, setDraftStatus] = useState<{ s: "idle" | "pending" | "saving" | "saved" | "error"; text?: string }>(
    props.draft ? { s: "saved", text: props.draft.updated } : { s: "idle" },
  );
  const [draftConflict, setDraftConflict] = useState<string | null>(null);
  const conflictRef = useRef(false);
  const [publishing, setPublishing] = useState<PublishState | null | false>(
    props.published?.state === "running" ? props.published : false,
  );
  const autoTimer = useRef(0);
  const draftRun = useRef<Promise<DraftRef | null>>(Promise.resolve(null));
  const bkey = useRef(backupKey(props.draft, props.initial));

  const saveDraft = useCallback((): Promise<DraftRef | null> => {
    if (!props.publish) return Promise.resolve(null);
    window.clearTimeout(autoTimer.current);
    const run = draftRun.current
      .catch(() => null)
      .then(async () => {
        // an edit the server is still working out goes in first
        await queue.current.catch(() => undefined);
        const m = modelRef.current;
        const text = JSON.stringify(m);
        if (text === savedText.current) return draftRef.current;
        if (conflictRef.current) throw new ApiError("черновик не сохраняется: его сохранили в другом месте", 409);
        const d = draftRef.current;
        setDraftStatus({ s: "saving" });
        const base = d?.base || info?.commit || "";
        const r = await api.saveDraft({ uuid: d?.uuid, rev: d?.rev, base, model: m });
        if (r.status === 200 && r.data.uuid) {
          const ref: DraftRef = { uuid: r.data.uuid, rev: Number(r.data.rev), base, updated: r.data.updated };
          draftRef.current = ref;
          savedText.current = text;
          const now = JSON.stringify(modelRef.current) === text;
          if (now) dropBackup(bkey.current);
          if (!d) {
            dropBackup(bkey.current);
            bkey.current = backupKey(ref, m);
            props.onDraft?.(ref);
          }
          setDraftStatus({ s: now ? "saved" : "pending", text: r.data.updated });
          if (!now) autoTimer.current = window.setTimeout(() => saveDraft().catch(() => undefined), AUTOSAVE_MS);
          return ref;
        }
        const why = r.data.error || `ответ ${r.status}`;
        if (r.status === 409) {
          conflictRef.current = true;
          setDraftConflict(why);
          setDraftStatus({ s: "error", text: why });
          throw new ApiError(why, 409);
        }
        setDraftStatus({ s: "error", text: why });
        autoTimer.current = window.setTimeout(() => saveDraft().catch(() => undefined), RETRY_MS);
        throw new ApiError(why, r.status);
      });
    draftRun.current = run;
    return run;
  }, [props.publish, info]);

  // every change: a copy in the browser at once, the draft after a quiet moment
  useEffect(() => {
    if (!props.publish || readOnly) return;
    const text = JSON.stringify(model);
    if (text === savedText.current) return;
    writeBackup(bkey.current, { model, rev: draftRef.current?.rev ?? 0, at: Date.now() });
    if (conflictRef.current) return;
    setDraftStatus({ s: "pending" });
    window.clearTimeout(autoTimer.current);
    autoTimer.current = window.setTimeout(() => saveDraft().catch(() => undefined), AUTOSAVE_MS);
  }, [model, saveDraft]);
  useEffect(() => () => window.clearTimeout(autoTimer.current), []);

  // a page opened again takes back what the browser kept and the draft had not
  useEffect(() => {
    if (!props.publish || readOnly) return;
    const b = readBackup(bkey.current);
    if (!b || !b.model || (b.rev ?? 0) !== (props.draft?.rev ?? 0)) return;
    if (JSON.stringify(b.model) === savedText.current) return;
    if (b.model.id !== props.initial.id) return;
    undo.current.push(modelRef.current);
    setModel({ ...b.model, etag: props.initial.etag, state: props.initial.state });
    setHist((h) => h + 1);
    toast("info", "Вернул правки, которые не успели уйти в черновик: они сохраняются сейчас.", 8000);
  }, []);

  const draftLabel = (() => {
    switch (draftStatus.s) {
      case "idle":
        return "правок нет";
      case "pending":
        return "черновик: есть несохранённое";
      case "saving":
        return "сохраняю черновик…";
      case "saved":
        return `черновик сохранён${draftStatus.text ? ` ${clock(draftStatus.text)}` : ""}`;
      default:
        return "черновик не сохранён";
    }
  })();

  const published = (res: { id?: number | null }) => {
    dropBackup(bkey.current);
    setPublishing(false);
    getLocations(true);
    toast("ok", res.id ? `Опубликовано: место #${res.id}` : "Опубликовано", 9000);
    props.onBack();
  };

  const back = async () => {
    if (savingRef.current) {
      toast("info", "Идёт сохранение: дождитесь ответа.");
      return;
    }
    if (props.publish) {
      if (!readOnly && JSON.stringify(modelRef.current) !== savedText.current) {
        try {
          await saveDraft();
        } catch (e) {
          const go = await ask({
            title: "Уйти без черновика?",
            text: `Последние правки не сохранились в черновик (${errText(e)}). В этом браузере их копия останется.`,
            ok: "Уйти",
            cancel: "Остаться",
            danger: true,
          });
          if (!go) return;
        }
      }
      props.onBack();
      return;
    }
    if (dirty && !readOnly) {
      const go = await ask({
        title: "Уйти без сохранения?",
        text: "Правки этой локации не сохранены и пропадут.",
        ok: "Уйти",
        cancel: "Остаться",
        danger: true,
      });
      if (!go) return;
    }
    props.onBack();
  };

  useEffect(() => {
    const f = (e: BeforeUnloadEvent) => {
      if (props.publish ? draftStatus.s === "pending" || draftStatus.s === "saving" : dirty && !readOnly) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", f);
    return () => window.removeEventListener("beforeunload", f);
  }, [dirty, readOnly, props.publish, draftStatus]);

  // --- what a cell holds ----------------------------------------------------------
  const lookup = useMemo(() => {
    const walls = new Map<string, string>();
    for (const w of model.walls) walls.set(key(w[0], w[1]), w[2]);
    const exits = new Map<string, string>();
    for (const e of model.exits) exits.set(key(e[0], e[1]), e[2]);
    const entries = new Set(model.entries.map((c) => key(c[0], c[1])));
    const wars = new Set(model.war_entries.map((c) => key(c[0], c[1])));
    const inh = new Map<string, number>();
    model.inhabitants.forEach((r, i) => inh.set(key(r.cell[0], r.cell[1]), i));
    return { walls, exits, entries, wars, inh };
  }, [model]);

  // --- pointer, by tool -----------------------------------------------------------
  const applyStroke = (s: Stroke, cells: Cell[]) => {
    const m = s.draft;
    const W = m.width;
    const H = m.height;
    // each cell once: a stroke's samples and a brush's discs overlap
    const fresh: Cell[] = [];
    for (const c of cells) {
      const k = key(c[0], c[1]);
      if (!inGrid(c, W, H) || s.cells.has(k)) continue;
      s.cells.set(k, c);
      fresh.push(c);
    }
    if (!fresh.length) return;
    const ks = new Set(fresh.map((c) => key(c[0], c[1])));
    if (tool === "walls") {
      if (s.erase) m.walls = m.walls.filter((w) => !ks.has(key(w[0], w[1])));
      else {
        m.walls = m.walls.map((w) => (ks.has(key(w[0], w[1])) ? ([w[0], w[1], wallCode] as [number, number, string]) : w));
        const have = new Set(m.walls.map((w) => key(w[0], w[1])));
        for (const c of fresh) {
          const k = key(c[0], c[1]);
          if (have.has(k)) continue;
          have.add(k);
          m.walls.push([c[0], c[1], wallCode]);
        }
      }
    } else if (tool === "entries" || tool === "wars") {
      const field = tool === "entries" ? "entries" : "war_entries";
      if (s.erase) m[field] = m[field].filter((c) => !ks.has(key(c[0], c[1])));
      else {
        const have = new Set(m[field].map((c) => key(c[0], c[1])));
        m[field] = [...m[field], ...fresh.filter((c) => !have.has(key(c[0], c[1])))];
      }
    } else if (tool === "exits" && s.erase) {
      m.exits = m.exits.filter((e) => !ks.has(key(e[0], e[1])));
    }
    canvas.current?.setModel(m);
  };

  const startStroke = (p: PointerInfo, erase: boolean) => {
    const before = modelRef.current;
    const draft: Model = { ...before, walls: before.walls.slice(), entries: before.entries.slice(), war_entries: before.war_entries.slice(), exits: before.exits.slice() };
    stroke.current = { before, draft, start: p.cell, last: p.cell, erase, cells: new Map() };
  };

  const line = (a: Cell, b: Cell): Cell[] => {
    // the cells between two pointer samples, so a fast stroke has no gaps
    const [ax, ay] = cellPx(a[0], a[1]);
    const [bx, by] = cellPx(b[0], b[1]);
    const n = Math.max(1, Math.ceil(Math.hypot(bx - ax, by - ay) / 10));
    const out: Cell[] = [];
    for (let i = 0; i <= n; i++) out.push(pxCell(ax + ((bx - ax) * i) / n, ay + ((by - ay) * i) / n));
    return out;
  };

  const brushCells = (c: Cell) => (tool === "walls" ? disc(c, brush) : [c]);

  const flood = (start: Cell): Cell[] | null => {
    const m = modelRef.current;
    if (lookup.walls.has(key(start[0], start[1]))) return null;
    const seen = new Set<string>([key(start[0], start[1])]);
    const out: Cell[] = [start];
    for (let i = 0; i < out.length; i++) {
      for (const n of neighbours(out[i][0], out[i][1])) {
        const k = key(n[0], n[1]);
        if (seen.has(k) || !inGrid(n, m.width, m.height) || lookup.walls.has(k)) continue;
        seen.add(k);
        out.push(n);
      }
    }
    return out;
  };

  const ghostFor = (it: PaletteItem, c: Cell) => {
    if (!it.picture) return null;
    const [cx, cy] = cellPx(c[0], c[1]);
    const d = it.default || { dx: -Math.round((it.w || 0) / 2), dy: -(it.h || 0) + 5 };
    const ext = it.type === "ext";
    return { url: it.picture, x: cx + d.dx + (ext ? it.ox || 0 : 0), y: cy + d.dy + (ext ? it.oy || 0 : 0) };
  };

  pointer.current = (p: PointerInfo) => {
    const m = modelRef.current;
    const inside = inGrid(p.cell, m.width, m.height);
    if (readOnly) {
      if (p.kind === "down" && tool === "objects") setSelSprite(canvas.current?.hitSprite(p.px) || null);
      return;
    }
    switch (tool) {
      case "walls": {
        if (wallMode === "fill") {
          if (p.kind !== "down" || !inside) return;
          const region = flood(p.cell);
          if (!region) {
            toast("info", "Заливка заполняет пустые клетки до стен. Стереть стены — ластиком или прямоугольником с Shift.");
            return;
          }
          const apply = () => patch((mm) => ({ ...mm, walls: [...mm.walls, ...region.map((c) => [c[0], c[1], wallCode] as [number, number, string])] }));
          if (region.length > 1500) {
            ask({
              title: "Залить большую область?",
              text: `Заливка поставит ${region.length} клеток стен: область не замкнута стенами или очень велика.`,
              ok: "Залить",
            }).then((y) => y && apply());
          } else apply();
          return;
        }
        if (wallMode === "rect") {
          if (p.kind === "down") {
            startStroke(p, p.shift);
            setPreview([p.cell]);
          } else if (p.kind === "move" && stroke.current) {
            stroke.current.last = p.cell;
            setPreview(rectCells(stroke.current.start, p.cell, m.width, m.height));
          } else if (p.kind === "up" && stroke.current) {
            const s = stroke.current;
            stroke.current = null;
            setPreview([]);
            applyStroke(s, rectCells(s.start, p.cell, m.width, m.height));
            if (s.cells.size) commit(s.draft, s.before);
          }
          return;
        }
        // brush and eraser
        if (p.kind === "down") {
          startStroke(p, wallMode === "erase");
          applyStroke(stroke.current!, brushCells(p.cell));
        } else if (p.kind === "move" && stroke.current) {
          const cells = line(stroke.current.last, p.cell).flatMap(brushCells);
          stroke.current.last = p.cell;
          applyStroke(stroke.current, cells);
        } else if (p.kind === "up" && stroke.current) {
          const s = stroke.current;
          stroke.current = null;
          if (s.cells.size) commit(s.draft, s.before);
          else canvas.current?.setModel(modelRef.current);
        }
        return;
      }
      case "entries":
      case "wars": {
        const set = tool === "entries" ? lookup.entries : lookup.wars;
        if (p.kind === "down") {
          if (!inside) return;
          startStroke(p, set.has(key(p.cell[0], p.cell[1])));
          applyStroke(stroke.current!, [p.cell]);
        } else if (p.kind === "move" && stroke.current) {
          const cells = line(stroke.current.last, p.cell);
          stroke.current.last = p.cell;
          applyStroke(stroke.current, cells);
        } else if (p.kind === "up" && stroke.current) {
          const s = stroke.current;
          stroke.current = null;
          if (s.cells.size) commit(s.draft, s.before);
        }
        return;
      }
      case "exits": {
        if (exitErase) {
          if (p.kind === "down") {
            startStroke(p, true);
            applyStroke(stroke.current!, [p.cell]);
          } else if (p.kind === "move" && stroke.current) {
            const cells = line(stroke.current.last, p.cell);
            stroke.current.last = p.cell;
            applyStroke(stroke.current, cells);
          } else if (p.kind === "up" && stroke.current) {
            const s = stroke.current;
            stroke.current = null;
            if (s.cells.size) commit(s.draft, s.before);
          }
          return;
        }
        // painting: the cells are collected, the server gives them their side
        if (p.kind === "down") {
          if (!inside) return;
          stroke.current = { before: m, draft: m, start: p.cell, last: p.cell, erase: false, cells: new Map([[key(p.cell[0], p.cell[1]), p.cell]]) };
          setPreview([p.cell]);
        } else if (p.kind === "move" && stroke.current) {
          for (const c of line(stroke.current.last, p.cell)) if (inGrid(c, m.width, m.height)) stroke.current.cells.set(key(c[0], c[1]), c);
          stroke.current.last = p.cell;
          setPreview([...stroke.current.cells.values()]);
        } else if (p.kind === "up" && stroke.current) {
          const cells = [...stroke.current.cells.values()];
          stroke.current = null;
          setPreview([]);
          serverEdit({ op: "exits", cells, side: exitSide });
        }
        return;
      }
      case "objects": {
        if (p.kind === "down") {
          if (armed) {
            if (!inside) return;
            serverEdit({ op: "place", kind: armed.origin === "object" ? "object" : armed.type, id: armed.name, cell: p.cell, stamp }).then((r) => {
              if (r && r.sprite) setSelSprite(r.sprite);
            });
            return;
          }
          const hit = canvas.current?.hitSprite(p.px) || null;
          setSelSprite(hit);
          setSelInh(null);
          drag.current = hit ? { kind: "sprite", id: hit, start: p.px, moved: false } : null;
        } else if (p.kind === "move" && drag.current && drag.current.kind === "sprite") {
          const d = drag.current;
          const dx = p.px[0] - d.start[0];
          const dy = p.px[1] - d.start[1];
          if (!d.moved && Math.abs(dx) + Math.abs(dy) < 6) return;
          d.moved = true;
          canvas.current?.setDrag({ sprite: d.id as [number, number], dx, dy });
        } else if (p.kind === "up" && drag.current) {
          const d = drag.current;
          drag.current = null;
          canvas.current?.setDrag(null);
          if (!d.moved || d.kind !== "sprite") return;
          const [si, ai] = d.id as [number, number];
          const sp = m.sprites[si];
          if (!sp) return;
          const [ax, ay] = sp.anchors[ai];
          const [cx, cy] = cellPx(ax, ay);
          const to = pxCell(cx + p.px[0] - d.start[0], cy + p.px[1] - d.start[1]);
          if (to[0] === ax && to[1] === ay) return;
          if (!inGrid(to, m.width, m.height)) {
            toast("info", "Клетка за краем локации");
            return;
          }
          serverEdit({ op: "move", sprite: si, anchor: ai, cell: to, stamp });
        }
        return;
      }
      case "inhabitants": {
        if (p.kind === "down") {
          if (!inside) return;
          const at = lookup.inh.get(key(p.cell[0], p.cell[1]));
          if (at !== undefined) {
            setSelInh(at);
            setSelSprite(null);
            drag.current = { kind: "inh", id: at, start: p.px, moved: false };
            return;
          }
          if (armedMob) {
            const t = armedMob.type;
            patch((mm) => ({ ...mm, inhabitants: [...mm.inhabitants, { type: t, cell: p.cell, why: "" }] }));
            setSelInh(modelRef.current.inhabitants.length - 1);
          } else setSelInh(null);
        } else if (p.kind === "move" && drag.current && drag.current.kind === "inh") {
          const d = drag.current;
          if (!d.moved && Math.abs(p.px[0] - d.start[0]) + Math.abs(p.px[1] - d.start[1]) < 6) return;
          d.moved = true;
          setPreview([p.cell]);
        } else if (p.kind === "up" && drag.current) {
          const d = drag.current;
          drag.current = null;
          setPreview([]);
          if (!d.moved || d.kind !== "inh" || !inside) return;
          const i = d.id as number;
          if (lookup.inh.has(key(p.cell[0], p.cell[1]))) {
            toast("info", "На этой клетке уже стоит житель");
            return;
          }
          patch((mm) => ({ ...mm, inhabitants: mm.inhabitants.map((r, j) => (j === i ? { ...r, cell: p.cell } : r)) }));
        }
        return;
      }
      default:
        return;
    }
  };

  hovered.current = (c) => {
    setHover(c);
    if (tool === "objects" && armed && c && !readOnly) canvas.current?.setGhost(ghostFor(armed, c));
    else canvas.current?.setGhost(null);
  };
  useEffect(() => {
    if (!armed) canvas.current?.setGhost(null);
  }, [armed]);

  // --- keys -------------------------------------------------------------------------
  const deleteSelected = useCallback(() => {
    if (selSprite) {
      const [si, ai] = selSprite;
      setSelSprite(null);
      serverEdit({ op: "delete", sprite: si, anchor: ai, stamp });
    } else if (selInh !== null) {
      const i = selInh;
      setSelInh(null);
      patch((mm) => ({ ...mm, inhabitants: mm.inhabitants.filter((_, j) => j !== i) }));
    }
  }, [selSprite, selInh, stamp, serverEdit, patch]);

  const nudge = useCallback(
    (ddx: number, ddy: number) => {
      if (!selSprite) return;
      const [si, ai] = selSprite;
      const sp = modelRef.current.sprites[si];
      if (!sp) return;
      serverEdit({ op: "nudge", sprite: si, anchor: ai, dx: Number(sp.dx) + ddx, dy: Number(sp.dy) + ddy }).then((r) => {
        if (r && r.sprite) setSelSprite(r.sprite);
      });
    },
    [selSprite, serverEdit],
  );

  useEffect(() => {
    const k = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT")) return;
      if (document.querySelector(".overlay")) return;
      const mod = e.ctrlKey || e.metaKey;
      if (savingRef.current) {
        // nothing is edited while a save runs (the keys included)
        if (mod || e.key === "Delete" || e.key === "Backspace") e.preventDefault();
        return;
      }
      if (mod && e.code === "KeyZ") {
        e.preventDefault();
        if (e.shiftKey) doRedo();
        else doUndo();
      } else if (mod && e.code === "KeyY") {
        e.preventDefault();
        doRedo();
      } else if (mod && e.code === "KeyS") {
        e.preventDefault();
        if (props.publish) saveDraft().catch(() => undefined);
        else save();
      } else if (e.key === "Delete" || e.key === "Backspace") {
        if (selSprite || selInh !== null) {
          e.preventDefault();
          deleteSelected();
        }
      } else if (e.altKey && e.key.startsWith("Arrow") && selSprite) {
        e.preventDefault();
        const step = e.shiftKey ? 10 : 1;
        const d = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] }[e.key] as [number, number];
        nudge(d[0], d[1]);
      } else if (e.key === "Escape") {
        setArmed(null);
        setArmedMob(null);
        setSelSprite(null);
        setSelInh(null);
      } else if (!mod && !e.altKey && /^Digit[1-9]$/.test(e.code)) {
        setTool(TOOLS[Number(e.code.slice(5)) - 1].id);
      } else if (!mod && (e.key === "+" || e.key === "=")) {
        canvas.current?.zoomTo(canvas.current.zoom * 1.25);
      } else if (!mod && e.key === "-") {
        canvas.current?.zoomTo(canvas.current.zoom / 1.25);
      }
    };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  });

  // --- the problems ---------------------------------------------------------------
  const pickProblem = (p: Problem, i: number) => {
    setSelProblem(i);
    if (typeof p.loc === "number" && p.loc !== model.id) {
      const wi = model.walk_ins.findIndex((w) => w.from === p.loc);
      setTool("ways");
      setPicker({ from: p.loc, index: wi >= 0 ? wi : null, focus: p.cells });
      return;
    }
    if (p.what === "map") {
      setTool("map");
      return;
    }
    if (p.what === "inhabitants" && tool !== "inhabitants") setTool("inhabitants");
    if (p.cells.length) {
      if (tool === "map") setTool("objects");
      requestAnimationFrame(() => canvas.current?.centerOn(p.cells[0], Math.max(canvas.current.zoom, 0.8)));
      setFlash(p.cells);
    }
  };
  useEffect(() => {
    if (!flash.length) return;
    const t = window.setTimeout(() => setFlash([]), 6000);
    return () => window.clearTimeout(t);
  }, [flash]);

  // --- the status line ---------------------------------------------------------------
  const hoverText = (() => {
    if (!hover) return "";
    if (!inGrid(hover, model.width, model.height)) return `${hover[0]}:${hover[1]} · за краем`;
    const k = key(hover[0], hover[1]);
    const parts = [`${hover[0]}:${hover[1]}`];
    const w = lookup.walls.get(k);
    if (w) parts.push(`стена ${w}`);
    const e = lookup.exits.get(k);
    if (e) parts.push(`выход: ${SIDE_RU[e] || e}`);
    if (lookup.entries.has(k)) parts.push("вход");
    if (lookup.wars.has(k)) parts.push("военный вход");
    const i = lookup.inh.get(k);
    if (i !== undefined) parts.push(`житель: ${mobName(Number(model.inhabitants[i].type))}`);
    return parts.join(" · ");
  })();

  const errors = problems.filter((p) => p.level === "error").length;
  const title = model.attrs.title || "без названия";

  return (
    <div className="screen editor">
      <header className="topbar">
        <button className="ghost" onClick={back}>
          ← Локации
        </button>
        <span className="loc-title">
          <b>{typeof model.id === "string" ? "новое место" : `#${model.id}`}</b> {title}
        </span>
        <span className={`tag state-${model.state}`}>{(props.publish ? STATE_RU_PUBLISH : STATE_RU)[model.state]}</span>
        {!props.publish && dirty && !readOnly && model.state !== "new" && <span className="tag dirty">есть несохранённые правки</span>}
        {props.publish && !readOnly && (
          <span className={`tag draft-${draftStatus.s}`} title={draftStatus.s === "error" ? draftStatus.text : undefined}>
            {draftLabel}
          </span>
        )}
        <span className="grow" />
        <button onClick={doUndo} disabled={saving || !undo.current.length} title="Ctrl+Z">
          ↶ Отменить
        </button>
        <button onClick={doRedo} disabled={saving || !redo.current.length} title="Ctrl+Y">
          ↷ Вернуть
        </button>
        {readOnly ? (
          !model.closed && (
            <button className="primary" onClick={() => setCopying(true)}>
              Сделать копию
            </button>
          )
        ) : (
          <>
            <span className={`status ${errors ? "bad" : "good"}`}>{checking ? "проверка…" : errors ? `ошибок: ${errors}` : "без ошибок"}</span>
            <button onClick={runFullCheck} disabled={checking || saving}>
              Проверить
            </button>
            {props.publish ? (
              <button
                className="primary"
                onClick={() => setPublishing(null)}
                disabled={draftStatus.s === "idle" && !draftRef.current}
                title={
                  draftStatus.s === "idle" && !draftRef.current
                    ? "Правок нет: публиковать нечего"
                    : "Черновик — в main (Ctrl+S сохраняет черновик сейчас)"
                }
              >
                Опубликовать…
              </button>
            ) : (
              <button className="primary" onClick={() => save()} disabled={saving} title="Ctrl+S">
                {saving ? `Сохраняю… ${saveSec} с` : "Сохранить"}
              </button>
            )}
          </>
        )}
      </header>
      {props.published?.state === "done" && (
        <div className="banner">
          Этот черновик уже опубликован
          {props.published.result?.commit ? ` (коммит ${props.published.result.commit.slice(0, 10)})` : ""}: дальнейшие правки — в
          локации из списка.
        </div>
      )}
      {dropped.length > 0 && (
        <div className="banner">
          Из существ копии сюда не встали ({dropped.length}):{" "}
          {dropped.map((d) => `${d.name} на ${d.cell.join(":")} — ${d.why}`).join("; ")}.{" "}
          <button className="ghost small" onClick={() => setDropped([])}>
            Понятно
          </button>
        </div>
      )}
      <div className="editor-body">
        {saving && (
          <div className="saving-veil" role="status" aria-live="polite">
            <div className="saving-box">
              <b>
                <Spinner /> Сохраняю… {saveSec} с
              </b>
              <p>
                Сервер проверяет место так, как его прочтёт игра. Если менялись название, стороны выходов, библиотека, фон или
                клетка на карте, он ещё пересчитывает места на карте: это занимает около минуты. Остальное сохраняется за
                несколько секунд.
              </p>
              <p className="muted small">Пока идёт сохранение, править нельзя: правки, сделанные сейчас, пропали бы.</p>
            </div>
          </div>
        )}
        <nav className="toolbar" aria-label="Инструменты">
          {TOOLS.map((t, i) => (
            <button key={t.id} className={tool === t.id ? "on" : ""} onClick={() => setTool(t.id)} title={`${t.label} (${i + 1})`}>
              <span className="le-ico">{t.icon}</span>
              <span className="lbl">{t.label}</span>
            </button>
          ))}
        </nav>
        <main className="stage">
          <div className="stage-loc" style={{ display: tool === "map" ? "none" : "flex" }}>
            <div className="canvas-tools">
              <button onClick={() => canvas.current?.zoomTo(canvas.current.zoom / 1.25)} aria-label="Мельче" title="Мельче (−)">
                −
              </button>
              <span className="zoom mono">{Math.round(zoom * 100)}%</span>
              <button onClick={() => canvas.current?.zoomTo(canvas.current.zoom * 1.25)} aria-label="Крупнее" title="Крупнее (+)">
                +
              </button>
              <button onClick={() => canvas.current?.fit()}>Вписать</button>
              <span className="sep" />
              {ALL_LAYERS.map((l) => (
                <label key={l} className={`le-chip${layers.has(l) ? " on" : ""}`}>
                  <input
                    type="checkbox"
                    checked={layers.has(l)}
                    onChange={(e) => {
                      const n = new Set(layers);
                      if (e.target.checked) n.add(l);
                      else n.delete(l);
                      setLayers(n);
                    }}
                  />
                  {LAYER_RU[l]}
                </label>
              ))}
            </div>
            <div className="canvas-host" ref={host} />
            <div className="statusbar">
              <span className="mono">{hoverText || "наведите мышь на клетку"}</span>
              <span className="grow" />
              {bgState === "wait" && <span className="muted small">рисую картинку…</span>}
              {bgState !== "wait" && bgState !== "ok" && <span className="err-text small">картинка: {bgState}</span>}
              <span className="muted small">
                колёсико — масштаб ({Math.round(ZOOM_MIN * 100)}–{Math.round(ZOOM_MAX * 100)}%), правая кнопка или пробел — сдвиг
              </span>
            </div>
          </div>
          {tool === "map" && (
            <MapView
              model={model}
              onPick={(cell) => {
                if (readOnly) return;
                const mp = model.map;
                patch((mm) => ({ ...mm, map: { cell, label: mp?.label || mm.attrs.title || "", square: mp?.square ?? null, why: mp?.why || "" } }));
              }}
            />
          )}
        </main>
        <aside className="le-side">
          <div className="side-tool">
            <h3>{TOOLS.find((t) => t.id === tool)?.label}</h3>
            {tool === "props" && (
              <PropsPanel
                info={info}
                model={model}
                readOnly={readOnly}
                onAttr={(k, v) => patch((mm) => ({ ...mm, attrs: { ...mm.attrs, [k]: v } }), `attr:${k}`)}
                onWhy={(v) =>
                  patch((mm) => ({ ...mm, index: { ...(mm.index || { title: mm.attrs.title, from: mm.from, author: "owner", created: "" }), why: v } }), "why")
                }
              />
            )}
            {tool === "objects" && (
              <ObjectsPanel
                model={model}
                palette={palette}
                paletteErr={paletteErr}
                armed={armed}
                onArm={(it) => {
                  setArmed(it);
                  if (it) setSelSprite(null);
                }}
                stamp={stamp}
                onStamp={setStamp}
                selected={selSprite}
                onNudge={nudge}
                onDelete={deleteSelected}
                readOnly={readOnly}
              />
            )}
            {tool === "walls" && (
              <WallsPanel info={info} model={model} mode={wallMode} onMode={setWallMode} code={wallCode} onCode={setWallCode} size={brush} onSize={setBrush} />
            )}
            {tool === "exits" && (
              <ExitsPanel
                model={model}
                side={exitSide}
                onSide={setExitSide}
                erase={exitErase}
                onErase={setExitErase}
                onRing={() => serverEdit({ op: "ring" })}
                readOnly={readOnly}
              />
            )}
            {tool === "entries" && <EntriesPanel model={model} war={false} />}
            {tool === "wars" && <EntriesPanel model={model} war />}
            {tool === "inhabitants" && (
              <InhabitantsPanel
                model={model}
                armed={armedMob}
                onArm={setArmedMob}
                selected={selInh}
                onSelect={(i) => {
                  setSelInh(i);
                  if (i !== null && model.inhabitants[i]) canvas.current?.centerOn(model.inhabitants[i].cell, Math.max(zoom, 0.8));
                }}
                onWhy={(i, why) => patch((mm) => ({ ...mm, inhabitants: mm.inhabitants.map((r, j) => (j === i ? { ...r, why } : r)) }), `inh-why:${i}`)}
                onDelete={(i) => {
                  setSelInh(null);
                  patch((mm) => ({ ...mm, inhabitants: mm.inhabitants.filter((_, j) => j !== i) }));
                }}
                readOnly={readOnly}
              />
            )}
            {tool === "ways" && (
              <WaysPanel
                model={model}
                readOnly={readOnly}
                onDoor={(s, d) =>
                  patch(
                    (mm) => {
                      const doors = { ...mm.doors };
                      if (d) doors[s] = d;
                      else delete doors[s];
                      return { ...mm, doors };
                    },
                    d ? `door:${s}` : undefined,
                  )
                }
                onWalkIn={(i, pt) =>
                  patch(
                    (mm) => ({
                      ...mm,
                      walk_ins: pt ? mm.walk_ins.map((w, j) => (j === i ? { ...w, ...pt } : w)) : mm.walk_ins.filter((_, j) => j !== i),
                    }),
                    pt ? `walk:${i}` : undefined,
                  )
                }
                onPickWalkIn={(from, index) => setPicker({ from, index })}
                onNoMap={(v) => patch((mm) => ({ ...mm, no_map: v }), v ? "nomap" : undefined)}
              />
            )}
            {tool === "map" && (
              <MapPanel model={model} colours={info?.colours || []} readOnly={readOnly} onChange={(mp) => patch((mm) => ({ ...mm, map: mp }), mp ? "map" : undefined)} />
            )}
          </div>
          <Problems problems={problems} checking={checking} full={fullCheck} seconds={seconds} selected={selProblem} onPick={pickProblem} />
        </aside>
      </div>

      {picker && (
        <WalkInPicker
          from={picker.from}
          cells={picker.index !== null ? model.walk_ins[picker.index]?.cells || [] : []}
          focus={picker.focus}
          target={`${typeof model.id === "string" ? "новое место" : `#${model.id}`} «${title}»`}
          onClose={() => setPicker(null)}
          onDone={(cells) => {
            const at = picker.index;
            const from = picker.from;
            setPicker(null);
            if (readOnly) return;
            patch((mm) => ({
              ...mm,
              walk_ins: at !== null && mm.walk_ins[at] ? mm.walk_ins.map((w, j) => (j === at ? { ...w, cells } : w)) : [...mm.walk_ins, { from, cells, why: "" }],
            }));
          }}
        />
      )}
      {conflict && (
        <Modal
          title="Не сохранено: на диске другое"
          onClose={() => setConflict(null)}
          footer={
            <>
              <button onClick={() => setConflict(null)}>Закрыть</button>
              {model.state === "new" && conflict.nextId !== undefined && (
                <button
                  className="primary"
                  onClick={() => {
                    const id = conflict.nextId!;
                    setConflict(null);
                    const next = { ...modelRef.current, id };
                    setModel(next);
                    save(next);
                  }}
                >
                  Сохранить под номером {conflict.nextId}
                </button>
              )}
              {model.state === "ours" && props.onReload && (
                <button className="danger" onClick={() => props.onReload!(true)}>
                  Открыть заново с диска
                </button>
              )}
            </>
          }
        >
          <p>{conflict.text}.</p>
          {model.state === "ours" && (
            <p className="muted">
              Кто-то (другая вкладка или сессия) поменял эту локацию или её строки в таблицах. «Открыть заново» покажет то, что на
              диске; ваши правки здесь пропадут.
            </p>
          )}
          {model.state === "new" && conflict.nextId !== undefined && (
            <p className="muted">Номер {model.id} тем временем заняли. Свободный сейчас — {conflict.nextId}.</p>
          )}
        </Modal>
      )}
      {copying && typeof model.id === "number" && (
        <NewFromCopy row={{ id: model.id, title: model.attrs.title }} onClose={() => setCopying(false)} onMade={props.onCopy} />
      )}
      {publishing !== false && (
        <PublishDialog
          uuid={draftRef.current?.uuid || null}
          model={modelRef.current}
          title={title}
          flush={saveDraft}
          watch={publishing}
          onClose={() => setPublishing(false)}
          onDone={published}
          onProblem={(p) => {
            setPublishing(false);
            pickProblem(p, problems.indexOf(p));
          }}
        />
      )}
      {draftConflict && (
        <Modal
          title="Черновик не сохраняется"
          onClose={() => setDraftConflict(null)}
          footer={
            <>
              <button onClick={() => setDraftConflict(null)}>Закрыть</button>
              {props.onReload && draftRef.current && <button onClick={() => props.onReload!(false)}>Открыть черновик заново</button>}
              {props.onReload && model.state === "ours" && (
                <button className="danger" onClick={() => props.onReload!(true)}>
                  Открыть локацию из main
                </button>
              )}
            </>
          }
        >
          <p>{draftConflict}.</p>
          <p className="muted">
            Правки этой страницы остаются в этом браузере, пока вы её не закроете. «Открыть черновик заново» покажет то, что
            сохранено на сервере.
          </p>
        </Modal>
      )}
    </div>
  );
}
