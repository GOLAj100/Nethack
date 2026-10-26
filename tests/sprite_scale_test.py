import os
import sys
import tempfile
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame
from engine.renderer import Renderer

pygame.font.init()
r=Renderer(pygame.Surface((200,200),pygame.SRCALPHA))
for symbol in ('!', '.', '█', '▓', '▒', '@'):
    color=(210,130,60)
    glyph=r.visual(symbol,color,size=(64,64))
    assert glyph.get_at((0,0)).a==0 or symbol in ('█','▓','▒')
    for y in range(64):
        for x in range(64):
            pixel=glyph.get_at((x,y))
            if pixel.a:
                assert pixel[:3]==color,(symbol,pixel)
with tempfile.TemporaryDirectory() as tmp:
    image=pygame.Surface((512,731),pygame.SRCALPHA)
    image.fill((255,255,255,255))
    path=os.path.join(tmp,'person.png')
    pygame.image.save(image,path)
    r.tileset.enabled=True
    r.tileset.auto_color=False
    r.tileset.tiles={'@':path}
    r.tileset.native_symbols={'@'}
    assert r.tileset.image('@',(255,255,255)).get_size()==(512,731)
    sprite=r.visual('@',(255,255,255))
    assert sprite.get_size()==(r.cw,r.ch)
    box=sprite.get_bounding_rect()
    assert abs(box.w/box.h-512/731)<.08
    projected=r.visual('@',(255,255,255),size=(128,128))
    box=projected.get_bounding_rect()
    assert box.h==128 and abs(box.w/box.h-512/731)<.02
    r.surface.fill((0,0,0,0))
    r.tile(2,2,'@',(255,255,255))
    assert r.cell_rect(2,2).contains(r.surface.get_bounding_rect())
    assert r.visual('@',(255,255,255),size=(128,128)) is projected
    padded=pygame.Surface((512,731),pygame.SRCALPHA)
    padded.fill((0,0,0,0))
    pygame.draw.rect(padded,(255,255,255,255),(150,30,250,670))
    pygame.image.save(padded,path)
    r.tileset.originals.clear(); r.tileset.cache.clear(); r.tileset.revision+=1
    cropped=r.visual('@',(255,255,255),size=(128,128)).get_bounding_rect()
    assert cropped.h==128 and abs(cropped.w/cropped.h-250/670)<.02
print('SPRITE SCALE OK')
