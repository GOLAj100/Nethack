"""Тест всех действий с предметами - ищет падения в редких ветках.

Особенно важно: пункты меню доступны и для предметов, лежащих на полу
(клавиша p), а не только для инвентаря.
"""

import os
import sys
import traceback

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame

from engine import config as C
from engine.renderer import Renderer
from game.app import Game
from game.items import ITEMS, Item

pygame.init()
probe = pygame.display.set_mode((64, 64))
r = Renderer(probe)
cols = C.CAMERA_W + C.SIDEBAR_W
rows = C.TOPBAR_H + C.CAMERA_H + C.LOG_H
r.surface = pygame.display.set_mode((cols * r.cw, rows * r.ch))
g = Game(r)
g.new_game()
p = g.player
g.views.mode = "ascii"

errors = []


def attempt(label, fn, *a, **kw):
    try:
        fn(*a, **kw)
        g.draw()
    except Exception:
        errors.append((label, traceback.format_exc()))


ALL_NAMES = list(ITEMS.keys())
ACTIONS = ["Info", "Drop it", "Eat it", "Quaff it", "Read it", "Wear it",
           "Wield it", "Take off", "Fire it", "Zap it", "Throw it"]

print(f"предметов в реестре: {len(ALL_NAMES)}, действий: {len(ACTIONS)}")

# --- 1. все действия над предметом в инвентаре ---------------------------
for name in ALL_NAMES:
    p.items.clear()
    it = Item(name)
    p.items.append(it)
    if p.items[0] is not it:
        continue
    for act in ACTIONS:
        attempt(f"carried {name} / {act}", g.show_item_actions, it)
        # закрыть всё, что открылось
        for _ in range(8):
            if g.mode == "modal":
                g.close_modal()
            elif g.mode == "target":
                g.targeting = None
                g.mode = "play"
            else:
                break
        g.mode = "play"
        p.hp = p.max_hp

# --- 2. те же действия, но предмет лежит НА ПОЛУ --------------------------
print("проверка предметов на полу...")
lv = g.level
for name in ALL_NAMES:
    lv.items.clear()
    lv.items[(p.x, p.y)] = Item(name)
    for act in ACTIONS:
        attempt(f"onfloor {name} / {act}", g.show_item_actions, lv.items[(p.x, p.y)])
        for _ in range(8):
            if g.mode == "modal":
                g.close_modal()
            elif g.mode == "target":
                g.targeting = None
                g.mode = "play"
            else:
                break
        g.mode = "play"
        p.hp = p.max_hp

# --- 3. прямые вызовы операций с чужими предметами ------------------------
print("проверка прямых вызовов...")
for name in ALL_NAMES:
    stranger = Item(name)
    for fn in (g.do_drop, g.do_eat, g.do_quaff, g.do_read,
               g.do_wield, g.do_wear, g.do_takeoff):
        attempt(f"direct {fn.__name__}({name})", fn, stranger)
        g.mode = "play"
        p.hp = p.max_hp

# --- 4. прочие ветки ------------------------------------------------------
from game import mapgen as MG

lv.items[(p.x, p.y)] = Item("gold piece")
lv.items[(p.x + 1, p.y)] = Item("potion of healing")
attempt("pickup_all", g.pickup_all)
attempt("pick_lock (нет замков)", g.pick_lock)
lv.doors[(p.x, p.y)] = {"open": False, "locked": True, "broken": False}
lv.set(p.x, p.y, MG.DOOR)
attempt("pick_lock (есть замок)", g.pick_lock)
if g.menu:
    g.menu.index = 0
    g.key_modal(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, mod=0))
attempt("toggle_lights x2", g.toggle_lights)
attempt("toggle_lights x2", g.toggle_lights)
attempt("toggle_map", g.toggle_map)
attempt("toggle_map", g.toggle_map)
attempt("ascend (нет лестницы)", g.ascend)
attempt("descend (нет лестницы)", g.descend)
attempt("char sheet", g.show_char)
attempt("help", g.show_help)
attempt("force_attack (пусто)", g.force_attack)
attempt("inventory (пусто)", g.open_inventory)
attempt("items here (пусто)", g.open_pick_items)
attempt("drop (пусто)", g.open_drop)
attempt("eat (пусто)", g.open_eat)
attempt("quaff (пусто)", g.open_quaff)
attempt("read (пусто)", g.open_read)
attempt("wield (пусто)", g.open_wield)
attempt("wear (пусто)", g.open_wear)
attempt("takeoff (пусто)", g.open_takeoff)
attempt("fire (нет лука)", g.open_fire)
attempt("zap (нет палочек)", g.open_zap)
attempt("throw (пусто)", g.open_throw)
g.mode = "play"

# --- 5. эффекты всех предметов -------------------------------------------
print("проверка эффектов всех предметов...")
from game import effects

for name in ALL_NAMES:
    it = Item(name)
    if it.kind not in ("potion", "scroll", "wand"):
        continue
    attempt(f"effect {name}", effects.apply, p, g.level, it, (p.x, p.y))
    p.hp = p.max_hp

# --- 6. предметы без эффекта, опознавание -------------------------------
attempt("identify", g.identify, 0)
attempt("save", g.save_quiet)

print()
if errors:
    print(f"НАЙДЕНО ОШИБОК: {len(errors)} (уникальных мест: "
          f"{len({e[1].strip().splitlines()[-1] for e in errors})})")
    seen = set()
    for label, tb in errors:
        key = tb.strip().splitlines()[-1][:100]
        if key in seen:
            continue
        seen.add(key)
        print("=" * 70)
        print(label)
        print(tb)
    raise SystemExit(1)
print("ТЕСТ ПРЕДМЕТОВ ПРОЙДЕН")
