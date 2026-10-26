"""Lighting, vertical camera, draw distance and debug movement checks."""
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
from game.items import Item

pygame.init()
with tempfile.TemporaryDirectory() as tmp, patch.object(lang, 'SETTINGS_PATH', os.path.join(tmp, 's.json')):
    g = Game(make_window(), seed=10)
    g.new_game()
    p = g.player
    assert hasattr(g, 'alt_camera')
    assert g.views.draw_distance == 52
    g.views.mode = 'first'
    g.draw()
    g.views.pitch = 0.8
    g.draw()
    g.views.pitch = -0.8
    g.draw()
    g.views.show_ceiling = False
    g.draw()
    assert g.level.ceiling_lamps <= set(g.level.light_sources)
    p.items.append(Item('lantern'))
    g.toggle_lights()
    assert p.turns == 0
    p.equip(p.items[-1])
    g.toggle_lights()
    assert p.turns == 1
    p.debug_fly = True
    above = g.world.chunk(p.chunk_x,p.chunk_y,1)
    above.set(p.x,p.y,MG.FLOOR)
    assert g.debug_change_z(1) is True
    assert g.debug_change_z(1) is False  # Upper bound of the test structure.
    p.debug_noclip = True
    g.level.set(p.x + 1, p.y, MG.WALL)
    before = p.x
    g.step_to(p.x + 1, p.y)
    assert p.x == before + 1
    g.open_debug()
    assert len(g.menu.entries) == 14
    g.world.storage.cleanup()
pygame.quit()
print('GRAPHICS DEBUG OK')
