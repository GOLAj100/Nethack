"""Software 3D: DDA first-person view and orbitable orthographic dungeon."""
import math
from functools import lru_cache
import pygame
from . import config as C
from .shaders import shade


class Views:
    def __init__(self):
        self.mode = "ascii"
        self.yaw = -math.pi / 2
        self.orbit = 0.65
        self.tilt = 0.85
        self.pitch = 0.0
        self.draw_distance = C.FOV_RADIUS * 4
        self.zoom = 1.0
        self.lighting = True
        self.fog = True
        self.outlines = False
        self.full_map = False
        self.single_layer = True
        self.quality = 1
        self.skybox = (13, 19, 32)
        self.ceiling_color = (8, 8, 14)
        self.show_ceiling = True
        self.picks = []
        self.columns = []
        self._board_key = None
        self._board_geometry = None
        self.board_polygons = []
        self.free_camera = False
        self.world_camera = [0, 0, 0]
        self._world_board_key = None
        self._world_board_image = None

    def turn(self, amount):
        if self.mode == "first":
            self.yaw = (self.yaw + amount) % math.tau
        else:
            self.orbit = (self.orbit + amount) % math.tau

    def color(self, color, distance=0, normal=1, light=1.0, profile=None):
        return shade(color, distance, normal, light, self.lighting, self.fog, profile)

    def pick(self, pos):
        if self.mode=='first' and getattr(self,'gpu_picker',None) is not None:
            return self.gpu_picker(pos)
        for rect, world in reversed(self.picks):
            if rect.collidepoint(pos):
                return world
        if self.mode == "first":
            for rect, world in self.columns:
                if rect.collidepoint(pos):
                    return world
        return None

    def draw(self, game):
        r = game.r
        from .volume import visible_visuals
        self.visual_objects = visible_visuals(game)
        # Pixel viewport fills under the HUD to the canvas edge. ASCII stays
        # on the cell grid so glyphs do not draw past a partial cell.
        if self.mode != "ascii":
            self.rect = game._sync_layout()[0].copy()
        else:
            self.rect = r.cell_rect(0, game.map_offset_y, game.camera_w, game.camera_h)
        old = r.surface.get_clip()
        r.surface.set_clip(self.rect)
        self.picks = []
        self.columns = []
        r.surface.fill(self.skybox, self.rect)
        if getattr(game.level,'profile',{}).get('absolute_darkness'):
            # Anomalous darkness overrides graphics toggles and GPU rendering.
            self.gpu_picker = None
            r.surface.fill((0,0,0),self.rect)
            r.surface.set_clip(old)
            return
        if self.mode == "first":
            self.first(game)
        elif getattr(game, "world", None) is not None:
            self.world_board(game)
        else:
            self.board(game)
        # Post-processing runs after the 3D image but before the HUD, so
        # text stays sharp.  Effects come from the level profile.
        profile = getattr(game.level, 'profile', {}) or {}
        effects = profile.get('postfx')
        if effects and self.mode == 'first':
            from .postfx import PostFX
            if getattr(game, '_postfx', None) is None:
                game._postfx = PostFX()
            game._postfx.apply(r.surface, self.rect, effects)
        r.surface.set_clip(old)

    def entities(self, game):
        from .volume import visible_visuals
        for lv, visual in visible_visuals(game):
            if visual.layer >= 2 and visual.sprite_id is not None and not visual.opaque:
                yield (visual.x-lv.chunk_x*lv.w, visual.y-lv.chunk_y*lv.h,
                       visual.sprite_id, visual.color)

    def ray_cell(self, game, gx, gy):
        """Return (level, local_x, local_y) for a first-person world cell.

        The old DDA treated the edge of the active 80x50 chunk as an opaque
        wall. Level 0 rays now resolve the next chunk through World instead.
        """
        lv = game.level
        world = getattr(game, "world", None)
        if world is None or lv.depth != 0:
            return (lv, gx, gy) if lv.in_bounds(gx, gy) else None
        cx, lx = divmod(gx, world.w)
        cy, ly = divmod(gy, world.h)
        target = world.chunk(cx, cy, game.player.world_z)
        if target is None:
            return None
        return target, lx, ly

    def first(self, game):
        from .volume import draw
        p=game.player
        levels = list(game.world.chunks.values()) if game.world else [game.level]
        visual_state = tuple((id(lv), lv.visual_manager.sync().revision) for lv in levels)
        state=(id(game.level),id(getattr(game,'display',None)),getattr(getattr(game,'display',None),'backend',None),getattr(getattr(game,'display',None),'generation',0),p.x,p.y,p.world_z,p.chunk_x,p.chunk_y,p.turns,
               self.yaw,self.pitch,self.quality,self.draw_distance,self.lighting,self.fog,
               self.show_ceiling,self.outlines,self.skybox,self.rect,
               game.r.tileset.enabled,game.r.tileset.auto_color,game.r.tileset.revision,
               round(game.lamp_flicker_modifier*32),
               tuple(sorted((id(lv),lv.lighting_revision) for lv in
                            (game.world.chunks.values() if game.world else [game.level]))),
               game.level.geometry_revision,tuple(sorted(game.level.visible)),
               tuple((f.kind,f.x,f.y,f.rotated) for f in game.level.furniture),
               tuple((pos,id(it)) for pos,it in game.level.items.items()),
               tuple((id(m),m.x,m.y,m.hp) for m in game.level.monsters),
               # Mode must bust the cache: opening a modal (action wheel,
               # inventory, settings) draws UI over the canvas.  Returning a
               # stale frame on close leaves the modal ghost painted into the
               # cached scene and skips fresh world rendering.
                game.mode, visual_state)
        if state==getattr(self,'_volume_state',None):
            if getattr(self, '_volume_scene', None) is not None and game.display:
                game.display.scene = self._volume_scene
                self.picks = self._volume_picks
                return
            game.r.surface.blit(self._volume_frame,self.rect)
            self.picks=self._volume_picks
            if getattr(self,'_volume_scene',None) is not None and game.display:
                game.r.surface.fill((0,0,0,0),self.rect)
                game.r.surface.blit(self._volume_frame,self.rect)
                game.display.scene=self._volume_scene
            return
        self.gpu_picker=None
        draw(self, game)
        self._volume_state=state
        self._volume_picks=self.picks
        self._volume_scene=getattr(getattr(game,'display',None),'scene',None)
        self._volume_frame = (None if self._volume_scene is not None else
                              game.r.surface.subsurface(self.rect).copy())
        return

    def invalidate(self):
        """Drop cached frame/scene.  Call after modal close, backend switch,
        resize, or any event that changes what the next frame must contain."""
        self._volume_state=None
        self._volume_frame=None
        self._volume_picks=None
        self._volume_scene=None

    def first_legacy(self, game):
        """Legacy flat-storey renderer retained for comparison/profiling."""
        lv, p, r = game.level, game.player, game.r
        area = self.rect
        # Pitch is a camera rotation: it moves the vanishing point, while each
        # wall edge is projected independently from its world height.  This is
        # deliberately kept in the view layer; light_grid remains authoritative
        # for all surface colours.
        horizon = int(area.centery + self.pitch * area.h * 0.35)
        profile = getattr(lv, 'profile', {}) or {}
        floor_base = tuple(profile.get('floor_color', (62, 65, 78)))
        ceiling_base = tuple(profile.get('ceiling_color', (8, 8, 14)))
        pygame.draw.rect(r.surface, self.skybox, area)
        if getattr(game, "world", None) is not None and lv.depth == 0:
            origin_x = p.chunk_x * game.world.w + p.x
            origin_y = p.chunk_y * game.world.h + p.y
        else:
            origin_x, origin_y = p.x, p.y
        px, py = origin_x + 0.5, origin_y + 0.5
        dx, dy = math.cos(self.yaw), math.sin(self.yaw)
        plane = 0.66
        focal = area.w / (2 * plane)
        eye_z = 0.45
        ceiling_z = 0.85
        # A first-person ray must never keep walking through the streamed
        # world.  In particular, an open Level-0 seam can otherwise make DDA
        # discover geometry in several neighbouring chunks and paint it over
        # the same screen column.  Keep the user setting as the lower limit,
        # but enforce a finite near-world horizon for this renderer.
        max_depth = min(20.0, max(1.0, float(getattr(self, "draw_distance", 20))))

        def projected_edges(distance):
            """Screen edges of the room cube at *distance*."""
            top = int(horizon - focal * (ceiling_z - eye_z) / max(0.05, distance))
            bottom = int(horizon + focal * eye_z / max(0.05, distance))
            return top, bottom

        def plane_sample(world_x, world_y, fallback):
            """Get floor light and color without exposing unexplored cells."""
            if getattr(game, "world", None) is not None:
                # visible_world uses coordinates relative to the active chunk;
                # the ray origin is expressed in streamed global coordinates.
                local = (world_x - game.player.chunk_x * game.world.w,
                         world_y - game.player.chunk_y * game.world.h)
                cell = getattr(game, "visible_world", {}).get(local)
                if cell is None:
                    return fallback, 0.035
                hit_lv, hx, hy = cell
                return floor_base, hit_lv.light_grid[hx][hy]
            if not lv.in_bounds(world_x, world_y) or (world_x, world_y) not in lv.visible:
                return fallback, 0.035
            return floor_base, lv.light_grid[world_x][world_y]

        def draw_planes():
            """Perspective-correct floor and ceiling, sampled per world cell."""
            # The camera is above floor z=0 and below ceiling z=ceiling_z.
            # Plane shading is deliberately coarser than wall DDA. A 3x4
            # block is below the character-cell scale, avoids hundreds of
            # thousands of draw calls, and still gives a clear perspective.
            step_y = 5 if self.quality > 0 else 8
            plane_stride = max(stride, 10 if self.quality > 0 else 16)
            for sy in range(area.top, area.bottom, step_y):
                if sy == horizon:
                    continue
                below = sy > horizon
                if not below and not self.show_ceiling:
                    continue
                height = eye_z if below else ceiling_z - eye_z
                depth = focal * height / max(0.5, abs(sy - horizon))
                if depth > max_depth:
                    continue
                for sx in range(0, area.w, plane_stride):
                    cam = 2 * (sx + plane_stride * 0.5) / area.w - 1
                    ray_x = dx - dy * plane * cam
                    ray_y = dy + dx * plane * cam
                    wx = math.floor(px + ray_x * depth)
                    wy = math.floor(py + ray_y * depth)
                    base, light = plane_sample(wx, wy, ceiling_base if not below else floor_base)
                    if not below:
                        base = ceiling_base
                    col = self.color(base, depth, 1.0, light)
                    pygame.draw.rect(r.surface, col, (sx, sy, plane_stride, step_y))
        stride = (6, 3, 1)[self.quality]
        draw_planes()
        depths = [100.0] * area.w
        for sx in range(0, area.w, stride):
            camera = 2 * (sx + stride / 2) / area.w - 1
            rx, ry = dx - dy * plane * camera, dy + dx * plane * camera
            mx, my = origin_x, origin_y
            ax, ay = abs(1 / rx) if rx else 1e10, abs(1 / ry) if ry else 1e10
            stepx, stepy = (1 if rx >= 0 else -1), (1 if ry >= 0 else -1)
            tx = ((mx + 1 - px) if rx >= 0 else px - mx) * ax
            ty = ((my + 1 - py) if ry >= 0 else py - my) * ay
            distance, side = 50.0, 0
            hit_cell = None
            for _ in range(int(max_depth * 2) + 4):
                if tx < ty:
                    distance, tx, mx, side = tx, tx + ax, mx + stepx, 0
                else:
                    distance, ty, my, side = ty, ty + ay, my + stepy, 1
                if distance > max_depth:
                    hit_cell = None
                    break
                hit_cell = self.ray_cell(game, mx, my)
                if hit_cell is None:
                    break
                hit_lv, hit_x, hit_y = hit_cell
                if not hit_lv.can_see_through(hit_x, hit_y):
                    break
            distance = max(0.05, distance)
            for col in range(sx, min(area.w, sx + stride)):
                depths[col] = distance
            if hit_cell is None:
                continue
            # The first opaque cell is the only surface this column can see.
            # DDA has already stopped, so no geometry behind this wall can be
            # painted from another streamed chunk.
            top_y, bottom_y = projected_edges(distance)
            top_y = max(area.top - area.h * 4, min(area.bottom + area.h * 4, top_y))
            bottom_y = max(area.top - area.h * 4, min(area.bottom + area.h * 4, bottom_y))
            wall = pygame.Rect(sx, top_y, stride, max(1, bottom_y - top_y))
            if hit_cell is None:
                hit_lv, hit_x, hit_y = lv, p.x, p.y
            tile = hit_lv.at(hit_x, hit_y)
            _, base = game.tile_glyph(hit_lv, tile, hit_x, hit_y, 0, False)
            light = hit_lv.light_grid[hit_x][hit_y] if hit_lv.in_bounds(hit_x, hit_y) else 0.05
            color = self.color(base, distance, 0.72 if side else 1.0, light)
            pygame.draw.rect(r.surface, color, wall)
            # Vertical mortar lines make orientation and wall depth visible.
            hit = (py + distance * ry) if not side else (px + distance * rx)
            if self.outlines and hit % 1 < 0.04:
                pygame.draw.rect(r.surface, self.color(base, distance, 0.4, light), wall)
            if hit_cell is not None:
                self.columns.append((wall.clip(area), (mx-origin_x+p.x, my-origin_y+p.y)))
        sprites = list(self.entities(game))
        # Stairs, fountains and other floor features remain discoverable.
        for x, y in lv.visible:
            if lv.at(x, y) not in (0, 1, 2, 8) and (x, y) != (p.x, p.y):
                glyph, color = game.tile_glyph(lv, lv.at(x, y), x, y, 0, False)
                sprites.append((x, y, glyph, color))
        if getattr(game, "world", None) is not None:
            sprites = []
            for (x,y),(source,lx,ly) in game.visible_world.items():
                if self.show_ceiling and (lx,ly) in source.ceiling_lamps:
                    sprites.append((x,y,'*',C.YELLOW))
                if source.at(lx,ly) not in (0,1,2,8) and (x,y) != (p.x,p.y):
                    glyph,color = game.tile_glyph(source,source.at(lx,ly),lx,ly,0,False)
                    sprites.append((x,y,glyph,color))
                if (lx,ly) in source.corpses:
                    sprites.append((x,y,"%",C.DARK_RED))
                item = source.items.get((lx,ly))
                if item is not None:
                    sprites.append((x,y,item.glyph,item.color))
                monster = source.monster_at(lx,ly)
                if monster is not None:
                    sprites.append((x,y,monster.glyph,monster.color))
        sprites.sort(key=lambda e: (e[0] - p.x)**2 + (e[1] - p.y)**2, reverse=True)
        for x, y, glyph, color in sprites:
            vx, vy = x - p.x, y - p.y
            depth, lateral = vx * dx + vy * dy, -vx * dy + vy * dx
            if depth <= 0.15:
                continue
            size = max(4, min(area.h * 2, int(focal * 0.65 / depth)))
            cx = int(area.centerx + lateral * focal / depth)
            light = lv.light_grid[x][y] if lv.in_bounds(x, y) else 0.05
            if (x,y) in getattr(game,"visible_world",{}):
                source,lx,ly = game.visible_world[x,y]
                light = source.light_grid[lx][ly]
            image = r.visual(glyph, self.color(color, depth, light=light), True, size=(size,size))
            if glyph == '*':
                # Ceiling lamps live on the ceiling plane, rather than at the
                # player horizon like ordinary floor sprites.
                lamp_y = int(horizon - focal * (ceiling_z - eye_z) / depth)
                top = lamp_y - size // 2
            else:
                top = horizon - size // 2
            left = cx - size // 2
            for col in range(max(0, left), min(area.w, left + size)):
                if depth < depths[col]:
                    r.surface.blit(image, (col, top), (col - left, 0, 1, size))
                    self.picks.append((pygame.Rect(col, top, 1, size).clip(area), (x, y)))
        pygame.draw.line(r.surface, C.CYAN, (area.centerx-5, horizon), (area.centerx+5, horizon))
        pygame.draw.line(r.surface, C.CYAN, (area.centerx, horizon-5), (area.centerx, horizon+5))

    def board(self, game):
        lv, r, p = game.level, game.r, game.player
        visual_grid = lv.visual_manager.grid()
        ca, sa = math.cos(self.orbit), math.sin(self.orbit)
        st, ct = math.sin(self.tilt), math.cos(self.tilt)
        extent = max(lv.w, lv.h) * 1.42
        scale = min(self.rect.w, self.rect.h) / extent * self.zoom

        def project(x, y, z):
            x, y = x - lv.w / 2, y - lv.h / 2
            a, b = x * ca - y * sa, x * sa + y * ca
            return (self.rect.centerx + a * scale,
                    self.rect.centery + (b * st - z * ct) * scale)

        known = ({(x, y) for y in range(lv.h) for x in range(lv.w)}
                 if self.full_map else lv.explored | lv.mapped)
        key = (lv.w, lv.h, round(self.orbit, 5), round(self.tilt, 5),
               round(self.zoom, 5), self.full_map, len(lv.explored), len(lv.mapped),
               lv.visual_manager.revision)
        if key == self._board_key and self._board_geometry is not None:
            faces = self._board_geometry
        else:
            faces = []
            for x, y in known:
                wall = bool(visual_grid.walls[y*lv.w+x])
                z = 0.85 if wall else 0
                _, base = game.tile_glyph(lv, visual_grid.tiles[y*lv.w+x], x, y, 0, False)
                if not wall and visual_grid.tiles[y*lv.w+x] == 1:
                    base = (62, 77, 89) if (x + y) % 2 else (46, 57, 72)
                distance = math.hypot(x - p.x, y - p.y) if not self.full_map else 3
                corners = [(x, y), (x+1, y), (x+1, y+1), (x, y+1)]
                top = [project(a, b, z) for a, b in corners]
                bottom = [project(a, b, -0.25) for a, b in corners]
                depth = ((x + 0.5 - lv.w/2)*sa + (y + 0.5 - lv.h/2)*ca)*ct + z*st
                faces.append((depth, top if st >= 0 else bottom, base, distance, 1.0, (x, y)))
                for i in range(4):
                    j = (i + 1) % 4
                    if wall or (x in (0, lv.w-1) or y in (0, lv.h-1)):
                        faces.append((depth - 0.01, [top[i], top[j], bottom[j], bottom[i]],
                                      base, distance, 0.55 + 0.1*(i%2), (x, y)))
            faces.sort(key=lambda f: f[0])
            self._board_key = key
            self._board_geometry = faces
        # Lighting changes every frame, geometry and painter order do not.
        self.board_polygons = []
        for _, poly, base, distance, normal, pos in faces:
            x, y = pos
            light = lv.light_grid[x][y]
            color = self.color(base, distance, normal, light)
            pygame.draw.polygon(r.surface, color, poly)
            if self.outlines:
                pygame.draw.polygon(r.surface, (20, 29, 42), poly, 1)
            self.board_polygons.append((poly, pos))
        for x, y, glyph, color in [*self.entities(game), (p.x, p.y, "@", C.WHITE)]:
            sx, sy = project(x+0.5, y+0.5, 1.05 if st >= 0 else -0.3)
            image = r.visual(glyph, color, True)
            rect = image.get_rect(center=(sx, sy))
            light = lv.light_grid[int(x)][int(y)] if lv.in_bounds(x, y) else 0.05
            image = r.visual(glyph, self.color(color, light=light), True)
            rect = image.get_rect(center=(sx, sy))
            r.surface.blit(image, rect)
            self.picks.append((rect, (x, y)))

    def board_pick(self, pos):
        if self.free_camera:
            return None
        found = self.pick(pos)
        if found:
            return found
        if getattr(self,'gpu_board_picker',None) is not None:
            return self.gpu_board_picker(pos)
        for poly, world in reversed(getattr(self, "board_polygons", [])):
            # Convex projected quad: all cross-products have the same sign.
            signs = []
            for a, b in zip(poly, poly[1:] + poly[:1]):
                signs.append((b[0]-a[0])*(pos[1]-a[1]) - (b[1]-a[1])*(pos[0]-a[0]))
            if max(signs) > 0 and min(signs) >= 0 or min(signs) < 0 and max(signs) <= 0:
                return world
        return None

    def world_board(self, game):
        """Terrain-only 80x50 window; at most five existing World Z slices."""
        from game.lang import t
        world, r, p = game.world, game.r, game.player
        cx, cy, focus_z = (self.world_camera if self.free_camera else
                            (p.chunk_x, p.chunk_y, p.world_z))
        layers = [world.chunk(cx, cy, z) for z in
                  ([focus_z] if getattr(self,'single_layer',False) else world.visible_z(focus_z))]
        visual_grids = {lv: lv.visual_manager.grid() for lv in layers}
        # No dynamic entities/lighting: this is a terrain inspection view.
        key = (id(world), cx, cy, focus_z, self.orbit, self.tilt, self.zoom, self.full_map,
               self.outlines, self.rect.size, p.world_z,
               tuple((lv.world_z,lv.visual_manager.revision,tuple((f.kind,f.x,f.y,f.rotated) for f in lv.furniture),frozenset(lv.explored),frozenset(lv.mapped),
                      tuple(sorted((pos,tuple(sorted(d.items()))) for pos,d in lv.doors.items()))) for lv in layers))
        ca, sa = math.cos(self.orbit), math.sin(self.orbit)
        st, ct = math.sin(self.tilt), math.cos(self.tilt)
        scale = min(self.rect.w, self.rect.h) / (max(world.w, world.h)*1.42) * self.zoom

        @lru_cache(maxsize=None)
        def project(x, y, z):
            x, y = x-world.w/2, y-world.h/2
            a, b = x*ca-y*sa, x*sa+y*ca
            return (self.rect.w/2+a*scale, self.rect.h/2+(b*st-z*ct)*scale)

        gpu=False
        self.gpu_board_picker=None
        display=getattr(game,'display',None)
        if display is not None and display.backend=='opengl' and not display.board_error:
            try:
                if display.board is None:
                    from .gpu_board import GPUBoard
                    display.board=GPUBoard(display.gl)
                display.board.draw(self,game,layers,focus_z,scale)
                self.gpu_board_picker=lambda pos: display.board.pick(self,game,pos)
                self.board_polygons=[]
                gpu=True
            except Exception as exc:
                display.board_error=str(exc)
                display.gl.glBindFramebuffer(display.gl.GL_FRAMEBUFFER,0)
                display.gl.glDisable(display.gl.GL_DEPTH_TEST)
                game.msg('GPU board fallback: '+str(exc),C.MSG_WARN)
        if not gpu and key != self._world_board_key:
            surface = pygame.Surface(self.rect.size)
            surface.fill((13, 19, 32))
            faces = []
            for lv in layers:
                grid = visual_grids[lv]
                known = lv.explored | lv.mapped
                base_z = (lv.world_z-focus_z)*4
                for y in range(lv.h):
                    run_end = 0
                    for x in range(lv.w):
                        if grid.tiles[y*lv.w+x]==10:
                            continue
                        if not self.full_map and (x,y) not in known:
                            continue
                        wall = bool(grid.walls[y*lv.w+x])
                        height = base_z + (0.85 if wall else 0)
                        if grid.fixtures[y*lv.w+x] is not None and not wall: height=base_z+.5
                        _, color = game.tile_glyph(lv, grid.tiles[y*lv.w+x], x,y,0,True)
                        depth = ((x+.5-lv.w/2)*sa+(y+.5-lv.h/2)*ca)*ct + height*st
                        # Merge coplanar row runs when grid outlines are off.
                        # Individual tiles remain available for inspected maps.
                        if x>=run_end:
                            run_end=x+1
                            if not self.outlines and self.full_map:
                                while (run_end<lv.w and grid.tiles[y*lv.w+run_end]==grid.tiles[y*lv.w+x]
                                       and grid.walls[y*lv.w+run_end]==grid.walls[y*lv.w+x]):
                                    run_end+=1
                            corners=[(x,y),(run_end,y),(run_end,y+1),(x,y+1)]
                            surface_z=height if st>=0 else base_z-.25
                            poly=[project(a,b,surface_z) for a,b in corners]
                            faces.append((depth,poly,color,(x,y),lv.world_z))
                        if wall or grid.fixtures[y*lv.w+x] is not None:
                            for i,(nx,ny) in enumerate(((x,y-1),(x+1,y),(x,y+1),(x-1,y))):
                                # Orthographic back-face culling: only the two
                                # sides facing the camera can be visible.
                                if (ca, -sa, -ca, sa)[i]*ct <= 0:
                                    continue
                                if lv.in_bounds(nx,ny) and grid.walls[ny*lv.w+nx]:
                                    continue
                                corners=[(x,y),(x+1,y),(x+1,y+1),(x,y+1)]
                                j=(i+1)%4
                                a,b=corners[i],corners[j]
                                faces.append((depth-.01,[project(*a,height),project(*b,height),
                                                        project(*b,base_z-.25),project(*a,base_z-.25)],
                                              tuple(int(c*.65) for c in color),(x,y),lv.world_z))
            self.board_polygons = []
            for _,poly,color,pos,z in sorted(faces,key=lambda f:f[0]):
                if (max(v[0] for v in poly)<0 or min(v[0] for v in poly)>self.rect.w
                        or max(v[1] for v in poly)<0 or min(v[1] for v in poly)>self.rect.h):
                    continue
                pygame.draw.polygon(surface,color,poly)
                if self.outlines:
                    pygame.draw.polygon(surface,(40,36,24),poly,1)
                if (cx,cy,z)==(p.chunk_x,p.chunk_y,p.world_z):
                    self.board_polygons.append(([(x+self.rect.x,y+self.rect.y) for x,y in poly],pos))
            self._world_board_image = surface
            self._world_board_key = key
        if not gpu:
            r.surface.blit(self._world_board_image,self.rect)
        self.picks = []
        if (cx, cy, focus_z) == (p.chunk_x, p.chunk_y, p.world_z):
            px, py = project(p.x + 0.5, p.y + 0.5, 1.05 if st >= 0 else -0.3)
            marker = r.visual("@", C.WHITE, True)
            marker_rect = marker.get_rect(center=(self.rect.x + px, self.rect.y + py))
            r.surface.blit(marker, marker_rect)
            self.picks.append((marker_rect, (p.x, p.y)))
        r.text(1,C.TOPBAR_H,f"B-Level {world.b_level} | X {cx*world.w} Y {cy*world.h} Z {focus_z} | {len(layers)}/5",C.WHITE,max_cells=48)
        r.text(1,C.TOPBAR_H+1,t("world.camera"),C.YELLOW,max_cells=48)
