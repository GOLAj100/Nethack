"""Тест генерации уровней: связность, двери, особые залы, лестницы."""

import os
import random
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import config as C
from game import mapgen as MG
from game.level import Level, populate

errors = []


def check(label, cond):
    print(("  ok   " if cond else "  FAIL ") + label)
    if not cond:
        errors.append(label)


def analyze(depth: int, seed: int):
    rng = random.Random(seed)
    data = MG.generate_level(C.MAP_W, C.MAP_H, depth, rng)
    lv = Level(depth, C.MAP_W, C.MAP_H, rng)
    lv.tiles = data["tiles"]
    lv.rooms = data["rooms"]
    lv.kind = data["kind"]
    lv.style = data["style"]
    populate(lv, rng)

    # двери
    for y in range(lv.h):
        for x in range(lv.w):
            if lv.at(x, y) == MG.DOOR:
                lv.doors[(x, y)] = {"open": False, "locked": False, "broken": False}

    rooms = [r for r in lv.rooms if r.area >= 6]

    # связность: все комнаты достижимы из первой
    if not rooms:
        return {"rooms": 0, "reachable": 0, "doors": 0, "purposes": {}}
    start = rooms[0]
    seen = MG._flood(C.MAP_W, C.MAP_H, lv.at, start.cx, start.cy)
    unreachable = [r for r in rooms if r.center() not in seen]

    # двери у каждой комнаты
    no_door = [r for r in rooms if not lv.door_tiles(r)]

    # лестница
    stairs_ok = lv.at(*lv.stairs_down) == MG.STAIR_DOWN

    purposes = {}
    for r in rooms:
        purposes[r.purpose] = purposes.get(r.purpose, 0) + 1

    return {"rooms": len(rooms), "reachable": len(rooms) - len(unreachable),
            "unreachable": len(unreachable), "no_door": len(no_door),
            "stairs_ok": stairs_ok, "kind": lv.kind,
            "purposes": purposes,
            "items": len(lv.items), "monsters": len(lv.monsters)}


print("анализ 30 уровней (по 2 сида на глубину):")
total_rooms = total_reach = total_nodoor = 0
stairs_bad = 0
purpose_count = {}
worst = None
for depth in range(1, 31):
    for seed in (1, 2):
        st = analyze(depth, seed * 1000 + depth)
        total_rooms += st["rooms"]
        total_reach += st["reachable"]
        total_nodoor += st["no_door"]
        if not st["stairs_ok"]:
            stairs_bad += 1
        for k, v in st["purposes"].items():
            purpose_count[k] = purpose_count.get(k, 0) + v
        if st["rooms"] and st["reachable"] < st["rooms"]:
            worst = (depth, seed, st["unreachable"])

print(f"  комнат всего: {total_rooms}, достижимо: {total_reach}")
print(f"  комнат без двери: {total_nodoor}")
print(f"  лестница не на месте: {stairs_bad}")
print(f"  особые залы: {purpose_count}")
print()

check("все комнаты достижимы", total_reach == total_rooms)
check("нет комнат без двери", total_nodoor == 0)
check("лестница всегда на месте", stairs_bad == 0)
check("есть хранилища", purpose_count.get("vault", 0) >= 25)
check("есть храмы", purpose_count.get("temple", 0) >= 15)
check("есть тронные залы", purpose_count.get("throne", 0) >= 20)
check("есть сокровищницы", purpose_count.get("treasury", 0) >= 15)
check("есть казармы", purpose_count.get("barracks", 0) >= 30)
check("есть фонтанные залы", purpose_count.get("fountain", 0) >= 15)

# пещеры тоже связаны
print("пещеры:")
cave_bad = 0
cave_rooms = 0
for depth in (6, 7, 11, 15, 18, 21, 24, 28):
    for seed in (3, 4):
        rng = random.Random(seed * 777 + depth)
        data = MG.generate_level(C.MAP_W, C.MAP_H, depth, rng)
        lv = Level(depth, C.MAP_W, C.MAP_H, rng)
        lv.tiles = data["tiles"]
        lv.rooms = data["rooms"]
        populate(lv, rng)
        for y in range(lv.h):
            for x in range(lv.w):
                if lv.at(x, y) == MG.DOOR:
                    lv.doors[(x, y)] = {"open": False, "locked": False,
                                        "broken": False}
        rooms = [r for r in lv.rooms if r.area >= 6]
        cave_rooms += len(rooms)
        if rooms:
            seen = MG._flood(C.MAP_W, C.MAP_H, lv.at, rooms[0].cx, rooms[0].cy)
            if any(r.center() not in seen for r in rooms):
                cave_bad += 1
check("залы в пещерах достижимы", cave_bad == 0)
print(f"  залов в пещерах проверено: {cave_rooms}")

print()
if errors:
    print("НАЙДЕНО ОШИБОК:", len(errors))
    for e in errors:
        print("-" * 60)
        print(e)
    raise SystemExit(1)
print("ТЕСТ ГЕНЕРАЦИИ ПРОЙДЕН")
