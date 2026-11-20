#!/usr/bin/env python3
"""Generate TeamMARS colour LUTs (.cube, 33^3). Original work, free to use (CC0).

LUTs change colour and contrast (they cannot add frames or remove motion blur):
they make a washed-out or dark FPV feed easier to read and help objects stand out.
"""

from pathlib import Path

import numpy as np

N = 33
OUT = Path(__file__).resolve().parent.parent / "web" / "luts"


def grid():
    v = np.linspace(0, 1, N)
    b, g, r = np.meshgrid(v, v, v, indexing="ij")  # .cube order: red changes fastest
    return np.stack([r, g, b], -1)


def luma(c):
    return (c * [0.2126, 0.7152, 0.0722]).sum(-1, keepdims=True)


def sat(c, s):
    y = luma(c)
    return y + (c - y) * s


def s_curve(c, amount):
    return c + amount * (c - c ** 2) * (2 * c - 1) * -1 + amount * 0  # gentle S (keeps 0 and 1)


def contrast(c, k):
    return np.clip(0.5 + (c - 0.5) * k, 0, 1)


def gamma(c, g):
    return np.clip(c, 0, 1) ** g


def write(name, title, c):
    OUT.mkdir(parents=True, exist_ok=True)
    c = np.clip(c, 0, 1)
    lines = [f'TITLE "{title}"', "# TeamMARS LUT - original, CC0", f"LUT_3D_SIZE {N}", "DOMAIN_MIN 0 0 0", "DOMAIN_MAX 1 1 1"]
    for row in c.reshape(-1, 3):
        lines.append(f"{row[0]:.6f} {row[1]:.6f} {row[2]:.6f}")
    (OUT / f"{name}.cube").write_text("\n".join(lines) + "\n")
    print("wrote", name)


c0 = grid()
write("neutral", "Neutral", c0)
write("clarity", "Clarity", sat(contrast(gamma(c0, 0.95), 1.18), 1.15))
# haze cut: pull the grey veil out (black point down), add contrast and colour, slightly cooler highlights
haze = np.clip((c0 - 0.06) / 0.94, 0, 1)
haze = sat(contrast(haze, 1.25), 1.3) * [0.98, 1.0, 1.03]
write("haze_cut", "Haze Cut", haze)
# low light: lift shadows a lot, protect highlights
write("low_light", "Low Light", sat(1 - (1 - gamma(c0, 0.6)) ** 1.1, 1.1))
# ground contrast: mute greens/browns of the ground, boost everything else so man-made objects pop
y = luma(c0)
chroma = c0 - y
greenish = np.clip((c0[..., 1:2] - np.maximum(c0[..., 0:1], c0[..., 2:3])) * 4, 0, 1)
brownish = np.clip((c0[..., 0:1] - c0[..., 2:3]) * 3, 0, 1) * np.clip(1 - np.abs(c0[..., 0:1] - c0[..., 1:2]) * 4, 0, 1)
damp = 1 - 0.55 * np.clip(greenish + brownish, 0, 1)
write("ground_contrast", "Ground Contrast", contrast(y + chroma * (1.5 * damp), 1.12))
write("mono_detail", "Mono Detail", np.repeat(contrast(gamma(luma(c0), 0.9), 1.3), 3, -1))
