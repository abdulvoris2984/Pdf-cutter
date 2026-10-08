"""Draw the app icon and the small UI images in assets/.

    python scripts/make_icons.py

Everything is drawn with Pillow at 4x size and scaled down, which gives smooth
(anti-aliased) edges.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ASSETS = Path(__file__).resolve().parent.parent / "assets"
SS = 4  # supersampling factor

INDIGO_LIGHT = (129, 140, 248)  # #818CF8
INDIGO = (99, 102, 241)  # #6366F1
INDIGO_DARK = (67, 56, 202)  # #4338CA
TEXT_LINE = (199, 210, 254)  # #C7D2FE


def gradient(size: int, start, end) -> Image.Image:
    """Diagonal gradient from top-left (start) to bottom-right (end)."""
    small = Image.new("RGB", (2, 2))
    small.putdata([start, _mix(start, end, 0.5), _mix(start, end, 0.5), end])
    return small.resize((size, size), Image.BILINEAR)


def _mix(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def make_page(size: int) -> Image.Image:
    """A white page with a folded corner and a few "text" lines."""
    page = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(page)
    left, right, top, bottom = 300 * SS, 724 * SS, 180 * SS, 844 * SS
    fold = 116 * SS
    draw.rounded_rectangle((left, top, right, bottom), radius=44 * SS, fill="white")
    draw.polygon([(right - fold, top - 1), (right + 1, top - 1), (right + 1, top + fold)], fill=(0, 0, 0, 0))
    draw.polygon([(right - fold, top), (right - fold, top + fold), (right, top + fold)], fill=TEXT_LINE)
    line_left = left + 64 * SS
    for y, line_right in [(320, 560), (390, 660), (450, 620), (580, 660), (640, 600), (700, 660), (760, 540)]:
        draw.rounded_rectangle(
            (line_left, y * SS, line_right * SS, y * SS + 22 * SS), radius=11 * SS, fill=TEXT_LINE
        )
    return page


def make_app_icon() -> Image.Image:
    size = 1024 * SS
    icon = Image.new("RGBA", (size, size), (0, 0, 0, 0))

    # Rounded-square background with a gradient.
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size - 1, size - 1), radius=230 * SS, fill=255)
    icon.paste(gradient(size, INDIGO_LIGHT, INDIGO_DARK), (0, 0), mask)

    # Slice the page in two and nudge the halves apart.
    page = make_page(size)
    cut_y, gap, shift = 515 * SS, 22 * SS, 20 * SS
    top_half = page.crop((0, 0, size, cut_y))
    bottom_half = page.crop((0, cut_y, size, size))
    pieces = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    pieces.alpha_composite(top_half, (-shift, -gap))
    pieces.alpha_composite(bottom_half, (shift, cut_y + gap))

    # Soft shadow under the pieces.
    shadow = Image.new("RGBA", (size, size), (30, 27, 75, 0))
    shadow.putalpha(pieces.split()[3].point(lambda a: a * 0.35))
    shadow = shadow.transform(shadow.size, Image.AFFINE, (1, 0, 0, 0, 1, -16 * SS))
    shadow = shadow.filter(ImageFilter.GaussianBlur(20 * SS))
    icon.alpha_composite(Image.composite(shadow, Image.new("RGBA", (size, size)), mask))
    icon.alpha_composite(pieces)

    # Dashed cut line through the gap.
    draw = ImageDraw.Draw(icon)
    dash, space, x = 52 * SS, 30 * SS, 150 * SS
    while x < 874 * SS:
        draw.rounded_rectangle(
            (x, cut_y - 7 * SS, min(x + dash, 874 * SS), cut_y + 7 * SS), radius=7 * SS, fill=(255, 255, 255, 235)
        )
        x += dash + space

    return icon.resize((1024, 1024), Image.LANCZOS)


def make_drop_icon() -> Image.Image:
    """Document outline with a plus sign, for the drop zone."""
    size = 96 * SS
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    w = 6 * SS
    x0, y0, x1, y1 = 20 * SS, 8 * SS, 76 * SS, 88 * SS
    fold = 20 * SS
    draw.rounded_rectangle((x0, y0, x1, y1), radius=9 * SS, outline=INDIGO, width=w)
    # Cut off the top-right corner and draw the folded flap.
    draw.polygon([(x1 - fold, y0 - 1), (x1 + 1, y0 - 1), (x1 + 1, y0 + fold)], fill=(0, 0, 0, 0))
    draw.line([(x1 - fold - w // 2, y0 + w // 2), (x1 - w // 2, y0 + fold + w // 2)], fill=INDIGO, width=w)
    draw.line([(x1 - fold, y0), (x1 - fold, y0 + fold), (x1, y0 + fold)], fill=INDIGO, width=w, joint="curve")
    cx, cy, arm = 48 * SS, 56 * SS, 13 * SS
    draw.rounded_rectangle((cx - arm, cy - w // 2, cx + arm, cy + w // 2), radius=w // 2, fill=INDIGO)
    draw.rounded_rectangle((cx - w // 2, cy - arm, cx + w // 2, cy + arm), radius=w // 2, fill=INDIGO)
    return img.resize((96, 96), Image.LANCZOS)


def main() -> None:
    ASSETS.mkdir(exist_ok=True)
    icon = make_app_icon()
    icon.save(ASSETS / "icon.png")
    icon.save(ASSETS / "icon.ico", sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    icon.save(ASSETS / "icon.icns")
    make_drop_icon().save(ASSETS / "drop.png")
    print("Wrote", ", ".join(sorted(p.name for p in ASSETS.iterdir())))


if __name__ == "__main__":
    main()
