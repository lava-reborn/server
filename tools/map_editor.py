#!/usr/bin/env python3
"""Launch the boundary draft editor over the current in-game map.

    python3 tools/map_editor.py

The editor opens on 127.0.0.1:8090 and keeps its editable copy under
outputs/boundary-editor. Water, walls and rocks retain separate types;
unmarked land is open. The generated shore and rock layout is a preview.
Saving writes the working draft, never the game terrain or bindings.

Legacy rendering and validation helpers remain available for existing tools.
"""
import io
import hashlib
import threading
import json
import os
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "server"))
os.environ.setdefault(
    "LAVA_RES", "/mnt/c/Users/gmkrt/OneDrive/Desktop/LAVA/res")

import world  # noqa: E402

PORT = int(os.environ.get("LAVA_EDITOR_PORT", "8090"))
PX = 6                      # pixels per cell in the rendered map
TILE = 32                   # cells per map tile
VERIFIED = os.path.join(ROOT, "data", "terrain_verified.json")
EDITOR_SEED = os.path.join(ROOT, "data", "boundary_editor_draft.json")
CACHE = os.path.join(ROOT, "data", "map_editor_base.png")
PREPARED_TILES = None
SAVE_LOCK = threading.Lock()


def render():
    """The client's own map tiles, stitched over the world rectangle."""
    import map_cells
    from PIL import Image
    read = map_cells.reader(world.RES)
    served = map_cells.Served(world.RES, prepared_tiles=PREPARED_TILES)
    source_files = sorted(os.listdir(os.path.join(world.RES, "globalmap", "full")))
    signature = hashlib.sha256()
    for name in source_files:
        if name.endswith(".jpg"):
            signature.update(name.encode())
            signature.update(read("globalmap/full/" + name) or b"")
    for path in (map_cells.PATH, map_cells.RETIRED, map_cells.__file__):
        with open(path, "rb") as source:
            signature.update(source.read())
    stamp = signature.hexdigest()
    try:
        with open(CACHE + ".sha256", encoding="ascii") as fh:
            if os.path.isfile(CACHE) and fh.read() == stamp:
                return
    except OSError:
        pass
    gx0, gx1 = world.MAP_X
    gy0, gy1 = world.MAP_Y
    root = os.path.join(world.RES, "globalmap", "full")
    tx0, tx1 = gx0 // TILE, gx1 // TILE
    ty0, ty1 = gy0 // TILE, gy1 // TILE
    print("собираю карту из тайлов клиента...")
    big = Image.new("RGB", ((tx1 - tx0 + 1) * TILE * 8,
                            (ty1 - ty0 + 1) * TILE * 8), (20, 18, 15))
    for ty in range(ty0, ty1 + 1):
        for tx in range(tx0, tx1 + 1):
            p = os.path.join(root, "%d.jpg" % (ty * 256 + tx))
            if os.path.exists(p):
                rel = "globalmap/full/%d.jpg" % (ty * 256 + tx)
                blob = served.get(rel) or read(rel)
                with Image.open(io.BytesIO(blob)) as tile:
                    big.paste(tile.convert("RGB"),
                              ((tx - tx0) * TILE * 8, (ty - ty0) * TILE * 8))
    left, top = (gx0 - tx0 * TILE) * 8, (gy0 - ty0 * TILE) * 8
    crop = big.crop((left, top, left + (gx1 - gx0 + 1) * 8,
                     top + (gy1 - gy0 + 1) * 8))
    if PX != 8:
        crop = crop.resize(((gx1 - gx0 + 1) * PX, (gy1 - gy0 + 1) * PX),
                           Image.LANCZOS)
    crop.save(CACHE)
    with open(CACHE + ".sha256", "w", encoding="ascii") as fh:
        fh.write(stamp)
    print("карта готова: %s (%dx%d)" % (CACHE, crop.width, crop.height))


