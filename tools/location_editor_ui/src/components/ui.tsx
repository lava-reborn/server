import { useEffect, useState, type ReactNode } from "react";

// Small pieces every screen uses: a dialog, the messages in the corner and
// a question with two answers (in the page itself, no browser dialogs).

export function Modal(props: {
  title: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  wide?: boolean;
  full?: boolean;
}) {
  useEffect(() => {
    const k = (e: KeyboardEvent) => {
      if (e.key === "Escape") props.onClose();
    };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [props.onClose]);
  return (
    <div className="overlay" onMouseDown={(e) => e.target === e.currentTarget && props.onClose()}>
      <div className={`modal${props.wide ? " wide" : ""}${props.full ? " full" : ""}`} role="dialog" aria-label={props.title}>
        <div className="modal-head">
          <h2>{props.title}</h2>
          <button className="x" onClick={props.onClose} aria-label="Закрыть">
            ✕
          </button>
        </div>
        <div className="modal-body">{props.children}</div>
        {props.footer && <div className="modal-foot">{props.footer}</div>}
      </div>
    </div>
  );
}

// --- the messages in the corner -----------------------------------------------------
export type ToastKind = "ok" | "err" | "info";
interface Toast {
  id: number;
  kind: ToastKind;
  text: string;
}
let toasts: Toast[] = [];
let seq = 0;
const subs = new Set<(t: Toast[]) => void>();
export function toast(kind: ToastKind, text: string, ms = kind === "err" ? 9000 : 4500) {
  const t = { id: ++seq, kind, text };
  toasts = [...toasts, t].slice(-5);
  subs.forEach((f) => f(toasts));
  window.setTimeout(() => {
    toasts = toasts.filter((x) => x.id !== t.id);
    subs.forEach((f) => f(toasts));
  }, ms);
}
export function Toasts() {
  const [list, setList] = useState<Toast[]>(toasts);
  useEffect(() => {
    subs.add(setList);
    return () => {
      subs.delete(setList);
    };
  }, []);
  return (
    <div className="toasts" aria-live="polite">
      {list.map((t) => (
        <div key={t.id} className={`toast ${t.kind}`} onClick={() => setList(list.filter((x) => x.id !== t.id))}>
          {t.text}
        </div>
      ))}
    </div>
  );
}

// --- a question ------------------------------------------------------------------
interface Ask {
  title: string;
  text: ReactNode;
  ok: string;
  cancel?: string;
  danger?: boolean;
  resolve: (v: boolean) => void;
}
let asking: Ask | null = null;
const askSubs = new Set<(a: Ask | null) => void>();
export function ask(o: Omit<Ask, "resolve">): Promise<boolean> {
  return new Promise((resolve) => {
    asking = { ...o, resolve };
    askSubs.forEach((f) => f(asking));
  });
}
export function AskHost() {
  const [a, setA] = useState<Ask | null>(asking);
  useEffect(() => {
    askSubs.add(setA);
    return () => {
      askSubs.delete(setA);
    };
  }, []);
  if (!a) return null;
  const done = (v: boolean) => {
    asking = null;
    setA(null);
    a.resolve(v);
  };
  return (
    <Modal
      title={a.title}
      onClose={() => done(false)}
      footer={
        <>
          <button onClick={() => done(false)}>{a.cancel || "Отмена"}</button>
          <button className={a.danger ? "danger" : "primary"} onClick={() => done(true)} autoFocus>
            {a.ok}
          </button>
        </>
      }
    >
      <div className="ask-text">{a.text}</div>
    </Modal>
  );
}

export function Field(props: { label: string; hint?: ReactNode; children: ReactNode }) {
  return (
    <label className="field-row">
      <span className="field-label">{props.label}</span>
      {props.children}
      {props.hint && <span className="hint">{props.hint}</span>}
    </label>
  );
}

export function Spinner() {
  return <span className="spinner" aria-hidden />;
}
