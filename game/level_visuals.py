"""Compatibility adapter: existing Level containers remain gameplay-owned.

Tile writes are tracked; small mutable entity collections are compared on read.
No pygame/GL resources, callbacks on Item slots, or changes to save formats.
"""
import math

from engine.visual import Visual
from engine.visual_manager import VisualManager
from engine import config as C, glyphs as G
from . import mapgen as MG


class TileList(list):
    """List-compatible terrain with a change set (None means full replacement)."""
    def __init__(self, values):
        super().__init__(values)
        self.changed = None

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        if isinstance(key, slice):
            self.changed = None
        elif self.changed is not None:
            self.changed.add(key % len(self))

    def _mutate(self, method, *args, **kwargs):
        result = getattr(super(), method)(*args, **kwargs)
        self.changed = None
        return result

    def __delitem__(self, key): return self._mutate('__delitem__', key)
    def append(self, value): return self._mutate('append', value)
    def extend(self, values): return self._mutate('extend', values)
    def insert(self, index, value): return self._mutate('insert', index, value)
    def pop(self, index=-1): return self._mutate('pop', index)
    def remove(self, value): return self._mutate('remove', value)
    def clear(self): return self._mutate('clear')
    def reverse(self): return self._mutate('reverse')
    def sort(self, *args, **kwargs): return self._mutate('sort', *args, **kwargs)
    def __iadd__(self, values):
        self.extend(values)
        return self
    def __imul__(self, count):
        self._mutate('__imul__', count)
        return self


FEATURES = {
    MG.STAIR_DOWN: (G.T_STAIR_DOWN, C.C_STAIR),
    MG.STAIR_UP: (G.T_STAIR_UP, (120, 160, 220)),
    MG.ALTAR: (G.T_ALTAR, (222, 210, 180)),
    MG.FOUNTAIN: (G.T_FOUNTAIN, C.CYAN),
    MG.RUBBLE: (G.T_RUBBLE, (110, 100, 96)),
    MG.TRAPDOOR: (G.T_TRAP_DOOR, (150, 110, 70)),
}
MATERIALS = {'металл': 'metal', 'дерево': 'wood', 'ткань': 'fabric',
             'картон': 'cardboard', 'доски': 'wood',
             'металл/ткань': 'metal', 'дерево/металл': 'wood'}


