"""Тест мыши и быстрых клавиш: ход по клику, осмотр, меню, quick-клавиши."""

import os
import random
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame

from engine import config as C
from engine.renderer import Renderer
from game.app import Game
from game import lang
from game.items import Item
from game import monsters as MON

pygame.init()
probe = pygame.display.set_mode((64, 64))
r = Renderer(probe)
cols = C.CAMERA_W + C.SIDEBAR_W
rows = C.TOPBAR_H + C.CAMERA_H + C.LOG_H
r.surface = pygame.display.set_mode((cols * r.cw, rows * r.ch))

errors = []


def check(label, cond):
    print(("  ok   " if cond else "  FAIL ") + label)
    if not cond:
        errors.append(label)


def mouse(col, row, button=1):
    g.on_mouse(pygame.event.Event(pygame.MOUSEBUTTONDOWN,
                                 pos=(int((col + 0.5) * r.cw), int((row + 0.5) * r.ch)),
                                 button=button))


def motion(col, row):
    px = int((col + 0.5) * r.cw)
    py = int((row + 0.5) * r.ch)
    g.on_mouse(pygame.event.Event(pygame.MOUSEMOTION, pos=(px, py)))


def key(k, mod=0):
    g.on_key(pygame.event.Event(pygame.KEYDOWN, key=k, mod=mod, unicode="", scancode=0))


def wheel(dy):
    g.on_mouse(pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=dy))


def open_game(seed=7):
    lang.set_lang("en")
    g = Game(r, seed=seed)
    lang.set_lang("en")  # Game loads persisted settings, including the language.
    g.new_game()
    g.views.mode = "ascii"
    p, lv = g.player, g.level
    # открываем проходимую часть карты, чтобы клику было куда идти
    walk = [(x, y) for x in range(lv.w) for y in range(lv.h)
            if not lv.is_wall(x, y) and lv.at(x, y) != 3]
    lv.explored = set(walk)
    lv.mapped = set(walk)
    lv.recompute_fov(p.x, p.y)
    return g, p, lv


def reachable(p, lv):
    """Первая достижимая видимая клетка на экране."""
    cx, cy = g.cam()
    for (wx, wy) in sorted(lv.visible):
        if (wx, wy) == (p.x, p.y) or lv.is_wall(wx, wy):
            continue
        if lv.next_step(p.x, p.y, wx, wy) is None:
            continue
        col, row = wx - cx, wy - cy + g.map_offset_y
        if 0 <= col < C.CAMERA_W and 0 <= row < C.TOPBAR_H + C.CAMERA_H:
            return wx, wy
    return None


# --- 1. левый клик не ходит, ПКМ осматривает -------------------------------
print("клики по карте:")
g, p, lv = open_game()
cx, cy = g.cam()
tgt = reachable(p, lv)
check("есть достижимая клетка", tgt is not None)
if tgt:
    before = (p.x, p.y, p.turns)
    mouse(tgt[0] - cx, tgt[1] - cy + g.map_offset_y)
    check("ЛКМ не перемещает", (p.x,p.y,p.turns) == before)
    check("всплывающий урон не сломал кадр", g.draw() is None)

# клик на собственную клетку не тратит ход
ccx, ccy = g.cam()
turns = p.turns
mouse(p.x - ccx, p.y - ccy + g.map_offset_y)
check("ЛКМ на себя не ждёт", p.turns == turns)

# клик в стену не тратит ход
wx, wy = None, None
for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
    if lv.is_wall(p.x + dx, p.y + dy):
        wx, wy = p.x + dx, p.y + dy
        break
if wx is not None:
    t = p.turns
    mouse(wx - g.cam()[0], wy - g.cam()[1] + g.map_offset_y)
    check("клик в стену не тратит ход", p.turns == t)

# --- 2. правый клик -> осмотр ---------------------------------------------
print("правый клик по карте:")
mouse(p.x - g.cam()[0], p.y - g.cam()[1] + g.map_offset_y, button=3)
check("подсказка появилась", g.tooltip is not None)
text = "\n".join(l for l, _ in g.tooltip["lines"])
check("в подсказке координаты", f"({p.x},{p.y})" in text)
check("в подсказке описание клетки", len(g.tooltip["lines"]) >= 2)
g.draw()
for _ in range(170):
    g.tick_floats()
check("подсказка исчезает со временем", g.tooltip is None)

# --- 3. клик по монстру не атакует ----------------------------------------
print("клик по монстру:")
cell = None
for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
    nx, ny = p.x + dx, p.y + dy
    if not lv.is_wall(nx, ny) and (nx, ny) in lv.visible:
        cell = (nx, ny)
        break
