import { useEffect, useState } from "react";

export function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <label className="field">
      <span className="flabel" title={hint}>
        {label}
        {hint ? <span className="hint-mark">?</span> : null}
      </span>
      <span className="fbody">{children}</span>
    </label>
  );
}

export function Num({
  value,
  onChange,
  min,
  max,
  step,
  width = 90,
}: {
  value: number | undefined | null;
  onChange: (v: number) => void;
  min?: number;
  max?: number;
  step?: number;
  width?: number;
}) {
  const [text, setText] = useState(value === undefined || value === null ? "" : String(value));
  useEffect(() => setText(value === undefined || value === null ? "" : String(value)), [value]);
  return (
    <input
      type="number"
      style={{ width }}
      value={text}
      min={min}
      max={max}
      step={step}
      onChange={(e) => {
        setText(e.target.value);
        const v = Number(e.target.value);
        if (e.target.value !== "" && Number.isFinite(v)) onChange(v);
      }}
      onBlur={() => {
        if (text === "") onChange(min !== undefined && min > 0 ? min : 0);
      }}
    />
  );
}

// Gold is kept in hundredths of an ounce (rew_gold, cost_gold); shown in G.
export function Gold({ value, onChange }: { value: number | undefined; onChange: (v: number) => void }) {
  const [text, setText] = useState(((value || 0) / 100).toFixed(2));
  useEffect(() => setText(((value || 0) / 100).toFixed(2)), [value]);
  return (
    <span className="inline">
      <input
        type="number"
        step="0.01"
        min={0}
        style={{ width: 90 }}
        value={text}
        onChange={(e) => {
          setText(e.target.value);
          const v = Number(e.target.value);
          if (Number.isFinite(v)) onChange(Math.round(v * 100));
        }}
      />
      <span className="muted">G</span>
    </span>
  );
}

export function Check({ value, onChange, label }: { value: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <label className="check">
      <input type="checkbox" checked={value} onChange={(e) => onChange(e.target.checked)} /> {label}
    </label>
  );
}

export function Area({ value, onChange, rows = 4 }: { value: string; onChange: (v: string) => void; rows?: number }) {
  return <textarea rows={rows} value={value} onChange={(e) => onChange(e.target.value)} />;
}

export function Section({ title, children, open = true, note }: { title: string; children: React.ReactNode; open?: boolean; note?: string }) {
  return (
    <details className="section" open={open}>
      <summary>
        {title}
        {note ? <span className="muted"> · {note}</span> : null}
      </summary>
      <div className="section-body">{children}</div>
    </details>
  );
}

// JSON of some keys, applied on demand: for whatever has no widget of its own.
export function JsonBox({ value, onApply, rows = 6 }: { value: unknown; onApply: (v: unknown) => void; rows?: number }) {
  const shown = JSON.stringify(value, null, 1);
  const [text, setText] = useState(shown);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    setText(shown);
    setErr(null);
  }, [shown]);
  return (
    <div className="jsonbox">
      <textarea rows={rows} value={text} spellCheck={false} onChange={(e) => setText(e.target.value)} />
      <div className="inline">
        <button
          disabled={text === shown}
          onClick={() => {
            try {
              onApply(JSON.parse(text));
              setErr(null);
            } catch (e) {
              setErr(String(e));
            }
          }}
        >
          Применить
        </button>
        {text !== shown && (
          <button className="ghost" onClick={() => setText(shown)}>
            Отменить
          </button>
        )}
        {err && <span className="err-text">{err}</span>}
      </div>
    </div>
  );
}