class LevelVisuals:
    def __init__(self, level):
        self.level = level
        self.manager = VisualManager(self.sync, self.grid_spec)
        self.ids = {}
        self.signatures = {}
        self.groups = {}
        self.terrain_key = None
        self.door_state = {}

    def grid_spec(self):
        lv = self.level
        return lv.w, lv.h, lv.chunk_x * lv.w, lv.chunk_y * lv.h, lv.world_z

    def _put(self, key, visual):
        if key in self.ids:
            self.manager.update(self.ids[key], visual)
        else:
            self.ids[key] = self.manager.add(visual)

    def _remove(self, key):
        if key in self.ids:
            self.manager.remove(self.ids.pop(key))

    def _group(self, name, signature, build):
        if self.signatures.get(name) == signature:
            return
        self.signatures[name] = signature
        new = set()
        for key, visual in build():
            key = (name, key)
            new.add(key)
            self._put(key, visual)
        for key in self.groups.get(name, set()) - new:
            self._remove(key)
        self.groups[name] = new

    def sync(self):
        lv = self.level
        w, h, ox, oy, oz = self.grid_spec()
        profile = getattr(lv, 'profile', {})
        floor_mat = profile.get('floor_texture', 'carpet')
        wall_mat = profile.get('wall_texture', 'wallpaper')
        placement = (ox, oy, oz)
        terrain_key = (id(lv.tiles), w, h, placement, floor_mat, wall_mat)
        full = self.terrain_key != terrain_key or lv.tiles.changed is None
        changed = range(w*h) if full else set(lv.tiles.changed)
        doors = {pos: (bool(d.get('open')), bool(d.get('broken'))) for pos, d in lv.doors.items()}
        if not full:
            changed.update(lv.idx(*pos) for pos in self.door_state.keys() | doors.keys()
                           if self.door_state.get(pos) != doors.get(pos) and lv.in_bounds(*pos))
        for i in changed:
            x, y = i % w, i // w
            tile = lv.tiles[i]
            floor_key, wall_key = ('floor', i), ('wall', i)
            if tile == MG.AIR:
                self._remove(floor_key)
            else:
                self._put(floor_key, Visual(x=ox+x, y=oy+y, z=oz, height=.02,
                                           material=floor_mat, layer=0, tile_id=tile))
            blocked = tile in MG.OPAQUE or (tile == MG.DOOR and
                       (x, y) in doors and not any(doors[x, y]))
            if blocked:
                self._put(wall_key, Visual(x=ox+x, y=oy+y, z=oz, material=wall_mat,
                                          layer=1, opaque=True, tile_id=tile))
            else:
                self._remove(wall_key)
        self.terrain_key = terrain_key
        self.door_state = doors
        terrain_changed = full or bool(changed)
        lv.tiles.changed = set()

        furniture_sig = (placement, tuple((id(f), f.kind, f.x, f.y, f.rotated) for f in lv.furniture))
        if self.signatures.get('furniture') != furniture_sig:
            # Existing gameplay lookup also needs invalidation for same-size moves.
            lv._furniture_index_size = -1
        def furniture():
            for f in lv.furniture:
                spec = f.spec
                width, depth = spec['size']
                if f.rotated:
                    width, depth = depth, width
                lamp = f.kind == 'lamp post'
                yield id(f), Visual(x=ox+f.x, y=oy+f.y, z=oz, width=width, depth=depth,
                    height=.85, rotation=math.pi/2 if f.rotated else 0,
                    material=MATERIALS.get(spec['material'], spec['material']),
                    layer=2, sprite_id=spec['glyph'], color=spec['color'], opaque=spec['opaque'],
                    emits_light=lamp, light_color=(255, 230, 170), light_radius=12 if lamp else 0)
        self._group('furniture', furniture_sig, furniture)

        item_sig = (placement, tuple((pos, id(it), it.glyph, tuple(it.color)) for pos, it in lv.items.items()))
        self._group('items', item_sig, lambda: (
            (id(it), Visual(x=ox+x, y=oy+y, z=oz+.03, height=.3, material='metal',
                            layer=3, sprite_id=it.glyph, color=tuple(it.color)))
            for (x, y), it in lv.items.items()))
        monster_sig = (placement, tuple((id(m), m.x, m.y, m.alive, m.glyph, tuple(m.color)) for m in lv.monsters))
        self._group('monsters', monster_sig, lambda: (
            (id(m), Visual(x=ox+m.x, y=oy+m.y, z=oz+.1, height=.7, material='flesh',
                           layer=4, sprite_id=m.glyph, color=tuple(m.color)))
            for m in lv.monsters if m.alive))
        self._group('corpses', (placement, tuple(lv.corpses)), lambda: (
            (pos, Visual(x=ox+pos[0], y=oy+pos[1], z=oz+.025, height=.25, material='flesh',
                         layer=3, sprite_id='%', color=(128, 34, 34))) for pos in lv.corpses))
        self._group('lights', (placement, frozenset(lv.ceiling_lamps), tuple(lv.light_sources)), lambda: (
            (pos, Visual(x=ox+pos[0], y=oy+pos[1], z=oz+.9, height=.1,
                         material='metal', layer=5, emits_light=True,
                         light_color=(240, 235, 180), light_radius=12,
                         sprite_id='*' if pos in lv.ceiling_lamps else None, color=C.YELLOW))
            for pos in set(lv.light_sources) | lv.ceiling_lamps))
        if terrain_changed:
            self.signatures.pop('features', None)
        def features():
            for i, tile in enumerate(lv.tiles):
                if tile not in FEATURES:
                    continue
                x, y = i % w, i // w
                glyph, color = FEATURES[tile]
                passage = lv.exits.get((x, y))
                sign = passage and passage.get('method') != 'noclip'
                if sign:
                    glyph, color = 'exit_sign:' + str(passage['target']), C.GREEN
                yield i, Visual(x=ox+x, y=oy+y, z=oz + (.175 if sign else 0),
                                height=.85 if sign else .4, material='metal',
                                layer=2, sprite_id=glyph, color=color, tile_id=tile,
                                emits_light=bool(sign), light_color=C.GREEN)
        exits = tuple((pos, data.get('method'), data.get('target')) for pos, data in lv.exits.items())
        self._group('features', (placement, exits), features)
