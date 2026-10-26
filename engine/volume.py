"""Low-resolution software 3D raycaster with real yaw/pitch and open Z shafts.

One world unit per tile and per storey. DDA tests horizontal slabs at Z
boundaries; AIR removes the slab, but leaves the shaft walls intact.
"""
import math
import time
import pygame
from . import config as C
from game import mapgen as MG


_FLOOR = math.floor
_INF = float('inf')
_AIR = MG.AIR
_MISS = object()


def cast(origin, direction, cell, limit, ceiling=True):
    px,py,pz = origin
    rx,ry,rz = direction
    x,y,z = _FLOOR(px),_FLOOR(py),_FLOOR(pz)
    sx,sy,sz = (1 if rx>=0 else -1),(1 if ry>=0 else -1),(1 if rz>=0 else -1)
    # 1/|r| без abs(): знак восстанавливается точно, деление на нуль даёт inf.
    if rx > 1e-9:
        ax = 1.0/rx
    elif rx < -1e-9:
        ax = -1.0/rx
    else:
        ax = _INF
    if ry > 1e-9:
        ay = 1.0/ry
    elif ry < -1e-9:
        ay = -1.0/ry
    else:
        ay = _INF
    if rz > 1e-9:
        az = 1.0/rz
    elif rz < -1e-9:
        az = -1.0/rz
    else:
        az = _INF
    tx = (x+1-px if sx>0 else px-x)*ax
    ty = (y+1-py if sy>0 else py-y)*ay
    tz = (z+1-pz if sz>0 else pz-z)*az
    four = None
    for _ in range(160):
        old_z = z
        if tx<ty and tx<tz:
            axis,dist=0,tx
            tx+=ax
            x+=sx
        elif ty<tz:
            axis,dist=1,ty
            ty+=ay
            y+=sy
        else:
            axis,dist=2,tz
            tz+=az
            z+=sz
        if dist > limit:
            return None
        target = cell(x,y,z)
        if axis == 2:
            upper_z = z if z > old_z else old_z
            upper = cell(x,y,upper_z)
            # Floors are the bottom boundary of their owning cell. An absent
            # upper storey closes the roof; only the ceiling toggle opens it.
            solid = upper is None or (upper[4] if len(upper) > 4 else upper[0].at(upper[1],upper[2]) != _AIR)
            if solid and (rz < 0 or ceiling):
                owner = cell(x,y,old_z) if rz > 0 else upper
                return dist, owner, axis, (x,y,old_z), rz > 0
        if target is None:
            return None
        if four is None:
            # Форма клетки постоянна в пределах луча: длина проверяется один раз.
            four = len(target) > 3
        if (target[3] if four else not target[0].can_see_through(target[1],target[2])):
            return dist,target,axis,(x,y,z),False
    return None


class RayContext:
    """Состояние одного лучевого кадра: кэш клеток и разрешение чанков."""
    __slots__ = ("world","level","chunks","cache","z_lo","z_hi","w","h","grids")

    def __init__(self, game):
        world = getattr(game,'world',None)
        self.world = world
        self.level = game.level
        self.chunks = {}
        self.cache = {}
        self.grids = {}
        self.z_lo = self.z_hi = None
        self.w = self.h = 0
        if world:
            profile = getattr(world,'profile',None) or {}
            self.z_lo, self.z_hi = profile.get('z_min'), profile.get('z_max')
            self.w, self.h = world.w, world.h

    def resolve(self, x, y, z):
        """Холодный путь: уровень и проходимость клетки (как в старом cell())."""
        world = self.world
        if world is None:
            level = self.level
            return self._cell(level, x, y) if z==0 and level.in_bounds(x,y) else None
        if (self.z_lo is not None and z < self.z_lo) or (self.z_hi is not None and z > self.z_hi):
            return None
        cx,lx = divmod(x,self.w)
        cy,ly = divmod(y,self.h)
        key = cx,cy,z
        lv = self.chunks.get(key)
        if lv is None:
            lv = world.chunk(cx,cy,z)
            self.chunks[key] = lv
        # Словарь уровней читается живьём: освещение пересоздаёт его целиком.
        levels = getattr(world,'_lighting_levels',None)
        if levels:
            alt = levels.get(key)
            if alt is not None:
                lv = alt
        return self._cell(lv, lx, ly)

    def _cell(self, lv, x, y):
        grid = self.grids.get(lv)
        if grid is None:
            grid = self.grids[lv] = lv.visual_manager.grid()
        i = y * lv.w + x
        return lv, x, y, bool(grid.walls[i]), bool(grid.floors[i])


