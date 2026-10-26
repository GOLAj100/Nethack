"""Собирает graphics-мод ``backrooms``: спрайты 32x32 для символов tile_catalog.

Запуск из папки проекта::

    python tools/make_backrooms_tiles.py

Результат: ``mods/graphics/backrooms/`` — PNG с альфа-каналом, ``manifest.json``
(``tile_size: 32``), атлас ``sheet.png`` и превью ``preview.png``.
Скрипт офлайн, зависимость только от Pillow; повторный запуск пересобирает
файлы мода с нуля, поэтому правки палитры сразу видны в игре.
"""
from __future__ import annotations

import json
import os
import random

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

W = 32
SEED = 20261016
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "mods", "graphics", "backrooms")

PAPER = (232, 217, 122)
PAPER_PALE = (241, 232, 160)
PAPER_DARK = (198, 179, 90)
PAPER_STAIN = (150, 132, 66)
CARPET = (156, 143, 78)
CARPET_PALE = (176, 163, 96)
CARPET_DARK = (124, 112, 60)
FLOOR_DUST = (138, 128, 74)
LIGHT = (255, 246, 192)
SHADOW = (74, 68, 51)
DARK = (34, 31, 24)
INK = (24, 22, 18)
METAL = (154, 160, 166)
METAL_DARK = (86, 92, 98)
RUST = (122, 84, 52)
WOOD = (108, 76, 44)
GLASS = (208, 218, 214)
ALMOND = (238, 232, 214)
BLUE = (58, 110, 165)
GREEN = (94, 122, 74)
GREEN_DARK = (62, 84, 50)
BLOOD = (122, 46, 46)
HEAT = (255, 168, 66)
SMOKE = (150, 152, 158)


def clamp(value: int) -> int:
    return 0 if value < 0 else 255 if value > 255 else int(value)


def jitter(color, rng, amount=5):
    return (clamp(color[0] + rng.randint(-amount, amount)),
            clamp(color[1] + rng.randint(-amount, amount)),
            clamp(color[2] + rng.randint(-amount, amount)),
            color[3] if len(color) > 3 else 255)


def new_tile():
    return Image.new("RGBA", (W, W), (0, 0, 0, 0))


def fill_noise(img, palette, rng, amount=5):
    px = img.load()
    for y in range(W):
        for x in range(W):
            px[x, y] = jitter(rng.choice(palette), rng, amount)


def fill_stripes(img, base, stripe, rng, amount=4, period=4):
    px = img.load()
    for y in range(W):
        for x in range(W):
            px[x, y] = jitter(stripe if x % period < 2 else base, rng, amount)


def blotches(img, color, rng, count=6, radius=7.0, alpha=70):
    layer = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    for _ in range(count):
        cx = rng.uniform(-4, W + 4)
        cy = rng.uniform(-4, W + 4)
        r = rng.uniform(radius * 0.4, radius)
        draw.ellipse([cx - r, cy - r * 0.8, cx + r, cy + r * 0.8],
                     fill=(color[0], color[1], color[2], alpha))
    img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(radius * 0.45)))


def fibres(img, rng, color, count=90, length=3, alpha=70):
    layer = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    for _ in range(count):
        x = rng.randrange(W)
        y = rng.randrange(W)
        dx = rng.choice((-1, 0, 1))
        dy = rng.choice((-1, 0, 1)) or 1
        draw.line([x, y, x + dx * length, y + dy * length],
                  fill=(color[0], color[1], color[2], alpha))
    img.alpha_composite(layer)


