"""Предметы Backrooms. Старые ID и kind сохранены для эффектов и сохранений.

Игровые названия на обоих языках находятся в lang.ITEM_NAMES.
"""

from __future__ import annotations

import random

from engine import config as C


# --------------------------------------------------------------------------
# Реестр предметов
# --------------------------------------------------------------------------
# kind: weapon | armor | potion | scroll | wand | ring | food | gold | tool | missile
# slot: куда надевается/берётся: weapon | armor | helm | ring | None
ITEMS: dict[str, dict] = {
    # --- Оружие ----------------------------------------------------------
    "dagger":        dict(kind="weapon", slot="weapon", glyph=")", color=C.LIGHT_GRAY, dmg=(1, 4),  hit=2,  price=100,  tier=1),
    "short sword":   dict(kind="weapon", slot="weapon", glyph=")", color=C.WHITE,     dmg=(1, 6),  hit=3,  price=200,  tier=1),
    "long sword":    dict(kind="weapon", slot="weapon", glyph=")", color=C.WHITE,     dmg=(1, 8),  hit=4,  price=400,  tier=2),
    "axe":           dict(kind="weapon", slot="weapon", glyph=")", color=C.LIGHT_GRAY, dmg=(2, 4),  hit=3,  price=400,  tier=2),
    "mace":          dict(kind="weapon", slot="weapon", glyph=")", color=C.LIGHT_GRAY, dmg=(1, 6),  hit=6,  price=300,  tier=1),
    "war hammer":    dict(kind="weapon", slot="weapon", glyph=")", color=C.LIGHT_GRAY, dmg=(1, 4),  hit=5,  price=350,  tier=1),
    "quarterstaff":  dict(kind="weapon", slot="weapon", glyph=")", color=C.BROWN,     dmg=(1, 6),  hit=5,  price=100,  tier=1),
    "staff":         dict(kind="weapon", slot="weapon", glyph=")", color=C.BROWN,     dmg=(1, 8),  hit=4,  price=500,  tier=2),
    "spear":         dict(kind="weapon", slot="weapon", glyph=")", color=C.LIGHT_GRAY, dmg=(1, 9),  hit=4,  price=300,  tier=1),
    "orcish axe":    dict(kind="weapon", slot="weapon", glyph=")", color=C.GREEN,     dmg=(2, 5),  hit=4,  price=400,  tier=2),
    "bow":           dict(kind="weapon", slot="weapon", glyph=")", color=C.BROWN,     dmg=(1, 6),  hit=2,  price=300,  tier=1, ranged=8),
    "crossbow":      dict(kind="weapon", slot="weapon", glyph=")", color=C.BROWN,     dmg=(1, 8),  hit=2,  price=400,  tier=2, ranged=9),
    # --- Броня: разные слоты, носится вместе ------------------------------
    "leather armor": dict(kind="armor", slot="armor", glyph="[", color=C.BROWN,     ac=2, price=200, tier=1),
    "studded leather":dict(kind="armor", slot="armor", glyph="[", color=C.BROWN,     ac=3, price=300, tier=1),
    "ring mail":     dict(kind="armor", slot="armor", glyph="[", color=C.CYAN,      ac=4, price=500, tier=2),
    "scale mail":    dict(kind="armor", slot="armor", glyph="[", color=C.CYAN,      ac=5, price=800, tier=2),
    "chain mail":    dict(kind="armor", slot="armor", glyph="[", color=C.LIGHT_GRAY,ac=6, price=1200,tier=3),
    "orcish helm":   dict(kind="armor", slot="helm",  glyph="[", color=C.GREEN,     ac=1, price=200, tier=1),
    "wooden shield": dict(kind="armor", slot="shield",glyph="[", color=C.BROWN,     ac=1, price=150, tier=1),
    "cloak":         dict(kind="armor", slot="cloak", glyph="[", color=C.PURPLE,   ac=1, price=100, tier=1),
    # --- Снаряды ---------------------------------------------------------
    "arrow":         dict(kind="missile", glyph="}", color=C.LIGHT_GRAY, price=20, tier=1),
    "crossbow bolt": dict(kind="missile", glyph="}", color=C.BROWN,     price=40, tier=1),
    # --- Зелья -----------------------------------------------------------
    "potion of healing":     dict(kind="potion", glyph="!", color=C.RED,    price=50,  tier=1),
    "potion of extra healing":dict(kind="potion", glyph="!", color=C.PINK,  price=100, tier=1),
    "potion of full healing":dict(kind="potion", glyph="!", color=C.WHITE,  price=300, tier=2),
    "potion of gain level":  dict(kind="potion", glyph="!", color=C.PURPLE, price=200, tier=2),
    "potion of strength":    dict(kind="potion", glyph="!", color=C.ORANGE, price=150, tier=2),
    "potion of poison":      dict(kind="potion", glyph="!", color=C.DARK_GREEN, price=80, tier=1),
    "potion of acid":        dict(kind="potion", glyph="!", color=C.YELLOW, price=80, tier=1),
    "potion of confusion":   dict(kind="potion", glyph="!", color=C.BLUE,   price=100, tier=1),
    "potion of hallucination":dict(kind="potion",glyph="!", color=C.CYAN,   price=100, tier=1),
    "potion of booze":       dict(kind="potion", glyph="!", color=C.GREEN,  price=50,  tier=1),
    "potion of sleeping":    dict(kind="potion", glyph="!", color=C.BLUE,   price=80,  tier=1),
    "water":                 dict(kind="potion", glyph="!", color=C.CYAN,   price=10,  tier=0),
    "distilled water":       dict(kind="potion", glyph="!", color=C.WHITE, price=10, tier=0),
    "salt water":            dict(kind="potion", glyph="!", color=C.CYAN, price=5, tier=0),
    "stagnant water":        dict(kind="potion", glyph="!", color=C.DARK_GREEN, price=5, tier=0),
    # --- Свитки ----------------------------------------------------------
    "noclip guide":          dict(kind="scroll", glyph="?", color=C.CYAN,    price=100, tier=1),
    "scroll of identify":    dict(kind="scroll", glyph="?", color=C.WHITE,   price=50,  tier=1),
    "scroll of mapping":     dict(kind="scroll", glyph="?", color=C.WHITE,   price=80,  tier=1),
    "scroll of magic mapping":dict(kind="scroll", glyph="?", color=C.CYAN,  price=120, tier=2),
    "scroll of teleport":    dict(kind="scroll", glyph="?", color=C.YELLOW,  price=100, tier=2),
    "scroll of aggravate monster":dict(kind="scroll", glyph="?", color=C.RED, price=150, tier=2),
    "scroll of amnesia":     dict(kind="scroll", glyph="?", color=C.PINK,   price=150, tier=2),
    "scroll of destroy armor":dict(kind="scroll", glyph="?", color=C.RED,   price=100, tier=1),
    "scroll of fire":        dict(kind="scroll", glyph="?", color=C.ORANGE, price=150, tier=2),
    "scroll of scare monster":dict(kind="scroll", glyph="?", color=C.GREEN,  price=80,  tier=1),
    "scroll of charging":    dict(kind="scroll", glyph="?", color=C.GREEN,  price=180, tier=2),
    "scroll of luck":        dict(kind="scroll", glyph="?", color=C.GREEN,  price=200, tier=3),
    "scroll of nothing":     dict(kind="scroll", glyph="?", color=C.GRAY,   price=0,   tier=0),
    # --- Палочки ---------------------------------------------------------
    "wand of light":     dict(kind="wand", glyph="/", color=C.YELLOW,  charges=5, price=50,  tier=1),
    "wand of dig":       dict(kind="wand", glyph="/", color=C.YELLOW,  charges=5, price=80,  tier=1),
    "wand of striking":  dict(kind="wand", glyph="/", color=C.YELLOW,  charges=5, price=150, tier=2),
    "wand of fire":      dict(kind="wand", glyph="/", color=C.ORANGE,  charges=4, price=150, tier=2),
    "wand of cold":      dict(kind="wand", glyph="/", color=C.CYAN,    charges=4, price=150, tier=2),
    "wand of sleep":     dict(kind="wand", glyph="/", color=C.PURPLE,  charges=4, price=120, tier=2),
    "wand of lightning": dict(kind="wand", glyph="/", color=C.BLUE,    charges=4, price=200, tier=2),
    "wand of nothing":   dict(kind="wand", glyph="/", color=C.GRAY,    charges=1, price=0,   tier=0),
    # --- Кольца ----------------------------------------------------------
    "ring of strength":     dict(kind="ring", glyph="=", color=C.ORANGE, ac=0, price=300, tier=2),
    "ring of dexterity":    dict(kind="ring", glyph="=", color=C.GREEN,  ac=0, price=300, tier=2),
    "ring of protection":   dict(kind="ring", glyph="=", color=C.CYAN,   ac=1, price=400, tier=2),
    "ring of constitution": dict(kind="ring", glyph="=", color=C.PINK,   ac=0, price=400, tier=2),
    "ring of damage":       dict(kind="ring", glyph="=", color=C.RED,    ac=0, price=450, tier=2),
    "ring of hunger":       dict(kind="ring", glyph="=", color=C.DARK_GREEN, ac=0, price=120, tier=1),
    # --- Еда и разное ----------------------------------------------------
    "food ration":      dict(kind="food", glyph="%", color=C.BROWN, saturation=10, food_tags=('dry',), price=60, tier=1),
    "tripe ration":     dict(kind="food", glyph="%", color=C.DARK_RED, saturation=10, food_tags=('salty', 'moist'), price=20, tier=1),
    "apple":            dict(kind="food", glyph="%", color=C.RED, saturation=5, food_tags=('sweet', 'moist'), price=10, tier=0),
    "crackers":         dict(kind="food", glyph="%", color=C.BROWN, saturation=5, food_tags=('dry',), price=10, tier=0),
    "salted nuts":      dict(kind="food", glyph="%", color=C.BROWN, saturation=5, food_tags=('salty', 'dry'), price=15, tier=0),
    "chocolate":        dict(kind="food", glyph="%", color=C.DARK_BROWN, saturation=5, food_tags=('sweet', 'dry'), price=15, tier=0),
    "cucumber":         dict(kind="food", glyph="%", color=C.GREEN, saturation=5, food_tags=('moist',), price=10, tier=0),
    "carrot":           dict(kind="food", glyph="%", color=C.ORANGE, saturation=5, food_tags=('moist',), price=10, tier=0),
    "fried potatoes":   dict(kind="food", glyph="%", color=C.YELLOW, saturation=10, food_tags=('salty', 'fried'), price=25, tier=1),
    "borscht":          dict(kind="food", glyph="%", color=C.DARK_RED, saturation=50, food_tags=('salty', 'moist'), price=60, tier=1),
    "gold piece":       dict(kind="gold", glyph="$", color=C.YELLOW,  price=1, tier=0),
    "pick-axe":         dict(kind="tool", slot="weapon", glyph="(", color=C.LIGHT_GRAY, dmg=(1, 4), hit=2, price=50, tier=1),
    "lantern":          dict(kind="tool", slot="weapon", glyph="(", color=C.YELLOW,    dmg=(1, 3), hit=1, price=50, tier=1),
}

