"""Уровень подземелья: тайлы, видимость, сущности, предметы."""

from __future__ import annotations

import random
from collections import deque

from engine import config as C
from engine import fov as F
from engine import glyphs as G
from . import mapgen as MG
from . import monsters as MON
from .items import Item, make_random_item


class Level:
    @property
    def tiles(self):
        return self._tiles

    @tiles.setter
    def tiles(self, values):
        from .level_visuals import TileList
        if values is not getattr(self, '_tiles', None):
            self._tiles = TileList(values)

    @property
    def visual_manager(self):
        # Lazy construction also supports Level.__new__ and historical saves.
        if not hasattr(self, '_visuals'):
            from .level_visuals import LevelVisuals
            self._visuals = LevelVisuals(self)
        return self._visuals.manager

    def __init__(self, depth: int, w: int, h: int, rng: random, generation=None):
        self.depth = depth
        self.b_level = depth
        self.world_z = 0
        self.chunk_x = self.chunk_y = 0
        self.w, self.h = w, h
        self.rng = rng
        gen = generation if generation is not None else MG.generate_level(w, h, depth, rng)
        self.tiles: list[int] = gen["tiles"]
        self.rooms: list[MG.Room] = gen["rooms"]
        self.kind: str = gen["kind"]
        self.style: int = gen["style"]
        self.doors: dict[tuple[int, int], dict] = {}
        self.variant: list[int] = [rng.randrange(9) for _ in range(w * h)]
        self.explored: set[tuple[int, int]] = set()
        self.visible: set[tuple[int, int]] = set()
        self.mapped: set[tuple[int, int]] = set()
        self.monsters: list = []
        self.furniture = []
        self.items: dict[tuple[int, int], Item] = {}
        self.corpses: dict[tuple[int, int], str] = {}
        self.bones: set[tuple[int, int]] = set()
        # Future vertical transitions. Level 0 keeps this empty by profile.
        self.falls: dict[tuple[int, int], dict] = {}
        self.exits = {}
        self.hazards = {}
        self.stairs_down = (1, 1)
        self.altar_room: MG.Room | None = None
        self._room_at: dict[tuple[int, int], MG.Room] = {}
        self._index_rooms()
        # Логическое освещение не знает о pygame и может использоваться всеми
        # представлениями: light_grid[x][y] == 0..1.
        self.light_grid: list[list[float]] = [
            [0.05 for _ in range(self.h)] for _ in range(self.w)
        ]
        self.lighting_revision = 0
        self.geometry_revision = 0
        self.light_sources: list[tuple[int, int]] = [
            room.center() for room in self.rooms if self.in_bounds(*room.center())
        ]
        self.ceiling_lamps: set[tuple[int, int]] = set(gen.get("lamps", ()))
        if self.ceiling_lamps:
            # Deduplicate while preserving the light_sources contract.
            self.light_sources = list({*self.light_sources, *self.ceiling_lamps})

    def _index_rooms(self):
        self._room_at = {}
        for r in self.rooms:
            for y in range(r.y1, r.y2 + 1):
                for x in range(r.x1, r.x2 + 1):
                    self._room_at.setdefault((x, y), r)

    def room_at(self, x, y) -> MG.Room | None:
        return self._room_at.get((x, y))

    def is_lit(self, x, y) -> bool:
        """Комната освещена (коридоры и лестницы видны всегда)."""
        r = self._room_at.get((x, y))
        return True if r is None else r.lit

    # --- Доступ к тайлам --------------------------------------------------
    def idx(self, x, y):
        return y * self.w + x

    def in_bounds(self, x, y):
        return 0 <= x < self.w and 0 <= y < self.h

    def at(self, x, y):
        if not self.in_bounds(x, y):
            return MG.WALL
        return self.tiles[self.idx(x, y)]

    def set(self, x, y, v):
        if self.in_bounds(x, y):
            self.tiles[self.idx(x, y)] = v
            self.geometry_revision += 1

    def is_wall(self, x, y):
        furniture=self.furniture_at(x,y)
        return self.at(x, y) in MG.OPAQUE or (furniture is not None and not furniture.spec.get('damage'))

    def furniture_at(self,x,y):
        if getattr(self,'_furniture_index_size',-1)!=len(self.furniture):
            self._furniture_index={pos:obj for obj in self.furniture for pos in obj.cells()}
            self._furniture_index_size=len(self.furniture)
        return self._furniture_index.get((x,y))

    def is_walkable(self, x, y):
        furniture=self.furniture_at(x,y)
        if not self.in_bounds(x, y) or self.at(x, y) not in MG.WALKABLE:
            return False
        if self.at(x, y) == MG.WATER and not getattr(self, 'profile', {}).get('swimming'):
            return False
        return furniture is None or bool(furniture.spec.get('damage'))

    def can_see_through(self, x, y):
        furniture=self.furniture_at(x,y)
        if furniture is not None and furniture.spec['opaque']:
            return False
        t = self.at(x, y)
        if t in MG.OPAQUE:
            return False
        if t == MG.DOOR:
            d = self.doors.get((x, y))
            if d and not d.get("open") and not d.get("broken"):
                return False
        return True

    # --- Соседи ------------------------------------------------------------
    def neighbors(self, x, y):
        return ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))

    def blocker_set(self):
        return {(x, y) for x in range(self.w) for y in range(self.h)
                if not self.can_see_through(x, y)}

    # --- Поле зрения -------------------------------------------------------
    def recompute_fov(self, px, py, radius=None):
        radius = radius or C.FOV_RADIUS
        profile = getattr(self,'profile',{})
        radius = min(radius,profile.get('fog_radius',radius))
        if profile.get('absolute_darkness'):
            radius = 1
        vis = F.compute_fov(px, py, radius, lambda x, y: not self.can_see_through(x, y))
        vis = {(x, y) for (x, y) in vis if self.in_bounds(x, y)}
        self.visible = vis
        self.explored |= vis
        return vis

    def lit_tiles(self):
        return self.visible

    def update_lighting(self, player_x, player_y, has_lantern=False,
                        lamp_flicker_modifier=1.0, lamp_states=None):
        """Пересчитывает свет BFS-волнами от игрока и центров комнат.

        Стены и закрытые двери получают свет на своей клетке, но не передают
        его дальше. Матрица индексируется как light_grid[x][y].

        lamp_states: optional dict[(x, y) -> float 0..1] with per-lamp
        flicker intensity.  When a lamp is not in the dict, the global
        lamp_flicker_modifier is used.  This lets individual fluorescent
        panels die out or strobe while the rest of the level hums along.
        """
        ambient = 0.05
        previous = getattr(self, 'light_grid', None)
        self.light_grid = [[ambient for _ in range(self.h)] for _ in range(self.w)]
        sources: list[tuple[int, int, float, int]] = []
        if self.in_bounds(player_x, player_y):
            player_radius = 12 if has_lantern else 10
            sources.append((player_x, player_y, 1.0, player_radius))
        base_strength = max(0.1, min(1.0, float(lamp_flicker_modifier)))
        lamp_states = lamp_states or {}
        for x, y in self.light_sources:
            room = self.room_at(x, y)
            if self.in_bounds(x, y) and (room is None or room.lit):
                # Per-lamp flicker overrides the global modifier.
                strength = lamp_states.get((x, y), base_strength)
                strength = max(0.0, min(1.0, strength))
                if strength < 0.05:
                    continue  # lamp is dead right now
                sources.append((x, y, strength, 12))

        # Источники обрабатываются одной очередью. Максимум уже записанной
        # яркости предотвращает повторное расширение слабой волны.
        queue = deque()
        for sx, sy, strength, radius in sources:
            self.light_grid[sx][sy] = max(self.light_grid[sx][sy], strength)
            queue.append((sx, sy, strength, radius, 0))
        while queue:
            x, y, source_strength, radius, distance = queue.popleft()
            if distance >= radius:
                continue
            next_distance = distance + 1
            value = source_strength * (1.0 - next_distance / (radius + 1.0))
            if value <= ambient:
                continue
            for nx, ny in self.neighbors(x, y):
                if not self.in_bounds(nx, ny):
                    continue
                old = self.light_grid[nx][ny]
                if value <= old + 1e-6:
                    continue
                self.light_grid[nx][ny] = value
                # Преграда освещается, но останавливает распространение.
                if self.can_see_through(nx, ny):
                    queue.append((nx, ny, source_strength, radius, next_distance))
        changed = previous is None or any(
            abs(previous[x][y] - self.light_grid[x][y]) > 0.002
            for x in range(self.w) for y in range(self.h))
        if changed:
            self.lighting_revision = getattr(self, 'lighting_revision', 0) + 1

    # --- Навигация ---------------------------------------------------------
    def bfs(self, sx, sy, targets, max_dist=40, avoid_walls=True):
        """Кратчайшие пути от (sx,sy) к набору целей. -> dict[(x,y)] -> (prev, dist)"""
        if not targets:
            return {}
        tset = set(targets)
        prev = {(sx, sy): None}
        q = deque([(sx, sy)])
        dist = 0
        found = {}
        while q and dist < max_dist:
            for _ in range(len(q)):
                x, y = q.popleft()
                if (x, y) in tset and (x, y) != (sx, sy):
                    found[(x, y)] = dist
                for nx, ny in self.neighbors(x, y):
                    if (nx, ny) in prev or not self.in_bounds(nx, ny):
                        continue
                    if avoid_walls and self.is_wall(nx, ny):
                        continue
                    if (nx, ny) not in self.explored and (nx, ny) not in self.mapped:
                        continue
                    prev[(nx, ny)] = (x, y)
                    q.append((nx, ny))
            dist += 1
        return prev

    def next_step(self, sx, sy, tx, ty, max_dist=40):
        """Первый шаг кратчайшего пути от (sx,sy) к (tx,ty) или None."""
        prev = self.bfs(sx, sy, [(tx, ty)], max_dist)
        if (tx, ty) not in prev:
            return None
        node = (tx, ty)
        parent = prev.get(node)
        while parent is not None and parent != (sx, sy):
            node = parent
            parent = prev.get(node)
        if node == (sx, sy):
            return None
        return node

    def random_open_tile(self, far=False, tries=400):
        best = None
        for _ in range(tries):
            x = self.rng.randrange(1, self.w - 1)
            y = self.rng.randrange(1, self.h - 1)
            if not self.is_walkable(x, y):
                continue
            if (x, y) in self.items or (x, y) in self.corpses:
                continue
            if self.monster_at(x, y):
                continue
            best = (x, y)
            if not far:
                return best
            break
        if best is None:
            for r in self.rooms:
                if self.is_walkable(r.cx, r.cy):
                    return (r.cx, r.cy)
        return best

    def random_tile_in(self, room, tries=24, exclude=None):
        """Свободная клетка внутри комнаты (с учётом колонн и декора)."""
        x1, y1, x2, y2 = room.inner()
        x1 = max(1, x1)
        y1 = max(1, y1)
        x2 = min(self.w - 2, x2)
        y2 = min(self.h - 2, y2)
        if x2 < x1 or y2 < y1:
            return None
        for _ in range(tries):
            x = self.rng.randint(x1, x2)
            y = self.rng.randint(y1, y2)
            if exclude and (x, y) in exclude:
                continue
            if not self.is_walkable(x, y):
                continue
            if (x, y) in self.items or (x, y) in self.corpses:
                continue
            if self.monster_at(x, y):
                continue
            return (x, y)
        return None

    def door_tiles(self, room):
        """Клетки дверей, примыкающих к комнате."""
        out = []
        for x, y in room.perimeter():
            if self.in_bounds(x, y) and self.at(x, y) == MG.DOOR:
                out.append((x, y))
        return out

    # --- Сущности ----------------------------------------------------------
    def monster_at(self, x, y):
        for m in self.monsters:
            if m.alive and m.x == x and m.y == y:
                return m
        return None

    def monsters_at(self, x, y):
        return [m for m in self.monsters if m.alive and m.x == x and m.y == y]

    def item_at(self, x, y):
        return self.items.get((x, y))

    def add_item(self, x, y, item):
        self.items[(x, y)] = item

    def drop_item(self, item, x=None, y=None):
        """Place an item without overwriting another ground item."""
        if x is None and hasattr(item, "x"):
            x = item.x
        if x is None or y is None:
            spot = self.random_open_tile()
            candidates = [spot] if spot is not None else []
        else:
            candidates = [(x, y)]
            candidates.extend((nx, ny) for radius in range(1, max(self.w, self.h))
                              for ny in range(max(0, y-radius), min(self.h, y+radius+1))
                              for nx in range(max(0, x-radius), min(self.w, x+radius+1))
                              if abs(nx-x)+abs(ny-y) == radius)
        spot = next((pos for pos in candidates
                     if pos is not None and self.is_walkable(*pos)
                     and pos not in self.items and self.monster_at(*pos) is None), None)
        if spot is None:
            return None
        self.items[spot] = item
        return spot

    def aggravate(self):
        n = 0
        for m in self.monsters:
            if m.alive:
                m.awake = True
                m.status["flee"] = 0
                m.energy = self.rng.randrange(50, 150)
                n += 1
        return n

    def area_effect(self, x, y, radius=2):
        return [m for m in self.monsters
                if m.alive and F.distance(x, y, m.x, m.y) <= radius]

    def dig_near(self, x, y, radius=1, target=None):
        changed = False
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                tx, ty = x + dx, y + dy
                if not self.in_bounds(tx, ty) or (target is not None and (tx, ty) != target):
                    continue
                if (tx, ty) == (x, y) or abs(dx) + abs(dy) > radius:
                    continue
                if self.is_wall(tx, ty):
                    self.set(tx, ty, MG.FLOOR)
                    changed = True
        if changed:
            self.recompute_fov(*self._player_pos())
        return changed

    def add_fall(self, x, y, to_z, enabled=True):
        """Register a future vertical fall without activating it automatically."""
        if self.in_bounds(x, y):
            self.falls[(x, y)] = {"from_z": self.world_z, "to_z": int(to_z),
                                  "height": abs(int(to_z) - self.world_z),
                                  "enabled": bool(enabled)}

    def _player_pos(self):
        return self._pp if hasattr(self, "_pp") else (0, 0)

    def set_player_pos(self, x, y):
        self._pp = (x, y)

    # --- Картографирование -------------------------------------------------
    def map_area(self, radius=6):
        px, py = self._player_pos()
        r2 = radius * radius
        self.mapped |= {(x, y) for x, y in self.explored
                        if (x - px) ** 2 + (y - py) ** 2 <= r2}

    def magic_map(self):
        self.mapped |= {(x, y) for x in range(self.w) for y in range(self.h)
                        if not self.is_wall(x, y)}

    # --- Описание ----------------------------------------------------------
    def describe_tile(self, x, y) -> str:
        furniture=self.furniture_at(x,y)
        if furniture is not None: return furniture.spec['name']
        from .lang import t
        if (x,y) in self.exits:
            exit_ = self.exits[x,y]
            return t(exit_['label']) + ' — ' + t('br.exit_hint',n=exit_['target'])
        if (x,y) in self.hazards:
            return t('br.hazard.'+self.hazards[x,y])
        t_ = self.at(x, y)
        if t_ == MG.AIR:
            return t('vertical.air')
        if t_ == MG.WALL:
            return t("t.wall")
        if t_ == MG.HEDGE:
            return t("t.hedge")
        if t_ == MG.DOOR:
            d = self.doors.get((x, y))
            if d and d.get("locked") and not d.get("broken"):
                return t("t.locked")
            if d and not d.get("open") and not d.get("broken"):
                return t("t.closed")
            return t("t.open")
        if t_ == MG.STAIR_DOWN:
            return t("t.down")
        if t_ == MG.STAIR_UP:
            return t("t.up")
        if t_ == MG.ALTAR:
            return t("t.altar")
        if t_ == MG.FOUNTAIN:
            return t("t.fountain")
        if t_ == MG.RUBBLE:
            return t("t.rubble")
        if t_ == MG.TRAPDOOR:
            return t("t.trapdoor")
        if t_ == MG.WATER:
            return t("t.water")
        return t("t.floor")

    def serialize(self) -> dict:
        return {
            "depth": self.depth, "w": self.w, "h": self.h,
            "tiles": self.tiles, "variant": self.variant,
            "rooms": [r.to_dict() for r in self.rooms],
            "kind": self.kind, "style": self.style,
            "doors": {f"{k[0]},{k[1]}": v for k, v in self.doors.items()},
            "explored": [list(p) for p in self.explored],
            "mapped": [list(p) for p in self.mapped],
            "stairs_down": list(self.stairs_down),
            "monsters": [monster_to_dict(m) for m in self.monsters],
            "furniture": [obj.serialize() for obj in self.furniture],
            "items": {f"{k[0]},{k[1]}": v.to_dict() for k, v in self.items.items()},
            "corpses": {f"{k[0]},{k[1]}": v for k, v in self.corpses.items()},
            "bones": [list(p) for p in self.bones],
            "b_level": self.b_level, "world_z": self.world_z,
            "chunk_x": self.chunk_x, "chunk_y": self.chunk_y,
            "falls": {f"{k[0]},{k[1]}": v for k, v in self.falls.items()},
            "exits": {f"{k[0]},{k[1]}": v for k,v in self.exits.items()},
            "hazards": {f"{k[0]},{k[1]}": v for k,v in self.hazards.items()},
            "ceiling_lamps": [list(p) for p in self.ceiling_lamps],
            "light_sources": [list(p) for p in self.light_sources],
            "lighting_revision": self.lighting_revision,
            "geometry_revision": self.geometry_revision,
        }

    @staticmethod
    def deserialize(data: dict, rng):
        lv = Level.__new__(Level)
        lv.depth = data["depth"]
        from .furniture import Furniture
        lv.furniture=[Furniture.deserialize(obj) for obj in data.get('furniture',[])]
        lv.b_level = data.get("b_level", lv.depth)
        lv.world_z = data.get("world_z", 0)
        lv.chunk_x = data.get("chunk_x", 0)
        lv.chunk_y = data.get("chunk_y", 0)
        lv.w, lv.h = data["w"], data["h"]
        lv.rng = rng
        lv.tiles = data["tiles"]
        lv.variant = data["variant"]
        lv.rooms = [MG.Room.from_dict(r) for r in data["rooms"]]
        lv.kind = data["kind"]
        lv.style = data["style"]
        lv.doors = {tuple(int(v) for v in k.split(",")): val for k, val in data["doors"].items()}
        lv.explored = {tuple(p) for p in data["explored"]}
        lv.visible = set()
        lv.mapped = {tuple(p) for p in data["mapped"]}
        lv.stairs_down = tuple(data["stairs_down"])
        lv.monsters = [monster_from_dict(m) for m in data["monsters"]
                       if m["name"] not in MON.RETIRED_NAMES]
        for m in lv.monsters:
            m.b_level, m.world_z = lv.b_level, lv.world_z
        lv.items = {tuple(int(v) for v in k.split(",")): Item.from_dict(v)
                    for k, v in data["items"].items()}
        lv.corpses = {tuple(int(v) for v in k.split(",")): v
                     for k, v in data["corpses"].items() if v not in MON.RETIRED_NAMES}
        lv.bones = {tuple(p) for p in data["bones"]}
        lv.falls = {tuple(int(v) for v in k.split(",")): val
                    for k, val in data.get("falls", {}).items()}
        lv.exits = {tuple(map(int,k.split(','))):v for k,v in data.get('exits',{}).items()}
        lv.hazards = {tuple(map(int,k.split(','))):v for k,v in data.get('hazards',{}).items()}
        lv.ceiling_lamps = {tuple(p) for p in data.get("ceiling_lamps", [])}
        lv.altar_room = None
        lv._room_at = {}
        lv._index_rooms()
        lv.light_grid = [[0.05 for _ in range(lv.h)] for _ in range(lv.w)]
        lv.lighting_revision = data.get("lighting_revision", 0)
        lv.geometry_revision = data.get("geometry_revision", 0)
        lv.light_sources = [r.center() for r in lv.rooms
                            if lv.in_bounds(*r.center())]
        lv.light_sources = list({*lv.light_sources, *lv.ceiling_lamps})
        if "light_sources" in data:
            lv.light_sources = [tuple(p) for p in data["light_sources"]]
        return lv


