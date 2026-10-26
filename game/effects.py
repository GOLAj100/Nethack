"""Эффекты зелий, свитков и палочек."""

from __future__ import annotations

import random

from engine import config as C
from .lang import t


def _heal(player, level, amount, label):
    healed = player.heal(amount)
    if healed <= 0:
        return t("e.heal_little"), C.MSG_INFO
    return f"{label} " + t("e.heal", n=healed), C.MSG_GOOD


# --------------------------------------------------------------------------
# Зелья
# --------------------------------------------------------------------------
def _potion(player, level, item, target):
    name = item.name
    roll = random.random()

    if name == "potion of healing":
        return _heal(player, level, random.randint(10, 20), t("e.warmth"))
    if name == "potion of extra healing":
        return _heal(player, level, random.randint(24, 40), t("e.flood"))
    if name == "potion of full healing":
        player.hp = player.max_hp
        return t("e.full_heal"), C.MSG_GOOD
    if name == "potion of gain level":
        player.gain_exp(player.xp_for_next_level())
        return t("e.experienced") + " " + t("e.powerful"), C.MSG_GOOD
    if name == "potion of strength":
        player.str += random.randint(1, 3)
        return t("e.stronger", n=player.str), C.MSG_GOOD
    if name == "potion of poison":
        dmg = random.randint(3, 9)
        player.take_damage(dmg, cause="poison")
        return t("e.burns", d=dmg), C.MSG_BAD
    if name == "potion of acid":
        dmg = random.randint(6, 16)
        player.take_damage(dmg, cause="acid")
        return t("e.sears", d=dmg), C.MSG_BAD
    if name == "potion of confusion":
        player.status["confused"] = random.randint(4, 10)
        return t("e.spinning"), C.MSG_WARN
    if name == "potion of hallucination":
        player.status["hallucinating"] = random.randint(8, 20)
        return t("e.breathe"), C.MSG_WARN
    if name == "potion of sleeping":
        player.status["asleep"] = random.randint(3, 7)
        return t("e.heavy"), C.MSG_WARN
    if name == "potion of booze":
        player.status["confused"] = max(player.status["confused"], random.randint(2, 5))
        player.str = max(3, player.str - 1)
        return t("e.tilts"), C.MSG_WARN
    if name in ('water', 'distilled water'):
        return t('e.water'), C.MSG_INFO
    if name == 'salt water':
        player.consume(-5)
        player.stamina = max(-50, player.stamina - 2)
        return t('e.salt_water'), C.MSG_WARN
    if name == 'stagnant water':
        return t('e.stagnant_water'), C.MSG_WARN
    return t("e.nothing"), C.MSG_HINT


# --------------------------------------------------------------------------
# Свитки
# --------------------------------------------------------------------------
def _scroll(player, level, item, target):
    name = item.name

    if name == "scroll of mapping":
        level.map_area()
        return t("e.map_area", d=level.depth), C.MSG_GOOD
    if name == "scroll of magic mapping":
        level.magic_map()
        return t("e.magic_map"), C.MSG_GOOD
    if name == "scroll of teleport":
        spot = level.random_open_tile()
        if spot is None:
            return t("e.nothing"), C.MSG_HINT
        player.x, player.y = spot
        level.set_player_pos(*spot)
        level.recompute_fov(*spot)
        return t("e.blink"), C.MSG_INFO
    if name == "scroll of aggravate monster":
        n = level.aggravate()
        return t("e.malice", n=n), C.MSG_WARN
    if name == "scroll of amnesia":
        n = 0
        for it in player.items:
            if it.kind in ("potion", "scroll", "wand", "ring") and it.identified:
                it.identified = False
                n += 1
        return t("e.forget", n=n), C.MSG_WARN
    if name == "scroll of destroy armor":
        if player.remove_armor():
            return t("e.armor_crumb"), C.MSG_BAD
        return t("m.no_armor"), C.MSG_HINT
    if name == "scroll of fire":
        count = 0
        for m in list(level.monsters):
            if m.alive and _dist(player, m) <= 4:
                m.take_damage(random.randint(6, 14), player, cause="fire")
                count += 1
        return t("e.fire_around", n=count), C.MSG_WARN
    if name == "scroll of scare monster":
        count = 0
        for m in list(level.monsters):
            if m.alive and _dist(player, m) <= 5 and m.flees(player):
                count += 1
        return t("e.fear", n=count), C.MSG_INFO
    if name == "scroll of charging":
        for it in player.items:
            if it.kind == "wand" and it.charges < it.charges_max:
                it.charges = it.charges_max
                return t("e.recharge", it=it.display_name()), C.MSG_GOOD
        return t("e.surge"), C.MSG_HINT
    if name == "scroll of luck":
        player.status["lucky"] = random.randint(20, 40)
        return t("e.lucky"), C.MSG_GOOD
    if name == "scroll of nothing":
        return t("e.blank"), C.MSG_HINT
    return t("e.crumble"), C.MSG_HINT


# --------------------------------------------------------------------------
# Палочки
# --------------------------------------------------------------------------
def _wand(player, level, item, target=None):
    name = item.name
    tx, ty = target if target else (player.x, player.y)

    if name == "wand of light":
        level.map_area(radius=8)
        return t("e.wand_light"), C.MSG_GOOD
    if name == "wand of nothing":
        return t("e.puff"), C.MSG_HINT
    if name == "wand of dig":
        changed = level.dig_near(player.x, player.y, 2)
        return (t("e.dig") if changed else t("e.no_soft")), C.MSG_INFO
    if name == "wand of striking":
        m = level.monster_at(tx, ty)
        dmg = random.randint(8, 20)
        if m:
            m.take_damage(dmg, player, cause="wand")
            return t("e.wand_hit", name=m.title, d=dmg), C.MSG_GOOD
        return t("e.wand_air"), C.MSG_INFO
    if name in ("wand of fire", "wand of cold", "wand of lightning", "wand of sleep"):
        hits = level.area_effect(tx, ty, radius=2)
        dmg = random.randint(10, 22)
        for m in hits:
            m.take_damage(dmg, player, cause="wand")
        elem = {"wand of fire": t("e.elem.flames"),
                "wand of cold": t("e.elem.frost"),
                "wand of lightning": t("e.elem.lightning"),
                "wand of sleep": t("e.elem.drowsy")}[name]
        if hits:
            if name == "wand of sleep":
                for m in hits:
                    m.status["asleep"] = random.randint(6, 14)
            return t("e.elem", what=elem, n=len(hits)), C.MSG_GOOD
        return t("e.elem_empty", what=elem), C.MSG_INFO
    return t("e.nothing"), C.MSG_HINT


def _dist(a, b):
    from engine import fov as F
    return F.distance(a.x, a.y, b.x, b.y)


EFFECTS = {"potion": _potion, "scroll": _scroll, "wand": _wand}


def apply(player, level, item, target=None):
    if item.spec.get("pending_effect"):
        return t("m.liquid_pending"), C.MSG_HINT
    fn = EFFECTS.get(item.kind)
    if fn is None:
        return t("e.nothing"), C.MSG_HINT
    try:
        return fn(player, level, item, target)
    except Exception as exc:  # noqa: BLE001 - не роняем игру из-за эффекта
        from .lang import kind_name
        return t("e.fizzle", kind=kind_name(item.kind), err=exc), C.MSG_WARN
