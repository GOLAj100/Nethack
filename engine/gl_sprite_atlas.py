"""Lazy, paged RGBA sprite atlas. Uploads occur only on cache misses."""
import pygame


class SpriteAtlas:
    def __init__(self, gl, page_size=1024):
        self.gl = gl
        self.size = min(page_size, int(gl.glGetIntegerv(gl.GL_MAX_TEXTURE_SIZE)))
        self.pages = []
        self.entries = {}
        self.x = self.y = self.row_height = 0

    def get(self, key, factory):
        if key in self.entries:
            return self.entries[key]
        surface = factory()
        w, h = surface.get_size()
        if w + 2 > self.size or h + 2 > self.size:
            raise ValueError("Sprite exceeds atlas page size")
        if self.x + w + 2 > self.size:
            self.x = 0
            self.y += self.row_height
            self.row_height = 0
        gl = self.gl
        if not self.pages or self.y + h + 2 > self.size:
            texture = gl.glGenTextures(1)
            self.pages.append(texture)
            gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
            gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA, self.size, self.size,
                            0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, None)
            for param in (gl.GL_TEXTURE_MIN_FILTER, gl.GL_TEXTURE_MAG_FILTER):
                gl.glTexParameteri(gl.GL_TEXTURE_2D, param, gl.GL_NEAREST)
            self.x = self.y = self.row_height = 0
        texture = self.pages[-1]
        # Convert colorkeys and surface alpha to real RGBA, with a clear gutter.
        rgba = pygame.Surface((w + 2, h + 2), pygame.SRCALPHA, 32)
        rgba.blit(surface, (1, 1))
        gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
        gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, 1)
        gl.glTexSubImage2D(gl.GL_TEXTURE_2D, 0, self.x, self.y, w + 2, h + 2,
                           gl.GL_RGBA, gl.GL_UNSIGNED_BYTE,
                           pygame.image.tostring(rgba, "RGBA", False))
        x, y = self.x + 1, self.y + 1
        entry = (texture, (x / self.size, y / self.size,
                           (x + w) / self.size, (y + h) / self.size), (w, h))
        self.entries[key] = entry
        self.x += w + 2
        self.row_height = max(self.row_height, h + 2)
        return entry

    def close(self):
        if self.pages:
            self.gl.glDeleteTextures(self.pages)
        self.pages.clear()
        self.entries.clear()
        self.x = self.y = self.row_height = 0
