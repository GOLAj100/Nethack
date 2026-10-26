"""Существа: базовый актёр, игрок, параметры и производные характеристики."""

from __future__ import annotations

import random

from engine import config as C
from . import survival

STR_DMG_BONUS = [
    (-2, -3), (-1, -3), (0, -3), (1, -3), (2, -3), (3, -3), (4, -3),
    (5, -2), (6, -2), (7, -1), (8, -1), (9, -1), (10, -1), (11, 0),
    (12, 0), (13, 0), (14, 0), (15, 0), (16, 0), (17, 1), (18, 1),
    (19, 2), (20, 2), (21, 3), (22, 3),
]


def str_dmg_bonus(s: int) -> int:
    if s < 5:
        return -3
    for hi, bonus in STR_DMG_BONUS:
        if s <= hi:
            return bonus
    return 3


def dex_hit_bonus(dx: int) -> int:
    if dx < 4:
        return -3
    if dx < 6:
        return -2
    if dx < 8:
        return -1
    if dx < 14:
        return 0
    if dx < 16:
        return 1
    if dx < 18:
        return 2
    return 3


class Actor:
    is_player = False

    def __init__(self, x=0, y=0, name="it", glyph="?", color=C.WHITE,
                 hp=1, max_hp=1, ac=0, dmg=(1, 2), to_hit=0,
                 speed=100, depth=1, tier=1):
        self.x, self.y = x, y
        self.name = name
        self.glyph = glyph
        self.color = color
        self.hp = hp
        self.max_hp = max_hp
        self.base_ac = ac
        self.dmg = dmg
        self.to_hit = to_hit
        self.speed = speed
        self.depth = depth
        self.b_level = depth
        self.world_z = 0
        self.behavior = "chase"
        self.tier = tier
        self.status: dict[str, int] = {}
        self.awake = False
        self.hostile = False
        self.energy = 0
        self.last_seen = None
        self.corpse = False

    # --- состояние --------------------------------------------------------
    @property
    def alive(self) -> bool:
        return self.hp > 0 and not self.corpse

    @property
    def title(self) -> str:
        """Отображаемое имя (с учётом языка)."""
        from .lang import monster_name
        return monster_name(self.name)

    def is_asleep(self) -> bool:
        return self.status.get("asleep", 0) > 0

    def is_confused(self) -> bool:
        return self.status.get("confused", 0) > 0

    def is_fleeing(self) -> bool:
        return self.status.get("flee", 0) > 0

    # --- Производные характеристики --------------------------------------
    @property
    def ac_total(self) -> int:
        return self.base_ac

    @property
    def damage_bonus(self) -> int:
        return 0

    @property
    def hit_bonus(self) -> int:
        return self.to_hit

    # --- Действия ---------------------------------------------------------
    def heal(self, amount: int) -> int:
        before = self.hp
        self.hp = min(self.max_hp, self.hp + amount)
        return self.hp - before

    def take_damage(self, amount: int, source=None, cause="damage"):
        self.hp -= max(0, amount)
        if self.hp <= 0:
            self.hp = 0
            self.corpse = True
            return True
        return False

    def moves_left(self) -> int:
        return self.speed

    def flees(self, source=None, turns: int = 8) -> bool:
        """Испугаться и убежать."""
        self.status["flee"] = max(self.status.get("flee", 0), turns)
        self.awake = True
        return True


