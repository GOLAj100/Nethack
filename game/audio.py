"""Звук: маппинг игровых событий на файлы из папки sound/."""

from __future__ import annotations

import os
import random
import time
import math
from array import array

import pygame

from engine import config as C

# event -> список кандидатов (путь относительно sound/, индекс файла)
SOUND_MAP: dict[str, list[tuple[str, int]]] = {
    "sleep_alarm": [("FX", 11), ("FX", 37)],
    "hit":        [("KICK", 2), ("BASS SHOT", 1), ("PERC/CONGA", 2)],
    "hit_weak":   [("SNARE", 28), ("BASS SHOT", 10), ("KICK", 24)],
    "miss":       [("PERC/SHAKER", 1), ("FX", 17), ("CYMBALL/OPEN HAT", 1)],
    "crit":       [("KICK", 37), ("FX", 44), ("SNARE", 3)],
    "kill":       [("SNARE", 3), ("PERC/CONGA", 1), ("CYMBALL/CRASH", 1)],
    "player_hurt":[("KICK", 2), ("SNARE", 1), ("BASS", 19)],
    "player_die": [("FX", 11), ("SNARE", 4), ("FX", 37)],
    "monster_hurt":[("SNARE", 6), ("BASS", 18), ("PERC/PERC", 4)],
    "step":       [("CYMBALL/OPEN HAT", 1), ("PERC/SHAKER", 4)],
    "door":       [("PERC/SHAKER", 2), ("FX", 8), ("CLAP", 6)],
    "door_bump":  [("FX", 6), ("BASS", 18)],
    "pickup":     [("COWBELL", 1), ("COWBELL", 4), ("CYMBALL/HI HAT", 2)],
    "gold":       [("COWBELL", 2), ("PERC/BONGO", 3)],
    "item":       [("COWBELL", 5), ("PERC/BONGO", 1)],
    "wield":      [("CLAP", 1), ("CYMBALL/HI HAT", 3)],
    "armor":      [("FILL", 4), ("CLAP", 3)],
    "eat":        [("PERC/BONGO", 1), ("SNARE", 9)],
    "drink":      [("FILL", 4), ("FILL", 5)],
    "read":       [("FILL", 5), ("PERC/PERC", 12)],
    "quaff_bad":  [("FX", 6), ("PERC/SHAKER", 3)],
    "magic":      [("FX", 10), ("FX", 15), ("SAMPLE", 8)],
    "magic_big":  [("FX", 44), ("FX", 37), ("FX", 46)],
    "fire":       [("FX", 11), ("FX", 2)],
    "zap":        [("FX", 15), ("FX", 12)],
    "ammo":       [("CYMBALL/HI HAT", 4), ("PERC/SHAKER", 4)],
    "stairs":     [("CYMBALL/HI HAT", 2), ("PERC/CONGA", 4)],
    "levelup":    [("ACAPELLA", 30), ("PERC/CONGA", 7)],
    "descend":    [("ACAPELLA", 13), ("CYMBALL/CRASH", 3)],
    "error":      [("BASS", 18), ("SNARE", 28)],
    "menu":       [("CYMBALL/HI HAT", 6), ("PERC/BONGO", 2)],
    "select":     [("CYMBALL/OPEN HAT", 2)],
    "quaff":      [("FILL", 4)],
    "heal":       [("ACAPELLA", 31), ("FILL", 4)],
    "death":      [("FX", 11)],
    "lowhp":      [("SNARE", 28)],
    "hungry":     [("PERC/SHAKER", 2)],
    "kick":       [("KICK", 1), ("KICK", 5)],
    "trap":       [("FX", 16), ("SNARE", 2)],
}

MUSIC_MAP = {
    "title": [("LOOP", 42), ("LOOP", 38), ("LOOP", 40)],
    "game":  [("LOOP", 41), ("LOOP", 45)],
    "danger": [("LOOP", 45), ("LOOP", 43)],
}


