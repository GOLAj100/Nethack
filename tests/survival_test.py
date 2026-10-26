"""Deterministic UI/survival tests without modifying user settings."""
import os
import sys
import tempfile
from unittest.mock import patch
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame
from main import make_window
from game.app import Game
from game import lang
from game.entities import Player, Actor
from game.items import Item

pygame.init()
with tempfile.TemporaryDirectory() as tmp, patch.object(lang, "SETTINGS_PATH", os.path.join(tmp, "settings.json")):
    g = Game(make_window(), seed=42)
    g.new_game()
    p = g.player
    p.items.append(Item("apple"))
    g.level.monsters.clear()
    p.status["asleep"] = 3
    turns = p.turns
    for key in (pygame.K_F2, pygame.K_SLASH, pygame.K_i):
        g.on_key(pygame.event.Event(pygame.KEYDOWN, key=key, mod=0))
        assert g.mode in ("modal", "inventory")
        assert p.turns == turns and p.status["asleep"] == 3
        if g.mode == "inventory":
            g.handle_inventory_result("close")
        else:
            g.close_modal()
    g.key_play(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_w, mod=0))
    assert p.turns == turns+1 and p.status["asleep"] == 2
    p.status["asleep"] = 0
    g.level.doors = {(p.x+1, p.y): {"locked": True}, (p.x+5, p.y): {"locked": True}}
    assert g.pick_lock()
    assert len(g.menu.entries) == 1
    cb = g.menu_cb
    g.close_modal()
    cb(0)
    assert g.level.doors[(p.x+1, p.y)]["open"]
    assert not g.pick_lock()
    p.hp = 1
    before = p.turns
    g.rest()
    assert p.turns == before+10 and p.hp == 11
    m = Actor(p.x, p.y, hp=10)
    g.level.monsters = [m]
    before = p.turns
    g.rest()
    assert p.turns == before
    g.level.monsters.clear()
    def arrive():
        g.level.monsters.append(m)
    with patch.object(g, "monster_turn", side_effect=arrive):
        g.rest()
    assert p.turns == before+1
    g.level.monsters.clear()
    p.items = [Item("dagger"), Item("long sword")]
    p.equip(p.items[0])
    g.swap_weapon()
    assert p.wielded is p.items[1] and g.mode == "play"
    g.swap_weapon()
    assert p.wielded is p.items[0]
    ctl = g.ctl
    ctl.assign("move_north", 0, pygame.K_F9)
    for key in (pygame.K_w, pygame.K_UP, pygame.K_KP8, pygame.K_F9):
        assert ctl.action_for(key, 0) == "move_north"
    assert ctl.action_for(pygame.K_b, pygame.KMOD_SHIFT) == "rest"
    assert ctl.action_for(pygame.K_x, pygame.KMOD_SHIFT) == "swap_weapon"
    p = Player()
    p.con = 14
    before = p.max_hp
    with patch("game.entities.random.randint", return_value=3):
        p.gain_exp(p.xp_for_next_level())
    assert p.max_hp == before+5
pygame.quit()
print("SURVIVAL OK")