# Питьевые жидкости участвуют в питании; яд/кислота и прочие опасные жидкости — нет.
for _name in ('wood plank','nails','rag','thread'):
    ITEMS[_name]=dict(kind='material',glyph=';',color=C.BROWN,price=5,tier=0)
ITEMS['needle']=dict(kind='tool',glyph='(',color=C.LIGHT_GRAY,price=5,tier=0)
ITEMS['crafted jacket']=dict(kind='armor',slot='armor',glyph='[',color=C.BROWN,ac=2,price=25,tier=0)
for _name in ('scrap metal','cord','fuel','potato','salt','cardboard'):
    ITEMS[_name]=dict(kind='material',glyph=';',color=C.BROWN,price=5,tier=0)
for _name in ('cooking pot','lighter'):
    ITEMS[_name]=dict(kind='tool',glyph='(',color=C.LIGHT_GRAY,price=15,tier=0)
ITEMS['improvised spear']=dict(kind='weapon',slot='weapon',glyph=')',color=C.BROWN,dmg=(2,7),hit=2,price=20,tier=1)
ITEMS['nailed club']=dict(kind='weapon',slot='weapon',glyph=')',color=C.BROWN,dmg=(2,6),hit=1,price=15,tier=1)
ITEMS['vegetable soup']=dict(kind='food',glyph='%',color=C.ORANGE,saturation=25,food_tags=('moist',),price=20,tier=1)
ITEMS['trail mix']=dict(kind='food',glyph='%',color=C.BROWN,saturation=15,food_tags=('salty','sweet','dry'),price=20,tier=1)

