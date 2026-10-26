"""Optional character-to-image tilesets with a safe ASCII fallback.

Tileset format (mods/graphics/<name>/manifest.json):
{"tile_size": 32, "tiles": {"@": "at.png", "#": "wall.png"}}
Missing/broken files are deliberately ignored.
"""
from __future__ import annotations

import json
import os
import pygame

from . import config as C


class TilesetManager:
    def __init__(self):
        self.root = os.path.join(C.BASE_DIR, "mods", "graphics")
        self.enabled = False
        self.auto_color = True
        self.tile_size = 32
        self.mod_name = "default"
        self.tiles = {}
        self.sheet = None
        self.atlas = {}
        self.sheet_image = None
        self.cache = {}
        self.originals = {}
        self._neutral_cache = {}
        self.native_symbols = set()
        self.revision = 0

    def mods(self):
        try:
            return sorted(name for name in os.listdir(self.root)
                          if os.path.isdir(os.path.join(self.root, name)))
        except OSError:
            return []

    def configure(self, enabled=None, auto_color=None, tile_size=None, mod_name=None):
        self.revision += 1
        if enabled is not None:
            self.enabled = bool(enabled)
        if auto_color is not None:
            self.auto_color = bool(auto_color)
        if tile_size is not None and int(tile_size) in (16, 24, 32, 48, 64):
            self.tile_size = int(tile_size)
        if mod_name:
            self.mod_name = str(mod_name)
        self.cache.clear()
        self.originals.clear()
        self._neutral_cache.clear()
        self.native_symbols = set()
        self.tiles = {}
        self.sheet = None
        self.atlas = {}
        self.sheet_image = None
        path = os.path.join(self.root, self.mod_name, "manifest.json")
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            size = data.get("tile_size", self.tile_size)
            self.native_symbols = set(data.get("native_symbols", []))
            if tile_size is None and int(size) in (16, 24, 32, 48, 64):
                self.tile_size = int(size)
            for char, filename in data.get("tiles", {}).items():
                if isinstance(char, str) and len(char) == 1 and isinstance(filename, str):
                    self.tiles[char] = os.path.join(os.path.dirname(path), filename)
            sheet_name = data.get("sheet")
            if isinstance(sheet_name, str):
                self.sheet = os.path.join(os.path.dirname(path), sheet_name)
                self.atlas = data.get("atlas", {}) if isinstance(data.get("atlas", {}), dict) else {}
        except (OSError, ValueError, TypeError):
            pass

    def _tint(self, image, color):
        if not self.auto_color:
            return image
        # Only neutral sprites are recoloured; colourful custom art stays intact.
        key=id(image)
        cached=self._neutral_cache.get(key)
        if cached is None or cached[0] is not image:
            neutral = all(max(image.get_at((x, y))[:3]) - min(image.get_at((x, y))[:3]) < 20
                          for x in range(image.get_width()) for y in range(image.get_height())
                          if image.get_at((x, y)).a)
            if len(self._neutral_cache)>128: self._neutral_cache.clear()
            self._neutral_cache[key]=(image,neutral)
        else:
            neutral=cached[1]
        if not neutral:
            return image
        out = image.copy()
        tint = pygame.Surface(out.get_size(), pygame.SRCALPHA)
        tint.fill((*color, 255))
        out.blit(tint, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        return out

    def image(self, char, color, bold=False):
        if not self.enabled or (char not in self.tiles and char not in self.atlas):
            return None
        native = char in self.native_symbols
        key = (char, tuple(color), bool(bold), self.tile_size, self.auto_color, native)
        if key in self.cache:
            return self.cache[key]
        try:
            source_key = ("atlas", self.sheet, char, self.tile_size) if char in self.atlas else ("file", self.tiles.get(char))
            if source_key not in self.originals:
                source = pygame.image.load(self.sheet if char in self.atlas else self.tiles[char])
                if char in self.atlas:
                    cell = self.atlas[char]
                    if isinstance(cell, list) and len(cell) == 2:
                        rect = pygame.Rect(int(cell[0]) * self.tile_size, int(cell[1]) * self.tile_size,
                                           self.tile_size, self.tile_size)
                    elif isinstance(cell, list) and len(cell) == 4:
                        rect = pygame.Rect(*map(int, cell))
                    else:
                        raise ValueError("atlas coordinate must be [column,row] or [x,y,w,h]")
                    source = source.subsurface(rect).copy()
                self.originals[source_key] = source
            if self.originals[source_key] is None:
                return None
            image = self.originals[source_key]
            if not native:
                image = pygame.transform.smoothscale(image, (self.tile_size, self.tile_size))
            image = self._tint(image, color)
        except (pygame.error, OSError, ValueError):
            self.originals[source_key] = None
            return None
        if len(self.cache) >= (16 if native else 512):
            self.cache.clear()
        self.cache[key] = image
        return image
