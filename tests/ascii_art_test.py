import os
import sys
import tempfile
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame
from engine.ascii_art import convert
from engine.tileset import TilesetManager

pygame.font.init()
source=pygame.Surface((32,32),pygame.SRCALPHA)
source.fill((255,255,255,255))
image,text=convert(source,8,colored=False)
assert set(text.replace('\n',''))=={'@'}
assert all(len(line)==8 for line in text.splitlines())
assert abs(image.get_width()/image.get_height()-1)<.25
assert set(convert(source,8,invert=True)[1].replace('\n',''))=={' '}
source.fill((255,255,255,0))
image,text=convert(source,8)
assert not text.strip() and image.get_bounding_rect().size==(0,0)
source.fill((0,255,0,255))
image,text=convert(source,8)
assert image.get_bounding_rect().width>0
assert any(image.get_at((x,y)).g>0 for x in range(image.get_width()) for y in range(image.get_height()))
with tempfile.TemporaryDirectory() as tmp:
    path=os.path.join(tmp,'art.png')
    pygame.image.save(image,path)
    ts=TilesetManager()
    ts.enabled=True
    ts.tiles={'%':path}
    assert ts.image('%',(255,255,255)) is not None
for bad in (0,1000):
    try: convert(source,bad)
    except ValueError: pass
    else: raise AssertionError('Invalid detail accepted')
print('ASCII CONVERSION OK')
