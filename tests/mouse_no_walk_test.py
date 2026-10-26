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
from engine import config as C

pygame.init()
with tempfile.TemporaryDirectory() as tmp,patch.object(lang,'SETTINGS_PATH',os.path.join(tmp,'settings.json')):
    g=Game(make_window(),seed=4); g.new_game()
    pos=(20*g.r.cw,15*g.r.ch)
    before=g.player.to_dict()
    with patch.object(g,'click_map') as walk:
        for mode in ('ascii','first','board'):
            g.views.mode=mode
            for button in (1,2,4,5):
                g.on_mouse(pygame.event.Event(pygame.MOUSEBUTTONDOWN,pos=pos,button=button))
            for _ in range(12):
                g.on_mouse(pygame.event.Event(pygame.MOUSEWHEEL,x=0,y=1))
        walk.assert_not_called()
    assert g.player.to_dict()==before
    g.views.mode='ascii'
    g.open_settings()
    with patch.object(g.menu,'handle_click',return_value=None) as menu:
        g.on_mouse(pygame.event.Event(pygame.MOUSEBUTTONDOWN,pos=pos,button=1))
        menu.assert_called_once()
    g.close_modal()
    g.start_target('throw')
    g.on_mouse(pygame.event.Event(pygame.MOUSEBUTTONDOWN,pos=pos,button=1))
    assert g.target_pos==g.screen_to_world(20,15-g.map_offset_y)
    g.world.storage.cleanup()
pygame.quit()
print('MOUSE NO WALK OK')
