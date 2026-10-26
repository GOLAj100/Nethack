"""Stable visual IDs, spatial/layer indexes and cached terrain snapshots."""
from dataclasses import dataclass, fields
from math import ceil, floor

from .visual import Visual, VisualCamera


@dataclass(slots=True)
class VisualGrid:
    tiles: list
    walls: bytearray
    floors: bytearray
    materials: list
    floor_materials: list
    fixtures: list


class VisualManager:
    def __init__(self, synchronize=None, grid_spec=None):
        self._synchronize = synchronize
        self._syncing = False
        self._objects = {}
        self._layers = {}
        self._cells = {}
        self._footprints = {}
        self._next_id = 1
        self.revision = 0
        self.geometry_revision = 0
        self._grid_spec = grid_spec
        self._grid_cache = None
        self._visible_cache = None

    def sync(self):
        if self._synchronize is not None and not self._syncing:
            self._syncing = True
            try:
                self._synchronize()
            finally:
                self._syncing = False
        return self

    def __len__(self):
        self.sync()
        return len(self._objects)

    @staticmethod
    def _coverage(v):
        return tuple((x, y, z)
                     for z in range(floor(v.z), ceil(v.z + max(0, v.height)))
                     for y in range(floor(v.y), ceil(v.y + max(0, v.depth)))
                     for x in range(floor(v.x), ceil(v.x + max(0, v.width))))

    def _index(self, key, v):
        cells = self._coverage(v)
        self._footprints[key] = (v.layer, cells)
        self._layers.setdefault(v.layer, {})[key] = v
        for cell in cells:
            self._cells.setdefault(cell, set()).add(key)

    def _unindex(self, key):
        layer, cells = self._footprints.pop(key)
        self._layers[layer].pop(key)
        for cell in cells:
            bucket = self._cells[cell]
            bucket.remove(key)
            if not bucket:
                del self._cells[cell]

    @staticmethod
    def _geometry(v):
        return v.layer in (0, 1, 2) or v.opaque

    def _changed(self, geometry=True):
        self.revision += 1
        self._visible_cache = None
        if geometry:
            self.geometry_revision += 1
            self._grid_cache = None

    def add(self, visual):
        key = self._next_id
        self._next_id += 1
        visual.dirty = True
        self._objects[key] = visual
        self._index(key, visual)
        self._changed(self._geometry(visual))
        return key

    def remove(self, key):
        if key in self._objects:
            geometry = self._geometry(self._objects[key])
            self._unindex(key)
            del self._objects[key]
            self._changed(geometry)

    def update(self, key, visual):
        """Update in place so held Visual references and IDs remain valid."""
        current = self._objects[key]
        names = [f.name for f in fields(Visual) if f.name != 'dirty']
        if any(getattr(current, n) != getattr(visual, n) for n in names):
            geometry = self._geometry(current) or self._geometry(visual)
            self._unindex(key)
            for name in names:
                setattr(current, name, getattr(visual, name))
            current.dirty = True
            self._index(key, current)
            self._changed(geometry)

    @staticmethod
    def _order(v):
        return v.layer, v.z, v.y

    def get_by_layer(self, layer):
        self.sync()
        return sorted(self._layers.get(layer, {}).values(), key=self._order)

    def get_at(self, x, y, z):
        self.sync()
        candidates = (self._objects[k] for k in self._cells.get((floor(x), floor(y), floor(z)), ()))
        return max((v for v in candidates if v.visible and
                    v.x <= x < v.x + v.width and v.y <= y < v.y + v.depth and
                    v.z <= z < v.z + v.height), key=self._order, default=None)

    def mark_dirty(self, key):
        self.sync()
        if key in self._objects:
            self._unindex(key)
            self._objects[key].dirty = True
            self._index(key, self._objects[key])
            # The caller may have changed opacity/layer before notifying us.
            self._changed()

    def clear_dirty(self):
        self.sync()
        for v in self._objects.values():
            v.dirty = False

    def iter_visible(self, camera=None):
        self.sync()
        camera = camera or VisualCamera()
        cache_key = (self.revision, camera)
        if self._visible_cache is not None and self._visible_cache[0] == cache_key:
            return iter(self._visible_cache[1])
        if camera.cells is None:
            keys = self._objects.keys()
        else:
            keys = set()
            for cell in camera.cells:
                keys.update(self._cells.get(cell, ()))
            keys = sorted(keys)  # Stable tie order even when the FOV is a set.
        result = []
        for key in keys:
            v = self._objects[key]
            if not v.visible:
                continue
            if camera.bounds is not None:
                left, top, right, bottom, low, high = camera.bounds
                if not (v.x < right and v.x + v.width > left and
                        v.y < bottom and v.y + v.depth > top and
                        v.z < high and v.z + v.height > low):
                    continue
            result.append(v)
        result.sort(key=self._order)
        self._visible_cache = (cache_key, tuple(result))
        return iter(result)

    def grid(self):
        """Local cell snapshot for a Level; synchronize once, then index arrays.

        Layer 1 walls and opaque furniture block rays. Layer 0 owns floor slabs.
        This never queries the legacy tile/furniture containers.
        """
        self.sync()
        if self._grid_cache is not None:
            return self._grid_cache
        w, h, ox, oy, oz = self._grid_spec()
        grid = VisualGrid([10] * (w*h), bytearray(w*h), bytearray(w*h), [None] * (w*h), [None] * (w*h), [None] * (w*h))
        for key, visual in self._objects.items():
            if not visual.visible or (visual.layer not in (0, 1, 2) and not visual.opaque):
                continue
            for x, y, z in self._footprints[key][1]:
                x, y = x - ox, y - oy
                if z != oz or not (0 <= x < w and 0 <= y < h):
                    continue
                i = y*w + x
                if visual.layer == 0:
                    grid.floors[i] = 1
                    grid.tiles[i] = visual.tile_id if visual.tile_id is not None else 1
                    grid.floor_materials[i] = visual
                if visual.layer == 1 or visual.opaque:
                    grid.walls[i] = 1
                    grid.materials[i] = visual
                if visual.layer == 2 and visual.tile_id is None:
                    grid.fixtures[i] = visual
        self._grid_cache = grid
        return grid

    def blocks_cell(self, x, y):
        grid = self.grid()
        w, h, *_ = self._grid_spec()
        return not (0 <= x < w and 0 <= y < h) or bool(grid.walls[y*w+x])

    def has_floor(self, x, y):
        grid = self.grid()
        w, h, *_ = self._grid_spec()
        return 0 <= x < w and 0 <= y < h and bool(grid.floors[y*w+x])
