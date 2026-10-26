"""Мир: переходы между чанками и уровнями, лестницы, двери, свет и карта."""
from __future__ import annotations

import random

import pygame

from engine import config as C
from engine import fov as F
from . import mapgen as MG
from . import monsters as MON
from .lang import save_settings, t
from .workshop import Workshop
from .world import World


def debug_change_z(game, delta):
        if not game.player.debug_fly or game.world is None:
            return False
        z = game.player.world_z + delta
        if not game.world.exists(z):
            game.msg(t('debug.no_z'), C.MSG_HINT)
            return False
        target = game.world.chunk(game.player.chunk_x, game.player.chunk_y, z)
        if not game.player.debug_noclip and (not target.is_walkable(game.player.x, game.player.y)
                                           or target.monster_at(game.player.x, game.player.y)):
            game.msg(t('m.wall'), C.MSG_HINT)
            return False
        game.player.world_z = z
        game.level = game.world.chunk(game.player.chunk_x, game.player.chunk_y, z, visit=True)
        game._visible_world_key = None
        game.visible_world = {}
        game.tooltip = None
        game.floats.clear()
        game.level.set_player_pos(game.player.x, game.player.y)
        game.level.recompute_fov(game.player.x, game.player.y)
        game.update_lighting()
        game.msg(t('debug.z_changed', z=z), C.MSG_GOOD)
        return True


def cross_chunk(game, nx, ny):
        p = game.player
        ox, x = divmod(nx, game.world.w)
        oy, y = divmod(ny, game.world.h)
        cx, cy = p.chunk_x + ox, p.chunk_y + oy
        target = game.world.chunk(cx, cy, p.world_z)
        monster = target.monster_at(x, y)
        if monster is not None:
            game.player_attack(monster, level=target)
            game.end_turn()
            return True
        if not target.is_walkable(x, y):
            game.msg(t("m.wall"), C.MSG_HINT)
            game.end_turn()
            return True
        if target.at(x, y) == MG.DOOR:
            door = target.doors.setdefault((x, y), {'open': False, 'locked': False, 'broken': False})
            if not door.get('open') and not door.get('broken'):
                door['open'] = True
                game.world.visited.add((cx, cy, p.world_z))
                game.msg(t('m.open_door'), C.MSG_INFO)
                game.end_turn()
                return True
        game.level = game.world.chunk(cx, cy, p.world_z, visit=True)
        p.chunk_x, p.chunk_y = cx, cy
        p.x, p.y = x, y
        from . import survival
        survival.movement(p, running=getattr(game, '_running_step', False))
        game.level.set_player_pos(x, y)
        game.level.recompute_fov(x, y)
        game.tooltip = None
        game.floats.clear()
        if p.alive:
            game.check_tile(x, y)
        game.end_turn()
        game.update_lighting()
        return True


def move_monster_cross_chunk(game, monster, nx, ny, source=None):
        """Move a monster through a Level 0 chunk seam when the destination is open."""
        source = source if source is not None else game.level
        if game.world is None or source.depth != 0:
            return False
        # A monster can be processed from a snapshot of the simulated chunks.
        # Verify its current owner before mutating either list; otherwise a
        # stale/duplicate turn can raise ValueError during list.remove().
        if not any(candidate is monster for candidate in source.monsters):
            return False
        p = game.player
        ox, x = divmod(nx, game.world.w)
        oy, y = divmod(ny, game.world.h)
        cx, cy = source.chunk_x + ox, source.chunk_y + oy
        target = game.world.chunk(cx, cy, source.world_z)
        if target is None or not target.is_walkable(x, y) or target.monster_at(x, y):
            return False
        if (target.chunk_x == p.chunk_x and target.chunk_y == p.chunk_y
                and target.world_z == p.world_z and (x, y) == (p.x, p.y)):
            return False
        if not target.can_see_through(x, y):
            return False
        game.world.visited.add((source.chunk_x, source.chunk_y, source.world_z))
        game.world.visited.add((cx, cy, source.world_z))
        source.monsters[:] = [candidate for candidate in source.monsters
                              if candidate is not monster]
        monster.x, monster.y = x, y
        monster.b_level, monster.world_z = target.b_level, target.world_z
        target.monsters.append(monster)
        obstacle=target.furniture_at(x,y)
        if obstacle and obstacle.spec.get('damage'):
            monster.take_damage(obstacle.spec['damage'],cause='spikes')
        return True


