"""Readable default passage artwork; independent of optional tilesets."""
from functools import lru_cache
import pygame


@lru_cache(maxsize=64)
def image(destination):
    surface=pygame.Surface((160,96),pygame.SRCALPHA)
    pygame.draw.rect(surface,(22,104,57),(2,2,156,92),border_radius=6)
    pygame.draw.rect(surface,(225,255,235),(5,5,150,86),3,border_radius=4)
    for text,size,y in (('EXIT',38,10),(f'LEVEL {destination}',18,57)):
        font=pygame.font.SysFont('consolas',size,bold=True)
        label=font.render(text,True,(245,255,245))
        surface.blit(label,label.get_rect(midtop=(80,y)))
    return surface
