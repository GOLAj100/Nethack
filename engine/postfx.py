"""Post-processing effects for the first-person view.

Effects are applied to the 3D viewport only (not the HUD) so text stays
crisp.  Everything is optional and controlled by the level profile so
each Backrooms level can pick its own atmosphere:

    "postfx": ["vignette", "grain", "aberration"]

The pipeline is deliberately cheap: vignette is a precomputed alpha
mask, grain is a small tiled noise surface, aberration is skipped in
software mode (it needs per-pixel channel shifts).
"""

from __future__ import annotations

import random
import pygame


class PostFX:
    def __init__(self):
        self._vignette: pygame.Surface | None = None
        self._vignette_size = None
        self._grain_tiles: list[pygame.Surface] = []
        self._grain_size = None
        self._grain_frame = 0
        self._grain_seed = 0
        self._aberration_frames: dict[tuple, pygame.Surface] = {}

    # ------------------------------------------------------------------
    # Vignette
    # ------------------------------------------------------------------
    def _build_vignette(self, size):
        """Precompute a radial alpha mask: transparent centre, dark edges."""
        w, h = size
        mask = pygame.Surface(size, pygame.SRCALPHA)
        # Draw concentric rectangles with increasing alpha.  Cheaper than
        # per-pixel maths and visually indistinguishable at this resolution.
        steps = 24
        cx, cy = w / 2, h / 2
        max_dist = (cx * cx + cy * cy) ** 0.5
        # Use a coarse grid then smoothscale up.
        small_w, small_h = max(2, w // 8), max(2, h // 8)
        small = pygame.Surface((small_w, small_h), pygame.SRCALPHA)
        for y in range(small_h):
            for x in range(small_w):
                dx = (x + 0.5) / small_w * 2 - 1
                dy = (y + 0.5) / small_h * 2 - 1
                dist = (dx * dx + dy * dy) ** 0.5
                # 0 at centre, 1 at corners.
                alpha = int(max(0.0, min(1.0, (dist - 0.55) / 0.9)) ** 2 * 255)
                if alpha:
                    small.set_at((x, y), (0, 0, 0, alpha))
        mask = pygame.transform.smoothscale(small, size)
        self._vignette = mask
        self._vignette_size = size

    def draw_vignette(self, surface, rect, strength=1.0):
        if self._vignette is None or self._vignette_size != rect.size:
            self._build_vignette(rect.size)
        if strength >= 0.99:
            surface.blit(self._vignette, rect.topleft)
        else:
            mask = self._vignette.copy()
            mask.fill((255, 255, 255, int(255 * strength)),
                      special_flags=pygame.BLEND_RGBA_MULT)
            surface.blit(mask, rect.topleft)

    # ------------------------------------------------------------------
    # Film grain
    # ------------------------------------------------------------------
    def _build_grain_tiles(self, size):
        """Build a handful of small noise tiles that are tiled over the
        viewport.  Cycling through them each frame gives animated grain
        without generating a full-screen random buffer every frame."""
        tile = 128
        rng = random.Random(0xC0FFEE)
        self._grain_tiles = []
        for _ in range(4):
            surf = pygame.Surface((tile, tile), pygame.SRCALPHA)
            # Sparse bright and dark dots: pure alpha noise reads as static
            # rather than film grain.
            for _ in range(tile * tile // 14):
                x = rng.randrange(tile)
                y = rng.randrange(tile)
                if rng.random() < 0.5:
                    surf.set_at((x, y), (255, 255, 255, 18))
                else:
                    surf.set_at((x, y), (0, 0, 0, 26))
            self._grain_tiles.append(surf)
        self._grain_size = size

    def draw_grain(self, surface, rect, strength=1.0):
        if not self._grain_tiles or self._grain_size != rect.size:
            self._build_grain_tiles(rect.size)
        self._grain_frame = (self._grain_frame + 1) % len(self._grain_tiles)
        tile = self._grain_tiles[self._grain_frame]
        tw, th = tile.get_size()
        clip = surface.get_clip()
        surface.set_clip(rect)
        # Tile offset drifts slightly each frame so movement is visible.
        ox = (self._grain_frame * 37) % tw
        oy = (self._grain_frame * 91) % th
        for y in range(rect.top - oy, rect.bottom, th):
            for x in range(rect.left - ox, rect.right, tw):
                surface.blit(tile, (x, y))
        surface.set_clip(clip)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    def apply(self, surface, rect, effects, strength=1.0):
        """Apply the named effects to *surface* inside *rect*.

        effects is an iterable drawn from {"vignette", "grain"}.  Unknown
        names are ignored so a profile can opt in before the effect exists.
        """
        effects = set(effects or ())
        if "grain" in effects:
            self.draw_grain(surface, rect, strength)
        if "vignette" in effects:
            self.draw_vignette(surface, rect, strength)
