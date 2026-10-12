// The film tools/flash_headless/run.sh plays in the real Flash Player 32
// projector (README.md beside this file). FFDec compiles this frame script
// when the image is built; mkhost.py then puts the client's own location
// classes, copied unchanged out of main.swf, in front of it.
//
// It drives those classes the way the client does: LDParser.parseLD reads
// the location, LocSourceLoader loads its library and ext sprites,
// LocBuilder.buildScenery's placement and DisplayLocBackground's background
// and decals build the scene (the depth manager aside). Every instance of an
// object of ours, an ext sprite whose id starts with c_, is then watched for
// WATCH game frames and reported: where it stands, which frame of its own
// it shows on each of those frames, its pixels, and the scene around it.
// The whole scene goes out at a quarter of its size. Everything is POSTed to
// the stand (stand.py), which check.py reads afterwards.
var BASE = _url.substring(0, _url.lastIndexOf("/"));
var LOC = "fh";
var MAX_OURS = 8;
var WATCH = 50;
var T0 = getTimer();
function post(name, text) {
    var lv = new LoadVars();
    lv.name = name;
    lv.body = text;
    lv.sendAndLoad(BASE + "/report", new LoadVars(), "POST");
}
function log(s) {
    post("log", String(getTimer() - T0) + " " + s);
}
var jobs = new Array();
function dump(name, bd) {
    if (bd == undefined) {
        log("NO BITMAP for " + name);
        return;
    }
    var j = new Object();
    j.name = name;
    j.bd = bd;
    j.y = 0;
    j.rows = new Array();
    jobs.push(j);
}
log("start: LDParser=" + (typeof lol.core.location.LDParser.parseLD) + " LocSourceLoader=" + (typeof lol.core.location.LocSourceLoader) + " SourceLibrary=" + (typeof lol.display.SourceLibrary.create) + " AnimationSprite=" + (typeof lol.display.AnimationSprite.create));

lol.services.SSEmulator.PATHTYPE = lol.services.SSEmulator.WEB;
lol.core.SSettings.getInstance().base = BASE;
lol.display.SourceLibrary.create();

var scene = _root.createEmptyMovieClip("scene", 10);
var bg_mc = scene.createEmptyMovieClip("bg_mc", 1);
var core = scene.createEmptyMovieClip("core_mc", 2);
var info;
var ours = new Array();
var built = false;
var builtFrame = 0;
var finished = false;

function buildScene() {
    var W = info.width * 40;
    var H = info.height * 15;
    // DisplayLocBackground.fillBackground + drawBGDecor, through the client's getFromLib/getBitmap
    var bm = new flash.display.BitmapData(W, H, true, 0);
    var tile;
    if (info.back.resType == "ext") {
        tile = lol.display.SourceLibrary.getSource(info.back.id).getBitmap();
    } else {
        tile = lol.display.SourceLibrary.getSource(info.libraryID).getFromLib(info.back.id);
    }
    var tx;
    var ty;
    if (tile == undefined || !(tile.width > 0)) {
        log("NO BACKGROUND " + info.back.id + "/" + info.back.resType);
    } else {
        for (tx = 0; tx < W; tx += tile.width) {
            for (ty = 0; ty < H; ty += tile.height) {
                bm.copyPixels(tile, tile.rectangle, new flash.geom.Point(tx, ty));
            }
        }
    }
    var m = new flash.geom.Matrix();
    var i;
    var dec;
    for (i = 0; i < info.bgDecorations.length; i++) {
        var o = info.bgDecorations[i];
        if (o.resType == "ext") {
            dec = lol.display.SourceLibrary.getSource(o.resID).getBitmap();
        } else {
            dec = lol.display.SourceLibrary.getSource(info.libraryID).getFromLib(o.resID);
        }
        if (dec == undefined) {
            log("NO DECORATION " + o.resID + "/" + o.resType);
        } else {
            m.translate(o.dx, o.dy);
            bm.draw(dec, m);
            m.translate(- o.dx, - o.dy);
        }
    }
    bg_mc.attachBitmap(bm, 1);
    // LocBuilder.buildScenery, line for line but for the depth manager
    for (i = 0; i < info.sprites.length; i++) {
        var obj = info.sprites[i];
        var d = core.getNextHighestDepth();
        var spr;
        if (obj.resType == "lib") {
            spr = lol.display.DisplaySprite.create(core, "el" + d, d);
        } else {
            spr = lol.display.AnimationSprite.create(core, "el" + d, d);
        }
        var gy = obj.point.y;
        var gx = obj.point.x;
        // LocationGrid.getCellFromGrid: CellsGrid[y][x], undefined off the
        // grid (the extra row y == H); DisplayLocScene.placeObject then
        // sets NaN, which Flash ignores, and dx, dy land from 0, 0
        var cell = (gy >= 0 && gy < info.height && gx >= 0 && gx < info.width) ? {rx:gx + 0.5 * (gy % 2), ry:gy * 0.8660254037844386} : undefined;
        var p = lol.core.location.LocDeclaration.abstractToReal({x:cell.rx, y:cell.ry});
        spr._x = p.x;
        spr._y = p.y;
        spr._x += obj.resDX;
        spr._y += obj.resDY;
        if (obj.resType == "lib") {
            spr.displayLibrary(info.libraryID, obj.resID);
        } else {
            spr.display(obj.resID, lol.services.SSEmulator.getSpriteURL("sprite", obj.resID));
        }
        if (obj.resType == "ext" && obj.resID.substr(0, 2) == "c_") {
            var fr = new Array();
            for (var k = 0; k < obj.front_arr.length; k++) {
                fr.push(obj.front_arr[k].x + ":" + obj.front_arr[k].y);
            }
            log("built " + obj.resID + " cell " + obj.point.x + ":" + obj.point.y + " at " + spr._x + "," + spr._y + " front " + fr.join(" "));
            if (ours.length < MAX_OURS) {
                var w = new Object();
                w.spr = spr;
                w.id = obj.resID;
                w.cell = obj.point.x + ":" + obj.point.y;
                w.trace = new Array();
                ours.push(w);
            }
        }
    }
    built = true;
}

