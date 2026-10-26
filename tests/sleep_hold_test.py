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
from game.entities import Actor
from game import lang

pygame.init()
with tempfile.TemporaryDirectory() as tmp, patch.object(lang,'SETTINGS_PATH',os.path.join(tmp,'settings.json')):
    g=Game(make_window(),seed=1)
    g.new_game()
    g.views.mode='ascii'
    with patch.object(g,'move') as move:
        g.key_play(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_w,mod=0))
        assert move.call_count==1
        g.update(2.9)
        assert move.call_count==1
        g.update(.11)
        assert move.call_count==2
        pygame.event.post(pygame.event.Event(pygame.KEYUP,key=pygame.K_w,mod=0))
        g.handle_events()
        g.update(.13)
        assert move.call_count==2
    g.sleep_setting=10
    g.sleep()
    assert g.mode=='sleep_slider' and not g.player.is_asleep()
    g.finish_sleep_slider(True)
    g.draw()
    assert g.r.surface.get_at((0,0))[:3]==(0,0,0)
    before=g.player.turns
    g.update(.2)
    assert g.player.turns==before+1 and g.player.status['asleep']==9
    m=Actor(g.player.x+1,g.player.y,name='hound',hp=10)
    g.level.monsters.append(m)
    g.update(.2)
    assert g.mode=='modal' and g.sleep_prompt
    cb=g.menu_cb
    g.close_modal(); cb(1)
    assert g.mode=='play' and g.player.is_asleep()
    g.update(.2)
    assert g.mode=='play'
    g.level.monsters.clear()
    for _ in range(12): g.update(.2)
    assert not g.player.is_asleep()
    g.sleep()
    g.finish_sleep_slider(False)
    assert g.mode=='play' and not g.player.is_asleep()
    g._slider_return='play'; g.mode='sleep_slider'
    bar=g.sleep_slider_rect()
    g.on_mouse(pygame.event.Event(pygame.MOUSEBUTTONDOWN,pos=(bar.right-1,bar.centery),button=1))
    assert g.sleep_setting==360
    g.draw()
    g.world.storage.cleanup()
pygame.quit()
print('SLEEP AND HOLD OK')
