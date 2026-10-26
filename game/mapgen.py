"""Процедурная генерация уровней: комнаты, коридоры, пещеры, особые залы.

Гарантии:
  * все комнаты достижимы (флуд-заливка + дополнительные коридоры);
  * у каждой комнаты есть хотя бы одна дверь;
  * есть особые залы: храм, сокровищница, тронный зал, казармы,
    фонтанный зал и хранилище с запертой дверью.
"""

from __future__ import annotations

import random
from collections import deque

from engine import config as C

WALL, FLOOR, DOOR, STAIR_DOWN, STAIR_UP, RUBBLE, ALTAR, FOUNTAIN, HEDGE, TRAPDOOR, WATER = range(11)

WALKABLE = {FLOOR, DOOR, STAIR_DOWN, STAIR_UP, RUBBLE, ALTAR, FOUNTAIN, TRAPDOOR, WATER}
OPAQUE = {WALL, HEDGE}
AIR = 11; WINDOW = 12; PIPE = 13; BLACK_GRASS = 14
WALKABLE.update((AIR, BLACK_GRASS))


def vertical_test_layout(level, z):
    """Aligned structures across Z: sunken hall, bridge, stairs, double height."""
    if level.w < 65 or level.h < 40:
        return
    # A two-storey hall and a neighbouring pit room, connected to corridors.
    for x0, y0, x1, y1 in ((10, 10, 29, 29), (40, 10, 59, 29)):
        for y in range(y0, y1+1):
            for x in range(x0, x1+1):
                edge = x in (x0,x1) or y in (y0,y1)
                level.set(x,y,WALL if edge else FLOOR)
        for x in (x0,x1):
            level.set(x,20,FLOOR)
            level.set(x,21,FLOOR)
    if z == 1:
        for y in range(11,29):
            for x in range(11,29):
                level.set(x,y,AIR)
    if z == 0:
        for y in range(12,28):
            for x in range(42,58):
                level.set(x,y,FLOOR if y in (20,21) else AIR)
    # Two independent paired stairs, from basement to lobby and lobby upstairs.
    if z == -1:
        level.set(41,20,STAIR_UP)
    if z == 0:
        level.set(41,20,STAIR_DOWN)
        level.set(30,20,STAIR_UP)
    if z == 1:
        level.set(30,20,STAIR_DOWN)

LEVEL_TYPES = {
    1: ("dungeon", 0), 2: ("dungeon", 1), 3: ("dungeon", 2), 4: ("dungeon", 3),
    5: ("dungeon", 4), 6: ("mine", 2), 7: ("mine", 3), 8: ("dungeon", 0),
    9: ("dungeon", 1), 10: ("orc", 4), 11: ("mine", 3), 12: ("dungeon", 2),
    13: ("orc", 4), 14: ("dungeon", 1), 15: ("mine", 2), 16: ("orc", 4),
    17: ("dungeon", 3), 18: ("mine", 3), 19: ("dungeon", 0), 20: ("orc", 4),
    21: ("mine", 2), 22: ("dungeon", 1), 23: ("dungeon", 2), 24: ("mine", 3),
    25: ("dungeon", 4), 26: ("dungeon", 0), 27: ("dungeon", 3), 28: ("mine", 2),
    29: ("dungeon", 1), 30: ("dungeon", 4),
}

PURPOSES = ("vault", "throne", "temple", "fountain", "treasury", "barracks")


class Room:
    __slots__ = ("x1", "y1", "x2", "y2", "kind", "lit", "purpose")

    def __init__(self, x1, y1, x2, y2, kind=0, purpose=None):
        self.x1, self.y1, self.x2, self.y2 = x1, y1, x2, y2
        self.kind = kind
        self.lit = False
        self.purpose = purpose

    @property
    def cx(self):
        return (self.x1 + self.x2) // 2

    @property
    def cy(self):
        return (self.y1 + self.y2) // 2

    @property
    def w(self):
        return self.x2 - self.x1 + 1

    @property
    def h(self):
        return self.y2 - self.y1 + 1

    @property
    def area(self):
        return self.w * self.h

    def inner(self):
        return (self.x1 + 1, self.y1 + 1, self.x2 - 1, self.y2 - 1)

    def center(self):
        return (self.cx, self.cy)

    def perimeter(self):
        """Клетки кольца сразу за стенами комнаты."""
        pts = []
        for x in range(self.x1 - 1, self.x2 + 2):
            pts.append((x, self.y1 - 1))
            pts.append((x, self.y2 + 1))
        for y in range(self.y1, self.y2 + 1):
            pts.append((self.x1 - 1, y))
            pts.append((self.x2 + 1, y))
        return pts

    def to_dict(self):
        return {"x1": self.x1, "y1": self.y1, "x2": self.x2, "y2": self.y2,
                "kind": self.kind, "lit": self.lit, "purpose": self.purpose}

    @staticmethod
    def from_dict(d):
        room = Room(d["x1"], d["y1"], d["x2"], d["y2"], d.get("kind", 0), d.get("purpose"))
        room.lit = bool(d.get("lit", False))
        return room


