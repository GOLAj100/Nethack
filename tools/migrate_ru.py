"""Одноразовый скрипт: переводит строковые литералы в game/app.py на t("...")."""

import io
import re
import sys

PATH = "game/app.py"

REPL = [
    # --- new_game / init -------------------------------------------------
    ('from .save import has_save, load_game, save_game',
     'from .lang import (LANG_NAMES, load_settings, other_lang, save_settings,\n'
     '                   set_lang, t)\nfrom .save import has_save, load_game, save_game'),
    ('self.msg("You descend into the dungeon. Beware.", C.MSG_GOOD)',
     'self.msg(t("m.descend"), C.MSG_GOOD)'),
    ('self.msg("Press ? for help, m for the full map, S to save.", C.MSG_HINT)',
     'self.msg(t("m.help_hint"), C.MSG_HINT)'),
    ('self.msg("Game loaded.", C.MSG_GOOD)',
     'self.msg(t("m.loaded"), C.MSG_GOOD)'),
    ('self.msg("No save found.", C.MSG_BAD)',
     'self.msg(t("m.no_save"), C.MSG_BAD)'),

    # --- move -------------------------------------------------------------
    ('self.msg("The wall is solid.", C.MSG_HINT)\n            self.audio.play("door_bump", 0.4)',
     'self.msg(t("m.wall"), C.MSG_HINT)\n            self.audio.play("door_bump", 0.4)'),
    ('self.msg("The wall is solid.", C.MSG_HINT)\n            self.audio.play("door_bump", 0.35)',
     'self.msg(t("m.wall"), C.MSG_HINT)\n            self.audio.play("door_bump", 0.35)'),
    ('self.msg("The hedge resists you.", C.MSG_WARN)',
     'self.msg(t("m.hedge"), C.MSG_WARN)'),
    ('self.msg("You open the door.", C.MSG_INFO)',
     'self.msg(t("m.open_door"), C.MSG_INFO)'),
    ('self.msg("You step over a corpse.", C.MSG_HINT)',
     'self.msg(t("m.corpse"), C.MSG_HINT)'),
    ('self.msg("You stumble...", C.MSG_WARN)',
     'self.msg(t("m.stumble"), C.MSG_WARN)'),
    ('self.msg("You feel less confused.", C.MSG_INFO)',
     'self.msg(t("m.confused_off"), C.MSG_INFO)'),
    ('self.msg("You wake up.", C.MSG_INFO)',
     'self.msg(t("m.wake"), C.MSG_INFO)'),

    # --- бой --------------------------------------------------------------
    ('self.msg("There is nothing adjacent to fight.", C.MSG_HINT)',
     'self.msg(t("m.nothing_adj"), C.MSG_HINT)'),
    ('options.append((m, f"{m.name} (HP {m.hp}/{m.max_hp})"))',
     'options.append((m, f"{m.title} ({t(\'ui.bars\')} {m.hp}/{m.max_hp})"))'),
    ('            msgs.append(f"{source} (+{amount} xp)")',
     '            msgs.append(t("m.xp", src=source, n=amount))'),
    ('            msgs.append(f"Welcome to experience level {self.lvl}!")',
     '            msgs.append(t("m.level_up", n=self.lvl))'),
    ('self.msg("You wait.", C.MSG_HINT)',
     'self.msg(t("m.wait"), C.MSG_HINT)'),

    # --- предметы ---------------------------------------------------------
    ('self.msg("There is nothing here.", C.MSG_HINT)\n            return False\n        if len(p.items) >= 26:',
     'self.msg(t("m.nothing_here"), C.MSG_HINT)\n            return False\n        if len(p.items) >= 26:'),
    ('self.msg("Your pack is full.", C.MSG_BAD)',
     'self.msg(t("m.pack_full"), C.MSG_BAD)'),
    ('self.msg(f"You pick up {it.qty} gold pieces.", C.MSG_GOOD)',
     'self.msg(t("m.pickup_gold", n=it.qty), C.MSG_GOOD)'),
    ('self.msg(f"You pick up {it.label()}.", C.MSG_GOOD)',
     'self.msg(t("m.pickup", it=it.label()), C.MSG_GOOD)'),
    ('self.msg(f"You pick up {len(here)} item(s).", C.MSG_GOOD)',
     'self.msg(t("m.pickup_many", n=len(here)), C.MSG_GOOD)'),
    ('            mark = f" ({it.equipped})"',
     '            mark = f" [{it.equipped}]"'),
    ('        self.msg("You have to pick it up first.", C.MSG_WARN)',
     '        self.msg(t("need.pickup"), C.MSG_WARN)'),
    ('        self.show_menu("Inventory", self._item_labels(p.items), cb, width=48)',
     '        self.show_menu(t("ui.inventory"), self._item_labels(p.items), cb, width=48)'),
    ('        self.show_menu("Fight what?", [o[1] for o in options], cb, width=34)',
     '        self.show_menu(t("pick.fight"), [o[1] for o in options], cb, width=34)'),
    ('        self.show_menu("Items here", self._item_labels(here), cb, width=48)',
     '        self.show_menu(t("ui.items_here"), self._item_labels(here), cb, width=48)'),
    ('        entries = ["Info", "Drop it", "Eat it", "Quaff it", "Read it",\n'
     '                   "Wear it", "Wield it", "Take off", "Fire it", "Zap it",\n'
     '                   "Throw it"]',
     '        entries = [t("act.info"), t("act.drop"), t("act.eat"), t("act.quaff"),\n'
     '                   t("act.read"), t("act.wear"), t("act.wield"), t("act.takeoff"),\n'
     '                   t("act.fire"), t("act.zap"), t("act.throw")]'),
    ('        self.show_menu(item.display_name(), entries, cb, width=34)',
     '        self.show_menu(item.display_name(), entries, cb, width=34)'),
    ('            lines.append((f"damage {spec[\'dmg\'][0]}d{spec[\'dmg\'][1]}", C.WHITE))\n'
     '            lines.append((f"to-hit {spec.get(\'hit\', 0)}", C.WHITE))\n'
     '            if spec.get("ranged"):\n'
     '                lines.append((f"range {spec[\'ranged\']}", C.WHITE))\n'
     '        elif item.kind == "armor":\n'
     '            lines.append((f"armor class {spec[\'ac\']}", C.WHITE))\n'
     '        elif item.kind == "ring":\n'
     '            lines.append((f"bonus {spec.get(\'ac\', 0) or \'special\'}", C.WHITE))\n'
     '        elif item.kind == "wand":\n'
     '            lines.append((f"charges {item.charges}/{item.charges_max}", C.WHITE))\n'
     '        elif item.kind == "food":\n'
     '            lines.append((f"nutrition {spec.get(\'nutrition\', 0)}", C.WHITE))\n'
     '        lines.append((f"value ~{item.value} gold", C.YELLOW))\n'
     '        if item.blessed:\n'
     '            lines.append(("It is blessed.", C.CYAN))\n'
     '        if item.cursed:\n'
     '            lines.append(("It is cursed.", C.RED))\n'
     '        self.show_text("Item info", lines)',
     '            lines.append((t("item.damage", n=spec["dmg"][0], s=spec["dmg"][1]), C.WHITE))\n'
     '            lines.append((t("item.to_hit", n=spec.get("hit", 0)), C.WHITE))\n'
     '            if spec.get("ranged"):\n'
     '                lines.append((t("item.range", n=spec["ranged"]), C.WHITE))\n'
     '        elif item.kind == "armor":\n'
     '            lines.append((t("item.ac", n=spec["ac"]), C.WHITE))\n'
     '        elif item.kind == "ring":\n'
     '            lines.append((t("item.bonus"), C.WHITE))\n'
     '        elif item.kind == "wand":\n'
     '            lines.append((t("item.charges", a=item.charges, b=item.charges_max), C.WHITE))\n'
     '        elif item.kind == "food":\n'
     '            lines.append((t("item.nutrition", n=spec.get("nutrition", 0)), C.WHITE))\n'
     '        lines.append((t("item.value", v=item.value), C.YELLOW))\n'
     '        if item.blessed:\n'
     '            lines.append((t("item.blessed"), C.CYAN))\n'
     '        if item.cursed:\n'
     '            lines.append((t("item.cursed"), C.RED))\n'
     '        self.show_text(t("item.info"), lines)'),
    ('        self.msg("You are not carrying anything.", C.MSG_HINT)',
     '        self.msg(t("m.not_carrying"), C.MSG_HINT)'),
    ('        self._pick_carried("Drop what?", self.do_drop)',
     '        self._pick_carried(t("pick.drop"), self.do_drop)'),
    ('        self._pick_carried("Eat what?", self.do_eat, kinds={"food", "gold"})',
     '        self._pick_carried(t("pick.eat"), self.do_eat, kinds={"food", "gold"})'),
    ('        self._pick_carried("Quaff what?", self.do_quaff, kinds={"potion"})',
     '        self._pick_carried(t("pick.quaff"), self.do_quaff, kinds={"potion"})'),
    ('        self._pick_carried("Read what?", self.do_read, kinds={"scroll"})',
     '        self._pick_carried(t("pick.read"), self.do_read, kinds={"scroll"})'),
    ('        self._pick_carried("Wield what?", self.do_wield, kinds={"weapon"})',
     '        self._pick_carried(t("pick.wield"), self.do_wield, kinds={"weapon"})'),
    ('        self._pick_carried("Wear what?", self.do_wear, kinds={"armor", "ring"})',
     '        self._pick_carried(t("pick.wear"), self.do_wear, kinds={"armor", "ring"})'),
    ('            self.msg("You are not wearing anything.", C.MSG_HINT)',
     '            self.msg(t("m.not_wearing"), C.MSG_HINT)'),
    ('        self._pick_from(worn, "Take off what?", self.do_takeoff)',
     '        self._pick_from(worn, t("pick.takeoff"), self.do_takeoff)'),
    ('            self.msg(f"Nothing suitable ({title.lower()}).", C.MSG_HINT)',
     '            self.msg(t("need.suitable"), C.MSG_HINT)'),
    ('            self.show_menu("Identify what?", self._item_labels(p.items), cb, width=48)',
     '            self.show_menu(t("pick.identify"), self._item_labels(p.items), cb, width=48)'),
    ('                    self.msg("You put the scroll away.", C.MSG_HINT)',
     '                    self.msg(t("m.put_away"), C.MSG_HINT)'),

    # --- операции ----------------------------------------------------------
    ('            self.msg(f"You drop {item.label()}.", C.MSG_INFO)',
     '            self.msg(t("m.drop_it", it=item.label()), C.MSG_INFO)'),
    ('            self.msg("There is no room to drop it.", C.MSG_BAD)',
     '            self.msg(t("m.no_room_drop"), C.MSG_BAD)'),
    ('        self.msg("You have to pick it up first.", C.MSG_WARN)\n'
     '        self.audio.play("error", 0.4)\n        return False\n\n    def do_eat',
     '        self.msg(t("need.pickup"), C.MSG_WARN)\n        self.audio.play("error", 0.4)\n'
     '        return False\n\n    def do_eat'),
    ('                self.msg("You swallow a gold piece. That was a mistake.", C.MSG_WARN)',
     '                self.msg(t("m.gold_swallow"), C.MSG_WARN)'),
    ('                self.msg(f"You cannot eat {item.display_name()}.", C.MSG_BAD)',
     '                self.msg(t("m.cannot_eat", it=item.display_name()), C.MSG_BAD)'),
    ('            self.msg(f"You eat {item.name}.", C.MSG_INFO)',
     '            self.msg(t("m.eat_it", it=item.display_name()), C.MSG_INFO)'),
    ('            self.msg(f"You cannot drink {item.display_name()}.", C.MSG_BAD)',
     '            self.msg(t("m.cannot_quaff", it=item.display_name()), C.MSG_BAD)'),
    ('            self.msg("You feel a little worse.", C.MSG_WARN)',
     '            self.msg(t("m.feel_worse"), C.MSG_WARN)'),
    ('            self.msg(f"You cannot read {item.display_name()}.", C.MSG_BAD)',
     '            self.msg(t("m.cannot_read", it=item.display_name()), C.MSG_BAD)'),
    ('        self.msg(f"You now know: {it.display_name()}.", C.MSG_GOOD)',
     '        self.msg(t("m.know", it=it.display_name()), C.MSG_GOOD)'),
    ('            self.msg(f"You cannot wield {item.display_name()}.", C.MSG_BAD)',
     '            self.msg(t("m.cannot_wield", it=item.display_name()), C.MSG_BAD)'),
    ('        self.msg(f"You are now wielding {item.display_name()}.", C.MSG_INFO)',
     '        self.msg(t("m.wield", it=item.display_name()), C.MSG_INFO)'),
    ('            self.msg(f"You cannot wear {item.display_name()}.", C.MSG_BAD)',
     '            self.msg(t("m.cannot_wear", it=item.display_name()), C.MSG_BAD)'),
    ('            self.msg("You feel a chill. Something is wrong.", C.MSG_WARN)',
     '            self.msg(t("m.cold"), C.MSG_WARN)'),
    ('        self.msg(f"You are now wearing {item.display_name()}.", C.MSG_INFO)',
     '        self.msg(t("m.wear", it=item.display_name()), C.MSG_INFO)'),
    ('        self.msg(f"You take off {item.display_name()}.", C.MSG_INFO)',
     '        self.msg(t("m.takeoff", it=item.display_name()), C.MSG_INFO)'),
    ('                self.msg("You have nothing to fire.", C.MSG_HINT)',
     '                self.msg(t("m.no_ammo"), C.MSG_HINT)'),
    ('            self._pick_from(ammo, "Fire what?", self._do_fire_pick)',
     '            self._pick_from(ammo, t("act.fire"), self._do_fire_pick)'),
    ('            self.msg("Nothing to fire.", C.MSG_HINT)',
     '            self.msg(t("m.no_ammo"), C.MSG_HINT)'),
    ('            self.msg("You have no bow or crossbow to shoot with.", C.MSG_BAD)',
     '            self.msg(t("m.no_bow"), C.MSG_BAD)'),
    ('            self.msg("You have nothing to throw.", C.MSG_HINT)',
     '            self.msg(t("m.no_throw"), C.MSG_HINT)'),
    ('        self._pick_from(items, "Throw what?", self._do_throw_pick)',
     '        self._pick_from(items, t("act.throw"), self._do_throw_pick)'),
    ('            self.msg("You have no wands.", C.MSG_HINT)',
     '            self.msg(t("m.no_wands"), C.MSG_HINT)'),
    ('        self._pick_from(wands, "Zap what?", self._do_zap_pick)',
     '        self._pick_from(wands, t("act.zap"), self._do_zap_pick)'),
    ('            self.msg("The wand is spent.", C.MSG_WARN)\n            return\n        self.pending_item = item',
     '            self.msg(t("m.wand_spent"), C.MSG_WARN)\n            return\n        self.pending_item = item'),
    ('            self.msg("The wand is spent.", C.MSG_WARN)\n            return\n        item.charges -= 1',
     '            self.msg(t("m.wand_spent"), C.MSG_WARN)\n            return\n        item.charges -= 1'),

    # --- уровни -----------------------------------------------------------
    ('            self.msg("There are no stairs here.", C.MSG_HINT)',
     '            self.msg(t("m.no_stairs"), C.MSG_HINT)'),
    ('            self.msg("You have reached the bottom of the dungeon!", C.MSG_GOOD)',
     '            self.msg(t("m.bottom"), C.MSG_GOOD)'),
    ('        self.msg(f"You descend to level {p.depth}.", C.MSG_GOOD)',
     '        self.msg(t("m.descend_to", d=p.depth), C.MSG_GOOD)'),
    ('            self.msg("There are no stairs up here.", C.MSG_HINT)',
     '            self.msg(t("m.no_stairs"), C.MSG_HINT)'),
    ('            self.msg("You refuse to climb back into the sunlight.", C.MSG_HINT)',
     '            self.msg(t("m.no_stairs_up"), C.MSG_HINT)'),
    ('        self.msg(f"You climb to level {p.depth}.", C.MSG_INFO)',
     '        self.msg(t("m.ascend_to", d=p.depth), C.MSG_INFO)'),
    ('            self.msg("The map fades.", C.MSG_INFO)',
     '            self.msg(t("m.map_fade"), C.MSG_INFO)'),
    ('            self.msg(f"You memorize the whole level ({lv.depth} z).", C.MSG_GOOD)',
     '            self.msg(t("m.map_memorize", d=lv.depth), C.MSG_GOOD)'),
    ('            self.msg("The rooms fade into darkness.", C.MSG_INFO)',
     '            self.msg(t("m.lights_off"), C.MSG_INFO)'),
    ('            self.msg("You light every room you can see.", C.MSG_INFO)',
     '            self.msg(t("m.lights_on"), C.MSG_INFO)'),
    ('            self.msg(f"You fall into a trap! {dmg} damage.", C.MSG_BAD)',
     '            self.msg(t("m.trap", d=dmg), C.MSG_BAD)'),
    ('            self.msg("The fountain water heals you.", C.MSG_GOOD)',
     '            self.msg(t("m.fountain"), C.MSG_GOOD)'),
    ('            self.msg("There is no locked door nearby.", C.MSG_HINT)',
     '            self.msg(t("m.no_lock"), C.MSG_HINT)'),
    ('        opts = [f"{lv.describe_tile(x, y)} at ({x},{y})" for x, y in locked]',
     '        opts = [t("m.lock_at", what=lv.describe_tile(x, y), x=x, y=y) for x, y in locked]'),
    ('        self.show_menu("Which lock?", opts, cb, width=34)',
     '        self.show_menu(t("pick.lock"), opts, cb, width=34)'),
    ('            self.msg("You pick the lock.", C.MSG_INFO)',
     '            self.msg(t("m.pick_lock"), C.MSG_INFO)'),

    # --- ход --------------------------------------------------------------
    ('                self.msg("You wake up.", C.MSG_INFO)',
     '                self.msg(t("m.wake"), C.MSG_INFO)'),
    ('            self.msg("You are starving!", C.MSG_BAD)',
     '            self.msg(t("m.starving"), C.MSG_BAD)'),
    ('        self.msg("You die...", C.MSG_BAD)',
     '        self.msg(t("m.die"), C.MSG_BAD)'),

    # --- сохранение -------------------------------------------------------
    ('            self.msg("Game saved.", C.MSG_GOOD)',
     '            self.msg(t("m.saved"), C.MSG_GOOD)'),
    ('        self.msg("Could not save the game.", C.MSG_BAD)\n        return False\n\n    def save_and_quit',
     '        self.msg(t("m.save_err"), C.MSG_BAD)\n        return False\n\n    def save_and_quit'),
    ('            self.msg("Game saved. Goodbye.", C.MSG_GOOD)',
     '            self.msg(t("m.save_quit"), C.MSG_GOOD)'),
    ('        self.msg("Could not save the game.", C.MSG_BAD)\n        return False',
     '        self.msg(t("m.save_err"), C.MSG_BAD)\n        return False'),
    ('            self.msg("Cancelled.", C.MSG_HINT)',
     '            self.msg(t("m.cancelled"), C.MSG_HINT)'),
]


def main():
    src = io.open(PATH, encoding="utf-8").read()
    missing = []
    for old, new in REPL:
        if old not in src:
            missing.append(old.splitlines()[0][:70])
            continue
        src = src.replace(old, new, 1)
    io.open(PATH, "w", encoding="utf-8").write(src)
    if missing:
        print("НЕ НАЙДЕНО:")
        for m in missing:
            print("  -", m)
        return 1
    print("app.py: замен выполнено", len(REPL))
    return 0


if __name__ == "__main__":
    sys.exit(main())
