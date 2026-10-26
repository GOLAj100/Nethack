"""Tiny procedural 3D furniture models rendered from coloured box primitives."""
import pygame
from functools import lru_cache


def model(kind,color):
    return _model(kind,tuple(color))


@lru_cache(maxsize=128)
def _model(kind,color):
    surface=pygame.Surface((96,96),pygame.SRCALPHA)
    def project(x,y,z): return (48+(x-y)*37,76+(x+y)*12-z*58)
    def box(x,y,z,w,d,h):
        a,b,c,e=[project(xx,yy,z+h) for xx,yy in ((x,y),(x+w,y),(x+w,y+d),(x,y+d))]
        floor=[project(xx,yy,z) for xx,yy in ((x,y),(x+w,y),(x+w,y+d),(x,y+d))]
        pygame.draw.polygon(surface,tuple(int(v*.6) for v in color),[b,c,floor[2],floor[1]])
        pygame.draw.polygon(surface,tuple(int(v*.8) for v in color),[c,e,floor[3],floor[2]])
        pygame.draw.polygon(surface,color,[a,b,c,e])
        pygame.draw.lines(surface,tuple(int(v*.45) for v in color),True,[a,b,c,e],1)
    if kind in ('nightstand','chair'):
        for x,y in ((-.4,-.4),(.3,-.4),(-.4,.3),(.3,.3)): box(x,y,0,.1,.1,.45)
        box(-.45,-.45,.45,.9,.9,.1)
        if kind=='chair': box(-.45,-.45,.55,.9,.12,.4)
    elif kind in ('bed','sofa','table'):
        box(-.5,-.5,0,1,1,.35 if kind=='bed' else .5)
    elif kind=='barricade':
        box(-.4,-.15,0,.1,.3,.9); box(.3,-.15,0,.1,.3,.9)
        for z in (.1,.4,.7): box(-.5,-.2,z,1,.15,.15)
    else:
        box(-.4,-.4,0,.8,.8,.95 if kind=='wardrobe' else .5)
    return surface
