"""
TeamMARS "liquid glass" ttk theme: bottle green and bone, with a hint of vermilion.

Every window in the application calls ``apply_glass_theme(root)`` instead of
``ttk.Style().theme_use("alt")``. Only the look changes; widget behaviour and the
backend are untouched.

Design notes
------------
* Tk cannot blur what is behind a widget, so the glass effect is drawn: each glass
  element is a small rounded image with a vertical gradient body, a bright top sheen,
  a 1px white inner rim and a soft outer edge. Images are 9-slice stretched by ttk,
  so they are created once per Tk interpreter and cost nothing at runtime.
* Entry / Combobox / Spinbox fields stay colour-based (clam field element) on purpose:
  the parameter editor colours fields light-blue (default value), orange-red (below
  limit) and red (above limit) through ``fieldbackground``. Image-based fields would
  silently hide those safety cues.
* Vermilion is used sparingly: keyboard focus rims, the selected tab underline,
  progress bars and the "pressed" sheen.

This file is part of TeamMARS-PID-tuner(DRONE), a fork of ArduPilot Methodic Configurator.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

# ruff: noqa: N806, PLR0915  (drawing code uses W/H/R/S for supersampled sizes; theme setup is one long table)

from __future__ import annotations

import base64
import contextlib
import io
import tkinter as tk
from tkinter import ttk

try:
    from PIL import Image, ImageDraw, ImageFilter
except ImportError:  # pragma: no cover - Pillow is a hard dependency, but never crash the UI over looks
    Image = None  # type: ignore[assignment]

THEME_NAME = "teammars_glass"

# ---------------------------------------------------------------- palette
BOTTLE = "#006A4E"  # bottle green (primary)
BOTTLE_DEEP = "#00432F"
BOTTLE_DARK = "#00553E"
BOTTLE_LIGHT = "#2E8B6E"
BOTTLE_MIST = "#9CC2B3"  # bottle green seen through frosted glass
BONE = "#E3DAC9"  # bone (primary surface)
BONE_LIGHT = "#F1EBE0"
BONE_DARK = "#CEC3AE"
FROST = "#FBF8F2"  # frosted-glass field / list background
VERMILION = "#E34234"  # accent, used sparingly
VERMILION_LIGHT = "#F07A6E"
INK = "#1D2A24"  # main text: near-black with a green cast
INK_MUTED = "#6B746C"

# Semantic field colours used by the parameter editor (meaning must not change)
FIELD_DEFAULT_VALUE = "#CFE8F3"  # was "light blue": parameter equals its default
FIELD_BELOW_LIMIT = "orangered"
FIELD_ABOVE_LIMIT = "red3"

# Keep PhotoImages alive per Tcl interpreter (ttk does not hold references)
_IMAGES: dict[str, dict[str, tk.PhotoImage]] = {}


# ---------------------------------------------------------------- image helpers
def _rgba(hex_color: str, alpha: float = 1.0) -> tuple[int, int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), round(255 * alpha)


def _mix(c1: str, c2: str, t: float) -> str:
    a, b = _rgba(c1), _rgba(c2)
    return "#{:02x}{:02x}{:02x}".format(*(round(a[i] + (b[i] - a[i]) * t) for i in range(3)))


def _glass_png(  # noqa: PLR0913 # pylint: disable=too-many-arguments, too-many-locals, too-many-statements
    w: int,
    h: int,
    radius: int,
    top: str,
    bottom: str,
    *,
    edge: str,
    edge_alpha: float = 1.0,
    sheen: float = 0.45,
    rim: float = 0.7,
    shadow: float = 0.18,
    stripe: str | None = None,
    ring: str | None = None,
    mid: str | None = None,
    slice_px: int | None = None,
) -> bytes:
    """
    Draw one glass tile (4x supersampled, then downsampled for smooth corners).

    ttk *tiles* the centre of an image element instead of stretching it, so all shading
    lives inside the border slices (``slice_px`` from each edge) and the centre rows are
    one flat colour (``mid``). That keeps large panels free of banding.
    """
    ss = 4
    W, H, R = w * ss, h * ss, radius * ss
    sl = (slice_px if slice_px is not None else max(radius, h // 2 - 1)) * ss
    pad = ss  # 1px outer margin for the soft shadow / ring
    mid_c = mid or _mix(top, bottom, 0.5)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    # soft drop shadow (bottom edge only, gives thickness)
    if shadow > 0:
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(sh).rounded_rectangle((pad, pad + ss, W - pad - 1, H - 1), R, fill=_rgba(BOTTLE_DEEP, shadow))
        img = Image.alpha_composite(img, sh.filter(ImageFilter.GaussianBlur(ss)))

    body_box = (pad, pad, W - pad - 1, H - pad - ss)
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle(body_box, R, fill=255)

    t_rgba, m_rgba, b_rgba = _rgba(top), _rgba(mid_c), _rgba(bottom)

    def lerp(a: tuple, b: tuple, f: float) -> tuple:
        return tuple(round(a[i] + (b[i] - a[i]) * f) for i in range(4))

    grad = Image.new("RGBA", (W, H))
    gd = ImageDraw.Draw(grad)
    for y in range(H):
        if y < sl:
            c = lerp(t_rgba, m_rgba, y / max(1, sl))
        elif y >= H - sl:
            c = lerp(m_rgba, b_rgba, (y - (H - sl)) / max(1, sl - 1))
        else:
            c = m_rgba
        gd.line([(0, y), (W, y)], fill=c)
    body = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    body.paste(grad, (0, 0), mask)
    img = Image.alpha_composite(img, body)

    # specular sheen: white at the top edge, faded out before the top slice ends
    if sheen > 0:
        sheen_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        sd = ImageDraw.Draw(sheen_layer)
        top_y, end_y = body_box[1], max(body_box[1] + 1, sl - ss)
        for y in range(int(top_y), int(end_y)):
            f = (y - top_y) / max(1, end_y - top_y)
            sd.line([(0, y), (W, y)], fill=(255, 255, 255, round(255 * sheen * (1 - f) ** 1.6)))
        clipped = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        clipped.paste(sheen_layer, (0, 0), mask)
        img = Image.alpha_composite(img, clipped)

    # optional accent stripe along the bottom (selected tab)
    if stripe:
        st = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(st).rectangle((0, body_box[3] - 3 * ss, W, body_box[3]), fill=_rgba(stripe))
        clipped = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        clipped.paste(st, (0, 0), mask)
        img = Image.alpha_composite(img, clipped)

    d = ImageDraw.Draw(img)
    d.rounded_rectangle(body_box, R, outline=_rgba(edge, edge_alpha), width=ss)
    if rim > 0:  # inner bright rim, strongest along the top
        inset = ss
        rim_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(rim_layer).rounded_rectangle(
            (body_box[0] + inset, body_box[1] + inset, body_box[2] - inset, body_box[3] - inset),
            max(0, R - inset),
            outline=(255, 255, 255, round(255 * rim)),
            width=max(1, ss // 2 + 1),
        )
        img = Image.alpha_composite(img, rim_layer)
        d = ImageDraw.Draw(img)
    if ring:
        d.rounded_rectangle(body_box, R, outline=_rgba(ring), width=2 * ss)

    out = img.resize((w, h), Image.LANCZOS)
    buf = io.BytesIO()
    out.save(buf, format="PNG")
    return buf.getvalue()


def _indicator_png(size: int, kind: str, *, checked: bool, active: bool, disabled: bool) -> bytes:
    """Checkbox / radio indicator as a small glass bead."""
    ss = 4
    S = size * ss
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    box = (ss, ss, S - ss - 1, S - ss - 1)
    edge = BOTTLE_MIST if disabled else (VERMILION if active else BOTTLE)
    if checked:
        fill_top, fill_bottom = (BOTTLE_MIST, BOTTLE_MIST) if disabled else (BOTTLE_LIGHT, BOTTLE_DEEP)
    else:
        fill_top, fill_bottom = FROST, BONE_LIGHT
    mask = Image.new("L", (S, S), 0)
    md = ImageDraw.Draw(mask)
    if kind == "radio":
        md.ellipse(box, fill=255)
    else:
        md.rounded_rectangle(box, 3 * ss, fill=255)
    grad = Image.new("RGBA", (S, S))
    gd = ImageDraw.Draw(grad)
    a, b = _rgba(fill_top), _rgba(fill_bottom)
    for y in range(S):
        t = y / (S - 1)
        gd.line([(0, y), (S, y)], fill=tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(4)))
    img.paste(grad, (0, 0), mask)
    # sheen
    sheen = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(sheen).ellipse((box[0] + 2 * ss, box[1] + ss, box[2] - 2 * ss, box[1] + S // 2), fill=(255, 255, 255, 90))
    clipped = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    clipped.paste(sheen, (0, 0), mask)
    img = Image.alpha_composite(img, clipped)
    d = ImageDraw.Draw(img)
    if kind == "radio":
        d.ellipse(box, outline=_rgba(edge), width=ss + ss // 2)
        if checked:
            c = S // 2
            r = S // 6
            d.ellipse((c - r, c - r, c + r, c + r), fill=_rgba(BONE_LIGHT))
    else:
        d.rounded_rectangle(box, 3 * ss, outline=_rgba(edge), width=ss + ss // 2)
        if checked:
            d.line(
                [(S * 0.27, S * 0.52), (S * 0.43, S * 0.68), (S * 0.74, S * 0.33)],
                fill=_rgba(BONE_LIGHT),
                width=2 * ss,
                joint="curve",
            )
    out = img.resize((size, size), Image.LANCZOS)
    buf = io.BytesIO()
    out.save(buf, format="PNG")
    return buf.getvalue()


def _photo(root: tk.Misc, key: str, png: bytes) -> tk.PhotoImage:
    store = _IMAGES.setdefault(str(root.tk), {})
    if key not in store:
        store[key] = tk.PhotoImage(master=root, data=base64.b64encode(png).decode("ascii"))
    return store[key]


def _scale(root: tk.Misc) -> float:
    try:
        return max(1.0, min(3.0, float(root.winfo_fpixels("1i")) / 96.0))
    except (tk.TclError, AttributeError, TypeError, ValueError, RuntimeError):
        return 1.0


# ---------------------------------------------------------------- theme
def _create_theme(style: ttk.Style, root: tk.Misc) -> None:  # pylint: disable=too-many-locals, too-many-statements
    k = _scale(root)
    px = lambda v: max(1, round(v * k))  # noqa: E731

    style.theme_create(THEME_NAME, parent="clam")
    style.theme_use(THEME_NAME)

    # ---- global defaults
    style.configure(
        ".",
        background=BONE,
        foreground=INK,
        troughcolor=BONE_DARK,
        bordercolor=BOTTLE_MIST,
        lightcolor=BONE_LIGHT,
        darkcolor=BONE_DARK,
        focuscolor=VERMILION,
        selectbackground=BOTTLE,
        selectforeground=BONE_LIGHT,
        insertcolor=BOTTLE_DEEP,
        fieldbackground=FROST,
        arrowcolor=BOTTLE,
    )
    style.map(".", foreground=[("disabled", INK_MUTED)])

    have_pil = Image is not None
    if not have_pil:  # flat fallback: same palette, no glass images
        style.configure("TButton", background=BOTTLE, foreground=BONE_LIGHT, padding=(px(10), px(4)))
        style.map("TButton", background=[("pressed", BOTTLE_DEEP), ("active", BOTTLE_LIGHT)])
        return

    def img(key: str, w: int, h: int, r: int, top: str, bottom: str, **kw) -> tk.PhotoImage:
        return _photo(root, key, _glass_png(px(w), px(h), px(r), top, bottom, **kw))

    # ---- buttons: bottle-green glass, vermilion focus rim
    b_norm = img("btn", 40, 30, 9, "#13896A", BOTTLE_DARK, edge=BOTTLE_DEEP, sheen=0.42, rim=0.45)
    b_hover = img("btn_h", 40, 30, 9, "#1FA07C", BOTTLE, edge=BOTTLE_DEEP, sheen=0.5, rim=0.55)
    b_press = img("btn_p", 40, 30, 9, BOTTLE_DEEP, "#0A5E45", edge=BOTTLE_DEEP, sheen=0.12, rim=0.2, shadow=0.05)
    b_focus = img("btn_f", 40, 30, 9, "#13896A", BOTTLE_DARK, edge=BOTTLE_DEEP, sheen=0.42, rim=0.45, ring=VERMILION)
    b_dis = img("btn_d", 40, 30, 9, BONE_LIGHT, BONE_DARK, edge=BONE_DARK, sheen=0.3, rim=0.6, shadow=0.06)
    border = px(14)
    style.element_create(
        "glass.button",
        "image",
        b_norm,
        ("disabled", b_dis),
        ("pressed", b_press),
        ("active", b_hover),
        ("focus", b_focus),
        border=(border, border, border, border),
        padding=(px(4), px(2), px(4), px(3)),
        sticky="nsew",
    )
    style.layout(
        "TButton",
        [
            (
                "glass.button",
                {
                    "sticky": "nsew",
                    "children": [("Button.padding", {"sticky": "nsew", "children": [("Button.label", {"sticky": "nsew"})]})],
                },
            )
        ],
    )
    style.configure("TButton", foreground=BONE_LIGHT, padding=(px(8), px(5)), anchor="center")
    style.map("TButton", foreground=[("disabled", INK_MUTED), ("pressed", BONE)])
    style.configure("narrow.TButton", padding=(px(2), px(1)))

    # ---- tool / toggle buttons reuse the same glass
    style.layout("Toolbutton", style.layout("TButton"))
    style.configure("Toolbutton", foreground=BONE_LIGHT, padding=(px(6), px(3)))

    # ---- glass cards for label frames, with a bottle-green chip as caption
    card = img(
        "card", 48, 48, 12, BONE_LIGHT, BONE_DARK, edge=BOTTLE_MIST, sheen=0.6, rim=0.9, shadow=0.14, mid=BONE, slice_px=12
    )
    cb = px(12)
    style.element_create(
        "glass.card", "image", card, border=(cb, cb, cb, cb), padding=(px(4), px(6), px(4), px(4)), sticky="nsew"
    )
    style.layout("TLabelframe", [("glass.card", {"sticky": "nsew"})])
    style.configure("TLabelframe", background=BONE, padding=(px(8), px(8)), labelmargins=(px(10), 0, px(10), px(2)))
    chip = img("chip", 32, 22, 11, "#13896A", BOTTLE_DARK, edge=BOTTLE_DEEP, sheen=0.4, rim=0.4, shadow=0.0)
    style.element_create(
        "glass.chip", "image", chip, border=(px(11), px(10), px(11), px(10)), padding=(px(2), px(1)), sticky="nsew"
    )
    style.layout(
        "TLabelframe.Label",
        [
            (
                "glass.chip",
                {
                    "sticky": "nsew",
                    "children": [("Label.padding", {"sticky": "nsew", "children": [("Label.text", {"sticky": "nsew"})]})],
                },
            )
        ],
    )
    style.configure("TLabelframe.Label", foreground=BONE_LIGHT, background=BONE, padding=(px(8), px(1)))
    # captions passed to LabelFrame(labelwidget=...) get the same chip
    style.layout("Caption.TLabel", style.layout("TLabelframe.Label"))
    style.configure("Caption.TLabel", foreground=BONE_LIGHT, background=BONE, padding=(px(8), px(1)))
    style.configure("Optional.TLabelframe.Label", foreground=BONE)
    style.configure("Legend.TLabelframe.Label", foreground=BONE_LIGHT)

    # ---- notebook: frosted tabs, selected tab is bottle green with a vermilion underline
    tab = img("tab", 40, 30, 9, FROST, BONE, edge=BOTTLE_MIST, sheen=0.5, rim=0.9, shadow=0.08)
    tab_hover = img("tab_h", 40, 30, 9, "#FFFFFF", BONE_LIGHT, edge=BOTTLE_LIGHT, sheen=0.6, rim=0.9, shadow=0.08)
    tab_sel = img("tab_s", 40, 30, 9, "#13896A", BOTTLE_DARK, edge=BOTTLE_DEEP, sheen=0.4, rim=0.45, stripe=VERMILION)
    tb = px(14)
    style.element_create(
        "glass.tab",
        "image",
        tab,
        ("selected", tab_sel),
        ("active", tab_hover),
        border=(tb, tb, tb, tb),
        padding=(px(4), px(2), px(4), px(4)),
        sticky="nsew",
    )
    style.layout(
        "TNotebook.Tab",
        [
            (
                "glass.tab",
                {
                    "sticky": "nsew",
                    "children": [("Notebook.padding", {"sticky": "nsew", "children": [("Notebook.label", {"sticky": ""})]})],
                },
            )
        ],
    )
    style.configure("TNotebook.Tab", padding=(px(10), px(3)), foreground=INK)
    style.map("TNotebook.Tab", foreground=[("selected", BONE_LIGHT)], expand=[("selected", (0, 0, 0, 0))])
    style.element_create("glass.pane", "image", card, border=(cb, cb, cb, cb), padding=(px(4), px(4)), sticky="nsew")
    style.layout("TNotebook", [("glass.pane", {"sticky": "nsew"})])
    style.configure("TNotebook", background=BONE, tabmargins=(px(4), px(4), px(4), 0), padding=px(4))

    # ---- treeview: frosted rows, glass bottle-green headings
    head = img("head", 40, 26, 0, "#13896A", BOTTLE_DARK, edge=BOTTLE_DEEP, sheen=0.35, rim=0.35, shadow=0.0)
    head_h = img("head_h", 40, 26, 0, "#1FA07C", BOTTLE, edge=BOTTLE_DEEP, sheen=0.45, rim=0.45, shadow=0.0)
    style.element_create(
        "glass.heading",
        "image",
        head,
        ("active", head_h),
        border=(px(6), px(12), px(6), px(12)),
        padding=(px(2), px(1)),
        sticky="nsew",
    )
    style.layout(
        "Treeview.Heading",
        [
            (
                "glass.heading",
                {
                    "sticky": "nsew",
                    "children": [
                        (
                            "Treeheading.padding",
                            {
                                "sticky": "nsew",
                                "children": [
                                    ("Treeheading.image", {"side": "right", "sticky": ""}),
                                    ("Treeheading.text", {"sticky": "we"}),
                                ],
                            },
                        )
                    ],
                },
            )
        ],
    )
    style.configure("Treeview.Heading", foreground=BONE_LIGHT, padding=(px(4), px(3)))
    style.configure(
        "Treeview", background=FROST, fieldbackground=FROST, foreground=INK, bordercolor=BOTTLE_MIST, rowheight=px(24)
    )
    style.map("Treeview", background=[("selected", BOTTLE)], foreground=[("selected", BONE_LIGHT)])

    # ---- check / radio buttons: glass beads
    size = px(18)
    for kind, elem in (("check", "Checkbutton.indicator"), ("radio", "Radiobutton.indicator")):
        n = _photo(root, f"{kind}_0", _indicator_png(size, kind, checked=False, active=False, disabled=False))
        na = _photo(root, f"{kind}_0a", _indicator_png(size, kind, checked=False, active=True, disabled=False))
        c = _photo(root, f"{kind}_1", _indicator_png(size, kind, checked=True, active=False, disabled=False))
        ca = _photo(root, f"{kind}_1a", _indicator_png(size, kind, checked=True, active=True, disabled=False))
        d0 = _photo(root, f"{kind}_0d", _indicator_png(size, kind, checked=False, active=False, disabled=True))
        d1 = _photo(root, f"{kind}_1d", _indicator_png(size, kind, checked=True, active=False, disabled=True))
        style.element_create(
            f"glass.{kind}",
            "image",
            n,
            ("disabled", "selected", d1),
            ("disabled", d0),
            ("selected", "active", ca),
            ("selected", c),
            ("active", na),
            sticky="",
            padding=(0, 0, px(6), 0),
        )
        widget = "TCheckbutton" if kind == "check" else "TRadiobutton"
        style.layout(
            widget,
            [
                (
                    f"{'Checkbutton' if kind == 'check' else 'Radiobutton'}.padding",
                    {
                        "sticky": "nsew",
                        "children": [
                            (f"glass.{kind}", {"side": "left", "sticky": ""}),
                            (
                                f"{'Checkbutton' if kind == 'check' else 'Radiobutton'}.focus",
                                {
                                    "side": "left",
                                    "sticky": "",
                                    "children": [
                                        (f"{'Checkbutton' if kind == 'check' else 'Radiobutton'}.label", {"sticky": "nsew"})
                                    ],
                                },
                            ),
                        ],
                    },
                )
            ],
        )
        style.configure(widget, padding=(px(2), px(2)))
        style.configure(f"{widget}", indicatormargin=(0, 0, px(6), 0))
        style.map(widget, background=[("active", BONE)])
        _ = elem

    # ---- entry-like fields (colour based so semantic field colours keep working)
    for w in ("TEntry", "TCombobox", "TSpinbox"):
        style.configure(
            w,
            fieldbackground=FROST,
            foreground=INK,
            bordercolor=BOTTLE_MIST,
            lightcolor=FROST,
            darkcolor=BONE_LIGHT,
            padding=(px(5), px(3)),
            arrowsize=px(13),
        )
        style.map(
            w,
            bordercolor=[("focus", VERMILION), ("hover", BOTTLE_LIGHT)],
            lightcolor=[("focus", VERMILION_LIGHT)],
            fieldbackground=[("readonly", FROST), ("disabled", BONE_LIGHT)],
            foreground=[("disabled", INK_MUTED)],
            arrowcolor=[("disabled", BOTTLE_MIST), ("pressed", VERMILION), ("active", BOTTLE_LIGHT)],
            background=[("active", BONE_LIGHT), ("pressed", BONE_DARK)],
        )
    style.configure("TCombobox", background=BONE_LIGHT, selectbackground=FROST, selectforeground=INK)
    style.configure("TSpinbox", background=BONE_LIGHT)

    # ---- progress bars: vermilion glass on a bone trough
    for orient in ("Horizontal", "Vertical"):
        style.configure(
            f"{orient}.TProgressbar",
            background=VERMILION,
            lightcolor=VERMILION_LIGHT,
            darkcolor="#B8322A",
            troughcolor=BONE_DARK,
            bordercolor=BOTTLE_MIST,
            thickness=px(14),
        )

    # ---- scrollbars: slim bottle-green thumb
    for orient in ("Horizontal", "Vertical"):
        style.configure(
            f"{orient}.TScrollbar",
            background=BOTTLE_LIGHT,
            troughcolor=BONE,
            bordercolor=BONE,
            lightcolor="#4FA889",
            darkcolor=BOTTLE,
            arrowcolor=BONE_LIGHT,
            gripcount=0,
            arrowsize=px(14),
        )
        style.map(f"{orient}.TScrollbar", background=[("pressed", VERMILION), ("active", BOTTLE)])

    # ---- scale, separator, panes, sizegrip
    style.configure("TScale", background=BOTTLE, troughcolor=BONE_DARK, lightcolor=BOTTLE_LIGHT, darkcolor=BOTTLE_DEEP)
    style.map("TScale", background=[("active", VERMILION)])
    style.configure("TSeparator", background=BOTTLE_MIST)
    style.configure("Sash", sashthickness=px(6), gripcount=0, background=BONE_DARK)
    style.configure("TPanedwindow", background=BONE)

    # ---- labels
    style.configure("TLabel", background=BONE, foreground=INK)
    style.configure("TFrame", background=BONE)


def _apply_classic_tk_defaults(root: tk.Misc) -> None:
    """Defaults for classic (non-ttk) widgets: Toplevel, Text, Canvas, Listbox, Menu..."""
    opts = {
        "*Background": BONE,
        "*Foreground": INK,
        "*activeBackground": BOTTLE_LIGHT,
        "*activeForeground": BONE_LIGHT,
        "*selectBackground": BOTTLE,
        "*selectForeground": BONE_LIGHT,
        "*highlightColor": VERMILION,
        "*highlightBackground": BONE,
        "*insertBackground": BOTTLE_DEEP,
        "*troughColor": BONE_DARK,
        "*disabledForeground": INK_MUTED,
        "*Text.Background": FROST,
        "*Listbox.Background": FROST,
        "*Entry.Background": FROST,
        "*Spinbox.Background": FROST,
        "*Menu.Background": BONE_LIGHT,
        "*Menu.activeBackground": BOTTLE,
        "*Menu.activeForeground": BONE_LIGHT,
        "*Button.Background": BOTTLE,
        "*Button.Foreground": BONE_LIGHT,
        "*TCombobox*Listbox.Background": FROST,
        "*TCombobox*Listbox.selectBackground": BOTTLE,
        "*TCombobox*Listbox.selectForeground": BONE_LIGHT,
    }
    if not callable(getattr(root, "option_add", None)):
        return  # not a real Tk widget (e.g. a stand-in object)
    try:
        for pattern, value in opts.items():
            root.option_add(pattern, value, "widgetDefault")
    except (tk.TclError, RuntimeError, TypeError):
        return
    with contextlib.suppress(tk.TclError):
        root.configure(background=BONE)


def apply_glass_theme(root: tk.Misc | None = None) -> ttk.Style:
    """
    Activate the TeamMARS glass theme for the Tk interpreter that owns ``root``.

    Safe to call many times: the theme and its images are created once per interpreter.
    """
    style = ttk.Style(root)
    master = root if root is not None else style.master
    if THEME_NAME in style.theme_names():
        style.theme_use(THEME_NAME)
    else:
        try:
            _create_theme(style, master)
        except (tk.TclError, RuntimeError, AttributeError, TypeError, ValueError, OSError):
            # Never let styling take the application down; fall back to a plain theme.
            with contextlib.suppress(tk.TclError, RuntimeError, AttributeError):
                style.theme_use("clam")
    if master is not None:
        _apply_classic_tk_defaults(master)
    return style


def palette_mix(c1: str, c2: str, t: float) -> str:
    """Public helper for other frontends that need an in-between palette colour."""
    return _mix(c1, c2, t)
