import { useEffect, useRef, useState } from "react";
import { api, ApiError, errText } from "../api";
import { Field, Spinner, ask, toast } from "../components/ui";
import { HEX, key, offsetPx, pxCell } from "../hex";
import { forgetPalettes } from "../store";
import type { Cell, ObjectEntry } from "../types";

// «Мои объекты»: the owner's own pictures for locations
// (client/objects/<id>/ and manifest.json). One picture or several (an
// animation, frames a second), the pixel that stands on the cell («ноги»),
// the cells that block walking (the footprint, written as walls f) and the
// depth line (front: whoever stands below it is drawn over the object).

type Mode = "anchor" | "footprint" | "front";

interface Form {
  id: string | null;
  title: string;
  fps: number;
  note: string;
  frames: string[];
  framesChanged: boolean;
  anchor: Cell | null;
  front: Cell[];
  footprint: Cell[];
  usedIn: number[];
}

const blank = (): Form => ({
  id: null,
  title: "",
  fps: 4,
  note: "",
  frames: [],
  framesChanged: false,
  anchor: null,
  front: [[0, 0]],
  footprint: [[0, 0]],
  usedIn: [],
});

const fromEntry = (id: string, e: ObjectEntry): Form => ({
  id,
  title: e.title,
  fps: e.fps || 4,
  note: e.note || "",
  frames: e.pictures,
  framesChanged: false,
  anchor: e.anchor || null,
  front: e.front || [[0, 0]],
  footprint: e.footprint || [],
  usedIn: e.used_in,
});

const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);