def use_level_exit(game):
        if game.world is None:
            return False
        exit_ = game.level.exits.get((game.player.x,game.player.y))
        if exit_ is None:
            return False
        if exit_.get('requires') and exit_['requires'] not in getattr(game.player,'knowledge',[]):
            game.msg(t('br.need_knowledge'),C.MSG_HINT)
            return True
        game.travel_to_level(exit_['target'])
        return True


def show_level_passages(game):
        if game.world is None: return
        lv=game.level
        lines=[(f'B-Level {game.player.b_level} | World Z={game.player.world_z}',C.CYAN)]
        if game.player.world_z!=0:
            lines.append((t('br.passage_z'),C.YELLOW))
        else:
            from . import backrooms
            backrooms.ensure_exits(lv,game.world.profile)
            for (x,y),exit_ in lv.exits.items():
                lines.append((t('br.passage_at',n=exit_['target'],x=x,y=y),C.CYAN))
                lines.append((t(exit_['label']),C.WHITE))
                if exit_.get('requires'): lines.append((t('br.need_knowledge'),C.PURPLE))
            if not lv.exits: lines.append((t('br.no_passage'),C.GRAY))
        lines.append((t('br.passage_help'),C.WHITE))
        game.show_text(t('a.passages'),lines)


def travel_to_level(game, target):
        """Shared destination API for passages and future artifacts/noclip routes."""
        if game.world is None or target not in range(21) or game.player.is_asleep():
            return False
        p = game.player
        worlds = getattr(game,'worlds',{})
        worlds[game.world.b_level] = game.world
        destination = worlds.get(target)
        if destination is None:
            destination = World(game.world.seed,target)
        level = destination.chunk(0,0,0,visit=True)
        # Fixed spine is free in every generator. Search if the player built here.
        positions = sorted(((x,y) for y in range(level.h) for x in range(level.w)
                            if level.is_walkable(x,y) and level.at(x,y)!=MG.AIR
                            and not level.monster_at(x,y) and (x,y) not in level.hazards
                            and (x,y) not in level.exits),
                           key=lambda pos:abs(pos[0]-4)+abs(pos[1]-4))
        if not positions:
            if target not in worlds:
                destination.storage.cleanup()
            game.msg(t('br.blocked'),C.MSG_HINT)
            return False
        worlds[target] = destination
        game.worlds,game.world,game.level = worlds,destination,level
        p.depth = p.b_level = target
        p.deepest = max(p.deepest,target)
        p.chunk_x = p.chunk_y = p.world_z = 0
        p.x,p.y = positions[0]
        game._held_move = None
        game._sleep_auto = False
        game.tooltip = None
        game.floats.clear()
        game.visible_world = {}
        game._visible_world_key = None
        game.views.free_camera = False
        game.views.world_camera = [0,0,0]
        game.views.picks.clear()
        game.workshop = Workshop(game)
        game.level.set_player_pos(p.x,p.y)
        game.level.recompute_fov(p.x,p.y)
        game.end_turn()
        game.update_lighting()
        game.msg(t('br.arrive',n=target,name=t('br.name.'+str(target))),C.MSG_GOOD)
        game.msg(t('br.info.'+str(target)),C.MSG_HINT)
        return True


def descend(game):
        if game.use_level_exit():
            return
        if game.world is not None and game.level.at(game.player.x,game.player.y)==MG.STAIR_DOWN:
            return game.use_world_stairs(-1)
        p, lv = game.player, game.level
        if game.world is not None and p.b_level == 0:
            game.msg(t("world.no_exit"), C.MSG_HINT)
            return
        if lv.at(p.x, p.y) != MG.STAIR_DOWN:
            game.msg(t("m.no_stairs"), C.MSG_HINT)
            return
        if p.depth >= C.MAX_LEVEL:
            game.msg(t("m.bottom"), C.MSG_GOOD)
            game.mode = "dead"
            game.win = True
            return
        p.depth += 1
        p.deepest = max(p.deepest, p.depth)
        for line in p.gain_exp(C.DESCEND_XP, t("m.src.descend")):
            game.msg(line, C.MSG_GOOD)
        game.level = game.make_level(p.depth)
        rooms = game.level.rooms
        start = rooms[0].center() if rooms else (5, 5)
        p.x, p.y = start
        game.level.set_player_pos(*start)
        if rooms:
            rooms[0].lit = True
        game.level.recompute_fov(*start)
        game.msg(t("m.descend_to", d=p.depth), C.MSG_GOOD)
        game.audio.play("descend")


