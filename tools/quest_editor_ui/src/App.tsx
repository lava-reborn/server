import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Background,
  Controls,
  MarkerType,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  useNodesState,
  useReactFlow,
  useStore,
  type Connection,
  type Edge,
  type NodeChange,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import "./styles.css";
import { api, ApiError, config, onNotice, type Notice } from "./api";
import type { CommitInfo, Generated, Kind, Layout, Pos, Problem, PublishResp, Rebase, Refs, Row, TextsResp } from "./types";
import { KIND_LABEL } from "./types";
import { count, plural } from "./words";
import { anyOf, autoLayout, excludes, forget, links, needs, placeNear, withList, withNeeds, wouldCycle, type LinkKind } from "./graph";
import { makeLookup, RefsContext, creatureName } from "./refs";
import { token } from "./theme";
import { QuestNode, type QuestNodeT } from "./components/QuestNode";
import { Inspector } from "./components/Inspector";
import { matches, NO_FILTERS, Sidebar, type Filters } from "./components/Sidebar";
import { DiffModal, Problems } from "./components/Problems";
import { PublishDialog } from "./components/Publish";

const nodeTypes = { quest: QuestNode };

// The panel's tokens (theme.ts): a prerequisite in steel, one of several in
// the brand's amber, the other branch of a choice in danger red.
function edgeStyles(): Record<LinkKind, Partial<Edge>> {
  const need = token("--steel");
  const any = token("--brand");
  const excl = token("--danger");
  return {
    need: { style: { stroke: need, strokeWidth: 2 }, markerEnd: { type: MarkerType.ArrowClosed, color: need } },
    any: {
      style: { stroke: any, strokeWidth: 2, strokeDasharray: "7 5" },
      markerEnd: { type: MarkerType.ArrowClosed, color: any },
      label: "или",
    },
    excl: { style: { stroke: excl, strokeWidth: 2, strokeDasharray: "2 5" }, label: "≠" },
  };
}

const KIND_TOKEN: Record<string, string> = { kill_mobs: "--danger", bring_l_obj: "--success", del_obj: "--steel" };

// The minimap by the canvas's width. The panel on a 1366-1536 px screen
// leaves the canvas 520-625 px: a smaller minimap fits there, the check bar
// beside it on one line (styles.css, .canvas.mini-small); a canvas under
// 480 px (the panel at 1280) goes without. The size goes in as the
// minimap's style, which React Flow also scales a drag in it by, so the drag
// keeps pace with the pointer (a CSS scale would not).
const MINIMAP = { full: { width: 200, height: 150 }, small: { width: 120, height: 90 } };
type Mini = keyof typeof MINIMAP | "none";
const miniFor = (width: number): Mini => (width > 640 ? "full" : width >= 480 ? "small" : "none");

interface EdgeMenu {
  id: string;
  kind: LinkKind;
  source: number;
  target: number;
  x: number;
  y: number;
}

interface Toast {
  text: string;
  links?: { href: string; label: string }[];
}

// Whether the rows are the ones last loaded, saved or published: the same
// objects (an undo brings those back), or row by row the same values.
function sameRows(a: Row[], b: Row[] | null): boolean {
  if (a === b) return true;
  if (!b || a.length !== b.length) return false;
  return a.every((r, i) => r === b[i] || JSON.stringify(r) === JSON.stringify(b[i]));
}