class Audio:
    def __init__(self, enabled=True, volume=0.45):
        self.enabled = enabled
        self.volume = volume
        self.music_volume = 0.55
        self.effects_volume = 1.0
        self.ui_volume = 1.0
        self.environment_volume = 1.0
        self.alarm_volume = 1.0
        self._channels = {}
        self.ok = False
        self.sounds: dict[str, list[pygame.mixer.Sound]] = {}
        self.music: dict[str, pygame.mixer.Sound] = {}
        self.current_music = None
        self.current_music_key = None
        self.muted = False
        self._missing: set[str] = set()
        self.playlists = {}
        self.skipped_tracks = []
        self._track_index = {}
        self._bad_tracks = set()
        self.current_track = None
        self._mood_since = 0.0
        self._combat_until = 0.0
        self._last_sound = {}

    # --- Инициализация -----------------------------------------------------
    def init(self):
        try:
            pygame.mixer.pre_init(44100, -16, 2, 512)
            pygame.mixer.init()
            pygame.mixer.set_num_channels(24)
            self.ok = True
            self._load_all()
            self._load_music()
        except Exception:  # noqa: BLE001 - нет звука не должно ломать игру
            self.ok = False
            print("[audio] mixer unavailable:", pygame.get_error())
        return self.ok

    def _resolve(self, folder: str, index: int) -> str | None:
        base = os.path.join(C.SOUND_DIR, *folder.split("/"))
        for ext in (".wav", ".mp3", ".ogg", ".flac"):
            p = os.path.join(base, f"{folder.split('/')[-1]} ({index}){ext}")
            if os.path.isfile(p):
                return p
        return None

    def _load_all(self):
        # Neutral synthesized cues replace the unrelated music production pack.
        # A user can override an event with sound/events/<event>.wav or .ogg.
        rate,fmt,channels=pygame.mixer.get_init()
        self.loaded_count=0
        if fmt != -16: return
        rng=random.Random(918)
        for event in SOUND_MAP:
            path=next((os.path.join(C.SOUND_DIR,'events',event+ext)
                       for ext in ('.wav','.ogg','.mp3')
                       if os.path.isfile(os.path.join(C.SOUND_DIR,'events',event+ext))),None)
            if path:
                try:
                    self.sounds[event]=[pygame.mixer.Sound(path)]
                    self.loaded_count+=1
                    continue
                except pygame.error: pass
            duration=.07 if event in ('step','select','menu') else .18
            if event=='sleep_alarm': duration=.7
            frequency=140 if event in ('hit','player_hurt','door_bump','death','sleep_alarm') else 480
            samples=array('h')
            for i in range(int(rate*duration)):
                t=i/rate
                envelope=math.sin(math.pi*t/duration)**2
                noise=rng.uniform(-1,1)
                signal=noise*.4 if event in ('step','read','armor','eat') else math.sin(2*math.pi*frequency*t)*.6+noise*.1
                value=int(32767*.18*signal*envelope)
                samples.extend([value]*channels)
            self.sounds[event]=[pygame.mixer.Sound(buffer=samples.tobytes())]
            self.loaded_count+=1

    def _load_music(self):
        root = os.path.join(C.BASE_DIR, 'Sound trak')
        aliases = {'menu sound':'title','stranger':'stranger','strange':'stranger',
                   'happy stranger':'happy stranger','ocen':'ocean'}
        if os.path.isdir(root):
            for folder in sorted(os.listdir(root)):
                path=os.path.join(root,folder)
                if not os.path.isdir(path): continue
                mood=aliases.get(folder.lower(),folder.lower())
                tracks=[]
                for filename in sorted(os.listdir(path)):
                    full=os.path.join(path,filename)
                    if filename.lower().endswith(('.mp3','.ogg','.wav','.flac')):
                        tracks.append(full)
                    elif filename.lower().endswith('.mp4'):
                        # Optional offline conversion tool writes beside no originals.
                        converted=os.path.join(C.BASE_DIR,'sound_cache',folder,filename+'.ogg')
                        if os.path.isfile(converted): tracks.append(converted)
                        else: self.skipped_tracks.append(full)
                self.playlists[mood]=tracks

    # --- Воспроизведение ---------------------------------------------------
    def play(self, event: str, volume_scale=1.0):
        now=time.monotonic()
        if event in ('hit','miss','player_hurt','ammo','kill','crit'):
            self._combat_until=now+8
        if not self.enabled or not self.ok or self.muted:
            return
        bucket = self.sounds.get(event)
        if not bucket:
            return
        if now-self._last_sound.get(event,-100)<(.12 if event in ('step','select','menu') else .05):
            return
        self._last_sound[event]=now
        snd = bucket[0]
        if event in ('menu','select','error'):
            category='ui_volume'
        elif event in ('sleep_alarm','lowhp','hungry','trap'):
            category='alarm_volume'
        elif event in ('step','door','door_bump','stairs','descend','ambience'):
            category='environment_volume'
        else:
            category='effects_volume'
        v = max(0.0,min(1.0, self.volume * getattr(self,category) * volume_scale))
        try:
            channel=pygame.mixer.find_channel()
            if channel:
                channel.set_volume(v)
                channel.play(snd)
                self._channels[channel]=(category,volume_scale)
        except Exception:  # noqa: BLE001
            pass

    def play_music(self, key: str):
        key={'game':'stranger'}.get(key,key)
        if not self.enabled or not self.ok or self.muted:
            return
        if self.current_music_key == key and pygame.mixer.music.get_busy():
            return
        tracks=self.playlists.get(key) or self.playlists.get('stranger',[])
        for _ in range(len(tracks)):
            index=self._track_index.get(key,0)%len(tracks)
            self._track_index[key]=index+1
            path=tracks[index]
            if path in self._bad_tracks: continue
            try:
                pygame.mixer.music.load(path)
                pygame.mixer.music.set_volume(self.volume*self.music_volume)
                pygame.mixer.music.play(fade_ms=800)
                self.current_music_key=key
                self.current_track=path
                self._mood_since=time.monotonic()
                return
            except (pygame.error,OSError): self._bad_tracks.add(path)

    def update_context(self, game):
        if not self.ok or not self.enabled or self.muted: return
        p=game.player
        if game.mode=='title' or p is None or getattr(game,'modal_return',None)=='title' and game.mode=='modal':
            mood='title'
        elif not p.alive:
            mood='memory'
        else:
            profile=getattr(game.level,'profile',{})
            cells=getattr(game,'visible_world',{})
            levels={id(lv):lv for lv,x,y in cells.values()}
            levels[id(game.level)]=game.level
            nearby=[m for lv in levels.values() for m in lv.monsters
                    if m.alive and (m.x,m.y) in lv.visible and m.hostile]
            from .monsters import MONSTERS
            if p.sanity<=10 or (nearby and p.hp<=p.max_hp*.25):
                mood='madness'
            elif any(MONSTERS.get(m.name,{}).get('music_mood')=='danger' or m.tier>=3 for m in nearby):
                mood='danger'
            elif time.monotonic()<self._combat_until:
                mood='attack'
            else:
                mood=str(profile.get('music_mood','madness' if p.b_level==6 else 'stranger')).lower()
        urgent=mood in ('title','danger','madness','attack','memory')
        rank={'title':5,'memory':5,'madness':4,'danger':3,'attack':2}
        if (mood!=self.current_music_key and mood not in ('title','memory')
                and rank.get(mood,0)<rank.get(self.current_music_key,0)
                and time.monotonic()-self._mood_since<8): return
        if mood!=self.current_music_key and not urgent and time.monotonic()-self._mood_since<8:
            return
        self.play_music(mood)

    def stop_music(self):
        if self.ok:
            pygame.mixer.music.stop()
        self.current_track=None
        if self.current_music is not None:
            try:
                self.current_music.stop()
            except Exception:  # noqa: BLE001
                pass
        self.current_music = None
        self.current_music_key = None

    def toggle_mute(self) -> bool:
        self.muted = not self.muted
        if self.ok:
            if self.muted:
                pygame.mixer.stop()
                pygame.mixer.music.pause()
            else:
                pygame.mixer.music.unpause()
        return self.muted

    def set_volume(self, value: float):
        """Устанавливает общую громкость для эффектов и музыки."""
        self.volume = max(0.0, min(1.0, float(value)))
        for bucket in self.sounds.values():
            for snd in bucket:
                snd.set_volume(1.0)
        for snd in self.music.values():
            snd.set_volume(self.volume * self.music_volume)
        if self.current_music is not None:
            self.current_music.set_volume(self.volume * self.music_volume)
        if self.ok:
            pygame.mixer.music.set_volume(self.volume*self.music_volume)
            for channel,(category,scale) in list(self._channels.items()):
                if channel.get_busy():
                    channel.set_volume(max(0,min(1,self.volume*getattr(self,category)*scale)))
                else:
                    del self._channels[channel]

    def set_mix(self, name, value):
        if name not in ('volume','music_volume','effects_volume','ui_volume','environment_volume','alarm_volume'):
            raise ValueError(name)
        setattr(self,name,max(0.0,min(1.0,float(value))))
        self.set_volume(self.volume)

    def status(self) -> str:
        if not self.ok:
            return "sound: unavailable"
        state = "muted" if self.muted else "on"
        return f"sound: {state} | music: {self.current_music_key or '-'}"