# --------------------------------------------------------------------------
# Утилиты
# --------------------------------------------------------------------------
def _dist(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _overlaps(rooms, x1, y1, x2, y2, pad=1):
    for r in rooms:
        if not (x2 + pad < r.x1 or x1 - pad > r.x2
                or y2 + pad < r.y1 or y1 - pad > r.y2):
            return True
    return False


def _h_corr(x1, x2, y, put):
    step = 1 if x2 > x1 else -1
    for x in range(x1, x2 + step, step):
        put(x, y, FLOOR)


def _v_corr(y1, y2, x, put):
    step = 1 if y2 > y1 else -1
    for y in range(y1, y2 + step, step):
        put(x, y, FLOOR)


def _carve_corridor(a, b, put, rng):
    x, y = a.cx, a.cy
    bx, by = b.cx, b.cy
    if rng.random() < 0.5:
        _h_corr(x, bx, y, put)
        _v_corr(y, by, bx, put)
    else:
        _v_corr(y, by, x, put)
        _h_corr(x, bx, by, put)


def _connect(rooms, put, rng, loops=0.4):
    """Остовное дерево по ближайшей комнате + лишние петли."""
    if len(rooms) < 2:
        return
    connected = [rooms[0]]
    remaining = rooms[1:]
    while remaining:
        best = None
        best_d = 1 << 30
        for a in connected:
            for b in remaining:
                d = abs(a.cx - b.cx) + abs(a.cy - b.cy)
                if d < best_d:
                    best_d = d
                    best = (a, b)
        if best is None:
            break
        a, b = best
        _carve_corridor(a, b, put, rng)
        remaining.remove(b)
        connected.append(b)

    extra = max(1, int(len(rooms) * loops))
    for _ in range(extra):
        a, b = rng.sample(rooms, 2)
        _carve_corridor(a, b, put, rng)


def _flood(w, h, get, sx, sy):
    """Все проходимые клетки, достижимые из (sx,sy)."""
    seen = {(sx, sy)}
    q = deque([(sx, sy)])
    while q:
        x, y = q.popleft()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if not (0 <= nx < w and 0 <= ny < h) or (nx, ny) in seen:
                continue
            if get(nx, ny) == WALL:
                continue
            seen.add((nx, ny))
            q.append((nx, ny))
    return seen


def _carve_to_region(sx, sy, region, put, get, rng):
    """Проложить коридор из (sx,sy) к ближайшей клетке области."""
    best = None
    best_d = 1 << 30
    for (x, y) in region:
        d = abs(x - sx) + abs(y - sy)
        if d < best_d:
            best_d = d
            best = (x, y)
    if best is None:
        return
    bx, by = best
    if rng.random() < 0.5:
        _h_corr(sx, bx, sy, put)
        _v_corr(sy, by, bx, put)
    else:
        _v_corr(sy, by, sx, put)
        _h_corr(sx, bx, by, put)


def _ensure_doors(rooms, put, get, rng, max_doors=2):
    """Каждая комната получает дверь, если её ещё нет."""
    for r in rooms:
        cands = [p for p in r.perimeter() if get(*p) == FLOOR]
        if not cands:
            continue
        rng.shuffle(cands)
        for pos in cands[:max_doors]:
            put(*pos, DOOR)


def _decorate_rooms(rooms, put, rng, depth):
    """Колонны и мелкий декор внутри обычных комнат."""
    for r in rooms:
        if r.purpose:
            continue
        x1, y1, x2, y2 = r.inner()
        if x2 < x1 or y2 < y1:
            continue
        roll = rng.random()
        if roll < 0.22 and (x2 - x1) >= 6 and (y2 - y1) >= 4:
            # колоннами - не блокируем центр
            for _ in range(rng.randint(1, 3)):
                px = rng.randint(x1 + 1, max(x1 + 1, x2 - 1))
                py = rng.randint(y1 + 1, max(y1 + 1, y2 - 1))
                if (px, py) in ((r.cx, r.cy), (r.cx - 1, r.cy), (r.cx, r.cy - 1)):
                    continue
                put(px, py, WALL)
        elif roll < 0.34 and r.area >= 16:
            px, py = rng.randint(x1, x2), rng.randint(y1, y2)
            put(px, py, RUBBLE)


def _assign_purposes(rooms, rng):
    """Распределяет особые залы: дальше от входа - ценнее."""
    if len(rooms) < 2:
        return
    start = rooms[0]
    rest = list(rooms[1:])
    rng.shuffle(rest)
    by_dist = sorted(rest, key=lambda r: -_dist(r.center(), start.center()))
    if by_dist:
        by_dist[0].purpose = "vault"
    if len(by_dist) > 1:
        by_dist[1].purpose = "throne"
    pool = [r for r in by_dist[2:] if r.purpose is None]
    big = [r for r in pool if r.area >= 20]
    if big:
        rng.choice(big).purpose = "temple"
    pool = [r for r in by_dist[2:] if r.purpose is None]
    wide = [r for r in pool if r.area >= 16]
    if wide:
        rng.choice(wide).purpose = "fountain"
    pool = [r for r in by_dist if r.purpose is None]
    if pool:
        max(pool, key=lambda r: r.area).purpose = "treasury"
    pool = [r for r in by_dist if r.purpose is None]
    rng.shuffle(pool)
    for r in pool[:2]:
        r.purpose = "barracks"


# --------------------------------------------------------------------------
# Комнаты и коридоры
# --------------------------------------------------------------------------
def _place_rooms(w, h, rng, target=18, pad=2):
    rooms = []
    tries = 0
    while len(rooms) < target and tries < 900:
        tries += 1
        rw = rng.randint(5, 12)
        rh = rng.randint(4, 8)
        x1 = rng.randint(2, max(2, w - rw - 3))
        y1 = rng.randint(2, max(2, h - rh - 3))
        x2, y2 = x1 + rw, y1 + rh
        if _overlaps(rooms, x1, y1, x2, y2, pad):
            continue
        rooms.append(Room(x1, y1, x2, y2, rng.choice([0, 0, 0, 1, 2, 3])))
    if not rooms:
        cx, cy = w // 2, h // 2
        rooms.append(Room(cx - 4, cy - 3, cx + 4, cy + 3))
    return rooms


def _carve_rooms(rooms, put):
    for r in rooms:
        for y in range(r.y1, r.y2 + 1):
            for x in range(r.x1, r.x2 + 1):
                put(x, y, FLOOR)


# --------------------------------------------------------------------------
# Пещеры
# --------------------------------------------------------------------------
def _carve_caves(w, h, rng, put, get):
    """Клеточный автомат + оставляем только самую большую область."""
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            put(x, y, WALL if rng.random() < 0.46 else FLOOR)

    for _ in range(4):
        nxt = {}
        for y in range(1, h - 1):
            for x in range(1, w - 1):
                walls = 0
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        if dx == 0 and dy == 0:
                            continue
                        if get(x + dx, y + dy) == WALL:
                            walls += 1
                nxt[(x, y)] = WALL if walls >= 5 else FLOOR
        for y in range(1, h - 1):
            for x in range(1, w - 1):
                put(x, y, nxt[(x, y)])

    seen = set()
    best = set()
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            if get(x, y) != FLOOR or (x, y) in seen:
                continue
            region = _flood(w, h, get, x, y)
            seen |= region
            if len(region) > len(best):
                best = region
    for y in range(h):
        for x in range(w):
            if (x, y) not in best:
                put(x, y, WALL)
    return best


def _rooms_in_caves(w, h, rng, open_set, count=13, put=None, get=None):
    """Вырезаем залы внутри пещеры и связываем их с пещерой."""
    rooms = []
    cells = sorted(open_set)
    tries = 0
    while len(rooms) < count and tries < 700 and cells:
        tries += 1
        cx, cy = rng.choice(cells)
        rw = rng.randint(5, 10)
        rh = rng.randint(4, 7)
        x1, y1 = cx - rw // 2, cy - rh // 2
        x2, y2 = x1 + rw, y1 + rh
        if x1 < 1 or y1 < 1 or x2 >= w - 1 or y2 >= h - 1:
            continue
        if _overlaps(rooms, x1, y1, x2, y2, 1):
            continue
        rooms.append(Room(x1, y1, x2, y2, rng.choice([2, 3])))
    for r in rooms:
        _carve_rooms([r], put)
    # изолированные залы соединяем с пещерой
    for r in rooms:
        if r.center() not in open_set:
            _carve_to_region(r.cx, r.cy, open_set, put, get, rng)
    return rooms


# --------------------------------------------------------------------------
# Точка входа
# --------------------------------------------------------------------------
def generate_level(w, h, depth: int, rng: random) -> dict:
    if depth == 0:
        return generate_lobby(w, h, rng)
    kind_name, style = LEVEL_TYPES.get(depth, ("dungeon", depth % 5))
    tiles = [WALL] * (w * h)

    def put(x, y, v):
        if 0 <= x < w and 0 <= y < h:
            tiles[y * w + x] = v

    def get(x, y):
        if 0 <= x < w and 0 <= y < h:
            return tiles[y * w + x]
        return WALL

    if kind_name == "mine":
        open_set = _carve_caves(w, h, rng, put, get)
        rooms = _rooms_in_caves(w, h, rng, open_set, max(6, 13 - depth // 4),
                                put, get)
        _ensure_doors(rooms, put, get, rng, max_doors=2)
    else:
        rooms = _place_rooms(w, h, rng,
                             target=22 if kind_name == "orc" else 18, pad=2)
        _carve_rooms(rooms, put)
        _connect(rooms, put, rng, loops=0.5 if kind_name == "orc" else 0.35)
        _ensure_doors(rooms, put, get, rng, max_doors=3)
        _connect_stragglers(rooms, w, h, put, get, rng)
        _ensure_doors(rooms, put, get, rng, max_doors=2)
        _decorate_rooms(rooms, put, rng, depth)

    _assign_purposes(rooms, rng)
    rooms.sort(key=lambda r: (r.x1, r.y1))

    return {"tiles": tiles, "rooms": rooms, "kind": kind_name, "style": style,
            "doors": {}, "w": w, "h": h, "depth": depth}


def generate_lobby(w, h, rng):
    """Repeated yellow rooms, irregular partitions and guaranteed chunk seams.

    Rooms tile the plane in modules. Each module has a cross passage, so all
    openings meet the adjacent module/chunk and no player is sealed off.
    No stairs, traps, exits or special dungeon rooms are generated.
    """
    tiles = [FLOOR] * (w*h)
    rooms = []
    for y0 in range(0, h, 10):
        for x0 in range(0, w, 10):
            x1, y1 = min(w-1, x0+9), min(h-1, y0+9)
            room = Room(x0+1, y0+1, x1-1, y1-1)
            room.lit = True
            rooms.append(room)
            vertical = rng.choice((True, False))
            split = rng.randint(3, 7)
            gap = rng.randint(2, 7)
            for y in range(y0, y1+1):
                for x in range(x0, x1+1):
                    lx, ly = x-x0, y-y0
                    wall = lx == 0 or ly == 0
                    if vertical and lx == split and ly not in (gap, gap+1):
                        wall = True
                    if not vertical and ly == split and lx not in (gap, gap+1):
                        wall = True
                    # Wide common passages connect neighbouring chunks.
                    if lx in (4, 5) or ly in (4, 5):
                        wall = False
                    tiles[y*w+x] = WALL if wall else FLOOR
    # Chunk seams are real corridors, not solid generated borders. This keeps
    # neighbouring 80x50 chunks traversable in both directions.
    for y in (h // 2 - 1, h // 2):
        if 0 <= y < h:
            tiles[y * w] = FLOOR
            tiles[y * w + (w - 1)] = FLOOR
    for x in (w // 2 - 1, w // 2):
        if 0 <= x < w:
            tiles[x] = FLOOR
            tiles[(h - 1) * w + x] = FLOOR
    # Backrooms lamps: one fluorescent panel per room, offset from the wall
    # so the light BFS can spread in all four directions.  The lobby is
    # famous for these; without them the level is pitch black in first
    # person even though every room is marked lit=True.
    lamps = set()
    for room in rooms:
        cx, cy = room.center()
        if 0 < cx < w-1 and 0 < cy < h-1:
            lamps.add((cx, cy))
    return {"tiles": tiles, "rooms": rooms, "kind": "lobby", "style": 0,
            "lamps": lamps}


def _connect_stragglers(rooms, w, h, put, get, rng):
    """Если комната не достижима от стартовой - дотапливаем коридор."""
    if len(rooms) < 2:
        return
    start = rooms[0]
    seen = _flood(w, h, get, start.cx, start.cy)
    for r in rooms[1:]:
        if r.center() in seen:
            continue
        _carve_to_region(r.cx, r.cy, seen, put, get, rng)
        seen |= _flood(w, h, get, r.cx, r.cy)
