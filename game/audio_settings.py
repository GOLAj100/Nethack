"""Sound sliders in logical canvas coordinates (works with GPU presentation)."""
import pygame
from engine import config as C
from .lang import t, save_settings

class AudioSettings:
    fields=('volume','music_volume','effects_volume','environment_volume','alarm_volume','ui_volume')
    def __init__(self, game):
        self.game=game
        self.selected=0
        self.drag=None

    def bar(self,index):
        r=self.game.r
        width=r.surface.get_width()
        return pygame.Rect(width//8,(6+index*3)*r.ch,width*3//4,12)

    def button(self,index):
        r=self.game.r
        return pygame.Rect(r.surface.get_width()//8,(7+len(self.fields)*3+index*2)*r.ch,r.surface.get_width()*3//4,r.ch+4)

    def change(self,index,value):
        self.game.audio.set_mix(self.fields[index],round(max(0,min(1,value))*100)/100)
        save_settings(self.game)

    def activate(self,index):
        if index==0:
            self.game.audio.toggle_mute()
        elif index==1:
            self.game.audio.play('pickup',1)
        elif index==2:
            for key,value in zip(self.fields,(.45,.55,1.,1.,1.,1.)):
                self.game.audio.set_mix(key,value)
        else:
            self.drag=None
            self.game.mode=self.game._audio_return
            self.game.open_settings()
        save_settings(self.game)

    def key(self,event):
        if event.key==pygame.K_ESCAPE:
            self.activate(3)
        elif event.key in (pygame.K_UP,pygame.K_DOWN,pygame.K_TAB):
            self.selected=(self.selected+(-1 if event.key==pygame.K_UP else 1))%(len(self.fields)+4)
        elif event.key in (pygame.K_LEFT,pygame.K_RIGHT,pygame.K_HOME,pygame.K_END) and self.selected<len(self.fields):
            value=getattr(self.game.audio,self.fields[self.selected])
            if event.key==pygame.K_HOME: value=0
            elif event.key==pygame.K_END: value=1
            else: value+=(-.05 if event.key==pygame.K_LEFT else .05)
            self.change(self.selected,value)
        elif event.key in (pygame.K_RETURN,pygame.K_SPACE) and self.selected>=len(self.fields):
            self.activate(self.selected-len(self.fields))

    def mouse(self,event):
        if event.type==pygame.MOUSEBUTTONUP:
            self.drag=None
            return
        if event.type==pygame.MOUSEBUTTONDOWN and event.button==1:
            for i in range(len(self.fields)):
                if self.bar(i).inflate(20,28).collidepoint(event.pos):
                    self.drag=self.selected=i
                    break
            for i in range(4):
                if self.button(i).collidepoint(event.pos):
                    self.selected=len(self.fields)+i
                    self.activate(i)
                    return
        if event.type in (pygame.MOUSEBUTTONDOWN,pygame.MOUSEMOTION) and self.drag is not None:
            if event.type==pygame.MOUSEMOTION and not event.buttons[0]:
                self.drag=None
                return
            bar=self.bar(self.drag)
            self.change(self.drag,(event.pos[0]-bar.x)/bar.w)

    def draw(self):
        g=self.game
        r=g.r
        if g.display: g.display.scene=None
        r.clear()
        r.text(3,2,t('audio.title'),C.CYAN,bold=True)
        for i,name in enumerate(self.fields):
            bar=self.bar(i)
            value=getattr(g.audio,name)
            r.text(bar.x//r.cw,bar.y//r.ch-1,t('audio.'+name)+f'  {round(value*100)}%',C.WHITE if self.selected==i else C.GRAY)
            pygame.draw.rect(r.surface,C.DARK_GRAY,bar)
            pygame.draw.rect(r.surface,C.CYAN,(bar.x,bar.y,round(bar.w*value),bar.h))
            pygame.draw.circle(r.surface,C.WHITE,(bar.x+round(bar.w*value),bar.centery),8)
        labels=(t('set.sound')+': '+t('set.off' if g.audio.muted else 'set.on'),t('audio.test'),t('set.reset'),t('set.back'))
        for i,label in enumerate(labels):
            rect=self.button(i)
            pygame.draw.rect(r.surface,(32,42,58) if self.selected==i+len(self.fields) else (20,24,34),rect)
            r.text(rect.x//r.cw+1,rect.y//r.ch,label,C.WHITE)
        r.text(3,34,t('audio.hint'),C.GRAY,max_cells=r.surface.get_width()//r.cw-6)
        if not g.audio.ok:
            r.text(3,35,t('audio.unavailable'),C.YELLOW)
