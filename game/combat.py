"""Боевая система: точность попадания, урон, смерть."""

from __future__ import annotations

import random

from engine import config as C
from .lang import t


def hit_chance(attacker, defender) -> float:
    acc = 0.55
    acc += attacker.hit_bonus * 0.045
    acc -= defender.ac_total * 0.035
    if getattr(attacker, "is_confused", lambda: False)():
        acc -= 0.15
    if getattr(defender, "is_fleeing", lambda: False)():
        acc += 0.20
    return max(0.10, min(0.92, acc))


def roll_damage(attacker, base_dmg=None) -> int:
    weapon = getattr(attacker, "weapon_dmg", None) if attacker.is_player else None
    n, s = base_dmg or (weapon() if callable(weapon) else weapon) or attacker.dmg
    dmg = random.randint(n, s) * 1
    dmg += attacker.damage_bonus
    return max(1, dmg)


def attack(attacker, defender, ctx, weapon_item=None):
    """Возвращает (текст, цвет, звук)."""
    audio = ctx.audio
    dtitle = defender.title

    if random.random() > hit_chance(attacker, defender):
        if attacker.is_player:
            msg = t("c.miss", name=dtitle)
            audio.play("miss")
            return msg, C.MSG_WARN, "miss"

    dmg = roll_damage(attacker)
    extra = ""
    if weapon_item is not None and weapon_item.blessed and random.random() < 0.15:
        dmg += random.randint(1, 4)
        extra = t("c.flash")

    # броня немного гасит урон
    if random.random() < min(0.5, defender.ac_total * 0.03):
        dmg -= random.randint(1, max(1, dmg // 3))
    dmg = max(1, dmg)

    died = defender.take_damage(dmg, attacker, cause=attacker.name)
    ctx.floats.append((defender.x, defender.y, f"-{dmg}",
                       C.RED if defender.is_player else C.ORANGE, 12))

    if attacker.is_player:
        msg = t("c.hit", name=dtitle, d=dmg) + extra
        audio.play("hit")
        if died:
            msg += t("c.kill", name=dtitle)
            audio.play("kill")
        return msg, C.MSG_GOOD, "hit"
    else:
        msg = t("c.hurt", name=attacker.title, d=dmg)
        audio.play("player_hurt")
        if died:
            msg += t("c.you_die")
            audio.play("player_die")
        return msg, C.MSG_BAD, "hurt"


def ranged_attack(attacker, target, ctx, damage_mult=1.0):
    audio = ctx.audio
    if target is None:
        audio.play("miss")
        return t("c.whistle"), C.MSG_WARN

    chance = hit_chance(attacker, target) - 0.15
    if random.random() > max(0.1, chance):
        audio.play("miss")
        return t("c.missile_miss", name=target.title), C.MSG_WARN

    weapon = getattr(attacker, "weapon_dmg", None) if attacker.is_player else None
    n, s = (weapon() if callable(weapon) else weapon) or attacker.dmg
    dmg = max(1, int(random.randint(n, s) * damage_mult) + attacker.damage_bonus)
    died = target.take_damage(dmg, attacker, cause=attacker.name)
    ctx.floats.append((target.x, target.y, f"-{dmg}", C.ORANGE, 12))
    msg = t("c.missile_hit", name=target.title, d=dmg)
    audio.play("hit")
    if died:
        msg += t("c.kill", name=target.title)
        audio.play("kill")
    return msg, C.MSG_GOOD
