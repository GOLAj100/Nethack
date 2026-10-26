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

pygame.init()
with tempfile.TemporaryDirectory() as tmp, patch.object(lang,'SETTINGS_PATH',os.path.join(tmp,'settings.json')):
    g=Game(make_window(),seed=4)
    g.new_game(); calls=[]
    g.r.char=lambda *a,**k: calls.append('ascii')
    g.r.tile=lambda *a,**k: calls.append('tile')
    g.views.mode='ascii'; g.draw()
    assert calls and 'tile' not in calls
    g.world.storage.cleanup()
pygame.quit()
print('ASCII TILESET SEPARATION OK')
