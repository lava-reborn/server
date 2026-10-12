import { Field } from "../components/ui";
import type { Info, Model } from "../types";

// «Свойства»: the attributes of <location> the owner sets, and the why.
export default function PropsPanel(props: {
  info: Info | null;
  model: Model;
  readOnly: boolean;
  onAttr: (k: string, v: string) => void;
  onWhy: (v: string) => void;
}) {
  const m = props.model;
  const a = m.attrs;
  const ro = props.readOnly;
  return (
    <div className="tool-panel">
      <Field label="Название" hint="Его видит игрок над локацией">
        <input value={a.title || ""} disabled={ro} maxLength={80} onChange={(e) => props.onAttr("title", e.target.value)} />
      </Field>
      {m.state !== "original" && (
        <Field label="Почему это место есть" hint="Ваше слово, строка data/locations/index.json">
          <textarea rows={3} value={m.index?.why || ""} disabled={ro} onChange={(e) => props.onWhy(e.target.value)} />
        </Field>
      )}
      <Field label="fn" hint="Внутреннее имя: латиница, цифры и _">
        <input className="mono" value={a.fn || ""} disabled={ro} onChange={(e) => props.onAttr("fn", e.target.value.replace(/[^A-Za-z0-9_]/g, ""))} />
      </Field>
      <label className="check">
        <input type="checkbox" checked={a.war === "1"} disabled={ro} onChange={(e) => props.onAttr("war", e.target.checked ? "1" : "0")} />
        Военная (war): враждебные существа, военные входы
      </label>
      <label className="check">
        <input type="checkbox" checked={a.pvp === "1"} disabled={ro} onChange={(e) => props.onAttr("pvp", e.target.checked ? "1" : "0")} />
        PvP: игроки могут нападать друг на друга
      </label>
      <Field label="Музыка">
        <select value={a.bgsound || ""} disabled={ro} onChange={(e) => props.onAttr("bgsound", e.target.value)}>
          <option value="">по умолчанию</option>
          {(props.info?.tracks || []).map((t) => (
            <option key={t}>{t}</option>
          ))}
        </select>
      </Field>
      <dl className="facts">
        <dt>Номер</dt>
        <dd>{m.id}</dd>
        <dt>Размер</dt>
        <dd>
          {m.width} × {m.height} клеток
        </dd>
        <dt>Библиотека</dt>
        <dd>{a.library}</dd>
        <dt>Фон</dt>
        <dd className="mono small">{m.background?.id || a.bg || "нет"}</dd>
        {m.from !== null && (
          <>
            <dt>Копия</dt>
            <dd>#{m.from}</dd>
          </>
        )}
        {m.index?.created && (
          <>
            <dt>Сделано</dt>
            <dd>
              {m.index.created}, {m.index.author}
            </dd>
          </>
        )}
      </dl>
    </div>
  );
}
