#!/usr/bin/env python3
"""Regenerates every image asset for the link hub (headshot, OG card, favicons, QR, wallpapers).

Not part of the site runtime. Needs: pillow, segno, fonttools.
Fonts: static TTF instances of Fraunces 300 and DM Mono 300/400 (from @fontsource, converted
from .woff) in FONT_DIR.

  FONT_DIR=/path/to/ttf HEADSHOT=/path/to/Brodie\ Meah.PNG SITE_URL=https://brodiemeah.netlify.app \
  python3 tools/make_assets.py
"""
import os
from pathlib import Path
from PIL import Image, ImageChops, ImageDraw, ImageFont
import segno
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
FONT_DIR = Path(os.environ["FONT_DIR"])
HEADSHOT = os.environ["HEADSHOT"]
SITE_URL = os.environ.get("SITE_URL", "https://brodiemeah.netlify.app").rstrip("/")
QR_URL = f"{SITE_URL}/?src=pep-nov26"

PARCH = (244, 240, 232)
INK = (26, 23, 20)
STONE = (155, 145, 137)
NAVY = (29, 52, 97)

FRAUNCES = str(FONT_DIR / "fraunces-latin-300-normal.ttf")
MONO = str(FONT_DIR / "dm-mono-latin-400-normal.ttf")


def font(path, size):
    return ImageFont.truetype(path, size)


def circle_headshot(size):
    """Warm-graded, circle-cropped headshot as RGBA at size x size."""
    img = Image.open(HEADSHOT).convert("RGB")
    # The studio wall is ~245, not 255: lift so it clips to white before grading.
    img = img.point(lambda v: min(255, round(v * 1.045)))
    # Multiply by Parchment: pure white becomes exactly #F4F0E8, skin picks up a light warmth.
    img = ImageChops.multiply(img, Image.new("RGB", img.size, PARCH))
    cx, cy, r = 627, 560, 560
    img = img.crop((cx - r, max(cy - r, 0), cx + r, max(cy - r, 0) + 2 * r))
    img = img.resize((size, size), Image.LANCZOS)
    ss = 4
    mask = Image.new("L", (size * ss, size * ss), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size * ss - 1, size * ss - 1), fill=255)
    mask = mask.resize((size, size), Image.LANCZOS)
    img = img.convert("RGBA")
    img.putalpha(mask)
    return img


def tracked(draw, xy, text, fnt, fill, tracking=0.0, anchor="l"):
    """Draw text with letter-spacing. anchor 'l' = xy is left, 'm' = xy is centre. y is baseline-top."""
    widths = [fnt.getlength(c) + tracking for c in text]
    total = sum(widths) - tracking
    x, y = xy
    if anchor == "m":
        x -= total / 2
    for c, w in zip(text, widths):
        draw.text((x, y), c, font=fnt, fill=fill)
        x += w
    return total


# ---------- headshot ----------
for px in (400, 800):
    circle_headshot(px).save(ROOT / "img" / f"headshot-{px}.webp", "WEBP", quality=84, method=6)

# ---------- OG card 1200x630 ----------
W, H = 1200, 630
og = Image.new("RGB", (W, H), PARCH)
d = ImageDraw.Draw(og)
D = 400
shot = circle_headshot(D)
og.paste(shot, (90, (H - D) // 2), shot)
tx = 90 + D + 80
name_f = font(FRAUNCES, 104)
d.text((tx, 200), "Brodie Meah", font=name_f, fill=INK)
d.rectangle((tx, 338, W - 90, 339), fill=NAVY)  # 2px rule at OG scale
tracked(d, (tx, 372), "FOUNDER · OPERATOR · INVESTOR", font(MONO, 24), STONE, tracking=3.2)
og.save(ROOT / "og-image.png", optimize=True)

# ---------- favicon / apple-touch-icon: BM monogram ----------
def monogram(size, pad=0.0):
    im = Image.new("RGB", (size, size), PARCH)
    dd = ImageDraw.Draw(im)
    f = font(FRAUNCES, int(size * 0.5))
    bb = dd.textbbox((0, 0), "BM", font=f)
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    dd.text(((size - w) / 2 - bb[0], (size - h) / 2 - bb[1]), "BM", font=f, fill=INK)
    return im

monogram(180).save(ROOT / "apple-touch-icon.png", optimize=True)
monogram(512).resize((48, 48), Image.LANCZOS).save(
    ROOT / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)]
)
monogram(192).save(ROOT / "icon-192.png", optimize=True)