for _name in ('water', 'distilled water', 'potion of healing',
              'potion of extra healing', 'potion of full healing'):
    ITEMS[_name].update(saturation=5, hydrating=True)
ITEMS['stagnant water'].update(saturation=2, hydrating=False)
ITEMS['potion of booze'].update(saturation=1, hydrating=False)

# Веса выпадения по уровню
from .equipment_catalog import install as install_clothing
install_clothing(ITEMS)
for _name in ('screwdriver','pliers','hacksaw','wrench','hand drill'):
    ITEMS[_name]=dict(kind='tool',slot='weapon',glyph='(',color=C.LIGHT_GRAY,dmg=(1,3),hit=1,price=20,tier=1)
for _name in ('small parts','steel plate','fabric roll','rubber','machine parts'):
    ITEMS[_name]=dict(kind='material',glyph=';',color=C.GRAY,price=10,tier=1)
ITEMS['crowbar']=dict(kind='weapon',slot='weapon',glyph=')',color=C.GRAY,dmg=(2,7),hit=2,price=35,tier=2)
ITEMS['reinforced spear']=dict(kind='weapon',slot='weapon',glyph=')',color=C.LIGHT_GRAY,dmg=(3,9),hit=3,price=60,tier=3)

WEAPON_POOL = ["dagger", "short sword", "mace", "war hammer", "quarterstaff",
               "long sword", "axe", "spear", "staff", "orcish axe", "bow", "crossbow"]
