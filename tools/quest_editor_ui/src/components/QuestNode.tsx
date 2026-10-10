import { memo } from "react";
import { Handle, Position, type NodeProps, type Node } from "@xyflow/react";
import type { Row } from "../types";
import { creatureName, itemName, useLookup } from "../refs";
import { plain } from "../markup";
import { ItemIcon } from "./Pickers";

export interface QuestData extends Record<string, unknown> {
  row: Row;
  source?: string;
  errors: number;
  warns: number;
}

export type QuestNodeT = Node<QuestData, "quest">;

const KIND_SHORT: Record<string, string> = { kill_mobs: "Убить", bring_l_obj: "Принести", del_obj: "Доставить" };

function goal(row: Row, lk: ReturnType<typeof useLookup>): string {
  if (row.kind === "kill_mobs") {
    const mobs = row.mobs_kill || [];
    if (!mobs.length) return "цели не заданы";
    return mobs.map((m, i) => `${creatureName(lk, m)} ×${(row.num_kill || [])[i] ?? 1}`).join(", ");
  }
  if (row.kind === "bring_l_obj") {
    const objs = row.objs || [];
    if (!objs.length) return "предметы не заданы";
    return objs.map((o) => `${itemName(lk, o.obj)} ×${o.num ?? 1}`).join(", ");
  }
  if (row.obj) return `Доставить: ${itemName(lk, row.obj)}`;
  if (row.complete_skills && Object.keys(row.complete_skills).length) return "Развить навыки";
  return "Поговорить";
}

function who(list: number[] | undefined, lk: ReturnType<typeof useLookup>): string {
  const l = list || [];
  if (!l.length) return "—";
  return creatureName(lk, l[0]) + (l.length > 1 ? ` +${l.length - 1}` : "");
}

export const QuestNode = memo(({ data, selected }: NodeProps<QuestNodeT>) => {
  const lk = useLookup();
  const r = data.row;
  const readOnly = !!data.source;
  const things = [...(r.rew_obj || []), ...(r.rew_also || []).map((p) => p.obj), ...(r.rew_random || []).map((p) => p.obj)];
  const off = !(r.give || []).length;
  return (
    <div className={`qnode kind-${r.kind}${selected ? " sel" : ""}${readOnly ? " ro" : ""}${off ? " off" : ""}`}>
      <Handle type="target" position={Position.Top} isConnectable={!readOnly} />
      <div className="qhead">
        <span className="qkind">{KIND_SHORT[r.kind] || r.kind}</span>
        <span className="qtype">#{r.type}</span>
        {r.repeatable ? <span className="flag" title="Повторяемый">⟳{r.per_day ? ` ${r.per_day}/сут` : ""}</span> : null}
        {r.service ? <span className="flag" title="Служебный: не считается в дневной лимит">серв.</span> : null}
        {r.cost_afro || r.cost_gold ? <span className="flag" title="Комиссия при сдаче">$</span> : null}
        {r.way ? <span className="flag" title="Переход после сдачи">➜</span> : null}
        {readOnly ? <span className="flag" title={`Сгенерирован: ${data.source}`}>🔒</span> : null}
        <span className="grow" />
        {data.errors > 0 && <span className="qbadge err" title="Ошибки">{data.errors}</span>}
        {data.warns > 0 && <span className="qbadge warn" title="Предупреждения">{data.warns}</span>}
      </div>
      <div className="qname" title={plain(r.name)}>{plain(r.name) || "без названия"}</div>
      <div className="qwho">
        <span title="Выдаёт">{off ? "выключен" : who(r.give, lk)}</span>
        <span className="arrow">→</span>
        <span title="Принимает">{who(r.take, lk)}</span>
        {r.level ? <span className="lvl"> · ур. {r.level}</span> : null}
      </div>
      <div className="qgoal" title={goal(r, lk)}>{goal(r, lk)}</div>
      <div className="qrew">
        {r.rew_afro ? <span>{r.rew_afro} а</span> : null}
        {r.rew_gold ? <span className="gold">{(r.rew_gold / 100).toFixed(2)} G</span> : null}
        {r.rew_xp && Object.keys(r.rew_xp).length ? <span title="Опыт">XP</span> : null}
        {things.slice(0, 4).map((t, i) => (
          <ItemIcon key={i} t={t} size={20} />
        ))}
        {things.length > 4 && <span className="muted">+{things.length - 4}</span>}
      </div>
      <Handle type="source" position={Position.Bottom} isConnectable={!readOnly} />
    </div>
  );
});
QuestNode.displayName = "QuestNode";