def read_document():
    try:
        with open(VERIFIED, "rb") as fh:
            raw = fh.read()
    except FileNotFoundError:
        raw = b"{}"
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def normalise(doc):
    """Keep terrain kinds separate; every water/rock cell is also blocked."""
    def cells(name):
        rows = doc.get(name, [])
        if not isinstance(rows, list):
            raise ValueError("Некорректный слой: " + name)
        result = set()
        for key in rows:
            if not isinstance(key, str):
                raise ValueError("Некорректные координаты")
            parts = key.split(",")
            if len(parts) != 2:
                raise ValueError("Некорректные координаты: " + key)
            x, y = map(int, parts)
            if not world.in_map(x, y):
                raise ValueError("Клетка вне карты: " + key)
            result.add("%d,%d" % (x, y))
        return result
    water, rocks = cells("water"), cells("rocks")
    blocked, opened = cells("blocked") | water | rocks, cells("passable")
    if water & rocks or blocked & opened:
        raise ValueError("У клетки указаны несовместимые типы")
    opacity = doc.get("opacity", 70)
    if isinstance(opacity, bool) or not isinstance(opacity, (int, float)) or not 0 <= opacity <= 100:
        raise ValueError("Непрозрачность должна быть от 0 до 100%")
    return dict(blocked=sorted(blocked), passable=sorted(opened),
                water=sorted(water), rocks=sorted(rocks), opacity=opacity)


def save_document(doc):
    with SAVE_LOCK:
        old, revision = read_document()
        if doc.get("revision") != revision:
            return 409, {"error": "Черновик уже изменён в другой вкладке. Сохранение остановлено; ваши отметки остались на экране."}
        if not all(key in doc for key in ("blocked", "passable", "water", "rocks")):
            raise ValueError("Обновите страницу редактора перед сохранением")
        layers = normalise(doc)
        old.update(layers)
        raw = (json.dumps(old, ensure_ascii=False, indent=1, sort_keys=True) + "\n").encode("utf-8")
        temporary = VERIFIED + ".tmp"
        try:
            with open(temporary, "wb") as fh:
                fh.write(raw)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(temporary, VERIFIED)
        finally:
            if os.path.exists(temporary):
                os.remove(temporary)
        return 200, dict(saved=True, revision=hashlib.sha256(raw).hexdigest(),
                         **{key: len(layers[key]) for key in ("blocked", "passable", "water", "rocks")})


def state():
    """Everything the page needs to draw itself."""
    gx0, gx1 = world.MAP_X
    gy0, gy1 = world.MAP_Y
    doc, revision = read_document()
    layers = normalise(doc)
    # What the photograph says, so the hand-drawn layer can be seen against
    # it rather than in the dark.
    (rx0, ry0, rx1, ry1), rows = world.terrain()
    photo = []
    for gy in range(gy0, gy1 + 1):
        line = []
        for gx in range(gx0, gx1 + 1):
            if rx0 <= gx <= rx1 and ry0 <= gy <= ry1:
                line.append(rows[gy - ry0][gx - rx0])
            else:
                line.append(".")
        photo.append("".join(line))
    return {
        "x0": gx0, "y0": gy0, "x1": gx1, "y1": gy1, "px": PX,
        **layers, "revision": revision,
        "photo": photo,
        "settlements": ["%d,%d" % c for c in world.settlements()],
        "repairs": ["%d,%d" % c for c in world.terrain_repairs()],
    }


