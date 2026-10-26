"""Regression for GPU material refresh after crossing a chunk seam."""
import os
import sys
import tempfile
from unittest.mock import patch
os.environ['SDL_VIDEODRIVER']='dummy'
os.environ['SDL_AUDIODRIVER']='dummy'
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame
from main import make_window
from game.app import Game
from game import lang, mapgen as MG

pygame.init()
with tempfile.TemporaryDirectory() as tmp, patch.object(lang,'SETTINGS_PATH',os.path.join(tmp,'settings.json')):
    g=Game(make_window(),seed=51)
    g.new_game()
    p=g.player
    a=g.level
    b=g.world.chunk(1,0)
    for lv in (a,b):
        lv.tiles=[MG.FLOOR]*(lv.w*lv.h)
        lv.light_sources.clear()
    p.x,p.y=79,25
    g.update_lighting()
    rev_a,rev_b=a.lighting_revision,b.lighting_revision
    # The neighboring chunk must receive player light before the first GPU draw.
    assert b.light_grid[0][25] > .8
    assert rev_b > 0
    g.cross_chunk(80,25)
    g.update_lighting()
    assert g.level is b
    assert b.light_grid[0][25] > .8
    assert b.lighting_revision >= rev_b
    # A lamp/flicker update must invalidate GPU material data as well.
    b.light_sources=[(10,25)]
    for room in b.rooms:
        room.lit=True
    g.lamp_flicker_modifier=1.0
    g.update_lighting()
    old=b.lighting_revision
    g.lamp_flicker_modifier=.1
    g.update_lighting()
    assert b.lighting_revision > old
    g.world.storage.cleanup()
pygame.quit()
print('GPU LIGHT BOUNDARY OK')
