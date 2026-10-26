"""Reproducible 180-step walk, chunk seams and idle comparison; isolated saves."""
import os
import sys
import time
import statistics
import tempfile
import cProfile
import pstats
from unittest.mock import patch
if '--gpu' not in sys.argv: os.environ['SDL_VIDEODRIVER']='dummy'
os.environ['SDL_AUDIODRIVER']='dummy'
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame
from main import make_window
from game.app import Game
from game import lang

pygame.init()
with tempfile.TemporaryDirectory() as tmp, patch.object(lang,'SETTINGS_PATH',os.path.join(tmp,'settings.json')):
    g=Game(make_window(),seed=47); g.new_game()
    p=g.player; p.x,p.y=4,4
    g.views.mode='first'; g.views.quality=2 if '--high' in sys.argv else 0; g.views.yaw=0
    if '--gpu' in sys.argv:
        g.resize_window(); g.display.configure((1280,720),backend='opengl')
    g.level.set_player_pos(p.x,p.y)
    profiler=cProfile.Profile()
    times=[]
    positions=[]
    if '--profile' in sys.argv: profiler.enable()
    for i in range(180):
        if '--rebuild-lamps' in sys.argv: g.world._static_light_key=None
        start=time.perf_counter(); g.move(0,-1); moved=time.perf_counter()
        g.update(.016); updated=time.perf_counter(); g.draw(); done=time.perf_counter()
        if g.display: g.display.present()
        times.append(((moved-start)*1000,(updated-moved)*1000,(done-updated)*1000))
        positions.append((p.chunk_x,p.chunk_y,p.x,p.y))
    profiler.disable()
    assert len(set(positions))==180,'Benchmark route is blocked'
    for start in (0,60,120,150):
        subset=times[start:min(start+30,180)]
        print('steps',start,'move/update/draw ms',*[round(statistics.mean(t[k] for t in subset),2) for k in range(3)],flush=True)
    start=time.perf_counter()
    for _ in range(30): g.update(.016); g.draw()
    print('idle ms',round((time.perf_counter()-start)*1000/30,2), 'world',p.chunk_x,p.x,flush=True)
    if '--profile' in sys.argv: pstats.Stats(profiler).sort_stats('cumulative').print_stats(18)
    g.world.storage.cleanup()
    if g.display: g.display.close()
pygame.quit()
