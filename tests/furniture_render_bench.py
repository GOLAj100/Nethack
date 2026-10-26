"""Cold sprite-cache comparison; no display, no save/settings writes."""
import os
import sys
import time
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame
from engine.renderer import Renderer
from engine.furniture_art import model

pygame.font.init()
r=Renderer(pygame.Surface((200,200)))
colors=[(100+i,120+i,140+i) for i in range(12)]
start=time.perf_counter()
for color in colors:
    source=model('bed',color)
    scaled=pygame.transform.smoothscale(source.premul_alpha(),(256,256))
    for y in range(256):
        for x in range(256):
            red,green,blue,a=scaled.get_at((x,y))
            if a:
                scaled.set_at((x,y),(min(255,round(red*255/a)),min(255,round(green*255/a)),min(255,round(blue*255/a)),a))
old=(time.perf_counter()-start)*1000/len(colors)
start=time.perf_counter()
for color in colors:
    image=r.visual('π',color,True,size=(256,256))
    assert image.get_bounding_rect().width>0
new=(time.perf_counter()-start)*1000/len(colors)
print(f'Bed cold-cache sprite old/new: {old:.2f}/{new:.2f} ms')
