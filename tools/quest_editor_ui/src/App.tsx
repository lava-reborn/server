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
  type Connection,
  type Edge,
  type NodeChange,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import "./styles.css";
import { api } from "./api";
import type { Generated, Kind, Layout, Pos, Problem, Refs, Row, TextsResp } from "./types";
import { KIND_LABEL } from "./types";
import { anyOf, autoLayout, excludes, forget, links, needs, placeNear, withList, withNeeds, wouldCycle, type LinkKind } from "./graph";
import { makeLookup, RefsContext, creatureName } from "./refs";
import { QuestNode, type QuestNodeT } from "./components/QuestNode";
import { Inspector } from "./components/Inspector";
import { matches, NO_FILTERS, Sidebar, type Filters } from "./components/Sidebar";
import { DiffModal, Problems } from "./components/Problems";

const nodeTypes = { quest: QuestNode };

const EDGE_STYLE: Record<LinkKind, Partial<Edge>> = {
  need: { style: { stroke: "#6b9cff", strokeWidth: 2 }, markerEnd: { type: MarkerType.ArrowClosed, color: "#6b9cff" } },
  any: {
    style: { stroke: "#e6a23c", strokeWidth: 2, strokeDasharray: "7 5" },
    markerEnd: { type: MarkerType.ArrowClosed, color: "#e6a23c" },
    label: "или",
  },
  excl: { style: { stroke: "#f56c6c", strokeWidth: 2, strokeDasharray: "2 5" }, label: "≠" },
};

const KIND_COLOR: Record<string, string> = { kill_mobs: "#c0504d", bring_l_obj: "#4f9d69", del_obj: "#4f7fc0" };

interface EdgeMenu {
  id: string;
  kind: LinkKind;
  source: number;
  target: number;
  x: number;
  y: number;
}

