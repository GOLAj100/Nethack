"""Real OpenGL colour parity across a seam; isolated settings, no dummy SDL."""
import os
import sys
import tempfile
from unittest.mock import patch
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame
from main import make_window
from game.app import Game
from game import lang, mapgen as MG
from engine.gpu_rays import GPURays

pygame.init()
with tempfile.TemporaryDirectory() as tmp, patch.object(lang,'SETTINGS_PATH',os.path.join(tmp,'settings.json')):
    g=Game(make_window(),seed=51)
    g.new_game()
    g.resize_window()
    g.display.configure((640,480),backend='opengl')
    assert g.display.backend=='opengl',g.display.error
    g.display.rays=rays=GPURays(g.display.gl)
    a=g.level
    b=g.world.chunk(1,0)
    for lv in (a,b):
        lv.tiles=[MG.FLOOR]*(lv.w*lv.h)
        lv.light_sources=[]
    b.set(2,25,MG.WALL)
    g.world.visited.add((1,0,0))
    g.player.x,g.player.y=79,25
    g.views.fog=False
    for modifier in (1.0,.1):
        g.lamp_flicker_modifier=modifier
        g.update_lighting()
        b=g.world.chunk(1,0)
        for strength in (.9,.2):
            b.light_grid[2][25]=strength
            b.lighting_revision+=1
            image,depth,hits=rays.render(g.views,g,1,1,(79.5,25.5,.45),(1,0,0),(0,0,0),(0,0,0))
            _,base=g.tile_glyph(b,MG.WALL,2,25,0,False)
            expected=g.views.color(base,depth[0],1,strength)
            actual=image.get_at((0,0))[:3]
            assert all(abs(x-y)<=2 for x,y in zip(expected,actual)),(expected,actual)
            assert hits[0]==(82,25)
    g.display.close()
    g.world.storage.cleanup()
pygame.quit()
print('REAL GPU LIGHT PARITY OK')
