import os
import sys
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame
from engine.background import remove_background

source=pygame.Surface((20,20),pygame.SRCALPHA)
source.fill('white')
pygame.draw.rect(source,'red',(4,4,12,12))
source.set_at((10,10),'white')
out=remove_background(source)
assert out.get_at((0,0)).a==0
assert out.get_at((4,4)).a==255
assert out.get_at((10,10)).a==255  # Enclosed detail is preserved.
assert source.get_at((0,0)).a==255
assert remove_background(source,edges_only=False).get_at((10,10)).a==0
source.set_at((0,0),(240,240,240,255))
assert remove_background(source,color=(255,255,255),tolerance=10).get_at((0,0)).a==255
assert remove_background(source,color=(255,255,255),tolerance=20).get_at((0,0)).a==0
source.fill((0,0,0,0))
assert remove_background(source).get_bounding_rect().size==(0,0)
print('BACKGROUND OK')