def cast_fast(origin, direction, ctx, limit, ceiling=True):
    """То же, что cast(), но поиск клетки встроен в цикл DDA.

    Отдельная копия горячего цикла существует ради скорости: вызов функции
    на каждый шаг луча стоит больше, чем сам шаг. Совпадение результатов с
    cast() проверяется сравнением на всех лучах кадра.
    """
    px,py,pz = origin
    rx,ry,rz = direction
    x,y,z = _FLOOR(px),_FLOOR(py),_FLOOR(pz)
    sx,sy,sz = (1 if rx>=0 else -1),(1 if ry>=0 else -1),(1 if rz>=0 else -1)
    if rx > 1e-9:
        ax = 1.0/rx
    elif rx < -1e-9:
        ax = -1.0/rx
    else:
        ax = _INF
    if ry > 1e-9:
        ay = 1.0/ry
    elif ry < -1e-9:
        ay = -1.0/ry
    else:
        ay = _INF
    if rz > 1e-9:
        az = 1.0/rz
    elif rz < -1e-9:
        az = -1.0/rz
    else:
        az = _INF
    tx = (x+1-px if sx>0 else px-x)*ax
    ty = (y+1-py if sy>0 else py-y)*ay
    tz = (z+1-pz if sz>0 else pz-z)*az
    cache = ctx.cache
    cache_get = cache.get
    resolve = ctx.resolve
    for _ in range(160):
        old_z = z
        if tx<ty and tx<tz:
            axis,dist=0,tx
            tx+=ax
            x+=sx
        elif ty<tz:
            axis,dist=1,ty
            ty+=ay
            y+=sy
        else:
            axis,dist=2,tz
            tz+=az
            z+=sz
        if dist > limit:
            return None
        pos = x,y,z
        target = cache_get(pos,_MISS)
        if target is _MISS:
            target = resolve(x,y,z)
            cache[pos] = target
        if axis == 2:
            upper_z = z if z > old_z else old_z
            pos_up = x,y,upper_z
            upper = cache_get(pos_up,_MISS)
            if upper is _MISS:
                upper = resolve(x,y,upper_z)
                cache[pos_up] = upper
            solid = upper is None or upper[4]
            if solid and (rz < 0 or ceiling):
                if rz > 0:
                    pos_owner = x,y,old_z
                    owner = cache_get(pos_owner,_MISS)
                    if owner is _MISS:
                        owner = resolve(x,y,old_z)
                        cache[pos_owner] = owner
                else:
                    owner = upper
                return dist, owner, axis, (x,y,old_z), rz > 0
        if target is None:
            return None
        if target[3]:
            return dist,target,axis,(x,y,z),False
    return None


def camera(view, game, area):
    """Позиция, базис камеры и внутреннее разрешение кадра.

    Resolution table is per-quality; the GPU path overrides it through
    GPURays anyway, but the CPU raycaster is the hot path on low-end
    systems and on rotation-heavy frames where the cache misses.  Pure
    Python DDA costs ~1ms per 1000 cast rays, so each step down the table
    buys real FPS:
        quality 0 -> 120x?,  ~7.5k rays   (potato)
        quality 1 -> 200x?,  ~20k rays    (low)
        quality 2 -> 320x?,  ~53k rays    (default)
    """
    p = game.player
    world = getattr(game,'world',None)
    bx = p.chunk_x*world.w if world else 0
    by = p.chunk_y*world.h if world else 0
    z0 = p.world_z if world else 0
    origin = (bx+p.x+.5, by+p.y+.5, z0+.45)
    # Adaptive quality: drop a tier while the player is rotating.  During
    # a yaw change the geometry cache is invalidated every frame, so the
    # full-resolution cast is what produces the visible hitch.
    tier = view.quality
    if getattr(view, '_last_yaw', None) is not None and abs(view.yaw - view._last_yaw) > 1e-4:
        tier = max(0, tier - 1)
    view._last_yaw = view.yaw
    width = (120, 200, 320)[tier]
    height = max(1, round(width * area.h / max(1, area.w)))
    ca,sa = math.cos(view.yaw),math.sin(view.yaw)
    cp,sp = math.cos(view.pitch),math.sin(view.pitch)
    forward = (ca*cp,sa*cp,sp)
    right = (-sa,ca,0)
    up = (-ca*sp,-sa*sp,cp)
    return origin,forward,right,up,width,height,(bx,by,z0)


