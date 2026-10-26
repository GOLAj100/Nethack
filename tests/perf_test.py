"""Замер производительности: время хода и отрисовки на разных глубинах."""

import os
import random
import sys
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame

from engine import config as C
from engine.renderer import Renderer
from game.app import Game
from game import mapgen as MG

pygame.init()
probe = pygame.display.set_mode((64, 64))
r = Renderer(probe)
cols = C.CAMERA_W + C.SIDEBAR_W
rows = C.TOPBAR_H + C.CAMERA_H + C.LOG_H
r.surface = pygame.display.set_mode((cols * r.cw, rows * r.ch))
g = Game(r)


def bench(depth, turns=60):
    g.new_game()
    lv = g.level
    for _ in range(depth - 1):
        lv = g.level
        sx, sy = lv.stairs_down
        g.player.x, g.player.y = sx, sy
        g.descend()
    lv = g.level
    lv.set_player_pos(g.player.x, g.player.y)
    lv.recompute_fov(g.player.x, g.player.y)

    # будим всех - худший случай
    for m in lv.monsters:
        m.awake = True
    # добавим побольше монстров для проверки нагрузки на ИИ
    while len(lv.monsters) < 60:
        pos = lv.random_open_tile()
        if not pos:
            break
        from game.entities import Actor
        m = Actor(pos[0], pos[1], name="test entity", hp=6, max_hp=6)
        m.awake = m.hostile = True
        lv.monsters.append(m)

    rng = random.Random(1)
    turn_ms = draw_ms = 0.0
    for _ in range(turns):
        dx, dy = rng.choice([(1, 0), (-1, 0), (0, 1), (0, -1)])
        t = time.perf_counter()
        g.move(dx, dy)
        turn_ms += (time.perf_counter() - t) * 1000
        t = time.perf_counter()
        g.draw()
        draw_ms += (time.perf_counter() - t) * 1000
        pygame.display.flip()
    print(f"depth {depth:2d} | monsters {len(lv.monsters):3d} | "
          f"turn {turn_ms/turns:6.2f} ms | draw {draw_ms/turns:6.2f} ms | "
          f"total {(turn_ms+draw_ms)/turns:6.2f} ms")


for d in (1, 5, 10, 15, 20, 25, 30):
    bench(d)
