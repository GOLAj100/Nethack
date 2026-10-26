"""Streaming generation, seams, persistence and render bounds."""
import os
import sys
import tempfile
from unittest.mock import patch
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from game.world import CHUNK_CACHE, World
from game import mapgen as MG
from game import lang
from game.save import save_game, load_game
import pygame
from main import make_window
from game.app import Game

world = World(42)
first = world.chunk(0, 0, visit=True)
assert len(first.tiles) == 4000 and MG.AIR in first.tiles
assert not first.falls and not first.monsters
assert first.at(first.w - 1, first.h // 2) == MG.FLOOR
assert world.chunk(1, 0).at(0, first.h // 2) == MG.FLOOR
for cx,cy in ((-1,0),(0,-1),(1,0),(0,1),(12,-20)):
    lv = world.chunk(cx,cy)
    assert set(lv.tiles) <= {MG.WALL,MG.FLOOR,MG.AIR,MG.STAIR_DOWN,MG.STAIR_UP}
    seen = MG._flood(lv.w,lv.h,lv.at,*lv.rooms[0].center())
    floors = {(x,y) for y in range(lv.h) for x in range(lv.w) if lv.at(x,y)!=MG.WALL}
    assert seen == floors
assert len(world.chunks) <= CHUNK_CACHE
assert world.visible_z(0)==[-1,0,1] and not world.exists(2)
first.set(4,4,MG.RUBBLE)
for i in range(10):
    world.chunk(i+1,0,visit=True)
assert world.chunk(0,0,visit=True).at(4,4)==MG.RUBBLE
clone = World.deserialize(world.serialize())
assert clone.chunk(0,0).at(4,4)==MG.RUBBLE
profile = dict(world.profile, z_min=None, z_max=None)
unlimited = World(42,profile=profile)
assert unlimited.visible_z(100)==[98,99,100,101,102]
pygame.init()
with tempfile.TemporaryDirectory() as tmp, patch.object(lang,'SETTINGS_PATH',os.path.join(tmp,'settings.json')):
    g = Game(make_window(),seed=99)
    g.new_game()
    p=g.player
    g.level.monsters.clear()
    p.x,p.y=79,4
    g.step_to(80,4)
    assert p.chunk_x==1 and p.x==0 and p.b_level==0
    g.level.monsters.clear()
    g.step_to(-1,4)
    assert p.chunk_x==0 and p.x==79
    p.x,p.y=0,4
    g.step_to(-1,4)
    assert p.chunk_x==-1 and p.x==79
    g.views.mode='board'
    g.views.free_camera=True
    g.views.world_camera=[100,-100,0]
    g.draw()
    before=(p.chunk_x,p.chunk_y,p.x,p.y,p.turns)
    g.draw()
    assert before==(p.chunk_x,p.chunk_y,p.x,p.y,p.turns)
    # First-person DDA must resolve beyond the active chunk seam instead of
    # painting the seam itself as a fake brown wall.
    g.views.mode = 'first'
    p.chunk_x, p.chunk_y, p.x, p.y = 0, 0, 79, 25
    g.level = g.world.chunk(0, 0, 0, visit=True)
    g.level.set_player_pos(p.x, p.y)
    g.draw()
    assert any(x >= 80 for x,y in g.visible_world)
    path=os.path.join(tmp,'slot.json')
    assert save_game(path,g) and load_game(path,g)
    assert p.chunk_x==g.player.chunk_x and g.level.b_level==0
    for obj in (g.world,world,clone,unlimited):
        obj.storage.cleanup()
pygame.quit()
print('WORLD OK')
