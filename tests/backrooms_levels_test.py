"""Main Nine: reachable exits, distinct deterministic layouts, travel/save/darkness."""
import os
import sys
import tempfile
from collections import deque
from unittest.mock import patch

os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from game.world import World
from game import mapgen as MG, lang
from game.save import save_game, load_game
from game.items import Item
from game.entities import Player


def reachable(lv):
    seen = {(4,4)}
    queue = deque(seen)
    while queue:
        for pos in lv.neighbors(*queue.popleft()):
            if pos not in seen and lv.is_walkable(*pos) and lv.at(*pos)!=MG.AIR:
                seen.add(pos)
                queue.append(pos)
    return seen


for seed in (1,42,919):
    signatures = set()
    for number in range(21):
        world = World(seed,number)
        for cx,cy in ((0,0),(-1,2),(3,-2)):
            lv = world.chunk(cx,cy,visit=True)
            seen = reachable(lv)
            assert set(lv.exits) <= seen, (number,cx,cy)
            assert all(lv.at(*pos)==MG.STAIR_UP for pos in lv.exits)
            assert all(pos not in lv.hazards and not lv.furniture_at(*pos) for pos in lv.exits)
            if number<20:
                assert any(e['target']==number+1 and e['method']=='passage' for e in lv.exits.values())
            else:
                assert not lv.exits
            for edge in ((0,lv.h//2),(lv.w-1,lv.h//2),(lv.w//2,0),(lv.w//2,lv.h-1)):
                assert edge in seen,(number,edge)
            if cx==cy==0:
                signatures.add(tuple(lv.tiles))
        clone = World(seed,number)
        assert clone.chunk(0,0).tiles==world.chunk(0,0).tiles
        if number==6:
            assert world.chunk(0,0,0).at(4,4)==MG.STAIR_DOWN
            assert world.chunk(0,0,-1).at(4,4)==MG.STAIR_UP
            assert not world.chunk(0,0,-1).light_sources
        clone.storage.cleanup()
        world.storage.cleanup()
    # The lore mapping intentionally reuses compatible architectural families
    # (hospital/asylum and hotel/well/inn), while still keeping deterministic
    # profiles and separate gameplay rules.
    assert len(signatures)>=15

# Migration of a pre-stage world does not regenerate or erase edited tiles.
old = World(91)
old.chunk(0,0,visit=True).set(6,4,MG.RUBBLE)
data = old.serialize()
data['profile'].pop('next_level')
data['profile']['exits'] = False
for chunk in data['chunks'].values():
    chunk.pop('exits',None)
migrated = World.deserialize(data)
assert migrated.chunk(0,0).at(6,4)==MG.RUBBLE
assert migrated.chunk(0,0).exits
old.storage.cleanup()
migrated.storage.cleanup()

import pygame
from main import make_window
from game.app import Game
pygame.init()
with tempfile.TemporaryDirectory() as tmp, patch.object(lang,'SETTINGS_PATH',os.path.join(tmp,'settings.json')):
    g = Game(make_window(),seed=902)
    g.new_game()
    p = g.player
    guide = next(it for it in g.level.items.values() if it.name=='noclip guide')
    p.items.append(guide)
    for number in range(20):
        assert p.b_level==number
        g.level.set(6,4,MG.RUBBLE)
        # Exercise the actual Enter interaction, not only the travel API.
        p.x,p.y = next(pos for pos,e in g.level.exits.items() if e['method']=='passage')
        before = p.turns
        g.interact()
        assert p.b_level==number+1 and p.depth==number+1
        assert p.turns==before+1
    assert not g.travel_to_level(21) and p.b_level==20
    assert g.travel_to_level(6) and p.b_level==6
    p.x,p.y = 4,4
    assert g.use_world_stairs(-1) and p.b_level==6 and p.world_z==-1
    assert g.use_world_stairs(1) and p.world_z==0
    # Portable lights cannot illuminate Level 6; visibility stays tactile.
    p.items.append(Item('lantern',rng=g.rng))
    g.world.update_lighting(p,True,1)
    assert all(value==0 for column in g.level.light_grid for value in column)
    cells = g.world.view_cells(p)
    assert all(abs(x-p.x)<=1 and abs(y-p.y)<=1 for x,y in cells)
    for mode in ('first','board','ascii'):
        g.views.mode = mode
        g.views.full_map = True
        g.views.lighting = False
        g.draw()
    assert g.travel_to_level(1)
    p.x,p.y = next(pos for pos,e in g.level.exits.items() if e['method']=='noclip')
    before = p.turns
    g.interact()
    assert p.b_level==1 and p.turns==before
    g.do_read(guide)
    assert 'noclip' in p.knowledge
    g.interact()
    assert p.b_level==4
    path = os.path.join(tmp,'main-nine.json')
    assert save_game(path,g)
    assert load_game(path,g)
    assert g.player.b_level==4 and 'noclip' in g.player.knowledge
    assert set(g.worlds)==set(range(21))
    for number in range(20):
        assert g.worlds[number].chunk(0,0).at(6,4)==MG.RUBBLE
    for world in g.worlds.values():
        world.storage.cleanup()
pygame.quit()
print('BACKROOMS LEVELS OK')
