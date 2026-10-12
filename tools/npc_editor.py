#!/usr/bin/env python3
"""Name the inhabitants and decide what they sell.

    python3 tools/npc_editor.py

Opens a page on 127.0.0.1:8091. Pick a location, and it lists whoever stands
in it, straight out of the client's own XML. Each one gets a name field and,
if they trade, a list of goods: search the catalogue, click to add, click the
cross to take away. "Сохранить" writes data/npcs.json.

Nothing here touches the game while it runs: the file is data, the server
reads it at start (server/npcs.py), and names.py and items.stock_for consult
it over the wiki. Restart the server -- and rebuild the launcher, because the
string table rides inside the exe -- for names to reach anybody.

This is the first half of the editor the world needs. It does not move
anyone: placement is the map editor's kind of problem, and both belong in one
tool later.
"""
import io
import json
import os
import re
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "server"))
os.environ.setdefault(
    "LAVA_RES", "/mnt/c/Users/gmkrt/OneDrive/Desktop/LAVA/res")

import items   # noqa: E402
import names   # noqa: E402
import npcs    # noqa: E402
import shop_bands   # noqa: E402
import world   # noqa: E402

PORT = int(os.environ.get("LAVA_NPC_EDITOR_PORT", "8091"))
OUT = os.path.join(ROOT, "data", "npcs.json")

# root_type_id, as mobs.xml gives it. Only some of these have anything to
# sell; the rest get a name and nothing else.
ROLES = {0: "моб", 1: "торговец", 4: "житель", 5: "лекарь"}
TRADERS = (1, 4)

_MOBS = None
_PLACES = None


def mobs_table():
    global _MOBS
    if _MOBS is None:
        _MOBS = world.mob_types()
    return _MOBS


