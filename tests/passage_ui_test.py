import os
import sys
import tempfile
from unittest.mock import patch
os.environ['SDL_VIDEODRIVER']='dummy'; os.environ['SDL_AUDIODRIVER']='dummy'
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame
from main import make_window
from game.app import Game
from game import lang

pygame.init()
with tempfile.TemporaryDirectory() as tmp,patch.object(lang,'SETTINGS_PATH',os.path.join(tmp,'settings.json')):
    g=Game(make_window(),seed=47); g.new_game()
    turns=g.player.turns
    g.on_key(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_F1,mod=0))
    assert g.mode=='modal' and g.modal_lines
    assert g.level.exits
    g.on_mouse(pygame.event.Event(pygame.MOUSEBUTTONDOWN,button=3,pos=(0,0)))
    assert g.mode=='play' and g.player.turns==turns
    g.open_settings()
    g.on_mouse(pygame.event.Event(pygame.MOUSEBUTTONDOWN,button=3,pos=(0,0)))
    assert g.mode=='play'
    pos=next(pos for pos,e in g.level.exits.items() if not e.get('requires'))
    p=g.player
    # Reachable via walkable terrain without crossing holes/furniture.
    from collections import deque
    from game import mapgen as MG
    seen={(p.x,p.y)}; q=deque(seen)
    while q:
        for n in g.level.neighbors(*q.popleft()):
            if n not in seen and g.level.is_walkable(*n) and g.level.at(*n)!=MG.AIR:
                seen.add(n); q.append(n)
    assert pos in seen
    p.x,p.y=pos
    g.interact()
    assert p.b_level==1
    for w in g.worlds.values(): w.storage.cleanup()
pygame.quit()
print('PASSAGE UI OK')