# favicon.svg: glyph outlines as paths so it needs no font at runtime
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen

tt = TTFont(FRAUNCES)
gs, cmap, hmtx = tt.getGlyphSet(), tt.getBestCmap(), tt["hmtx"]
upm = tt["head"].unitsPerEm
cap = tt["OS/2"].sCapHeight
scale = (512 * 0.36) / cap  # cap height = 36% of the tile
adv = [hmtx[cmap[ord(c)]][0] for c in "BM"]
total = sum(adv) * scale
x = (512 - total) / 2
base = 512 / 2 + (cap * scale) / 2
paths = []
for c, a in zip("BM", adv):
    pen = SVGPathPen(gs)
    gs[cmap[ord(c)]].draw(TransformPen(pen, (scale, 0, 0, -scale, x, base)))
    paths.append(pen.getCommands())
    x += a * scale
svg = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">'
    '<rect width="512" height="512" fill="#F4F0E8"/>'
    f'<path fill="#1A1714" d="{" ".join(paths)}"/></svg>'
)
(ROOT / "favicon.svg").write_text(svg)

# ---------- QR ----------
qr = segno.make(QR_URL, error="h", micro=False)
qr.save(ROOT / "qr.svg", scale=10, border=4, dark="#1A1714", light="#F4F0E8", xmldecl=False)
qr.save(ROOT / "qr.png", scale=24, border=4, dark="#1A1714", light="#F4F0E8")
matrix = [list(row) for row in qr.matrix]
n = len(matrix)


def qr_image(target_px):
    scale = max(1, round(target_px / n))
    im = Image.new("RGB", (n * scale, n * scale), PARCH)
    dd = ImageDraw.Draw(im)
    for r, row in enumerate(matrix):
        for c, v in enumerate(row):
            if v:
                dd.rectangle((c * scale, r * scale, (c + 1) * scale - 1, (r + 1) * scale - 1), fill=INK)
    return im


# ---------- lock-screen wallpapers ----------
def wallpaper(w, h, out):
    wp = Image.new("RGB", (w, h), PARCH)
    dd = ImageDraw.Draw(wp)
    q = qr_image(w * 0.45)  # modules only; parchment margin around it is the quiet zone
    name_f = font(FRAUNCES, round(w * 0.072))
    lab_f = font(MONO, round(w * 0.0245))
    name_h, gap, lab_h = round(w * 0.072 * 1.0), round(w * 0.05), round(w * 0.0245)
    block = name_h + gap + q.height + gap + lab_h
    top_safe, bot_safe = h * 0.35, h * 0.88
    y0 = round((top_safe + bot_safe) / 2 - block / 2)
    # name, centred, optical tweak via bbox
    bb = dd.textbbox((0, 0), "Brodie Meah", font=name_f)
    dd.text(((w - (bb[2] - bb[0])) / 2 - bb[0], y0 - bb[1]), "Brodie Meah", font=name_f, fill=INK)
    qy = y0 + name_h + gap
    wp.paste(q, ((w - q.width) // 2, qy))
    ly = qy + q.height + gap
    lb = dd.textbbox((0, 0), "S", font=lab_f)
    tracked(dd, (w / 2, ly - lb[1]), "SCAN TO CONNECT", lab_f, STONE, tracking=w * 0.006, anchor="m")
    wp.save(ROOT / "wallpapers" / out, optimize=True)
    return dict(out=out, qr_px=q.width, qr_pct=round(q.width / w * 100, 1), qr_top=qy, qr_bottom=qy + q.height,
                top_safe=round(top_safe), bottom_safe=round(bot_safe + h * 0.0), block=(y0, ly + lab_h))

for spec in [(1179, 2556, "lockscreen-1179x2556.png"), (1290, 2796, "lockscreen-1290x2796.png")]:
    print(wallpaper(*spec))
print("QR modules:", n, "url:", QR_URL)
