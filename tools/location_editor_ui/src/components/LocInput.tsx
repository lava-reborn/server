import { useEffect, useId, useState } from "react";
import { getLocations } from "../store";
import type { LocRow } from "../types";

// A location by its number, with the titles to pick from as one types.
export default function LocInput(props: {
  value: number | null;
  onChange: (id: number | null) => void;
  placeholder?: string;
  exclude?: number | string;
  label?: string;
}) {
  const id = useId();
  const [rows, setRows] = useState<LocRow[]>([]);
  const [text, setText] = useState(props.value !== null ? String(props.value) : "");
  useEffect(() => {
    getLocations().then(setRows, () => undefined);
  }, []);
  useEffect(() => {
    setText(props.value !== null ? String(props.value) : "");
  }, [props.value]);
  const row = rows.find((r) => r.id === props.value);
  const q = text.trim().toLowerCase();
  const options = rows
    .filter((r) => r.id !== props.exclude && !r.closed)
    .filter((r) => (!q ? true : /^\d+$/.test(q) ? String(r.id).startsWith(q) : r.title.toLowerCase().includes(q)))
    .slice(0, 80);
  return (
    <span className="loc-input">
      <input
        list={id}
        value={text}
        aria-label={props.label || "Номер локации"}
        placeholder={props.placeholder || "номер или название"}
        onChange={(e) => {
          const v = e.target.value;
          setText(v);
          const m = v.match(/^\s*(\d+)/);
          props.onChange(m ? Number(m[1]) : null);
        }}
      />
      <datalist id={id}>
        {options.map((r) => (
          <option key={r.id} value={`${r.id} — ${r.title}`} />
        ))}
      </datalist>
      {props.value !== null && (
        <span className={`small ${row ? "muted" : "err-text"}`}>{row ? `«${row.title}»` : "нет такой локации"}</span>
      )}
    </span>
  );
}
