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
from game import lang, survival, mapgen as MG
from game.entities import Player

p=Player()
for i in range(700):
    p.turns+=1; survival.advance_sanity(p)
assert p.sanity==48 and p.awake_turns==700
for _ in range(10): survival.advance_sanity(p,sleeping=True)
assert p.sanity==50 and p.awake_turns==600
q=Player(); q.load_dict(p.to_dict())
assert q.awake_turns==p.awake_turns
pygame.init()
with tempfile.TemporaryDirectory() as tmp, patch.object(lang,'SETTINGS_PATH',os.path.join(tmp,'settings.json')):
    g=Game(make_window(),seed=3); g.new_game(); p=g.player
    p.x,p.y=20,20
    lower=g.level; upper=g.world.chunk(0,0,1)
    for lv in (lower,upper):
        lv.monsters.clear(); lv.light_sources.clear()
    lower.set(20,20,MG.FLOOR); lower.set(21,20,MG.FLOOR)
    upper.set(20,20,MG.AIR); upper.set(21,20,MG.FLOOR)
    for pos in ((20,19),(19,20),(20,21)): upper.set(*pos,MG.AIR)
    g.update_lighting()
    assert upper.light_grid[20][20]>.8
    upper.set(20,20,MG.FLOOR); g.update_lighting()
    assert not g.climb()
    upper.set(20,20,MG.AIR)
    with patch.object(g.rng,'random',return_value=.9),patch.object(g.rng,'dice',return_value=3):
        hp=p.hp; turns=p.turns
        assert g.climb() and p.world_z==0 and p.hp==hp-3 and p.turns==turns+1
    with patch.object(g.rng,'random',return_value=.1):
        assert g.climb() and (p.world_z,p.x,p.y)==(1,21,20)
    g.world.storage.cleanup()
pygame.quit()
print('CLIMB SANITY OK')
