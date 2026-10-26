"""Сохранение и загрузка состояния игры в JSON."""

from __future__ import annotations

import json
import os

from engine import config as C
from .level import Level
from .world import World


def has_save(path: str = C.SAVE_PATH) -> bool:
    return os.path.isfile(path)


def save_game(path: str, game) -> bool:
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        data = {
            "version": 4,
            "rng": game.rng.state(),
            "player": game.player.to_dict(),
            "level": game.level.serialize(),
            "world": game.world.serialize() if getattr(game, "world", None) is not None else None,
            "other_worlds": {str(n):world.serialize() for n,world in getattr(game,'worlds',{}).items()
                             if world is not game.world},
        }
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp, path)
        return True
    except Exception as exc:  # noqa: BLE001
        print("[save] error:", exc)
        return False


def load_game(path: str, game) -> bool:
    """Восстанавливает состояние в объект Game."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:  # noqa: BLE001
        print("[load] cannot open save:", exc)
        return False

    try:
        from .entities import Player

        game.rng.load_state(data["rng"])
        p = Player()
        p.load_dict(data["player"])
        game.player = p
        old_world = getattr(game, "world", None)
        old_worlds = getattr(game,'worlds',{})
        game.worlds = {}
        if data.get("world"):
            game.world = World.deserialize(data["world"])
            game.worlds = {int(n):World.deserialize(value) for n,value in data.get('other_worlds',{}).items()}
            game.worlds[game.world.b_level] = game.world
            game.level = game.world.chunk(p.chunk_x, p.chunk_y, p.world_z, visit=True)
        else:
            game.world = None
            game.level = Level.deserialize(data["level"], game.rng)
            p.b_level = p.depth
        if old_world is not None:
            old_world.storage.cleanup()
        for world in old_worlds.values():
            if world is not old_world:
                world.storage.cleanup()
        game.level.set_player_pos(p.x, p.y)
        game.level.recompute_fov(p.x, p.y)
        game.update_lighting()
        game.views.free_camera = False
        from .workshop import Workshop
        game.workshop=Workshop(game)
        game._visible_world_key = None
        game.visible_world = {}
        game.tooltip = None
        game.floats.clear()
        game.mode = "play"
        game.log.clear()
        game.msg(f"You return to level {p.depth}.", C.MSG_INFO)
        return True
    except Exception as exc:  # noqa: BLE001
        print("[load] corrupt save:", exc)
        return False


def describe_save(path: str = C.SAVE_PATH) -> str:
    if not has_save(path):
        return "no save"
    try:
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
        p = d["player"]
        return f"depth {p['depth']}, lvl {p['lvl']}, {p['gold']} gold"
    except Exception:  # noqa: BLE001
        return "corrupt save"
