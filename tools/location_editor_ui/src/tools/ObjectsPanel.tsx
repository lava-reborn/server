import { useMemo, useState } from "react";
import { Spinner } from "../components/ui";
import type { Model, Palette, PaletteItem } from "../types";

type Tab = "lib" | "ext" | "mine";
const PAGE = 120;

// «Объекты»: the palette (the location's library, the game's separate
// sprites, the owner's own objects) and the picked placing.
export default function ObjectsPanel(props: {
  model: Model;
  palette: Palette | null;
  paletteErr: string | null;
  armed: PaletteItem | null;
  onArm: (it: PaletteItem | null) => void;
  stamp: boolean;
  onStamp: (v: boolean) => void;
  selected: [number, number] | null;
  onNudge: (dx: number, dy: number) => void;
  onDelete: () => void;
  readOnly: boolean;
}) {
  const [tab, setTab] = useState<Tab>("lib");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const items = useMemo(() => {
    const all = props.palette?.items || [];
    const words = q.trim().toLowerCase().split(/\s+/).filter(Boolean);
    return all.filter((it) => {
      const t: Tab = it.origin === "object" ? "mine" : it.type === "lib" ? "lib" : "ext";
      if (t !== tab) return false;
      const hay = `${it.name} ${it.title || ""}`.toLowerCase();
      return words.every((w) => hay.includes(w));
    });
  }, [props.palette, tab, q]);
  const counts = useMemo(() => {
    const c = { lib: 0, ext: 0, mine: 0 };
    for (const it of props.palette?.items || []) c[it.origin === "object" ? "mine" : it.type === "lib" ? "lib" : "ext"]++;
    return c;
  }, [props.palette]);

  const sel = props.selected;
  const sp = sel ? props.model.sprites[sel[0]] : null;
  const anchor = sp && sel ? sp.anchors[sel[1]] : null;
  // the owner's object by the name he gave it, its id under it
  const mine = sp ? (props.palette?.items || []).find((it) => it.origin === "object" && it.name === sp.id) : undefined;

  return (
    <div className="tool-panel objects-panel">
      {sp && anchor ? (
        <div className="selected-box">
          <div className="row">
            <b className="ellipsis" title={sp.id}>
              {mine?.title || sp.id}
            </b>
            <span className="tag">{sp.id.startsWith("c_") ? "мой" : sp.type === "ext" ? "отдельный" : "библиотека"}</span>
          </div>
          {mine?.title && <div className="small muted mono ellipsis">{sp.id}</div>}
          <div className="small muted">
            клетка {anchor[0]}:{anchor[1]} · сдвиг dx {sp.dx}, dy {sp.dy}
            {sp.anchors.length > 1 ? ` · таких же мест: ${sp.anchors.length}` : ""}
          </div>
          {!props.readOnly && (
            <div className="row nudge">
              <span className="small muted">Сдвиг на пиксель (Alt+стрелки):</span>
              <button className="arr" onClick={() => props.onNudge(-1, 0)} aria-label="влево">
                ←
              </button>
              <button className="arr" onClick={() => props.onNudge(0, -1)} aria-label="вверх">
                ↑
              </button>
              <button className="arr" onClick={() => props.onNudge(0, 1)} aria-label="вниз">
                ↓
              </button>
              <button className="arr" onClick={() => props.onNudge(1, 0)} aria-label="вправо">
                →
              </button>
              <span className="grow" />
              <button className="danger" onClick={props.onDelete}>
                Убрать
              </button>
            </div>
          )}
        </div>
      ) : (
        <p className="hint">
          Выберите картинку и щёлкните по клетке, чтобы поставить. Перетащите поставленную, чтобы сдвинуть; Delete убирает,
          Alt+стрелки двигают на пиксель, Esc снимает выбор.
        </p>
      )}
      <label className="check">
        <input type="checkbox" checked={props.stamp} onChange={(e) => props.onStamp(e.target.checked)} /> Со следом: ставить и
        убирать стены под объектом
      </label>
      <div className="tabs" role="tablist">
        <button role="tab" className={tab === "lib" ? "on" : ""} onClick={() => (setTab("lib"), setPage(1))}>
          Этой локации <span className="n">{counts.lib}</span>
        </button>
        <button role="tab" className={tab === "ext" ? "on" : ""} onClick={() => (setTab("ext"), setPage(1))}>
          Отдельные <span className="n">{counts.ext}</span>
        </button>
        <button role="tab" className={tab === "mine" ? "on" : ""} onClick={() => (setTab("mine"), setPage(1))}>
          Мои <span className="n">{counts.mine}</span>
        </button>
      </div>
      <input
        className="search"
        placeholder="Поиск по имени"
        value={q}
        onChange={(e) => {
          setQ(e.target.value);
          setPage(1);
        }}
      />
      {tab === "lib" && <p className="small muted">Картинки библиотеки {props.palette?.library || props.model.attrs.library}: у локации одна библиотека.</p>}
      {tab === "ext" && <p className="small muted">Отдельные спрайты игры ставятся в любую локацию.</p>}
      {tab === "mine" && <p className="small muted">Ваши картинки из «Мои объекты». Встают ногами на клетку.</p>}
      {props.paletteErr && <p className="err-text">{props.paletteErr}</p>}
      {!props.palette && !props.paletteErr && (
        <p className="muted">
          <Spinner /> читаю палитру…
        </p>
      )}
      {props.palette?.warming && tab === "ext" && (
        <p className="small warn-text">
          <Spinner /> Картинки отдельных спрайтов ещё готовятся (около минуты в первый раз).
        </p>
      )}
      <div className="palette-grid">
        {items.slice(0, PAGE * page).map((it) => (
          <button
            key={`${it.type}:${it.name}`}
            className={`pal-item${props.armed && props.armed.name === it.name && props.armed.type === it.type ? " on" : ""}`}
            title={`${it.title ? it.title + " · " : ""}${it.name}${it.w ? ` · ${it.w}×${it.h}` : ""}${it.default?.uses ? ` · в оригинале ${it.default.uses} раз` : ""}`}
            disabled={props.readOnly}
            onClick={() => props.onArm(props.armed && props.armed.name === it.name && props.armed.type === it.type ? null : it)}
          >
            {it.thumb ? <img src={it.thumb} alt="" loading="lazy" /> : <span className="noimg">?</span>}
            <span className="cap">{it.title || it.name.replace(/\.(png|jpg)$/i, "")}</span>
            {(it.frames || 1) > 1 && <span className="anim">анимация</span>}
          </button>
        ))}
      </div>
      {items.length > PAGE * page && (
        <button className="more" onClick={() => setPage(page + 1)}>
          Показать ещё {items.length - PAGE * page}
        </button>
      )}
      {props.palette && !items.length && (
        <p className="muted small">{tab === "mine" ? "Своих объектов пока нет: добавьте их в «Мои объекты»." : "Ничего не нашлось."}</p>
      )}
    </div>
  );
}
