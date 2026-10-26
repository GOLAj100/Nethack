"""Regression tests for dropping items and delayed held-movement repeat."""
import os
import sys
import tempfile
from unittest.mock import patch

os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
from main import make_window
from game import lang
from game.app import Game
from game.items import Item

pygame.init()
with tempfile.TemporaryDirectory() as tmp, patch.object(
        lang, 'SETTINGS_PATH', os.path.join(tmp, 'settings.json')):
    game = Game(make_window(), seed=934)
    game.new_game()
    player, level = game.player, game.level
    pos = next((x, y) for y in range(level.h) for x in range(level.w)
               if level.is_walkable(x, y) and (x, y) not in level.items
               and level.monster_at(x, y) is None)
    player.x, player.y = pos

    # Empty player cell: dropping places the exact Item instance on that tile.
    first = Item('dagger', rng=game.rng)
    player.items.append(first)
    game.do_drop(first)
    assert first not in player.items
    assert level.items[pos] is first

    # Occupied floor item: neither item is overwritten or lost.
    existing = Item('apple', rng=game.rng)
    level.items[pos] = existing
    second = Item('lantern', rng=game.rng)
    player.items.append(second)
    game.do_drop(second)
    assert second not in player.items
    assert level.items[pos] is existing
    assert sum(item is second for item in level.items.values()) == 1
    assert level.item_at(*pos) is existing

    # A blocked/occupied starting tile still allows the dropped item to land
    # on a nearby free walkable tile.
    assert any(item is second for item in level.items.values())

    # Held movement waits 3 seconds after key-down, then repeats at a short
    # cadence. The ordinary key-down movement itself is handled separately.
    calls = []
    game.mode = 'play'
    game.views.mode = 'ascii'
    game._held_move = ('move_east', 0)
    game._held_move_time = game._held_move_initial_delay
    game.update_lighting = lambda *args, **kwargs: None
    game.move = lambda *args, **kwargs: calls.append(args)
    game.update(2.99)
    assert not calls
    game.update(0.02)
    assert len(calls) == 1
    game.update(0.15)
    assert len(calls) == 1
    game.update(0.02)
    assert len(calls) == 2

    for world in game.worlds.values():
        world.storage.cleanup()
pygame.quit()
print('DROP AND HELD MOVEMENT OK')
