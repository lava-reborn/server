"""SWF pictures: tools/swfx.py draws a library symbol as the client does.

The two fixes over lava-godot's swfx: a DefineBitsJPEG3's colour is
un-premultiplied by its alpha plane, and a symbol is cut to its shapes'
bounds (SpriteSource.drawBitmap) rather than trimmed to its visible pixels.
Small SWFs made here check the bounds maths with the standard library alone
and the pictures where Pillow is; with the original's Mountains.swf at hand
(tools/location_art.py finds it by client/base.txt), edge01.png is 424 px
wide as the client draws it, 368 trimmed, and its edges are not dark.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "server"))
import swfx  # noqa: E402
from swf_fixture import (export, jpeg3, lossless2, matrix, place, rect, shape,  # noqa: E402
                         sprite, swf)
from testkit import check, fails  # noqa: E402

try:
    import numpy as np
    from PIL import Image
except ImportError:
    Image = np = None


# --- bounds, standard library only ---------------------------------------------------------------
# A symbol: shape 1 with bounds (-100..300, 40..440) twips, inside sprite 2
# at (+200, -60) twips: its getRect is (100..500, -20..380) twips.
lib = swf([shape(1, (-100, 300, 40, 440)),
           sprite(2, [[place(1, 1, matrix(tx=200, ty=-60))]]),
           sprite(3, [[place(1, 2, matrix(2.0, 2.0))]]),
           export([(2, "sym.png"), (3, "big.png")])])
s = swfx.Swf(lib)
check("the fixture parses with no picture in it (no Pillow needed)",
      (sorted(s.exports), s.unknown), (["big.png", "sym.png"], set()))
check("rect: a shape's bounds through a sprite's placement, in twips",
      s.rect({1: (2, swfx.IDENT)}), (100.0, 500.0, -20.0, 380.0))
check("rect: through a scaled placement as well",
      s.rect({1: (3, swfx.IDENT)}), (200.0, 1000.0, -40.0, 760.0))
check("rect: an empty frame has none", s.rect({}), None)
s4 = swfx.Swf(swf([shape(1, (-40, 440, -40, 340), code=83, edges=(0, 400, 0, 300)),
                   sprite(2, [[place(1, 1)]]), export([(2, "e.png")])]))
check("rect: DefineShape4's edge bounds are getRect's, its shape bounds give _width",
      (s4.rect({1: (2, swfx.IDENT)}), s4.rect({1: (2, swfx.IDENT)}, edges=False)),
      ((0.0, 400.0, 0.0, 300.0), (-40.0, 440.0, -40.0, 340.0)))
check("read_rect reads what rect() writes",
      swfx.read_rect(rect(-7, 1234, 0, -99) + b"\0", 0)[0], [-7, 1234, 0, -99])
check("read_matrix reads a scale and a translation",
      swfx.read_matrix(matrix(20.0, 20.0, 40, -60), 0)[0], (20.0, 0.0, 0.0, 20.0, 40, -60))

# --- pictures ---------------------------------------------------------------------------------------
if Image is None:
    print("  --  Pillow or numpy not installed: picture checks skipped (WSL ~/venvs/lavagd has them)")
else:
    # 10x10 red, opaque, its fill at (2, 3) px inside shape bounds 20 x 15 px
    red = bytes([255, 255, 0, 0]) * 100
    pic = swf([lossless2(1, 10, 10, red),
               shape(2, (0, 400, 0, 300), bitmap=1, fill=(20.0, 20.0, 40, 60)),
               sprite(3, [[place(1, 2)]]), export([(3, "red.png")]),
               # the registration point inside the picture: bounds start at (-10, -5) px
               shape(4, (-200, 200, -100, 200), bitmap=1, fill=(20.0, 20.0, -200, -100)),
               sprite(5, [[place(1, 4)]]), export([(5, "centred.png")])])
    p = swfx.Swf(pic)
    (bimg, boff), = p.render_symbol("red.png")
    (aimg, aoff), = p.render_symbol("red.png", crop="alpha")
    check("crop=bounds: the shape's bounds, the picture inside at its place, offset (0, 0)",
          (bimg.size, boff, bimg.getbbox()), ((20, 15), (0, 0), (2, 3, 12, 13)))
    check("crop=alpha: trimmed to the red square, offset (2, 3) (lava-godot's swfx)",
          (aimg.size, aoff), ((10, 10), (2, 3)))
    check("library_bitmap is getFromLib: the symbol by its bounds",
          (p.library_bitmap("red.png")[0].size, p.library_bitmap("red.png")[1]), ((20, 15), (0, 0)))
    img, off = p.library_bitmap("centred.png")
    check("a registration point inside the picture: the offset is the bounds' top-left",
          (img.size, off), ((20, 15), (-10, -5)))
    check("library_bitmap of a name the library lacks: the root's picture, here none",
          p.library_bitmap("nope.png"), (None, None))
    stage = swfx.Swf(swf([lossless2(1, 10, 10, red),
                          shape(2, (0, 200, 0, 200), bitmap=1, fill=(20.0, 20.0, 0, 0)),
                          place(1, 2, matrix(tx=100, ty=40))]))
    check("a painted library: the root's picture for any name; getBitmap the same",
          (stage.library_bitmap("bg.jpg")[0].size, stage.library_bitmap("bg.jpg")[1],
           stage.root_bitmap()[1]), ((10, 10), (5, 2), (5, 2)))

    # premultiplied colour: JPEG3 stores rgb * alpha / 255; alpha 128 here
    buf = __import__("io").BytesIO()
    Image.new("RGB", (16, 16), (50, 25, 100)).save(buf, "JPEG", quality=100)
    j = swfx.Swf(swf([jpeg3(1, buf.getvalue(), bytes([128]) * 256),
                      shape(2, (0, 320, 0, 320), bitmap=1, fill=(20.0, 20.0, 0, 0)),
                      sprite(3, [[place(1, 2)]]), export([(3, "half.png")])]))
    px = np.asarray(j.render_symbol("half.png")[0][0]).astype(int)
    rgb = px[..., :3].reshape(-1, 3).mean(axis=0)
    check("fix 1: a JPEG3's colour is un-premultiplied by its alpha plane "
          "(stored 50,25,100 at alpha 128 -> about 100,50,199)",
          ([abs(int(round(v)) - w) <= 4 for v, w in zip(rgb, (100, 50, 199))], int(px[..., 3].min())),
          ([True, True, True], 128))
    # Lossless2 already was: ARGB premultiplied
    l2 = swfx.Swf(swf([lossless2(1, 2, 1, bytes([128, 64, 32, 16, 255, 10, 20, 30])),
                       shape(2, (0, 40, 0, 20), bitmap=1, fill=(20.0, 20.0, 0, 0)),
                       sprite(3, [[place(1, 2)]]), export([(3, "l2.png")])]))
    check("Lossless2 stays un-premultiplied as before",
          [l2.render_symbol("l2.png")[0][0].getpixel((x, 0)) for x in (0, 1)],
          [(127, 63, 31, 128), (10, 20, 30, 255)])

    # --- the original's Mountains.swf --------------------------------------------------------
    raw = None
    try:
        import location_art
        raw = location_art.Art().read("locations/libs/Mountains.swf")
    except Exception as e:      # no client/base.txt reader, no res
        print("  --  Mountains.swf not readable (%s)" % e)
    if raw is None:
        print("  --  the original's Mountains.swf not found (LAVA_ART_RES / LAVA_ART_STORE):"
              " real-art checks skipped")
    else:
        m = swfx.Swf(raw)
        (bimg, boff), = m.render_symbol("edge01.png")
        (aimg, aoff), = m.render_symbol("edge01.png", crop="alpha")
        check("Mountains edge01.png: 424 px wide by its bounds, 368 trimmed, 56 px further right",
              (bimg.size[0], aimg.size[0], aoff[0] - boff[0]), (424, 368, 56))
        a = np.asarray(bimg).astype(int)
        semi = (a[..., 3] > 0) & (a[..., 3] < 255)
        mean = a[..., :3][semi].mean()
        over = ((a[..., :3].max(axis=2) > a[..., 3] + 8) & semi).sum() / semi.sum()
        print("  ..  edge01: %d half-transparent px, mean RGB %.1f, rgb above alpha in %.0f%%"
              % (semi.sum(), mean, 100 * over))
        check("Mountains edge01.png: its half-transparent edge is not dark "
              "(mean RGB about 86; 51 premultiplied)", 78 <= mean <= 95, True)
        check("90 symbols, every one drawn", (len(m.exports),
              sum(1 for n in m.exports if m.library_bitmap(n)[0] is not None)), (90, 90))

print()
if fails:
    print("FAILED %d:" % len(fails))
    for failure in fails:
        print(" -", failure)
    sys.exit(1)
print("swfx OK")