def places():
    """Every static location that has somebody standing in it.

    Read once, on the first request: it is 1353 small files, and the answer
    does not change while the editor is open.
    """
    global _PLACES
    if _PLACES is not None:
        return _PLACES
    out = []
    base = os.path.join(world.RES, "locations", "static")
    for fn in sorted(os.listdir(base)):
        if not fn.endswith(".xml"):
            continue
        try:
            loc_id = int(fn[:-4])
        except ValueError:
            continue
        try:
            txt = world._read(os.path.join(base, fn))
        except OSError:
            continue
        node = re.search(r"<mobs>(.*?)</mobs>", txt, re.S)
        if not node:
            continue
        body = re.sub(r"\s+", "", node.group(1))
        if not body:
            continue
        title = re.search(r'<location[^>]*title="([^"]*)"', txt)
        out.append({"id": loc_id,
                    "title": title.group(1) if title else "",
                    "count": len(body) // 8})
    _PLACES = sorted(out, key=lambda p: (-p["count"], p["id"]))
    return _PLACES


def item_name(type_id):
    return names.text(items.STRING_ID_OFFSET + type_id)


def describe(type_id):
    """One inhabitant, as the page shows them."""
    root, internal, art = mobs_table().get(type_id, (0, "", ""))
    return {
        "type": type_id,
        "root": root,
        "role": ROLES.get(root, "?"),
        "art": art,
        "internal": internal,
        # What the player sees today, whatever decided it.
        "name": names.text(type_id),
        # And what they would see if nobody had. Saving a field nobody
        # touched must not record "#2191" or "Npc_Trader000032" as somebody's
        # considered choice of name.
        "fallback": names.BASE.get(type_id, "#%d" % type_id),
        # Whether the owner has already had a say about this one.
        "named": type_id in npcs.NAMES,
        "trades": root in TRADERS,
        # The trader's own list, without the (G) pouches the server puts
        # after the ordinary ones (items.GOLD_POUCHES): those are a rule, so
        # the page shows them apart and Save never writes them into
        # data/npcs.json (items.own_stock).
        "stock": [{"type": t, "name": item_name(t)}
                  for t in items.own_stock(type_id)],
        "stock_chosen": npcs.stock(type_id) is not None,
    }


def gold_pouches():
    """items.GOLD_POUCHES as the page reads it: ordinary id -> the (G) one."""
    return {str(a): {"type": g, "name": item_name(g)}
            for a, g in items.GOLD_POUCHES.items()}


def gold_added(stock):
    """The (G) pouches the server puts after the ordinary ones of this list
    (items.with_gold_pouches), the ones the list does not hold itself: what
    the page shows apart, in Python for the tests (the page's own goldOf)."""
    have, out = set(stock), []
    for t in stock:
        gold = items.GOLD_POUCHES.get(t)
        if gold is not None and gold not in have and gold not in out:
            out.append(gold)
    return out


def occupants(loc_id):
    """The location as a plan: its floor, and who stands on it.

    Two lists, because they answer different questions. `spawns` is every
    figure with the cell it stands on -- that is the picture. `npcs` is the
    creature types among them, deduplicated, because a name and a stock list
    belong to a type and not to a spot: put the same trader down twice and
    there is still one trader. The page says so when it happens, rather than
    letting somebody rename one of the two and wonder why both changed.

    The floor comes with it: obstacles are what makes the shape of a place
    readable, and without them the figures float in a rectangle of nothing.
    """
    loc = world.location(loc_id)
    counts = {}
    for _cell, type_id in loc.spawns:
        counts[type_id] = counts.get(type_id, 0) + 1

    out = []
    city = shop_bands.city(loc_id)
    for type_id in counts:
        one = describe(type_id)
        one["copies"] = counts[type_id]
        # A weapon, set or medicine seller of a city sells its band here besides
        # its own list (server/shop_bands.py, data/shop_bands.json; the medicine
        # by the city's tiers and the one below, one currency where the file
        # says only): shown, not edited, and never saved into data/npcs.json.
        if city and shop_bands.kinds(type_id):
            one["band_city"] = "%s %d-%d" % city
            one["band"] = [{"type": t, "name": item_name(t)}
                           for t in items.stock_for(type_id, loc_id)
                           if shop_bands.band_ware(t)]
        out.append(one)
    # Traders first: they are what the tool is for.
    out.sort(key=lambda n: (not n["trades"], n["name"]))
    return {
        "id": loc_id,
        "title": loc.title,
        "width": loc.width,
        "height": loc.height,
        "npcs": out,
        # Ordinary base belt -> its (G) copy, for the read-only list under the
        # goods: the page works it out from the list as it is being edited.
        "gold_pouches": gold_pouches(),
        "spawns": [{"cell": c, "type": t} for c, t in loc.spawns],
        "obstacles": sorted(loc.obstacles),
        "entries": sorted(set(loc.entries)),
    }


def search(query, limit=60):
    """The catalogue by name, for the goods picker."""
    q = (query or "").strip().casefold()
    if len(q) < 2:
        return []
    out = []
    for type_id in items.catalogue():
        name = item_name(type_id)
        if q in name.casefold():
            out.append({"type": type_id, "name": name})
            if len(out) >= limit:
                break
    return sorted(out, key=lambda i: i["name"])


def save(doc):
    """Merge what the page sent into the file, and write it whole.

    Merged rather than replaced: the page only ever holds one location, and
    overwriting the file with it would drop every decision made about every
    other. What the page sends about a creature is the whole truth about
    that creature -- an empty name means "no decision", an empty list of
    goods means "sells nothing".
    """
    kept_names = dict(npcs.NAMES)
    kept_stock = dict(npcs.STOCK)
    for entry in doc.get("npcs") or ():
        type_id = int(entry["type"])
        name = str(entry.get("name") or "").strip()
        # A name only counts as a decision if it differs from what was in the
        # field to begin with. Otherwise every Save froze the whole location's
        # fallbacks into the file -- internal names, and even the "#2191"
        # placeholder that names.text() hands back for an id nothing knows.
        if name and name != str(entry.get("fallback") or ""):
            kept_names[type_id] = name
        else:
            kept_names.pop(type_id, None)
        if entry.get("stock_chosen"):
            kept_stock[type_id] = [int(t) for t in entry.get("stock") or ()]
        else:
            kept_stock.pop(type_id, None)

    out = {
        "_": ("Имена жителей и их ассортимент, выбранные вручную. "
              "server/npcs.py читает это при старте: names.py берёт отсюда "
              "имя поверх вики, items.stock_for — список товаров поверх неё "
              "же. Ключ — тип существа из mobs.xml, не локация: два рынка с "
              "одним типом торговца ставят одного и того же торговца. "
              "Пишется tools/npc_editor.py."),
        "names": {str(k): v for k, v in sorted(kept_names.items())},
        "stock": {str(k): v for k, v in sorted(kept_stock.items())},
    }
    # The keys this page does not edit, including healer fees and home
    # registration decisions (server/npcs.py), stay as the file has them.
    try:
        with io.open(OUT, encoding="utf-8") as fh:
            for key, value in json.load(fh).items():
                out.setdefault(key, value)
    except (OSError, ValueError):
        pass
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
    # The module was loaded at import and the page will ask again.
    npcs.NAMES, npcs.STOCK = kept_names, kept_stock
    print("сохранено: %d имён, %d ассортиментов" % (len(kept_names),
                                                    len(kept_stock)))
    return {"saved": True, "names": len(kept_names), "stock": len(kept_stock)}


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
        path, _, query = self.path.partition("?")
        args = dict(p.split("=", 1) for p in query.split("&") if "=" in p)
        try:
            if path == "/places":
                self._send(json.dumps(places()))
            elif path == "/loc":
                self._send(json.dumps(occupants(int(args.get("id", "102")))))
            elif path == "/items":
                from urllib.parse import unquote_plus
                self._send(json.dumps(search(unquote_plus(args.get("q", "")))))
            else:
                self._send(PAGE, "text/html; charset=utf-8")
        except Exception as e:
            self._send(json.dumps({"error": "%s: %s" % (type(e).__name__, e)}),
                       code=500)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        doc = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
        try:
            self._send(json.dumps(save(doc)))
        except Exception as e:
            self._send(json.dumps({"error": "%s: %s" % (type(e).__name__, e)}),
                       code=500)


PAGE = r"""<!doctype html><html lang=ru><meta charset=utf-8>
<title>Жители — LAVA</title>
<style>
 html,body{margin:0;height:100%;background:#15130f;color:#cfc6b0;
   font:14px/1.45 system-ui,sans-serif;overflow:hidden}
 #bar{display:flex;gap:10px;align-items:center;padding:9px 14px;
   background:#1e1b15;border-bottom:1px solid #332d22}
 select,input{background:#100e0a;color:#e8dfc8;border:1px solid #3d362a;
   border-radius:3px;padding:6px 8px;font:inherit}
 select{max-width:380px}
 button{background:#6b5a34;color:#f2e9d2;border:0;border-radius:3px;
   padding:7px 14px;font:inherit;cursor:pointer}
 button:hover{background:#7d6a3e}
 #msg{color:#8a8071;margin-left:auto;font-size:13px}
 #split{display:flex;height:calc(100% - 47px)}
 #plan{flex:1;position:relative;overflow:auto;background:#100e0a}
 #hint{position:fixed;pointer-events:none;background:#1e1b15;
   border:1px solid #3d362a;border-radius:3px;padding:5px 9px;font-size:12px;
   display:none;z-index:9;white-space:pre}
 #side{width:380px;border-left:1px solid #332d22;background:#1a1712;
   overflow:auto;padding:16px}
 h2{font:500 17px/1.3 system-ui;margin:0 0 2px;color:#e8dfc8}
 .meta{font:12px ui-monospace,monospace;color:#6f675a;margin-bottom:14px}
 .lab{font-size:12px;color:#8a8071;margin:14px 0 5px}
 .row{display:flex;gap:8px;align-items:center}
 .good{display:flex;gap:6px;align-items:center;background:#100e0a;
   border:1px solid #3d362a;border-radius:3px;padding:3px 4px 3px 9px;
   font-size:13px;margin:0 0 5px}
 .good b{font-weight:400;flex:1}
 .good i{cursor:pointer;color:#8a8071;font-style:normal;padding:0 5px}
 .good i:hover{color:#e2543a}
 .hits{border:1px solid #3d362a;border-radius:3px;max-height:230px;
   overflow:auto;margin-top:5px}
 .hits div{padding:5px 9px;cursor:pointer;font-size:13px}
 .hits div:hover{background:#2a251d}
 .none{color:#6f675a;font-size:13px}
 .warn{color:#d9a441;font-size:12px;margin-top:8px}
 .legend{font-size:12px;color:#6f675a;padding:8px 14px;border-top:1px solid #332d22}
 .dot{display:inline-block;width:9px;height:9px;border-radius:9px;
   vertical-align:-1px;margin:0 4px 0 12px}
</style>
<div id=bar>
 <input id=filter placeholder="найти место — «нубий», «рынок»…" size=26>
 <select id=place></select>
 <input id=zoom type=range min=6 max=26 value=13 title="масштаб">
 <button id=save>Сохранить</button>
 <span id=msg></span>
</div>
<div id=split>
 <div id=plan><canvas id=cv></canvas></div>
 <div id=side><p class=none>Кликните фигуру на плане.</p></div>
</div>
<div class=legend>
 <span class=dot style=background:#d9a441></span>торговец
 <span class=dot style=background:#8bb75a></span>лекарь
 <span class=dot style=background:#b3a894></span>житель
 <span class=dot style=background:#e2543a></span>моб
 <span class=dot style=background:#2a251d></span>препятствие
 <span class=dot style="background:#100e0a;border:1px solid #3d5c33"></span>вход
</div>
<div id=hint></div>
<script>
// The grid the client measures with (LocationGrid.as, mirrored in
// server/mobs.py): odd rows step half a hex right, and a row is 0.866 of a
// hex tall. Everything below is that, times the zoom.
var ROW_H = 0.8660254037844386;
var COLOURS = {0: "#e2543a", 1: "#d9a441", 4: "#b3a894", 5: "#8bb75a"};

var state = null, S = 13, sel = null, byType = {};
var cv = document.getElementById("cv"), ctx = cv.getContext("2d");

function esc(s){ return String(s).replace(/[<&]/g, function(c){
  return c === "<" ? "&lt;" : "&amp;"; }); }
function say(t){ document.getElementById("msg").textContent = t; }

function centre(cell){
  var gx = cell % state.width, gy = Math.floor(cell / state.width);
  return {x: (gx + 0.5 * (gy % 2) + 0.5) * S, y: (gy * ROW_H + 0.5) * S};
}

function hex(x, y, r){
  ctx.beginPath();
  for (var i = 0; i < 6; i++){
    var a = Math.PI / 180 * (60 * i - 30);
    var px = x + r * Math.cos(a), py = y + r * Math.sin(a);
    i ? ctx.lineTo(px, py) : ctx.moveTo(px, py);
  }
  ctx.closePath();
}

function draw(){
  if (!state) return;
  cv.width = Math.ceil((state.width + 1) * S);
  cv.height = Math.ceil((state.height * ROW_H + 1) * S);
  ctx.fillStyle = "#100e0a";
  ctx.fillRect(0, 0, cv.width, cv.height);

  // The floor first: obstacles are what gives a place its shape.
  ctx.fillStyle = "#2a251d";
  state.obstacles.forEach(function(c){
    var p = centre(c); hex(p.x, p.y, S * 0.56); ctx.fill();
  });
  ctx.strokeStyle = "#3d5c33";
  ctx.lineWidth = 1;
  state.entries.forEach(function(c){
    var p = centre(c); hex(p.x, p.y, S * 0.5); ctx.stroke();
  });

  // Then the figures, biggest thing on the plan.
  var r = Math.max(3.5, S * 0.42);
  state.spawns.forEach(function(sp){
    var n = byType[sp.type];
    if (!n) return;
    var p = centre(sp.cell);
    ctx.beginPath(); ctx.arc(p.x, p.y, r, 0, 7);
    ctx.fillStyle = COLOURS[n.root] || "#b3a894";
    ctx.fill();
    if (sel === sp.type){
      ctx.strokeStyle = "#f0c46a"; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.arc(p.x, p.y, r + 3.5, 0, 7); ctx.stroke();
    }
  });

  // Labels last, and with somewhere to go. Traders in a market stand
  // shoulder to shoulder, so written straight beside the dot the names
  // land on top of each other and the plan becomes less readable than the
  // list it replaced. Each one is nudged down past whatever was already
  // written near it, with a leader line back to its figure.
  if (S < 9) return;
  ctx.font = "11px system-ui";
  var taken = [];
  state.spawns.slice().sort(function(a, b){
    return centre(a.cell).y - centre(b.cell).y;
  }).forEach(function(sp){
    var n = byType[sp.type];
    if (!n) return;
    var p = centre(sp.cell);
    var text = n.name.slice(0, 24);
    var w = ctx.measureText(text).width;
    var x = p.x + r + 5, y = p.y + 4;
    for (var guard = 0; guard < 40; guard++){
      var clash = taken.some(function(t){
        return Math.abs(t.y - y) < 12 && x < t.x + t.w + 6 && t.x < x + w + 6;
      });
      if (!clash) break;
      y += 12;
    }
    taken.push({x: x, y: y, w: w});
    if (y - p.y > 8){
      ctx.strokeStyle = "#4a4236"; ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(p.x + r, p.y);
      ctx.lineTo(x - 3, y - 4);
      ctx.stroke();
    }
    ctx.fillStyle = "rgba(16,14,10,0.82)";
    ctx.fillRect(x - 2, y - 10, w + 4, 13);
    ctx.fillStyle = sel === sp.type ? "#f0c46a" : "#cfc6b0";
    ctx.fillText(text, x, y);
  });
}

function nearest(mx, my){
  var best = null, bd = S * 0.9;
  state.spawns.forEach(function(sp){
    var p = centre(sp.cell);
    var d = Math.hypot(p.x - mx, p.y - my);
    if (d < bd){ bd = d; best = sp; }
  });
  return best;
}

cv.onmousemove = function(e){
  var r = cv.getBoundingClientRect();
  var sp = nearest(e.clientX - r.left, e.clientY - r.top);
  var h = document.getElementById("hint");
  if (!sp){ h.style.display = "none"; return; }
  var n = byType[sp.type];
  h.textContent = n.name + "\n" + n.role + " · тип " + n.type +
                  "\n" + n.internal + " · " + n.art +
                  (n.trades ? "\nтоваров: " + n.stock.length : "");
  h.style.display = "block";
  h.style.left = (e.clientX + 14) + "px";
  h.style.top = (e.clientY + 14) + "px";
};
cv.onmouseleave = function(){ document.getElementById("hint").style.display = "none"; };
cv.onclick = function(e){
  var r = cv.getBoundingClientRect();
  var sp = nearest(e.clientX - r.left, e.clientY - r.top);
  if (sp){ sel = sp.type; side(); draw(); }
};

document.getElementById("zoom").oninput = function(e){
  S = +e.target.value; draw();
};

// The (G) pouches the server puts after the ordinary ones on this list
// (items.with_gold_pouches): shown, never sent with Save (gold_added).
function goldOf(n){
  var gp = (state && state.gold_pouches) || {}, out = [];
  n.stock.forEach(function(s){
    var g = gp[s.type];
    if (g && !n.stock.some(function(x){ return x.type === g.type; }) &&
        !out.some(function(x){ return x.type === g.type; })) out.push(g);
  });
  return out;
}

function side(){
  var box = document.getElementById("side");
  var n = byType[sel];
  if (!n){ box.innerHTML = "<p class=none>Кликните фигуру на плане.</p>"; return; }
  box.innerHTML =
    '<h2>' + esc(n.name) + '</h2>' +
    '<div class=meta>' + esc(n.role) + " · тип " + n.type + " · " +
      esc(n.internal) + " · " + esc(n.art) +
      (n.named ? " · имя своё" : "") + (n.stock_chosen ? " · список свой" : "") +
    '</div>' +
    '<div class=lab>Имя</div>' +
    '<input id=nm style=width:100% value="' + esc(n.name) + '">' +
    (n.copies > 1 ? '<div class=warn>Этот тип стоит в локации ' + n.copies +
      ' раза — правка меняет все сразу: имя и товары принадлежат типу, ' +
      'а не месту.</div>' : "") +
    (n.trades ?
      '<div class=lab>Продаёт (' + n.stock.length + ')</div><div id=goods>' +
      (n.stock.length ? n.stock.map(function(s, j){
        return '<div class=good><b>' + esc(s.name) + '</b>' +
               '<i data-j="' + j + '">×</i></div>'; }).join("")
        : '<p class=none>ничего</p>') +
      '</div><input id=find placeholder="найти товар — два знака и больше">' +
      '<div class=hits id=hits style=display:none></div>' +
      (goldOf(n).length ?
        '<div class=lab>И (G) следом за обычными подсумками (' + goldOf(n).length +
        '; ставятся сами, items.GOLD_POUCHES)</div>' +
        goldOf(n).map(function(s){ return '<div class=good><b>' + esc(s.name) + '</b></div>'; })
          .join("") : "") +
      (n.band && n.band.length ?
        '<div class=lab>И по уровню города (' + esc(n.band_city) + ', ' + n.band.length +
        '; правится в data/shop_bands.json)</div>' +
        n.band.map(function(s){ return '<div class=good><b>' + esc(s.name) + '</b></div>'; })
          .join("") : "")
      : '<div class=lab>Не торгует</div>');

  var nm = document.getElementById("nm");
  if (nm) nm.oninput = function(){ n.name = nm.value; draw(); };
  box.querySelectorAll(".good i").forEach(function(el){
    el.onclick = function(){
      n.stock.splice(+el.dataset.j, 1); n.stock_chosen = true; side();
    };
  });
  var find = document.getElementById("find"), hits = document.getElementById("hits");
  if (find) find.oninput = function(){
    if (find.value.trim().length < 2){ hits.style.display = "none"; return; }
    fetch("/items?q=" + encodeURIComponent(find.value))
      .then(function(r){ return r.json(); })
      .then(function(list){
        hits.innerHTML = list.map(function(h){
          return '<div data-type="' + h.type + '">' + esc(h.name) + '</div>';
        }).join("");
        hits.style.display = list.length ? "block" : "none";
        hits.querySelectorAll("div[data-type]").forEach(function(row){
          row.onclick = function(){
            var t = +row.dataset.type;
            if (!n.stock.some(function(s){ return s.type === t; })){
              n.stock.push({type: t, name: row.textContent});
            }
            n.stock_chosen = true; side();
          };
        });
      });
  };
}

function load(){
  say("");
  sel = null;
  fetch("/loc?id=" + document.getElementById("place").value)
    .then(function(r){ return r.json(); })
    .then(function(d){
      state = d;
      byType = {};
      d.npcs.forEach(function(n){ byType[n.type] = n; });
      say(d.title + " · " + d.spawns.length + " фигур · " +
          d.width + "×" + d.height);
      side(); draw();
    });
}

// 1345 places, and the one you want is never the one on screen. The list is
// held here whole and the box narrows it: by name, or by the number if you
// already know it.
var places = [];

function fill(){
  var q = document.getElementById("filter").value.trim().toLowerCase();
  var box = document.getElementById("place");
  var was = box.value;
  var show = !q ? places : places.filter(function(p){
    return p.title.toLowerCase().indexOf(q) >= 0 || String(p.id) === q;
  });
  box.innerHTML = show.map(function(p){
    return '<option value="' + p.id + '">' + esc(p.title || "без названия") +
           "  ·  " + p.id + "  ·  " + p.count + "</option>"; }).join("");
  box.size = 1;
  if (!show.length) return;
  // Stay where we were if the filter still holds it; otherwise go to the
  // first match, so typing a name opens it without a second click.
  var keep = show.some(function(p){ return String(p.id) === was; });
  box.value = keep ? was : show[0].id;
  if (!keep) load();
}

fetch("/places").then(function(r){ return r.json(); }).then(function(ps){
  places = ps;
  fill();
  document.getElementById("place").value = 102;
  document.getElementById("place").onchange = load;
  document.getElementById("filter").oninput = fill;
  load();
});

document.getElementById("save").onclick = function(){
  say("сохраняю…");
  fetch("/", {method: "POST", body: JSON.stringify({
    npcs: state.npcs.map(function(n){
      return {type: n.type, name: n.name, fallback: n.fallback,
              stock_chosen: n.stock_chosen,
              stock: n.stock.map(function(s){ return s.type; })};
    })})})
    .then(function(r){ return r.json(); })
    .then(function(d){
      say(d.error ? d.error
                  : "записано: " + d.names + " имён, " + d.stock + " ассортиментов");
      load();
    });
};
</script>
"""


def main():
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    url = "http://127.0.0.1:%d/" % PORT
    print("редактор жителей: " + url)
    print("пишет: " + OUT)
    try:
        webbrowser.open(url)
    except Exception:
        pass
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print()


if __name__ == "__main__":
    main()
