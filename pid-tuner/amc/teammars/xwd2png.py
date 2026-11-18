"""Convert a 24/32-bit ZPixmap XWD dump to PNG (dev helper for theme screenshots)."""
import struct, sys
from PIL import Image
d = open(sys.argv[1], "rb").read()
h = struct.unpack(">25I", d[:100])
hsize, w, hgt, bpl, ncolors = h[0], h[4], h[5], h[12], h[19]
off = hsize + ncolors * 12
order = h[7]  # byte_order 0=LSB
raw = d[off:off + bpl * hgt]
img = Image.frombuffer("RGBX", (w, hgt), raw, "raw", "BGRX" if order == 0 else "XRGB", bpl, 1).convert("RGB")
img.save(sys.argv[2])
print(w, hgt)
