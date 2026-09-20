#!/usr/bin/env python3
"""Draw launcher/assets/lava.ico from the brand mark.

The mark is the three polygons of lava-site/src/assets/logo-horizontal.svg on
its own 48-unit grid, over the rounded dark square of app-icon-180.png. Drawn
rather than resampled from the PNG: an icon is mostly seen at 16 and 32
pixels, and a downscaled photograph of a logo is mush at that size.

Below 48 the small diamond is dropped and the chevrons are given the room it
used, the way favicon.svg already does it -- at 16 pixels the diamond is two
grey pixels that only make the mark look dirty.

    python3 launcher/assets/make_icon.py
"""
from PIL import Image, ImageDraw

BG = (0x14, 0x11, 0x0e, 255)
BRAND = (0xd9, 0xa4, 0x41, 255)
MUTED = (0xb3, 0xa8, 0x94, 255)

DIAMOND = [(24, 3), (26.5, 8), (24, 13), (21.5, 8)]
UPPER = [(24, 15), (38, 30), (30.5, 30), (24, 23), (17.5, 30), (10, 30)]
LOWER = [(24, 29), (38, 44), (30.5, 44), (24, 37), (17.5, 44), (10, 44)]

SIZES = [16, 24, 32, 48, 64, 128, 256]
SS = 8          # supersampling: drawn this many times over, then averaged down


def draw(size, full):
    """One icon at `size` px. `full` keeps the diamond and its spacing."""
    n = size * SS
    im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, n - 1, n - 1], radius=n * 0.20, fill=BG)

    # The artwork's own bounds on the 48 grid, fitted into the square with a
    # margin. Without the diamond the mark starts at y=15 instead of y=3.
    top = 3 if full else 15
    height = 44 - top
    inset = 0.20 if full else 0.24
    k = n * (1 - 2 * inset) / height
    ox = n / 2 - 24 * k
    oy = n * inset - top * k

    def poly(points, colour):
        d.polygon([(ox + x * k, oy + y * k) for x, y in points], fill=colour)

    if full:
        poly(DIAMOND, BRAND)
    poly(UPPER, BRAND)
    poly(LOWER, MUTED)
    return im.resize((size, size), Image.LANCZOS)


def main():
    frames = [draw(s, s >= 48) for s in SIZES]
    # Pillow writes every frame it is given into one .ico; the largest carries
    # the file and the rest are listed in sizes.
    frames[-1].save("launcher/assets/lava.ico", format="ICO",
                    sizes=[(s, s) for s in SIZES],
                    append_images=frames[:-1])
    print("lava.ico:", ", ".join("%dx%d" % (s, s) for s in SIZES))


if __name__ == "__main__":
    main()
