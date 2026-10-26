"""Тест ввода: синтетические клавиши проходят через key_play/menu/target."""

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
from game.lang import t

pygame.init()
cols = C.CAMERA_W + C.SIDEBAR_W
rows = C.TOPBAR_H + C.CAMERA_H + C.LOG_H
probe = pygame.display.set_mode((64, 64))
r = Renderer(probe)
r.surface = pygame.display.set_mode((cols * r.cw, rows * r.ch))
g = Game(r)
g.new_game()


def key(k, mod=0, unicode=""):
    ev = pygame.event.Event(pygame.KEYDOWN, key=k, mod=mod, unicode=unicode,
                           mod_num=0, scancode=0, window=None)
    g.on_key(ev)


def press(k, times=1, mod=0):
    for _ in range(times):
        key(k, mod)


g.mode = "play"
p, lv = g.player, g.level

# --- перемещение -------------------------------------------------------
start = (p.x, p.y)
press(pygame.K_RIGHT, 3)
print("moved:", start, "->", (p.x, p.y))
assert (p.x, p.y) != start
press(pygame.K_w, 2)  # вверх
press(pygame.K_s, 1)
print("after w/s:", (p.x, p.y), "turns:", p.turns)

# --- диагональ и ожидание ---------------------------------------------
press(pygame.K_y, 1)
press(pygame.K_PERIOD, 3)
print("diagonal + wait ok, turns:", p.turns)

# --- лестница: спуск ---------------------------------------------------
lv.set(p.x, p.y, MG.STAIR_DOWN)
press(pygame.K_GREATER)
print("descend via > -> depth", p.depth, "level kind", g.level.kind)
# Level 0 is the current Backrooms lobby and has no vertical exit yet.
assert p.depth == 0

# --- инвентарь: открыть, выбрать, надеть --------------------------------
from game.items import Item

p.items.append(Item("dagger"))
p.items.append(Item("potion of healing"))
key(pygame.K_i)
print("mode after i:", g.mode, "panel items:", len(g.inventory_panel.items) if g.inventory_panel else None)
assert g.mode == "inventory" and g.inventory_panel is not None
panel = g.inventory_panel
panel.selected = next(i for i, it in enumerate(panel.items) if it.name == "dagger")
g.on_key(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, mod=0))
print("action menu:", g.menu.entries[:4] if g.menu else None)
assert g.mode == "modal" and g.menu is not None
idx = g.menu.entries.index(t("act.wield"))
press(pygame.K_DOWN, idx)
press(pygame.K_RETURN)
print("wielded:", p.wielded.name if p.wielded else None)
assert p.wielded is not None and p.wielded.name == "dagger"

# --- зелье: выпить ------------------------------------------------------
p.hp = 10
key(pygame.K_q)
press(pygame.K_DOWN, 1)
press(pygame.K_RETURN)
print("after quaff hp:", p.hp, "items:", len(p.items))

# --- еда ----------------------------------------------------------------
p.items.append(Item("food ration"))
p.nutrition = 100
key(pygame.K_e)
entries = g.menu.entries
print("eat menu:", entries)
press(pygame.K_RETURN)
print("nutrition:", p.nutrition)

# --- карта --------------------------------------------------------------
key(pygame.K_m)
print("mapped cells:", len(g.level.mapped), "mode:", g.mode)
press(pygame.K_ESCAPE)

# --- подсказка ----------------------------------------------------------
key(pygame.K_SLASH)
print("help mode:", g.mode)
press(pygame.K_ESCAPE)
print("after esc:", g.mode)

# --- прицеливание и выстрел --------------------------------------------
p.items.append(Item("bow"))
p.items.append(Item("arrow"))
p.items = [it for it in p.items if it.name != "dagger"]
from game.items import Item as I2

bow = I2("bow")
bow.equipped = "wield"
p.items.append(bow)
key(pygame.K_f)
print("fire mode:", g.mode, "menu:", g.menu.entries if g.menu else None)
press(pygame.K_RETURN)   # выбрать стрелу
print("target mode:", g.mode, "target:", g.target_pos)
press(pygame.K_RIGHT, 2)
press(pygame.K_RETURN)
print("after fire, arrows left:", sum(1 for i in p.items if i.kind == "missile"))

# --- очистка модалок и сохранение ---------------------------------------
while g.mode == "modal":
    press(pygame.K_ESCAPE)
g.mode = "play"
key(pygame.K_s, pygame.KMOD_SHIFT)
print("saved:", os.path.isfile(C.SAVE_PATH))

# --- смерть --------------------------------------------------------------
p.hp = 0
p.corpse = True
key(pygame.K_RIGHT)
print("mode after death:", g.mode)
assert g.mode == "dead"
press(pygame.K_RETURN)
print("back to title:", g.mode)

print("INPUT OK")
