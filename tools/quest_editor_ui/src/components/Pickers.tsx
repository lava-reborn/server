import { useMemo, useRef, useState } from "react";
import type { CreatureRef, ItemRef, LocRef, Row } from "../types";
import { creatureName, itemName, npcRoleLabel, rootLabel, useLookup } from "../refs";
import { plain } from "../markup";
import { iconUrl } from "../api";

// --- a search box with a list under it --------------------------------------

interface SearchProps<T> {
  items: T[];
  text: (t: T) => string;
  render: (t: T) => React.ReactNode;
  onPick: (t: T) => void;
  placeholder: string;
  limit?: number;
}

export function Search<T>({ items, text, render, onPick, placeholder, limit = 40 }: SearchProps<T>) {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [hi, setHi] = useState(0);
  const box = useRef<HTMLInputElement>(null);
  const found = useMemo(() => {
    const s = q.trim().toLowerCase();
    if (!s) return [];
    const out: T[] = [];
    for (const it of items) {
      if (text(it).toLowerCase().includes(s)) {
        out.push(it);
        if (out.length >= limit) break;
      }
    }
    return out;
  }, [q, items, text, limit]);
  const pick = (t: T) => {
    onPick(t);
    setQ("");
    setOpen(false);
    box.current?.blur();
  };
  return (
    <div className="search">
      <input
        ref={box}
        value={q}
        placeholder={placeholder}
        onChange={(e) => {
          setQ(e.target.value);
          setOpen(true);
          setHi(0);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") setHi((h) => Math.min(h + 1, found.length - 1));
          else if (e.key === "ArrowUp") setHi((h) => Math.max(h - 1, 0));
          else if (e.key === "Enter" && found[hi]) pick(found[hi]);
          else if (e.key === "Escape") setOpen(false);
        }}
      />
      {open && found.length > 0 && (
        <div className="search-list">
          {found.map((it, i) => (
            <div
              key={i}
              className={"search-item" + (i === hi ? " hi" : "")}
              onMouseDown={(e) => {
                e.preventDefault();
                pick(it);
              }}
              onMouseEnter={() => setHi(i)}
            >
              {render(it)}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// --- what is picked, shown small ----------------------------------------------

export function ItemIcon({ t, size = 26 }: { t: number; size?: number }) {
  const lk = useLookup();
  const it = lk.item(t);
  if (it && it.i) {
    return <img className="item-icon" src={iconUrl(it.i)} width={size} height={size} alt="" />;
  }
  return (
    <span className="item-icon glyph" style={{ width: size, height: size }}>
      {it ? rootLabel(it.r).slice(0, 1).toUpperCase() : "?"}
    </span>
  );
}

export function ItemLine({ it }: { it: ItemRef }) {
  return (
    <span className="line">
      <ItemIcon t={it.t} />
      <span className="grow">{it.n}</span>
      <span className="muted">
        {rootLabel(it.r)}
        {it.q ? " · квестовый" : ""}
        {it.c ? ` · ${it.c} а` : ""} · #{it.t}
      </span>
    </span>
  );
}

export function CreatureLine({ c }: { c: CreatureRef }) {
  const lk = useLookup();
  const places = lk.where(c.t);
  return (
    <span className="line">
      <span className="grow">
        {c.n}
        {c.sub ? <span className="muted"> · {c.sub}</span> : null}
        {c.l ? <span className="lvl"> ур. {c.l}</span> : null}
      </span>
      <span className="muted">
        {npcRoleLabel(c)}
        {places.length ? ` · ${places[0].title}${places.length > 1 ? ` +${places.length - 1}` : ""}` : ""} · #{c.t}
      </span>
    </span>
  );
}

export function Chip({ children, onRemove, title }: { children: React.ReactNode; onRemove?: () => void; title?: string }) {
  return (
    <span className="qchip" title={title}>
      {children}
      {onRemove && (
        <button className="x" onClick={onRemove} title="Убрать">
          ✕
        </button>
      )}
    </span>
  );
}

// --- the pickers --------------------------------------------------------------

export function ItemPicker({ onPick, placeholder = "Найти предмет…" }: { onPick: (t: number) => void; placeholder?: string }) {
  const lk = useLookup();
  const items = lk.refs?.items || [];
  return (
    <Search
      items={items}
      text={(i) => `${i.n} #${i.t}`}
      render={(i) => <ItemLine it={i} />}
      onPick={(i) => onPick(i.t)}
      placeholder={placeholder}
    />
  );
}

export function CreaturePicker({ onPick, who, placeholder }: { onPick: (t: number) => void; who: "npc" | "mob" | "any"; placeholder?: string }) {
  const lk = useLookup();
  const list = who === "npc" ? lk.npcs : who === "mob" ? lk.mobs : lk.refs?.creatures || [];
  return (
    <Search
      items={list}
      text={(c) => `${c.n} #${c.t} ${lk.where(c.t).map((l) => l.title).join(" ")}`}
      render={(c) => <CreatureLine c={c} />}
      onPick={(c) => onPick(c.t)}
      placeholder={placeholder || (who === "npc" ? "Найти жителя…" : "Найти существо…")}
    />
  );
}

export function LocationPicker({ onPick, placeholder = "Найти локацию…" }: { onPick: (id: number) => void; placeholder?: string }) {
  const lk = useLookup();
  return (
    <Search<LocRef>
      items={lk.refs?.locations || []}
      text={(l) => `${l.title} #${l.id}`}
      render={(l) => (
        <span className="line">
          <span className="grow">{l.title || "без названия"}</span>
          <span className="muted">#{l.id}</span>
        </span>
      )}
      onPick={(l) => onPick(l.id)}
      placeholder={placeholder}
    />
  );
}

export function QuestPicker({ onPick, exclude, placeholder = "Найти квест…" }: { onPick: (t: number) => void; exclude?: number[]; placeholder?: string }) {
  const lk = useLookup();
  const list = useMemo(() => lk.quests.filter((q) => !(exclude || []).includes(q.type)), [lk.quests, exclude]);
  return (
    <Search<Row>
      items={list}
      text={(q) => `${plain(q.name)} #${q.type}`}
      render={(q) => (
        <span className="line">
          <span className="grow">{plain(q.name)}</span>
          <span className="muted">#{q.type}</span>
        </span>
      )}
      onPick={(q) => onPick(q.type)}
      placeholder={placeholder}
    />
  );
}

export function NpcChip({ t, onRemove }: { t: number; onRemove?: () => void }) {
  const lk = useLookup();
  const places = lk.where(t);
  return (
    <Chip onRemove={onRemove} title={places.map((p) => `${p.title} #${p.id}`).join("\n") || "не стоит ни в одной локации"}>
      <b>{creatureName(lk, t)}</b> <span className="muted">#{t}</span>
      {places.length > 0 ? (
        <span className="muted"> · {places[0].title}{places.length > 1 ? ` +${places.length - 1}` : ""}</span>
      ) : (
        <span className="warn-text"> · нигде не стоит</span>
      )}
    </Chip>
  );
}

export function QuestChip({ t, onRemove, onOpen }: { t: number; onRemove?: () => void; onOpen?: (t: number) => void }) {
  const lk = useLookup();
  const q = lk.quest(t);
  return (
    <Chip onRemove={onRemove}>
      <span className={onOpen ? "link" : ""} onClick={() => onOpen && onOpen(t)}>
        {q ? plain(q.name) : "нет такого"} <span className="muted">#{t}</span>
      </span>
    </Chip>
  );
}

export function LocChip({ id, onRemove }: { id: number; onRemove?: () => void }) {
  const lk = useLookup();
  const l = lk.location(id);
  return (
    <Chip onRemove={onRemove}>
      {l?.title || "локация"} <span className="muted">#{id}</span>
    </Chip>
  );
}

export function ItemChip({ t, onRemove }: { t: number; onRemove?: () => void }) {
  const lk = useLookup();
  return (
    <Chip onRemove={onRemove}>
      <ItemIcon t={t} size={18} /> {itemName(lk, t)} <span className="muted">#{t}</span>
    </Chip>
  );
}
