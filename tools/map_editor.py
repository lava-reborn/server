#!/usr/bin/env python3
"""Draw the world's walls by hand, over the map the client itself draws.

Reading the mountains off the picture has a ceiling: roughness finds the
crests and leaves the body of a massif open, colour floods, and no threshold
tells a ridge from a boulder field. A person looking at the map has no such
trouble, so this hands them the brush.

    python3 tools/map_editor.py

Opens a page on 127.0.0.1:8090. Paint red where a walker must not pass,
green where they must -- green wins over everything, including the
photograph -- and press "Сохранить". It writes data/terrain_verified.json,
which world.passable() consults before anything else, and says straight away
how many settlements can still be walked to.

Nothing here touches the game: the file is data, the server reads it at
start. Restart the server (or redeploy) for a change to take effect.
"""
import io
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
CACHE = os.path.join(ROOT, "data", "map_editor_base.png")


def render():
    """The client's own map tiles, stitched over the world rectangle."""
    if os.path.exists(CACHE):
        return
    from PIL import Image
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
                big.paste(Image.open(p).convert("RGB"),
                          ((tx - tx0) * TILE * 8, (ty - ty0) * TILE * 8))
    left, top = (gx0 - tx0 * TILE) * 8, (gy0 - ty0 * TILE) * 8
    crop = big.crop((left, top, left + (gx1 - gx0 + 1) * 8,
                     top + (gy1 - gy0 + 1) * 8))
    if PX != 8:
        crop = crop.resize(((gx1 - gx0 + 1) * PX, (gy1 - gy0 + 1) * PX),
                           Image.LANCZOS)
    crop.save(CACHE)
    print("карта готова: %s (%dx%d)" % (CACHE, crop.width, crop.height))


def load_verified():
    try:
        with io.open(VERIFIED, encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError):
        doc = {}
    return (list(doc.get("blocked") or ()), list(doc.get("passable") or ()))


def state():
    """Everything the page needs to draw itself."""
    gx0, gx1 = world.MAP_X
    gy0, gy1 = world.MAP_Y
    blocked, passable = load_verified()
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
        "blocked": blocked, "passable": passable,
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
        return world.passable(gx, gy)

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
        n = int(self.headers.get("Content-Length") or 0)
        doc = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
        blocked = sorted(set(doc.get("blocked") or ()))
        passable = sorted(set(doc.get("passable") or ()))
        if self.path.startswith("/check"):
            self._send(json.dumps(reachability(blocked, passable)))
            return
        out = {
            "_": ("Клетки, размеченные вручную поверх фотографии карты. "
                  "world.passable() смотрит сюда первым делом: это слово "
                  "человека, который смотрел на карту, и оно сильнее и "
                  "растра, и починок по выходам. Рисуется "
                  "tools/map_editor.py."),
            "blocked": blocked,
            "passable": passable,
        }
        with io.open(VERIFIED, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=1, sort_keys=True)
            fh.write("\n")
        print("сохранено: %d закрытых, %d открытых" % (len(blocked),
                                                      len(passable)))
        self._send(json.dumps({"saved": True, "blocked": len(blocked),
                               "passable": len(passable)}))


