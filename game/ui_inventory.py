"""Инвентарь и действия с предметами: выбор, экипировка, применение."""
from __future__ import annotations

import random

import pygame

from engine import config as C
from engine.widgets import InventoryPanel, Menu
from . import ai
from . import combat
from . import effects
from . import mapgen as MG
from . import monsters as MON
from .items import ITEMS, Item
from .lang import item_name, t


def _item_labels(game, items):
        labels = []
        for it in items:
            mark = ""
            if it.equipped:
                mark = f" [{it.equipped}]"
            labels.append(f"{it.label()}{mark}")
        return labels


def open_inventory(game):
        p = game.player
        if not p.items:
            game.msg(t("m.not_carrying"), C.MSG_HINT)
            return False

        # The modern panel is the primary inventory.  The legacy list remains
        # available through the ASCII/debug presentation while the new panel
        # is being expanded with equipment slots and drag-and-drop.
        game.inventory_panel = InventoryPanel(game.r, p.items, t)
        game.mode = 'inventory'
        game._held_move = None
        game.tooltip = None
        if hasattr(game.views, 'invalidate'):
            game.views.invalidate()
        return True


def handle_inventory_result(game, result):
        if result == 'close':
            game.inventory_panel = None
            game.mode = 'play'
            if hasattr(game.views, 'invalidate'):
                game.views.invalidate()
        elif isinstance(result, tuple) and result[0] == 'actions':
            game.inventory_panel = None
            game.mode = 'play'
            game.show_item_actions(result[1])
        elif isinstance(result, tuple) and result[0] == 'action':
            item, method = result[1], result[2]
            game.inventory_panel = None
            game.mode = 'play'
            if method == 'show_item_info':
                game.show_item_info(item)
            else:
                getattr(game, method)(item)
        return


def show_item_actions(game, item):
        entries = [t(key) for key, _ in game.ITEM_ACTIONS]

        def cb(idx):
            if idx is None:
                return
            _, method = game.ITEM_ACTIONS[idx]
            if method == "show_item_info":
                game.show_item_info(item)
            elif method in ("open_fire", "open_zap", "open_throw"):
                getattr(game, method)(pre=item)
            else:
                getattr(game, method)(item)

        game.show_menu(item.display_name(), entries, cb, width=34)


def show_item_info(game, item):
        spec = ITEMS[item.name]
        lines = []
        if item.kind == "weapon":
            lines.append((t("item.damage", n=spec["dmg"][0], s=spec["dmg"][1]), C.WHITE))
            lines.append((t("item.to_hit", n=spec.get("hit", 0)), C.WHITE))
            if spec.get("ranged"):
                lines.append((t("item.range", n=spec["ranged"]), C.WHITE))
        elif item.kind == "armor":
            lines.append((t("item.ac", n=spec["ac"]), C.WHITE))
        elif item.kind == "ring":
            lines.append((t("item.bonus"), C.WHITE))
        elif item.kind == "wand":
            lines.append((t("item.charges", a=item.charges, b=item.charges_max), C.WHITE))
        elif item.kind == "food":
            lines.append((t("item.nutrition", n=spec.get("saturation", 0)), C.WHITE))
            tags = ', '.join(t('food.' + tag) for tag in spec.get('food_tags', ()))
            lines.append((t('item.food_tags', tags=tags), C.WHITE))
        elif item.kind == 'potion' and spec.get('saturation'):
            lines.append((t('item.nutrition', n=spec['saturation']), C.WHITE))
            if spec.get('hydrating'):
                lines.append((t('item.hydrating'), C.CYAN))
        lines.append((t("item.value", v=item.value), C.YELLOW))
        if item.blessed:
            lines.append((t("item.blessed"), C.CYAN))
        if item.cursed:
            lines.append((t("item.cursed"), C.RED))
        game.show_text(t("item.info"), lines)
        game.end_turn()


def open_drop(game):
        game._pick_carried(t("pick.drop"), game.do_drop)
        return True


def open_eat(game):
        game._pick_carried(t("pick.eat"), game.do_eat, kinds={"food"})
        return True


def open_quaff(game):
        game._pick_carried(t("pick.quaff"), game.do_quaff, kinds={"potion"})
        return True


def open_read(game):
        game._pick_carried(t("pick.read"), game.do_read, kinds={"scroll"})
        return True


def open_wield(game):
        game._pick_carried(t("pick.wield"), game.do_wield, kinds={"weapon"})
        return True


def open_wear(game):
        game._pick_carried(t("pick.wear"), game.do_wear, kinds={"armor", "ring"})
        return True


def open_takeoff(game):
        worn = [it for it in game.player.items if it.equipped]
        if not worn:
            game.msg(t("m.not_wearing"), C.MSG_HINT)
            return False
        game._pick_from(worn, t("pick.takeoff"), game.do_takeoff)
        return True


