import { useEffect, useState } from "react";
import { api, errText } from "../api";
import { Spinner } from "../components/ui";
import { lookupMob, mobIcon, mobName, remember } from "../store";
import type { Mob, Model } from "../types";

// world.creature_role: "" is a peaceful one (a trader, a guard, a cow)
const ROLE: Record<string, string> = {
  "": "мирный",
  mob: "враг",
  animal: "зверь",
  boss: "босс",
  object: "предмет",
};

// «Жители»: creatures of mobs.xml by a search, put on cells; each one a
// row of data/placements.json.
export default function InhabitantsPanel(props: {
  model: Model;
  armed: Mob | null;
  onArm: (m: Mob | null) => void;
  selected: number | null;
  onSelect: (i: number | null) => void;
  onWhy: (i: number, why: string) => void;
  onDelete: (i: number) => void;
  readOnly: boolean;
}) {
  const [q, setQ] = useState("");
  const [found, setFound] = useState<Mob[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [, setNames] = useState(0);

  useEffect(() => {
    let live = true;
    setBusy(true);
    const t = window.setTimeout(() => {
      api
        .mobs(q, 80)
        .then((list) => {
          if (!live) return;
          remember(list);
          setFound(list);
          setErr(null);
        })
        .catch((e) => live && setErr(errText(e)))
        .finally(() => live && setBusy(false));
    }, 250);
    return () => {
      live = false;
      window.clearTimeout(t);
    };
  }, [q]);

  // names of the inhabitants already there
  useEffect(() => {
    let live = true;
    Promise.all(props.model.inhabitants.map((r) => lookupMob(Number(r.type)))).then(() => live && setNames((n) => n + 1));
    return () => {
      live = false;
    };
  }, [props.model.inhabitants]);

  const war = props.model.attrs.war === "1";
  const sel = props.selected !== null ? props.model.inhabitants[props.selected] : null;
  return (
    <div className="tool-panel">
      {sel && props.selected !== null ? (
        <div className="selected-box">
          <div className="row">
            <img className="mob-icon" src={mobIcon(Number(sel.type))} alt="" />
            <b>{mobName(Number(sel.type))}</b>
            <span className="small muted">
              #{sel.type} · клетка {sel.cell[0]}:{sel.cell[1]}
            </span>
          </div>
          <label className="field-row">
            <span className="field-label">Почему он здесь</span>
            <textarea
              rows={2}
              value={sel.why || ""}
              disabled={props.readOnly}
              placeholder="Пусто: редактор напишет сам"
              onChange={(e) => props.onWhy(props.selected!, e.target.value)}
            />
          </label>
          {!props.readOnly && (
            <div className="row">
              <span className="small muted">Перетащите, чтобы переставить.</span>
              <span className="grow" />
              <button className="danger" onClick={() => props.onDelete(props.selected!)}>
                Убрать
              </button>
            </div>
          )}
        </div>
      ) : (
        <p className="hint">
          Найдите существо и щёлкните по клетке, чтобы поставить. Щелчок по жителю выбирает его, Delete убирает.
          {!war && " Локация мирная: враждебных существ сюда ставить нельзя."}
        </p>
      )}
      <input className="search" placeholder="Поиск: имя, номер, вид" value={q} onChange={(e) => setQ(e.target.value)} />
      {err && <p className="err-text">{err}</p>}
      <div className="mob-list">
        {busy && !found && (
          <p className="muted">
            <Spinner /> ищу…
          </p>
        )}
        {(found || []).map((m) => (
          <button
            key={m.type}
            className={`mob-row${props.armed?.type === m.type ? " on" : ""}${m.retired || !m.known ? " dim" : ""}`}
            disabled={props.readOnly}
            onClick={() => props.onArm(props.armed?.type === m.type ? null : m)}
            title={m.retired ? "выведен из игры" : !m.known ? "у клиента нет его имени" : `${m.sub}`}
          >
            <img src={m.icon} alt="" loading="lazy" />
            <span className="mob-text">
              <span className="ellipsis">{m.name}</span>
              <span className="small muted ellipsis">
                #{m.type} · {ROLE[m.role] ?? m.role}
                {m.sub ? ` · ${m.sub}` : ""}
                {m.retired ? " · выведен" : ""}
              </span>
            </span>
          </button>
        ))}
      </div>
      <h4>В локации: {props.model.inhabitants.length}</h4>
      <ul className="inh-list">
        {props.model.inhabitants.map((r, i) => (
          <li key={i} className={props.selected === i ? "sel" : ""} onClick={() => props.onSelect(i)}>
            <img src={mobIcon(Number(r.type))} alt="" loading="lazy" />
            <span className="ellipsis">{mobName(Number(r.type))}</span>
            <span className="small muted mono">
              {r.cell[0]}:{r.cell[1]}
            </span>
          </li>
        ))}
      </ul>
      {props.model.spawns.some((s) => s[2]) && (
        <p className="small muted">У файла есть свои существа (&lt;mobs&gt;): они только читаются и показаны фиолетовыми кольцами.</p>
      )}
    </div>
  );
}
