import type { Kind, Piece, Problem, Row, Slot, TextKey, TextsResp } from "../types";
import { KIND_LABEL, SKILL_LABEL, SPEC_LABEL, TEXT_KEYS } from "../types";
import { anyOf, excludes, needs, withList, withNeeds } from "../graph";
import { renderMarkup } from "../markup";
import { creatureName, useLookup } from "../refs";
import { Area, Check, Field, Gold, JsonBox, Num, Section } from "./Fields";
import {
  CreaturePicker,
  ItemChip,
  ItemIcon,
  ItemPicker,
  LocChip,
  LocationPicker,
  NpcChip,
  QuestChip,
  QuestPicker,
} from "./Pickers";

// Keys a widget below edits; the rest are shown as JSON («Прочие поля»).
const KNOWN = new Set([
  "type", "kind", "name", "start", "notfinish", "finish", "give", "take", "rew_obj", "num_rew_obj",
  "rew_afro", "rew_gold", "repeatable", "level", "q_type", "loc", "finish_loc", "rew_loc", "need_quest",
  "need_any", "excludes", "obj", "objs", "mobs_kill", "num_kill", "kill_also", "rew_xp", "rew_spec_xp",
  "requires_spec", "complete_skills", "service", "per_day", "cooldown", "cost_afro", "cost_gold",
  "start_obj", "lent", "stay_in", "rew_random", "rew_also", "max_level", "party_size", "own_texts",
  "way", "collection", "why",
]);

const TEXT_LABEL: Record<TextKey, string> = {
  name: "Название",
  start: "Начало (что говорит выдающий)",
  notfinish: "Пока не выполнено",
  finish: "Завершение (при сдаче)",
};

// A map cell packed as the client packs it (world.pack): gx << 13 | gy.
const unpack = (v: number) => [v >> 13, v & 0x1fff] as const;
const pack = (gx: number, gy: number) => (gx << 13) | gy;

interface Props {
  row: Row;
  readOnly?: string;
  texts: TextsResp | null;
  problems: Problem[];
  onChange: (row: Row) => void;
  onOpen: (t: number) => void;
  onFollowUp: () => void;
  onDuplicate: () => void;
  onDelete: () => void;
}

function without(row: Row, ...keys: string[]): Row {
  const r: Row = { ...row };
  for (const k of keys) delete r[k];
  return r;
}