def climb(game):
        p=game.player
        if not game.world or not p.alive or p.is_asleep() or game.views.mode=='board':
            return False
        z=p.world_z+1
        if not game.world.exists(z):
            game.msg(t('climb.none'),C.MSG_HINT)
            return False
        w=game.world
        above=w.chunk(p.chunk_x,p.chunk_y,z)
        if above.at(p.x,p.y)!=MG.AIR:
            game.msg(t('climb.ceiling'),C.MSG_HINT)
            return False
        options=[]
        for dx,dy in ((0,-1),(1,0),(0,1),(-1,0)):
            cx,x=divmod(p.x+dx,w.w); cy,y=divmod(p.y+dy,w.h)
            target=w.chunk(p.chunk_x+cx,p.chunk_y+cy,z)
            lower=w.chunk(p.chunk_x+cx,p.chunk_y+cy,p.world_z)
            if (lower.can_see_through(x,y) and target.is_walkable(x,y)
                    and target.at(x,y)!=MG.AIR and target.can_see_through(x,y)
                    and not target.monster_at(x,y)):
                options.append((target,x,y))
        if not options:
            game.msg(t('climb.none'),C.MSG_HINT)
            return False
        if p.stamina<5:
            game.msg(t('climb.tired'),C.MSG_HINT)
            return False
        p.stamina-=5
        if game.rng.random()<.5:
            target,x,y=options[0]
            game.level=w.chunk(target.chunk_x,target.chunk_y,z,visit=True)
            p.chunk_x,p.chunk_y,p.world_z=target.chunk_x,target.chunk_y,z
            p.x,p.y=x,y
            game.level.set_player_pos(x,y)
            game.level.recompute_fov(x,y)
            game.visible_world={}; game._visible_world_key=None
            game.tooltip=None; game.floats.clear()
            game.msg(t('climb.success'),C.MSG_GOOD)
        else:
            damage=game.rng.dice(1,6)
            p.take_damage(damage,cause='climbing')
            game.msg(t('climb.failed',n=damage),C.MSG_WARN)
        game.end_turn()
        game.update_lighting()
        return True


def use_world_stairs(game, delta):
        p = game.player
        z = p.world_z+delta
        if not game.world.exists(z):
            return False
        target = game.world.chunk(p.chunk_x,p.chunk_y,z)
        required = MG.STAIR_DOWN if delta>0 else MG.STAIR_UP
        if target.at(p.x,p.y)!=required or target.monster_at(p.x,p.y):
            game.msg(t('m.wall'),C.MSG_HINT)
            return False
        game.level=game.world.chunk(p.chunk_x,p.chunk_y,z,visit=True)
        p.world_z=z
        game.level.set_player_pos(p.x,p.y)
        game.level.recompute_fov(p.x,p.y)
        game.visible_world={}
        game._visible_world_key=None
        game.tooltip=None
        game.floats.clear()
        game.end_turn()
        game.update_lighting()
        game.msg(t('debug.z_changed',z=z),C.MSG_INFO)
        return True


def ascend(game):
        if game.use_level_exit():
            return
        if game.world is not None and game.level.at(game.player.x,game.player.y)!=MG.STAIR_UP:
            return game.climb()
        if game.world is not None and game.level.at(game.player.x,game.player.y)==MG.STAIR_UP:
            return game.use_world_stairs(1)
        p, lv = game.player, game.level
        if game.world is not None and p.b_level == 0:
            game.msg(t("world.no_exit"), C.MSG_HINT)
            return
        if lv.at(p.x, p.y) != MG.STAIR_UP:
            game.msg(t("m.no_stairs"), C.MSG_HINT)
            return
        if p.depth <= 1:
            game.msg(t("m.no_stairs_up"), C.MSG_HINT)
            return
        p.depth -= 1
        for line in p.gain_exp(C.DESCEND_XP, t("m.src.ascend")):
            game.msg(line, C.MSG_INFO)
        game.level = game.make_level(p.depth)
        rooms = game.level.rooms
        start = rooms[0].center() if rooms else (5, 5)
        p.x, p.y = start
        game.level.set_player_pos(*start)
        if rooms:
            rooms[0].lit = True
        game.level.recompute_fov(*start)
        game.msg(t("m.ascend_to", d=p.depth), C.MSG_INFO)
        game.audio.play("stairs")


