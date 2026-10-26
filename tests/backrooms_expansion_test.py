"""Regression coverage for B-Levels 7-10 and Level 7 swimming."""
import os
import sys
from types import SimpleNamespace

os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game import backrooms
from game import mapgen as MG
from game.entities import Player
from game.world import World


for number, generator in ((7, 'ocean'), (8, 'cave'), (9, 'suburbs'), (10, 'fields')):
    world = World(7717, number)
    lv = world.chunk(0, 0, visit=True)
    assert lv.kind == generator
    assert lv.w == 80 and lv.h == 50
    if number < 10:
        assert any(exit_['target'] == number + 1 for exit_ in lv.exits.values())
    world.storage.cleanup()

world = World(7717, 7)
lv = world.chunk(0, 0, visit=True)
water = next((x, y) for y in range(lv.h) for x in range(lv.w) if lv.at(x, y) == MG.WATER)
player = Player(*water)
player.b_level = 7
player.world_z = 0
game = SimpleNamespace(player=player, level=lv, world=world, messages=[])
game.msg = game.messages.append
game.on_death = lambda: None

before_stamina = player.stamina
for _ in range(5):
    player.turns += 1
    backrooms.advance_environment(game)
assert player.status['swim_turns'] == 5
assert player.stamina == before_stamina - 1

world.profile = dict(world.profile, swim_damage_interval=5)
lv.profile = world.profile
player.status['swim_turns'] = 4
before_hp = player.hp
backrooms.advance_environment(game)
assert player.hp == before_hp - 1

# Level 10's clean lakes are traversable, but do not cause Level 7's cold damage.
normal = World(7717, 10)
normal_lv = normal.chunk(0, 0)
water = next((x, y) for y in range(normal_lv.h) for x in range(normal_lv.w)
             if normal_lv.at(x, y) == MG.WATER)
assert normal_lv.is_walkable(*water)
lake_player = Player(*water)
lake_game = SimpleNamespace(player=lake_player, level=normal_lv, world=normal,
                            messages=[])
lake_game.msg = lake_game.messages.append
lake_game.on_death = lambda: None
for _ in range(20):
    lake_player.turns += 1
    backrooms.advance_environment(lake_game)
assert lake_player.hp == lake_player.max_hp
normal.storage.cleanup()
world.storage.cleanup()
print('BACKROOMS EXPANSION OK')
