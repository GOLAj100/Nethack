import os
import sys
import tempfile
from unittest.mock import patch
os.environ['SDL_VIDEODRIVER']='dummy'; os.environ['SDL_AUDIODRIVER']='dummy'
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame
from main import make_window
from game.app import Game
from game.furniture import Furniture
from game.items import Item
from game import lang, mapgen as MG

pygame.init()
with tempfile.TemporaryDirectory() as tmp,patch.object(lang,'SETTINGS_PATH',os.path.join(tmp,'settings.json')):
    g=Game(make_window(),seed=9); g.new_game(); g.views.mode='ascii'
    p=g.player; lv=g.level
    lv.furniture=[]; lv.monsters=[]; lv.items={}; lv.tiles=[MG.FLOOR]*(lv.w*lv.h)
    p.x,p.y=5,5
    sofa=Furniture('sofa',6,5); lv.furniture.append(sofa)
    assert g.workshop.comfort()==0
    assert g.workshop.sit(lv,sofa)
    assert (p.x,p.y) in sofa.cells() and g.workshop.comfort()==2
    g.workshop.rotate(lv,sofa)
    assert not sofa.rotated
    assert g.step_to(5,5) and g.workshop.comfort()==0
    wardrobe=Furniture('wardrobe',4,5); lv.furniture.append(wardrobe)
    g._held_move=('move_west',0)
    g.step_to(4,5)
    assert g._held_move is None
    before=(p.x,p.y,p.turns)
    for _ in range(40):
        g.rotate_view(1); g.update(.2)
    assert (p.x,p.y,p.turns)==before
    box=Furniture('box',6,4,contents=[Item('apple')]); lv.furniture.append(box)
    lv.set(6,3,MG.AIR)
    lower=g.world.chunk(0,0,-1); lower.furniture=[]; lower.monsters=[]; lower.items={}
    lower.set(6,3,MG.FLOOR)
    assert g.workshop.drop_down(lv,box,0,-1)
    assert box not in lv.furniture and box in lower.furniture
    assert box.contents[0].name=='apple'
    saved=type(lv).deserialize(lower.serialize(),g.rng)
    assert saved.furniture_at(6,3).contents[0].name=='apple'
    # A removed workstation invalidates the accelerated job.
    table=Furniture('table',6,5); lv.furniture=[table]
    p.items=[Item('rag',2),Item('thread'),Item('needle')]
    g.workshop.start_job('jacket'); assert g.workshop.job['work']==2
    lv.furniture.clear(); g.workshop.update(.2)
    assert g.workshop.job is None and g.mode=='play'
    g.world.storage.cleanup()
pygame.quit()
print('FURNITURE REGRESSIONS OK')
