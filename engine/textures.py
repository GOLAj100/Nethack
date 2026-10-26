"""Procedural texture sampler for the raycaster.

Textures are generated on demand per material name and cached.  Each
texture is a small RGB array (numpy) that the raycaster samples by UV.
The same generator is used by the CPU path (volume.cast_frame) and the
GPU path (gpu_rays) through a shared material lookup.

Currently procedural only; PNG/JPG file loading can be added by replacing
``_generate`` with a loader that fills the same array shape.
"""

from __future__ import annotations

import numpy as np

# Texture resolution.  64x64 is large enough to read a pattern on a wall
# at typical raycaster distances but small enough to keep the cache tiny.
TEX_SIZE = 64

_cache: dict[str, np.ndarray] = {}


def _wallpaper(rng: np.random.Generator) -> np.ndarray:
    """Backrooms Level 0 yellow wallpaper: faded yellow with subtle
    vertical stripes and a faint dot pattern.  The pattern period is
    larger than one tile so adjacent walls don't look like clones."""
    n = TEX_SIZE
    base = np.empty((n, n, 3), dtype=np.float32)
    base[..., 0] = 195  # R
    base[..., 1] = 175  # G
    base[..., 2] = 85   # B
    # Subtle vertical stripes every 32 px (wider than one cell).
    stripes = ((np.arange(n) % 32) < 16).astype(np.float32) * 0.04 - 0.02
    base += stripes[None, :, None]
    # Small dot pattern (the iconic wallpaper print).
    yy, xx = np.mgrid[0:n, 0:n]
    dots = ((xx % 6 == 0) & (yy % 6 == 0)).astype(np.float32) * 8
    base += dots[..., None]
    # Slight per-pixel variation so the wall doesn't read as flat noise.
    grain = rng.normal(0, 3, (n, n, 1)).astype(np.float32)
    base += grain
    return np.clip(base, 0, 255).astype(np.uint8)


def _carpet(rng: np.random.Generator) -> np.ndarray:
    """Backrooms Level 0 moist carpet: dark olive with high-frequency
    noise so the floor reads as fabric.  Darker than walls."""
    n = TEX_SIZE
    base = np.empty((n, n, 3), dtype=np.float32)
    base[..., 0] = 70   # R — much darker
    base[..., 1] = 60   # G
    base[..., 2] = 35   # B
    # High-frequency fiber noise.
    noise = rng.normal(0, 12, (n, n, 1)).astype(np.float32)
    base += noise
    # Very subtle carpet tile banding.
    bands = ((np.arange(n) // 16) % 2).astype(np.float32) * 0.03 - 0.015
    base *= (1.0 + bands[:, None, None])
    return np.clip(base, 0, 255).astype(np.uint8)


def _ceiling(rng: np.random.Generator) -> np.ndarray:
    """Ceiling tiles with bright fluorescent panels.  Backrooms Level 0
    is famous for its humming fluorescent lights, so the lamp strips are
    the brightest thing in the scene."""
    n = TEX_SIZE
    base = np.empty((n, n, 3), dtype=np.float32)
    base[..., 0] = 220  # R
    base[..., 1] = 218  # G
    base[..., 2] = 200  # B
    # Tile grid.
    grid = ((np.arange(n) % 16 == 0) | (np.arange(n)[:, None] % 16 == 0)).astype(np.float32)
    base *= (1.0 - grid * 0.3)[..., None]
    # Fluorescent panels: bright strips every 16 px.
    lamp = ((np.arange(n) // 8) % 2 == 1).astype(np.float32)
    base += (lamp[:, None] * 35)[..., None]
    return np.clip(base, 0, 255).astype(np.uint8)


def _concrete(rng: np.random.Generator) -> np.ndarray:
    """Generic concrete: grey with mottling."""
    n = TEX_SIZE
    base = np.full((n, n, 3), 130, dtype=np.float32)
    noise = rng.normal(0, 14, (n, n, 1)).astype(np.float32)
    base += noise
    return np.clip(base, 0, 255).astype(np.uint8)


_GENERATORS = {
    "wallpaper": _wallpaper,
    "carpet": _carpet,
    "ceiling": _ceiling,
    "concrete": _concrete,
}


def get(name: str) -> np.ndarray:
    """Return the texture array for *name*, generating it on first use."""
    tex = _cache.get(name)
    if tex is None:
        rng = np.random.default_rng(hash(name) & 0xFFFFFFFF)
        gen = _GENERATORS.get(name, _concrete)
        tex = gen(rng)
        _cache[name] = tex
    return tex


def sample(name: str, u: float, v: float) -> tuple[int, int, int]:
    """Sample the texture at UV coordinates (0..1).  Out-of-range wraps."""
    tex = get(name)
    n = TEX_SIZE
    x = int((u % 1.0) * n)
    y = int((v % 1.0) * n)
    r, g, b = tex[y, x]
    return int(r), int(g), int(b)


# Stable layer order for the GPU texture array.  Never reorder without
# bumping the atlas version in gpu_rays, or old shader uniforms would sample
# the wrong material.
LAYER_NAMES = ("wallpaper", "carpet", "ceiling", "concrete")


def layer_index(name: str | None) -> int:
    if not name:
        return 0
    try:
        return LAYER_NAMES.index(name)
    except ValueError:
        return 0


def atlas_layers() -> np.ndarray:
    """Stacked RGB texture array of shape (layers, TEX_SIZE, TEX_SIZE, 3)."""
    return np.stack([get(name) for name in LAYER_NAMES], axis=0)
