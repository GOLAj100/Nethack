"""Тест локализации: ru/en переключаются, ключи полные, всё рендерится."""

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
from game.items import ITEMS, Item
from game.monsters import MONSTERS

pygame.init()
probe = pygame.display.set_mode((64, 64))
r = Renderer(probe)
cols = C.CAMERA_W + C.SIDEBAR_W
rows = C.TOPBAR_H + C.CAMERA_H + C.LOG_H
r.surface = pygame.display.set_mode((cols * r.cw, rows * r.ch))

errors = []

# --- 1. все ключи присутствуют в обоих языках -----------------------------
missing_ru = [k for k, v in lang.S.items() if len(v) < 2 or not v[1].strip()]
if missing_ru:
    errors.append(("lang table", "нет русского перевода: " + ", ".join(missing_ru[:10])))
missing_en = [k for k, v in lang.S.items() if not v[0].strip()]
if missing_en:
    errors.append(("lang table", "нет английского: " + ", ".join(missing_en[:10])))

# --- 2. ключи, используемые в коде, существуют -----------------------------
source = ""
for root, _, files in os.walk("game"):
    for fn in files:
        if fn.endswith(".py") and fn != "lang.py":
            source += open(os.path.join(root, fn), encoding="utf-8").read()
import re

used = set(re.findall(r"""(?<![\w.])t\(\s*["']([a-z][\w.]*)["']""", source))
used |= {m for m in re.findall(r"""(?<![\w.])t\(f["']([\w.]+)""", source)}
used = {k for k in used if not k.endswith(".")}
unknown = sorted(k for k in used if k not in lang.S)
if unknown:
    errors.append(("lang table", "нет такого ключа: " + ", ".join(unknown[:15])))

# --- 3. названия предметов и монстров --------------------------------------
for name in ITEMS:
    if name not in lang.ITEM_NAMES:
        errors.append(("items", f"нет перевода предмета: {name}"))
for name in MONSTERS:
    if name not in lang.MONSTER_NAMES:
        errors.append(("monsters", f"нет перевода монстра: {name}"))

# --- 4. форматирование всех строк в обоих языках ---------------------------
for code in lang.LANGS:
    lang.set_lang(code)
    for key, pair in lang.S.items():
        try:
            lang.t(key)
        except Exception:
            errors.append(("format", f"{code}:{key}\n{traceback.format_exc()}"))

# --- 5. полный прогон игры на каждом языке ---------------------------------
for code in lang.LANGS:
    lang.set_lang(code)
    g = Game(r)
    try:
        g.refresh_title_menu()
        g.draw()
        g.new_game()
        p = g.player
        from game.items import Item as I

        p.items.extend(I(n) for n in
                       ["dagger", "chain mail", "potion of healing",
                        "scroll of identify", "wand of fire", "food ration",
                        "gold piece", "ring of strength"])
        p.items[0].equipped = "wield"
        p.items[1].equipped = "armor"
        p.status["confused"] = 3
        p.status["hallucinating"] = 5
        p.status["lucky"] = 7
        for fn in (g.show_char, g.show_help, g.open_inventory,
                   g.open_pick_items, g.force_attack, g.pick_lock):
            try:
                fn()
            except Exception:
                errors.append((f"{code}:{fn.__name__}", traceback.format_exc()))
            for _ in range(6):
                if g.mode == "modal":
                    g.close_modal()
                elif g.mode == "target":
                    g.targeting = None
                    g.mode = "play"
                else:
                    break
            g.mode = "play"
        g.show_item_actions(p.items[2])
        g.draw()
        g.close_modal()
        g.mode = "play"
        g.draw()
        g.toggle_lights()
        g.toggle_map()
        g.toggle_map()
        g.end_turn()
        g.draw()
        # монстры и предметы на экране
        for m in g.level.monsters[:10]:
            m.title
        for it in list(g.level.items.values())[:10]:
            it.label()
        # смерть
        p.hp = 0
        p.corpse = True
        g.win = False
        g.mode = "dead"
        g.draw()
        # краш-экран
        g.crash_tb = "Traceback (most recent call last):\n  ValueError: test"
        g.mode = "crash"
        g.draw()
        g.mode = "title"
        g.draw()
        # меню настроек
        g.mode = "modal"
        g.open_settings()
        g.draw()
        g.close_modal()
    except Exception:
        errors.append((f"{code}:game", traceback.format_exc()))

# --- 6. сохранение настроек ----------------------------------------------
lang.set_lang("ru")
lang.save_settings()
data = lang.load_settings()
if data.get("lang") != "ru" or lang.get_lang() != "ru":
    errors.append(("settings", f"настройки не сохранились: {data}"))
lang.set_lang("en")

print()
if errors:
    print(f"НАЙДЕНО ОШИБОК: {len(errors)}")
    for label, tb in errors:
        print("=" * 70)
        print(label)
        print(tb)
    raise SystemExit(1)
print(f"ключей в таблице: {len(lang.S)}")
print("предметов: %d, монстров: %d" % (len(ITEMS), len(MONSTERS)))
print("ТЕСТ ЛОКАЛИЗАЦИИ ПРОЙДЕН")
