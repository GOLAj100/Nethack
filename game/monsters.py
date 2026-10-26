"""Реестр сущностей Backrooms и общий механизм появления.

Определение: характеристики Actor, behavior, b_levels (список B-level),
z_range (границы Z, None без ограничения), w (вес появления).
depths можно задать для старого генератора подземелий.
"""
from __future__ import annotations

import random
from .entities import Actor

MONSTERS: dict[str, dict] = {
    "the thing": dict(glyph="T", color=(180, 220, 230), hp=24, ac=2,
                       dmg=(2, 7), hit=3, speed=80, b_levels=[7],
                       behavior="aquatic_chase", terrain="water", w=1,
                       awake_chance=0.65, tier=3),
    "mortisdoptera swarm": dict(glyph="m", color=(210, 190, 92), hp=8, ac=1,
                       dmg=(1, 4), hit=2, speed=120, b_levels=[8],
                       behavior="swarm", w=3, awake_chance=0.75, tier=1),
    "the observer": dict(glyph="O", color=(190, 190, 210), hp=12, ac=4,
                       dmg=(1, 2), hit=1, speed=70, b_levels=[9],
                       behavior="observer", hostile=False, w=2,
                       awake_chance=1.0, tier=2),
    "burrowing worm": dict(glyph="w", color=(154, 116, 66), hp=16, ac=3,
                       dmg=(2, 5), hit=2, speed=90, b_levels=[10],
                       behavior="burrower", terrain="field", w=2,
                       awake_chance=0.45, tier=2),
}
SLEEP_WARNINGS = {'hound':'m.sleep_wake_legs', 'skin-stealer':'m.sleep_wake_slap',
                  'skin stealer':'m.sleep_wake_slap', 'unknown':'m.sleep_wake_unknown'}
MONSTER_LETTERS = []

# Только миграция сохранений, без характеристик и возможности появления.
RETIRED_NAMES = frozenset((
    "giant rat", "jackal", "kobold", "goblin", "newt", "snake", "bat",
    "kobold lord", "goblin shaman", "orc", "huge rat", "orc warrior",
    "troll", "ogre", "ogre lord", "wraith", "skeleton", "gnome lord",
    "winter wolf cub", "fire giant", "green dragon",
))


def monster_pool(depth: int, b_level=None, world_z=0) -> list[tuple[str, int]]:
    pool = []
    for name, d in MONSTERS.items():
        lo, hi = d.get("depths", (0, float("inf")))
        if not lo <= depth <= hi:
            continue
        if b_level is not None and d.get("b_levels") is not None:
            if b_level not in d["b_levels"]:
                continue
        zlo, zhi = d.get("z_range", (None, None))
        if (zlo is not None and world_z < zlo) or (zhi is not None and world_z > zhi):
            continue
        weight = d.get("w", 1)
        if weight > 0:
            pool.append((name, weight))
    return pool


def spawn_monster(name: str | None, x: int, y: int, depth: int, rng=random,
                  *, b_level=None, world_z=0) -> Actor | None:
    if name is None:
        return None
    d = MONSTERS[name]
    hp = rng.randint(max(1, d["hp"] - 2), d["hp"] + 3)
    m = Actor(x=x, y=y, name=name, glyph=d["glyph"], color=d["color"],
              hp=hp, max_hp=hp, ac=d["ac"], dmg=d["dmg"], to_hit=d["hit"],
              speed=d["speed"], depth=depth, tier=d.get("tier", 1))
    m.b_level = depth if b_level is None else b_level
    m.world_z = world_z
    m.behavior = d.get("behavior", "chase")
    m.hostile = d.get("hostile", True)
    m.awake = rng.random() < d.get("awake_chance", 0.35)
    return m


def random_monster(depth: int, rng=random, *, b_level=None, world_z=0) -> str | None:
    pool = monster_pool(depth, b_level, world_z)
    if not pool:
        return None
    r = rng.uniform(0, sum(w for _, w in pool))
    acc = 0.0
    for name, weight in pool:
        acc += weight
        if r <= acc:
            return name
    return pool[-1][0]


def spawn_random(level, x, y, rng=random, depth=None):
    # Legacy dungeon Levels created directly by unit tests do not represent a
    # Backrooms profile. Keep their old empty-roster behaviour; streamed worlds
    # attach the profile before spawning lore entities.
    if level.b_level in (7, 8, 9, 10) and not getattr(level, "profile", None):
        return None
    depth = level.depth if depth is None else depth
    name = random_monster(depth, rng, b_level=level.b_level, world_z=level.world_z)
    if name is not None:
        spec = MONSTERS[name]
        terrain = spec.get("terrain")
        if terrain == "water" and level.at(x, y) != 10:  # mapgen.WATER
            candidates = [(xx, yy) for yy in range(level.h) for xx in range(level.w)
                          if level.at(xx, yy) == 10 and level.monster_at(xx, yy) is None]
            if not candidates:
                return None
            x, y = rng.choice(candidates)
        elif terrain == "field" and level.at(x, y) not in (0, 14):
            candidates = [(xx, yy) for yy in range(level.h) for xx in range(level.w)
                          if level.at(xx, yy) in (0, 14) and level.monster_at(xx, yy) is None]
            if not candidates:
                return None
            x, y = rng.choice(candidates)
    return spawn_monster(name, x, y, depth, rng,
                         b_level=level.b_level, world_z=level.world_z)
