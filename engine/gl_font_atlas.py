"""Bitmap font atlas for GPU text rendering.

Renders all ASCII + Cyrillic glyphs into a single OpenGL texture at init time,
then each text draw becomes a few quads instead of a CPU glyph cache lookup.
"""
from __future__ import annotations

import pygame


class GlyphAtlas:
    """Single-texture font atlas with UV lookup for ASCII + Cyrillic."""
    
    # Printable ASCII + common box-drawing + Cyrillic range
    CHARS = "".join(chr(i) for i in range(32, 127))  # ASCII printable
    CHARS += "─│┌┐└┘├┤┬┴┼═║╔╗╚╝╠╣╦╩╬"  # Box drawing
    CHARS += "АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯабвгдеёжзийклмнопрстуфхцчшщъыьэюя"
    CHARS += "█▓▒░▀▄▌▐■□●○·•→←↑↓↔✓✗π…—–"
    
    def __init__(self, gl, font_name=None, size=18):
        self.gl = gl
        self.font = pygame.font.SysFont(font_name, size)
        self.font_bold = pygame.font.SysFont(font_name, size, bold=True)
        self.size = size
        self.texture = None
        self.char_map = {}  # char → (u0, v0, u1, v1, advance_x, advance_y)
        self.atlas_w = 0
        self.atlas_h = 0
        self._build()
    
    def _build(self):
        """Render all glyphs onto a grid texture and record UV coordinates."""
        chars = list(self.CHARS) + [ch + "_bold" for ch in self.CHARS]
        
        # Measure max glyph size
        max_w = max(max(self.font.size(ch)[0], self.font_bold.size(ch)[0])
                    for ch in self.CHARS)
        max_h = max(max(self.font.size(ch)[1], self.font_bold.size(ch)[1])
                    for ch in self.CHARS)
        cell_w = max_w + 2  # padding
        cell_h = max_h + 2
        
        # Grid layout: pack all glyphs into a square-ish texture
        cols = 32
        rows = (len(chars) + cols - 1) // cols
        self.atlas_w = cols * cell_w
        self.atlas_h = rows * cell_h
        
        # Render to pygame surface
        surface = pygame.Surface((self.atlas_w, self.atlas_h), pygame.SRCALPHA, 32)
        surface.fill((0, 0, 0, 0))
        
        for index, ch_key in enumerate(chars):
            is_bold = ch_key.endswith("_bold")
            ch = ch_key.replace("_bold", "") if is_bold else ch_key
            font = self.font_bold if is_bold else self.font
            
            glyph = font.render(ch, True, (255, 255, 255))
            col, row = index % cols, index // cols
            x, y = col * cell_w + 1, row * cell_h + 1
            surface.blit(glyph, (x, y))
            
            # UV coordinates: normalized to [0, 1]
            u0, v0 = x / self.atlas_w, y / self.atlas_h
            u1 = (x + glyph.get_width()) / self.atlas_w
            v1 = (y + glyph.get_height()) / self.atlas_h
            
            key = (ch, is_bold)
            self.char_map[key] = (u0, v0, u1, v1, glyph.get_width(), glyph.get_height())
        
        # Upload to GL texture
        data = pygame.image.tostring(surface, "RGBA", False)
        self.texture = self.gl.glGenTextures(1)
        self.gl.glBindTexture(self.gl.GL_TEXTURE_2D, self.texture)
        self.gl.glTexImage2D(
            self.gl.GL_TEXTURE_2D, 0, self.gl.GL_RGBA,
            self.atlas_w, self.atlas_h, 0,
            self.gl.GL_RGBA, self.gl.GL_UNSIGNED_BYTE, data
        )
        self.gl.glTexParameteri(self.gl.GL_TEXTURE_2D, self.gl.GL_TEXTURE_MIN_FILTER, self.gl.GL_LINEAR)
        self.gl.glTexParameteri(self.gl.GL_TEXTURE_2D, self.gl.GL_TEXTURE_MAG_FILTER, self.gl.GL_LINEAR)
    
    def uv(self, char, bold=False):
        """Return (u0, v0, u1, v1, w, h) for a character, or None if missing."""
        return self.char_map.get((char, bold))
    
    def close(self):
        if self.texture is not None:
            self.gl.glDeleteTextures([self.texture])
            self.texture = None
