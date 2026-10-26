import os
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch
os.environ['SDL_VIDEODRIVER']='dummy'; os.environ['SDL_AUDIODRIVER']='dummy'
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame
from main import make_window
from game.app import Game
from game import lang, mapgen as MG, ai
from game.entities import Player, Actor
from game.furniture import Furniture, FURNITURE, fill_loot, LOOT
from game.recipes import RECIPES, consume, missing
from game.items import ITEMS, Item
from game.rng import RNG

for recipe in RECIPES.values():
    assert all(name in ITEMS for name in [*recipe['materials'],*recipe['tools']])
    assert recipe.get('result') in ITEMS or recipe.get('furniture') in FURNITURE
    p=Player()
    p.items=[Item(name,count=n,rng=RNG(3)) for name,n in recipe['materials'].items()]
    p.items.extend(Item(name,rng=RNG(4)) for name in recipe['tools'])
    assert not missing(p,recipe)
    assert consume(p,recipe)
    assert sorted(it.name for it in p.items)==sorted(recipe['tools'])
for kind in LOOT:
    results=[]
    for seed in range(60):
        a,b=Furniture(kind,1,1),Furniture(kind,1,1)
        fill_loot(a,RNG(seed)); fill_loot(b,RNG(seed))
        assert a.serialize()==b.serialize()
        assert sum(it.count for it in a.contents)<=a.spec['capacity']
        results.append(tuple((it.name,it.count) for it in a.contents))
    assert () in results and len(set(results))>10

pygame.init()
with tempfile.TemporaryDirectory() as tmp,patch.object(lang,'SETTINGS_PATH',os.path.join(tmp,'settings.json')):
    g=Game(make_window(),seed=1); g.new_game()
    lv=g.level; p=g.player
    lv.furniture.clear(); lv.monsters.clear(); lv.items.clear()
    lv.tiles=[MG.FLOOR]*(lv.w*lv.h)
    for name in ('soup','spear','build_spikes','build_bed'):
        r=RECIPES[name]
        p.items=[Item(n,count=c,rng=g.rng) for n,c in r['materials'].items()]+[Item(n,rng=g.rng) for n in r['tools']]
        site=(lv,20,20) if 'furniture' in r else None
        g.workshop.start_job(name,site)
        for _ in range(50): g.workshop.update(.2)
        assert g.workshop.job is None
        if site:
            assert lv.furniture_at(20,20).kind==r['furniture']
            lv.furniture.clear()
        else: assert any(it.name==r['result'] for it in p.items)
    spikes=Furniture('spikes',10,10); lv.furniture.append(spikes)
    lv._furniture_index_size=-1
    p.x,p.y=9,10
    hp=p.hp
    g.step_to(10,10)
    assert p.hp==hp-4 and (p.x,p.y)==(10,10)
    p.x,p.y=15,10
    m=Actor(9,10,hp=10,max_hp=10)
    lv.monsters.append(m)
    assert ai._try_move(m,lv,10,10,g) and m.hp==6
    p.items=[Item('vegetable soup',count=2)]
    g.do_eat(p.items[0]); assert p.items[0].count==1
    g.world.storage.cleanup()
pygame.quit()
print('RECIPES AND LOOT OK')
