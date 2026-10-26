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
from game import lang
from game.entities import Actor
from game.items import Item

pygame.init()
with tempfile.TemporaryDirectory() as tmp, patch.object(lang,'SETTINGS_PATH',os.path.join(tmp,'settings.json')):
    g=Game(make_window(),seed=44)
    g.new_game()
    p=g.player
    p.x,p.y=79,25
    a=g.level
    b=g.world.chunk(1,0)
    for lv in (a,b):
        lv.tiles=[0]*(lv.w*lv.h)
        lv.monsters.clear()
        lv.items.clear()
        lv.explored.clear()
        lv.mapped.clear()
        for x in range(lv.w):
            lv.set(x,25,1)
    b.set(5,25,0)
    b.monsters.append(Actor(2,25,glyph='k',hp=10))
    b.items[1,25]=Item('apple')
    b.items[6,25]=Item('apple')
    g.views.mode='first'
    g.views.yaw=0
    g.draw()
    assert (81,25) in g.visible_world and (82,25) in g.visible_world
    assert (86,25) not in g.visible_world
    assert any(pos==(81,25) for _,pos in g.views.picks)
    assert any(pos==(82,25) for _,pos in g.views.picks)
    assert not any(pos==(86,25) for _,pos in g.views.picks)
    g.views.mode='ascii'
    with patch.object(g.r,'char',wraps=g.r.char) as tile:
        g.draw()
        assert any(call.args[2]=='k' for call in tile.call_args_list)
    g.cross_chunk(80,25)
    g.draw()
    assert (1,25) in g.visible_world
    assert (6,25) not in g.visible_world
    g.world.storage.cleanup()
pygame.quit()
print('SEAM VISIBILITY OK')
