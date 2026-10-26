"""Backend-independent render data. Units are cells; angles are radians.

Position is the minimum corner. Width/depth span world X/Y, height spans Z.
Rotation is about the footprint centre; width/depth describe its current AABB.
Gameplay ownership and save data remain outside this module.
"""
from dataclasses import dataclass


@dataclass(slots=True)
class Visual:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    width: float = 1.0
    height: float = 1.0
    depth: float = 1.0
    rotation: float = 0.0
    material: str = 'wallpaper'
    uv_scale: tuple[float, float] = (1.0, 1.0)
    emits_light: bool = False
    light_color: tuple[int, int, int] = (255, 255, 255)
    light_radius: float = 0.0
    layer: int = 0
    mesh_id: str | None = None
    sprite_id: str | None = None
    visible: bool = True
    dirty: bool = True
    # Compatibility metadata shared by software and GPU consumers.
    color: tuple[int, int, int] = (255, 255, 255)
    opaque: bool = False
    tile_id: int | None = None


@dataclass(frozen=True, slots=True)
class VisualCamera:
    """Optional world-space AABB and FOV cells; None means no such filter.

    Bounds: (left, top, right, bottom, z_min, z_max), upper limits exclusive.
    FOV applies to footprint cells, independently of the visual's Z offset.
    """
    bounds: tuple[float, float, float, float, float, float] | None = None
    cells: frozenset[tuple[int, int, int]] | None = None
