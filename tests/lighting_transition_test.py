"""Regression: room persistence, seam lighting and safe Z travel."""
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
from game.world import World
from game.level import Level
from game import lang, mapgen as MG

pygame.init()
with tempfile.TemporaryDirectory() as tmp, patch.object(lang, 'SETTINGS_PATH', os.path.join(tmp,'settings.json')):
    g = Game(make_window(), seed=47)
    g.new_game()
    p = g.player
    p.x,p.y = 79,25
    a = g.level
    b = g.world.chunk(1,0)
    for lv in (a,b):
        lv.tiles = [MG.FLOOR]*(lv.w*lv.h)
        lv.monsters.clear()
        lv.light_sources.clear()
    g.update_lighting()
    assert b.light_grid[0][25] > .8
    before = b.light_grid[2][25]
    b.set(0,25,MG.WALL)
    g.update_lighting()
    assert b.light_grid[0][25] > .8
    assert b.light_grid[2][25] < before
    b.set(0,25,MG.FLOOR)
    a.light_sources = [(78,20)]
    for r in a.rooms:
        r.lit = True
    restored = Level.deserialize(a.serialize(), a.rng)
    assert all(r.lit for r in restored.rooms)
    assert restored.light_sources == a.light_sources
    g.lamp_flicker_modifier = 1
    g.update_lighting()
    light = b.light_grid[1][20]
    g.lamp_flicker_modifier = .1
    g.update_lighting()
    assert b.light_grid[1][20] < light
    g.world.profile['z_max'] = 1
    p.debug_fly = True
    p.debug_noclip = False
    above = g.world.chunk(0,0,1)
    above.set(p.x,p.y,MG.WALL)
    assert not g.debug_change_z(1)
    assert p.world_z == 0 and g.level is a
    above.set(p.x,p.y,MG.FLOOR)
    assert g.debug_change_z(1)
    assert p.world_z == 1 and g.level is above
    assert above.light_grid[p.x][p.y] == 1
    assert g.debug_change_z(-1)
    g.world.storage.cleanup()
pygame.quit()
print('LIGHTING TRANSITIONS OK')