# --------------------------------------------------------------------------
def monster_to_dict(m) -> dict:
    return {
        "x": m.x, "y": m.y, "name": m.name, "glyph": m.glyph, "color": list(m.color),
        "hp": m.hp, "max_hp": m.max_hp, "base_ac": m.base_ac, "dmg": list(m.dmg),
        "to_hit": m.to_hit, "speed": m.speed, "depth": m.depth, "tier": m.tier,
        "status": dict(m.status), "awake": m.awake, "hostile": m.hostile,
        "corpse": m.corpse, "energy": m.energy,
        "b_level": m.b_level, "world_z": m.world_z,
        "behavior": m.behavior, "last_seen": m.last_seen,
    }


def monster_from_dict(d: dict):
    from .entities import Actor
    m = Actor(x=d["x"], y=d["y"], name=d["name"], glyph=d["glyph"],
              color=tuple(d["color"]), hp=d["hp"], max_hp=d["max_hp"],
              ac=d["base_ac"], dmg=tuple(d["dmg"]), to_hit=d["to_hit"],
              speed=d["speed"], depth=d["depth"], tier=d["tier"])
    m.status = dict(d.get("status", {}))
    m.awake = d.get("awake", False)
    m.hostile = d.get("hostile", True)
    m.corpse = d.get("corpse", False)
    m.energy = d.get("energy", 0)
    m.b_level = d.get("b_level", m.depth)
    m.world_z = d.get("world_z", 0)
    m.behavior = d.get("behavior", "chase")
    m.last_seen = d.get("last_seen")
    return m


