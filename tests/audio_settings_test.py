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
    g=Game(make_window(),seed=3)
    g.new_game()
    turns=g.player.turns
    g.open_settings()
    g.menu.index=2
    g.key_modal(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_RETURN,mod=0))
    assert g.mode=='audio_settings'
    assert len(g.audio_settings.fields)==6
    for i,field in enumerate(g.audio_settings.fields):
        bar=g.audio_settings.bar(i)
        g.on_mouse(pygame.event.Event(pygame.MOUSEBUTTONDOWN,pos=(bar.x,bar.centery),button=1))
        assert getattr(g.audio,field)==0
        g.on_mouse(pygame.event.Event(pygame.MOUSEMOTION,pos=(bar.right,bar.centery),buttons=(1,0,0)))
        assert getattr(g.audio,field)==1
        g.on_mouse(pygame.event.Event(pygame.MOUSEBUTTONUP,pos=(bar.right,bar.centery),button=1))
        assert g.audio_settings.drag is None
    g.audio_settings.selected=1
    g.on_key(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_LEFT,mod=0))
    assert g.audio.music_volume==.95
    g.draw()
    assert g.player.turns==turns
    data=lang.load_settings(g)
    assert data['music_volume']==.95 and data['environment_volume']==1
    g.on_key(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_ESCAPE,mod=0))
    assert g.mode=='modal'
    g.close_modal()
    assert g.mode=='play'
    g.world.storage.cleanup()
pygame.quit()
print('AUDIO SETTINGS OK')
