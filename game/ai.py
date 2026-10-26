"""Поведение монстров: сон, паника, поиск игрока, атаки."""

from __future__ import annotations

import random
from collections import deque

from engine import fov as F
from . import combat
from . import mapgen as MG
from .lang import t

DIRS = ((0, -1), (1, 0), (0, 1), (-1, 0))
CHASE_RADIUS = 18
# Новые поведения подключаются функцией (monster, ctx, source_level, levels).
BEHAVIORS = {}


def _observer(m, ctx, level, levels):
    """The suburban watcher never attacks, but being seen costs sanity."""
    player = ctx.player
    if can_see_monster(level, m, player.x, player.y, 10):
        if player.turns % 12 == 0:
            player.sanity = max(-50, player.sanity - 1)
            _msg(ctx, t("m.observer_watch"), C_WARN)
        m.last_seen = (player.x, player.y)
    _wander(m, level, ctx)


BEHAVIORS["observer"] = _observer


class _WorldMap:
    """Navigation in source-local coordinates across the simulated chunks."""

    def __init__(self, source, levels):
        self.source = source
        self.levels = levels

    def resolve(self, x, y):
        cx, lx = divmod(x, self.source.w)
        cy, ly = divmod(y, self.source.h)
        key = (self.source.chunk_x + cx, self.source.chunk_y + cy,
               self.source.world_z)
        return self.levels.get(key), lx, ly

    def in_bounds(self, x, y):
        return self.resolve(x, y)[0] is not None

    def is_wall(self, x, y):
        lv, lx, ly = self.resolve(x, y)
        return lv is None or lv.is_wall(lx, ly)

    def can_see_through(self, x, y):
        lv, lx, ly = self.resolve(x, y)
        return lv is not None and lv.can_see_through(lx, ly)

    def next_step(self, sx, sy, tx, ty, max_dist=CHASE_RADIUS):
        # Monster navigation must not depend on the player's explored tiles.
        start, goal = (sx, sy), (tx, ty)
        queue = deque([(start, 0)])
        prev = {start: None}
        while queue:
            node, distance = queue.popleft()
            if node == goal:
                while prev[node] is not None and prev[node] != start:
                    node = prev[node]
                return node if node != start else None
            if distance >= max_dist:
                continue
            for dx, dy in DIRS:
                nxt = (node[0] + dx, node[1] + dy)
                if nxt in prev or self.is_wall(*nxt):
                    continue
                lv, x, y = self.resolve(*nxt)
                if nxt != goal and lv.monster_at(x, y):
                    continue
                prev[nxt] = node
                queue.append((nxt, distance + 1))
        return None


def _msg(ctx, text, color):
    ctx.messages(text, color)


def can_see_monster(level, m, px, py, radius=9):
    if F.chebyshev(m.x, m.y, px, py) > radius:
        return False
    return F.has_los(lambda x, y: not level.can_see_through(x, y),
                     m.x, m.y, px, py)


def _open_or_bash(level, m, tx, ty, ctx):
    """Монстр пытается пройти через закрытую дверь."""
    d = level.doors.get((tx, ty))
    if d is None:
        return False
    if d.get("open") or d.get("broken"):
        return True
    if d.get("locked") and not d.get("broken"):
        if random.random() < 0.3:
            d["open"] = True
            d["locked"] = False
            _msg(ctx, t("m.picks_lock", name=m.title), C_WARN)
            return True
        return False
    if random.random() < 0.55:
        d["open"] = True
        _msg(ctx, t("m.opens_door", name=m.title), C_WARN)
        return True
    d["broken"] = True
    level.set(tx, ty, MG.FLOOR)
    _msg(ctx, t("m.breaks_door", name=m.title), C_WARN)
    return True


C_WARN = (222, 190, 78)