function Editor() {
  const flow = useReactFlow();
  const mini = useStore((s) => miniFor(s.width));
  const [rows, setRows] = useState<Row[]>([]);
  const [generated, setGenerated] = useState<Generated[]>([]);
  const [ways, setWays] = useState<ReadonlySet<number>>(new Set());
  const [sha, setSha] = useState("");
  const [layout, setLayout] = useState<Layout>({});
  const [positions, setPositions] = useState<Record<string, Pos>>({});
  const [refs, setRefs] = useState<Refs | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [problems, setProblems] = useState<Problem[]>([]);
  const [texts, setTexts] = useState<TextsResp | null>(null);
  const [filters, setFilters] = useState<Filters>(NO_FILTERS);
  // Unsaved is derived: rows other than the ones last loaded, saved or
  // published (null: none of those is on the page), or a quest moved.
  const [savedRows, setSavedRows] = useState<Row[] | null>(null);
  const [layoutDirty, setLayoutDirty] = useState(false);
  const [past, setPast] = useState<Row[][]>([]);
  const [future, setFuture] = useState<Row[][]>([]);
  const [toast, setToast] = useState<Toast | null>(null);
  const [diff, setDiff] = useState<string | null>(null);
  const [edgeMenu, setEdgeMenu] = useState<EdgeMenu | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  // Until the first table arrives the mode is not known: no editor yet, and
  // no Save or Publish (the admin's page would flash local mode otherwise).
  const [loaded, setLoaded] = useState(false);
  const [checking, setChecking] = useState(false);
  const [checkError, setCheckError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [newMenu, setNewMenu] = useState(false);
  // on a narrow editor the list is a drawer over the canvas (styles.css)
  const [listOpen, setListOpen] = useState(false);
  // publish mode (the admin panel): the commit the page's rows come from,
  // and where to look at it
  const [mode, setMode] = useState<"publish" | "local">("local");
  const [base, setBase] = useState("");
  const [branch, setBranch] = useState("main");
  const [web, setWeb] = useState("");
  const [head, setHead] = useState<CommitInfo | null>(null);
  const [stale, setStale] = useState<string | null>(null);
  const [notice, setNotice] = useState<Notice>(null);
  const [publishing, setPublishing] = useState(false);
  const [pubNote, setPubNote] = useState("");
  const toastTimer = useRef<number | undefined>(undefined);
  const canvasRef = useRef<HTMLDivElement>(null);
  const publishMode = mode === "publish";
  const dirty = useMemo(() => loaded && (layoutDirty || !sameRows(rows, savedRows)), [loaded, layoutDirty, rows, savedRows]);

  useEffect(() => onNotice(setNotice), []);

  const say = useCallback((text: string, links?: Toast["links"], ms = 4000) => {
    setToast({ text, links });
    window.clearTimeout(toastTimer.current);
    toastTimer.current = window.setTimeout(() => setToast(null), ms);
  }, []);

  // --- loading ---------------------------------------------------------------
  const allRows = useMemo(() => [...rows, ...generated.flatMap((g) => g.rows)], [rows, generated]);
  const genCount = useMemo(() => generated.reduce((n, g) => n + g.rows.length, 0), [generated]);
  const sourceOf = useMemo(() => {
    const m = new Map<number, string>();
    for (const g of generated) for (const r of g.rows) m.set(r.type, g.source);
    return m;
  }, [generated]);
  const lookup = useMemo(() => makeLookup(refs, allRows), [refs, allRows]);
  const giverName = useCallback((r: Row) => ((r.give || []).length ? creatureName(lookup, r.give[0]) : "яя"), [lookup]);

  const load = useCallback(async () => {
    try {
      const t = await api.table();
      setRows(t.rows);
      setGenerated(t.generated);
      setWays(new Set(t.ways || []));
      setSha(t.sha);
      setLayout(t.layout || {});
      setPositions((t.layout && t.layout.positions) || {});
      setMode(t.mode === "publish" ? "publish" : "local");
      setBase(t.commit || "");
      setBranch(t.branch || "main");
      setWeb(t.web || "");
      setHead(t.head || null);
      setStale(t.stale || null);
      setSavedRows(t.rows);
      setLayoutDirty(false);
      setPast([]);
      setFuture([]);
      setLoadError(null);
      setLoaded(true);
    } catch (e) {
      setLoadError(e instanceof ApiError && e.status === 401 ? "" : e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    load();
    api.refs().then(setRefs).catch((e) => say("Справочники не загрузились: " + (e instanceof Error ? e.message : e)));
  }, [load, say]);

  // Quests that have no place yet get one: the whole table laid out at once
  // the first time, then only the newcomers.
  useEffect(() => {
    if (!rows.length) return;
    const missing = allRows.filter((r) => !positions[String(r.type)]);
    if (!missing.length) return;
    if (Object.keys(positions).length === 0) {
      const hand = autoLayout(rows, giverName);
      const genOffset = Math.max(0, ...Object.values(hand).map((p) => p.y)) + 600;
      const gen = autoLayout(generated.flatMap((g) => g.rows), giverName);
      const out = { ...hand };
      for (const [k, p] of Object.entries(gen)) out[k] = { x: p.x, y: p.y + genOffset };
      setPositions(out);
    } else {
      const next = { ...positions };
      let i = 0;
      const maxY = Math.max(0, ...Object.values(positions).map((p) => p.y));
      for (const r of missing) next[String(r.type)] = { x: (i++ % 12) * 310, y: maxY + 250 + Math.floor(i / 12) * 170 };
      setPositions(next);
    }
  }, [rows, generated, allRows, positions, giverName]);

  // --- checks and texts --------------------------------------------------------
  useEffect(() => {
    if (!rows.length) return;
    setChecking(true);
    const h = window.setTimeout(() => {
      api
        .check(rows)
        .then((p) => {
          setProblems(p);
          setCheckError(null);
        })
        .catch((e) => {
          // said, not swallowed: the marks on the cards are the last check's
          const why = e instanceof Error ? e.message : String(e);
          setCheckError(why);
          say("Проверка не прошла: " + why);
        })
        .finally(() => setChecking(false));
    }, 450);
    return () => window.clearTimeout(h);
  }, [rows, refs]);

  const selRow = useMemo(() => (selected === null ? null : allRows.find((r) => r.type === selected) || null), [selected, allRows]);

  useEffect(() => {
    if (!selRow) {
      setTexts(null);
      return;
    }
    const h = window.setTimeout(() => {
      api.texts(selRow).then(setTexts).catch(() => setTexts(null));
    }, 300);
    return () => window.clearTimeout(h);
  }, [selRow]);

  const byType = useMemo(() => {
    const e = new Map<number, number>();
    const w = new Map<number, number>();
    for (const p of problems) {
      if (p.type === null) continue;
      const m = p.level === "error" ? e : w;
      m.set(p.type, (m.get(p.type) || 0) + 1);
    }
    return { e, w };
  }, [problems]);
  const errorsOf = useCallback((t: number) => byType.e.get(t) || 0, [byType]);
  const warnsOf = useCallback((t: number) => byType.w.get(t) || 0, [byType]);
  const hasProblem = useCallback((t: number) => !!(byType.e.get(t) || byType.w.get(t)), [byType]);
  const errorCount = problems.filter((p) => p.level === "error").length;

  // --- editing ------------------------------------------------------------------
  const commit = useCallback(
    (next: Row[]) => {
      setPast((p) => [...p.slice(-99), rows]);
      setFuture([]);
      setRows(next);
    },
    [rows],
  );

  const updateRow = useCallback(
    (row: Row) => {
      if (sourceOf.has(row.type)) return;
      commit(rows.map((r) => (r.type === row.type ? row : r)));
    },
    [rows, commit, sourceOf],
  );

  const undo = useCallback(() => {
    if (!past.length) return;
    setFuture((f) => [rows, ...f]);
    setRows(past[past.length - 1]);
    setPast((p) => p.slice(0, -1));
  }, [past, rows]);

  const redo = useCallback(() => {
    if (!future.length) return;
    setPast((p) => [...p, rows]);
    setRows(future[0]);
    setFuture((f) => f.slice(1));
  }, [future, rows]);

  const focus = useCallback(
    (t: number) => {
      setSelected(t);
      const p = positions[String(t)];
      if (p) flow.setCenter(p.x + 135, p.y + 66, { zoom: Math.max(flow.getZoom(), 0.8), duration: 400 });
    },
    [positions, flow],
  );

  const addRow = useCallback(
    (row: Row, near: number | null) => {
      // the middle of the canvas, wherever the editor sits on the page
      const box = canvasRef.current?.getBoundingClientRect();
      const mid = box ? { x: box.left + box.width / 2, y: box.top + box.height / 2 } : { x: window.innerWidth / 2, y: window.innerHeight / 2 };
      const vp = flow.screenToFlowPosition(mid);
      const pos = placeNear(positions, near, { x: vp.x - 135, y: vp.y - 66 });
      setPositions((ps) => ({ ...ps, [String(row.type)]: pos }));
      commit([...rows, row]);
      setSelected(row.type);
      flow.setCenter(pos.x + 135, pos.y + 66, { zoom: Math.max(flow.getZoom(), 0.8), duration: 400 });
    },
    [flow, positions, rows, commit],
  );

  const newQuest = useCallback(
    async (kind: Kind) => {
      setNewMenu(false);
      try {
        addRow(await api.newRow(kind, rows), null);
      } catch (e) {
        say(e instanceof Error ? e.message : String(e));
      }
    },
    [rows, addRow, say],
  );

  const followUp = useCallback(async () => {
    if (!selRow) return;
    try {
      const fresh = await api.newRow("del_obj", rows);
      const row = withNeeds({ ...fresh, give: [...(selRow.take || [])], take: [...(selRow.take || [])] }, [selRow.type]);
      addRow(row, selRow.type);
    } catch (e) {
      say(e instanceof Error ? e.message : String(e));
    }
  }, [selRow, rows, addRow, say]);

  const duplicate = useCallback(async () => {
    if (!selRow) return;
    try {
      const fresh = await api.newRow(selRow.kind, rows);
      const copy: Row = { ...JSON.parse(JSON.stringify(selRow)), type: fresh.type, why: fresh.why };
      copy.name = `${selRow.name} (копия)`;
      delete copy.own_texts;
      addRow(copy, selRow.type);
    } catch (e) {
      say(e instanceof Error ? e.message : String(e));
    }
  }, [selRow, rows, addRow, say]);

  const remove = useCallback(() => {
    if (!selRow) return;
    const dependents = rows.filter(
      (r) => needs(r).includes(selRow.type) || anyOf(r).includes(selRow.type) || excludes(r).includes(selRow.type),
    );
    const msg =
      `Удалить квест #${selRow.type} «${selRow.name}»?` +
      (dependents.length
        ? `\n\nОн упомянут в цепочках ${count(dependents.length, "квеста", "квестов", "квестов")} (${dependents.map((d) => "#" + d.type).join(", ")}); оттуда он тоже уйдёт.`
        : "");
    if (!window.confirm(msg)) return;
    commit(forget(rows.filter((r) => r.type !== selRow.type), selRow.type));
    setSelected(null);
  }, [selRow, rows, commit]);

  // --- the graph ---------------------------------------------------------------
  const visible = useMemo(() => {
    const base = filters.generated ? allRows : rows;
    return base.filter((r) => matches(r, filters, lookup, hasProblem, ways));
  }, [rows, allRows, filters, lookup, hasProblem, ways]);

  const [nodes, setNodes, onNodesChangeBase] = useNodesState<QuestNodeT>([]);
  useEffect(() => {
    setNodes(
      visible.map((r) => ({
        id: String(r.type),
        type: "quest" as const,
        position: positions[String(r.type)] || { x: 0, y: 0 },
        selected: r.type === selected,
        draggable: true,
        data: { row: r, source: sourceOf.get(r.type), errors: errorsOf(r.type), warns: warnsOf(r.type) },
      })),
    );
  }, [visible, positions, selected, sourceOf, errorsOf, warnsOf, setNodes]);

  // The first time the quests stand somewhere, show them all.
  const fitted = useRef(false);
  useEffect(() => {
    if (fitted.current || !visible.length) return;
    const placed = visible.map((r) => positions[String(r.type)]).filter(Boolean);
    if (placed.length < visible.length) return;
    fitted.current = true;
    // Readable cards, the top of the graph in the middle of the canvas: the
    // whole table fitted at once is too small to read, and the minimap shows
    // the rest.
    const top = placed.reduce((a, b) => (b.y < a.y || (b.y === a.y && b.x < a.x) ? b : a));
    const zoom = 0.75;
    const w = canvasRef.current ? canvasRef.current.clientWidth : 900;
    window.setTimeout(() => flow.setViewport({ x: w / 2 - (top.x + 135) * zoom, y: 80 - top.y * zoom, zoom }), 60);
  }, [visible, positions, flow]);

  const onNodesChange = useCallback(
    (changes: NodeChange<QuestNodeT>[]) => {
      onNodesChangeBase(changes.filter((c) => c.type === "position" || c.type === "dimensions"));
    },
    [onNodesChangeBase],
  );

  const styles = useMemo(edgeStyles, []);
  const edges = useMemo<Edge[]>(() => {
    const vis = new Set(visible.map((r) => r.type));
    return links(visible)
      .filter((l) => vis.has(l.source) && vis.has(l.target))
      .map((l) => {
        const hot = selected !== null && (l.source === selected || l.target === selected);
        const base = styles[l.kind];
        return {
          id: l.id,
          source: String(l.source),
          target: String(l.target),
          type: "smoothstep",
          ...base,
          style: { ...(base.style || {}), opacity: selected === null || hot ? 1 : 0.35, strokeWidth: hot ? 3 : 2 },
          data: { kind: l.kind },
        } as Edge;
      });
  }, [visible, selected, styles]);

  const onConnect = useCallback(
    (c: Connection) => {
      const s = Number(c.source);
      const t = Number(c.target);
      if (!s || !t || s === t) return;
      if (sourceOf.has(t)) return say("Сгенерированную строку здесь не правят.");
      const target = rows.find((r) => r.type === t);
      if (!target) return;
      if (needs(target).includes(s)) return;
      if (wouldCycle(allRows, s, t)) return say(`Связь #${s} → #${t} замкнула бы цепочку в кольцо.`);
      updateRow(withNeeds(target, [...needs(target), s]));
      say(`#${t} теперь открывается после #${s}`);
    },
    [rows, allRows, updateRow, say, sourceOf],
  );

  const setLink = useCallback(
    (m: EdgeMenu, kind: LinkKind | null) => {
      setEdgeMenu(null);
      const target = rows.find((r) => r.type === m.target);
      const source = rows.find((r) => r.type === m.source);
      if (!target) return;
      // take the old link out
      let t = target;
      let sRow = source;
      if (m.kind === "need") t = withNeeds(t, needs(t).filter((x) => x !== m.source));
      if (m.kind === "any") t = withList(t, "need_any", anyOf(t).filter((x) => x !== m.source));
      if (m.kind === "excl") {
        t = withList(t, "excludes", excludes(t).filter((x) => x !== m.source));
        if (sRow) sRow = withList(sRow, "excludes", excludes(sRow).filter((x) => x !== m.target));
      }
      // and put the new one in
      if (kind === "need") t = withNeeds(t, [...needs(t), m.source]);
      if (kind === "any") t = withList(t, "need_any", [...anyOf(t), m.source]);
      if (kind === "excl") {
        t = withList(t, "excludes", [...excludes(t), m.source]);
        if (sRow) sRow = withList(sRow, "excludes", [...excludes(sRow), m.target]);
      }
      commit(rows.map((r) => (r.type === t.type ? t : sRow && r.type === sRow.type ? sRow : r)));
    },
    [rows, commit],
  );

  const relayout = useCallback(() => {
    const base = filters.generated ? allRows : rows;
    const pos = autoLayout(base, giverName);
    setPositions((p) => ({ ...p, ...pos }));
    setLayoutDirty(true);
    window.setTimeout(() => flow.fitView({ duration: 400 }), 50);
  }, [filters.generated, allRows, rows, giverName, flow]);

  // --- saving (local mode) ------------------------------------------------------
  const save = useCallback(
    async (force = false) => {
      setSaving(true);
      try {
        const lay: Layout = { ...layout, positions };
        const { status, data } = await api.save(rows, lay, sha, force);
        if (status === 200 && data.sha) {
          setSha(data.sha);
          setLayout(lay);
          setSavedRows(rows);
          setLayoutDirty(false);
          say("Сохранено в data/quests.json");
        } else if (status === 409) {
          if (window.confirm("data/quests.json изменился на диске после загрузки (другая сессия, merge, другой редактор).\n\nОК — записать поверх, Отмена — ничего не делать (можно перезагрузить страницу, чтобы взять свежий файл).")) {
            await save(true);
          }
        } else if (status === 422) {
          setProblems((p) => [...(data.problems || []), ...p.filter((x) => x.level === "warn")]);
          say("Не сохранено: в таблице ошибки, сервер на ней не запустится.");
        } else {
          say("Не сохранено: " + (data.ru || data.error || status));
        }
      } finally {
        setSaving(false);
      }
    },
    [rows, layout, positions, sha, say],
  );

  // --- publishing (publish mode) ------------------------------------------------
  const published = useCallback(
    (d: PublishResp) => {
      setPublishing(false);
      if (d.rows) {
        setRows(d.rows);
        setSavedRows(d.rows);
      }
      if (d.layout) {
        setLayout(d.layout);
        setPositions(d.layout.positions || {});
      }
      if (d.commit) setBase(d.commit);
      if (d.head) setHead(d.head);
      setLayoutDirty(false);
      setPast([]);
      setFuture([]);
      // a new quest that went out under another number: the selection follows it
      const moved = d.renumbered || {};
      setSelected((s) => (s !== null && moved[String(s)] ? moved[String(s)] : s));
      if (d.nothing || !d.commit) {
        say(`Публиковать нечего: всё это уже есть в ${branch}`);
        return;
      }
      setPubNote("");
      const out: Toast["links"] = [];
      if (d.url) out.push({ href: d.url, label: "коммит" });
      if (web) out.push({ href: `${web}/actions`, label: "проверки и выкатка" });
      const renamed = Object.entries(moved).map(([a, b]) => `#${a} ушёл как #${b}`);
      say(`Опубликовано ${d.commit.slice(0, 7)}` + (renamed.length ? ` · ${renamed.join(", ")}` : ""), out, 30000);
    },
    [branch, web, say],
  );

  // The preview found nothing to publish: the rows it was given are, as far
  // as the page is concerned, published.
  const nothing = useCallback((r: Row[]) => {
    setSavedRows(r);
    setLayoutDirty(false);
  }, []);

  // «Взять эти квесты из main»: main's commit becomes the page's base, the
  // quests in conflict main's version, the other edits stay.
  const rebased = useCallback(
    (r: Rebase, types: number[]) => {
      setPublishing(false);
      setRows(r.rows);
      setSavedRows(r.changed ? null : r.rows);
      setLayoutDirty(false);
      setLayout(r.layout || {});
      setPositions((r.layout && r.layout.positions) || {});
      setBase(r.commit);
      setHead(r.head);
      setPast([]);
      setFuture([]);
      say(`${types.map((t) => "#" + t).join(", ")} — как в ${branch}, остальные правки на месте`);
    },
    [branch, say],
  );

  const reloadFresh = useCallback(() => {
    setPublishing(false);
    setSelected(null);
    setPubNote("");
    load();
  }, [load]);

  const store = useCallback(() => {
    if (publishMode) setPublishing(true);
    else save();
  }, [publishMode, save]);
  const closePublish = useCallback(() => setPublishing(false), []);

  // keys
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      const typing = tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
        e.preventDefault();
        if (dirty && !saving && !publishing) store();
      } else if (publishing) {
        // the dialog publishes the rows it opened with: nothing behind it
        // changes while it is open (an undo there would be published, then
        // dropped with the history)
        return;
      } else if (!typing && (e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z" && !e.shiftKey) {
        e.preventDefault();
        undo();
      } else if (!typing && (e.ctrlKey || e.metaKey) && (e.key.toLowerCase() === "y" || (e.key.toLowerCase() === "z" && e.shiftKey))) {
        e.preventDefault();
        redo();
      } else if (e.key === "Escape") {
        setEdgeMenu(null);
        setNewMenu(false);
        setListOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [dirty, saving, publishing, store, undo, redo]);

  useEffect(() => {
    const warn = (e: BeforeUnloadEvent) => {
      if (dirty) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  const banners = (
    <>
      {notice === "session" && (
        <div className="qbanner err">
          Сессия панели закончилась. <a href="/admin">Войти заново</a>
        </div>
      )}
      {notice === "restarting" && <div className="qbanner">Редактор обновляется: подтягивает свежий {branch}…</div>}
      {stale && notice !== "restarting" && (
        <div className="qbanner">
          GitHub не ответил ({stale}). Таблица взята с коммита {base.slice(0, 7)}; публикация всё равно сверится со свежим {branch}.
        </div>
      )}
    </>
  );

  if (loadError !== null) {
    return (
      <div className="app">
        {banners}
        {loadError && <div className="fatal">Не загрузилась таблица: {loadError}</div>}
      </div>
    );
  }

  if (!loaded) {
    return (
      <div className="app">
        {banners}
        <div className="qloading">Загружаю квесты…</div>
      </div>
    );
  }

  const commitUrl = web && head ? `${web}/commit/${head.sha}` : "";

  return (
    <RefsContext.Provider value={lookup}>
      <div className="app">
        {banners}
        <div className="qframe">
          <header className="topbar">
            <button className="qlist-toggle" aria-pressed={listOpen} onClick={() => setListOpen(!listOpen)} title="Список квестов и поиск">
              Список
            </button>
            <b className="qbrand">Квесты</b>
            <span className="muted">
              {rows.length} {plural(rows.length, "свой", "своих", "своих")} · {genCount}{" "}
              {plural(genCount, "сгенерированный", "сгенерированных", "сгенерированных")}
            </span>
            {publishMode && head && (
              <a
                className="qcommit"
                href={commitUrl || undefined}
                target="_blank"
                rel="noopener noreferrer"
                title={`${head.subject}\n${head.author}, ${head.date.replace("T", " ").slice(0, 16)}`}
              >
                {branch} @ {head.sha.slice(0, 7)}
              </a>
            )}
            {!refs && <span className="muted"> · справочники грузятся…</span>}
            <span className="grow" />
            <div className="menu-wrap">
              <button className="primary" onClick={() => setNewMenu(!newMenu)}>
                + Новый квест
              </button>
              {newMenu && (
                <div className="menu">
                  {(Object.keys(KIND_LABEL) as Kind[]).map((k) => (
                    <div key={k} className="menu-item" onClick={() => newQuest(k)}>
                      {KIND_LABEL[k]}
                    </div>
                  ))}
                </div>
              )}
            </div>
            <button onClick={relayout} title="Разложить граф заново">Раскладка</button>
            <button onClick={undo} disabled={!past.length} title="Ctrl+Z">↶</button>
            <button onClick={redo} disabled={!future.length} title="Ctrl+Y">↷</button>
            {!publishMode && <button onClick={() => api.diff().then((d) => setDiff(d.diff)).catch((e) => say(String(e)))}>Изменения</button>}
            <span className={"status " + (errorCount || checkError ? "bad" : "good")} title={checkError || undefined}>
              {checking
                ? "проверка…"
                : checkError
                  ? "проверка не прошла"
                  : errorCount
                    ? count(errorCount, "ошибка", "ошибки", "ошибок")
                    : "ошибок нет"}
            </span>
            {publishMode ? (
              <button className="primary" disabled={!dirty || publishing} onClick={store} title={`Ctrl+S: правки уйдут в ${branch}`}>
                Опубликовать
              </button>
            ) : (
              <button className="primary" disabled={!dirty || saving || errorCount > 0} onClick={store} title="Ctrl+S">
                {saving ? "Сохранение…" : dirty ? "Сохранить" : "Сохранено"}
              </button>
            )}
          </header>
          <div className={"main" + (listOpen ? " list-open" : "")}>
            <Sidebar
              rows={rows}
              visible={visible}
              filters={filters}
              setFilters={setFilters}
              selected={selected}
              onSelect={(t) => {
                focus(t);
                setListOpen(false);
              }}
              errorsOf={errorsOf}
              warnsOf={warnsOf}
              generatedCount={genCount}
              ways={ways}
            />
            <div className={"canvas mini-" + mini} ref={canvasRef}>
              <ReactFlow
                nodes={nodes}
                edges={edges}
                nodeTypes={nodeTypes}
                onNodesChange={onNodesChange}
                onNodeDragStop={(_e, n) => {
                  setPositions((p) => ({ ...p, [n.id]: n.position }));
                  setLayoutDirty(true);
                }}
                onNodeClick={(_e, n) => setSelected(Number(n.id))}
                onPaneClick={() => {
                  setSelected(null);
                  setEdgeMenu(null);
                  setNewMenu(false);
                  setListOpen(false);
                }}
                onConnect={onConnect}
                onEdgeClick={(e, edge) => {
                  const kind = (edge.data as { kind: LinkKind }).kind;
                  setEdgeMenu({ id: edge.id, kind, source: Number(edge.source), target: Number(edge.target), x: e.clientX, y: e.clientY });
                }}
                deleteKeyCode={null}
                minZoom={0.05}
                maxZoom={2}
                onlyRenderVisibleElements
                fitView
                colorMode="dark"
                proOptions={{ hideAttribution: true }}
              >
                <Background gap={24} />
                {mini !== "none" && (
                  <MiniMap
                    style={MINIMAP[mini]}
                    pannable
                    zoomable
                    nodeColor={(n) => token(KIND_TOKEN[(n.data as { row: Row }).row.kind] || "--ink-faint")}
                    maskColor={token("--overlay")}
                  />
                )}
                <Controls showInteractive={false} />
              </ReactFlow>
              <Problems problems={problems} onSelect={focus} />
              <div className="legend">
                <span><i className="lg need" /> после</span>
                <span><i className="lg any" /> после одного из</span>
                <span><i className="lg excl" /> исключают друг друга</span>
                <span className="muted">тяните от нижней точки квеста к верхней точке следующего</span>
              </div>
            </div>
            <div className="qright">
              {selRow ? (
                <Inspector
                  key={selRow.type}
                  row={selRow}
                  readOnly={sourceOf.get(selRow.type)}
                  texts={texts}
                  problems={problems.filter((p) => p.type === selRow.type)}
                  onChange={updateRow}
                  onOpen={focus}
                  onFollowUp={followUp}
                  onDuplicate={duplicate}
                  onDelete={remove}
                />
              ) : (
                <div className="qempty">
                  <h3>Квест-редактор</h3>
                  <p>Выберите квест на графе или в списке слева.</p>
                  <ul>
                    <li>Стрелка от квеста к квесту: второй откроется после первого (<code>need_quest</code>).</li>
                    <li>Щелчок по стрелке: сменить её на «после одного из» или «исключают друг друга», либо убрать.</li>
                    <li>Всё, что меняете, сразу проверяется теми же проверками, что сервер делает при запуске.</li>
                    {publishMode ? (
                      <li>
                        «Опубликовать» (Ctrl+S) сверяет правки со свежим <code>{branch}</code> и отправляет их туда одним коммитом;
                        после зелёных тестов CI выкатит их сам, обычно минут через 20.
                      </li>
                    ) : (
                      <li>«Сохранить» пишет <code>data/quests.json</code>. В игру правки попадают коммитом в ветку и слиянием в main.</li>
                    )}
                  </ul>
                </div>
              )}
            </div>
          </div>
        </div>
        {edgeMenu && (
          <div className="edge-menu" style={{ left: edgeMenu.x, top: edgeMenu.y }}>
            <div className="muted small">
              #{edgeMenu.source} → #{edgeMenu.target}
            </div>
            {sourceOf.has(edgeMenu.target) ? (
              <div className="muted small">сгенерированная связь</div>
            ) : (
              <>
                <div className={"menu-item" + (edgeMenu.kind === "need" ? " on" : "")} onClick={() => setLink(edgeMenu, "need")}>после (need_quest)</div>
                <div className={"menu-item" + (edgeMenu.kind === "any" ? " on" : "")} onClick={() => setLink(edgeMenu, "any")}>после одного из (need_any)</div>
                <div className={"menu-item" + (edgeMenu.kind === "excl" ? " on" : "")} onClick={() => setLink(edgeMenu, "excl")}>исключают друг друга</div>
                <div className="menu-item danger" onClick={() => setLink(edgeMenu, null)}>убрать связь</div>
              </>
            )}
          </div>
        )}
        {diff !== null && <DiffModal text={diff} onClose={() => setDiff(null)} />}
        {publishing && (
          <PublishDialog
            rows={rows}
            layout={{ ...layout, positions }}
            base={base}
            branch={branch}
            who={config.who}
            note={pubNote}
            setNote={setPubNote}
            onClose={closePublish}
            onPublished={published}
            onNothing={nothing}
            onRebase={rebased}
            onReload={reloadFresh}
            onOpen={(t) => {
              setPublishing(false);
              focus(t);
            }}
          />
        )}
        {toast && (
          <div className="toast">
            <span>{toast.text}</span>
            {(toast.links || []).map((l) => (
              <a key={l.href} href={l.href} target="_blank" rel="noopener noreferrer">
                {l.label}
              </a>
            ))}
            {toast.links && toast.links.length > 0 && (
              <button className="x" title="Закрыть" onClick={() => setToast(null)}>
                ✕
              </button>
            )}
          </div>
        )}
      </div>
    </RefsContext.Provider>
  );
}

export default function App() {
  return (
    <ReactFlowProvider>
      <Editor />
    </ReactFlowProvider>
  );
}
