import os
import sys
from types import SimpleNamespace
from unittest.mock import patch
os.environ['SDL_AUDIODRIVER']='dummy'
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame
from game.audio import Audio

pygame.init()
a=Audio()
assert a.init()
assert a.playlists['title'] and a.playlists['stranger']
for mood,tracks in a.playlists.items():
    for track in tracks:
        pygame.mixer.music.load(track)
    if tracks:
        a.play_music(mood)
        assert a.current_music_key==mood
print('Decoded tracks:',sum(map(len,a.playlists.values())),'MP4 not prepared:',len(a.skipped_tracks))
a.toggle_mute()
assert a.muted
a.toggle_mute()
a.stop_music()
p=SimpleNamespace(alive=True,sanity=50,hp=27,max_hp=27,b_level=0)
lv=SimpleNamespace(profile={'music_mood':'snow'},monsters=[],visible=set())
g=SimpleNamespace(player=p,level=lv,mode='play',visible_world={})
a._mood_since=-100
with patch.object(a,'play_music') as play:
    a.update_context(g); play.assert_called_with('snow')
    p.sanity=0
    a.update_context(g); play.assert_called_with('madness')
    g.mode='title'
    a.update_context(g); play.assert_called_with('title')
snd=a.sounds['step'][0]
volume=snd.get_volume()
for _ in range(3):
    a._last_sound.clear(); a.play('step',.2)
assert snd.get_volume()==volume
a.stop_music()
pygame.quit()
print('AUDIO MUSIC OK')