var loader = new lol.core.location.LocSourceLoader();
var lis = new Object();
lis.locLoaded = function(ev) {
    log("loaded: " + ev.list.join(" | "));
    buildScene();
};
loader.addEventListener("locLoaded", lis);

var x = new XML();
x.ignoreWhite = true;
x.onLoad = function(ok) {
    if (!ok) {
        log("NO LOCATION XML");
        finished = true;
        log("DONE");
        return;
    }
    info = lol.core.location.LDParser.parseLD(x);
    var nl = 0;
    var ne = 0;
    for (var i = 0; i < info.sprites.length; i++) {
        if (info.sprites[i].resType == "lib") {
            nl++;
        } else {
            ne++;
        }
    }
    log("parse: library=" + info.libraryID + " size=" + info.width + "x" + info.height + " lib=" + nl + " ext=" + ne + " bgdecorations=" + info.bgDecorations.length + " obstacles=" + info.obstacles.length + " back=" + info.back.id + "/" + info.back.resType);
    loader.loadSources(info);
};
x.load(BASE + "/locations/static/" + LOC + ".xml");

var frameNo = 0;
_root.onEnterFrame = function() {
    frameNo++;
    var k;
    if (built && builtFrame == 0) {
        builtFrame = frameNo;
    }
    if (builtFrame > 0 && frameNo - builtFrame < WATCH) {
        for (k = 0; k < ours.length; k++) {
            ours[k].trace.push(ours[k].spr.display_mc._currentframe);
        }
    }
    if (builtFrame > 0 && frameNo - builtFrame == WATCH) {
        for (k = 0; k < ours.length; k++) {
            var o = ours[k];
            var s = o.spr;
            post("trace_" + k, o.id + "|" + o.cell + "|" + o.trace.join(","));
            log("instance " + k + " " + o.id + " cell " + o.cell + " at " + s._x + "," + s._y + " size " + s._width + "x" + s._height + " frame " + s.display_mc._currentframe);
            var b = new flash.display.BitmapData(s._width, s._height, true, 0);
            b.draw(s);
            dump("inst_" + k + "_f" + s.display_mc._currentframe, b);
            // the scene around it, 1:1
            var cx = Math.round(s._x + s._width / 2 - 200);
            var cy = Math.round(s._y + s._height / 2 - 150);
            var crop = new flash.display.BitmapData(400, 300, false, 0);
            var cm = new flash.geom.Matrix();
            cm.translate(- cx, - cy);
            crop.draw(scene, cm);
            log("crop " + k + " from " + cx + "," + cy);
            dump("crop_" + k, crop);
        }
        var all = new flash.display.BitmapData(Math.ceil(info.width * 10), Math.ceil(info.height * 15 / 4), false, 0);
        var m2 = new flash.geom.Matrix();
        m2.scale(0.25, 0.25);
        all.draw(scene, m2);
        dump("scene_quarter", all);
        // what the projector's window shows from now on: around the first object, 1:1
        if (ours.length > 0) {
            scene._x = 475 - (ours[0].spr._x + ours[0].spr._width / 2);
            scene._y = 325 - (ours[0].spr._y + ours[0].spr._height / 2);
        }
    }
    var budget = 12000;
    while (jobs.length > 0 && budget > 0) {
        var j = jobs[0];
        var w = j.bd.width;
        while (j.y < j.bd.height && budget > 0) {
            var row = new Array();
            for (var xx = 0; xx < w; xx++) {
                row.push(j.bd.getPixel32(xx, j.y).toString(16));
            }
            j.rows.push(row.join(","));
            j.y++;
            budget -= w;
        }
        if (j.y >= j.bd.height) {
            post("bmp_" + j.name, j.bd.width + "x" + j.bd.height + "|" + j.rows.join(";"));
            jobs.shift();
        }
    }
    if (builtFrame > 0 && !finished && frameNo - builtFrame > WATCH + 2 && jobs.length == 0) {
        finished = true;
        log("DONE frame " + frameNo);
    }
};
