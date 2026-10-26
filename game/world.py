"""Streaming B-Level world. World coordinates and Z are independent of B-Level.

Visited chunks and their neighbours stay resident (CHUNK_CACHE), so the ray
and FOV paths rarely regenerate or evict anything. Modified visited chunks are
spooled to an owned temporary directory and included in save files; writes are
queued and flushed between turns instead of during a rendered frame.
"""
import hashlib
import json
import os
import tempfile
from collections import OrderedDict, deque
from engine import config as C
from engine import fov as F
from .level import Level
from .rng import RNG
from . import mapgen as MG
from . import monsters as MON
from .items import Item, FOOD_POOL
from . import backrooms
from .level_catalog import profile as catalog_profile

CHUNK_CACHE = 24
PENDING_LIMIT = 6


class World:
    def __init__(self, seed, b_level=0, profile=None):
        self.seed = seed
        self.b_level = b_level
        if profile is None:
            path = os.path.join(C.BASE_DIR, "levels", f"{b_level}.json")
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    profile = json.load(f)
            else:
                profile = catalog_profile(b_level)
                if profile is None:
                    raise FileNotFoundError(f"No profile for B-Level {b_level}")
        self.profile = profile
        self.w, self.h = profile["chunk_size"]
        self.chunks = OrderedDict()
        self.visited = set()
        self.active_key = None
        self._light_dynamic = None
        self._light_personal = set()
        self._view_focus = None
        self._pending_writes = OrderedDict()
        self.storage = tempfile.TemporaryDirectory(prefix="nethack-world-")

    def exists(self, z):
        lo, hi = self.profile.get("z_min"), self.profile.get("z_max")
        return (lo is None or z >= lo) and (hi is None or z <= hi)

    def visible_z(self, z):
        return [n for n in range(z-2, z+3) if self.exists(n)]

    def path(self, key):
        return os.path.join(self.storage.name, "_".join(map(str, key)) + ".json")

    def chunk(self, cx, cy, z=0, visit=False):
        if not self.exists(z):
            return None
        key = (cx, cy, z)
        if visit:
            self.visited.add(key)
            self.active_key = key
        if key in self.chunks:
            self.chunks.move_to_end(key)
            return self.chunks[key]
        digest = hashlib.sha256(f"{self.seed}:{self.b_level}:{cx}:{cy}:{z}".encode()).digest()
        rng = RNG(int.from_bytes(digest[:8], "big"))
        illuminated=getattr(self,'_lighting_levels',{}).get(key)
        if illuminated is not None:
            lv=illuminated
        elif os.path.exists(self.path(key)):
            with open(self.path(key), encoding="utf-8") as f:
                lv = Level.deserialize(json.load(f), rng)
        else:
            layout = backrooms.generate(self.w,self.h,self.profile,rng,z)
            lv = Level(0, self.w, self.h, rng, generation=layout)
            if self.profile.get('vertical_test'):
                MG.vertical_test_layout(lv, z)
            # New chunks remain unexplored until reached by the shared FOV.
        lv.b_level, lv.world_z = self.b_level, z
        lv.chunk_x, lv.chunk_y = cx, cy
        lv.profile = self.profile
        if illuminated is None and not os.path.exists(self.path(key)):
            if self.profile.get('generator') != 'lobby':
                backrooms.decorate(lv,self.profile,rng)
            if self.profile.get('furniture',False):
                from .furniture import populate as populate_furniture
                populate_furniture(lv,rng)
            if self.profile.get('supplies', False):
                for room in lv.rooms[2::6]:
                    if rng.random()>self.profile.get('supply_chance',.4): continue
                    x, y = room.center()
                    if lv.at(x,y) not in (MG.FLOOR, MG.RUBBLE) or lv.furniture_at(x,y):
                        continue
                    lv.items[x, y] = Item(rng.choice(('crackers','apple','carrot','salted nuts','food ration')), rng=rng)
                    if rng.random()<.5 and lv.is_walkable(x + 1, y):
                        lv.items[x + 1, y] = Item(rng.choice(
                            ('water', 'distilled water', 'potion of healing', 'lantern')), rng=rng)
            for room in lv.rooms[4::4]:
                x, y = room.center()
                m = MON.spawn_random(lv, x, y, rng)
                if m is not None:
                    lv.monsters.append(m)
            # The first-pass lore entities need a valid themed tile. Small
            # levels such as the single bunker/cave would otherwise have no
            # room-center spawn point at all.
            if self.b_level in (7, 8, 10) and not lv.monsters:
                candidates = [(x, y) for y in range(lv.h) for x in range(lv.w)
                              if lv.is_walkable(x, y)]
                if candidates:
                    x, y = rng.choice(candidates)
                    m = MON.spawn_random(lv, x, y, rng)
                    if m is not None:
                        lv.monsters.append(m)
        backrooms.ensure_exits(lv,self.profile)
        self.chunks[key] = lv
        while len(self.chunks) > CHUNK_CACHE:
            if next(iter(self.chunks)) == self.active_key:
                self.chunks.move_to_end(self.active_key)
            old, chunk = self.chunks.popitem(last=False)
            if old in self.visited:
                self._pending_writes[old] = chunk
        if len(self._pending_writes) > PENDING_LIMIT:
            self.flush()
        return lv

    def flush(self):
        """Пишет отложенные чанки; вызывается между ходами, не в кадре."""
        pending, self._pending_writes = self._pending_writes, OrderedDict()
        for key, chunk in pending.items():
            with open(self.path(key), "w", encoding="utf-8") as f:
                json.dump(chunk.serialize(), f)

    def terrain(self, x, y, z):
        cx, lx = divmod(x, self.w)
        cy, ly = divmod(y, self.h)
        lv = self.chunk(cx, cy, z)
        return MG.WALL if lv is None else lv.at(lx, ly)

    def view_cells(self, player, lamp_modifier=1.0):
        """FOV coordinates relative to the player's chunk, including neighbours."""
        chunks = {}
        def resolve(x, y):
            cx, lx = divmod(x, self.w)
            cy, ly = divmod(y, self.h)
            key = (player.chunk_x+cx, player.chunk_y+cy, player.world_z)
            if key not in chunks:
                chunks[key] = self.chunk(*key)
            return chunks[key], lx, ly
        def blocked(x,y):
            lv,lx,ly = resolve(x,y)
            return not lv.can_see_through(lx,ly)
        radius = self.profile.get('fog_radius',C.FOV_RADIUS)
        if self.profile.get('absolute_darkness'):
            radius = 1  # tactile navigation; no distant terrain/entities revealed
        visible = F.compute_fov(player.x, player.y, radius, blocked)
        for lv in list(self.chunks.values()):
            lv.visible.clear()
        cells = {}
        focus = set()
        for x,y in visible:
            lv,lx,ly = resolve(x,y)
            lv.visible.add((lx,ly))
            lv.explored.add((lx,ly))
            self.visited.add((lv.chunk_x,lv.chunk_y,lv.world_z))
            cells[x,y] = (lv,lx,ly)
            focus.add((player.chunk_x*self.w+x, player.chunk_y*self.h+y, player.world_z))
        self._view_focus = focus
        return cells

    def update_lighting(self, player, has_lantern, modifier, lamp_states=None):
        """Shared BFS across chunk boundaries, with cached static light fields.

        lamp_states is accepted for API compatibility with Level.update_lighting;
        per-lamp flicker is approximated by the aggregated modifier because
        the flood field here is shared between many lamps and would need a
        separate BFS per lamp to reproduce individual strobing exactly.
        """
        if self.profile.get('absolute_darkness'):
            has_lantern = False
            modifier = 0.0
        period = self.profile.get('blackout_period',0)
        if period and player.turns % period >= period-self.profile.get('blackout_duration',0):
            modifier = 0.0
        gx = player.chunk_x*self.w + player.x
        gy = player.chunk_y*self.h + player.y
        # Lamps within 12 cells of the rendered horizon can affect that horizon.
        radius = C.FOV_RADIUS
        chunks = {}
        old_levels=getattr(self,'_lighting_levels',{})
        for z in self.visible_z(player.world_z):
            for cy in range((gy-radius)//self.h, (gy+radius)//self.h+1):
                for cx in range((gx-radius)//self.w, (gx+radius)//self.w+1):
                    pos=(cx,cy,z)
                    chunks[pos]=self.chunks.get(pos) or old_levels.get(pos) or self.chunk(*pos)
        self._lighting_levels=chunks
        geometry_key = (player.world_z, tuple(
             (pos, id(lv), lv.geometry_revision, tuple(sorted((p, tuple(sorted(d.items()))) for p,d in lv.doors.items())),
             tuple(lv.light_sources), tuple(r.lit for r in lv.rooms),
              tuple((f.kind,f.x,f.y,f.rotated) for f in lv.furniture)) for pos,lv in chunks.items()))
        key = (geometry_key,gx,gy,has_lantern)
        sample_key = (key, round(modifier*32))
        if sample_key == getattr(self, '_light_sample_key', None):
            return
        if geometry_key != getattr(self, '_static_light_key', None):
            cells = {(cx*self.w+x, cy*self.h+y,z): (lv,x,y)
                     for (cx,cy,z),lv in chunks.items()
                     for x in range(lv.w) for y in range(lv.h)}
            def flood(sources, reach):
                distances = {pos: 0 for pos in sources if pos in cells}
                queue = deque(distances)
                while queue:
                    x,y,z = queue.popleft()
                    dist = distances[x,y,z]
                    lv,lx,ly = cells[x,y,z]
                    if dist >= reach or not lv.can_see_through(lx,ly):
                        continue
                    neighbours=[(x+1,y,z),(x-1,y,z),(x,y+1,z),(x,y-1,z)]
                    upper=cells.get((x,y,z+1))
                    if upper and upper[0].at(upper[1],upper[2])==MG.AIR:
                        neighbours.append((x,y,z+1))
                    if lv.at(lx,ly)==MG.AIR:
                        neighbours.append((x,y,z-1))
                    for pos in neighbours:
                        if pos in cells and pos not in distances:
                            distances[pos] = dist+1
                            queue.append(pos)
                return {pos: 1-d/(reach+1) for pos,d in distances.items()}
            lamps = []
            for (cx,cy,z),lv in chunks.items():
                for x,y in lv.light_sources:
                    room = lv.room_at(x,y)
                    if room is None or room.lit:
                        lamps.append((cx*self.w+x,cy*self.h+y,z))
            self._static_fields=(cells,flood(lamps,12))
            self._flood_player=flood
            self._static_light_key=geometry_key
            self._light_dynamic=None
        fresh = key != getattr(self, '_light_key', None)
        if fresh:
            cells,lamps=self._static_fields
            self._light_fields=(cells,lamps,self._flood_player([(gx,gy,player.world_z)],12 if has_lantern else 10))
            self._light_key=key
        cells, lamps, personal = self._light_fields
        darkness = bool(self.profile.get('absolute_darkness'))
        scale = 1.0 if has_lantern or self.b_level==0 else .15
        changed_levels = set()

        def put(lv, x, y, value):
            if abs(lv.light_grid[x][y] - value) > 0.002:
                changed_levels.add(id(lv))
            lv.light_grid[x][y] = value

        if self._light_dynamic is None:
            # Первая сборка поля: значения нужны для всех клеток окрестности.
            dynamic = {}
            for pos,(lv,x,y) in cells.items():
                personal_light = personal.get(pos,0)*scale
                lamp = lamps.get(pos,0)
                value = max(0.05, personal_light, lamp*modifier)
                if darkness:
                    value = 0.0
                if lamp:
                    dynamic[pos] = (lv,x,y,lamp,max(0.05,personal_light))
                if abs(lv.light_grid[x][y] - value) > 0.002:
                    changed_levels.add(id(lv))
                lv.light_grid[x][y] = value
            self._light_dynamic = dynamic
            self._light_personal = set(personal)
        elif fresh:
            # Ход игрока двигает только персональный свет: клетки вне его
            # следа зависят от ламп и не изменились, писать их заново незачем.
            dynamic = self._light_dynamic
            for pos in set(personal) | self._light_personal:
                cell = cells.get(pos)
                if cell is None:
                    continue
                lv,x,y = cell
                base = max(0.05, personal.get(pos,0)*scale)
                entry = dynamic.get(pos)
                if entry is None:
                    put(lv,x,y, 0.0 if darkness else base)
                    continue
                lamp = entry[3]
                dynamic[pos] = (lv,x,y,lamp,base)
                put(lv,x,y, 0.0 if darkness else max(base, lamp*modifier))
            self._light_personal = set(personal)
        else:
            # Сменилась только выборка мерцания: обновляем клетки текущего
            # кадра, остальные догонит полный пересчёт при ближайшем ходе.
            focus = self._view_focus
            entries = (self._light_dynamic.get(pos) for pos in focus) if focus \
                else self._light_dynamic.values()
            for entry in entries:
                if entry is None:
                    continue
                lv,x,y,lamp,base = entry
                put(lv,x,y, 0.0 if darkness else max(base, lamp*modifier))
        for lv in chunks.values():
            if id(lv) in changed_levels:
                lv.lighting_revision = getattr(lv, 'lighting_revision', 0) + 1
        self._light_sample_key = sample_key

    def serialize(self):
        chunks = {}
        for key in self.visited:
            if key in self.chunks:
                data = self.chunks[key].serialize()
            elif key in self._pending_writes:
                data = self._pending_writes[key].serialize()
            else:
                with open(self.path(key), encoding="utf-8") as f:
                    data = json.load(f)
            chunks[",".join(map(str, key))] = data
        return {"seed": self.seed, "b_level": self.b_level, "profile": self.profile, "chunks": chunks}

    @classmethod
    def deserialize(cls, data):
        world = cls(data["seed"], data["b_level"], data["profile"])
        # Old Level 0 saves acquire progression without regenerating their maps.
        if world.b_level == 0 and 'next_level' not in world.profile:
            world.profile.update(exits=True,next_level=1,exit_label='br.exit.0')
        for text, chunk in data["chunks"].items():
            key = tuple(map(int, text.split(",")))
            world.visited.add(key)
            with open(world.path(key), "w", encoding="utf-8") as f:
                json.dump(chunk, f)
        return world