def geometry_key(view, game, area):
    """Ключ геометрии кадра: лучи пересчитываются только при его смене."""
    p = game.player
    world = getattr(game,'world',None)
    levels = tuple(sorted(
        (id(lv), lv.geometry_revision, lv.visual_manager.sync().geometry_revision,
         tuple(sorted((pos, tuple(sorted(d.items()))) for pos,d in lv.doors.items())),
         tuple((f.kind,f.x,f.y,f.rotated) for f in lv.furniture))
        for lv in (world.chunks.values() if world else [game.level])))
    return (id(game.level), p.x, p.y, p.world_z if world else 0,
            p.chunk_x if world else 0, p.chunk_y if world else 0,
            round(view.yaw,4), round(view.pitch,4), view.quality, area.size,
            view.show_ceiling, min(32,view.draw_distance), id(world), levels)


def cast_frame(view, game, area):
    """Лучевой проход: глубины, попадания и материалы по пикселям.

    Свет здесь намеренно не читается: раскраска (compose) берёт его заново,
    поэтому мерцание лампы не заставляет снова пускать лучи.
    """
    origin,forward,right,up,width,height,(bx,by,z0) = camera(view,game,area)
    depth_buffer = [float('inf')]*(width*height)
    hit_buffer = [None]*(width*height)
    pixels = [None]*(width*height)
    ctx = RayContext(game)
    from .display import RAY_PLANE
    focal = width/(2*RAY_PLANE)
    limit = min(32,view.draw_distance)
    materials = {}
    show_ceiling = view.show_ceiling
    # Hoist attribute lookups and bind locals — Python attribute access in
    # the inner loop is the dominant cost at 53k pixels per frame.
    resolve = ctx.resolve
    cache = ctx.cache
    cache_get = cache.get
    _miss = _MISS
    _inf = _INF
    _floor = _FLOOR
    # Precompute per-column horizontal direction components once.
    half_w = width * 0.5
    inv_focal = 1.0 / focal
    rx0, ry0, rz0 = right
    ux0, uy0, uz0 = up
    fx, fy, fz = forward
    col_x = [fx + ((sx + .5 - half_w) * inv_focal) * rx0 for sx in range(width)]
    col_y = [fy + ((sx + .5 - half_w) * inv_focal) * ry0 for sx in range(width)]
    col_z = [fz + ((sx + .5 - half_w) * inv_focal) * rz0 for sx in range(width)]
    ox, oy, oz = origin
    for sy in range(height):
        v = (height * 0.5 - sy - .5) * inv_focal
        row = sy * width
        vx = v * ux0
        vy = v * uy0
        vz = v * uz0
        for sx in range(width):
            # Inlined cast_fast.  Function call overhead at 53k rays * ~20
            # DDA steps eats a third of the frame time on its own.
            dx = col_x[sx] + vx
            dy = col_y[sx] + vy
            dz = col_z[sx] + vz
            px, py, pz = ox, oy, oz
            x = _floor(px); y = _floor(py); z = _floor(pz)
            sx_ = 1 if dx >= 0 else -1
            sy_ = 1 if dy >= 0 else -1
            sz_ = 1 if dz >= 0 else -1
            if dx > 1e-9: ax = 1.0/dx
            elif dx < -1e-9: ax = -1.0/dx
            else: ax = _inf
            if dy > 1e-9: ay = 1.0/dy
            elif dy < -1e-9: ay = -1.0/dy
            else: ay = _inf
            if dz > 1e-9: az = 1.0/dz
            elif dz < -1e-9: az = -1.0/dz
            else: az = _inf
            tx = (x+1-px if sx_>0 else px-x)*ax
            ty = (y+1-py if sy_>0 else py-y)*ay
            tz = (z+1-pz if sz_>0 else pz-z)*az
            hit = None
            for _ in range(160):
                old_z = z
                if tx<ty and tx<tz:
                    axis=0; dist=tx; tx+=ax; x+=sx_
                elif ty<tz:
                    axis=1; dist=ty; ty+=ay; y+=sy_
                else:
                    axis=2; dist=tz; tz+=az; z+=sz_
                if dist > limit:
                    break
                pos = (x,y,z)
                target = cache_get(pos,_miss)
                if target is _miss:
                    target = resolve(x,y,z)
                    cache[pos] = target
                if axis == 2:
                    upper_z = z if z > old_z else old_z
                    pos_up = (x,y,upper_z)
                    upper = cache_get(pos_up,_miss)
                    if upper is _miss:
                        upper = resolve(x,y,upper_z)
                        cache[pos_up] = upper
                    solid = upper is None or upper[4]
                    if solid and (dz < 0 or show_ceiling):
                        if dz > 0:
                            pos_owner = (x,y,old_z)
                            owner = cache_get(pos_owner,_miss)
                            if owner is _miss:
                                owner = resolve(x,y,old_z)
                                cache[pos_owner] = owner
                        else:
                            owner = upper
                        hit = (dist, owner, axis, (x,y,old_z), dz > 0)
                        break
                if target is None:
                    break
                if target[3]:
                    hit = (dist, target, axis, (x,y,z), False)
                    break
            if hit is None:
                continue
            dist,target,axis,pos,roof = hit
            if target is None:
                continue
            lv,lx,ly = target[:3]
            # UV on the wall face.  u is the position along the wall edge,
            # v is the height at the hit point.  These come from the exact
            # ray-wall intersection, not the cell corner.
            hit_x = ox + dx*dist
            hit_y = oy + dy*dist
            hit_z = oz + dz*dist
            if axis == 0:
                u = hit_y - ly  # along Y
            elif axis == 1:
                u = hit_x - lx  # along X
            else:
                u = hit_x - lx  # floor/ceiling use world XY
            v = hit_z - math.floor(hit_z)
            material_key = id(lv),lx,ly,axis==2,roof
            material = materials.get(material_key)
            if material is None:
                profile = getattr(lv,'profile',{})
                tex_name = None
                base = None
                fallback = None
                if axis==2:
                    # Floor/ceiling: pick texture by profile.
                    visual = ctx.grids[lv].floor_materials[ly*lv.w+lx]
                    tex_name = (profile.get('ceiling_texture','ceiling') if roof else
                                visual.material if visual is not None else 'carpet')
                    if roof and (lx,ly) in lv.ceiling_lamps:
                        base = (240,235,180)
                else:
                    visual = ctx.grids[lv].materials[ly*lv.w+lx]
                    tex_name = visual.material if visual is not None else 'wallpaper'
                    _,fallback = game.tile_glyph(lv,ctx.grids[lv].tiles[ly*lv.w+lx],lx,ly,0,False)
                material = (tex_name, base, axis, lv, lx, ly, fallback, roof)
                materials[material_key] = material
            pixels[row+sx]=(material,dist,u,v)
            depth_buffer[row+sx]=dist
            if pos[2]==z0:
                hit_buffer[row+sx]=(pos[0]-bx,pos[1]-by)
    return {"width":width,"height":height,"depth":depth_buffer,"hit":hit_buffer,
            "pixels":pixels,"forward":forward,"right":right,"up":up,"focal":focal,
            "origin":origin}


