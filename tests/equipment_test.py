"""Equipment regressions; no writes to saves/settings."""
import os
import sys
import random
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from game.entities import Player, Actor
from game.items import Item, make_random_item, WEAPON_POOL, POTION_POOL
from game import combat
from game.app import Game
from game.level import Level
from game.rng import RNG
from game import mapgen as MG

p = Player()
w = Item("long sword")
p.items.append(w)
p.equip(w)
assert p.hit_bonus == w.spec["hit"]
with patch.object(combat.random, "randint", return_value=8) as roll:
    assert combat.roll_damage(p) == 8 + p.damage_bonus
    roll.assert_called_once_with(*p.weapon_dmg)
with patch.object(combat.random, "random", return_value=0), patch.object(combat.random, "randint", return_value=8) as roll:
    target = Actor(hp=100, max_hp=100)
    result = combat.ranged_attack(p, target, SimpleNamespace(audio=Mock(), floats=[]))
    assert len(result) == 2
    roll.assert_called_once_with(*p.weapon_dmg)
for name, stat in (("strength", "str"), ("dexterity", "dex"), ("constitution", "con")):
    ring = Item("ring of " + name)
    p.items.append(ring)
    p.equip(ring)
    assert getattr(p, stat) == 12
    setattr(p, stat, getattr(p, stat) + 1)
    restored = Player()
    restored.load_dict(p.to_dict())
    assert getattr(restored, stat) == 13
    ring.equipped = None
    assert getattr(p, stat) == 11

enemy = Actor(dmg=(9, 9))
ctx = SimpleNamespace(audio=Mock(), floats=[])
with patch.object(combat.random, "random", return_value=0), patch.object(combat.random, "randint", side_effect=[9, 3]):
    before = p.hp
    combat.attack(enemy, p, ctx)
    assert p.hp == before - 6

a, b = RNG(123), RNG(123)
for _ in range(100):
    first = make_random_item(5, rng=a).to_dict()
    random.random()
    assert first == make_random_item(5, rng=b).to_dict()
assert {"bow", "crossbow"} <= set(WEAPON_POOL)
assert "potion of full healing" in POTION_POOL

lv = Level(1, 80, 50, RNG(7))
lv.tiles = [MG.FLOOR] * (lv.w * lv.h)
lv.light_sources.clear()
lv.update_lighting(20, 20, False)
assert lv.light_grid[31][20] == 0.05
lv.update_lighting(20, 20, True)
assert lv.light_grid[31][20] > 0.05
g = Game.__new__(Game)
g.player, g.level = Player(20, 20), lv
g.lamp_flicker_modifier = 1.0
lantern = Item("lantern")
g.player.items.append(lantern)
g.update_lighting()
assert lv.light_grid[31][20] == 0.05
g.player.equip(lantern)
g.update_lighting()
assert lv.light_grid[31][20] > 0.05
pick = Item("pick-axe")
g.player.items.append(pick)
g.player.equip(pick)
g.audio, g.end_turn = Mock(), Mock()
lv.set(21, 20, MG.WALL)
lv.set(20, 21, MG.WALL)
g.step_to(21, 20)
assert lv.at(21, 20) == MG.FLOOR and lv.at(20, 21) == MG.WALL
g.end_turn.assert_called_once()

g.monster_turn = Mock()
g.player.hp = g.player.max_hp
ring = Item("ring of hunger")
g.player.items.append(ring)
g.player.equip(ring)
g.player.turns = 19
before = g.player.nutrition
Game.end_turn(g)
assert g.player.nutrition == before
g.player.turns = 39
Game.end_turn(g)
assert g.player.nutrition == before - 1
print("EQUIPMENT OK")
