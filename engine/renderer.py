"""Рендерер: шрифт, кэш глифов и примитивы отрисовки в ячейках сетки."""

from __future__ import annotations

import pygame

from . import config as C
from . import glyphs as G
from .tileset import TilesetManager


class Renderer:
    def __init__(self, surface: pygame.Surface, font_size: int = C.FONT_SIZE, gl_renderer=None):
        self.surface = surface
        self.font_size = font_size
        self.font = None
        self.font_bold = None
        self._cache: dict[tuple[str, tuple[int, int, int], bool], pygame.Surface] = {}
        self.tileset = TilesetManager()
        self._visual_cache = {}
        self.gl_renderer = gl_renderer
        self._pick_font()

    def _pick_font(self):
        names = list(C.FONT_CANDIDATES) + [None]
        for name in names:
            try:
                f = pygame.font.SysFont(name, self.font_size)
            except Exception:
                continue
            if name is None or f is not None:
                self.font = f
                self.font_bold = pygame.font.SysFont(name, self.font_size, bold=True)
                self.font_name = name or "default"
                break
        if self.font is None:  # pragma: no cover
            self.font = pygame.font.Font(None, self.font_size)
            self.font_bold = self.font
            self.font_name = "default"

        # Ячейка должна вмещать и кириллицу: у некоторых моноширинных
        # шрифтов русские глифы шире латинской M и начинали налезать друг на друга.
        samples = "MWЖФЩЫЯ@█░→←"
        w = max(self.font.size(ch)[0] for ch in samples)
        h = max(self.font.size(ch)[1] for ch in samples)
        self.cw = max(8, w + 1)
        self.ch = max(12, h + 2)

    def cell_rect(self, col, row, w=1, h=1):
        return pygame.Rect(col * self.cw, row * self.ch, self.cw * w, self.ch * h)

    def cell_at(self, px, py):
        """Экранные пиксели -> координаты ячейки."""
        return px // self.cw, py // self.ch

    def glyph(self, char: str, color, bold=False) -> pygame.Surface:
        key = (char, tuple(color), bold)
        surf = self._cache.get(key)
        if surf is None:
            font = self.font_bold if bold else self.font
            surf = font.render(char, False, color)
            self._cache[key] = surf
        return surf

    def visual(self, char: str, color, bold=False, size=None) -> pygame.Surface:
        """Fit source art inside a display box, never use PNG pixels as world size.

        Default box is one UI/map cell. First-person renderers supply their
        projected box explicitly so native art is resampled only once.
        """
        source = self.tileset.image(char, color, bold)
        procedural=False
        if char.startswith('exit_sign:'):
            from .exit_sign import image
            source=image(char.split(':',1)[1])
            procedural=True
        if source is None:
            from game.furniture import FURNITURE
            kind=next((k for k,spec in FURNITURE.items() if spec['glyph']==char),None)
            if kind:
                procedural=True
                from .furniture_art import model
                source=model(kind,color)
        is_glyph = source is None
        if source is None:
            source = self.glyph(char, color, bold)
            if size is None:
                return source
        size = tuple(max(1,int(n)) for n in (size or (self.cw,self.ch)))
        key = (char, tuple(color), bool(bold), size,
               bool(self.tileset.enabled), bool(char in self.tileset.native_symbols),
               self.tileset.mod_name,self.tileset.tile_size,self.tileset.auto_color,
               getattr(self.tileset,'revision',0),is_glyph)
        cached = self._visual_cache.get(key)
        if cached is not None:
            return cached
        # Font.render(False) returns indexed pixels with a COLORKEY, not
        # SRCALPHA. Blit into RGBA before filtering so the key colour cannot
        # bleed into the glyph as blue/black rectangles.
        rgba=pygame.Surface(source.get_size(),pygame.SRCALPHA,32)
        rgba.blit(source,(0,0))
        source=rgba
        if not is_glyph and char in self.tileset.native_symbols:
            bounds=source.get_bounding_rect(min_alpha=16)
            if bounds.w and bounds.h:
                source=source.subsurface(bounds).copy()
        factor=min(size[0]/source.get_width(),size[1]/source.get_height())
        fitted=(max(1,round(source.get_width()*factor)),max(1,round(source.get_height()*factor)))
        result=pygame.Surface(size,pygame.SRCALPHA,32)
        result.fill((0,0,0,0))
        if is_glyph or procedural:
            scaled=pygame.transform.scale(source,fitted)
        else:
            # Filter premultiplied pixels, then restore straight alpha.
            scaled=pygame.transform.smoothscale(source.premul_alpha(),fitted)
            for y in range(fitted[1]):
                for x in range(fitted[0]):
                    red,green,blue,alpha=scaled.get_at((x,y))
                    if alpha:
                        scaled.set_at((x,y),(min(255,round(red*255/alpha)),
                                             min(255,round(green*255/alpha)),
                                             min(255,round(blue*255/alpha)),alpha))
        result.blit(scaled,scaled.get_rect(center=(size[0]//2,size[1]//2)))
        if len(self._visual_cache)>=64:
            self._visual_cache.clear()
        self._visual_cache[key]=result
        return result

    # --- Примитивы --------------------------------------------------------
    def clear(self, color=C.BLACK):
        if self.gl_renderer and self.gl_renderer.active:
            return self.gl_renderer.clear(color)
        self.surface.fill(color)

    def cell(self, col, row, color):
        self.fill_rect(col, row, 1, 1, color)

    def char(self, col, row, char: str, color, bold=False):
        if self.gl_renderer and self.gl_renderer.active:
            self.gl_renderer.char(col, row, char, color, bold)
        elif char != " ":
            self.surface.blit(self.glyph(char, color, bold), (col*self.cw, row*self.ch))

    def tile(self, col, row, char: str, color, bold=False):
        if self.gl_renderer and self.gl_renderer.active:
            return self.gl_renderer.tile(col, row, char, color, bold)
        if char == " ":
            return
        self.surface.blit(self.visual(char,color,bold,size=(self.cw,self.ch)), (col*self.cw,row*self.ch))

    def fill_tile(self, col, row, char: str, color, bold=False):
        """Terrain sprite covers the whole cell; aspect is kept, edges are cropped.

        The ASCII map cell is taller than wide, so an aspect-fitted square tile
        would leave gaps and turn the map into a dotted grid. Covering the cell
        keeps walls and floors seamless without stretching the artwork.
        """
        if self.gl_renderer and self.gl_renderer.active:
            self.gl_renderer.fill_tile(col, row, char, color, bold)
            return
        if char == " ":
            return
        image = self.tileset.image(char, color, bold)
        if image is None:
            self.char(col, row, char, color, bold)
            return
        size = (self.cw, self.ch)
        key = ("fill", char, tuple(color), bool(bold), size, self.tileset.mod_name,
               self.tileset.tile_size, self.tileset.auto_color,
               getattr(self.tileset, "revision", 0))
        result = self._visual_cache.get(key)
        if result is None:
            factor = max(size[0]/image.get_width(), size[1]/image.get_height())
            scaled = pygame.transform.scale(
                image, (max(1,round(image.get_width()*factor)),
                        max(1,round(image.get_height()*factor))))
            result = pygame.Surface(size, pygame.SRCALPHA, 32)
            result.fill((0,0,0,0))
            result.blit(scaled, scaled.get_rect(center=(size[0]//2, size[1]//2)))
            if len(self._visual_cache) >= 64:
                self._visual_cache.clear()
            self._visual_cache[key] = result
        self.surface.blit(result, (col*self.cw, row*self.ch))

    def sprite(self, col, row, char: str, color, bold=False):
        """Tileset sprite instead of a glyph; ASCII stays the safe fallback."""
        if self.tileset.enabled:
            self.tile(col, row, char, color, bold)
        else:
            self.char(col, row, char, color, bold)

    def text(self, col, row, text: str, color, bold=False, max_cells=None):
        """Вывод строки; возвращает число нарисованных ячеек."""
        if self.gl_renderer and self.gl_renderer.active:
            if max_cells is not None:
                text = text[:max_cells]
            self.gl_renderer.text(col, row, text, color, bold, max_cells)
            return len(text)
        if max_cells is not None:
            text = text[:max_cells]
        for i, ch in enumerate(text):
            self.char(col + i, row, ch, color, bold)
        return len(text)

    def fill_rect(self, col, row, w, h, color):
        if self.gl_renderer and self.gl_renderer.active:
            self.gl_renderer.fill_rect(col, row, w, h, color)
        else:
            self.surface.fill(color, self.cell_rect(col, row, w, h))

    def hline(self, col, row, w, color, char=G.BOX_H):
        for i in range(w):
            self.char(col + i, row, char, color)

    def vline(self, col, row, h, color, char=G.BOX_V):
        for i in range(h):
            self.char(col, row + i, char, color)

    def box(self, col, row, w, h, color, title=None, title_color=None, filled=False):
        if filled:
            self.fill_rect(col, row, w, h, C.BLACK)
        self.char(col, row, G.BOX_TL, color)
        self.char(col + w - 1, row, G.BOX_TR, color)
        self.char(col, row + h - 1, G.BOX_BL, color)
        self.char(col + w - 1, row + h - 1, G.BOX_BR, color)
        self.hline(col + 1, row, w - 2, color)
        self.hline(col + 1, row + h - 1, w - 2, color)
        self.vline(col, row + 1, h - 2, color)
        self.vline(col + w - 1, row + 1, h - 2, color)
        if title:
            tcol = title_color or color
            t = f" {title} "
            if len(t) <= w - 4:
                self.text(col + 2, row, t, tcol, bold=True)

    def shadow_box(self, col, row, w, h, color=C.DARK_GRAY, title=None, filled=False):
        self.box(col + 1, row + 1, w, h, C.BLACK, filled=True)
        self.box(col, row, w, h, color, title, filled=filled)

    def bar(self, col, row, w, frac, color, bg=C.HP_BAR_BG, glyph=G.BAR_FULL, empty=G.BAR_EMPTY):
        frac = max(0.0, min(1.0, frac))
        filled = int(round(frac * w))
        self.fill_rect(col, row, w, 1, bg)
        for i in range(filled):
            self.char(col + i, row, glyph, color)

    def bar_with_label(self, col, row, w, frac, color, label, label_color=C.WHITE):
        filled = max(0.0, min(1.0, frac))
        self.text(col, row, label, label_color)
        bx = col + len(label)
        bw = max(1, w - len(label))
        self.bar(bx, row, bw, filled, color)

    def gradient_bg(self, top=C.BLACK, bottom=(20, 12, 26), rows=None):
        h = rows or (self.surface.get_height() // self.ch)
        for r in range(h):
            t = r / max(1, h - 1)
            col = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
            self.fill_rect(0, r, self.surface.get_width() // self.cw + 1, 1, col)

    def present(self):
        pygame.display.flip()

    # --- Текстовые утилиты ------------------------------------------------
    @staticmethod
    def wrap(text: str, width: int) -> list[str]:
        words = text.split()
        lines: list[str] = []
        cur = ""
        for w in words:
            if not cur:
                cur = w
            elif len(cur) + 1 + len(w) <= width:
                cur += " " + w
            else:
                lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        return lines