ARMOR_POOL = ["leather armor", "studded leather", "ring mail", "scale mail",
              "chain mail", "orcish helm", "wooden shield", "cloak"]
POTION_POOL = ["potion of healing", "potion of extra healing", "potion of gain level",
               "potion of strength", "potion of poison", "potion of acid",
               "potion of confusion", "potion of hallucination", "potion of booze",
               "potion of sleeping", "potion of full healing", "water",
               "distilled water", "salt water", "stagnant water"]
SCROLL_POOL = ["scroll of identify", "scroll of mapping", "scroll of teleport",
               "scroll of magic mapping", "scroll of aggravate monster",
               "scroll of amnesia", "scroll of destroy armor", "scroll of fire",
               "scroll of scare monster", "scroll of charging", "scroll of luck",
               "scroll of nothing"]
WAND_POOL = ["wand of light", "wand of dig", "wand of striking", "wand of fire",
             "wand of cold", "wand of sleep", "wand of lightning", "wand of nothing"]
RING_POOL = ["ring of strength", "ring of dexterity", "ring of protection",
             "ring of constitution", "ring of damage", "ring of hunger"]
FOOD_POOL = [name for name, spec in ITEMS.items() if spec['kind'] == 'food']


class Item:
    __slots__ = ("name", "count", "charges", "charges_max", "identified",
                 "equipped", "cursed", "blessed", "qty", "artifact", "value")

    def __init__(self, name: str, count: int = 1, rng=None):
        rng = rng if rng is not None else random
        assert name in ITEMS, f"unknown item: {name}"
        self.name = name
        self.count = count
        spec = ITEMS[name]
        self.charges = spec.get("charges", 0)
        self.charges_max = self.charges
        self.identified = spec["kind"] in ("gold", "food", "weapon", "armor", "missile", "tool", "material")
        self.equipped = None
        self.cursed = rng.random() < 0.08 and spec["kind"] not in ("gold", "food")
        self.blessed = (not self.cursed) and rng.random() < 0.10
        self.qty = rng.randint(1, 6)
        self.artifact = False
        self.value = spec.get("price", 10)

    # --- доступ к характеристикам ---------------------------------------
    @property
    def spec(self) -> dict:
        return ITEMS[self.name]

    @property
    def kind(self) -> str:
        return ITEMS[self.name]["kind"]

    @property
    def slot(self) -> str | None:
        return ITEMS[self.name].get("slot", "ring" if self.kind == "ring" else None)

    @property
    def glyph(self) -> str:
        return ITEMS[self.name]["glyph"]

    @property
    def color(self):
        return ITEMS[self.name]["color"]

    @property
    def is_potion(self):
        return self.kind == "potion"

    def display_name(self) -> str:
        from .lang import item_name, kind_name, t
        if self.kind == "gold":
            return f"{self.qty} {t('kind.gold')}"
        if self.kind == "food":
            return item_name(self.name)
        if self._known():
            prefix = ""
            if self.blessed:
                prefix += t("item.blessed") + " "
            if self.cursed:
                prefix += t("item.cursed") + " "
            return prefix + item_name(self.name)
        return t("item.unident", k=kind_name(self.kind))

    def _known(self) -> bool:
        if self.kind in ("weapon", "armor", "missile", "gold", "tool", "food"):
            return True
        return self.identified

    def label(self) -> str:
        from .lang import t
        txt = self.display_name()
        if self.kind == "wand" and self.charges_max:
            txt += t("item.charges", a=self.charges, b=self.charges_max)
        if self.count > 1:
            txt += t("item.label.cnt", n=self.count)
        return txt

    def to_dict(self) -> dict:
        return {s: getattr(self, s) for s in self.__slots__}

    @staticmethod
    def from_dict(d: dict) -> "Item":
        it = Item.__new__(Item)
        for s in Item.__slots__:
            setattr(it, s, d.get(s))
        it.identified = bool(it.identified)
        it.equipped = it.equipped or None
        return it


