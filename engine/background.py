"""Offline colour-key background removal, preserving source and enclosed details."""
from collections import deque
import pygame


def remove_background(source, color=None, tolerance=30, edges_only=True):
    w,h=source.get_size()
    corners=[source.get_at(p)[:3] for p in ((0,0),(w-1,0),(0,h-1),(w-1,h-1))]
    if color is None:
        # Select the corner colour with greatest agreement among corners.
        color=min(corners,key=lambda a:sum(max(abs(a[i]-b[i]) for i in range(3)) for b in corners))
    tolerance=max(0,min(255,int(tolerance)))
    output=pygame.Surface((w,h),pygame.SRCALPHA)
    output.blit(source,(0,0))
    seen=bytearray(w*h)
    def matches(x,y):
        c=output.get_at((x,y))
        return c.a==0 or max(abs(c[i]-color[i]) for i in range(3))<=tolerance
    if not edges_only:
        for y in range(h):
            for x in range(w):
                if matches(x,y): output.set_at((x,y),(0,0,0,0))
        return output
    queue=deque()
    def visit(x,y):
        index=y*w+x
        if seen[index]: return
        seen[index]=1
        if matches(x,y):
            output.set_at((x,y),(0,0,0,0))
            queue.append((x,y))
    for x in range(w):
        visit(x,0); visit(x,h-1)
    for y in range(h):
        visit(0,y); visit(w-1,y)
    while queue:
        x,y=queue.popleft()
        if x>0: visit(x-1,y)
        if x+1<w: visit(x+1,y)
        if y>0: visit(x,y-1)
        if y+1<h: visit(x,y+1)
    return output