def compose(view, game, frame, area, r):
    """Раскраска по готовой геометрии; читает текущий свет и рисует биллборды.

    Material is (tex_name, base_color, axis, level, x, y, fallback_color).
    When tex_name is set, the pixel color comes from the procedural texture
    sampled at the UV stored during cast_frame; otherwise we fall back to
    the flat base color.
    """
    width, height = frame["width"], frame["height"]
    pixels = frame["pixels"]
    forward, right, up, focal = frame["forward"], frame["right"], frame["up"], frame["focal"]
    # Копия: биллборды пишут в буфер глубины, кэш геометрии должен остаться чистым.
    depth_buffer = frame["depth"][:]
    hit_buffer = frame["hit"]
    p = game.player
    image = pygame.Surface((width,height))
    image.fill(view.skybox)
    colors = {}
    # Lazy texture module import; numpy startup cost is paid once per session.
    from . import textures
    index = 0
    for sy in range(height):
        for sx in range(width):
            entry = pixels[index]
            index += 1
            if entry is None:
                continue
            material,dist,u,v = entry
            tex_name, base, axis, lv, x, y, fallback, roof = material
            light = lv.light_grid[x][y]
            # Sample texture or use flat color.  Quantize UV aggressively —
            # 8 buckets per tile is enough to read the pattern and keeps the
            # color cache tiny.
            if tex_name is not None and base is None:
                qu = round(u * 8) / 8
                qv = round(v * 8) / 8
                tex_key = (tex_name, qu, qv)
                tex_color = colors.get(tex_key)
                if tex_color is None:
                    tex_color = textures.sample(tex_name, qu, qv)
                    colors[tex_key] = tex_color
            elif base is not None:
                tex_color = base
            else:
                tex_color = fallback if fallback is not None else (128, 128, 128)
            key = (tex_color, round(dist*4), round(light*32), axis)
            color = colors.get(key)
            if color is None:
                color = view.color(tex_color,dist,.8 if axis==1 else 1,light,getattr(lv,'profile',None))
                colors[key]=color
            # Wet-floor sheen: light pools under ceiling lamps reflect on the
            # carpet at grazing angles.  Cheap approximation — no extra ray,
            # just an additive term driven by existing light and the screen
            # row's vertical angle (rows near the horizon graze the floor).
            if axis == 2 and not roof and light > 0.35:
                profile_ = getattr(lv, 'profile', None)
                if profile_ and profile_.get('wet_floor'):
                    pitch_ray = (height * 0.5 - sy - 0.5) / focal
                    grazing = 1.0 - min(1.0, abs(pitch_ray) * 2.2)
                    spec = light * light * grazing
                    if spec > 0.02:
                        boost = int(90 * spec)
                        color = (min(255, color[0] + boost),
                                 min(255, color[1] + int(boost * 0.94)),
                                 min(255, color[2] + int(boost * 0.7)))
            image.set_at((sx,sy),color)
    # Billboards use the same rotated camera and per-pixel depth as geometry.
    sprites=collect_sprites(game, getattr(view, 'visual_objects', None))
    overlay=getattr(game,'debug_overlay',None)
    boxes=[]
    for x,y,glyph,color,z,h,light in sorted(sprites,key=lambda s:(s[0]-p.x)**2+(s[1]-p.y)**2,reverse=True):
        offset=(x-p.x,y-p.y,z-.45)
        d=sum(a*b for a,b in zip(offset,forward))
        if d<=.1:
            continue
        cx=width/2+sum(a*b for a,b in zip(offset,right))*focal/d
        cy=height/2-sum(a*b for a,b in zip(offset,up))*focal/d
        size=max(1,min(height*2,int(h*focal/d)))
        sprite=r.visual(glyph,view.color(color,d,light=light),True,size=(size,size))
        left,top=int(cx-size/2),int(cy-size/2)
        if overlay is not None and overlay.enabled and 'sprites' in overlay.modes:
            sx0=area.x+int(left*area.w/width)
            sy0=area.y+int(top*area.h/height)
            boxes.append(pygame.Rect(sx0,sy0,max(1,int(size*area.w/width)),max(1,int(size*area.h/height))))
        for yy in range(max(0,top),min(height,top+size)):
            for xx in range(max(0,left),min(width,left+size)):
                index=yy*width+xx
                if d<depth_buffer[index] and sprite.get_at((xx-left,yy-top)).a:
                    image.blit(sprite,(xx,yy),(xx-left,yy-top,1,1))
                    depth_buffer[index]=d
                    hit_buffer[index]=(x,y)
    if overlay is not None:
        overlay.note_sprites(len(sprites), boxes)
    r.surface.blit(pygame.transform.scale(image, area.size), area)
    view.volume_hits=(width,height,hit_buffer)
    view.picks=[]
    # Run-length picking spans reduce allocation without losing pixel accuracy.
    for y in range(height):
        start=0
        while start<width:
            pos=hit_buffer[y*width+start]
            end=start+1
            while end<width and hit_buffer[y*width+end]==pos:
                end+=1
            if pos is not None:
                view.picks.append((pygame.Rect(area.x+start*area.w//width,area.y+y*area.h//height,
                                               math.ceil((end-start)*area.w/width),math.ceil(area.h/height)),pos))
            start=end
    pygame.draw.line(r.surface,CROSS,(area.centerx-4,area.centery),(area.centerx+4,area.centery))
    pygame.draw.line(r.surface,CROSS,(area.centerx,area.centery-4),(area.centerx,area.centery+4))


