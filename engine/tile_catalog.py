"""Human-readable list of every gameplay symbol understood by the renderer."""
from . import glyphs as G

SYMBOLS = {
    "@": "Игрок",
    "E": "EXIT — переход на другой B-Level (не лестница Z)",
    "#": "Стена (█ ▓ ▒)", "█": "Стена", "▓": "Стена светлая", "▒": "Стена тёмная",
    ".": "Пол", ",": "Пол (вариант)", "-": "Коридор / открытая дверь", "_": "Коридор",
    "♣": "Живая изгородь", "+": "Закрытая дверь", ">": "Лестница вниз", "<": "Лестница вверх",
    "⌂": "Алтарь", "≈": "Фонтан", "⌷": "Люк-ловушка", "%": "Еда / кости / труп",
    ":": "Обломки", '"': "Трава", "~": "Вода", "░": "Магия", " ": "Пустота",
    ")": "Оружие", "[": "Броня", "}": "Стрела / болт", "!": "Бутылка с жидкостью", "?": "Документ",
    "/": "Артефакт", "=": "Кольцо", "$": "Золото", "(": "Инструмент", "*": "Потолочная лампа", "►": "Маркер карты",
}


def entries():
    from game.monsters import MONSTERS
    from game.lang import monster_name
    symbols = dict(SYMBOLS)
    for name, spec in MONSTERS.items():
        symbols[spec["glyph"]] = monster_name(name)
    return [(char, name) for char, name in symbols.items() if char != " "]
