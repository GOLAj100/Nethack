"""Content migration, empty roster, liquid placeholders and Z-aware entity hooks."""
import os
import sys
import tempfile
from unittest.mock import patch

os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
from main import make_window
from game import ai, effects, lang, monsters as MON
from game.app import Game
from game.entities import Actor
from game.items import ITEMS, POTION_POOL, Item
from game.level import Level, populate, monster_to_dict
from game.rng import RNG
from game.world import World

assert MON.MONSTERS and MON.random_monster(1, b_level=1) is None
assert MON.spawn_monster(None, 1, 1, 1) is None
for depth in (1, 10, 30):
    lv = Level(depth, 80, 50, RNG(depth))
    populate(lv, lv.rng)
    assert not lv.monsters
    assert lv.items

for code in ('en', 'ru'):
    lang.set_lang(code)
    for key in ITEMS:
        assert key in lang.ITEM_NAMES
        label = lang.item_name(key).lower()
        assert not any(word in label for word in (
            'orcish', 'potion', 'scroll', 'wand', 'оркск', 'зелье', 'свиток', 'палочка'))
lang.set_lang('en')
assert lang.item_name('war hammer') == 'hammer'
assert lang.item_name('orcish axe') == 'fire axe'
assert lang.item_name('orcish helm') == 'military helm'
assert lang.item_name('potion of healing') == 'almond water'
assert lang.item_name('potion of poison') == 'liquid pain'
# Legacy item IDs survive round-trip and keep their existing effect.
it = Item.from_dict(Item('potion of healing').to_dict())
assert it.name == 'potion of healing'

pygame.init()
with tempfile.TemporaryDirectory() as tmp, patch.object(
        lang, 'SETTINGS_PATH', os.path.join(tmp, 'settings.json')):
    g = Game(make_window(), seed=44)
    g.new_game()
    assert not g.level.monsters
    for cx in range(8):
        assert not g.world.chunk(cx, 0).monsters
    assert not any(lv.monsters for lv in g.world.chunks.values())
    for name in ('distilled water', 'salt water', 'stagnant water'):
        assert name in POTION_POOL
        bottle = Item(name)
        bottle.cursed = False
        g.player.saturation = 50
        g.player.meal = None
        g.player.items.append(bottle)
        before = g.player.turns
        g.do_quaff(bottle)
        assert bottle not in g.player.items
        assert g.player.turns == before + 1

    # Old saves lose retired actors; terrain and items survive migration.
    data = g.level.serialize()
    data['monsters'] = [monster_to_dict(Actor(5, 5, name='kobold'))]
    data['items']['5,5'] = it.to_dict()
    loaded = Level.deserialize(data, RNG(1))
    assert not loaded.monsters
    assert loaded.item_at(5, 5).name == 'potion of healing'
    assert loaded.tiles == g.level.tiles

    # Temporary definition exercises the future registry without shipping an entity.
    definition = dict(glyph='E', color=(255, 255, 255), hp=10, ac=0,
                      dmg=(1, 2), hit=1, speed=100, b_levels=[0],
                      z_range=(1, 2), behavior='test_behavior', awake_chance=1)
    with patch.dict(MON.MONSTERS, {'test entity': definition}):
        assert MON.random_monster(0, b_level=0, world_z=0) is None
        assert MON.random_monster(0, b_level=1, world_z=1) is None
        assert MON.random_monster(0, b_level=0, world_z=1) == 'test entity'
        profile = dict(g.world.profile, z_min=-1, z_max=2)
        world = World(44, profile=profile)
        lower = world.chunk(0, 0, 0)
        upper = world.chunk(0, 0, 1)
        assert not lower.monsters and upper.monsters
        m = upper.monsters[0]
        assert m.b_level == 0 and m.world_z == 1 and m.behavior == 'test_behavior'
        calls = []
        with patch.dict(ai.BEHAVIORS, {'test_behavior': lambda *args: calls.append(args)}):
            ai.take_turn(m, g, upper, {(0, 0, 1): upper})
            assert not calls  # Player on another Z must not be targeted.
            with patch.object(g.player, 'world_z', 1):
                ai.take_turn(m, g, upper, {(0, 0, 1): upper})
                assert len(calls) == 1
        restored = Level.deserialize(upper.serialize(), RNG(2)).monsters[0]
        assert (restored.b_level, restored.world_z, restored.behavior) == (0, 1, 'test_behavior')
        world.storage.cleanup()
    assert set(MON.MONSTERS) >= {'the thing', 'mortisdoptera swarm', 'the observer', 'burrowing worm'}
    g.world.storage.cleanup()
pygame.quit()
print('BACKROOMS CONTENT OK')
