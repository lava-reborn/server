#!/usr/bin/env python3
"""Draw launcher/assets/lava.ico from the LAVA Reborn mark.

The mark is the flame on the left of launcher/assets/logo.png (the wordmark
the window shows); the letters are cut away by the gap between them and the
flame. It sits over the rounded dark square of the window's own background,
so the icon reads on a light Explorer pane and a dark taskbar alike.

Each size is cut from the 1014 px logo straight to its own pixel grid with a
Lanczos filter rather than scaled down in steps: the mark is flat colour on
a clean edge, which survives that, and the result is what a 16 px icon can
honestly show of it.

    python3 launcher/assets/make_icon.py
"""
import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
LOGO = os.path.join(HERE, "logo.png")
OUT = os.path.join(HERE, "lava.ico")

BG = (0x19, 0x1a, 0x1e, 255)
SIZES = [16, 24, 32, 48, 64, 128, 256]
SS = 4          # the square is drawn this many times over, then averaged down
INSET = 0.16    # margin around the mark, as a share of the icon's side


def mark():
    """The flame alone, cropped to its own alpha."""
    im = Image.open(LOGO).convert("RGBA")
    alpha = im.split()[3]
    w, h = im.size
    # Columns that carry ink; the first run of them is the flame, the gap
    # after it is where the letters start.
    cols = [x for x in range(w) if alpha.crop((x, 0, x + 1, h)).getbbox()]
    end = cols[0]
    for a, b in zip(cols, cols[1:]):
        if b - a > w // 60:
            break
        end = b
    flame = im.crop((cols[0], 0, end + 1, h))
    # Cropped to the flame's solid pixels, not to every pixel with some
    # alpha: the file carries a soft shadow down and to the right of the
    # mark, invisible on the dark square but wide enough to pull the mark
    # off centre by a tenth of its width when the box is fitted to it.
    solid = flame.split()[3].point(lambda v: 255 if v >= 200 else 0)
    return flame.crop(solid.getbbox())


def draw(flame, size):
    n = size * SS
    im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle([0, 0, n - 1, n - 1], radius=n * 0.20, fill=BG)
    room = n * (1 - 2 * INSET)
    k = min(room / flame.width, room / flame.height)
    fw, fh = max(1, round(flame.width * k)), max(1, round(flame.height * k))
    f = flame.resize((fw, fh), Image.LANCZOS)
    im.alpha_composite(f, (round((n - fw) / 2), round((n - fh) / 2)))
    return im.resize((size, size), Image.LANCZOS)


def main():
    flame = mark()
    frames = [draw(flame, s) for s in SIZES]
    # Pillow writes every frame it is given into one .ico; the largest carries
    # the file and the rest are listed in sizes.
    frames[-1].save(OUT, format="ICO", sizes=[(s, s) for s in SIZES],
                    append_images=frames[:-1])
    print("lava.ico:", ", ".join("%dx%d" % (s, s) for s in SIZES))


if __name__ == "__main__":
    main()