export function Inspector({ row, readOnly, texts, problems, onChange, onOpen, onFollowUp, onDuplicate, onDelete }: Props) {
  const set = (patch: Partial<Row>) => {
    if (readOnly) return;
    const r: Row = { ...row };
    for (const [k, v] of Object.entries(patch)) {
      if (v === undefined) delete r[k];
      else r[k] = v;
    }
    onChange(r);
  };
  // Optional keys disappear when emptied, the table's habit.
  const setOpt = (key: string, v: unknown) => {
    const empty =
      v === undefined || v === null || v === "" || v === 0 || v === false ||
      (Array.isArray(v) && v.length === 0) || (typeof v === "object" && v !== null && !Array.isArray(v) && Object.keys(v).length === 0);
    set({ [key]: empty ? undefined : v } as Partial<Row>);
  };

  const changeKind = (kind: Kind) => {
    let r: Row = { ...row, kind };
    if (kind !== "kill_mobs") r = without(r, "mobs_kill", "num_kill", "kill_also");
    if (kind !== "bring_l_obj") r = without(r, "objs");
    if (kind !== "del_obj") r = without(r, "obj", "complete_skills");
    if (kind === "kill_mobs") r = { ...r, mobs_kill: r.mobs_kill || [], num_kill: r.num_kill || [] };
    if (kind === "bring_l_obj") r = { ...r, objs: r.objs || [] };
    onChange(r);
  };

  const own = new Set(row.own_texts || []);
  const others = Object.fromEntries(Object.entries(row).filter(([k]) => !KNOWN.has(k)));

  return (
    <div className={"inspector" + (readOnly ? " ro" : "")}>
      <div className="insp-head">
        <div className="insp-title">
          <span className={`qkind kind-${row.kind}`}>{KIND_LABEL[row.kind]}</span> <b>#{row.type}</b>
        </div>
        {!readOnly && (
          <div className="inline">
            <button onClick={onFollowUp} title="Новый квест, который откроется после этого">+ Продолжение</button>
            <button onClick={onDuplicate}>Копия</button>
            <button className="danger" onClick={onDelete}>Удалить</button>
          </div>
        )}
      </div>
      {readOnly && (
        <div className="note">
          Строка сгенерирована (<code>{readOnly}</code>) и здесь не правится: её сборщик перезапишет правку. Меняйте
          сборщик в <code>data/</code>.
        </div>
      )}
      {problems.length > 0 && (
        <div className="insp-problems">
          {problems.map((p, i) => (
            <div key={i} className={p.level === "error" ? "err-text" : "warn-text"} title={p.text}>
              {p.level === "error" ? "✖ " : "⚠ "}
              {p.ru}
            </div>
          ))}
        </div>
      )}

      <Section title="Основное">
        <Field label="Вид">
          <select value={row.kind} onChange={(e) => changeKind(e.target.value as Kind)} disabled={!!readOnly}>
            {(Object.keys(KIND_LABEL) as Kind[]).map((k) => (
              <option key={k} value={k}>
                {KIND_LABEL[k]}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Уровень" hint="Уровень, который клиент пишет у задания (level)">
          <Num value={row.level} min={0} onChange={(v) => set({ level: v })} />
        </Field>
        <Field label="Повторяемый">
          <Check
            value={!!row.repeatable}
            label="можно брать снова"
            onChange={(v) => (v ? set({ repeatable: 1 }) : set({ repeatable: 0, per_day: undefined, cooldown: undefined }))}
          />
        </Field>
        {!!row.repeatable && (
          <>
            <Field label="Раз в сутки" hint="per_day: сколько раз за сутки можно сдать; 0 — без ограничения. К началу добавится примечание оригинала.">
              <Num value={row.per_day || 0} min={0} onChange={(v) => setOpt("per_day", v)} />
            </Field>
            <Field label="Перерыв, сек" hint="cooldown: через сколько секунд после сдачи квест предложат снова">
              <Num value={row.cooldown || 0} min={0} onChange={(v) => setOpt("cooldown", v)} />
            </Field>
          </>
        )}
        <Field label="Служебный" hint="service: обмен, лотерея, экзамен — не считается в дневной лимит и в журнал">
          <Check value={!!row.service} label="услуга, а не задание" onChange={(v) => setOpt("service", v)} />
        </Field>
        <Field label="Группа" hint="party_size: на сколько игроков рассчитан (для текста и баланса)">
          <Num value={row.party_size || 0} min={0} onChange={(v) => setOpt("party_size", v)} />
        </Field>
        <Field label="Коллекция" hint="collection: строка собирает памятные вещи (keepsakes.py)">
          <Check value={!!row.collection} label="коллекция" onChange={(v) => setOpt("collection", v)} />
        </Field>
        <Field label="q_type" hint="Категория в клиенте; во всех строках 0">
          <Num value={row.q_type} onChange={(v) => set({ q_type: v })} />
        </Field>
      </Section>

      <Section title="Тексты" note="разметка клиента: <Br>, <b>, <hint>, %имя%, %sex?ый:ая%">
        {TEXT_KEYS.map((key) => (
          <TextBlock
            key={key}
            k={key}
            row={row}
            own={own.has(key)}
            original={texts?.original?.[key]}
            shown={texts?.shown?.[key]}
            readOnly={!!readOnly}
            onText={(v) => set({ [key]: v } as Partial<Row>)}
            onOwn={(on, seed) => {
              const next = new Set(own);
              if (on) next.add(key);
              else next.delete(key);
              const list = TEXT_KEYS.filter((k) => next.has(k));
              const patch: Partial<Row> = { own_texts: list.length ? list : undefined };
              if (on && seed !== undefined) (patch as Record<string, unknown>)[key] = seed;
              set(patch);
            }}
          />
        ))}
        {texts?.error && <div className="err-text">{texts.error}</div>}
      </Section>

      <Section title="Кто выдаёт и принимает">
        <Field label="Выдаёт" hint="give: у кого квест в списке. Пусто — квест выключен.">
          <div className="chips">
            {(row.give || []).map((t) => (
              <NpcChip key={t} t={t} onRemove={readOnly ? undefined : () => set({ give: row.give.filter((x) => x !== t) })} />
            ))}
          </div>
          {!readOnly && <CreaturePicker who="npc" onPick={(t) => set({ give: Array.from(new Set([...(row.give || []), t])) })} />}
        </Field>
        <Field label="Принимает" hint="take: кому сдают">
          <div className="chips">
            {(row.take || []).map((t) => (
              <NpcChip key={t} t={t} onRemove={readOnly ? undefined : () => set({ take: row.take.filter((x) => x !== t) })} />
            ))}
          </div>
          {!readOnly && (
            <div className="inline">
              <CreaturePicker who="npc" onPick={(t) => set({ take: Array.from(new Set([...(row.take || []), t])) })} />
              <button className="ghost" onClick={() => set({ take: [...(row.give || [])] })} title="Сдать тому же, кто выдал">
                = выдающий
              </button>
            </div>
          )}
        </Field>
      </Section>

      <Section title="Цель">
        {row.kind === "kill_mobs" && <KillGoal row={row} set={set} setOpt={setOpt} readOnly={!!readOnly} />}
        {row.kind === "bring_l_obj" && <BringGoal row={row} set={set} readOnly={!!readOnly} />}
        {row.kind === "del_obj" && <DelGoal row={row} set={set} setOpt={setOpt} readOnly={!!readOnly} />}
        <div className="sub">Метки на карте</div>
        <MapCell label="Где искать" hint="loc: клетка карты для метки задания" value={row.loc} onChange={(v) => set({ loc: v })} />
        <MapCell label="Где сдавать" hint="finish_loc: клетка карты для метки сдачи" value={row.finish_loc} onChange={(v) => set({ finish_loc: v })} />
      </Section>

      <Section title="Награды">
        <Field label="Афро">
          <Num value={row.rew_afro} min={0} onChange={(v) => set({ rew_afro: v })} />
        </Field>
        <Field label="Золото" hint="rew_gold хранится в сотых унции">
          <Gold value={row.rew_gold} onChange={(v) => set({ rew_gold: v })} />
        </Field>
        <Field label="На выбор" hint="rew_obj: окно показывает их, игрок берёт один">
          <PieceList
            pieces={(row.rew_obj || []).map((t, i) => ({ obj: t, num: (row.num_rew_obj || [])[i] ?? 1 }))}
            readOnly={!!readOnly}
            onChange={(ps) => set({ rew_obj: ps.map((p) => p.obj), num_rew_obj: ps.map((p) => p.num ?? 1) })}
          />
        </Field>
        <Field label="Ещё выдаётся" hint="rew_also: сверх выбранного, окно их не показывает, видно в «Вы получили»">
          <PieceList pieces={row.rew_also || []} readOnly={!!readOnly} onChange={(ps) => setOpt("rew_also", ps)} />
        </Field>
        <Field label="Лотерея" hint="rew_random: одно из списка по весу">
          <PieceList pieces={row.rew_random || []} readOnly={!!readOnly} weight onChange={(ps) => setOpt("rew_random", ps)} />
        </Field>
        <Field label="Опыт в навыки" hint="rew_xp">
          <KeyNums labels={SKILL_LABEL} value={row.rew_xp || {}} onChange={(v) => setOpt("rew_xp", v)} />
        </Field>
        <Field label="Опыт в специализации" hint="rew_spec_xp: целиком в специализацию; неизученная не получит ничего">
          <KeyNums labels={SPEC_LABEL} value={row.rew_spec_xp || {}} onChange={(v) => setOpt("rew_spec_xp", v)} />
        </Field>
        <Field label="Перемещение" hint="rew_loc=1: клиент пишет «после выполнения задания Вас переместят в другое место»">
          <Check value={!!row.rew_loc} label="предупредить о переносе" onChange={(v) => setOpt("rew_loc", v ? 1 : 0)} />
        </Field>
      </Section>

      <Section title="Условия">
        <Field label="После всех" hint="need_quest: все эти квесты сданы. На графе — сплошная стрелка.">
          <QuestList list={needs(row)} onOpen={onOpen} readOnly={!!readOnly} self={row.type} onChange={(l) => onChange(withNeeds(row, l))} />
        </Field>
        <Field label="После одного из" hint="need_any: хотя бы один сдан. На графе — пунктир.">
          <QuestList list={anyOf(row)} onOpen={onOpen} readOnly={!!readOnly} self={row.type} onChange={(l) => onChange(withList(row, "need_any", l))} />
        </Field>
        <Field label="Исключает" hint="excludes: другая ветка выбора — не предлагается, если взят или сдан любой из них. На графе — красный пунктир.">
          <QuestList list={excludes(row)} onOpen={onOpen} readOnly={!!readOnly} self={row.type} onChange={(l) => onChange(withList(row, "excludes", l))} />
        </Field>
        <Field label="Пока лучший навык ≤" hint="max_level: предлагается, пока лучший навык не выше; пусто — без ограничения">
          <span className="inline">
            <Check
              value={row.max_level !== undefined && row.max_level !== null}
              label=""
              onChange={(v) => set({ max_level: v ? 2 : undefined })}
            />
            {row.max_level !== undefined && row.max_level !== null && (
              <Num value={row.max_level} min={0} max={20} onChange={(v) => set({ max_level: v })} />
            )}
          </span>
        </Field>
        <Field label="Нужны специализации" hint="requires_spec: не предлагается без изученных">
          <SpecSet value={row.requires_spec} onChange={(v) => setOpt("requires_spec", v.length === 0 ? undefined : v.length === 1 ? v[0] : v)} />
        </Field>
        <Field label="Комиссия, афро" hint="cost_afro: списывается при сдаче, пока не хватает — квест не готов">
          <Num value={row.cost_afro || 0} min={0} onChange={(v) => setOpt("cost_afro", v)} />
        </Field>
        <Field label="Комиссия, золото">
          <Gold value={row.cost_gold} onChange={(v) => setOpt("cost_gold", v)} />
        </Field>
      </Section>

      <Section title="Выдаётся при взятии" open={!!(row.start_obj && row.start_obj.length)}>
        <Field label="Предметы" hint="start_obj: кладутся в рюкзак при взятии, забираются при сдаче и отказе">
          <PieceList pieces={row.start_obj || []} lentFlag readOnly={!!readOnly} onChange={(ps) => setOpt("start_obj", ps)} />
        </Field>
        <Field label="Всё на время" hint="lent: выданное — во временное пользование: не продать, не передать, не выпадет">
          <Check value={!!row.lent} label="даётся на время" onChange={(v) => setOpt("lent", v)} />
        </Field>
        <Field label="Только в локациях" hint="stay_in: вне этих локаций выданное на время забирается">
          <div className="chips">
            {(row.stay_in || []).map((id) => (
              <LocChip key={id} id={id} onRemove={readOnly ? undefined : () => onChange(withList(row, "stay_in", (row.stay_in || []).filter((x) => x !== id)))} />
            ))}
          </div>
          {!readOnly && <LocationPicker onPick={(id) => onChange(withList(row, "stay_in", [...(row.stay_in || []), id]))} />}
        </Field>
      </Section>

      <Section title="Переход после сдачи" open={!!row.way}>
        {row.way ? (
          <>
            <Field label="Откуда">
              <LocSingle value={row.way.at} onChange={(v) => set({ way: { ...row.way, at: v } })} />
            </Field>
            <Field label="Куда">
              <LocSingle value={row.way.target_loc_id} onChange={(v) => set({ way: { ...row.way, target_loc_id: v } })} />
            </Field>
            <Field label="Кто везёт">
              {row.way.driver ? (
                <NpcChip t={row.way.driver} onRemove={() => set({ way: { ...row.way, driver: undefined } })} />
              ) : (
                <CreaturePicker who="npc" onPick={(t) => set({ way: { ...row.way, driver: t } })} />
              )}
            </Field>
            {!readOnly && (
              <button className="ghost" onClick={() => set({ way: undefined, rew_loc: undefined })}>
                Убрать переход
              </button>
            )}
          </>
        ) : (
          !readOnly && (
            <button onClick={() => set({ way: { at: 0, target_loc_id: 0 }, rew_loc: 1 })}>Добавить переход</button>
          )
        )}
      </Section>

      <Section title="Заметка (why)" open={false}>
        <Area value={row.why || ""} rows={6} onChange={(v) => setOpt("why", v)} />
      </Section>

      {Object.keys(others).length > 0 && (
        <Section title="Прочие поля" open={false} note="без своего виджета">
          <JsonBox
            value={others}
            onApply={(v) => {
              if (readOnly || typeof v !== "object" || v === null) return;
              const r: Row = Object.fromEntries(Object.entries(row).filter(([k]) => KNOWN.has(k))) as Row;
              onChange({ ...r, ...(v as Record<string, unknown>) } as Row);
            }}
          />
        </Section>
      )}

      <Section title="Строка целиком (JSON)" open={false}>
        <JsonBox
          value={row}
          rows={18}
          onApply={(v) => {
            if (readOnly || typeof v !== "object" || v === null) return;
            const r = v as Row;
            if (r.type !== row.type) {
              alert("Номер квеста здесь не меняется.");
              return;
            }
            onChange(r);
          }}
        />
      </Section>
    </div>
  );
}

// --- texts -------------------------------------------------------------------------

function TextBlock({
  k,
  row,
  own,
  original,
  shown,
  readOnly,
  onText,
  onOwn,
}: {
  k: TextKey;
  row: Row;
  own: boolean;
  original?: string;
  shown?: string;
  readOnly: boolean;
  onText: (v: string) => void;
  onOwn: (on: boolean, seed?: string) => void;
}) {
  const value = String(row[k] ?? "");
  const laid = !!original && !own;
  return (
    <div className="textblock">
      <div className="tb-head">
        <b>{TEXT_LABEL[k]}</b>
        {original && (
          <span className="muted">
            {laid ? " · текст оригинала (texts.xml)" : " · свой текст поверх оригинала"}
          </span>
        )}
        <span className="grow" />
        {original && !readOnly && (
          laid ? (
            <button className="ghost" onClick={() => onOwn(true, original)} title="Писать свой текст вместо оригинального (own_texts)">
              Написать свой
            </button>
          ) : (
            <button className="ghost" onClick={() => onOwn(false)} title="Вернуть текст оригинала">
              Вернуть оригинал
            </button>
          )
        )}
      </div>
      {laid ? (
        <div className="preview orig" dangerouslySetInnerHTML={{ __html: renderMarkup(original) }} />
      ) : k === "name" ? (
        <input className="wide" value={value} disabled={readOnly} onChange={(e) => onText(e.target.value)} />
      ) : (
        <textarea rows={4} value={value} disabled={readOnly} onChange={(e) => onText(e.target.value)} />
      )}
      {shown !== undefined && shown !== (laid ? original : value) && (
        <div className="tb-shown">
          <span className="muted small">Игрок увидит:</span>
          <div className="preview" dangerouslySetInnerHTML={{ __html: renderMarkup(shown) }} />
        </div>
      )}
      {!laid && k !== "name" && value && (shown === undefined || shown === value) && (
        <div className="preview" dangerouslySetInnerHTML={{ __html: renderMarkup(value) }} />
      )}
    </div>
  );
}

// --- goals ---------------------------------------------------------------------------

type SetFn = (patch: Partial<Row>) => void;
type SetOptFn = (key: string, v: unknown) => void;

function KillGoal({ row, set, setOpt, readOnly }: { row: Row; set: SetFn; setOpt: SetOptFn; readOnly: boolean }) {
  const lk = useLookup();
  const mobs = row.mobs_kill || [];
  const nums = row.num_kill || [];
  const also = row.kill_also || {};
  return (
    <>
      <Field label="Убить" hint="mobs_kill / num_kill">
        <div className="rows">
          {mobs.map((m, i) => (
            <div className="row-line" key={i}>
              <span className="grow">
                {creatureName(lk, m)} <span className="muted">#{m}{lk.creature(m)?.l ? ` · ур. ${lk.creature(m)!.l}` : ""}</span>
              </span>
              
              <Num value={nums[i] ?? 1} min={1} width={64} onChange={(v) => set({ num_kill: mobs.map((_, j) => (j === i ? v : nums[j] ?? 1)) })} /><span className="muted">шт.</span>
              {!readOnly && (
                <button className="x" title="Убрать" onClick={() => set({ mobs_kill: mobs.filter((_, j) => j !== i), num_kill: nums.filter((_, j) => j !== i) })}>
                  ✕
                </button>
              )}
            </div>
          ))}
        </div>
        {!readOnly && <CreaturePicker who="mob" onPick={(t) => set({ mobs_kill: [...mobs, t], num_kill: [...nums, 5] })} />}
      </Field>
      <Field label="Засчитывать также" hint="kill_also: другое существо засчитывается за цель из списка">
        <div className="rows">
          {Object.entries(also).map(([other, slot]) => (
            <div className="row-line" key={other}>
              <span className="grow">{creatureName(lk, Number(other))} <span className="muted">#{other}</span></span>
              <span className="muted">за</span>
              <select value={slot} onChange={(e) => setOpt("kill_also", { ...also, [other]: Number(e.target.value) })}>
                {mobs.map((m) => (
                  <option key={m} value={m}>
                    {creatureName(lk, m)}
                  </option>
                ))}
              </select>
              {!readOnly && (
                <button className="x" title="Убрать" onClick={() => setOpt("kill_also", Object.fromEntries(Object.entries(also).filter(([o]) => o !== other)))}>
                  ✕
                </button>
              )}
            </div>
          ))}
        </div>
        {!readOnly && mobs.length > 0 && (
          <CreaturePicker who="mob" placeholder="Добавить существо…" onPick={(t) => setOpt("kill_also", { ...also, [String(t)]: mobs[0] })} />
        )}
      </Field>
    </>
  );
}

function BringGoal({ row, set, readOnly }: { row: Row; set: SetFn; readOnly: boolean }) {
  const lk = useLookup();
  const objs = row.objs || [];
  const put = (i: number, s: Slot) => set({ objs: objs.map((o, j) => (j === i ? s : o)) });
  return (
    <Field label="Принести" hint="objs: до 6 предметов. Можно указать мобов, с которых предмет падает только для этого квеста (шанс 0..1).">
      <div className="rows">
        {objs.map((o, i) => (
          <div className="slot" key={i}>
            <div className="row-line">
              <ItemIcon t={o.obj} />
              <span className="grow">{lk.item(o.obj)?.n || `#${o.obj}`} <span className="muted">#{o.obj}</span></span>
              
              <Num value={o.num ?? 1} min={1} width={64} onChange={(v) => put(i, { ...o, num: v })} /><span className="muted">шт.</span>
              {!readOnly && (
                <button className="x" title="Убрать" onClick={() => set({ objs: objs.filter((_, j) => j !== i) })}>
                  ✕
                </button>
              )}
            </div>
            <div className="row-line small">
              <span className="muted">падает с:</span>
              <span className="chips">
                {(o.mobs || []).map((m) => (
                  <span className="chip" key={m}>
                    {creatureName(lk, m)}
                    {!readOnly && (
                      <button className="x" title="Убрать" onClick={() => put(i, cleanSlot({ ...o, mobs: (o.mobs || []).filter((x) => x !== m) }))}>
                        ✕
                      </button>
                    )}
                  </span>
                ))}
              </span>
              {!readOnly && <CreaturePicker who="mob" placeholder="моб…" onPick={(t) => put(i, { ...o, mobs: Array.from(new Set([...(o.mobs || []), t])) })} />}
            </div>
            {(o.mobs || []).length > 0 && (
              <div className="row-line small">
                <span className="muted">шанс</span>
                <Num value={o.drop ?? 0} min={0} max={1} step={0.01} width={70} onChange={(v) => put(i, cleanSlot({ ...o, drop: v || undefined }))} />
                <span className="muted">группа</span>
                <input
                  style={{ width: 110 }}
                  value={o.one_of || ""}
                  placeholder="одно из…"
                  onChange={(e) => put(i, cleanSlot({ ...o, one_of: e.target.value || undefined }))}
                />
              </div>
            )}
          </div>
        ))}
      </div>
      {!readOnly && objs.length < 6 && <ItemPicker onPick={(t) => set({ objs: [...objs, { obj: t, num: 1 }] })} />}
    </Field>
  );
}

function cleanSlot(s: Slot): Slot {
  const out: Slot = { obj: s.obj };
  for (const [k, v] of Object.entries(s)) {
    if (k === "obj") continue;
    if (v === undefined || v === null || v === "" || (Array.isArray(v) && v.length === 0)) continue;
    out[k] = v;
  }
  return out;
}

function DelGoal({ row, set, setOpt, readOnly }: { row: Row; set: SetFn; setOpt: SetOptFn; readOnly: boolean }) {
  return (
    <>
      <Field label="Доставить" hint="obj: что отнести. Пусто — задание-разговор.">
        {row.obj ? (
          <ItemChip t={row.obj} onRemove={readOnly ? undefined : () => setOpt("obj", 0)} />
        ) : (
          <span className="muted">разговор (ничего нести не нужно)</span>
        )}
        {!readOnly && <ItemPicker onPick={(t) => set({ obj: t, complete_skills: undefined })} />}
      </Field>
      {!row.obj && (
        <Field label="Развить навыки" hint="complete_skills: сдать можно, когда навыки дойдут до уровней (1..20)">
          <KeyNums labels={SKILL_LABEL} value={row.complete_skills || {}} max={20} onChange={(v) => setOpt("complete_skills", v)} />
        </Field>
      )}
    </>
  );
}

// --- small editors ------------------------------------------------------------------

function PieceList({
  pieces,
  onChange,
  readOnly,
  weight,
  lentFlag,
}: {
  pieces: Piece[];
  onChange: (ps: Piece[]) => void;
  readOnly: boolean;
  weight?: boolean;
  lentFlag?: boolean;
}) {
  const lk = useLookup();
  const put = (i: number, p: Piece) => onChange(pieces.map((q, j) => (j === i ? p : q)));
  return (
    <div>
      <div className="rows">
        {pieces.map((p, i) => (
          <div className="row-line" key={i}>
            <ItemIcon t={p.obj} />
            <span className="grow">{lk.item(p.obj)?.n || `#${p.obj}`} <span className="muted">#{p.obj}</span></span>
            
            <Num value={p.num ?? 1} min={1} width={64} onChange={(v) => put(i, { ...p, num: v })} /><span className="muted">шт.</span>
            {weight && (
              <>
                <span className="muted">вес</span>
                <Num value={p.w ?? 1} min={1} width={60} onChange={(v) => put(i, { ...p, w: v })} />
              </>
            )}
            {lentFlag && (
              <label className="check small" title="lent у одного предмета">
                <input type="checkbox" checked={!!p.lent} onChange={(e) => {
                  const q: Piece = { ...p };
                  if (e.target.checked) q.lent = true;
                  else delete q.lent;
                  put(i, q);
                }} /> на время
              </label>
            )}
            {!readOnly && (
              <button className="x" title="Убрать" onClick={() => onChange(pieces.filter((_, j) => j !== i))}>
                ✕
              </button>
            )}
          </div>
        ))}
      </div>
      {!readOnly && <ItemPicker onPick={(t) => onChange([...pieces, weight ? { obj: t, num: 1, w: 1 } : { obj: t, num: 1 }])} />}
    </div>
  );
}

function KeyNums({
  labels,
  value,
  onChange,
  max,
}: {
  labels: Record<string, string>;
  value: Record<string, number>;
  onChange: (v: Record<string, number>) => void;
  max?: number;
}) {
  return (
    <div className="keynums">
      {Object.entries(labels).map(([k, label]) => (
        <label key={k} className="keynum">
          <span>{label}</span>
          <Num
            value={value[k] || 0}
            min={0}
            max={max}
            width={74}
            onChange={(v) => {
              const next = { ...value };
              if (v > 0) next[k] = v;
              else delete next[k];
              onChange(next);
            }}
          />
        </label>
      ))}
    </div>
  );
}

function SpecSet({ value, onChange }: { value: string | string[] | undefined; onChange: (v: string[]) => void }) {
  const list = value === undefined ? [] : Array.isArray(value) ? value : [value];
  return (
    <div className="keynums">
      {Object.entries(SPEC_LABEL).map(([k, label]) => (
        <label key={k} className="check">
          <input
            type="checkbox"
            checked={list.includes(k)}
            onChange={(e) => onChange(e.target.checked ? [...list, k] : list.filter((x) => x !== k))}
          />{" "}
          {label}
        </label>
      ))}
    </div>
  );
}

function QuestList({
  list,
  onChange,
  onOpen,
  readOnly,
  self,
}: {
  list: number[];
  onChange: (l: number[]) => void;
  onOpen: (t: number) => void;
  readOnly: boolean;
  self: number;
}) {
  return (
    <div>
      <div className="chips">
        {list.map((t) => (
          <QuestChip key={t} t={t} onOpen={onOpen} onRemove={readOnly ? undefined : () => onChange(list.filter((x) => x !== t))} />
        ))}
      </div>
      {!readOnly && <QuestPicker exclude={[self, ...list]} onPick={(t) => onChange([...list, t])} />}
    </div>
  );
}

function LocSingle({ value, onChange }: { value: number | undefined; onChange: (v: number) => void }) {
  return value ? <LocChip id={value} onRemove={() => onChange(0)} /> : <LocationPicker onPick={onChange} />;
}

function MapCell({ label, hint, value, onChange }: { label: string; hint: string; value: number | undefined; onChange: (v: number) => void }) {
  const on = !!value && value > 0;
  const [gx, gy] = on ? unpack(value!) : [0, 0];
  return (
    <Field label={label} hint={hint}>
      <span className="inline">
        <Check value={on} label="" onChange={(v) => onChange(v ? pack(6268, 1819) : 0)} />
        {on && (
          <>
            <span className="muted">X</span>
            <Num value={gx} min={0} max={8191} width={74} onChange={(v) => onChange(pack(v, gy))} />
            <span className="muted">Y</span>
            <Num value={gy} min={0} max={8191} width={74} onChange={(v) => onChange(pack(gx, v))} />
          </>
        )}
      </span>
    </Field>
  );
}
