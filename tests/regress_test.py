"""Регрессия: всплывающий урон и работа настроек из главного меню."""

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
from game import lang

pygame.init()
probe = pygame.display.set_mode((64, 64))
r = Renderer(probe)
cols = C.CAMERA_W + C.SIDEBAR_W
rows = C.TOPBAR_H + C.CAMERA_H + C.LOG_H
r.surface = pygame.display.set_mode((cols * r.cw, rows * r.ch))
errors = []


def check(label, cond):
    if cond:
        print(f"  ok   {label}")
    else:
        errors.append(f"{label}")


def key(g, k, mod=0):
    g.on_key(pygame.event.Event(pygame.KEYDOWN, key=k, mod=mod, unicode="", scancode=0))


# --- 1. всплывающие числа урона ------------------------------------------
print("всплывающий урон:")
g = Game(r)
g.new_game()

# кортежи, как их создаёт combat.py
g.floats.append((g.player.x, g.player.y, "-3", C.RED, 12))
try:
    for _ in range(40):
        g.tick_floats()
    g.draw()
    check("кортежи не падают и исчезают", not g.floats)
except Exception:
    errors.append("floats tuple:\n" + traceback.format_exc())

# списки
g.floats.append([g.player.x, g.player.y, "-5", C.ORANGE, 3])
g.tick_floats()
check("ttl уменьшается у списков", g.floats and g.floats[0][4] == 2)
g.tick_floats()
g.tick_floats()
check("список удаляется по истечении ttl", not g.floats)

# мусорные записи не должны ломать
g.floats.extend([(1, 2), ("x",), (1, 2, "a", C.WHITE)])
try:
    g.tick_floats()
    g.draw()
    check("битые записи отбрасываются", not g.floats)
except Exception:
    errors.append("floats garbage:\n" + traceback.format_exc())

# реальный удар в бою порождает float и он переживает кадр
g.player_attack = g.player_attack
from game import monsters as MON

pos = g.level.random_open_tile()
from game.entities import Actor
m = Actor(pos[0], pos[1], name="test entity", hp=6, max_hp=6)
g.level.monsters.append(m)
g.player.x, g.player.y = pos[0] + 1, pos[1]
g.level.set_player_pos(*(pos[0] + 1, pos[1]))
try:
    for _ in range(30):
        g.player_attack(m)
        g.tick_floats()
        g.draw()
    check("бой + отрисовка 30 ударов", True)
except Exception:
    errors.append("combat floats:\n" + traceback.format_exc())

# --- 2. настройки из главного меню ----------------------------------------
print("настройки из главного меню:")
lang.set_lang("en")
g2 = Game(r)
g2.mode = "title"
check("в главном меню 4 пункта", len(g2.title_menu.entries) == 4)

# открыть настройки: пункт 2
g2.title_menu.index = 2
key(g2, pygame.K_RETURN)
check("режим настроек", g2.mode == "modal" and g2.menu is not None)
if g2.menu:
    print("     ", g2.menu.entries)

# переключить язык
lang_before = lang.get_lang()
key(g2, pygame.K_RETURN)
check("язык переключён", lang.get_lang() != lang_before)
check("меню осталось открытым для обновления", g2.mode == "modal" and g2.menu is not None)
if g2.menu:
    print("     ", g2.menu.entries)
g2.draw()

# переключить звук
before = g2.audio.muted
key(g2, pygame.K_DOWN)
key(g2, pygame.K_RETURN)
check("звук переключён", g2.audio.muted != before)
g2.draw()

# выход из настроек: пункт "Назад" (последний)
g2.menu.index = len(g2.menu.entries) - 1
key(g2, pygame.K_RETURN)
check("вернулись в главное меню, а не в игру", g2.mode == "title")

# Esc из настроек
g2.title_menu.index = 2
key(g2, pygame.K_RETURN)
check("настройки открылись", g2.mode == "modal")
key(g2, pygame.K_ESCAPE)
check("Esc вернул в главное меню", g2.mode == "title")
check("выход из игры не случился", g2.player is None)
g2.draw()

# --- 3. настройки прямо из игры -------------------------------------------
print("настройки из игры:")
g3 = Game(r)
g3.new_game()
key(g3, pygame.K_F2)
check("F2 открывает настройки в игре", g3.mode == "modal")
g3.draw()
key(g3, pygame.K_ESCAPE)
check("Esc вернул в игру", g3.mode == "play")

lang_before = lang.get_lang()
key(g3, pygame.K_F3)
check("F3 меняет язык на лету", lang.get_lang() != lang_before)
key(g3, pygame.K_F3)
muted_before = g3.audio.muted
key(g3, pygame.K_F4)
check("F4 переключает звук", g3.audio.muted != muted_before)
key(g3, pygame.K_F4)
g3.draw()

# --- 3b. настройки управления из игры -------------------------------------
g3.open_controls()
check("меню управления из игры", g3.mode == "modal" and g3.menu is not None)
n_entries = len(g3.menu.entries)
g3.menu.index = 0
key(g3, pygame.K_RETURN)
check("режим переназначения из игры", g3.mode == "rebind")
key(g3, pygame.K_F6)
check("клавиша назначена и вернулись к списку",
      g3.mode == "modal" and g3.ctl.action_for(pygame.K_F6, 0) == "move_north")
check("список сохранил размер", len(g3.menu.entries) == n_entries)
key(g3, pygame.K_ESCAPE)
check("Esc закрыл меню", g3.mode == "play")
g3.ctl.reset()

# --- 4. сохранение настроек ----------------------------------------------
lang.set_lang("ru")
lang.save_settings(g3)
lang.set_lang("en")
data = lang.load_settings(g3)
check("настройки сохранились на диск", data.get("lang") == "ru")
lang.set_lang("en")
lang.save_settings()
# --- 10. check_tile: фонтан и ловушка --------------------------------------
print("check_tile:")
from game import mapgen as MG

p, lv = g.player, g.level
lv.set(p.x, p.y, MG.TRAPDOOR)
hp_before = p.hp
turns_before = p.turns
g.step_to(p.x, p.y)
check("ловушка срабатывает и отнимает здоровье", p.hp < hp_before and p.turns > turns_before)
lv.set(p.x, p.y, MG.FOUNTAIN)
p.hp = 5
p.status["asleep"] = 0
from unittest.mock import patch
with patch("game.app.random.random", return_value=0.0):
    g.step_to(p.x, p.y)
check("фонтан лечит", p.hp > 5)
lv.set(p.x, p.y, MG.FLOOR)
lv.recompute_fov(p.x, p.y)

print()
if errors:
    print("НАЙДЕНО ОШИБОК:", len(errors))
    for e in errors:
        print("=" * 70)
        print(e)
    raise SystemExit(1)
print("РЕГРЕССИОННЫЙ ТЕСТ ПРОЙДЕН")
