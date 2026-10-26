"""Ход, бой, смерть и сон: мировая очередь и расход ресурсов."""
from __future__ import annotations

import random

import pygame

from engine import config as C
from engine import fov as F
from . import ai
from . import combat
from . import effects
from . import monsters as MON
from . import survival
from .items import make_random_item
from .lang import save_settings, t


def player_attack(game, monster, level=None):
        w = game.player.wielded
        text, color, _ = combat.attack(game.player, monster, game, w)
        game.msg(text, color)
        if not monster.alive:
            game.on_kill(monster, level=level)


def force_attack(game) -> bool:
        p = game.player
        options = []
        for m in game.level.monsters:
            if m.alive and F.chebyshev(p.x, p.y, m.x, m.y) <= 1:
                options.append((m, f"{m.title} ({t('ui.bars')} {m.hp}/{m.max_hp})"))
        if not options:
            game.msg(t("m.nothing_adj"), C.MSG_HINT)
            return False

        def cb(idx):
            if idx is None:
                return
            m = options[idx][0]
            if m.alive:
                game.player_attack(m)
                game.end_turn()

        game.show_menu(t("pick.fight"), [o[1] for o in options], cb, width=34)
        return True


def on_kill(game, monster, level=None):
        p = game.player
        lv = level if level is not None else game.level
        p.kills += 1
        base = MON.MONSTERS.get(monster.name, {}).get("xp", 8)
        xp = base + lv.depth
        for line in p.gain_exp(xp):
            game.msg(line, C.MSG_GOOD)
        game.audio.play("levelup", 0.5)
        if game.rng.random() < 0.22:
            spot = lv.random_open_tile()
            if spot:
                lv.items[spot] = make_random_item(lv.depth, rng=game.rng)
        lv.corpses[(monster.x, monster.y)] = monster.glyph
        lv.corpses_color = getattr(lv, "corpses_color", {})
        lv.corpses_color[(monster.x, monster.y)] = monster.color


def wait(game):
        game.msg(t("m.wait"), C.MSG_HINT)
        game.end_turn()


def rest(game):
        game._rest_tint_until=pygame.time.get_ticks()+1200
        p, lv = game.player, game.level

        def danger():
            return any(m.alive and (m.x, m.y) in lv.visible for m in lv.monsters)

        for _ in range(10):
            if not p.alive or game.mode != "play" or danger() or p.is_asleep():
                game.msg(t("m.rest_stop"), C.MSG_WARN)
                return
            hp = p.hp
            game.end_turn(resting=True)
            if not p.alive or game.mode != "play" or danger() or p.hp < hp or p.is_asleep():
                game.msg(t("m.rest_stop"), C.MSG_WARN)
                return
        game.msg(t("m.rest_done"), C.MSG_INFO)


def sleep(game):
        if game.views.mode=='board' or not game.player.alive:
            return False
        if game.player.is_asleep():
            return False
        game._slider_start_sleep=True
        game._slider_return=game.mode
        game.mode='sleep_slider'
        game._held_move=None
        return True


def finish_sleep_slider(game, confirm):
        game.mode=game._slider_return
        if confirm:
            save_settings(game)
        if game._slider_start_sleep:
            if confirm:
                game.start_sleep()
        else:
            game.open_settings()


def start_sleep(game):
        game.player.status['asleep'] = max(10, min(360, int(game.sleep_setting)))
        game.sleep_frame = 0
        game.sleep_prompt = None
        game._sleep_auto = True
        game._sleep_timer = .15
        game._sleep_ignored.clear()
        game._held_move=None
        game.msg(t('m.sleep_start', n=game.player.status['asleep']), C.MSG_INFO)
        return True


def report_nourishment(game, result):
        if result['gain']:
            game.msg(t('m.nourished', gain=result['gain'], bonus=result['bonus']), C.MSG_GOOD)
        if result['relief']:
            game.msg(t('m.exhaustion_relief', n=result['relief']), C.MSG_GOOD)


def end_turn(game, resting=False):
        if getattr(game, '_movement_batch', False):
            return
        delay = game.player.movement_delay
        game.player.movement_delay = 0
        for _ in range(1 + delay):
            game._advance_turn(resting=resting)
            if not game.player.alive or getattr(game,'sleep_prompt',None) is not None:
                break