def make_random_item(level: int = 1, forced_kind: str | None = None, rng=None) -> Item:
    r = rng or random
    kind = forced_kind or r.choice(["weapon", "armor", "potion", "scroll", "wand",
                                    "food", "ring", "gold", "tool", "missile"])
    if kind == "gold":
        it = Item("gold piece", rng=r)
        it.qty = r.randint(1, 60) + level * 8
        it.value = it.qty
        return it
    if kind == "weapon" and level <= 1:
        name = r.choice(["dagger", "short sword", "mace", "quarterstaff"])
    elif kind == "weapon":
        name = r.choice(WEAPON_POOL)
    elif kind == "armor":
        name = r.choice(ARMOR_POOL)
    elif kind == "potion":
        name = r.choice(POTION_POOL)
    elif kind == "scroll":
        name = r.choice(SCROLL_POOL)
    elif kind == "wand":
        name = r.choice(WAND_POOL)
    elif kind == "ring":
        name = r.choice(RING_POOL)
    elif kind == "food":
        name = r.choice(FOOD_POOL)
    elif kind == "missile":
        name = "arrow" if r.random() < 0.7 else "crossbow bolt"
    else:
        name = r.choice(["pick-axe", "lantern"])
    it = Item(name, rng=r)
    if r.random() < 0.5 and name not in ("lantern", "pick-axe"):
        it.identified = True
    return it