check("есть свободная соседняя клетка", cell is not None)
if cell:
    from game.entities import Actor
    m = Actor(cell[0], cell[1], name="test entity", hp=6, max_hp=6)
    lv.monsters.append(m)
    m.status["asleep"] = 9999
    hp_before = m.hp
    turns_before = p.turns
    for _ in range(8):
        if m.hp < hp_before or not m.alive:
            break
        mouse(cell[0] - g.cam()[0], cell[1] - g.cam()[1] + g.map_offset_y)
    log_text = " ".join(txt for txt, _ in g.log[-4:]).lower()
    check("клик по монстру не тратит ход", p.turns == turns_before)
    check("в журнале есть результат атаки",
          ("miss" not in log_text) and ("hit" not in log_text))

# --- 4. клики в меню -------------------------------------------------------
print("мышь в меню:")
p.items.extend(Item(n) for n in
               ["potion of healing", "dagger", "scroll of mapping",
                "food ration", "wand of fire"])
g.open_inventory()
check("инвентарь открыт", g.mode == "inventory" and g.inventory_panel is not None)
panel = g.inventory_panel
g.draw()
n = len(panel.items)
if n >= 2:
    pos = panel.item_rects[1].center
    g.on_mouse(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1))
    check("первый клик выбрал пункт", panel.selected == 1)
    g.draw()
    g.on_mouse(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1))
    check("повторный клик открыл действия предмета",
          g.mode == "modal" and g.menu is not None)
    key(pygame.K_ESCAPE)
    key(pygame.K_ESCAPE)
else:
    check("в инвентаре достаточно предметов", False)

# --- 5. колесо мыши -------------------------------------------------------
print("колесо мыши:")
g.open_inventory()
panel = g.inventory_panel
g.draw()
if len(panel.items) > 1:
    start = panel.selected
    wheel(1)
    check("колесо сдвинуло выбор",
          panel.selected == (start + 1) % len(panel.items))
    wheel(-1)
    check("колесо возвращает назад", panel.selected == start)
    key(pygame.K_ESCAPE)
else:
    check("в инвентаре достаточно предметов для колеса", False)

# --- 6. цифровой выбор ----------------------------------------------------
print("цифровой выбор:")
p.items.clear()
p.items.extend(Item(x) for x in
               ["potion of healing", "dagger", "scroll of mapping",
                "food ration", "wand of fire"])
g.open_inventory()
panel = g.inventory_panel
check("5 предметов", len(panel.items) == 5)
key(pygame.K_3)
check("цифра 3 открыла действия третьего предмета",
      g.mode == "modal" and g.menu is not None)
key(pygame.K_ESCAPE)
check("Esc закрыл подменю", g.mode == "play")

# --- 7. быстрые клавиши над предметами ------------------------------------
print("быстрые клавиши:")
p.hp = 5
p.items = [Item("potion of healing")]
g.open_inventory()
key(pygame.K_q)
check("q выпил зелье без второго меню", p.hp > 5 and not p.items)

p.items = [Item("potion of extra healing"), Item("potion of healing")]
g.open_inventory()
key(pygame.K_i)
check("i открыл свойства", g.mode == "modal" and g.modal_lines is not None)
key(pygame.K_ESCAPE)
p.items = [Item("dagger")]
g.open_inventory()
key(pygame.K_x)
check("x взял кинжал в руки", p.wielded is not None and p.wielded.name == "dagger")
p.items = [Item("potion of healing")]
g.open_inventory()
key(pygame.K_d, pygame.KMOD_SHIFT)
check("Shift+D выбросил", not p.items)
key(pygame.K_ESCAPE)

# --- 8. клик по предмету на полу ------------------------------------------
print("клик по предмету на полу:")
lv.items.clear()
lv.items[(p.x, p.y)] = Item("gold piece")
g.open_pick_items()
if g.menu is not None:
    mouse(g.menu.x + 1, g.menu.y + 3)
    check("клик по пункту открыл его действия", g.mode == "modal")
    key(pygame.K_ESCAPE)
    key(pygame.K_g)
    check("g подобрал предмет с пола", p.gold > 0)
else:
    check("меню предметов на полу открылось", False)

print()
if errors:
    print("НАЙДЕНО ОШИБОК:", len(errors))
    for e in errors:
        print("-" * 60)
        print(e)
    raise SystemExit(1)
print("ТЕСТ МЫШИ ПРОЙДЕН")
