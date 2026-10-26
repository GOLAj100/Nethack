"""Ordered GPU UI and sprite drawing into an offscreen composition target.

``visual`` retains its Surface-returning contract for software consumers;
``draw_visual``, ``tile`` and ``fill_tile`` draw cached atlas quads on the GPU.
"""
from __future__ import annotations

import pygame

from . import config as C
from . import glyphs as G

try:
    from OpenGL import GL
except ImportError:
    GL = None


class GLRenderer:
    def __init__(self, renderer, display=None):
        self.r = renderer
        self.display = display
        self.gl_enabled = False
        self.atlas = None
        self.font_atlases = {}
        self.sprites = None
        self.active = False
        self.batch = None
        self.fbo = None  # Framebuffer object for off-screen rendering
        self.fbo_texture = None
        self.fbo_rendered = False  # Flag: did we render to FBO this frame?
        if (GL is not None and display is not None
                and display.backend == "opengl" and display.gl is not None):
            self._init_gl()

    def __getattr__(self, name):
        # Called only for names not defined here: tileset, font, font_size,
        # _cache, _visual_cache ...  Read through __dict__ to avoid recursion
        # before __init__ has set ``r``.
        renderer = self.__dict__.get("r")
        if renderer is None:
            raise AttributeError(name)
        return getattr(renderer, name)

    # Always read live values: Display.sync_canvas() swaps the canvas.
    @property
    def surface(self):
        return self.r.surface

    @surface.setter
    def surface(self, value):
        self.r.surface = value

    @property
    def cw(self):
        return self.r.cw

    @property
    def ch(self):
        return self.r.ch

    # --- GL lifecycle ------------------------------------------------------
    def _init_gl(self):
        try:
            from .gl_font_atlas import GlyphAtlas
            from .gl_ui_batch import UIBatch
            name = getattr(self.r, "font_name", None)
            self.atlas = GlyphAtlas(GL, None if name == "default" else name, self.r.font_size)
            from .gl_sprite_atlas import SpriteAtlas
            self.sprites = SpriteAtlas(GL)
            self.batch = UIBatch(GL, self.atlas)
            self.batch.init()
            self.batch.resize(*self.r.surface.get_size())
            self._init_fbo()
            self.gl_enabled = True
        except Exception as exc:  # noqa: BLE001 - fall back to CPU drawing
            print(f"GL UI init failed: {exc}")
            self.gl_enabled = False
    
    def _init_fbo(self):
        """Create FBO for off-screen rendering (entire UI + 3D scene)."""
        w, h = self.r.surface.get_size()
        self.fbo = GL.glGenFramebuffers(1)
        self.fbo_texture = GL.glGenTextures(1)
        
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.fbo_texture)
        GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_RGBA, w, h, 0, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE, None)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
        
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, self.fbo)
        GL.glFramebufferTexture2D(GL.GL_FRAMEBUFFER, GL.GL_COLOR_ATTACHMENT0, GL.GL_TEXTURE_2D, self.fbo_texture, 0)
        
        if GL.glCheckFramebufferStatus(GL.GL_FRAMEBUFFER) != GL.GL_FRAMEBUFFER_COMPLETE:
            raise RuntimeError("FBO not complete")
        
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, 0)

    def resize(self, width, height):
        if self.batch and (self.batch.width, self.batch.height) == (width, height):
            return
        if self.batch:
            self.batch.resize(width, height)
        if self.fbo:
            # Recreate FBO with new size
            GL.glDeleteFramebuffers(1, [self.fbo])
            GL.glDeleteTextures([self.fbo_texture])
            self._init_fbo()

    def begin(self):
        """Start rendering to FBO instead of screen."""
        if self.gl_enabled:
            self.active = True
            self.fbo_rendered = False
            # Bound retained sprite memory, and invalidate only between frames.
            if len(self.sprites.pages) > 8:
                self.sprites.close()
            GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, self.fbo)
            GL.glViewport(0, 0, *self.surface.get_size())
            GL.glDisable(GL.GL_SCISSOR_TEST)
            GL.glClearColor(0, 0, 0, 0)
            GL.glClear(GL.GL_COLOR_BUFFER_BIT)
            self.batch.begin()

    def end(self):
        """Finish rendering and mark FBO as ready."""
        if self.gl_enabled:
            # Scene renderers use their own FBO and viewport in between begin/end.
            GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, self.fbo)
            GL.glViewport(0, 0, *self.surface.get_size())
            self.batch.end()
            GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, 0)
            self.fbo_rendered = True
            self.active = False

    def close(self):
        if self.sprites:
            self.sprites.close()
        for atlas in self.font_atlases.values():
            atlas.close()
        self.font_atlases.clear()
        if self.fbo:
            GL.glDeleteFramebuffers(1, [self.fbo])
            self.fbo = None
        if self.fbo_texture:
            GL.glDeleteTextures([self.fbo_texture])
            self.fbo_texture = None
        if self.batch:
            self.batch.close()
        if self.atlas:
            self.atlas.close()
        self.batch = self.atlas = None
        self.gl_enabled = False
        self.active = False
        self.fbo_rendered = False

    # --- geometry / CPU-only helpers ----------------------------------------
    def cell_rect(self, col, row, w=1, h=1):
        return self.r.cell_rect(col, row, w, h)

    def cell_at(self, px, py):
        return self.r.cell_at(px, py)

    def glyph(self, char, color, bold=False):
        return self.r.glyph(char, color, bold)

    def visual(self, char, color, bold=False, size=None):
        return self.r.visual(char, color, bold, size)

    def tile(self, col, row, char, color, bold=False):
        if not self.gl_enabled:
            return self.r.tile(col, row, char, color, bold)
        if char != " ":
            self.draw_visual((col * self.cw, row * self.ch), char, color, bold,
                             (self.cw, self.ch))

    def fill_tile(self, col, row, char, color, bold=False):
        if not self.gl_enabled:
            return self.r.fill_tile(col, row, char, color, bold)
        if char == " ":
            return
        image = self.r.tileset.image(char, color, bold)
        if image is None:
            return self.char(col, row, char, color, bold)
        texture, uv, (w, h) = self.sprites.get(self._sprite_key(char, color, bold, 'fill'), lambda: image)
        factor = max(self.cw / w, self.ch / h)
        du = (uv[2] - uv[0]) * self.cw / (w * factor) / 2
        dv = (uv[3] - uv[1]) * self.ch / (h * factor) / 2
        u, v = (uv[0] + uv[2]) / 2, (uv[1] + uv[3]) / 2
        self.batch.image(texture, self.cell_rect(col, row), (u-du, v-dv, u+du, v+dv))

    def _sprite_key(self, char, color, bold, size):
        ts = self.r.tileset
        return (char, tuple(color), bold, size, ts.enabled, ts.mod_name,
                ts.tile_size, ts.auto_color, getattr(ts, 'revision', 0),
                char in ts.native_symbols)

    def draw_visual(self, pos, char, color, bold=False, size=None):
        size = tuple(size or (self.cw, self.ch))
        if not self.gl_enabled:
            return self.surface.blit(self.r.visual(char, color, bold, size), pos)
        texture, uv, dimensions = self.sprites.get(
            self._sprite_key(char, color, bold, size),
            lambda: self.r.visual(char, color, bold, size))
        rect = pygame.Rect(pos, dimensions)
        self.batch.image(texture, rect, uv)
        return rect

    def text_pixels(self, pos, text, color, size=14, bold=False, align='left'):
        text = str(text)
        if not self.gl_enabled:
            font = pygame.font.SysFont('consolas', size, bold=bold)
            image = font.render(text, True, color)
            rect = image.get_rect(topleft=pos)
            if align == 'center':
                rect.centerx = pos[0]
            elif align == 'right':
                rect.right = pos[0]
            self.surface.blit(image, rect)
            return rect
        from .gl_font_atlas import GlyphAtlas
        key = ('consolas', size)
        atlas = self.font_atlases.get(key)
        if atlas is None:
            atlas = GlyphAtlas(GL, key[0], size)
            self.font_atlases[key] = atlas
        font = atlas.font_bold if bold else atlas.font
        rect = pygame.Rect(pos, font.size(text))
        if align == 'center':
            rect.centerx = pos[0]
        elif align == 'right':
            rect.right = pos[0]
        previous = self.batch.atlas
        self.batch.atlas = atlas
        x = rect.x
        for char in text:
            if atlas.uv(char, bold) is not None:
                self.batch.text(x, rect.y, char, color, size, bold)
            else:
                texture, uv, dimensions = self.sprites.get(
                    ('hud-glyph', key, bold, char),
                    lambda: font.render(char, True, (255, 255, 255)))
                self.batch.image(texture, (x, rect.y, *dimensions), uv, color)
            x += font.size(char)[0]
        self.batch.atlas = previous
        return rect

    # --- GPU primitives -----------------------------------------------------
    def clear(self, color=C.BLACK):
        if not self.gl_enabled:
            return self.r.clear(color)
        w, h = self.r.surface.get_size()
        self.batch.rect(0, 0, w, h, color)
    
    def fill(self, color):
        """Fill entire surface with color (replaces Surface.fill)."""
        if not self.gl_enabled:
            return self.r.surface.fill(color)
        w, h = self.r.surface.get_size()
        self.batch.rect(0, 0, w, h, color)
    
    def overlay(self, color):
        """Draw a semi-transparent overlay (color with alpha)."""
        if not self.gl_enabled:
            shade = pygame.Surface(self.r.surface.get_size(), pygame.SRCALPHA)
            shade.fill(color)
            return self.r.surface.blit(shade, (0, 0))
        w, h = self.r.surface.get_size()
        self.batch.rect(0, 0, w, h, color)

    def fill_rect(self, col, row, w, h, color):
        if not self.gl_enabled:
            return self.r.fill_rect(col, row, w, h, color)
        rect = self.r.cell_rect(col, row, w, h)
        self.batch.rect(rect.x, rect.y, rect.w, rect.h, color)
    
    def draw_rect(self, rect, color, border_radius=0):
        """Draw a pixel-space rectangle (for ModernHUD)."""
        if not self.gl_enabled:
            return pygame.draw.rect(self.r.surface, color, rect, border_radius=border_radius)
        if isinstance(rect, pygame.Rect):
            self.batch.rect(rect.x, rect.y, rect.w, rect.h, color, border_radius)
        else:
            x, y, w, h = rect
            self.batch.rect(x, y, w, h, color, border_radius)
    
    def draw_rect_outline(self, rect, color, thickness=1, border_radius=0):
        """Draw a pixel-space rectangle outline."""
        if not self.gl_enabled:
            return pygame.draw.rect(self.r.surface, color, rect, thickness, border_radius=border_radius)
        if isinstance(rect, pygame.Rect):
            self.batch.rect_outline(rect.x, rect.y, rect.w, rect.h, color, thickness, border_radius)
        else:
            x, y, w, h = rect
            self.batch.rect_outline(x, y, w, h, color, thickness, border_radius)
    
    def draw_line(self, start_pos, end_pos, color, thickness=1):
        """Draw a line between two pixel-space points."""
        if not self.gl_enabled:
            return pygame.draw.line(self.r.surface, color, start_pos, end_pos, thickness)
        self.batch.line(start_pos[0], start_pos[1], end_pos[0], end_pos[1], color, thickness)
    
    def draw_circle(self, center, radius, color, width=0):
        """Draw a circle. For now, fall back to pygame (TODO: SDF shader)."""
        # Need to end batch, draw on surface, then resume
        if self.gl_enabled:
            # Temporarily draw on surface (will be copied to GPU at end)
            return pygame.draw.circle(self.r.surface, color, center, radius, width)
        return pygame.draw.circle(self.r.surface, color, center, radius, width)

    def cell(self, col, row, color):
        self.fill_rect(col, row, 1, 1, color)

    def char(self, col, row, char, color, bold=False):
        if not self.gl_enabled:
            return self.r.char(col, row, char, color, bold)
        if char != " ":
            if self.atlas.uv(char, bold) is None:
                return self.draw_visual((col * self.cw, row * self.ch), char, color, bold)
            self.batch.text(col * self.r.cw, row * self.r.ch, char, color,
                            size=self.r.font_size, bold=bold)

    # --- composites (same logic as Renderer, routed through primitives) -----
    def sprite(self, col, row, char, color, bold=False):
        if self.r.tileset.enabled:
            self.tile(col, row, char, color, bold)
        else:
            self.char(col, row, char, color, bold)

    def text(self, col, row, text, color, bold=False, max_cells=None):
        if max_cells is not None:
            text = text[:max_cells]
        # One glyph per cell keeps text aligned to the grid like the CPU path.
        for i, ch in enumerate(text):
            self.char(col + i, row, ch, color, bold)
        return len(text)

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
            label = f" {title} "
            if len(label) <= w - 4:
                self.text(col + 2, row, label, title_color or color, bold=True)

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
        self.text(col, row, label, label_color)
        self.bar(col + len(label), row, max(1, w - len(label)),
                 max(0.0, min(1.0, frac)), color)

    def gradient_bg(self, top=C.BLACK, bottom=(20, 12, 26), rows=None):
        h = rows or (self.r.surface.get_height() // self.r.ch)
        width = self.r.surface.get_width() // self.r.cw + 1
        for row in range(h):
            t = row / max(1, h - 1)
            col = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
            self.fill_rect(0, row, width, 1, col)

    def present(self):
        if self.gl_enabled:
            self.end()  # Display.present() owns the buffer swap.
        else:
            self.r.present()

    @staticmethod
    def wrap(text, width):
        from .renderer import Renderer
        return Renderer.wrap(text, width)