def reachability(blocked, passable):
    """How much of the world is still walkable, once the drawing is applied.

    The answer that matters is settlements: a wall that seals one off is a
    wall in the wrong place, and the page says so before the file is used.
    """
    over = {}
    for key in blocked:
        gx, gy = (int(v) for v in key.split(","))
        over[(gx, gy)] = False
    for key in passable:
        gx, gy = (int(v) for v in key.split(","))
        over[(gx, gy)] = True

    def open_cell(gx, gy):
        if not world.in_map(gx, gy):
            return False
        fixed = over.get((gx, gy))
        if fixed is not None:
            return fixed
        # Erasing an old manual wall must restore the photo/exit baseline,
        # not consult the still-running game's previous manual overrides.
        if world.eden_map.inside_cell(gx, gy):
            return False
        return (gx, gy) in world.terrain_repairs() or not world.water(gx, gy)

    cells = set(world.settlements())
    start = (6268, 1819)
    if not open_cell(*start):
        return {"ok": False, "why": "стартовая клетка закрыта"}
    seen = {start}
    stack = [start]
    while stack:
        x, y = stack.pop()
        for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if n in seen or not open_cell(*n):
                continue
            seen.add(n)
            stack.append(n)
    cut = sorted(c for c in cells if c not in seen)
    return {"ok": not cut, "cells": len(seen), "settlements": len(cells),
            "cut": ["%d,%d" % c for c in cut[:40]], "cut_total": len(cut)}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, body, ctype="application/json; charset=utf-8", code=200):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/map.png"):
            with open(CACHE, "rb") as fh:
                self._send(fh.read(), "image/png")
        elif self.path.startswith("/state"):
            self._send(json.dumps(state()))
        else:
            self._send(PAGE, "text/html; charset=utf-8")

    def do_POST(self):
        if self.path not in ("/save", "/check"):
            self._send(json.dumps({"error": "Неизвестная команда"}), code=404)
            return
        try:
            if self.headers.get_content_type() != "application/json":
                raise ValueError("Обновите страницу редактора перед сохранением")
            n = int(self.headers.get("Content-Length") or 0)
            if not 0 < n <= 16 * 1024 * 1024:
                raise ValueError("Некорректный размер разметки")
            doc = json.loads(self.rfile.read(n).decode("utf-8"))
            if not isinstance(doc, dict):
                raise ValueError("Некорректная разметка")
            if self.path == "/check":
                layers = normalise(doc)
                self._send(json.dumps(reachability(layers["blocked"], layers["passable"])))
            else:
                code, result = save_document(doc)
                self._send(json.dumps(result, ensure_ascii=False), code=code)
        except (ValueError, TypeError, UnicodeError) as error:
            self._send(json.dumps({"error": str(error)}, ensure_ascii=False), code=400)
        except OSError:
            self._send(json.dumps({"error": "Не удалось записать черновик. Отметки на экране сохранены."}, ensure_ascii=False), code=500)


