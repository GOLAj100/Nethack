"""Fog/cache regressions and rotating camera timings (no user save writes)."""
import os
import sys
import time
import tempfile
from unittest.mock import patch
os.environ['SDL_VIDEODRIVER']='dummy'
os.environ['SDL_AUDIODRIVER']='dummy'
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame
from main import make_window
from game.app import Game
from game import lang

pygame.init()
with tempfile.TemporaryDirectory() as tmp, patch.object(lang,'SETTINGS_PATH',os.path.join(tmp,'settings.json')):
    g=Game(make_window(),seed=47)
    g.new_game()
    v=g.views
    assert not v.full_map and not v.outlines and v.single_layer
    v.mode='board'
    g.draw()
    before=v._world_board_key
    g.level.explored.add((70,40))
    g.draw()
    assert v._world_board_key != before
    assert all(pos in g.level.explored|g.level.mapped for _,pos in v.board_polygons)
    v.single_layer=False
    lang.save_settings(g)
    v.single_layer=True
    lang.load_settings(g)
    assert not v.single_layer and not v.full_map
    for full in (False,True):
        for single in (True,False):
            for outlines in (False,True):
                v.full_map,v.single_layer,v.outlines=full,single,outlines
                start=time.perf_counter()
                for _ in range(5):
                    v.orbit+=.04
                    g.draw()
                print('board full/single/lines',full,single,outlines,
                      'ms',round((time.perf_counter()-start)*200,1))
    v.mode='first'
    for position in ((5,5),(79,49)):
        g.player.x,g.player.y=position
        g.level.set(*position,1)
        g.update_lighting()
        for quality in (0,1,2):
            v.quality=quality
            start=time.perf_counter()
            for _ in range(5):
                v.yaw+=.1
                v.pitch+=.03
                g.draw()
            print('first position/quality',position,quality,'ms',round((time.perf_counter()-start)*200,1))
    g.world.storage.cleanup()
pygame.quit()
print('RENDER OPTIONS OK')
