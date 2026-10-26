import os
import sys
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from game.world import World
from game.entities import Player
from game import mapgen as MG

w=World(47)
p=Player(35,25); p.b_level=0
lv=w.chunk(0,0,0,visit=True)
w.update_lighting(p,False,1)
static=w._static_fields
p.x+=1
w.update_lighting(p,False,1)
assert w._static_fields is static
assert lv.light_grid[p.x][p.y]==1
w.update_lighting(p,False,.1)
assert w._static_fields is static
lv.set(36,24,MG.DOOR)
lv.doors[36,24]={'open':False}
w.update_lighting(p,False,1)
assert w._static_fields is not static
static=w._static_fields
lv.doors[36,24]['open']=True
w.update_lighting(p,False,1)
assert w._static_fields is not static
w.storage.cleanup()
print('LIGHT CACHE OK')