PAGE = r"""<!doctype html><html lang=ru><meta charset=utf-8>
<title>Границы карты — LAVA</title>
<meta name=viewport content="width=device-width,initial-scale=1">
<style>
 html,body{margin:0;height:100%;background:#15130f;color:#e1d8c4;font:14px/1.4 system-ui,sans-serif}
 body{display:flex;flex-direction:column}
 #bar{flex:none;display:flex;flex-wrap:wrap;align-items:center;gap:8px 12px;padding:10px 14px;background:#211e17;border-bottom:1px solid #514735}
 #wrap{flex:1;min-height:0;overflow:auto}
 #stage{position:relative;transform-origin:0 0}
 canvas{position:absolute;top:0;left:0;image-rendering:pixelated;touch-action:none}
 #map{display:block}
 button{background:#605033;color:#fff7e5;border:1px solid #8d7958;border-radius:3px;padding:5px 9px;cursor:pointer}
 button[aria-pressed=true]{outline:2px solid #fff0bc;outline-offset:1px}
 button:disabled{opacity:.5;cursor:wait}
 #wall{background:#a52a23} #water{background:#285e99} #open{background:#2d703c} #rocks{background:#854335}
 label{display:flex;align-items:center;gap:5px;white-space:nowrap}
 input[type=range]{width:90px}
 #msg{flex-basis:100%;color:#c9bc9f} output{min-width:28px}
</style>
<div id=bar>
 <b>Границы</b>
 <button id=water type=button aria-pressed=false>Вода</button>
 <button id=wall type=button aria-pressed=true>Стена</button>
 <button id=open type=button aria-pressed=false>Проход</button>
 <button id=rocks type=button aria-pressed=false>Скалы</button>
 <button id=erase type=button aria-pressed=false>Стереть</button>
 <label>Кисть <input type=range id=size min=1 max=15 step=2 value=3><output id=sz>3</output></label>
 <label>Непрозрачность <input type=range id=opacity min=0 max=100 value=70><output id=alpha>70%</output></label>
 <label title="Только отображение исходного слоя. Галочка не меняет сохранение черновика."><input type=checkbox id=showphoto checked> Показать авторазметку</label>
 <label><input type=checkbox id=showplaces checked> Локации</label>
 <button id=check type=button>Проверить</button>
 <button id=save type=button>Сохранить</button>
 <span id=msg role=status aria-live=polite>Загрузка…</span>
</div>
<div id=wrap><div id=stage><img id=map draggable=false alt="Актуальная глобальная карта игры"><canvas id=over></canvas></div></div>
<script>
let S=null, blocked=new Set(), passable=new Set(), water=new Set(), rocks=new Set();
let mode="wall",brush=3,zoom=1,painting=false,last=null,dirty=false,editVersion=0;
const stage=document.getElementById("stage"),img=document.getElementById("map");
const over=document.getElementById("over"),ctx=over.getContext("2d"),msg=document.getElementById("msg");
const modes=["water","wall","open","rocks","erase"];
const WATER_COLOR="rgba(60,120,200,.55)";
let photoLayer=null;
const groups=()=>[blocked,passable,water,rocks];
function key(x,y){return x+","+y}
function cellAt(ev){const r=img.getBoundingClientRect();return [S.x0+Math.floor((ev.clientX-r.left)/zoom/S.px),S.y0+Math.floor((ev.clientY-r.top)/zoom/S.px)];}
function draw(){
 if(!S)return;
 ctx.clearRect(0,0,over.width,over.height);
 ctx.globalAlpha=+document.getElementById("opacity").value/100;
 const p=S.px;
 const mark=(k)=>{const[x,y]=k.split(",").map(Number);ctx.fillRect((x-S.x0)*p,(y-S.y0)*p,p,p);};
 if(document.getElementById("showphoto").checked&&photoLayer)ctx.drawImage(photoLayer,0,0);
 // Manual terrain replaces the automatic type, including under translucent paint.
 for(const set of groups())for(const k of set){const[x,y]=k.split(",").map(Number);ctx.clearRect((x-S.x0)*p,(y-S.y0)*p,p,p);}
 for(const [set,color] of [[blocked,"#e6281e"],[water,WATER_COLOR],[rocks,"#c83c28"],[passable,"#3cdc50"]]){
  ctx.fillStyle=color;for(const k of set)mark(k);
 }
 if(document.getElementById("showplaces").checked){ctx.fillStyle="#ffd700";for(const k of S.settlements)mark(k);}
 ctx.globalAlpha=1;
}
function paintCell(cx,cy){
 const r=Math.floor(brush/2);
 for(let dy=-r;dy<=r;dy++)for(let dx=-r;dx<=r;dx++){
  const x=cx+dx,y=cy+dy;if(x<S.x0||x>S.x1||y<S.y0||y>S.y1)continue;
  const k=key(x,y);for(const set of groups())set.delete(k);
  if(mode==="wall")blocked.add(k);else if(mode==="open")passable.add(k);else if(mode==="water")water.add(k);else if(mode==="rocks")rocks.add(k);
 }
 dirty=true;editVersion++;
}
function paint(ev){
 const point=cellAt(ev),a=last||point;
 let[x,y]=a;const [tx,ty]=point,dx=Math.abs(tx-x),dy=-Math.abs(ty-y),sx=x<tx?1:-1,sy=y<ty?1:-1;let error=dx+dy;
 while(true){paintCell(x,y);if(x===tx&&y===ty)break;const twice=2*error;if(twice>=dy){error+=dy;x+=sx;}if(twice<=dx){error+=dx;y+=sy;}}
 last=point;draw();
}
for(const id of modes)document.getElementById(id).onclick=()=>{mode=id;for(const q of modes)document.getElementById(q).setAttribute("aria-pressed",q===id?"true":"false");};
document.getElementById("size").oninput=e=>{brush=+e.target.value;document.getElementById("sz").textContent=brush;};
document.getElementById("opacity").oninput=e=>{document.getElementById("alpha").textContent=e.target.value+"%";dirty=true;editVersion++;draw();};
document.getElementById("showphoto").onchange=draw;document.getElementById("showplaces").onchange=draw;
over.addEventListener("pointerdown",e=>{if(!S||e.button!==0)return;painting=true;last=null;over.setPointerCapture(e.pointerId);paint(e);});
window.addEventListener("pointerup",()=>{painting=false;last=null;});
over.addEventListener("pointercancel",()=>{painting=false;last=null;});
over.addEventListener("pointermove",e=>{if(!S)return;if(painting)paint(e);const[x,y]=cellAt(e);msg.textContent=x+","+y+(dirty?" · Есть несохранённые изменения":"");});
document.getElementById("wrap").addEventListener("wheel",e=>{if(!e.ctrlKey)return;e.preventDefault();zoom=Math.min(6,Math.max(.25,zoom*(e.deltaY<0?1.2:1/1.2)));stage.style.transform="scale("+zoom+")";},{passive:false});
window.addEventListener("beforeunload",e=>{if(dirty){e.preventDefault();e.returnValue="";}});
function payload(){return {blocked:[...blocked,...water,...rocks],passable:[...passable],water:[...water],rocks:[...rocks],opacity:+document.getElementById("opacity").value,revision:S.revision};}
async function post(path,body){const r=await fetch(path,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});const data=await r.json();if(!r.ok)throw Error(data.error||"Не удалось выполнить действие");return data;}
document.getElementById("save").onclick=async()=>{
 const button=document.getElementById("save"),version=editVersion;button.disabled=true;msg.textContent="Сохраняю…";
 try{const r=await post("/save",payload());S.revision=r.revision;dirty=editVersion!==version;msg.textContent="Сохранено: вода "+r.water+", скалы "+r.rocks+", непроходимых всего "+r.blocked+", проходов "+r.passable+(dirty?" · Остались несохранённые изменения":"");}
 catch(error){msg.textContent=error.message;}finally{button.disabled=false;}
};
document.getElementById("check").onclick=async()=>{
 msg.textContent="Проверяю…";
 try{const r=await post("/check",payload());msg.textContent=r.ok?"Все "+r.settlements+" локаций доступны":(r.why||"Недоступно локаций: "+r.cut_total+" — "+(r.cut||[]).slice(0,6).join(" "));}
 catch(error){msg.textContent=error.message;}
};
(async()=>{
 try{
  const response=await fetch("/state");if(!response.ok)throw Error("Не удалось загрузить разметку");S=await response.json();
  water=new Set(S.water||[]);rocks=new Set(S.rocks||[]);blocked=new Set(S.blocked.filter(k=>!water.has(k)&&!rocks.has(k)));passable=new Set(S.passable);
  document.getElementById("opacity").value=S.opacity;document.getElementById("alpha").textContent=S.opacity+"%";
  const w=(S.x1-S.x0+1)*S.px,h=(S.y1-S.y0+1)*S.px;img.src="/map.png";img.width=w;img.height=h;over.width=w;over.height=h;stage.style.width=w+"px";stage.style.height=h+"px";
  photoLayer=document.createElement("canvas");photoLayer.width=w;photoLayer.height=h;const pc=photoLayer.getContext("2d");
  for(let y=0;y<S.photo.length;y++)for(let x=0;x<S.photo[y].length;x++){
   const c=S.photo[y][x];if(c!=="#"&&c!=="~")continue;
   pc.fillStyle=c==="~"?WATER_COLOR:"rgba(200,60,40,.45)";pc.fillRect(x*S.px,y*S.px,S.px,S.px);
  }
  draw();msg.textContent="Вода, стены и скалы непроходимы · Проход открывает клетку · Ctrl+колесо — масштаб";
 }catch(error){msg.textContent=error.message;}
})();
</script></html>"""


def legacy_main():
    render()
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    url = "http://127.0.0.1:%d/" % PORT
    print("редактор границ: %s" % url)
    print("рисуйте красным стены, зелёным проходы; «Проверить» скажет,")
    print("не отрезало ли посёлки, «Сохранить» пишет data/terrain_verified.json")
    try:
        webbrowser.open(url)
    except Exception:
        pass
    srv.serve_forever()


# The same repository entry point now opens the boundary-aware editor. Keep
# the stitching and legacy parsing helpers for resource preparation/migration.

def main():
    render()
    import map_editor_preview
    if '--source' not in sys.argv:sys.argv.extend(['--source',EDITOR_SEED if os.path.isfile(EDITOR_SEED) else VERIFIED])
    if '--map-image' not in sys.argv:sys.argv.extend(['--map-image',CACHE])
    if '--port' not in sys.argv:sys.argv.extend(['--port',str(PORT)])
    map_editor_preview.main()


if __name__ == "__main__":
    main()