def shade(img, light=LIGHT, light_alpha=46, dark=INK, dark_alpha=64,
          angle=(1.0, 0.7)):
    alpha = img.getchannel("A")
    grad = Image.new("L", (W, W), 0)
    px = grad.load()
    span = angle[0] * W + angle[1] * W
    for y in range(W):
        for x in range(W):
            px[x, y] = clamp(255 * (1.0 - (angle[0] * x + angle[1] * y) / span))
    lit = Image.new("RGBA", (W, W), (light[0], light[1], light[2], 0))
    lit.putalpha(ImageChops.multiply(grad, alpha).point(
        lambda v: v * light_alpha // 255))
    img.alpha_composite(lit)
    dim = Image.new("RGBA", (W, W), (dark[0], dark[1], dark[2], 0))
    dim.putalpha(ImageChops.multiply(
        ImageChops.invert(grad), alpha).point(lambda v: v * dark_alpha // 255))
    img.alpha_composite(dim)


def glow_mask(radius, peak, cx=None, cy=None):
    mask = Image.new("L", (W, W), 0)
    px = mask.load()
    ox = W / 2.0 - 0.5 if cx is None else cx
    oy = W / 2.0 - 0.5 if cy is None else cy
    for y in range(W):
        for x in range(W):
            dx = x - ox
            dy = y - oy
            d = (dx * dx + dy * dy) ** 0.5
            v = 1.0 - d / radius
            px[x, y] = int(peak * v * v) if v > 0 else 0
    return mask


def add_glow(img, color, radius=13.0, peak=150, cx=None, cy=None):
    layer = Image.new("RGBA", (W, W), (color[0], color[1], color[2], 0))
    layer.putalpha(glow_mask(radius, peak, cx, cy))
    img.alpha_composite(layer)


def detail_layer(img, painter, blur=0.0):
    """Рисует полупрозрачные детали слоем: ImageDraw заменяет альфу, не смешивает."""
    layer = new_tile()
    painter(ImageDraw.Draw(layer))
    if blur:
        layer = layer.filter(ImageFilter.GaussianBlur(blur))
    img.alpha_composite(layer)


def outlined(shape, color=INK):
    alpha = shape.getchannel("A")
    grown = alpha.filter(ImageFilter.MaxFilter(3))
    ring = Image.new("RGBA", (W, W), (color[0], color[1], color[2], 0))
    ring.putalpha(grown)
    out = new_tile()
    out.alpha_composite(ring)
    out.alpha_composite(shape)
    return out


def wall_paper(rng, base, stripe, stains, stain_color=PAPER_STAIN):
    img = new_tile()
    fill_stripes(img, base, stripe, rng, amount=4)

    def details(draw):
        draw.line([0, 15, W, 15], fill=(SHADOW[0], SHADOW[1], SHADOW[2], 22))
        draw.line([0, 30, W, 30], fill=(PAPER_STAIN[0], PAPER_STAIN[1],
                                        PAPER_STAIN[2], 34))
        draw.line([0, 0, W, 0], fill=(PAPER_PALE[0], PAPER_PALE[1], PAPER_PALE[2], 110))
        draw.line([0, W - 1, W, W - 1], fill=(*SHADOW, 120))
        draw.line([0, W - 2, W, W - 2], fill=(*SHADOW, 70))

    detail_layer(img, details)
    blotches(img, stain_color, rng, count=max(1, stains - 1), radius=8.0, alpha=58)
    shade(img, light_alpha=34, dark_alpha=70)
    return img


def carpet(rng, base=CARPET, pale=CARPET_PALE, dark=CARPET_DARK, stain=None):
    img = new_tile()
    fill_noise(img, [base, base, base, dark, pale], rng, amount=6)
    fibres(img, rng, dark, count=150, length=2, alpha=54)
    fibres(img, rng, pale, count=80, length=1, alpha=40)

    def weave(draw):
        for y in range(1, W, 2):
            draw.line([0, y, W, y], fill=(pale[0], pale[1], pale[2], 18))
        for x in range(1, W, 2):
            draw.line([x, 0, x, W], fill=(dark[0], dark[1], dark[2], 16))

    detail_layer(img, weave, blur=0.3)
    if stain:
        blotches(img, stain[0], rng, count=stain[1], radius=10.0, alpha=stain[2])
    shade(img, light_alpha=26, dark_alpha=58)
    return img


def t_wall_plain(rng):
    return wall_paper(rng, PAPER, PAPER_PALE, 2)


def t_wall_mild(rng):
    return wall_paper(rng, PAPER, PAPER_DARK, 4)


def t_wall_light(rng):
    return wall_paper(rng, PAPER_PALE, PAPER, 1)


def t_wall_damaged(rng):
    img = wall_paper(rng, PAPER_DARK, PAPER, 7, stain_color=(112, 96, 58))
    blotches(img, GREEN_DARK, rng, count=3, radius=6.0, alpha=52)
    blotches(img, SHADOW, rng, count=2, radius=8.0, alpha=64)
    return img


def t_floor(rng):
    return carpet(rng)


def t_floor_stain(rng):
    return carpet(rng, stain=((96, 86, 50), 3, 76))


def t_corridor(rng):
    img = carpet(rng, base=CARPET_DARK, pale=CARPET, dark=(104, 94, 52))

    def details(draw):
        draw.rectangle([6, 0, 25, W - 1], fill=(*CARPET, 96))
        for y in range(0, W, 6):
            draw.line([6, y, 25, y], fill=(*CARPET_DARK, 80))

    detail_layer(img, details, blur=0.4)
    shade(img, light_alpha=30, dark_alpha=62)
    return img


def t_corridor_worn(rng):
    img = carpet(rng, base=FLOOR_DUST, pale=CARPET_PALE, dark=(110, 100, 58))
    fibres(img, rng, SHADOW, count=120, length=3, alpha=46)
    blotches(img, DARK, rng, count=2, radius=6.0, alpha=44)
    return img


def t_water(rng):
    img = new_tile()
    fill_noise(img, [(84, 92, 74), (72, 82, 66), (96, 104, 82)], rng, amount=5)

    def details(draw):
        for i in range(5):
            y = 4 + i * 6 + rng.randint(-1, 1)
            draw.arc([-4, y - 4, W + 2, y + 5], 0, 180, fill=(150, 168, 142, 150))
            draw.arc([2, y - 2, W - 4, y + 6], 200, 340, fill=(58, 66, 52, 140))

    detail_layer(img, details)
    blotches(img, (52, 60, 46), rng, count=3, radius=8.0, alpha=70)
    shade(img, light_alpha=32, dark_alpha=70)
    return img


def t_weeds(rng):
    img = carpet(rng, stain=((110, 96, 54), 2, 50))
    layer = new_tile()
    draw = ImageDraw.Draw(layer)
    for _ in range(11):
        x = rng.randint(3, W - 4)
        y = rng.randint(14, W - 3)
        h = rng.randint(6, 13)
        col = GREEN if rng.random() < 0.6 else GREEN_DARK
        draw.line([x, y, x + rng.randint(-3, 3), y - h], fill=(*col, 255))
        draw.line([x, y, x + rng.randint(-4, 4), y - h // 2], fill=(*col, 220))
        draw.line([x, y, x + rng.randint(-5, 5), y - h // 3],
                  fill=(*GREEN_DARK, 200))
    layer = outlined(layer, (36, 40, 28))
    img.alpha_composite(layer)
    return img


def t_debris(rng):
    img = carpet(rng, stain=((104, 94, 54), 2, 60))
    layer = new_tile()
    draw = ImageDraw.Draw(layer)
    for _ in range(6):
        x = rng.randint(4, W - 8)
        y = rng.randint(6, W - 8)
        w = rng.randint(4, 9)
        h = rng.randint(3, 7)
        tone = rng.choice((METAL, METAL_DARK, RUST, CARPET_PALE))
        draw.polygon([(x, y + h), (x + w // 3, y), (x + w, y + 2),
                      (x + w - 2, y + h)], fill=(*tone, 255))
    img.alpha_composite(outlined(layer, SHADOW))
    return img


def t_haze(rng):
    img = new_tile()
    px = img.load()
    for y in range(W):
        for x in range(W):
            a = rng.randint(46, 116)
            tone = SMOKE if rng.random() < 0.7 else (196, 198, 204)
            px[x, y] = (tone[0], tone[1], tone[2], a)
    img = img.filter(ImageFilter.GaussianBlur(1.1))
    return img


def t_hedge(rng):
    img = carpet(rng, base=(96, 108, 72), pale=(120, 132, 88), dark=(70, 82, 54))
    layer = new_tile()
    draw = ImageDraw.Draw(layer)
    for _ in range(26):
        cx = rng.randint(2, W - 3)
        cy = rng.randint(2, W - 3)
        r = rng.randint(3, 6)
        tone = rng.choice((GREEN, GREEN_DARK, (78, 100, 60), (110, 128, 76)))
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*tone, 255))
    img.alpha_composite(outlined(layer, (30, 40, 26)))
    blotches(img, (58, 70, 44), rng, count=3, radius=7.0, alpha=60)
    shade(img, light_alpha=34, dark_alpha=70)
    return img


def t_lamp(rng):
    img = new_tile()
    px = img.load()
    for y in range(W):
        for x in range(W):
            v = 1.0 - abs(y - W / 2) / (W / 2)
            tone = (clamp(84 + 92 * v), clamp(78 + 88 * v), clamp(56 + 62 * v), 255)
            px[x, y] = jitter(tone, rng, 4)
    add_glow(img, LIGHT, radius=26.0, peak=120)
    draw = ImageDraw.Draw(img)
    draw.rectangle([2, 3, W - 3, W - 4], fill=(62, 58, 46, 255))
    draw.rectangle([3, 4, W - 4, W - 5], fill=(38, 36, 30, 255))
    for top in (6, 18):
        draw.rectangle([4, top, W - 5, top + 7], fill=(*LIGHT, 255))
        draw.line([5, top + 3, W - 6, top + 3], fill=(255, 255, 246, 255))
        draw.rectangle([4, top, 5, top + 7], fill=(206, 200, 176, 255))
        draw.rectangle([W - 6, top, W - 5, top + 7], fill=(206, 200, 176, 255))
    add_glow(img, (255, 250, 220), radius=17.0, peak=170, cx=W / 2 - 0.5, cy=9.5)
    add_glow(img, (255, 250, 220), radius=17.0, peak=170, cx=W / 2 - 0.5, cy=21.5)
    return img


def t_remains(rng):
    img = carpet(rng, stain=((104, 84, 60), 2, 70))
    layer = new_tile()
    draw = ImageDraw.Draw(layer)
    draw.rectangle([18, 13, 25, 26], fill=(*METAL, 255))
    draw.ellipse([18, 11, 25, 16], fill=(*METAL, 255))
    draw.ellipse([19, 12, 24, 15], fill=(120, 126, 132, 255))
    draw.line([18, 17, 25, 17], fill=(*METAL_DARK, 255))
    draw.line([18, 22, 25, 22], fill=(*METAL_DARK, 255))
    draw.line([5, 25, 16, 21], fill=(232, 228, 214, 255), width=2)
    draw.line([6, 27, 15, 24], fill=(232, 228, 214, 255), width=2)
    draw.ellipse([3, 23, 7, 27], fill=(232, 228, 214, 255))
    draw.ellipse([14, 19, 17, 22], fill=(232, 228, 214, 255))
    img.alpha_composite(outlined(layer, SHADOW))
    return img


def t_altar(rng):
    img = carpet(rng, stain=((98, 88, 52), 2, 56))
    layer = new_tile()
    draw = ImageDraw.Draw(layer)
    draw.polygon([(6, 12), (26, 9), (26, 26), (6, 27)], fill=(138, 134, 120, 255))
    draw.polygon([(6, 12), (26, 9), (22, 6), (3, 9)], fill=(166, 162, 148, 255))
    draw.polygon([(6, 27), (26, 26), (22, 24), (3, 25)], fill=(104, 100, 88, 255))
    draw.line([8, 15, 24, 13], fill=(178, 174, 160, 220))
    draw.rectangle([14, 2, 18, 10], fill=(*ALMOND, 255))
    draw.polygon([(16, 0), (13, 4), (19, 4)], fill=(255, 176, 58, 255))
    draw.polygon([(16, 1), (14, 4), (18, 4)], fill=(255, 232, 150, 255))
    draw.ellipse([15, 22, 18, 25], fill=(*RUST, 255))
    img.alpha_composite(outlined(layer, DARK))
    add_glow(img, (255, 176, 70), radius=9.0, peak=95, cx=16, cy=3)
    return img


def t_fountain(rng):
    img = carpet(rng, stain=((92, 84, 50), 2, 54))
    layer = new_tile()
    draw = ImageDraw.Draw(layer)
    draw.ellipse([1, 1, W - 2, W - 2], fill=(150, 146, 132, 255))
    draw.ellipse([3, 3, W - 4, W - 4], fill=(176, 172, 158, 255))
    draw.ellipse([7, 7, W - 8, W - 8], fill=(74, 84, 68, 255))
    draw.ellipse([9, 9, W - 10, W - 10], fill=(88, 100, 80, 255))
    for i in range(4):
        y = 11 + i * 4
        draw.arc([9, y, W - 10, y + 4], 0, 180, fill=(140, 158, 134, 200))
    draw.ellipse([13, 13, 18, 18], fill=(166, 162, 148, 255))
    draw.line([15, 15, 15, 10], fill=(140, 158, 134, 200))
    img.alpha_composite(outlined(layer, DARK))
    shade(img, light_alpha=30, dark_alpha=64)
    return img


def t_trapdoor(rng):
    img = carpet(rng, stain=((100, 90, 52), 2, 50))
    layer = new_tile()
    draw = ImageDraw.Draw(layer)
    draw.rectangle([4, 4, W - 5, W - 5], fill=(96, 100, 106, 255))
    draw.rectangle([6, 6, W - 7, W - 7], fill=(126, 132, 138, 255))
    draw.rectangle([6, 6, W - 7, 9], fill=(154, 160, 166, 255))
    for x in range(8, W - 8, 4):
        draw.line([x, 11, x, W - 9], fill=(104, 110, 116, 255))
    draw.rectangle([13, 20, 19, 23], fill=(74, 78, 84, 255))
    draw.ellipse([13, 21, 19, 27], outline=(58, 62, 68, 255))
    img.alpha_composite(outlined(layer, DARK))
    return img


def t_stairs_down(rng):
    img = carpet(rng, stain=((84, 76, 48), 2, 60))
    layer = new_tile()
    draw = ImageDraw.Draw(layer)
    draw.rectangle([2, 2, W - 3, W - 3], fill=(38, 36, 32, 255))
    steps = [(4, 8), (7, 12), (10, 16), (13, 20), (16, 24)]
    for i, (x0, y0) in enumerate(steps):
        tone = 108 - i * 16
        draw.polygon([(x0, y0), (W - 1 - x0, y0), (W - 3 - x0, W - 5), (x0 + 2, W - 5)],
                     fill=(tone, tone - 4, tone - 12, 255))
    for i, (x0, y0) in enumerate(steps):
        draw.line([x0, y0, W - 1 - x0, y0],
                  fill=(clamp(150 - i * 16), clamp(146 - i * 16), clamp(112 - i * 14), 255))
    img.alpha_composite(outlined(layer, INK))
    shade(img, light_alpha=24, dark_alpha=76)
    return img


def t_stairs_up(rng):
    img = carpet(rng, stain=((100, 92, 54), 2, 50))
    layer = new_tile()
    draw = ImageDraw.Draw(layer)
    draw.rectangle([2, 2, W - 3, W - 3], fill=(50, 47, 40, 255))
    for i in range(5):
        y = 3 + i * 6
        tone = 190 - i * 16
        draw.rectangle([4, y, W - 5, y + 4], fill=(tone, tone - 12, tone - 46, 255))
        draw.line([4, y, W - 5, y], fill=(252, 246, 216, 255))
        draw.line([4, y + 5, W - 5, y + 5], fill=(78, 72, 58, 255))
    draw.line([3, 3, 3, W - 4], fill=(112, 106, 88, 255))
    draw.line([W - 4, 3, W - 4, W - 4], fill=(112, 106, 88, 255))
    img.alpha_composite(outlined(layer, INK))
    add_glow(img, LIGHT, radius=19.0, peak=95)
    shade(img, light_alpha=30, dark_alpha=54)
    return img


def t_door(rng):
    img = new_tile()
    fill_noise(img, [(112, 98, 76), (100, 88, 68)], rng, amount=4)
    leaf = new_tile()
    fill_noise(leaf, [(208, 192, 156), (198, 182, 146)], rng, amount=5)
    mask = Image.new("L", (W, W), 0)
    ImageDraw.Draw(mask).rectangle([3, 3, W - 4, W - 4], fill=255)
    img.paste(leaf, (0, 0), mask)
    draw = ImageDraw.Draw(img)
    draw.rectangle([5, 5, W - 6, 14], fill=(190, 172, 138, 255))
    draw.rectangle([5, 17, W - 6, W - 6], fill=(190, 172, 138, 255))
    draw.rectangle([8, 8, W - 9, 11], fill=(174, 156, 124, 255))
    draw.ellipse([22, 15, 26, 19], fill=(186, 148, 60, 255))
    draw.ellipse([23, 16, 25, 17], fill=(232, 202, 130, 255))

    def details(d):
        d.rectangle([5, 5, W - 6, 14], outline=(152, 134, 104, 255))
        d.rectangle([5, 17, W - 6, W - 6], outline=(152, 134, 104, 255))
        d.line([3, 3, W - 4, 3], fill=(232, 220, 190, 150))
        d.line([3, 3, 3, W - 4], fill=(60, 52, 42, 150))
        d.line([5, 15, W - 7, 15], fill=(120, 106, 84, 170))
        d.rectangle([3, W - 4, W - 4, W - 3], fill=(74, 66, 54, 180))

    detail_layer(img, details)
    shade(img, light_alpha=34, dark_alpha=56)
    return img


LETTERS = {
    "E": ["111", "100", "110", "100", "111"],
    "X": ["101", "101", "010", "101", "101"],
    "I": ["111", "010", "010", "010", "111"],
    "T": ["111", "010", "010", "010", "010"],
}


def t_exit_sign(rng):
    img = new_tile()
    fill_noise(img, [(58, 58, 54), (46, 46, 44)], rng, amount=4)
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, W - 1, W - 1], fill=(52, 52, 48, 255))
    draw.rectangle([1, 1, W - 2, W - 2], fill=(60, 60, 56, 255))
    draw.rectangle([2, 10, W - 3, 22], fill=(22, 92, 54, 255))
    draw.rectangle([3, 11, W - 4, 21], fill=(36, 140, 78, 255))
    text = "EXIT"
    width = len(text) * 4 - 1
    ox = (W - width) // 2
    oy = 14
    for i, ch in enumerate(text):
        rows = LETTERS[ch]
        for ry, row in enumerate(rows):
            for rx, bit in enumerate(row):
                if bit == "1":
                    draw.rectangle([ox + i * 4 + rx, oy + ry,
                                    ox + i * 4 + rx, oy + ry],
                                   fill=(240, 255, 238, 255))
    draw.line([2, 22, W - 3, 22], fill=(18, 70, 42, 255))
    add_glow(img, (120, 255, 170), radius=17.0, peak=70)
    shade(img, light_alpha=22, dark_alpha=64)
    return img


def t_marker(rng):
    layer = new_tile()
    draw = ImageDraw.Draw(layer)
    draw.polygon([(6, 3), (24, 16), (6, 29)], fill=(*PAPER_PALE, 255))
    draw.polygon([(9, 8), (20, 16), (9, 24)], fill=(214, 186, 62, 255))
    return outlined(layer, INK)


def art_player(rng):
    shape = new_tile()
    draw = ImageDraw.Draw(shape)
    draw.line([9, 27, 9, 30], fill=(*DARK, 255))
    draw.line([22, 27, 22, 30], fill=(*DARK, 255))
    draw.rectangle([9, 24, 14, 29], fill=(46, 52, 60, 255))
    draw.rectangle([17, 24, 22, 29], fill=(46, 52, 60, 255))
    draw.rectangle([8, 28, 15, 30], fill=(30, 28, 24, 255))
    draw.rectangle([16, 28, 23, 30], fill=(30, 28, 24, 255))
    draw.rounded_rectangle([8, 11, 23, 25], radius=3, fill=(84, 92, 70, 255))
    draw.rectangle([13, 11, 18, 16], fill=(64, 72, 54, 255))
    draw.rectangle([6, 12, 9, 22], fill=(70, 78, 58, 255))
    draw.rectangle([22, 12, 25, 22], fill=(70, 78, 58, 255))
    draw.ellipse([5, 20, 10, 25], fill=(214, 168, 128, 255))
    draw.ellipse([21, 20, 26, 25], fill=(214, 168, 128, 255))
    draw.ellipse([11, 3, 20, 12], fill=(222, 176, 134, 255))
    draw.polygon([(11, 6), (12, 2), (19, 2), (20, 6), (18, 4), (13, 4)],
                 fill=(58, 44, 32, 255))
    draw.rectangle([10, 4, 12, 10], fill=(58, 44, 32, 255))
    draw.rectangle([19, 4, 21, 10], fill=(58, 44, 32, 255))
    draw.rectangle([14, 7, 15, 8], fill=(40, 30, 22, 255))
    draw.rectangle([17, 7, 18, 8], fill=(40, 30, 22, 255))
    draw.line([15, 10, 17, 10], fill=(150, 106, 78, 255))
    shape = outlined(shape, INK)
    shade(shape, light=LIGHT, light_alpha=54, dark_alpha=52, angle=(0.9, 0.8))
    return shape


def art_bottle(rng):
    shape = new_tile()
    draw = ImageDraw.Draw(shape)
    draw.rectangle([13, 2, 19, 6], fill=(*BLUE, 255))
    draw.rectangle([14, 6, 18, 10], fill=(*GLASS, 255))
    draw.rounded_rectangle([10, 9, 22, 29], radius=3, fill=(*GLASS, 255))
    draw.rounded_rectangle([11, 13, 21, 27], radius=2, fill=(*ALMOND, 255))
    draw.rectangle([11, 18, 21, 22], fill=(242, 238, 226, 255))
    draw.line([12, 19, 20, 19], fill=(140, 136, 128, 255))
    draw.line([12, 21, 17, 21], fill=(140, 136, 128, 255))
    draw.line([13, 11, 20, 11], fill=(248, 248, 246, 200))
    draw.line([13, 12, 13, 26], fill=(248, 248, 246, 140))
    shape = outlined(shape, INK)
    shade(shape, light_alpha=44, dark_alpha=48)
    return shape


def art_document(rng):
    shape = new_tile()
    draw = ImageDraw.Draw(shape)
    draw.polygon([(6, 6), (23, 3), (26, 25), (9, 28)], fill=(206, 200, 184, 255))
    draw.polygon([(9, 8), (25, 5), (27, 26), (11, 29)], fill=(238, 234, 220, 255))
    for i in range(4):
        y = 11 + i * 4
        draw.line([13, y, 24, y - 1], fill=(122, 118, 108, 255))
    draw.line([13, 25, 19, 24], fill=(122, 118, 108, 255))
    shape = outlined(shape, INK)
    shade(shape, light_alpha=40, dark_alpha=50)
    return shape


def art_artifact(rng):
    shape = new_tile()
    draw = ImageDraw.Draw(shape)
    draw.rectangle([12, 4, 19, 12], fill=(*METAL_DARK, 255))
    draw.rectangle([10, 11, 21, 16], fill=(*METAL, 255))
    draw.polygon([(13, 23), (18, 23), (21, 15), (10, 15)], fill=(*METAL_DARK, 255))
    draw.rectangle([11, 22, 20, 25], fill=(*METAL, 255))
    draw.polygon([(15, 8), (20, 14), (16, 15), (19, 21), (12, 15), (16, 14)],
                 fill=(*HEAT, 255))
    draw.ellipse([13, 10, 17, 14], fill=(255, 238, 190, 255))
    shape = outlined(shape, INK)
    add_glow(shape, HEAT, radius=16.0, peak=130, cx=15.5, cy=14)
    shade(shape, light_alpha=30, dark_alpha=52)
    return shape


def art_axe(rng):
    shape = new_tile()
    draw = ImageDraw.Draw(shape)
    draw.polygon([(13, 6), (19, 6), (19, 30), (13, 30)], fill=(*WOOD, 255))
    draw.line([15, 7, 15, 29], fill=(138, 102, 62, 255))
    draw.polygon([(13, 3), (25, 1), (29, 9), (25, 17), (13, 15)], fill=(*METAL, 255))
    draw.polygon([(13, 10), (26, 11), (25, 17), (13, 15)], fill=(168, 50, 38, 255))
    draw.polygon([(8, 4), (13, 3), (13, 15), (8, 14)], fill=(*METAL_DARK, 255))
    draw.line([26, 2, 29, 9], fill=(226, 232, 238, 255))
    draw.line([29, 9, 26, 16], fill=(226, 232, 238, 255))
    draw.line([14, 4, 24, 2], fill=(214, 218, 222, 255))
    shape = outlined(shape, INK)
    shade(shape, light_alpha=40, dark_alpha=52)
    return shape


def art_armor(rng):
    shape = new_tile()
    draw = ImageDraw.Draw(shape)
    draw.ellipse([6, 6, 26, 27], fill=(96, 104, 76, 255))
    draw.rectangle([6, 16, 26, 26], fill=(96, 104, 76, 255))
    draw.ellipse([8, 8, 18, 16], fill=(122, 130, 98, 255))
    draw.rectangle([9, 15, 23, 18], fill=(28, 32, 24, 255))
    draw.line([11, 7, 21, 7], fill=(146, 154, 118, 255))
    draw.rectangle([4, 20, 28, 25], fill=(72, 80, 56, 255))
    draw.ellipse([3, 19, 12, 26], fill=(72, 80, 56, 255))
    draw.ellipse([20, 19, 29, 26], fill=(72, 80, 56, 255))
    for x in (8, 16, 24):
        draw.rectangle([x, 22, x + 1, 23], fill=(48, 54, 38, 255))
    draw.line([4, 20, 25, 20], fill=(104, 112, 82, 255))
    draw.rectangle([14, 3, 18, 6], fill=(104, 112, 82, 255))
    shape = outlined(shape, INK)
    shade(shape, light_alpha=44, dark_alpha=56)
    return shape


def art_bolt(rng):
    shape = new_tile()
    draw = ImageDraw.Draw(shape)
    draw.line([7, 27, 21, 10], fill=(96, 74, 48, 255), width=2)
    draw.polygon([(19, 12), (27, 3), (22, 14)], fill=(198, 204, 210, 255))
    draw.polygon([(9, 26), (3, 22), (8, 22)], fill=(176, 60, 52, 255))
    draw.polygon([(11, 24), (4, 19), (10, 19)], fill=(214, 210, 200, 255))
    draw.polygon([(11, 28), (5, 29), (9, 25)], fill=(176, 60, 52, 255))
    draw.polygon([(13, 26), (7, 30), (12, 24)], fill=(214, 210, 200, 255))
    shape = outlined(shape, INK)
    shade(shape, light_alpha=36, dark_alpha=50)
    return shape


def art_ring(rng):
    shape = new_tile()
    draw = ImageDraw.Draw(shape)
    draw.ellipse([6, 8, 26, 28], fill=(*METAL, 255))
    draw.ellipse([9, 11, 23, 25], fill=(72, 76, 82, 255))
    draw.ellipse([10, 12, 22, 24], fill=(0, 0, 0, 0))
    draw.arc([6, 8, 26, 28], 200, 340, fill=(222, 226, 230, 255))
    draw.arc([6, 8, 26, 28], 20, 160, fill=(96, 100, 106, 255))
    draw.polygon([(16, 4), (20, 10), (12, 10)], fill=(120, 200, 210, 255))
    shape = outlined(shape, INK)
    shade(shape, light_alpha=36, dark_alpha=50)
    return shape


def art_gold(rng):
    shape = new_tile()
    draw = ImageDraw.Draw(shape)
    for i, (cx, cy) in enumerate(((9, 24), (16, 26), (22, 23), (13, 19), (20, 18))):
        draw.ellipse([cx - 6, cy - 4, cx + 6, cy + 4], fill=(226, 180, 62, 255))
        draw.ellipse([cx - 6, cy - 4, cx + 6, cy + 1], fill=(246, 210, 104, 255))
        draw.ellipse([cx - 3, cy - 2, cx + 3, cy + 2], outline=(158, 116, 34, 255))
    draw.ellipse([11, 4, 23, 14], fill=(238, 196, 78, 255))
    draw.ellipse([13, 5, 21, 12], outline=(164, 120, 34, 255))
    draw.line([14, 6, 19, 6], fill=(255, 236, 170, 220))
    shape = outlined(shape, INK)
    shade(shape, light_alpha=40, dark_alpha=52)
    return shape


def art_tool(rng):
    shape = new_tile()
    draw = ImageDraw.Draw(shape)
    draw.rectangle([13, 9, 19, 30], fill=(*METAL, 255))
    draw.rectangle([7, 3, 25, 15], fill=(180, 186, 192, 255))
    draw.ellipse([5, 1, 13, 16], fill=(180, 186, 192, 255))
    draw.ellipse([19, 1, 27, 16], fill=(180, 186, 192, 255))
    draw.polygon([(12, 0), (20, 0), (19, 11), (13, 11)], fill=(0, 0, 0, 0))
    draw.line([8, 4, 12, 4], fill=(232, 238, 244, 230))
    draw.line([20, 4, 24, 4], fill=(232, 238, 244, 230))
    draw.rectangle([13, 20, 19, 24], fill=(*METAL_DARK, 255))
    draw.rectangle([14, 21, 18, 23], fill=(*RUST, 255))
    draw.line([15, 12, 15, 29], fill=(218, 224, 230, 200))
    draw.line([18, 12, 18, 29], fill=(104, 110, 116, 200))
    shape = outlined(shape, INK)
    shade(shape, light_alpha=42, dark_alpha=50)
    return shape


TILES = [
    ("#", "wall.png", t_wall_mild, False),
    ("█", "wall_plain.png", t_wall_plain, False),
    ("▓", "wall_light.png", t_wall_light, False),
    ("▒", "wall_damaged.png", t_wall_damaged, False),
    (".", "floor.png", t_floor, False),
    (",", "floor_stain.png", t_floor_stain, False),
    ("-", "corridor.png", t_corridor, False),
    ("_", "corridor_worn.png", t_corridor_worn, False),
    ("~", "water.png", t_water, False),
    ('"', "weeds.png", t_weeds, False),
    (":", "debris.png", t_debris, False),
    ("░", "haze.png", t_haze, False),
    ("♣", "hedge.png", t_hedge, False),
    ("*", "ceiling_lamp.png", t_lamp, False),
    ("%", "remains.png", t_remains, False),
    ("⌂", "altar.png", t_altar, False),
    ("≈", "fountain.png", t_fountain, False),
    ("⌷", "trapdoor.png", t_trapdoor, False),
    ("<", "stairs_up.png", t_stairs_up, False),
    (">", "stairs_down.png", t_stairs_down, False),
    ("+", "door_closed.png", t_door, False),
    ("E", "exit_sign.png", t_exit_sign, False),
    ("►", "marker.png", t_marker, True),
    ("@", "player.png", art_player, True),
    ("!", "bottle.png", art_bottle, True),
    ("?", "document.png", art_document, True),
    ("/", "artifact.png", art_artifact, True),
    (")", "axe.png", art_axe, True),
    ("[", "armor.png", art_armor, True),
    ("}", "bolt.png", art_bolt, True),
    ("=", "ring.png", art_ring, True),
    ("$", "gold.png", art_gold, True),
    ("(", "tool.png", art_tool, True),
]

SHEET_COLUMNS = 8
CHECKER_A = (58, 58, 58, 255)
CHECKER_B = (76, 76, 76, 255)


def build():
    os.makedirs(OUT, exist_ok=True)
    manifest = {"tile_size": W, "tiles": {}, "native_symbols": []}
    images = []
    for index, (char, filename, maker, native) in enumerate(TILES):
        rng = random.Random(SEED + index * 7919)
        image = maker(rng)
        if image.size != (W, W) or image.mode != "RGBA":
            raise ValueError(f"{filename}: ожидается RGBA {W}x{W}, получено "
                             f"{image.mode} {image.size}")
        image.save(os.path.join(OUT, filename))
        manifest["tiles"][char] = filename
        if native:
            manifest["native_symbols"].append(char)
        images.append((char, filename, image))
    with open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    write_sheet(images)
    write_preview(images)
    return manifest, images


def write_sheet(images):
    rows = (len(images) + SHEET_COLUMNS - 1) // SHEET_COLUMNS
    sheet = Image.new("RGBA", (SHEET_COLUMNS * W, rows * W), (0, 0, 0, 0))
    for index, (_, _, image) in enumerate(images):
        col = index % SHEET_COLUMNS
        row = index // SHEET_COLUMNS
        sheet.alpha_composite(image, (col * W, row * W))
    sheet.save(os.path.join(OUT, "sheet.png"))


def checkerboard(width, height, cell=8):
    board = Image.new("RGBA", (width, height), CHECKER_A)
    draw = ImageDraw.Draw(board)
    for y in range(0, height, cell):
        for x in range(0, width, cell):
            if (x // cell + y // cell) % 2:
                draw.rectangle([x, y, x + cell - 1, y + cell - 1], fill=CHECKER_B)
    return board


def write_preview(images, zoom=5, columns=8):
    font = ImageFont.load_default()
    cell = W * zoom
    label = 16
    rows = (len(images) + columns - 1) // columns
    width = columns * cell
    height = 22 + rows * (cell + label)
    sheet = Image.new("RGBA", (columns * W, rows * W), (0, 0, 0, 0))
    for index, (_, _, image) in enumerate(images):
        sheet.alpha_composite(image, ((index % columns) * W, (index // columns) * W))
    board = checkerboard(width, height)
    board.alpha_composite(sheet.resize((width, rows * cell), Image.NEAREST), (0, 22))
    draw = ImageDraw.Draw(board)
    draw.text((6, 6), "backrooms tileset 32x32 - preview 5x", font=font,
              fill=(240, 236, 220, 255))
    for index, (char, filename, _) in enumerate(images):
        col = index % columns
        row = index // columns
        x = col * cell + 3
        y = 22 + row * (cell + label) + 3
        draw.text((x, y), f"{index + 1:02d} [{char}]", font=font,
                  fill=(230, 226, 210, 255))
        draw.text((x, y + 8), filename.replace(".png", "")[:16], font=font,
                  fill=(160, 214, 240, 255))
    board.save(os.path.join(OUT, "preview.png"))


def main():
    manifest, images = build()
    print(f"{len(images)} спрайтов -> {OUT}")
    print(f"tile_size={manifest['tile_size']}, "
          f"native_symbols={len(manifest['native_symbols'])}")
    missing = [c for c in
               ("@", "E", "#", "█", "▓", "▒", ".", ",", "-", "_", "♣", "+", ">", "<",
                "⌂", "≈", "⌷", "%", ":", '"', "~", "░", ")", "[", "}", "!", "?", "/",
                "=", "$", "(", "*", "►") if c not in manifest["tiles"]]
    print("не покрыто:", missing or "нет")


if __name__ == "__main__":
    main()
