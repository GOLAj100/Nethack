"""Таблица глифов: символы тайлов, существ и предметов.

Смешанный стиль: буквы/цифры для существ, блочные символы и линии
для стен, пола и рамок.
"""

from __future__ import annotations

from . import config as C

# --- Тайлы --------------------------------------------------------------
T_FLOOR = "."
T_FLOOR_ALT = ","
T_CORRIDOR = "-"
T_CORRIDOR_ALT = "_"
T_WALL = "█"
T_WALL_LIGHT = "▓"
T_WALL_DARK = "▒"
T_HEDGE = "♣"
T_DOOR = "+"
T_DOOR_OPEN = "-"
T_STAIR_DOWN = ">"
T_STAIR_UP = "<"
T_ALTAR = "⌂"
T_FOUNTAIN = "≈"
T_TRAP_DOOR = "⌷"
T_BONES = "%"
T_RUBBLE = ":"
T_GRASS = "\""
T_WATER = "~"
T_MAGIC = "░"
T_VOID = " "

# --- Рамки (линейная графика) ------------------------------------------
BOX_TL = "┌"
BOX_TR = "┐"
BOX_BL = "└"
BOX_BR = "┘"
BOX_H = "─"
BOX_V = "│"
BOX_LT = "├"
BOX_RT = "┤"
BOX_TT = "┬"
BOX_BT = "┴"
BOX_X = "┼"
BOX_DOT = "·"
BOX_ARROW_R = "►"
BOX_ARROW_L = "◄"

BAR_FULL = "█"
BAR_EMPTY = "░"

# --- Стили стен по типу уровня ------------------------------------------
WALL_STYLES = {
    0: {"main": T_WALL, "dark": T_WALL_DARK, "color": C.C_WALL},
    1: {"main": T_WALL, "dark": T_WALL_LIGHT, "color": (104, 78, 62)},
    2: {"main": T_WALL, "dark": T_WALL_DARK, "color": (74, 96, 128)},
    3: {"main": T_WALL, "dark": T_WALL_DARK, "color": (52, 78, 56)},
    4: {"main": T_WALL, "dark": T_WALL_DARK, "color": (120, 64, 92)},
}


def wall_glyph(variant: int, style: int = 0) -> str:
    """Чередование глифов стен даёт ощущение объёма/фактуры."""
    if variant % 17 == 0:
        return WALL_STYLES[style]["dark"]
    if variant % 7 == 0:
        return WALL_STYLES[style]["main"]
    return WALL_STYLES[style]["main"]