def draw(view, game):
    area, r, p = view.rect, game.r, game.player
    overlay=getattr(game,'debug_overlay',None)
    started=time.perf_counter()
    display=getattr(game,'display',None)
    # GPU scene renders on top of the canvas in _present_opengl, which means
    # any modal UI (action wheel, dialogs, inventory) drawn to the canvas
    # would be hidden underneath the 3D view.  Only use the GPU scene in
    # pure gameplay mode; fall back to CPU rays when a modal is open.
    gpu_allowed = (
        display is not None
        and display.backend=='opengl'
        and not getattr(display,'ray_error',None)
        and (getattr(game, 'mode', 'play') == 'play'
             or (display.gl_renderer is not None and display.gl_renderer.active))
    )
    if gpu_allowed:
        try:
            if getattr(display,'rays',None) is None:
                from .gpu_rays import GPURays
                display.rays=GPURays(display.gl)
            origin,forward,right,up,width,height,_ = camera(view,game,area)
            frame = area
            texture=display.rays.render(view,game,width,height,origin,forward,right,up,direct=True)
            if overlay is not None:
                overlay.note_sprites(len(collect_sprites(game, getattr(view, 'visual_objects', None))))
                overlay.mark('gpu-rays', (time.perf_counter()-started)*1000)
            display.scene=(texture,frame.copy())
            display.fbo_size=(width,height)
            if overlay is not None:
                overlay.fbo_size=(width,height)
            # Leave the CPU view black.  The GPU texture is presented on top
            # of this canvas, so the opaque UI still covers the borders.
            r.surface.fill((0, 0, 0), area)
            view.gpu_picker=lambda pos: display.rays.pick(*pos,frame,game)
            view.picks=[]
            pygame.draw.line(r.surface,CROSS,(area.centerx-4,area.centery),(area.centerx+4,area.centery))
            pygame.draw.line(r.surface,CROSS,(area.centerx,area.centery-4),(area.centerx,area.centery+4))
            return
        except Exception as exc:
            display.ray_error=str(exc)
            display.gl.glUseProgram(0)
            display.gl.glBindFramebuffer(display.gl.GL_FRAMEBUFFER,0)
            game.msg('GPU rays fallback: '+str(exc), (222,190,78))
    elif display is not None and display.backend == 'opengl':
        # Modal is open over the first-person view: present through canvas so
        # the UI stays visible.  Discard the cached GPU scene for this frame.
        display.scene = None
    key = geometry_key(view, game, area)
    frame = getattr(view,'_volume_cast',None)
    cast_started=time.perf_counter()
    if frame is None or getattr(view,'_volume_cast_key',None) != key:
        frame = cast_frame(view, game, area)
        view._volume_cast = frame
        view._volume_cast_key = key
    composed=time.perf_counter()
    compose(view, game, frame, area, r)
    if overlay is not None:
        overlay.mark('cast', (composed-cast_started)*1000)
        overlay.mark('compose', (time.perf_counter()-composed)*1000)


