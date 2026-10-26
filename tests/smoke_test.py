"""Дымовой тест: генерация, ходьба, бой, предметы, сохранение (без окна)."""

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame

from engine import config as C
from engine.renderer import Renderer
from game.app import Game
from game import mapgen as MG

pygame.init()
screen = pygame.display.set_mode((1200, 800))
r = Renderer(screen)
g = Game(r)
print("font:", r.font_name, "cell:", r.cw, "x", r.ch)

g.new_game()
print("mode:", g.mode, "level kind:", g.level.kind, "rooms:", len(g.level.rooms))
print("visible tiles:", len(g.level.visible), "stairs:", g.level.stairs_down)
print("monsters:", len(g.level.monsters), "items:", len(g.level.items))

# симулируем 3000 случайных ходов
import random
rng = random.Random(12345)
steps = 0
kills = 0
for i in range(3000):
    dx, dy = rng.choice([(0, -1), (0, 1), (-1, 0), (1, 0), (0, 0)])
    if dx == 0 and dy == 0:
        g.wait()
    else:
        g.move(dx, dy)
    steps += 1
    if g.mode != "play":
        print("game ended at step", steps, "mode", g.mode)
        break

print("turns:", g.player.turns, "hp:", g.player.hp, "/", g.player.max_hp,
      "lvl:", g.player.lvl, "depth:", g.player.depth, "kills:", g.player.kills,
      "gold:", g.player.gold, "items:", len(g.player.items))
print("messages kept:", len(g.log))

# спуск на пару уровней
for _ in range(3):
    sx, sy = g.level.stairs_down
    g.player.x, g.player.y = sx, sy
    g.level.set_player_pos(sx, sy)
    g.descend()
print("after descends: depth", g.player.depth, "lvl", g.player.lvl,
      "rooms", len(g.level.rooms), "monsters", len(g.level.monsters))

# сохранение / загрузка
ok = g.save_quiet()
print("saved:", ok, os.path.isfile(C.SAVE_PATH))
g.player.gold = 999
loaded = __import__("game.save", fromlist=["load_game"]).load_game(C.SAVE_PATH, g)
print("loaded:", loaded, "gold after load:", g.player.gold, "depth:", g.player.depth)

# проверка предметов
from game.items import Item, make_random_item
from game import effects
for name in ["potion of healing", "scroll of mapping", "wand of fire", "dagger",
             "chain mail", "food ration", "gold piece", "ring of strength"]:
    it = Item(name)
    print(f"  {name:24s} kind={it.kind:8s} glyph={it.glyph} label={it.label()}")

for name in ["potion of healing", "potion of strength", "scroll of mapping",
             "scroll of teleport", "wand of fire", "wand of sleep"]:
    it = Item(name)
    text, color = effects.apply(g.player, g.level, it, target=(g.player.x, g.player.y))
    print(f"  effect {name:22s} -> {text}")

print("OK")