def _advance_turn(game, resting=False):
        p = game.player
        if not p.alive:
            game.on_death()
            return
        sleeping = p.is_asleep()
        hp_before = p.hp
        if sleeping and game.sleep_prompt is None:
            nearby=[]
            levels=[game.level]
            if game.world:
                levels=[game.world.chunk(cx,cy,p.world_z)
                        for cy in range((p.chunk_y*game.world.h+p.y-8)//game.world.h,(p.chunk_y*game.world.h+p.y+8)//game.world.h+1)
                        for cx in range((p.chunk_x*game.world.w+p.x-8)//game.world.w,(p.chunk_x*game.world.w+p.x+8)//game.world.w+1)]
            for level in levels:
                ox=(level.chunk_x-p.chunk_x)*level.w if game.world else 0
                oy=(level.chunk_y-p.chunk_y)*level.h if game.world else 0
                nearby.extend(m for m in level.monsters if m.alive and id(m) not in game._sleep_ignored
                              and F.chebyshev(p.x,p.y,m.x+ox,m.y+oy)<=8)
            if nearby:
                m=nearby[0]
                key = MON.MONSTERS.get(m.name,{}).get('sleep_warning',MON.SLEEP_WARNINGS.get(m.name,'m.sleep_wake_unknown'))
                game._sleep_ignored.add(id(m))
                game.audio.play('sleep_alarm',0.8)
                game.show_menu(t(key), [t('sleep.wake'),t('sleep.continue')], lambda idx: game._sleep_choice(idx), width=48)
                game.sleep_prompt=True
                return
        p.turns += 1
        if p.hp < p.max_hp * 0.2 and p.turns % 50 == 0:
            game.audio.play("lowhp", 0.4)

        game.monster_turn()
        if p.alive:
            from . import survival
            survival.advance(p, sleeping=sleeping and p.hp >= hp_before,
                             resting=resting and p.hp >= hp_before)
            if (sleeping or resting) and p.hp>=hp_before:
                comfort=game.workshop.comfort() if hasattr(game,'workshop') else 0
                p.stamina=min(50,p.stamina+comfort)
            survival.advance_sanity(p, sleeping=sleeping and p.hp>=hp_before,
                threatened=any(m.alive and m.hostile and F.chebyshev(p.x,p.y,m.x,m.y)<=8
                               for m in game.level.monsters), hurt=p.hp<hp_before)
            if getattr(game,'world',None) is not None:
                from .backrooms import advance_environment
                advance_environment(game)
                game.world.flush()

            if sleeping:
                p.status['asleep'] = max(0, p.status['asleep'] - 1)
                if p.status['asleep'] == 0:
                    game.msg(t('m.wake'), C.MSG_INFO)
                game.sleep_frame = (game.sleep_frame + 1) % 3
            if p.turns % 300 == 0:
                game.msg(p.nutrition_state(), C.MSG_WARN)
            game.level.recompute_fov(p.x, p.y)
            if p.status.get("confused", 0) > 0:
                p.status["confused"] -= 1
            if p.status.get("hallucinating", 0) > 0:
                p.status["hallucinating"] -= 1
            for k in ("flee", "lucky", "stunned"):
                if p.status.get(k, 0) > 0:
                    p.status[k] -= 1
        else:
            game.on_death()


def _sleep_choice(game, idx):
        game.sleep_prompt=None
        if idx != 1:
            game.player.status['asleep']=0
            game.msg(t('m.wake'),C.MSG_INFO)
            game._sleep_auto=False


def monster_turn(game):
        lv = game.level
        levels = None
        simulated = [lv]
        if game.world is not None and lv.depth == 0:
            p, world = game.player, game.world
            px = p.chunk_x * world.w + p.x
            py = p.chunk_y * world.h + p.y
            radius = ai.CHASE_RADIUS
            levels = {}
            for cy in range((py-radius)//world.h, (py+radius)//world.h + 1):
                for cx in range((px-radius)//world.w, (px+radius)//world.w + 1):
                    key = (cx, cy, p.world_z)
                    levels[key] = world.chunk(*key)
            simulated = list(levels.values())
        alive = [m for chunk in simulated for m in chunk.monsters if m.alive]
        for m in sorted(alive, key=lambda m: -m.speed):
            if not m.alive:
                continue
            turns = 2 if m.speed >= 120 and game.rng.random() < 0.5 else 1
            for _ in range(turns):
                source = next((chunk for chunk in simulated if m in chunk.monsters), None)
                if source is None:
                    break
                if levels is not None:
                    game.world.visited.add((source.chunk_x, source.chunk_y, source.world_z))
                ai.take_turn(m, game, source, levels)
                if not game.player.alive:
                    game.on_death()
                    return
        for chunk in simulated:
            chunk.monsters = [m for m in chunk.monsters if m.alive]


def on_death(game):
        p = game.player
        if p.hp > 0 or getattr(game, "_dead", False):
            return
        game._dead = True
        game.depth_of_death = p.depth
        game.win = False
        game.msg(t("m.die"), C.MSG_BAD)
        game.audio.play("death")
        game.mode = "dead"
