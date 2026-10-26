import os
import sys
import tempfile
import json
os.environ['SDL_VIDEODRIVER'] = 'dummy'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame
from engine.renderer import Renderer
pygame.init()
r = Renderer(pygame.Surface((200,200)))
with tempfile.TemporaryDirectory() as tmp:
    os.mkdir(os.path.join(tmp,'test'))
    image = pygame.Surface((16,16),pygame.SRCALPHA)
    image.fill((255,255,255,255))
    pygame.image.save(image,os.path.join(tmp,'test','white.png'))
    with open(os.path.join(tmp,'test','manifest.json'),'w') as f:
        json.dump({'tile_size':16,'tiles':{'@':'white.png','#':'missing.png'}},f)
    r.tileset.root = tmp
    r.tileset.configure(True,True,32,'test')
    assert r.visual('@',(255,0,0)).get_size() == (r.cw,r.ch)
    assert r.visual('@',(255,0,0),size=(32,32)).get_size() == (32,32)
    assert r.visual('#',(255,0,0)) is r.glyph('#',(255,0,0))
    atlas = pygame.Surface((32, 16), pygame.SRCALPHA)
    atlas.fill((0, 255, 0), pygame.Rect(16, 0, 16, 16))
    pygame.image.save(atlas, os.path.join(tmp, 'test', 'atlas.png'))
    r.tileset.configure(True, False, 16, 'test')
    r.tileset.sheet = os.path.join(tmp, 'test', 'atlas.png')
    r.tileset.atlas = {'k': [1, 0]}
    assert r.tileset.image('k', (255, 255, 255)).get_at((8, 8))[:3] == (0, 255, 0)
    r.text(0,0,'@',(255,0,0))
    r.tile(0,2,'@',(255,0,0))
    with open(os.path.join(tmp,'test','manifest.json'),'w') as f:
        f.write('{bad')
    r.tileset.configure()
    assert r.tileset.image('@',(255,0,0)) is None
pygame.quit()
print('TILESET OK')
