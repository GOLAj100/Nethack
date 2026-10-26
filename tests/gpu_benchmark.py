"""Real GPU benchmark (requires desktop OpenGL, not SDL dummy)."""
import os
import sys
import tempfile
import time
from unittest.mock import patch
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame
from main import make_window
from game.app import Game
from game import lang

pygame.init()
with tempfile.TemporaryDirectory() as tmp, patch.object(lang,'SETTINGS_PATH',os.path.join(tmp,'settings.json')):
    g=Game(make_window(),seed=47)
    g.new_game()
    g.resize_window()
    g.views.mode='first'
    g.views.quality=2
    for backend in ('software','opengl'):
        g.display.configure((1280,720),backend=backend)
        print('Backend:',g.display.backend,g.display.gpu_name,flush=True)
        for _ in range(2):
            g.update(.016); g.views.turn(.03); g.draw(); g.display.present()
        start=time.perf_counter()
        for _ in range(20):
            g.update(.016); g.views.turn(.03); g.draw(); g.display.present()
        ms=(time.perf_counter()-start)*50
        print('update/draw/present ms',round(ms,2),'fps',round(1000/ms,1),'error',g.display.ray_error,flush=True)
        if backend=='opengl':
            assert g.display.backend=='opengl'
            assert not g.display.ray_error,g.display.ray_error
            from engine.volume import cast
            rays=g.display.rays
            def cell(x,y,z):
                if not g.world.exists(z): return None
                cx,lx=divmod(x,g.world.w); cy,ly=divmod(y,g.world.h)
                lv=g.world.chunk(cx,cy,z)
                return lv,lx,ly
            for direction in ((1,0,0),(0,1,0),(0,0,1),(0,0,-1)):
                origin=(g.player.x+.5,g.player.y+.5,g.player.world_z+.45)
                _,depths,_=rays.render(g.views,g,1,1,origin,direction,(0,0,0),(0,0,0))
                expected=cast(origin,direction,cell,32)
                assert (depths[0]>=1e5 if expected is None else abs(depths[0]-expected[0])<.001),(depths,expected)
            print('GPU/CPU cardinal ray depths match',flush=True)
        g.views.mode='ascii'
        start=time.perf_counter()
        for _ in range(30):
            g.update(.016); g.draw(); g.display.present()
        ms=(time.perf_counter()-start)*1000/30
        print('ASCII ms',round(ms,2),'fps',round(1000/ms,1),flush=True)
        g.views.mode='first'
        g.views.mode='board'
        g.views.full_map=True
        g.views.single_layer=False
        g.views.outlines=True
        g.draw(); g.display.present()
        start=time.perf_counter()
        for _ in range(20):
            g.views.orbit+=.03; g.draw(); g.display.present()
        ms=(time.perf_counter()-start)*50
        print('board volume+outlines ms',round(ms,2),'fps',round(1000/ms,1),'error',g.display.board_error,flush=True)
        if backend=='opengl': assert not g.display.board_error,g.display.board_error
        g.views.mode='first'
    g.world.storage.cleanup()
    g.display.close()
pygame.quit()