function Editor() {
  const flow = useReactFlow();
  const [rows, setRows] = useState<Row[]>([]);
  const [generated, setGenerated] = useState<Generated[]>([]);
  const [sha, setSha] = useState("");
  const [layout, setLayout] = useState<Layout>({});
  const [positions, setPositions] = useState<Record<string, Pos>>({});
  const [refs, setRefs] = useState<Refs | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [problems, setProblems] = useState<Problem[]>([]);
  const [texts, setTexts] = useState<TextsResp | null>(null);
  const [filters, setFilters] = useState<Filters>(NO_FILTERS);
  const [dirty, setDirty] = useState(false);
  const [past, setPast] = useState<Row[][]>([]);
  const [future, setFuture] = useState<Row[][]>([]);
  const [toast, setToast] = useState<string | null>(null);
  const [diff, setDiff] = useState<string | null>(null);
  const [edgeMenu, setEdgeMenu] = useState<EdgeMenu | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);
  const [saving, setSaving] = useState(false);
  const [newMenu, setNewMenu] = useState(false);
  const toastTimer = useRef<number | undefined>(undefined);

  const say = useCallback((text: string) => {
    setToast(text);
    window.clearTimeout(toastTimer.current);
    toastTimer.current = window.setTimeout(() => setToast(null), 4000);
  }, []);

  // --- loading ---------------------------------------------------------------
  const allRows = useMemo(() => [...rows, ...generated.flatMap((g) => g.rows)], [rows, generated]);
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
      setSha(t.sha);
      setLayout(t.layout || {});
      setPositions((t.layout && t.layout.positions) || {});
      setDirty(false);
      setPast([]);
      setFuture([]);
    } catch (e) {
      setLoadError(String(e));
    }
  }, []);

  useEffect(() => {
    load();
    api.refs().then(setRefs).catch((e) => say("Справочники не загрузились: " + e));
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
        .then(setProblems)
        .catch(() => undefined)
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
      setDirty(true);
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
    setDirty(true);
  }, [past, rows]);

  const redo = useCallback(() => {
    if (!future.length) return;
    setPast((p) => [...p, rows]);
    setRows(future[0]);
    setFuture((f) => f.slice(1));
    setDirty(true);
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
      const vp = flow.screenToFlowPosition({ x: window.innerWidth / 2, y: window.innerHeight / 2 });
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
        say(String(e));
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
      say(String(e));
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
      say(String(e));
    }
  }, [selRow, rows, addRow, say]);

  const remove = useCallback(() => {
    if (!selRow) return;
    const dependents = rows.filter(
      (r) => needs(r).includes(selRow.type) || anyOf(r).includes(selRow.type) || excludes(r).includes(selRow.type),
    );
    const msg =
      `Удалить квест #${selRow.type} «${selRow.name}»?` +
      (dependents.length ? `\n\nОн упомянут в цепочках ${dependents.length} квестов (${dependents.map((d) => "#" + d.type).join(", ")}); оттуда он тоже уйдёт.` : "");
    if (!window.confirm(msg)) return;
    commit(forget(rows.filter((r) => r.type !== selRow.type), selRow.type));
    setSelected(null);
  }, [selRow, rows, commit]);

  // --- the graph ---------------------------------------------------------------
  const visible = useMemo(() => {
    const base = filters.generated ? allRows : rows;
    return base.filter((r) => matches(r, filters, lookup, hasProblem));
  }, [rows, allRows, filters, lookup, hasProblem]);

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
    const canvas = document.querySelector(".canvas") as HTMLElement | null;
    const w = canvas ? canvas.clientWidth : 900;
    window.setTimeout(() => flow.setViewport({ x: w / 2 - (top.x + 135) * zoom, y: 80 - top.y * zoom, zoom }), 60);
  }, [visible, positions, flow]);

  const onNodesChange = useCallback(
    (changes: NodeChange<QuestNodeT>[]) => {
      onNodesChangeBase(changes.filter((c) => c.type === "position" || c.type === "dimensions"));
    },
    [onNodesChangeBase],
  );

  const edges = useMemo<Edge[]>(() => {
    const vis = new Set(visible.map((r) => r.type));
    return links(visible)
      .filter((l) => vis.has(l.source) && vis.has(l.target))
      .map((l) => {
        const hot = selected !== null && (l.source === selected || l.target === selected);
        const base = EDGE_STYLE[l.kind];
        return {
          id: l.id,
          source: String(l.source),
          target: String(l.target),
          type: "smoothstep",
          ...base,
          style: { ...(base.style || {}), opacity: selected === null || hot ? 1 : 0.35, strokeWidth: hot ? 3 : 2 },
          data: { kind: l.kind },
          labelBgStyle: { fill: "#1d2230" },
          labelStyle: { fill: "#e6e9f0", fontSize: 11 },
        } as Edge;
      });
  }, [visible, selected]);

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
    setDirty(true);
    window.setTimeout(() => flow.fitView({ duration: 400 }), 50);
  }, [filters.generated, allRows, rows, giverName, flow]);

  // --- saving -------------------------------------------------------------------
  const save = useCallback(
    async (force = false) => {
      setSaving(true);
      try {
        const lay: Layout = { ...layout, positions };
        const { status, data } = await api.save(rows, lay, sha, force);
        if (status === 200 && data.sha) {
          setSha(data.sha);
          setLayout(lay);
          setDirty(false);
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

  // keys
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      const typing = tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
        e.preventDefault();
        if (dirty && !saving) save();
      } else if (!typing && (e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z" && !e.shiftKey) {
        e.preventDefault();
        undo();
      } else if (!typing && (e.ctrlKey || e.metaKey) && (e.key.toLowerCase() === "y" || (e.key.toLowerCase() === "z" && e.shiftKey))) {
        e.preventDefault();
        redo();
      } else if (e.key === "Escape") {
        setEdgeMenu(null);
        setNewMenu(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [dirty, saving, save, undo, redo]);

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

  if (loadError) return <div className="fatal">Не загрузилась таблица: {loadError}</div>;

  return (
    <RefsContext.Provider value={lookup}>
      <div className="app">
        <header className="topbar">
          <b className="brand">Квесты LAVA</b>
          <span className="muted">
            {rows.length} своих · {generated.reduce((n, g) => n + g.rows.length, 0)} сгенерированных
          </span>
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
          <button onClick={() => api.diff().then((d) => setDiff(d.diff))}>Изменения</button>
          <span className={"status " + (errorCount ? "bad" : "good")}>
            {checking ? "проверка…" : errorCount ? `${errorCount} ошибок` : "ошибок нет"}
          </span>
          <button className="primary" disabled={!dirty || saving || errorCount > 0} onClick={() => save()} title="Ctrl+S">
            {saving ? "Сохранение…" : dirty ? "Сохранить" : "Сохранено"}
          </button>
        </header>
        <div className="main">
          <Sidebar
            rows={rows}
            visible={visible}
            filters={filters}
            setFilters={setFilters}
            selected={selected}
            onSelect={focus}
            errorsOf={errorsOf}
            warnsOf={warnsOf}
            generatedCount={generated.reduce((n, g) => n + g.rows.length, 0)}
          />
          <div className="canvas">
            <ReactFlow
              nodes={nodes}
              edges={edges}
              nodeTypes={nodeTypes}
              onNodesChange={onNodesChange}
              onNodeDragStop={(_e, n) => {
                setPositions((p) => ({ ...p, [n.id]: n.position }));
                setDirty(true);
              }}
              onNodeClick={(_e, n) => setSelected(Number(n.id))}
              onPaneClick={() => {
                setSelected(null);
                setEdgeMenu(null);
                setNewMenu(false);
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
              proOptions={{ hideAttribution: true }}
            >
              <Background gap={24} color="#2a3142" />
              <MiniMap pannable zoomable nodeColor={(n) => KIND_COLOR[(n.data as { row: Row }).row.kind] || "#888"} maskColor="rgba(15,18,26,0.7)" />
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
          <div className="right">
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
              <div className="empty">
                <h3>Квест-редактор</h3>
                <p>Выберите квест на графе или в списке слева.</p>
                <ul>
                  <li>Стрелка от квеста к квесту: второй откроется после первого (<code>need_quest</code>).</li>
                  <li>Щелчок по стрелке: сменить её на «после одного из» или «исключают друг друга», либо убрать.</li>
                  <li>Всё, что меняете, сразу проверяется теми же проверками, что сервер делает при запуске.</li>
                  <li>«Сохранить» пишет <code>data/quests.json</code>. В игру правки попадают коммитом в ветку и слиянием в main.</li>
                </ul>
              </div>
            )}
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
        {toast && <div className="toast">{toast}</div>}
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
