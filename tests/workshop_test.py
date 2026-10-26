import os
import sys
import tempfile
from unittest.mock import patch
os.environ['SDL_VIDEODRIVER']='dummy'; os.environ['SDL_AUDIODRIVER']='dummy'
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame
from main import make_window
from game.app import Game
from game import lang, mapgen as MG
from game.furniture import Furniture
from game.recipes import PackingPuzzle, RECIPES, missing, skill_level
from game.items import Item

pygame.init()
with tempfile.TemporaryDirectory() as tmp, patch.object(lang,'SETTINGS_PATH',os.path.join(tmp,'settings.json')):
    g=Game(make_window(),seed=7); g.new_game(); g.level.furniture=[]
    obj=Furniture('box',g.player.x+1,g.player.y)
    assert g.level.is_walkable(obj.x,obj.y)
    g.level.furniture.append(obj)
    assert g.level.furniture_at(obj.x,obj.y) is obj and not g.level.is_walkable(obj.x,obj.y)
    g.player.items.append(Item('rag',count=2)); g.player.items.append(Item('thread')); g.player.items.append(Item('needle'))
    assert not missing(g.player,RECIPES['jacket'])
    puzzle=PackingPuzzle()
    for i,(x,y) in enumerate(((0,0),(0,1),(0,2),(2,2),(4,2),(2,5))):
        assert puzzle.place(i,x,y,0)
    assert puzzle.complete
    before=g.player.turns
    g.workshop.start_job('jacket')
    for _ in range(25):
        g.workshop.update(.2)
    assert g.mode=='play' and g.player.turns>before
    assert any(it.name=='crafted jacket' for it in g.player.items)
    assert any(it.name=='needle' for it in g.player.items)
    assert not any(it.name=='rag' for it in g.player.items)
    assert g.player.skills['crafting']==25
    obj.contents=[Item('apple')]
    g.workshop.pack(g.level,obj)
    assert obj not in g.level.furniture and g.player.carried_furniture
    packed=Furniture.deserialize(g.player.carried_furniture[0])
    assert packed.contents[0].name=='apple'
    g.level.furniture.append(packed)
    g.player.skills['building']=300
    assert skill_level(g.player,'building')==3
    for name,count in (('wood plank',3),('nails',4),('war hammer',1)):
        g.player.items.append(Item(name,count=count))
    x,y=g.player.x,g.player.y+1
    g.level.set(x,y,MG.FLOOR)
    g.level.items.pop((x,y),None)
    g.workshop.start_puzzle('barricade',g.level,x,y)
    turns=g.player.turns
    g.workshop.draw()
    assert g.player.turns==turns
    g.workshop.confirm_puzzle(True)
    assert g.mode=='work'
    g.workshop.cancel_job()
    assert not missing(g.player,RECIPES['barricade'])
    g.workshop.start_job('barricade',(g.level,x,y))
    for _ in range(20): g.workshop.update(.2)
    assert g.level.furniture_at(x,y).kind=='barricade'
    assert not g.level.can_see_through(x,y)
    assert any(it.name=='war hammer' for it in g.player.items)
    data=g.level.serialize(); restored=type(g.level).deserialize(data,g.rng)
    assert restored.furniture[0].kind=='box' and restored.furniture[0].contents[0].name=='apple'
    g.world.storage.cleanup()
pygame.quit()
print('WORKSHOP OK')