export default function Objects(props: { onBack: () => void }) {
  const [objects, setObjects] = useState<Record<string, ObjectEntry> | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [form, setForm] = useState<Form>(blank());
  const [orig, setOrig] = useState<Form | null>(null);
  const [size, setSize] = useState<[number, number] | null>(null);
  const [mode, setMode] = useState<Mode>("anchor");
  const [zoom, setZoom] = useState(2);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);
  const [sizes, setSizes] = useState<string | null>(null);

  const load = () =>
    api
      .objects()
      .then((o) => {
        setObjects(o);
        setErr(null);
        return o;
      })
      .catch((e) => {
        setErr(errText(e));
        return null;
      });
  useEffect(() => {
    load();
  }, []);

  // the picture's size, from its first frame; frames of other sizes are named
  useEffect(() => {
    setSize(null);
    setSizes(null);
    if (!form.frames.length) return;
    let live = true;
    Promise.all(
      form.frames.map(
        (src) =>
          new Promise<[number, number]>((res) => {
            const im = new Image();
            im.onload = () => res([im.naturalWidth, im.naturalHeight]);
            im.onerror = () => res([0, 0]);
            im.src = src;
          }),
      ),
    ).then((dims) => {
      if (!live) return;
      setSize(dims[0]);
      const set = [...new Set(dims.map((d) => d.join("×")))];
      setSizes(set.length > 1 ? `кадры разного размера: ${set.join(", ")} — нужен один` : null);
      // the feet: the bottom middle for a new picture; an object's own feet
      // stay when its pictures are replaced (they cannot change while a
      // location places it), unless they fall off a smaller picture of an
      // object that stands nowhere
      setForm((f) => {
        const [w, h] = dims[0];
        const off = f.anchor && (f.anchor[0] > w || f.anchor[1] > h);
        if (f.anchor && !(off && !f.usedIn.length)) return f;
        return { ...f, anchor: [Math.floor(w / 2), h - 1] };
      });
    });
    return () => {
      live = false;
    };
  }, [form.frames]);

  // whether the form holds what is not saved: an object's changed fields,
  // or anything at all of a new one
  const unsaved = () => {
    if (!orig) return !!(form.title.trim() || form.frames.length || form.note.trim());
    // a background has no feet: the ones the picture's size gave it are no edit
    const fields = (f: Form) => ({ ...f, frames: [], anchor: orig.anchor === null ? null : f.anchor });
    return form.framesChanged || !same(fields(orig), fields(form));
  };
  const leave = async () => {
    if (!unsaved() || busy) return !busy;
    return ask({
      title: "Уйти без сохранения?",
      text: form.id ? `Правки объекта «${form.title || form.id}» не сохранены и пропадут.` : "Новый объект не сохранён и пропадёт.",
      ok: "Уйти",
      cancel: "Остаться",
      danger: true,
    });
  };
  const goBack = async () => {
    if (await leave()) props.onBack();
  };
  const choose = async (id: string | null) => {
    if (id === form.id && id !== null) return;
    if (await leave()) pick(id);
  };

  const pick = (id: string | null) => {
    setMsg(null);
    setMode("anchor");
    if (id && objects?.[id]) {
      const f = fromEntry(id, objects[id]);
      setForm(f);
      setOrig(f);
    } else {
      setForm(blank());
      setOrig(null);
    }
  };

  const onFiles = async (files: FileList | null) => {
    if (!files || !files.length) return;
    const list = [...files].sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true }));
    const urls = await Promise.all(
      list.map(
        (f) =>
          new Promise<string>((res, rej) => {
            const r = new FileReader();
            r.onload = () => res(String(r.result));
            r.onerror = () => rej(r.error);
            r.readAsDataURL(f);
          }),
      ),
    );
    setForm((f) => ({
      ...f,
      frames: urls,
      framesChanged: true,
      // a new object's feet come from its picture; an object's own stay
      anchor: f.id ? f.anchor : null,
      title: f.title || list[0].name.replace(/\.[^.]+$/, ""),
    }));
  };

  const toggle = (field: "front" | "footprint", c: Cell) => {
    setForm((f) => {
      const k = key(c[0], c[1]);
      const have = f[field].some((x) => key(x[0], x[1]) === k);
      return { ...f, [field]: have ? f[field].filter((x) => key(x[0], x[1]) !== k) : [...f[field], c] };
    });
  };

  const save = async () => {
    setBusy(true);
    setMsg(null);
    try {
      let id: string;
      if (!form.id) {
        const r = await api.objectNew({
          title: form.title.trim(),
          frames: form.frames,
          fps: form.frames.length > 1 ? form.fps : null,
          anchor: form.anchor,
          front: form.front,
          footprint: form.footprint,
          note: form.note || null,
        });
        id = r.id;
      } else {
        const body: Record<string, unknown> = { id: form.id, title: form.title.trim(), note: form.note || null };
        body.fps = form.frames.length > 1 ? form.fps : null;
        if (form.framesChanged) body.frames = form.frames;
        if (!orig || !same(orig.anchor, form.anchor)) body.anchor = form.anchor;
        if (!orig || !same(orig.front, form.front)) body.front = form.front;
        if (!orig || !same(orig.footprint, form.footprint)) body.footprint = form.footprint;
        id = (await api.objectUpdate(body)).id;
      }
      forgetPalettes();
      const o = await load();
      if (o && o[id]) {
        const f = fromEntry(id, o[id]);
        setForm(f);
        setOrig(f);
      }
      setMsg({ kind: "ok", text: `Сохранено: client/objects/${id}/ и строка manifest.json. В редакторе он во вкладке «Мои».` });
      toast("ok", `Объект ${id} сохранён`);
    } catch (e) {
      const used = e instanceof ApiError && e.status === 409;
      setMsg({ kind: "err", text: used ? `${errText(e)}.` : `Не сохранено: ${errText(e)}` });
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    if (!form.id) return;
    const yes = await ask({
      title: `Удалить ${form.title}?`,
      text: `Картинки client/objects/${form.id}/ и его строка manifest.json будут удалены.`,
      ok: "Удалить",
      danger: true,
    });
    if (!yes) return;
    setBusy(true);
    try {
      await api.objectDelete(form.id);
      forgetPalettes();
      await load();
      pick(null);
      toast("ok", "Объект удалён");
    } catch (e) {
      setMsg({ kind: "err", text: errText(e) });
    } finally {
      setBusy(false);
    }
  };

  const list = objects ? Object.entries(objects) : [];
  const locked = !!form.id && form.usedIn.length > 0;
  const canSave = !busy && form.title.trim() && form.frames.length && form.anchor && !sizes;

  return (
    <div className="screen objects-screen">
      <header className="topbar">
        <button className="ghost" onClick={goBack}>
          ← Локации
        </button>
        <span className="brand">Мои объекты</span>
        <span className="muted small">свои картинки для локаций: client/objects</span>
        <span className="grow" />
        <button onClick={() => choose(null)}>Новый объект</button>
      </header>
      <div className="objects-body">
        <aside className="obj-list">
          {err && <p className="err-text pad">{err}</p>}
          {!objects && !err && (
            <p className="muted pad">
              <Spinner /> читаю…
            </p>
          )}
          {objects && !list.length && <p className="muted pad">Своих объектов пока нет.</p>}
          {list.map(([id, e]) => (
            <button key={id} className={`obj-row${form.id === id ? " on" : ""}`} onClick={() => choose(id)}>
              {e.pictures[0] ? <img src={e.pictures[0]} alt="" /> : <span className="noimg">?</span>}
              <span className="mob-text">
                <span className="ellipsis">{e.title}</span>
                <span className="small muted ellipsis mono">{id}</span>
                <span className="small muted">
                  {e.frames.length > 1 ? `анимация: ${e.frames.length} кадров, ${e.fps}/с` : "картинка"}
                  {e.used_in.length ? ` · стоит в ${e.used_in.join(", ")}` : ""}
                </span>
                {e.problem && <span className="small err-text">{e.problem}</span>}
              </span>
            </button>
          ))}
        </aside>
        <main className="obj-edit">
          <div className="obj-form">
            <h2>{form.id ? `${form.title} · ${form.id}` : "Новый объект"}</h2>
            <Field label="Название" hint="Его видно в палитре; id сделается из него сам">
              <input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="Например: Бочка" />
            </Field>
            <div className="field-row">
              <span className="field-label">Картинки</span>
              <label className="file-btn">
                <input
                  type="file"
                  accept="image/png,image/jpeg"
                  multiple
                  aria-label="Картинки объекта"
                  onChange={(e) => {
                    onFiles(e.target.files);
                    e.target.value = "";
                  }}
                />
                {form.frames.length ? "Заменить картинки…" : "Выбрать картинки…"}
              </label>
              <span className="hint">
                PNG (без чересстрочности) или обычный JPEG (не progressive и не повёрнутый записью в EXIF, как фото с телефона),
                до 2880 точек на сторону. Несколько картинок одного размера — анимация, по порядку имён файлов. Сборка игры
                распаковывает каждую точку PNG: у объекта их до 24 миллионов (например, шесть кадров 2000 × 2000), у всех объектов
                вместе — до 64 миллионов.
              </span>
            </div>
            {form.frames.length > 0 && (
              <div className="frames">
                {form.frames.map((f, i) => (
                  <figure key={i}>
                    <img src={f} alt={`кадр ${i + 1}`} />
                    <figcaption className="small muted">{i + 1}</figcaption>
                  </figure>
                ))}
                {size && <span className="small muted">{size.join(" × ")} точек</span>}
              </div>
            )}
            {sizes && <p className="err-text">{sizes}</p>}
            {form.frames.length > 1 && (
              <Field label="Кадров в секунду" hint={`В игре кадр держится ${Math.max(1, Math.round(25 / form.fps))} из 25 кадров секунды`}>
                <input type="number" min={1} max={25} value={form.fps} onChange={(e) => setForm({ ...form, fps: Math.max(1, Math.min(25, Number(e.target.value) || 1)) })} />
              </Field>
            )}
            <Field label="Заметка" hint="Для людей; игра её не читает">
              <input value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} />
            </Field>
            {locked && (
              <p className="small warn-text">
                Объект стоит в локациях {form.usedIn.join(", ")}: ноги, след и линию глубины можно менять только у объекта, который
                нигде не стоит. Название, заметку и скорость — можно.
              </p>
            )}
            <div className="row actions">
              <button className="primary" disabled={!canSave} onClick={save}>
                {busy ? "Сохраняю…" : form.id ? "Сохранить" : "Сохранить объект"}
              </button>
              {form.id && (
                <button className="danger" disabled={busy} onClick={remove}>
                  Удалить
                </button>
              )}
              {form.id && orig && !same(orig, form) && <button onClick={() => pick(form.id)}>Отменить правки</button>}
            </div>
            {msg && <p className={msg.kind === "ok" ? "ok-text" : "err-text"}>{msg.text}</p>}
            {form.frames.length > 0 && (
              <div className="anim-box">
                <h4>Как он играет</h4>
                <Animation frames={form.frames} fps={form.frames.length > 1 ? form.fps : 0} />
              </div>
            )}
          </div>
          <div className="obj-stage-wrap">
            {form.frames.length && size && form.anchor ? (
              <>
                <div className="canvas-tools">
                  <div className="seg">
                    <button className={mode === "anchor" ? "on" : ""} onClick={() => setMode("anchor")} disabled={locked}>
                      Ноги (якорь)
                    </button>
                    <button className={mode === "footprint" ? "on" : ""} onClick={() => setMode("footprint")} disabled={locked}>
                      След: стены
                    </button>
                    <button className={mode === "front" ? "on" : ""} onClick={() => setMode("front")} disabled={locked}>
                      Линия глубины
                    </button>
                  </div>
                  <span className="sep" />
                  {[1, 2, 3].map((z) => (
                    <button key={z} className={zoom === z ? "on" : ""} onClick={() => setZoom(z)}>
                      ×{z}
                    </button>
                  ))}
                </div>
                <p className="hint pad-x">
                  {mode === "anchor" &&
                    "Щёлкните по точке картинки, которая стоит на земле: она встанет в центр клетки. Обычно это низ посередине."}
                  {mode === "footprint" && "Щёлкните по клеткам, через которые нельзя пройти: они станут стенами f под объектом."}
                  {mode === "front" &&
                    "Линия глубины: клетки, ниже которых стоящий рисуется поверх объекта. Для узкого объекта — одна клетка под ногами; для широкого — его нижний край."}
                </p>
                <Stage
                  frame={form.frames[0]}
                  size={size}
                  anchor={form.anchor}
                  footprint={form.footprint}
                  front={form.front}
                  zoom={zoom}
                  onClick={(px, cell) => {
                    if (locked) return;
                    if (mode === "anchor") {
                      setForm({ ...form, anchor: [Math.max(0, Math.min(size[0] - 1, Math.round(px[0]))), Math.max(0, Math.min(size[1] - 1, Math.round(px[1])))] });
                    } else toggle(mode, cell);
                  }}
                />
                <p className="small muted pad-x">
                  Ноги: {form.anchor[0]}, {form.anchor[1]} · след: {form.footprint.length} клет. · линия глубины: {form.front.length} клет.
                  <span className="legend">
                    {" "}
                    <i className="sw wall" /> след <i className="sw front" /> линия глубины <i className="sw anchor" /> клетка ног
                  </span>
                </p>
              </>
            ) : (
              <div className="empty-stage muted">
                {form.frames.length ? <Spinner /> : "Выберите картинку: здесь появится она с сеткой клеток под ней."}
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}

function Animation({ frames, fps }: { frames: string[]; fps: number }) {
  const [i, setI] = useState(0);
  useEffect(() => {
    setI(0);
    if (!fps || frames.length < 2) return;
    // as the game plays it: each picture held round(25 / fps) frames of 25
    const hold = Math.max(1, Math.round(25 / fps));
    const t = window.setInterval(() => setI((n) => (n + 1) % frames.length), (1000 / 25) * hold);
    return () => window.clearInterval(t);
  }, [frames, fps]);
  return (
    <div className="anim">
      <img src={frames[Math.min(i, frames.length - 1)]} alt="предпросмотр" />
      {frames.length > 1 && (
        <span className="small muted">
          кадр {i + 1} из {frames.length}
        </span>
      )}
    </div>
  );
}

// The picture over a patch of the location grid: the anchor cell's centre
// at the anchor pixel, cells as offsets from it (even row).
function Stage(props: {
  frame: string;
  size: [number, number];
  anchor: Cell;
  footprint: Cell[];
  front: Cell[];
  zoom: number;
  onClick: (px: [number, number], cell: Cell) => void;
}) {
  const ref = useRef<HTMLCanvasElement>(null);
  const [img, setImg] = useState<HTMLImageElement | null>(null);
  useEffect(() => {
    const im = new Image();
    im.onload = () => setImg(im);
    im.src = props.frame;
  }, [props.frame]);

  const [w, h] = props.size;
  const [ax, ay] = props.anchor;
  const dxMin = Math.floor((-ax - 20) / 40) - 1;
  const dxMax = Math.ceil((w - ax + 20) / 40) + 1;
  const dyMin = Math.floor((-ay - 10) / 15) - 1;
  const dyMax = Math.ceil((h - ay + 10) / 15) + 3;
  const minX = Math.min(0, ax + 40 * dxMin - 20);
  const maxX = Math.max(w, ax + 40 * dxMax + 40);
  const minY = Math.min(0, ay + 15 * dyMin - 10);
  const maxY = Math.max(h, ay + 15 * dyMax + 10);
  const s = props.zoom;
  const cw = Math.ceil((maxX - minX) * s);
  const ch = Math.ceil((maxY - minY) * s);

  useEffect(() => {
    const c = ref.current;
    if (!c) return;
    const dpr = window.devicePixelRatio || 1;
    c.width = cw * dpr;
    c.height = ch * dpr;
    c.style.width = `${cw}px`;
    c.style.height = `${ch}px`;
    const ctx = c.getContext("2d")!;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    // a checkerboard shows what is transparent
    for (let y = 0; y < ch; y += 12)
      for (let x = 0; x < cw; x += 12) {
        ctx.fillStyle = ((x + y) / 12) % 2 ? "#2a241f" : "#1f1a16";
        ctx.fillRect(x, y, 12, 12);
      }
    ctx.setTransform(dpr * s, 0, 0, dpr * s, -minX * s * dpr, -minY * s * dpr);
    ctx.imageSmoothingEnabled = s < 1;
    if (img) ctx.drawImage(img, 0, 0);
    ctx.strokeStyle = "rgba(239,232,217,0.35)";
    ctx.lineWidth = 1 / s;
    ctx.strokeRect(0, 0, w, h);
    const hex = (dx: number, dy: number) => {
      const [ox, oy] = offsetPx(dx, dy);
      const cx = ax + ox;
      const cy = ay + oy;
      ctx.beginPath();
      ctx.moveTo(cx + HEX[0][0], cy + HEX[0][1]);
      for (let i = 1; i < 6; i++) ctx.lineTo(cx + HEX[i][0], cy + HEX[i][1]);
      ctx.closePath();
    };
    for (let dy = dyMin; dy <= dyMax; dy++)
      for (let dx = dxMin; dx <= dxMax; dx++) {
        hex(dx, dy);
        ctx.strokeStyle = "rgba(255,255,255,0.18)";
        ctx.lineWidth = 1 / s;
        ctx.stroke();
      }
    for (const [dx, dy] of props.footprint) {
      hex(dx, dy);
      ctx.fillStyle = "rgba(226,64,48,0.5)";
      ctx.fill();
    }
    for (const [dx, dy] of props.front) {
      hex(dx, dy);
      ctx.strokeStyle = "#f0d040";
      ctx.lineWidth = 3 / s;
      ctx.stroke();
    }
    hex(0, 0);
    ctx.strokeStyle = "#d9a441";
    ctx.lineWidth = 2 / s;
    ctx.setLineDash([4 / s, 3 / s]);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.strokeStyle = "#7fe0ff";
    ctx.lineWidth = 1.5 / s;
    ctx.beginPath();
    ctx.moveTo(ax - 8, ay + 0.5);
    ctx.lineTo(ax + 9, ay + 0.5);
    ctx.moveTo(ax + 0.5, ay - 8);
    ctx.lineTo(ax + 0.5, ay + 9);
    ctx.stroke();
  }, [img, w, h, ax, ay, props.footprint, props.front, s, cw, ch, minX, minY, dxMin, dxMax, dyMin, dyMax]);

  return (
    <div className="obj-stage">
      <canvas
        ref={ref}
        aria-label="Картинка объекта с сеткой клеток"
        onClick={(e) => {
          const r = e.currentTarget.getBoundingClientRect();
          const x = (e.clientX - r.left) / s + minX;
          const y = (e.clientY - r.top) / s + minY;
          props.onClick([x, y], pxCell(x - ax, y - ay));
        }}
      />
    </div>
  );
}
