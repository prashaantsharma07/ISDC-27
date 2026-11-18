"""Generate the TeamMARS-PID-tuner app icon (bottle-green glass tile, bone panel, vermilion step response)."""
import math
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

BOTTLE, DEEP, BONE, VERM = (0, 106, 78), (0, 67, 47), (227, 218, 201), (227, 66, 52)
S, ss = 256, 4
N = S * ss
img = Image.new("RGBA", (N, N), (0, 0, 0, 0))
# shadow
sh = Image.new("RGBA", (N, N), (0, 0, 0, 0))
ImageDraw.Draw(sh).rounded_rectangle((24, 40, N - 24, N - 8), 200, fill=(0, 40, 28, 120))
img = Image.alpha_composite(img, sh.filter(ImageFilter.GaussianBlur(24)))
# glass tile body (gradient)
mask = Image.new("L", (N, N), 0)
box = (16, 16, N - 16, N - 40)
ImageDraw.Draw(mask).rounded_rectangle(box, 200, fill=255)
grad = Image.new("RGBA", (N, N))
gd = ImageDraw.Draw(grad)
for y in range(N):
    t = y / N
    gd.line([(0, y), (N, y)], fill=tuple(round(a + (b - a) * t) for a, b in zip((31, 150, 115), DEEP)) + (255,))
tile = Image.new("RGBA", (N, N), (0, 0, 0, 0))
tile.paste(grad, (0, 0), mask)
img = Image.alpha_composite(img, tile)
# bone panel with grid
d = ImageDraw.Draw(img)
panel = (150, 150, N - 150, N - 330)
d.rounded_rectangle(panel, 70, fill=BONE + (240,))
for i in range(1, 4):
    x = panel[0] + (panel[2] - panel[0]) * i / 4
    y = panel[1] + (panel[3] - panel[1]) * i / 4
    d.line([(x, panel[1] + 30), (x, panel[3] - 30)], fill=(190, 178, 156, 255), width=4)
    d.line([(panel[0] + 30, y), (panel[2] - 30, y)], fill=(190, 178, 156, 255), width=4)
# setpoint line (bottle) and damped step response (vermilion)
x0, x1 = panel[0] + 60, panel[2] - 60
yb, yt = panel[3] - 90, panel[1] + 170
d.line([(x0, yb), (x0 + 60, yb), (x0 + 60, yt), (x1, yt)], fill=BOTTLE + (255,), width=18, joint="curve")
pts = []
for i in range(200):
    t = i / 199
    x = x0 + (x1 - x0) * t
    k = t * 9
    resp = 0 if t < 0.04 else 1 - math.exp(-0.9 * (k - 0.36)) * math.cos(2.6 * (k - 0.36))
    pts.append((x, yb - (yb - yt) * resp))
d.line(pts, fill=VERM + (255,), width=26, joint="curve")
# sheen on the top half of the tile
sheen = Image.new("RGBA", (N, N), (0, 0, 0, 0))
sd = ImageDraw.Draw(sheen)
for y in range(16, N // 2):
    a = round(110 * (1 - (y - 16) / (N // 2 - 16)) ** 2)
    sd.line([(0, y), (N, y)], fill=(255, 255, 255, a))
clip = Image.new("RGBA", (N, N), (0, 0, 0, 0))
clip.paste(sheen, (0, 0), mask)
img = Image.alpha_composite(img, clip)
d = ImageDraw.Draw(img)
# rims
d.rounded_rectangle(box, 200, outline=DEEP + (255,), width=8)
d.rounded_rectangle((box[0] + 10, box[1] + 10, box[2] - 10, box[3] - 10), 190, outline=(255, 255, 255, 120), width=6)
# label
try:
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 120)
    text = "MARS"
    w = d.textlength(text, font=font)
    d.text(((N - w) / 2, N - 300), text, font=font, fill=BONE + (255,))
except OSError:
    pass
img.resize((S, S), Image.LANCZOS).save(sys.argv[1])
print("icon written", sys.argv[1])