def _pick_carried(game, title, fn, kinds=None):
        items = game.player.items
        if kinds:
            items = [it for it in items if it.kind in kinds]
        if not items:
            game.msg(t("need.suitable"), C.MSG_HINT)
            return False
        game._pick_from(items, title, fn)
        return True


def _pick_from(game, items, title, fn):
        def cb(idx):
            if idx is None:
                return
            fn(items[idx])

        game.show_menu(title, game._item_labels(items), cb, width=48)


def pickup_item(game, item):
        """Взять конкретный предмет с пола."""
        p, lv = game.player, game.level
        if (p.x, p.y) not in lv.items or lv.items.get((p.x, p.y)) is not item:
            game.msg(t("m.nothing_here"), C.MSG_HINT)
            return False
        lv.items.pop((p.x, p.y), None)
        if item.kind == "gold":
            p.gold += item.qty
            game.msg(t("m.pickup_gold", n=item.qty), C.MSG_GOOD)
        else:
            p.items.append(item)
            game.msg(t("m.pickup", it=item.label()), C.MSG_GOOD)
        game.audio.play("pickup")
        return True


def open_pick_items(game):
        lv = game.level
        here = [it for (x, y), it in lv.items.items() if (x, y) == (game.player.x, game.player.y)]
        if not here:
            game.msg(t("m.nothing_here"), C.MSG_HINT)
            return False

        def cb(idx):
            if idx is None:
                return
            game.show_item_actions(here[idx])

        game.show_menu(t("ui.items_here"), game._item_labels(here), cb, width=48)
        game.menu.quick = dict(game.FLOOR_QUICK)
        game.menu_items = list(here)
        return True


def _carried(game, item) -> bool:
        """Предмет должен лежать в инвентаре - иначе действие недопустимо."""
        if item in game.player.items:
            return True
        game.msg(t("need.pickup"), C.MSG_WARN)
        game.audio.play("error", 0.4)
        return False


def do_drop(game, item):
        if not game._carried(item):
            return
        old_equipped = item.equipped
        item.equipped = None
        spot = game.level.drop_item(item, game.player.x, game.player.y)
        if spot is not None:
            game.player.items.remove(item)
            game.msg(t("m.drop_it", it=item.label()), C.MSG_INFO)
        else:
            item.equipped = old_equipped
            game.msg(t("m.no_room_drop"), C.MSG_BAD)
        game.audio.play("select", 0.4)
        game.end_turn()


def do_eat(game, item):
        p = game.player
        if not game._carried(item):
            return
        if item.kind != "food":
            game.msg(t("m.cannot_eat", it=item.display_name()), C.MSG_BAD)
            return
        result = p.nourish(item.spec)
        game.msg(t("m.eat_it", it=item.display_name()), C.MSG_INFO)
        game.report_nourishment(result)
        item.count-=1
        if item.count<=0: p.items.remove(item)
        game.audio.play("eat")
        game.end_turn()


def do_quaff(game, item):
        p, lv = game.player, game.level
        if not game._carried(item):
            return
        if item.kind != "potion":
            game.msg(t("m.cannot_quaff", it=item.display_name()), C.MSG_BAD)
            return
        if item.spec.get("pending_effect"):
            game.msg(t("m.liquid_pending"), C.MSG_HINT)
            return
        if item.cursed:
            game.msg(t("m.feel_worse"), C.MSG_WARN)
            p.take_damage(random.randint(2, 6), None, cause="unstable liquid")
        item.count-=1
        if item.count<=0: p.items.remove(item)
        text, color = effects.apply(p, lv, item)
        item.identified = True
        game.msg(text, color)
        game.report_nourishment(p.nourish(item.spec))
        game.audio.play("drink")
        lv.recompute_fov(p.x, p.y)
        game.end_turn()


def do_read(game, item):
        p, lv = game.player, game.level
        if not game._carried(item):
            return
        if item.kind != "scroll":
            game.msg(t("m.cannot_read", it=item.display_name()), C.MSG_BAD)
            return
        if item.name == 'noclip guide':
            p.knowledge = sorted(set(getattr(p,'knowledge',[])) | {'noclip'})
            item.identified = True
            game.msg(t('br.learn_noclip'),C.MSG_GOOD)
            game.audio.play('read')
            game.end_turn()
            return
        if item.name == "scroll of identify":
            p.items.remove(item)

            def cb(idx):
                if idx is None:
                    game.msg(t("m.put_away"), C.MSG_HINT)
                    return
                game.identify(idx)
                game.end_turn()

            game.show_menu(t("pick.identify"), game._item_labels(p.items), cb, width=48)
            game.audio.play("read")
            return
        p.items.remove(item)
        text, color = effects.apply(p, lv, item)
        item.identified = True
        game.msg(text, color)
        game.audio.play("magic", 0.7)
        lv.recompute_fov(p.x, p.y)
        game.end_turn()