# --------------------------------------------------------------------------
def _treasure(depth: int, rng: random):
    """Ценный предмет для особых залов."""
    from .items import ITEMS, Item, make_random_item
    for _ in range(8):
        it = make_random_item(depth, rng=rng)
        if it.kind == "gold" or it.value >= 120:
            return it
    it = Item("gold piece", rng=rng)
    it.qty = rng.randint(25, 140) + depth * 12
    it.value = it.qty
    return it


def populate(level: Level, rng: random, density: float = 1.0):
    if level.depth == 0:
        return
    """Расставляет лестницы, особые залы, предметы и монстров."""
    walkable = [(x, y) for y in range(level.h) for x in range(level.w)
                if level.is_walkable(x, y)]
    if not walkable:
        return

    rooms = [r for r in level.rooms if r.area >= 6]
    if not rooms:
        return
    level.ceiling_lamps = {r.center() for r in rooms if rng.random() < 0.35}
    level.light_sources = list({*level.light_sources, *level.ceiling_lamps})
    start = rooms[0]
    safe = start.center()

    # --- лестница вниз: подальше от входа, но не в хранилище ---
    pool = [r for r in rooms if r.purpose != "vault"]
    if len(pool) >= 2:
        far = max(pool, key=lambda r: F.distance(*safe, r.cx, r.cy))
        spot = level.random_tile_in(far) or far.center()
    else:
        spot = level.random_tile_in(rooms[-1]) or rooms[-1].center()
    level.set(*spot, MG.STAIR_DOWN)
    level.stairs_down = spot

    # --- особые залы ---
    avoid = {level.stairs_down}
    for r in rooms:
        purpose = r.purpose
        if purpose == "temple":
            t = level.random_tile_in(r, exclude=avoid) or r.center()
            level.set(*t, MG.ALTAR)
            level.altar_room = r
        elif purpose == "fountain":
            for _ in range(rng.randint(2, 4)):
                t = level.random_tile_in(r, exclude=avoid)
                if t:
                    level.set(*t, MG.FOUNTAIN)
        elif purpose == "treasury":
            for _ in range(rng.randint(4, 8)):
                t = level.random_tile_in(r, exclude=avoid)
                if t and t not in level.items:
                    level.items[t] = _treasure(level.depth, rng)
        elif purpose == "vault":
            for _ in range(rng.randint(4, 7)):
                t = level.random_tile_in(r, exclude=avoid)
                if t and t not in level.items:
                    level.items[t] = _treasure(level.depth + 3, rng)
            for _ in range(rng.randint(2, 3)):
                t = level.random_tile_in(r, exclude=avoid)
                if t and not level.monster_at(*t):
                    m = MON.spawn_random(level, t[0], t[1], rng, depth=level.depth + 2)
                    if m is not None:
                        m.awake = True
                        level.monsters.append(m)
        elif purpose == "throne":
            for _ in range(rng.randint(2, 3)):
                t = level.random_tile_in(r, exclude=avoid)
                if t and not level.monster_at(*t):
                    m = MON.spawn_random(level, t[0], t[1], rng, depth=level.depth + 1)
                    if m is not None:
                        m.awake = True
                        level.monsters.append(m)
        elif purpose == "barracks":
            for _ in range(rng.randint(3, 5)):
                t = level.random_tile_in(r, exclude=avoid)
                if t and not level.monster_at(*t):
                    m = MON.spawn_random(level, t[0], t[1], rng, depth=level.depth + 1)
                    if m is not None:
                        level.monsters.append(m)

    # --- обычный декор ---
    for r in rooms:
        if r.purpose:
            continue
        roll = rng.random()
        if roll < 0.09 and r.area >= 18:
            level.set(r.cx, r.cy, MG.ALTAR)
            level.altar_room = r
        elif roll < 0.16 and r.area >= 14:
            t = level.random_tile_in(r)
            if t:
                level.set(*t, MG.FOUNTAIN)
        elif roll < 0.24:
            t = level.random_tile_in(r)
            if t:
                level.set(*t, MG.RUBBLE)

    # --- лестница гарантированно на месте ---
    level.set(*level.stairs_down, MG.STAIR_DOWN)

    # --- предметы на полу ---
    free = [p for p in walkable
            if level.at(*p) not in (MG.STAIR_DOWN, MG.ALTAR, MG.FOUNTAIN)
            and p not in level.items]
    rng.shuffle(free)
    n_items = max(3, int(len(walkable) / 26 * density))
    for pos in free[:n_items]:
        level.items[pos] = make_random_item(level.depth, rng=rng)

    # --- монстры: не во входной комнате ---
    candidates = [p for p in free[n_items:]
                  if F.distance(*safe, p[0], p[1]) > 9
                  and level.at(*p) != MG.STAIR_DOWN]
    n_mons = max(2, int(len(candidates) / 34 * density + level.depth * 0.7))
    for pos in candidates[:n_mons]:
        if level.monster_at(*pos):
            continue
        m = MON.spawn_random(level, pos[0], pos[1], rng)
        if m is not None:
            level.monsters.append(m)

    # --- гарнизон в дальней обычной комнате ---
    guards = [r for r in rooms[1:] if r.purpose is None]
    if guards:
        guard_room = max(guards, key=lambda r: F.distance(*safe, r.cx, r.cy))
        for _ in range(1 + level.depth // 8):
            t = level.random_tile_in(guard_room)
            if t and not level.monster_at(*t):
                m = MON.spawn_random(level, t[0], t[1], rng, depth=level.depth + 3)
                if m is not None:
                    m.awake = True
                    level.monsters.append(m)