def visible_visuals(game):
    """One world-space source for both views and billboard renderers."""
    from .visual import VisualCamera
    world = getattr(game, 'world', None)
    groups = {}
    if world:
        for lv, lx, ly in getattr(game, 'visible_world', {}).values():
            groups.setdefault(lv, set()).add((lv.chunk_x*lv.w+lx, lv.chunk_y*lv.h+ly, lv.world_z))
    else:
        lv = game.level
        groups[lv] = {(lv.chunk_x*lv.w+x, lv.chunk_y*lv.h+y, lv.world_z) for x, y in lv.visible}
    result = []
    for lv, cells in groups.items():
        result.extend((lv, v) for v in lv.visual_manager.iter_visible(VisualCamera(cells=frozenset(cells))))
    result.sort(key=lambda pair: (pair[1].layer, pair[1].z, pair[1].y))
    return result


def collect_sprites(game, visuals=None):
    world = getattr(game, 'world', None)
    p = game.player
    bx, by, bz = (p.chunk_x*world.w, p.chunk_y*world.h, p.world_z) if world else (0, 0, 0)
    sprites = []
    for lv, v in (visible_visuals(game) if visuals is None else visuals):
        if v.layer not in (2, 3, 4) or v.opaque or v.sprite_id is None:
            continue
        x, y = v.x + v.width/2 - .5 - bx, v.y + v.depth/2 - .5 - by
        if v.layer == 2 and v.tile_id is None and v.x <= bx+p.x < v.x+v.width and v.y <= by+p.y < v.y+v.depth:
            continue
        lx = min(lv.w-1, max(0, int(v.x-lv.chunk_x*lv.w)))
        ly = min(lv.h-1, max(0, int(v.y-lv.chunk_y*lv.h)))
        light = 1.0 if v.emits_light else lv.light_grid[lx][ly]
        sprites.append((x, y, v.sprite_id, v.color, v.z+v.height/2-bz, v.height, light))
    return sprites


CROSS=(86,186,194)