def identify(game, idx):
        it = game.player.items[idx]
        it.identified = True
        game.msg(t("m.know", it=it.display_name()), C.MSG_GOOD)
        game.audio.play("magic", 0.6)


def do_wield(game, item):
        p = game.player
        if not game._carried(item):
            return
        if item.slot != "weapon":
            game.msg(t("m.cannot_wield", it=item.display_name()), C.MSG_BAD)
            return
        p.unequip_slot("weapon", keep=item)
        item.equipped = "weapon"
        game.msg(t("m.wield", it=item.display_name()), C.MSG_INFO)
        game.audio.play("wield")
        game.end_turn()


def do_wear(game, item):
        p = game.player
        if not game._carried(item):
            return
        if not item.slot:
            game.msg(t("m.cannot_wear", it=item.display_name()), C.MSG_BAD)
            return
        removed = p.equip(item)
        if removed and item.cursed:
            game.msg(t("m.cold"), C.MSG_WARN)
            p.take_damage(random.randint(1, 5), None, cause="curse")
        game.msg(t("m.wear", it=item.display_name()), C.MSG_INFO)
        if removed:
            game.msg(t("m.took_off", its=", ".join(r.display_name() for r in removed)),
                     C.MSG_HINT)
        game.audio.play("armor")
        game.end_turn()


def do_takeoff(game, item):
        if not game._carried(item):
            return
        game.player.items.remove(item)
        item.equipped = None
        game.msg(t("m.takeoff", it=item.display_name()), C.MSG_INFO)
        game.audio.play("select", 0.4)
        game.end_turn()


def open_fire(game, pre=None):
        p = game.player
        if pre is None:
            ammo = [it for it in p.items if it.kind == "missile"]
            if not ammo:
                game.msg(t("m.no_ammo"), C.MSG_HINT)
                return False
            game._pick_from(ammo, t("act.fire"), game._do_fire_pick)
            return True
        game.start_target("fire")
        game.pending_item = pre
        return True


def _do_fire_pick(game, item):
        game.pending_item = item
        game.start_target("fire")


def _do_fire(game, x, y):
        item = getattr(game, "pending_item", None)
        p = game.player
        if item is None or item not in p.items:
            game.msg(t("m.no_ammo"), C.MSG_HINT)
            return
        if not game.player_has_bow():
            game.msg(t("m.no_bow"), C.MSG_BAD)
            return
        w = p.wielded
        p.items.remove(item)
        monster = game.level.monster_at(x, y)
        text, color = combat.ranged_attack(p, monster, game, 1.0)
        game.msg(text, color)
        if monster is not None and not monster.alive:
            game.on_kill(monster)
        game.audio.play("ammo")
        game.end_turn()


def player_has_bow(game):
        w = game.player.wielded
        return w is not None and bool(ITEMS[w.name].get("ranged"))


def open_throw(game, pre=None):
        if pre is not None:
            game.pending_item = pre
            game.start_target("throw")
            return True
        items = [it for it in game.player.items]
        if not items:
            game.msg(t("m.no_throw"), C.MSG_HINT)
            return False
        game._pick_from(items, t("act.throw"), game._do_throw_pick)
        return True


def _do_throw_pick(game, item):
        game.pending_item = item
        game.start_target("throw")


def _do_throw(game, x, y):
        item = getattr(game, "pending_item", None)
        p = game.player
        if item is None or item not in p.items:
            return
        p.items.remove(item)
        dist = F.distance(p.x, p.y, x, y)
        monster = game.level.monster_at(x, y)
        text, color = combat.ranged_attack(p, monster, game, max(0.4, 1.4 - dist * 0.1))
        game.msg(text, color)
        if monster is not None and not monster.alive:
            game.on_kill(monster)
        elif monster is None:
            spot = game.level.random_open_tile()
            if spot:
                game.level.items[spot] = item
        game.audio.play("ammo", 0.7)
        game.end_turn()


def open_zap(game, pre=None):
        if pre is not None:
            game.pending_item = pre
            game.start_target("zap")
            return True
        wands = [it for it in game.player.items if it.kind == "wand"]
        if not wands:
            game.msg(t("m.no_wands"), C.MSG_HINT)
            return False
        game._pick_from(wands, t("act.zap"), game._do_zap_pick)
        return True


def _do_zap_pick(game, item):
        if item.charges <= 0:
            game.msg(t("m.wand_spent"), C.MSG_WARN)
            return
        game.pending_item = item
        game.start_target("zap")


def _do_zap(game, x, y):
        item = getattr(game, "pending_item", None)
        p, lv = game.player, game.level
        if item is None or item not in p.items:
            return
        if item.charges <= 0:
            game.msg(t("m.wand_spent"), C.MSG_WARN)
            return
        item.charges -= 1
        text, color = effects.apply(p, lv, item, target=(x, y))
        item.identified = True
        game.msg(text, color)
        game.audio.play("zap", 0.8)
        lv.recompute_fov(p.x, p.y)
        game.end_turn()
