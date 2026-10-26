"""Стресс-тест: длинная случайная игра с отрисовкой каждого хода.

Цель - поймать исключения, из-за которых окно игры закрывается.
"""

import os
import random
import sys
import traceback

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame

from engine import config as C
from engine.renderer import Renderer
from game.app import Game

pygame.init()
probe = pygame.display.set_mode((64, 64))
r = Renderer(probe)
cols = C.CAMERA_W + C.SIDEBAR_W
rows = C.TOPBAR_H + C.CAMERA_H + C.LOG_H
r.surface = pygame.display.set_mode((cols * r.cw, rows * r.ch))
g = Game(r)
g.new_game()

rng = random.Random(2024)
LEVELS = int(os.environ.get("STRESS_LEVELS", "12"))
TURNS = int(os.environ.get("STRESS_TURNS", "400"))
errors = []

KEYS = [pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT,
        pygame.K_y, pygame.K_u, pygame.K_b, pygame.K_n,
        pygame.K_PERIOD, pygame.K_i, pygame.K_g, pygame.K_COMMA,
        pygame.K_e, pygame.K_q, pygame.K_r, pygame.K_x,
        pygame.K_f, pygame.K_z, pygame.K_t, pygame.K_c, pygame.K_m,
        pygame.K_SLASH, pygame.K_p, pygame.K_F2, pygame.K_F3]


def press(k, mod=0):
    g.on_key(pygame.event.Event(pygame.KEYDOWN, key=k, mod=mod, unicode="",
                                scancode=0))


def run_turn(i):
    """Один ход со случайным набором нажатий."""
    steps = rng.randint(1, 4)
    for _ in range(steps):
        k = rng.choice(KEYS)
        mod = pygame.KMOD_SHIFT if rng.random() < 0.15 else 0
        if mod and k in (pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT,
                         pygame.K_RIGHT, pygame.K_PERIOD, pygame.K_SLASH):
            mod = 0
        try:
            press(k, mod)
        except Exception:
            errors.append(("input", k, traceback.format_exc()))
            return False
        # закрываем всё, что открылось, иначе застрянем в модалке
        for _ in range(6):
            if g.mode in ("modal", "rebind"):
                try:
                    press(pygame.K_ESCAPE)
                except Exception:
                    errors.append(("modal", k, traceback.format_exc()))
                    return False
            elif g.mode == "target":
                try:
                    press(pygame.K_ESCAPE)
                except Exception:
                    errors.append(("target", k, traceback.format_exc()))
                    return False
            else:
                break
        if g.mode == "dead":
            return False
        if g.mode == "title":
            # случайно попали в "сохранить и выйти" - продолжаем игру
            g.new_game()
    return True


for depth in range(1, LEVELS + 1):
    if g.mode != "play":
        print(f"  game ended early at depth {g.player.depth}, mode={g.mode}")
        break
    t0 = depth
    # спускаемся на следующий уровень
    if depth > 1:
        lv = g.level
        sx, sy = lv.stairs_down
        g.player.x, g.player.y = sx, sy
        lv.set_player_pos(sx, sy)
        lv.recompute_fov(sx, sy)
    for i in range(TURNS):
        if not run_turn(i):
            break
        try:
            g.draw()
            pygame.display.flip()
        except Exception:
            errors.append(("draw", depth, traceback.format_exc()))
            break
        if g.mode == "dead":
            break
    print(f"depth {depth:2d}: kind={g.level.kind:6s} rooms={len(g.level.rooms):2d} "
          f"monsters={len(g.level.monsters):3d} turns={g.player.turns} "
          f"hp={g.player.hp}/{g.player.max_hp} mode={g.mode}")
    if g.mode == "dead":
        print("  -> умер, перезапуск")
        g._dead = False
        g.win = False
        g.mode = "play"
        g.new_game()
    # принудительный спуск на следующий уровень
    if depth < LEVELS:
        lv = g.level
        sx, sy = lv.stairs_down
        g.player.x, g.player.y = sx, sy
        lv.set_player_pos(sx, sy)
        try:
            g.descend()
        except Exception:
            errors.append(("descend", depth, traceback.format_exc()))
            break

print()
if errors:
    print(f"НАЙДЕНО ОШИБОК: {len(errors)}")
    seen = set()
    for kind, ctx, tb in errors:
        key = tb.strip().splitlines()[-1][:120]
        if key in seen:
            continue
        seen.add(key)
        print("=" * 70)
        print(f"[{kind}] ctx={ctx}")
        print(tb)
    raise SystemExit(1)
print("СТРЕСС-ТЕСТ ПРОЙДЕН БЕЗ ОШИБОК")