PAGE = r"""<!doctype html><html lang=ru><meta charset=utf-8>
<title>Границы карты — LAVA</title>
<style>
 html,body{margin:0;height:100%;background:#15130f;color:#cfc6b0;
   font:14px/1.4 system-ui,sans-serif;overflow:hidden}
 #bar{position:fixed;top:0;left:0;right:0;height:46px;background:#1e1b15;
   border-bottom:1px solid #332d22;display:flex;align-items:center;gap:14px;
   padding:0 14px;z-index:5}
 #wrap{position:absolute;top:46px;left:0;right:0;bottom:0;overflow:auto}
 #stage{position:relative;transform-origin:0 0}
 canvas{position:absolute;top:0;left:0;image-rendering:pixelated}
 button{background:#6b5a34;color:#f2e9d2;border:0;border-radius:3px;
   padding:6px 12px;cursor:pointer}
 button:hover{background:#7d6a3e}
 button.on{background:#b9432f}
 button.open.on{background:#3d7a33}
 .dim{color:#7d7566}
 #msg{margin-left:auto}
 label{color:#9c9280}
 input[type=range]{width:110px;vertical-align:middle}
</style>
<div id=bar>
 <b>Границы</b>
 <button id=wall class="on">Стена</button>
 <button id=open class="open">Проход</button>
 <button id=erase>Стереть</button>
 <label>кисть <input type=range id=size min=1 max=12 value=3>
   <span id=sz>3</span></label>
 <label><input type=checkbox id=showphoto checked> показывать растр</label>
 <button id=check>Проверить</button>
 <button id=save>Сохранить</button>
 <span id=msg class=dim>загрузка…</span>
</div>
<div id=wrap><div id=stage>
 <img id=map draggable=false>
 <canvas id=over></canvas>
</div></div>
<script>
let S=null, blocked=new Set(), passable=new Set(), mode="wall", brush=3;
let zoom=1, painting=false;
const stage=document.getElementById("stage"), img=document.getElementById("map");
const over=document.getElementById("over"), ctx=over.getContext("2d");
const msg=document.getElementById("msg");

function key(x,y){return x+","+y}
function cellAt(ev){
  const r=img.getBoundingClientRect();
  const px=(ev.clientX-r.left)/zoom, py=(ev.clientY-r.top)/zoom;
  return [S.x0+Math.floor(px/S.px), S.y0+Math.floor(py/S.px)];
}

function draw(){
  ctx.clearRect(0,0,over.width,over.height);
  const p=S.px;
  if(document.getElementById("showphoto").checked){
    for(let y=0;y<S.photo.length;y++){
      const row=S.photo[y];
      for(let x=0;x<row.length;x++){
        const c=row[x];
        if(c!=="#"&&c!=="~")continue;
        ctx.fillStyle=c==="~"?"rgba(60,120,200,.45)":"rgba(200,60,40,.35)";
        ctx.fillRect(x*p,y*p,p,p);
      }
    }
  }
  ctx.fillStyle="rgba(230,40,30,.85)";
  for(const k of blocked){const[a,b]=k.split(",").map(Number);
    ctx.fillRect((a-S.x0)*p,(b-S.y0)*p,p,p);}
  ctx.fillStyle="rgba(60,220,80,.85)";
  for(const k of passable){const[a,b]=k.split(",").map(Number);
    ctx.fillRect((a-S.x0)*p,(b-S.y0)*p,p,p);}
  ctx.fillStyle="#ffd700";
  for(const k of S.settlements){const[a,b]=k.split(",").map(Number);
    ctx.fillRect((a-S.x0)*p,(b-S.y0)*p,p,p);}
}

function paint(ev){
  const [cx,cy]=cellAt(ev);
  const r=Math.floor(brush/2);
  for(let dy=-r;dy<=r;dy++)for(let dx=-r;dx<=r;dx++){
    const x=cx+dx, y=cy+dy;
    if(x<S.x0||x>S.x1||y<S.y0||y>S.y1)continue;
    const k=key(x,y);
    blocked.delete(k); passable.delete(k);
    if(mode==="wall")blocked.add(k);
    else if(mode==="open")passable.add(k);
  }
  draw();
}

for(const [id,m] of [["wall","wall"],["open","open"],["erase","erase"]]){
  document.getElementById(id).onclick=()=>{
    mode=m;
    for(const q of ["wall","open","erase"])
      document.getElementById(q).classList.toggle("on",q===id);
  };
}
document.getElementById("size").oninput=e=>{
  brush=+e.target.value; document.getElementById("sz").textContent=brush;};
document.getElementById("showphoto").onchange=draw;

over.addEventListener("mousedown",e=>{if(e.button===0){painting=true;paint(e);}});
window.addEventListener("mouseup",()=>painting=false);
over.addEventListener("mousemove",e=>{if(painting)paint(e);
  const [x,y]=cellAt(e); msg.textContent=x+","+y;});
document.getElementById("wrap").addEventListener("wheel",e=>{
  if(!e.ctrlKey)return; e.preventDefault();
  zoom=Math.min(6,Math.max(.25,zoom*(e.deltaY<0?1.2:1/1.2)));
  stage.style.transform="scale("+zoom+")";
},{passive:false});

async function post(path,body){
  const r=await fetch(path,{method:"POST",body:JSON.stringify(body)});
  return r.json();
}
document.getElementById("save").onclick=async()=>{
  msg.textContent="сохраняю…";
  const r=await post("/save",{blocked:[...blocked],passable:[...passable]});
  msg.textContent="сохранено: "+r.blocked+" закрытых, "+r.passable+" открытых";
};
document.getElementById("check").onclick=async()=>{
  msg.textContent="считаю…";
  const r=await post("/check",{blocked:[...blocked],passable:[...passable]});
  msg.textContent=r.ok
    ? "всё проходимо: "+r.cells+" клеток, все "+r.settlements+" посёлков"
    : "ОТРЕЗАНО посёлков: "+r.cut_total+" — "+(r.cut||[]).slice(0,6).join(" ");
};

(async()=>{
  S=await (await fetch("/state")).json();
  blocked=new Set(S.blocked); passable=new Set(S.passable);
  const w=(S.x1-S.x0+1)*S.px, h=(S.y1-S.y0+1)*S.px;
  img.src="/map.png"; img.width=w; img.height=h;
  over.width=w; over.height=h;
  stage.style.width=w+"px"; stage.style.height=h+"px";
  draw();
  msg.textContent="карта "+(S.x1-S.x0+1)+"x"+(S.y1-S.y0+1)+
    " клеток · Ctrl+колесо — масштаб · жёлтым посёлки";
})();
</script></html>"""


def main():
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


if __name__ == "__main__":
    main()
