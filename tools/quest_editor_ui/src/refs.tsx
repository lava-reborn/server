import { createContext, useContext } from "react";
import type { CreatureRef, ItemRef, LocRef, Refs, Row } from "./types";
import { ITEM_ROOT_LABEL, NPC_ROOT_LABEL } from "./types";

export interface Lookup {
  refs: Refs | null;
  item: (t: number) => ItemRef | undefined;
  creature: (t: number) => CreatureRef | undefined;
  location: (id: number) => LocRef | undefined;
  where: (t: number) => LocRef[];
  quest: (t: number) => Row | undefined;
  npcs: CreatureRef[];
  mobs: CreatureRef[];
  quests: Row[];
}

export function makeLookup(refs: Refs | null, quests: Row[]): Lookup {
  const items = new Map((refs?.items || []).map((i) => [i.t, i]));
  const creatures = new Map((refs?.creatures || []).map((c) => [c.t, c]));
  const locs = new Map((refs?.locations || []).map((l) => [l.id, l]));
  const byType = new Map(quests.map((q) => [q.type, q]));
  const used = new Set<number>();
  for (const q of quests) for (const t of [...(q.give || []), ...(q.take || [])]) used.add(Number(t));
  const where = refs?.where || null;
  const placed = (t: number) => !!where && !!where[String(t)] && where[String(t)].length > 0;
  const npcs = (refs?.creatures || []).filter(
    (c) => used.has(c.t) || ([1, 4, 5].includes(c.root) && (where === null || placed(c.t))),
  );
  const mobs = (refs?.creatures || []).filter(
    (c) => c.root === 0 && ["mob", "boss", "animal", ""].includes(c.role) && (where === null || placed(c.t) || c.role !== ""),
  );
  return {
    refs,
    item: (t) => items.get(t),
    creature: (t) => creatures.get(t),
    location: (id) => locs.get(id),
    where: (t) => ((where && where[String(t)]) || []).map((id) => locs.get(id) || { id, title: `#${id}` }),
    quest: (t) => byType.get(t),
    npcs,
    mobs,
    quests,
  };
}

export const RefsContext = createContext<Lookup>(makeLookup(null, []));
export const useLookup = () => useContext(RefsContext);

export function itemName(lk: Lookup, t: number): string {
  return lk.item(t)?.n || `предмет #${t}`;
}

export function creatureName(lk: Lookup, t: number): string {
  const c = lk.creature(t);
  return c?.n || `#${t}`;
}

export function rootLabel(r: number): string {
  return ITEM_ROOT_LABEL[r] || "прочее";
}

export function npcRoleLabel(c: CreatureRef | undefined): string {
  if (!c) return "";
  if (c.role) return { mob: "моб", boss: "босс", animal: "зверь", object: "объект" }[c.role] || c.role;
  return NPC_ROOT_LABEL[c.root] || "";
}