class Player(Actor):
    is_player = True

    def __init__(self, x=0, y=0):
        super().__init__(x, y, name="you", glyph="@", color=C.WHITE,
                         hp=27, max_hp=27, ac=10, speed=100)
        self.lvl = 1
        self.xp = 0
        self.str = 10
        self.dex = 10
        self.con = 10
        self.gold = 0
        survival.initialize(self)
        self.god_mode = False
        self.debug_fly = False
        self.debug_noclip = False
        self.depth = 1
        self.b_level = 1
        self.world_z = 0
        self.chunk_x = self.chunk_y = 0
        self.items: list = []
        self.skills = {'building':0,'crafting':0}
        self.carried_furniture = []
        self.kills = 0
        self.turns = 0
        self.max_turns = 0
        self.deepest = 1
        self.status["blessed_water"] = 0

    # --- Характеристики ---------------------------------------------------
    def take_damage(self, amount, source=None, cause="damage"):
        if self.god_mode:
            return False
        return super().take_damage(amount, source, cause)

    @property
    def max_hp(self):
        level = survival.reserve_level(self) if hasattr(self, 'body_reserve') else 0
        penalty = min(0.7, max(0, -level) * 0.1)
        return max(1, int(self._base_max_hp * (1.0 - penalty)))

    @max_hp.setter
    def max_hp(self, value):
        self._base_max_hp = int(value)

    @property
    def base_max_hp(self):
        return self._base_max_hp

    @property
    def exhaustion_level(self):
        return survival.reserve_level(self)

    @property
    def exhaustion_progress(self):
        return abs(self.body_reserve) % survival.RESERVE_STEP

    @property
    def exhaustion_color(self):
        return survival.reserve_color(self)

    @property
    def nutrition(self):
        """Совместимость старых вызовов: теперь значение в шкале 0..100."""
        return self.saturation

    @nutrition.setter
    def nutrition(self, value):
        self.saturation = max(0, min(survival.SATURATION_MAX, int(value)))

    def ring_bonus(self, stat):
        return 2 * sum(it.equipped == "ring" and it.name == "ring of " + stat
                       for it in getattr(self, "items", []))

    @property
    def str(self):
        return self._str + self.ring_bonus("strength")

    @str.setter
    def str(self, value):
        self._str = value - self.ring_bonus("strength")

    @property
    def dex(self):
        return self._dex + self.ring_bonus("dexterity")

    @dex.setter
    def dex(self, value):
        self._dex = value - self.ring_bonus("dexterity")

    @property
    def con(self):
        return self._con + self.ring_bonus("constitution")

    @con.setter
    def con(self, value):
        self._con = value - self.ring_bonus("constitution")

    @property
    def ac_total(self) -> int:
        from .items import ITEMS
        ac = self.base_ac
        for it in self.items:
            if not it.equipped:
                continue
            spec = ITEMS[it.name]
            if it.equipped in ("armor", "helm", "shield", "cloak"):
                ac -= spec.get("ac", 0) + spec.get('protection',0)
            elif it.equipped == "ring" and "protection" in it.name:
                ac -= 1
        return ac

    @property
    def clothing_weight(self):
        return sum(it.spec.get('weight',0) for it in self.items if it.equipped)

    @property
    def clothing_warmth(self):
        return sum(it.spec.get('warmth',0) for it in self.items if it.equipped)

    @property
    def clothing_mobility(self):
        return sum(it.spec.get('mobility',0) for it in self.items if it.equipped)

    @staticmethod
    def items_def(it):
        from .items import ITEMS
        return ITEMS[it.name]

    @property
    def damage_bonus(self) -> int:
        bonus = str_dmg_bonus(self.str)
        for it in self.items:
            if it.equipped == "ring" and "damage" in it.name:
                bonus += random.randint(1, 3)
        return bonus

    @property
    def hit_bonus(self) -> int:
        weapon = self.wielded
        return dex_hit_bonus(self.dex) + (weapon.spec.get("hit", 0) if weapon else 0)

    @property
    def wielded(self):
        out = [it for it in self.items if it.equipped == "weapon"]
        return out[0] if out else None

    @property
    def weapon_dmg(self):
        w = self.wielded
        if w is None:
            return (1, 3)
        spec = self.items_def(w)
        return tuple(spec.get("dmg", (1, 3)))

    @property
    def is_ranged_only(self) -> bool:
        w = self.wielded
        if w is None:
            return False
        return bool(self.items_def(w).get("ranged"))

    def equipped_of(self, slot):
        return [it for it in self.items if it.equipped == slot]

    def unequip_slot(self, slot, keep=None):
        """Снимает всё из слота (кроме keep)."""
        for it in list(self.items):
            if it.equipped == slot and it is not keep:
                it.equipped = None

    def equip(self, item):
        """Надеть/взять с учётом слота. Возвращает снятые предметы."""
        slot = item.slot
        if not slot:
            return []
        removed = []
        if slot == "ring":
            # два кольца одновременно
            worn = self.equipped_of("ring")
            if len(worn) >= 2 and item not in worn:
                removed.append(worn[0])
                worn[0].equipped = None
        else:
            for it in self.equipped_of(slot):
                removed.append(it)
                it.equipped = None
        item.equipped = slot
        return removed

    # --- Опыт и уровни ----------------------------------------------------
    def xp_for_next_level(self) -> int:
        lvl = self.lvl
        return 20 * lvl * lvl + 100 * (lvl - 1)

    def xp_for_level(self, lvl: int) -> int:
        return 20 * lvl * lvl + 100 * (lvl - 1)

    def gain_exp(self, amount: int, source: str = "") -> list[str]:
        from .lang import t
        msgs = []
        self.xp += amount
        if source:
            msgs.append(t("m.xp", src=source, n=amount))
        while self.xp >= self.xp_for_next_level():
            need = self.xp_for_next_level()
            self.xp -= need
            self.lvl += 1
            self._base_max_hp += random.randint(2, 5) + max(0, (self.con - 10) // 2)
            self.hp = self.max_hp
            self.base_ac = max(6, self.base_ac - (1 if self.lvl % 2 == 0 else 0))
            msgs.append(t("m.level_up", n=self.lvl))
        return msgs

    # --- Насыщение и запасы ------------------------------------------------
    def nutrition_state(self) -> str:
        from .lang import t
        n = self.saturation
        if n >= 75:
            return t("m.hunger.0")
        if n >= 25:
            return t("m.hunger.1")
        if n > 0:
            return t("m.hunger.2")
        return t("m.hunger.3")

    def consume(self, nutrition: int):
        return survival.add_saturation(self, nutrition)

    def nourish(self, spec):
        return survival.nourish(self, spec)

    def exhaustion_state(self):
        from .lang import t
        level = self.exhaustion_level
        key = 'exhausted' if level < 0 else ('obese' if level >= 5 else
              ('reserve' if level > 1 else ('plump' if level == 1 else 'neutral')))
        return t('body.' + key)

    def remove_armor(self) -> bool:
        slots = ("armor", "helm", "cloak", "shield", "ring")
        for slot in slots:
            if self.equipped_of(slot):
                self.equipped_of(slot)[0].equipped = None
                return True
        return False

    # --- Сохранение -------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "x": self.x, "y": self.y, "hp": self.hp, "max_hp": self.max_hp,
            "base_ac": self.base_ac, "lvl": self.lvl, "xp": self.xp,
            "str": self._str, "dex": self._dex, "con": self._con,
            "gold": self.gold, "depth": self.depth,
            "base_max_hp": self.base_max_hp,
            "saturation": self.saturation, "body_reserve": self.body_reserve,
            "stamina": self.stamina, "sanity": self.sanity,
            "last_nourished_turn": self.last_nourished_turn, "meal": self.meal,
            "walk_steps": self.walk_steps, "slow_steps": getattr(self, 'slow_steps', 0),
            "sleep_healing": self.sleep_healing,
            "awake_turns": self.awake_turns, "sleep_recovery": self.sleep_recovery,
            "b_level": self.b_level, "world_z": self.world_z,
            "chunk_x": self.chunk_x, "chunk_y": self.chunk_y,
            "items": [it.to_dict() for it in self.items],
            "skills": dict(self.skills), "carried_furniture": list(self.carried_furniture),
            "status": dict(self.status), "kills": self.kills,
            "turns": self.turns, "max_turns": self.max_turns,
            "deepest": self.deepest,
            "knowledge": list(getattr(self,'knowledge',[])),
        }

    def load_dict(self, d: dict):
        from .items import Item
        for k, v in d.items():
            if k in ('nutrition', 'max_hp', 'base_max_hp'):
                continue
            if k in ("str", "dex", "con"):
                setattr(self, "_" + k, v)
            elif k == "items":
                self.items = [Item.from_dict(i) for i in v]
            elif k == "status":
                self.status = {kk: vv for kk, vv in v.items()}
            else:
                setattr(self, k, v)
        self._base_max_hp = d.get('base_max_hp', d.get('max_hp', 20))
        if 'saturation' not in d:
            self.saturation = max(0, min(100, int(d.get('nutrition', 1000) / 10)))
            self.last_nourished_turn = self.turns
        self.stamina = max(-50, min(50, self.stamina))
        self.moved_this_turn = False
        self.movement_delay = 0
        self.hp = min(self.hp, self.max_hp)