def toggle_lights(game):
        lv = game.level
        if not any(it.name == "lantern" and it.equipped for it in game.player.items):
            game.msg(t("m.need_light_source"), C.MSG_HINT)
            return False
        if all(r.lit for r in lv.rooms):
            for r in lv.rooms:
                r.lit = False
            game.msg(t("m.lights_off"), C.MSG_INFO)
        else:
            for r in lv.rooms:
                r.lit = True
            game.msg(t("m.lights_on"), C.MSG_INFO)
        game.audio.play("magic", 0.4)
        game.update_lighting()
        game.end_turn()


def toggle_map(game):
        lv = game.level
        if len(lv.mapped) > len(lv.explored):
            lv.mapped.clear()
            game.msg(t("m.map_fade"), C.MSG_INFO)
        else:
            lv.magic_map()
            game.msg(t("m.map_memorize", d=lv.depth), C.MSG_GOOD)
            game.audio.play("magic", 0.5)
        game.end_turn()


def check_tile(game, x, y):
        if (x,y) in game.level.exits:
            game.msg(game.level.describe_tile(x,y),C.MSG_GOOD)
        obstacle=game.level.furniture_at(x,y)
        if obstacle and obstacle.spec.get('damage'):
            game.player.take_damage(obstacle.spec['damage'],cause='spikes')
            game.msg('Вы наступили на колья!',C.MSG_BAD)
        if game.world is not None and game.level.at(x,y)==MG.AIR:
            z = game.player.world_z-1
            while game.world.exists(z):
                target = game.world.chunk(game.player.chunk_x,game.player.chunk_y,z)
                if target.at(x,y) != MG.AIR and target.is_walkable(x,y):
                    height = game.player.world_z-z
                    game.player.world_z=z
                    game.level=game.world.chunk(game.player.chunk_x,game.player.chunk_y,z,visit=True)
                    game.level.set_player_pos(x,y)
                    game._visible_world_key=None
                    game.tooltip=None
                    game.level.recompute_fov(x,y)
                    game.update_lighting()
                    damage = 0 if height==1 and game.rng.random()<.5 else game.rng.dice(height,6)
                    game.player.take_damage(damage,cause='fall')
                    game.msg(t('vertical.fall',n=height,d=damage),C.MSG_WARN)
                    return
                z-=1
        lv = game.level
        tile = lv.at(x, y)
        if tile == MG.TRAPDOOR:
            dmg = random.randint(2, 8)
            game.player.take_damage(dmg, None, cause="trap")
            game.msg(t("m.trap", d=dmg), C.MSG_BAD)
            game.audio.play("trap")
        elif tile == MG.WATER:
            game.msg(t("m.swim"), C.MSG_INFO)
        elif tile == MG.FOUNTAIN and random.random() < 0.25:
            game.player.heal(5)
            game.msg(t("m.fountain"), C.MSG_GOOD)
            game.audio.play("heal", 0.6)


def pick_lock(game):
        p, lv = game.player, game.level
        locked = [(x, y) for (x, y), d in lv.doors.items()
                  if d.get("locked") and not d.get("broken")
                  and F.chebyshev(p.x, p.y, x, y) <= 1.5]
        if not locked:
            game.msg(t("m.no_lock"), C.MSG_HINT)
            return False
        opts = [t("m.lock_at", what=lv.describe_tile(x, y), x=x, y=y) for x, y in locked]

        def cb(idx):
            if idx is None:
                return
            x, y = locked[idx]
            if F.chebyshev(p.x, p.y, x, y) > 1.5:
                game.msg(t("m.no_lock"), C.MSG_HINT)
                return
            d = lv.doors[(x, y)]
            d["open"] = True
            d["locked"] = False
            lv.geometry_revision += 1
            game.msg(t("m.pick_lock"), C.MSG_INFO)
            game.audio.play("door")
            game.end_turn()

        game.show_menu(t("pick.lock"), opts, cb, width=34)
        return True
