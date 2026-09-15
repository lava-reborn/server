import struct, zlib, io
p = "/mnt/c/Users/gmkrt/OneDrive/Desktop/LAVA/res/main.swf"
raw = open(p, "rb").read()
body = zlib.decompress(raw[8:]) if raw[:3] == b"CWS" else raw[8:]
nbits = body[0] >> 3
bits = "".join(format(b, "08b") for b in body[:(5 + nbits * 4 + 7) // 8])
vals = [int(bits[5 + i * nbits:5 + (i + 1) * nbits], 2) for i in range(4)]
xmin, xmax, ymin, ymax = [v // 20 for v in vals]
print("родной размер сцены main.swf: %d x %d" % (xmax - xmin, ymax - ymin))
off = (5 + nbits * 4 + 7) // 8
fps = struct.unpack("<H", body[off:off+2])[0] / 256.0
print("кадров в секунду: %.1f" % fps)
