"""Каталог запланированных B-Level 21--100.

Уровни из этого диапазона описаны диапазоном в ``levels/catalog.json``.
Каталог держит утверждённую последовательность из ``docs/LEVELS_21_100_PLAN.md`` и
даёт игре безопасный процедурный профиль до появления уникальной геометрии.
Тематические поля намеренно являются данными: генератор можно заменить для
одного уровня, не меняя код потокового мира.
"""

from __future__ import annotations


# Игровой номер -> источник/редакция из утверждённого плана.
SOURCES = {
    21: "Fandom Level 21", 22: "Fandom Level 26", 23: "Fandom Level 27",
    24: "Fandom Level 28", 25: "Fandom Level 25", 26: "Fandom Level 33",
    27: "Fandom Level 30", 28: "Fandom Level 37", 29: "Fandom Level 34",
    30: "Fandom Level 39", 31: "Fandom Level 41", 32: "Author variation of Fandom Level 41",
    33: "Fandom Level 29", 34: "Fandom Level 43", 35: "Fandom Level 44",
    36: "Fandom Level 52", 37: "Fandom Level 55", 38: "Fandom Level 58",
    39: "Fandom Level 59", 40: "Fandom Level 38", 41: "Fandom Level 45",
    42: "Fandom Level 40", 43: "Fandom Level 49", 44: "Fandom Level 57",
    45: "Fandom Level 61 (working choice)", 46: "Fandom Level 74",
    47: "Fandom Level 70", 48: "Fandom Level 72", 49: "Fandom Level 63",
    50: "Fandom Level 66", 51: "Fandom Level 65", 52: "Fandom Level 67",
    53: "Fandom Level 75", 54: "Fandom Level 77", 55: "Fandom Level 76",
    56: "Fandom Level 81", 57: "Fandom Level 83", 58: "Fandom Level 84",
    59: "Fandom Level 78", 60: "Fandom Level 90", 61: "Fandom Level 91",
    62: "Fandom Level 92", 63: "Fandom Level 94", 64: "Fandom Level 95",
    65: "Fandom Level 96", 66: "Fandom Level 97", 67: "Fandom Level 98",
    68: "Fandom Level 80", 69: "Fandom Level 69", 70: "Fandom Level 68",
    71: "Fandom Level 23", 72: "Fandom Level 73", 73: "Fandom Level 54",
    74: "Fandom Level 51", 75: "Fandom Level 47", 76: "Fandom Level 36",
    77: "Fandom Level 32", 78: "Fandom Level 31", 79: "Fandom Level 20",
    80: "Fandom Level 35", 81: "Fandom Level 50", 82: "Fandom Level 46",
    83: "Fandom Level 48", 84: "Fandom Level 79", 85: "Fandom Level 82",
    86: "Fandom Level 85", 87: "Fandom Level 88", 88: "Fandom Level 86",
    89: "original Fandom Level 89", 90: "Fandom Level 99", 91: "Russian Fandom Level 23",
    92: "Russian Fandom Level 26", 93: "Russian Fandom Level 32",
    94: "Russian Fandom Level 41", 95: "Russian Fandom Level 71",
    96: "Russian Fandom Level 72", 97: "Russian Fandom Level 75",
    98: "Russian Fandom Level 77", 99: "Russian Fandom Level 85",
    100: "original Fandom Level 100",
}


def _generator(level: int) -> str:
    """Choose a stable fallback geometry matching the broad level theme."""
    if level in (21, 25, 30, 39, 45, 61, 68, 79, 89, 100):
        return "city"
    if level in (22, 26, 31, 34, 36, 40, 42, 50, 52, 56, 60, 70, 74, 77, 80, 81, 86, 88):
        return "pipes"
    if level in (23, 27, 29, 33, 35, 41, 43, 44, 51, 53, 55, 57, 59, 62, 63, 64, 65, 66, 67, 69, 73, 75, 76, 78, 82, 83, 84, 85, 87, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99):
        return "office"
    return "tundra"


def profile(level: int) -> dict | None:
    """Return a generated profile, or ``None`` for levels with JSON files."""
    source = SOURCES.get(level)
    if source is None:
        return None
    generator = _generator(level)
    return {
        "id": level,
        "name": f"B-Level {level}",
        "source": source,
        "generator": generator,
        "chunk_size": [80, 50],
        "z_min": 0,
        "z_max": 0,
        "exits": level < 100,
        "next_level": level + 1 if level < 100 else None,
        "exit_label": "br.exit.generic",
        "supplies": True,
        "supply_chance": 0.30,
        "furniture": generator == "office",
        "fog_radius": 9,
        "stress_interval": 25,
        "wall_color": [92, 96, 101],
        "floor_color": [78, 80, 76],
        "ceiling_color": [28, 30, 34],
    }


def is_catalog_level(level: int) -> bool:
    return level in SOURCES
