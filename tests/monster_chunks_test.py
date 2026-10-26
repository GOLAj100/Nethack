"""Regression checks for monster turns and navigation across chunk seams."""
import os
import sys
import tempfile
from unittest.mock import patch

os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
from main import make_window
from game.app import Game
from game import lang, mapgen as MG
from game.entities import Actor
from game.world import World


def prepare(g, cx, cy, x, y):
    g.world.storage.cleanup()
    g.world = World(44)
    p = g.player
    p.chunk_x, p.chunk_y, p.world_z = cx, cy, 0
    p.x, p.y = x, y
    p.hp = p.max_hp
    g.level = g.world.chunk(cx, cy, 0, visit=True)
    # All chunks that the bounded turn simulation can use, with unexplored floors.
    px, py = cx*g.world.w+x, cy*g.world.h+y
    for yy in range((py-18)//g.world.h, (py+18)//g.world.h+1):
        for xx in range((px-18)//g.world.w, (px+18)//g.world.w+1):
            lv = g.world.chunk(xx, yy)
            lv.tiles = [MG.FLOOR] * (lv.w*lv.h)
            lv.doors.clear()
            lv.monsters.clear()
            lv.explored.clear()
            lv.mapped.clear()


def monster(lv, x, y, speed=100):
    m = Actor(x, y, name='test entity', hp=10, max_hp=10, speed=speed)
    m.awake = True
    m.hostile = True
    lv.monsters.append(m)
    return m


pygame.init()
with tempfile.TemporaryDirectory() as tmp, patch.object(
        lang, 'SETTINGS_PATH', os.path.join(tmp, 'settings.json')):
    g = Game(make_window(), seed=44)
    g.new_game()
    # Pursue in all four directions, including negative chunk coordinates.
    for cx, cy, px, py, sx, sy, mx, my, expected in (
            (1, 0, 3, 25, 0, 0, 79, 25, (0, 25)),
            (-1, 0, 76, 25, 0, 0, 0, 25, (79, 25)),
            (0, 1, 40, 3, 0, 0, 40, 49, (40, 0)),
            (0, -1, 40, 46, 0, 0, 40, 0, (40, 49))):
        prepare(g, cx, cy, px, py)
        source = g.world.chunk(sx, sy)
        m = monster(source, mx, my)
        g.monster_turn()
        assert m not in source.monsters and m in g.level.monsters
        assert (m.x, m.y) == expected
        assert g.world.active_key == (cx, cy, 0)
        assert sum(m in lv.monsters for lv in g.world.chunks.values()) == 1

    # Player crossing must leave the pursuer active in the old chunk.
    prepare(g, 0, 0, 79, 25)
    source = g.level
    m = monster(source, 77, 25)
    g.cross_chunk(80, 25)
    assert (m.x, m.y) == (78, 25)
    g.player.x = 3
    g.monster_turn()
    g.monster_turn()
    assert m in g.level.monsters and (m.x, m.y) == (0, 25)

    # A fast monster continues its second step from its new owning chunk.
    prepare(g, 1, 0, 4, 25)
    source = g.world.chunk(0, 0)
    m = monster(source, 79, 25, speed=120)
    with patch.object(g.rng, 'random', return_value=0):
        g.monster_turn()
    assert m in g.level.monsters and (m.x, m.y) == (1, 25)

    # Reject walls, occupied cells, closed doors and the player's own cell.
    prepare(g, 1, 0, 3, 25)
    source = g.world.chunk(0, 0)
    m = monster(source, 79, 25)
    g.level.set(0, 25, MG.WALL)
    assert not g.move_monster_cross_chunk(m, 80, 25, source)
    g.level.set(0, 25, MG.FLOOR)
    blocker = monster(g.level, 0, 25)
    assert not g.move_monster_cross_chunk(m, 80, 25, source)
    g.level.monsters.remove(blocker)
    g.level.set(0, 25, MG.DOOR)
    g.level.doors[0, 25] = {'open': False}
    assert not g.move_monster_cross_chunk(m, 80, 25, source)
    # The AI can open a door across the seam and then transfer.
    with patch('game.ai.random.random', return_value=0):
        g.monster_turn()
    assert m in g.level.monsters and g.level.doors[0, 25]['open']
    prepare(g, 1, 0, 0, 25)
    source = g.world.chunk(0, 0)
    m = monster(source, 79, 25)
    assert not g.move_monster_cross_chunk(m, 80, 25, source)
    with patch('game.ai.combat.attack', return_value=('hit', (255, 0, 0), 'hurt')) as attack:
        g.monster_turn()
        assert attack.call_count == 1
    assert m in source.monsters

    # Fleeing can also cross a seam without changing the active player chunk.
    prepare(g, 0, 0, 77, 25)
    source = g.level
    m = monster(source, 79, 25)
    m.status['flee'] = 3
    g.monster_turn()
    target = g.world.chunk(1, 0)
    assert m in target.monsters and (m.x, m.y) == (0, 25)
    assert g.world.active_key == (0, 0, 0)
    clone = World.deserialize(g.world.serialize())
    assert not clone.chunk(0, 0).monsters
    assert clone.chunk(1, 0).monster_at(0, 25) is not None
    clone.storage.cleanup()
    g.world.storage.cleanup()
pygame.quit()
print('MONSTER CHUNKS OK')
