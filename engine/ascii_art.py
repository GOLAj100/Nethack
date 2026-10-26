"""Offline image -> text mosaic. No display or GPU context required."""
import pygame

PALETTES = {"Классика": " .:-=+*#%@", "Блоки": " ░▒▓█", "Контраст": " .oO@"}


def convert(source, columns=24, ramp=PALETTES["Классика"], colored=True,
            invert=False, contrast=1.0, font=None):
    if not 4 <= int(columns) <= 96:
        raise ValueError("Детализация: от 4 до 96 столбцов")
    if len(ramp) < 2:
        raise ValueError("Нужны хотя бы два символа в палитре")
    font = font or pygame.font.SysFont("consolas", 14)
    cw = max(font.size(c)[0] for c in ramp)
    ch = font.get_linesize()
    columns = int(columns)
    rows = max(1, min(128, round(columns * source.get_height()/source.get_width() * cw/ch)))
    sampled = pygame.transform.smoothscale(source, (columns, rows))
    output = pygame.Surface((columns*cw, rows*ch), pygame.SRCALPHA)
    lines = []
    glyphs = {}
    for y in range(rows):
        line = []
        for x in range(columns):
            r,g,b,a = sampled.get_at((x,y))
            luminance = (0.2126*r+0.7152*g+0.0722*b)/255
            luminance = max(0.0,min(1.0,(luminance-.5)*contrast+.5))
            if invert:
                luminance=1-luminance
            char = ramp[round(luminance*(len(ramp)-1))] if a>=32 else ' '
            line.append(char)
            if char==' ':
                continue
            color = (r,g,b) if colored else (255,255,255)
            key = char,color
            if key not in glyphs:
                glyphs[key]=font.render(char,False,color)
            glyph=glyphs[key]
            if a<255:
                glyph=glyph.copy()
                glyph.set_alpha(a)
            output.blit(glyph,(x*cw,y*ch))
        lines.append(''.join(line))
    return output, '\n'.join(lines)
