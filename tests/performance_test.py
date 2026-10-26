import os
import sys
from types import SimpleNamespace
os.environ['SDL_VIDEODRIVER']='dummy'
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame
from engine.performance import Performance
from engine.renderer import Renderer
pygame.init()
p=Performance()
p.record(16,1,2,3)
assert not p.samples
p.enabled=True
for _ in range(299): p.record(16,1,2,3)
p.record(100,2,80,5)
means,p99,peak=p.stats()
assert peak==100 and p99==16
r=Renderer(pygame.Surface((1040,1026)))
p.draw(SimpleNamespace(display=None,r=r,views=SimpleNamespace(mode='ascii'),world=None))
p.reset()
assert p.stats() is None
pygame.quit()
print('PERFORMANCE MONITOR OK')
