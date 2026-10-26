"""Тест настройки управления: раскладки, переназначение, сохранение, справка."""

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
from game.controls import (ACTION_GROUPS, ACTIONS, Controls, code_of, fmt,
                            label, name_of, parse)

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


def key(g, k, mod=0):
    g.on_key(pygame.event.Event(pygame.KEYDOWN, key=k, mod=mod, unicode="", scancode=0))


# --- 1. разбор имён клавиш ------------------------------------------------
print("разбор имён клавиш:")
for name in ["w", "left", ".", ",", ">", "<", "/", "f2", "space", "[5]", "return"]:
    try:
        code = code_of(name)
        back = name_of(code)
        check(f"{name!r} -> {code} -> {back!r}", True)
    except Exception:
        errors.append(f"key {name}:\n{traceback.format_exc()}")
        check(f"{name!r}", False)

check("shift+d разбирается", parse("shift+d") == (pygame.KMOD_SHIFT, pygame.K_d))
check("shift+d печатается", fmt(*parse("shift+d")) == "shift+d")
check("метки читаемы", label(*parse("shift+d")) == "Shift+d")
check("метка numpad", label(*parse("[5]")) == "Num5")
check("метка стрелки", label(*parse("left")) == "←")

# --- 2. раскладки по умолчанию --------------------------------------------
print("раскладки по умолчанию:")
ctl = Controls()
flat = [a for _g, items in ACTION_GROUPS for a, _ in items]
check("все действия описаны", set(flat) == set(ctl.bindings.keys()))
check("у каждого есть клавиша", all(ctl.bindings[a] for a in flat))

# первичные клавиши не должны совпадать (иначе одна команда перекроет другую)
prim = {}
dups = []
for a in flat:
    b = ctl.primary.get(a)
    if b in prim:
        dups.append(f"{prim[b]} и {a} -> {b}")
    prim[b] = a
check("нет конфликтов основных клавиш", not dups)
for d in dups:
    print("        конфликт:", d)

check("WASD работает", ctl.action_for(pygame.K_d, 0) == "move_east")
check("стрелки работают", ctl.action_for(pygame.K_LEFT, 0) == "move_west")
check("numpad работает", ctl.action_for(pygame.K_KP7, 0) == "move_nw")
check("точка - ждать", ctl.action_for(pygame.K_PERIOD, 0) == "wait")
check("> - спуск", ctl.action_for(pygame.K_GREATER, 0) == "descend")
check("Shift+D - выбросить", ctl.action_for(pygame.K_d, pygame.KMOD_SHIFT) == "drop")
check("Shift+S - сохранить", ctl.action_for(pygame.K_s, pygame.KMOD_SHIFT) == "save")
check("F2 - настройки", ctl.action_for(pygame.K_F2, 0) == "settings")
check("неизвестная клавиша -> None", ctl.action_for(pygame.K_F12, 0) is None)
check("Ctrl не перехватывается", ctl.action_for(pygame.K_d, pygame.KMOD_CTRL) is None)

# --- 3. переназначение ----------------------------------------------------
print("переназначение:")
ctl2 = Controls()
ctl2.assign("inventory", 0, pygame.K_F6)
check("F6 теперь инвентарь", ctl2.action_for(pygame.K_F6, 0) == "inventory")
check("старая клавиша i осталась альтернативой", ctl2.action_for(pygame.K_i, 0) == "inventory")
check("Esc нельзя назначить", ctl2.assign("inventory", 0, pygame.K_ESCAPE) is None)
check("F1 нельзя назначить", ctl2.assign("inventory", 0, pygame.K_F1) is None)
ctl2.add_alias("inventory", 0, pygame.K_F7)
check("дополнительная клавиша работает", ctl2.action_for(pygame.K_F7, 0) == "inventory")

# --- 4. сохранение и загрузка ---------------------------------------------
print("сохранение и загрузка:")
data = ctl2.save()
check("сохранился F6", "f6" in " ".join(data["inventory"]))
ctl3 = Controls()
ctl3.load(data)
check("загрузился F6", ctl3.action_for(pygame.K_F6, 0) == "inventory")
ctl3.reset()
check("сброс вернул i", ctl3.action_for(pygame.K_i, 0) == "inventory")
ctl3.load({"inventory": ["F6"], "wait": ["["], "bogus": ["z"]})
check("мусор в настройках не ломает", ctl3.action_for(pygame.K_F6, 0) == "inventory")
check("действие не исчезло", bool(ctl3.bindings["pickup"]))

