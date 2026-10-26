import os
import sys
import tempfile
import time
from unittest.mock import patch
os.environ['SDL_VIDEODRIVER']='dummy'
os.environ['SDL_AUDIODRIVER']='dummy'
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame
from main import make_window
from game.app import Game
from game import lang, mapgen as MG
from engine.volume import cast

pygame.init()
with tempfile.TemporaryDirectory() as tmp, patch.object(lang,'SETTINGS_PATH',os.path.join(tmp,'settings.json')):
    g=Game(make_window(),seed=7)
    g.new_game()
    p=g.player
    p.x,p.y=30,20
    assert g.level.at(30,20)==MG.STAIR_UP
    assert g.use_world_stairs(1) and p.world_z==1
    assert g.use_world_stairs(-1) and p.world_z==0
    p.x,p.y=41,20
    assert g.use_world_stairs(-1) and p.world_z==-1
    assert g.use_world_stairs(1) and p.world_z==0
    assert g.level.at(45,20)==MG.FLOOR  # Bridge.
    p.x,p.y=45,15
    g.check_tile(p.x,p.y)
    assert p.world_z==-1 and g.level.at(p.x,p.y)==MG.FLOOR
    p.x,p.y=41,20
    g.use_world_stairs(1)
    def cell(x,y,z):
        lv=g.world.chunk(0,0,z)
        return (lv,x,y) if lv and lv.in_bounds(x,y) else None
    # Straight-up ray goes through open upper storey to high roof.
    roof=cast((20.5,20.5,.45),(0,0,1),cell,20)
    assert roof and abs(roof[0]-1.55)<.001
    # Straight-down ray crosses the pit and hits the basement floor.
    floor=cast((45.5,15.5,.45),(0,0,-1),cell,20)
    assert floor and abs(floor[0]-1.45)<.001
    g.views.mode='board'
    before=(p.x,p.y,p.turns)
    g.on_key(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_w,mod=0))
    assert before==(p.x,p.y,p.turns)
    g.views.mode='first'
    durations=[]
    for pitch in (-1.3,0,1.3):
        g.views.pitch=pitch
        start=time.perf_counter()
        g.draw()
        durations.append(round((time.perf_counter()-start)*1000,1))
    print('first-person draw ms:',durations)
    for quality in (0,1,2):
        g.views.quality=quality
        start=time.perf_counter()
        g.draw()
        fresh=(time.perf_counter()-start)*1000
        start=time.perf_counter()
        g.draw()
        print('quality',quality,'new/cached ms',round(fresh,1),round((time.perf_counter()-start)*1000,1))
    g.world.storage.cleanup()
pygame.quit()
print('VERTICAL OK')