def take_turn(m, ctx, level=None, levels=None):
    level = level if level is not None else ctx.level
    player = ctx.player
    if levels is not None and (level.world_z != player.world_z
                               or level.b_level != player.b_level):
        return
    handler = BEHAVIORS.get(m.behavior)
    if handler is not None:
        return handler(m, ctx, level, levels)
    px, py = player.x, player.y
    if levels is not None:
        px += (player.chunk_x - level.chunk_x) * level.w
        py += (player.chunk_y - level.chunk_y) * level.h
        level = _WorldMap(level, levels)

    # --- статусы ---------------------------------------------------------
    if m.status.get("asleep", 0) > 0:
        m.status["asleep"] -= 1
        if m.status["asleep"] == 0:
            _msg(ctx, t("m.wake_up", name=m.title), C_WARN)
            m.awake = True
        return

    if m.status.get("flee", 0) > 0:
        m.status["flee"] -= 1
        if m.status["flee"] == 0:
            m.status["flee"] = 0
        _step_away(m, level, px, py, ctx)
        return

    confused = m.status.get("confused", 0) > 0
    if confused:
        m.status["confused"] -= 1
        if m.status["confused"] == 0:
            _msg(ctx, t("m.no_confused", name=m.title), C_WARN)
        _random_step(m, level, ctx)
        return

    # --- восприятие -------------------------------------------------------
    dist = F.distance(m.x, m.y, px, py)
    if not m.awake:
        if dist <= 1.5:
            m.awake = True
        elif dist <= 8 and can_see_monster(level, m, px, py, 8):
            if random.random() < 0.55:
                m.awake = True
        else:
            if random.random() < 0.18:
                _random_step(m, level, ctx)
            return

    # --- атака ------------------------------------------------------------
    if (m.hostile and dist <= 1.45 and F.chebyshev(m.x, m.y, px, py) <= 1
            and can_see_monster(level, m, px, py, 2)):
        text, color, _ = combat.attack(m, player, ctx)
        _msg(ctx, text, color)
        return

    # --- преследование / патрулирование -----------------------------------
    if m.awake and m.hostile and player.alive and m.behavior == "chase":
        step = level.next_step(m.x, m.y, px, py, max_dist=CHASE_RADIUS)
        if step is not None:
            _try_move(m, level, step[0], step[1], ctx)
        else:
            _wander(m, level, ctx)
    else:
        _wander(m, level, ctx)


def _try_move(m, level, tx, ty, ctx):
    if isinstance(level, _WorldMap):
        target, x, y = level.resolve(tx, ty)
        if target is None or target.is_wall(x, y) or target.monster_at(x, y):
            return False
        if (target is ctx.level and (x, y) == (ctx.player.x, ctx.player.y)
                or target.chunk_x == ctx.player.chunk_x
                and target.chunk_y == ctx.player.chunk_y
                and target.world_z == ctx.player.world_z
                and (x, y) == (ctx.player.x, ctx.player.y)):
            return False
        if target.at(x, y) == MG.DOOR:
            if not _open_or_bash(target, m, x, y, ctx):
                return False
        if target is not level.source:
            return ctx.move_monster_cross_chunk(m, tx, ty, source=level.source)
        m.x, m.y = x, y
        obstacle=target.furniture_at(x,y)
        if obstacle and obstacle.spec.get('damage'): m.take_damage(obstacle.spec['damage'],cause='spikes')
        return True
    if not level.in_bounds(tx, ty):
        if getattr(ctx, "world", None) is not None and level.depth == 0:
            return ctx.move_monster_cross_chunk(m, tx, ty, source=level)
        return False
    if level.is_wall(tx, ty):
        return False
    if (tx, ty) == (ctx.player.x, ctx.player.y):
        return False
    if level.at(tx, ty) == MG.DOOR:
        if not _open_or_bash(level, m, tx, ty, ctx):
            return False
    if level.monster_at(tx, ty):
        return False
    m.x, m.y = tx, ty
    obstacle=level.furniture_at(tx,ty)
    if obstacle and obstacle.spec.get('damage'): m.take_damage(obstacle.spec['damage'],cause='spikes')
    return True


def _random_step(m, level, ctx):
    dx, dy = random.choice(DIRS)
    _try_move(m, level, m.x + dx, m.y + dy, ctx)


def _wander(m, level, ctx):
    if random.random() < 0.55:
        dx, dy = random.choice(DIRS)
        _try_move(m, level, m.x + dx, m.y + dy, ctx)


def _step_away(m, level, px, py, ctx):
    best = None
    best_d = F.distance(m.x, m.y, px, py)
    for dx, dy in DIRS:
        nx, ny = m.x + dx, m.y + dy
        if not level.in_bounds(nx, ny) or level.is_wall(nx, ny):
            continue
        d = F.distance(nx, ny, px, py)
        if d > best_d:
            best_d = d
            best = (nx, ny)
    if best:
        _try_move(m, level, best[0], best[1], ctx)
