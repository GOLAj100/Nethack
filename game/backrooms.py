"""Main Nine generation and progression. B-Level exits are independent of Z stairs."""
from collections import deque

from . import mapgen as MG
from .items import Item
from .lang import t


def generate(w, h, profile, rng, z=0):
    kind = profile['generator']
    if kind == 'lobby':
        return MG.generate_lobby(w, h, rng)
    tiles = [MG.WALL] * (w*h)
    rooms = []

    def rect(x1, y1, x2, y2, tile=MG.FLOOR):
        for y in range(max(0,y1), min(h,y2+1)):
            for x in range(max(0,x1), min(w,x2+1)):
                tiles[y*w+x] = tile

    def room(x1, y1, x2, y2, lit=True):
        rect(x1,y1,x2,y2)
        r = MG.Room(x1,y1,x2,y2)
        r.lit = lit
        rooms.append(r)

    if kind in ('parking', 'city'):
        # Broad parking bays divided by concrete columns and maintenance walls.
        for y in range(0,h,10):
            for x in range(0,w,20):
                room(x+1,y+1,min(w-2,x+18),min(h-2,y+8))
                rect(x+9,y+2,x+10,y+3,MG.WALL)
                rect(x+3,y+1,x+6,y+1,MG.WINDOW)
    elif kind in ('pipes','sewer','carrier','electrical') or (kind in ('tundra','extraterrestrial') and z < 0):
        # Long utility runs; electrical rooms widen junctions, pipes do not.
        for y in range(4,h,10):
            rect(0,y,w-1,y+1)
        for x in range(4,w,10):
            rect(x,0,x+1,h-1)
        if kind in ('pipes','sewer','carrier','electrical'):
            for x in range(2,w,10): rect(x,2,x+1,h-3,MG.PIPE)
        for y in range(0,h,10):
            for x in range(0,w,10):
                if kind == 'electrical':
                    room(x+2,y+2,min(w-1,x+7),min(h-1,y+7),rng.random()<.55)
                    rect(x+2,y+2,x+3,y+3,MG.WALL)
                else:
                    room(x+4,y+4,x+5,y+5,rng.random()<.3 and kind!='tundra')
        if kind in ('sewer', 'carrier'):
            for x in range(6, w, 14):
                rect(x, 0, min(w-1, x+1), h-1, MG.WATER)
    elif kind in ('office','memories','flesh','hotel','well','hospital','asylum','abyss'):
        for y in range(0,h,10):
            rect(0,y+4,w-1,y+5)
            for x in range(0,w,10):
                rect(x+4,0,x+5,h-1)
                room(x+1,y+1,min(w-2,x+8),min(h-2,y+3),kind in ('hotel','well','hospital','asylum','abyss') or rng.random()<.5)
                room(x+1,y+6,min(w-2,x+8),min(h-2,y+8),kind in ('hotel','well','hospital','asylum','abyss') or rng.random()<.5)
                rect(x+4,y+3,x+4,y+3,MG.DOOR)
                rect(x+5,y+6,x+5,y+6,MG.DOOR)
        if kind in ('hotel','well','hospital','asylum','abyss'):
            room(w//2-8,h//2-6,w//2+8,h//2+6)  # ballroom
            room(w-18,h-12,w-2,h-2,False)  # boiler/service area
        if kind == 'flesh':
            # Aedificium's rooms are familiar but slightly wrong: a dark core
            # and a few structural gaps break the regular house grid.
            rect(w//2-1, 1, w//2+1, h-2, MG.WALL)
            rect(w//2, h//2-2, w//2, h//2+2)
    elif kind in ('tundra','extraterrestrial'):
        rect(0,0,w-1,h-1)
        for y in range(0,h,10):
            for x in range(0,w,10):
                r = MG.Room(x+1,y+1,min(w-1,x+8),min(h-1,y+8))
                rooms.append(r)
                # Rock outcrops and dead vegetation; passages remain connected.
                rect(x+1,y+1,x+rng.randint(2,3),y+rng.randint(2,3),MG.WALL)
                rect(x+7,y+7,x+8,y+8,MG.HEDGE)
    elif kind == 'ocean':
        # Level 7: a small rusted bunker surrounded by an endless, calm sea.
        rect(0, 0, w-1, h-1, MG.WATER)
        bx1, by1, bx2, by2 = w//2-14, h//2-9, w//2+14, h//2+9
        rect(bx1, by1, bx2, by2, MG.WALL)
        rect(bx1+1, by1+1, bx2-1, by2-1)
        rect(bx1+5, by1, bx1+7, by1, MG.DOOR)
        rect(bx2-7, by2, bx2-5, by2, MG.DOOR)
        # A short pier is the safe route from the hatch to the water.
        rect(w//2-1, by2+1, w//2, min(h-1, by2+6), MG.FLOOR)
        rooms.append(MG.Room(bx1+1, by1+1, bx2-1, by2-1))
    elif kind == 'cave':
        # Large connected chambers with narrow rocky passages and cold pools.
        rect(1, 1, w-2, h-2)
        for y in range(5, h-4, 9):
            for x in range(7, w-6, 15):
                if rng.random() < .65:
                    rect(x, y, min(w-3, x+4), min(h-3, y+3), MG.WALL)
        for x in range(8, w-8, 18):
            rect(x, h//2-1, x+5, h//2+1)
        for x, y, rw, rh in ((14, 10, 7, 4), (48, 31, 8, 5), (67, 14, 5, 3)):
            rect(x, y, min(w-3, x+rw), min(h-3, y+rh), MG.WATER)
        rooms.append(MG.Room(2, 2, w-3, h-3))
    elif kind == 'suburbs':
        for y in range(1, h-5, 12):
            rect(0, y+5, w-1, y+6)
            for x in range(3, w-8, 14):
                room(x, y, min(w-3, x+8), min(h-2, y+4), rng.random() < .35)
                rect(x+4, y+4, x+4, y+5, MG.DOOR)
        rect(0, h//2-1, w-1, h//2)
    elif kind == 'fields':
        rect(0, 0, w-1, h-1)
        for x in range(8, w, 16):
            rect(x, 0, x, h-1, MG.HEDGE)
        for y in range(8, h, 13):
            rect(0, y, w-1, y, MG.HEDGE)
        for x, y in ((w//3, h//3), (w*2//3, h*2//3)):
            for yy in range(max(1,y-2), min(h-1,y+3)):
                for xx in range(max(1,x-3), min(w-1,x+4)):
                    tiles[yy*w+xx] = MG.WATER
        rooms.append(MG.Room(1, 1, w-2, h-2))
    else:
        raise ValueError('Unknown Backrooms generator: '+kind)

    # Shared, unobstructed seams. These also connect every room to the spine.
    if kind == 'ocean':
        return dict(tiles=tiles,rooms=rooms,kind=kind,style=0)
    for y in range(4,h,10):
        rect(0,y,w-1,y+1)
    for x in range(4,w,10):
        rect(x,0,x+1,h-1)
    rect(0,h//2-1,w-1,h//2)
    rect(w//2-1,0,w//2,h-1)
    return dict(tiles=tiles,rooms=rooms,kind=kind,style=0)


def decorate(lv, profile, rng):
    """Fixtures off the shared corridors; loot is generated once and persists."""
    from .furniture import Furniture, can_place
    kind = profile['generator']
    pools = {'parking': ('box',), 'city': ('box',), 'electrical': ('box',),
             'pipes': ('box',), 'sewer': ('pump','valve'), 'carrier': ('box','valve'),
             'office': ('table','chair','nightstand'), 'memories': ('chair','sofa','table'),
             'flesh': ('table','chair'),
             'hotel': ('bed','nightstand','sofa','table'), 'well': ('bed','nightstand'),
             'hospital': ('bed','nightstand','table','medical cart'), 'asylum': ('bed','chair','table','generator'),
             'abyss': ('bed','nightstand','sofa','table')}
    for i, room in enumerate(lv.rooms[1::3]):
        if kind not in pools:
            break
        obj = Furniture(pools[kind][i%len(pools[kind])],room.x1,room.y1)
        if can_place(lv,obj,obj.x,obj.y):
            lv.furniture.append(obj)
            if obj.spec['capacity']:
                for name in ('potion of healing','food ration'):
                    obj.contents.append(Item(name,rng=rng))
    for pos in ((x,y) for y in range(lv.h) for x in range(lv.w) if lv.at(x,y)==MG.DOOR):
        lv.doors[pos] = dict(open=False,locked=False,broken=False)
    if kind in ('tundra','extraterrestrial'):
        # Paired access to the underground corridors, not another B-Level.
        lv.set(4,4,MG.STAIR_DOWN if lv.world_z==0 else MG.STAIR_UP)
        lv.light_sources = []
    if kind in ('pipes','sewer','carrier','electrical'):
        # Exposed steam/electrics are inspectable, avoidable floor hazards.
        for room in lv.rooms[3::7]:
            pos = (room.cx+1,room.cy)
            if lv.at(*pos)==MG.FLOOR:
                lv.hazards[pos] = 'steam' if kind in ('pipes','sewer') else 'wire'
                lv.set(*pos,MG.RUBBLE)
    elif kind == 'ocean':
        for y in range(7, lv.h, 13):
            for x in range(9, lv.w, 21):
                if lv.at(x, y) == MG.WATER:
                    lv.hazards[(x, y)] = 'current'
                    if lv.in_bounds(x + 1, y) and lv.at(x + 1, y) == MG.WATER:
                        lv.hazards[(x + 1, y)] = 'deep_water'
    elif kind == 'cave':
        for pos in ((14, 10), (48, 31), (67, 14)):
            if lv.in_bounds(*pos) and lv.at(*pos) == MG.WATER:
                lv.hazards[pos] = 'cave_cold'
    elif kind == 'suburbs':
        for y in range(6, lv.h, 12):
            for x in range(10, lv.w, 18):
                if lv.in_bounds(x, y) and lv.at(x, y) in MG.WALKABLE:
                    lv.light_sources.append((x, y))
                    from .furniture import Furniture, can_place
                    lamp = Furniture('lamp post', x, y)
                    if can_place(lv, lamp, x, y):
                        lv.furniture.append(lamp)
        for room in lv.rooms[2::7]:
            pos = room.center()
            if lv.at(*pos) in MG.WALKABLE:
                lv.hazards[pos] = 'silence'
    elif kind == 'fields':
        for y in range(5, lv.h, 17):
            for x in range(12, lv.w, 23):
                if lv.at(x, y) == MG.FLOOR:
                    lv.set(x, y, MG.BLACK_GRASS)
                    lv.hazards[(x, y)] = 'black_grass'
        from .furniture import Furniture, can_place
        barn_candidates = [(3, 3), (30, 20), (55, 35), (72, 8)]
        for pos in barn_candidates:
            barn = Furniture('barn', pos[0], pos[1])
            if can_place(lv, barn, *pos):
                lv.furniture.append(barn)
    # Level-specific first-pass lore hazards. They are sparse, deterministic
    # and serialized with the chunk, so revisiting a location keeps its state.
    if kind == 'sewer':
        # Contaminated runoff in water damages exposed travellers; pumps mark
        # the few places where the player can later attach purification logic.
        for y in range(2, lv.h, 9):
            for x in range(5, lv.w, 17):
                if lv.at(x, y) == MG.WATER:
                    lv.hazards[(x, y)] = 'sewage'
    elif kind == 'hospital':
        for room in lv.rooms[1::8]:
            pos = room.center()
            if lv.at(*pos) in MG.WALKABLE and not lv.furniture_at(*pos):
                lv.hazards[pos] = 'toxic'
    elif kind == 'asylum':
        for room in lv.rooms[2::9]:
            pos = (room.x1 + 1, room.y1 + 1)
            if lv.in_bounds(*pos) and lv.at(*pos) in MG.WALKABLE:
                lv.hazards[pos] = 'static'
    elif kind == 'carrier':
        for y in range(3, lv.h, 11):
            for x in range(8, lv.w, 19):
                if lv.at(x, y) == MG.WATER:
                    lv.hazards[(x, y)] = 'electric_water'


def ensure_exits(lv, profile):
    """Idempotent also for existing Level 0 saves: never replaces furniture/items."""
    if lv.world_z != 0 or lv.exits or not profile.get('exits'):
        return
    target = profile.get('next_level')
    if target is None:
        return
    start = (4,4)
    if not lv.is_walkable(*start) or lv.at(*start)==MG.AIR:
        available=[(x,y) for y in range(lv.h) for x in range(lv.w)
                   if lv.is_walkable(x,y) and lv.at(x,y)!=MG.AIR]
        if not available: return
        start=min(available,key=lambda p:abs(p[0]-4)+abs(p[1]-4))
    queue = deque([start])
    distances = {start:0}
    while queue:
        pos = queue.popleft()
        for near in lv.neighbors(*pos):
            if near not in distances and lv.is_walkable(*near) and lv.at(*near)!=MG.AIR:
                distances[near] = distances[pos]+1
                queue.append(near)
    candidates = [pos for pos in distances if lv.at(*pos)==MG.FLOOR
                  and pos not in lv.items and pos not in lv.hazards
                  and lv.furniture_at(*pos) is None
                  and 1 < pos[0] < lv.w-2 and 1 < pos[1] < lv.h-2]
    if not candidates:
        return
    primary = candidates
    if profile.get('generator')=='hotel':
        primary = [p for p in candidates if p[0]>=lv.w-18 and p[1]>=lv.h-12] or candidates
    pos = max(primary,key=lambda p:(distances[p],p))
    lv.exits[pos] = dict(target=target,method='passage',label=profile['exit_label'])
    lv.set(*pos,MG.STAIR_UP)
    alternate = profile.get('noclip_target')
    if alternate is not None:
        choices = [p for p in candidates if p!=pos and abs(p[0]-pos[0])+abs(p[1]-pos[1])>15]
        if choices:
            other = max(choices,key=lambda p:distances[p])
            lv.exits[other] = dict(target=alternate,method='noclip',requires='noclip',label='br.noclip')
            lv.set(*other,MG.STAIR_UP)
    if lv.b_level==0 and lv.chunk_x==0 and lv.chunk_y==0:
        spot = next((p for p in sorted(candidates,key=lambda p:distances[p])
                     if p not in lv.exits),None)
        if spot:
            guide = Item('noclip guide',rng=lv.rng)
            guide.identified = True
            lv.items[spot] = guide


def advance_environment(game):
    p, lv = game.player, game.level
    profile = game.world.profile
    interval = profile.get('stress_interval',0)
    if interval and p.turns % interval == 0:
        p.sanity = max(-50,p.sanity-1)
        game.msg(t('br.stress'))
    interval = profile.get('heat_interval',0)
    if interval and p.turns % interval == 0:
        p.stamina = max(0,p.stamina-1)
        game.msg(t('br.heat'))
    hazard = lv.hazards.get((p.x,p.y))
    if hazard:
        p.take_damage(1,cause=hazard)
        game.msg(t('br.hazard.'+hazard))
        if not p.alive:
            game.on_death()
        elif hazard == 'current':
            nx, ny = p.x + 1, p.y
            if lv.is_walkable(nx, ny) and not lv.monster_at(nx, ny) and not lv.furniture_at(nx, ny):
                p.x, p.y = nx, ny
                lv.set_player_pos(nx, ny)
                game.msg(t('br.current'))
        elif hazard == 'black_grass':
            p.status['disoriented'] = max(p.status.get('disoriented', 0), 3)
            game.msg(t('br.black_grass'))
        elif hazard == 'silence':
            p.status['silenced'] = max(p.status.get('silenced', 0), 2)
            game.msg(t('br.silence'))
    if profile.get('swimming') and lv.at(p.x, p.y) == MG.WATER:
        p.status['swim_turns'] = p.status.get('swim_turns', 0) + 1
        cold_interval = profile.get('swim_cold_interval', 5)
        if cold_interval and p.status['swim_turns'] % cold_interval == 0:
            p.stamina = max(0, p.stamina - 1)
            game.msg(t('br.cold_water'))
            damage_interval = profile.get('swim_damage_interval', 20)
            if damage_interval and p.status['swim_turns'] % damage_interval == 0:
                p.take_damage(1, cause='hypothermia')
                if not p.alive:
                    game.on_death()
    else:
        p.status.pop('swim_turns', None)
