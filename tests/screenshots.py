"""Рендерит несколько экранов игры в PNG для визуальной проверки."""

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame

from engine import config as C
from engine.renderer import Renderer
from game.app import Game

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shots")
os.makedirs(OUT, exist_ok=True)

pygame.init()
cols = C.CAMERA_W + C.SIDEBAR_W
rows = C.TOPBAR_H + C.CAMERA_H + C.LOG_H
probe = pygame.display.set_mode((64, 64))
r = Renderer(probe)
screen = pygame.display.set_mode((cols * r.cw, rows * r.ch))
r.surface = screen
g = Game(r)


def shot(name):
    g.draw()
    pygame.image.save(screen, os.path.join(OUT, name))
    print("saved", name, screen.get_size())


shot("01_title.png")

g.new_game()
shot("02_start.png")

# подойти к паре предметов и монстров, чтобы было видно содержимое
import random
rng = random.Random(7)
p, lv = g.player, g.level
for _ in range(400):
    dx, dy = rng.choice([(1, 0), (-1, 0), (0, 1), (0, -1)])
    nx, ny = p.x + dx, p.y + dy
    if lv.is_walkable(nx, ny) and not lv.monster_at(nx, ny):
        p.x, p.y = nx, ny
        lv.set_player_pos(nx, ny)
lv.recompute_fov(p.x, p.y)
shot("03_explore.png")

# принудительно покажем предметы и монстров рядом
it = next(iter(lv.items.values()))
lx, ly = next(iter(lv.items))
p.x, p.y = max(1, lx - 2), max(1, ly - 2)
lv.set_player_pos(p.x, p.y)
lv.recompute_fov(p.x, p.y)
shot("04_items.png")

g.show_char()
shot("05_char.png")
g.close_modal()

g.show_help()
shot("06_help.png")
g.close_modal()

# инвентарь
from game.items import Item

for name in ["dagger", "long sword", "potion of healing", "scroll of identify",
             "wand of fire", "chain mail", "food ration", "gold piece"]:
    p.items.append(Item(name))
p.items[0].equipped = "wield"
p.items[5].equipped = "armor"
g.open_inventory()
shot("07_inventory.png")
g.close_modal()

# прицеливание
g.mode = "play"
g.start_target("fire")
g.target_pos = (p.x + 4, p.y)
shot("08_target.png")
g.targeting = None
g.mode = "play"

# экран смерти
p.hp = 0
g.win = False
g.mode = "dead"
g.draw_death()
shot("09_death.png")

print("OK")

# --- русский язык --------------------------------------------------------
from game import lang

for code, suffix in (("en", ""), ("ru", "_ru")):
    lang.set_lang(code)
    g.refresh_title_menu()
    g.mode = "title"
    shot(f"10_title{suffix}.png")
    g.new_game()
    p = g.player
    from game.items import Item

    for n in ["dagger", "chain mail", "potion of healing", "scroll of identify",
              "wand of fire", "food ration", "gold piece", "ring of strength"]:
        p.items.append(Item(n))
    p.items[0].equipped = "wield"
    p.items[1].equipped = "armor"
    lv.items[(p.x, p.y)] = Item("potion of extra healing")
    lv.items[(p.x + 2, p.y)] = Item("scroll of teleport")
    lv.recompute_fov(p.x, p.y)
    shot(f"11_play{suffix}.png")
    g.show_help()
    shot(f"12_help{suffix}.png")
    g.close_modal()
    g.show_char()
    shot(f"13_char{suffix}.png")
    g.close_modal()
    g.open_inventory()
    shot(f"14_inventory{suffix}.png")
    g.close_modal()
    g.mode = "modal"
    g.open_settings()
    shot(f"15_settings{suffix}.png")
    # открыть управление (пункт 2)
    g.menu.index = 2
    g.on_key(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, mod=0))
    shot(f"16_controls{suffix}.png")
    # выбрать первое действие -> режим переназначения
    g.menu.index = 0
    g.on_key(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, mod=0))
    shot(f"17_rebind{suffix}.png")
    # Esc -> обратно к списку, затем Esc -> закрыть
    g.on_key(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0))
    g.on_key(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0))
    g.on_key(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0))
    g.mode = "play"

lang.set_lang("en")
print("LANG SHOTS OK")