# --- 5. переназначение в игре ---------------------------------------------
print("переназначение в игре:")
lang.set_lang("en")
g = Game(r)
g.ctl.reset()
g.new_game()

g.open_controls()
check("меню управления открылось", g.mode == "modal" and g.menu is not None)
n = len(g.menu.entries)
check("в меню есть сброс", g.menu.entries[-1] == lang.t("set.reset"))

g.menu.index = 1  # move_south
key(g, pygame.K_RETURN)
check("режим переназначения", g.mode == "rebind" and g.rebind == "move_south")
g.draw()

key(g, pygame.K_F6, pygame.KMOD_SHIFT)
check("клавиша назначена", g.ctl.action_for(pygame.K_F6, pygame.KMOD_SHIFT) == "move_south")
check("вернулись в меню", g.mode == "modal")
g.draw()

# отмена
g.menu.index = 2
key(g, pygame.K_RETURN)
before = g.ctl.primary_label("move_west")
key(g, pygame.K_ESCAPE)
check("Esc отменяет", g.mode == "modal" and g.rebind is None)
check("клавиша не изменилась", g.ctl.primary_label("move_west") == before)

# сброс
g.menu.index = len(g.menu.entries) - 1
key(g, pygame.K_RETURN)
check("сброс вернул умолчания", g.ctl.action_for(pygame.K_j, 0) == "move_south")

# Esc из меню управления
while g.mode == "modal":
    key(g, pygame.K_ESCAPE)
check("Esc закрыл меню", g.mode in ("play", "title"))

# --- 6. сохранение настроек на диск ---------------------------------------
print("настройки на диске:")
lang.set_lang("ru")
g.ctl.assign("quaff", 0, pygame.K_F9)
lang.save_settings(g)
lang.set_lang("en")
g2 = Game(r)
check("язык загружен", lang.get_lang() == "ru")
check("клавиши загружены", g2.ctl.action_for(pygame.K_F9, 0) == "quaff")
lang.set_lang("en")
lang.save_settings()

# --- 7. справка строится из раскладок -------------------------------------
print("справка:")
g2.lang_before = g2.ctl.primary_label("inventory")
g2.ctl.assign("inventory", 0, pygame.K_F6)
g2.show_help()
check("справка открылась", g2.mode == "modal")
title, lines = g2.modal_lines
text = "\n".join(l for l, _ in lines)
check("в справке есть новая клавиша", "F6" in text)
check("в справке есть заголовки групп", "Movement" in text and "System" in text)
g2.close_modal()
g2.ctl.reset()

# --- 8. русская справка ----------------------------------------------------
lang.set_lang("ru")
g2.show_help()
title, lines = g2.modal_lines
text = "\n".join(l for l, _ in lines)
check("русские заголовки", "Движение" in text and "Система" in text)
check("русские названия действий", "Открыть инвентарь" in text)
g2.close_modal()
lang.set_lang("en")

# --- 9. переводы для новых строк ------------------------------------------
used = set()
for root, _, files in os.walk("game"):
    for fn in files:
        if fn.endswith(".py") and fn != "lang.py":
            src = open(os.path.join(root, fn), encoding="utf-8").read()
            used |= set(__import__("re").findall(
                r"""(?<![\w.])t\(\s*["']([a-z][\w.]*)["']""", src))
used |= {m for m in __import__("re").findall(
    r"""(?<![\w.])t\(f["']([\w.]+)""", open("game/controls.py", encoding="utf-8").read())}
missing = sorted(k for k in used if not k.endswith(".") and k not in lang.S)
check("все ключи есть в таблице", not missing)
for m in missing[:10]:
    print("        нет ключа:", m)

print()
if errors:
    print("НАЙДЕНО ОШИБОК:", len(errors))
    for e in errors:
        print("-" * 60)
        print(e)
    raise SystemExit(1)
print("ТЕСТ УПРАВЛЕНИЯ ПРОЙДЕН")
