"""Управление: переназначение клавиш и описание раскладок.

Связка хранится строкой вида "w", "shift+d", "left", "[5]", "f2".
"""

from __future__ import annotations

import pygame

# имена клавиш, которые pygame не умеет разбирать обратно
ALIASES = {
    "[1]": pygame.K_KP1, "[2]": pygame.K_KP2, "[3]": pygame.K_KP3,
    "[4]": pygame.K_KP4, "[5]": pygame.K_KP5, "[6]": pygame.K_KP6,
    "[7]": pygame.K_KP7, "[8]": pygame.K_KP8, "[9]": pygame.K_KP9,
    "[0]": pygame.K_KP0, "[.]": pygame.K_KP_PERIOD, "[+]": pygame.K_KP_PLUS,
    "kp enter": pygame.K_KP_ENTER, "numpad enter": pygame.K_KP_ENTER,
}

LABELS = {
    "left": "←", "right": "→", "up": "↑", "down": "↓",
    "return": "Enter", "escape": "Esc", "space": "Space",
    "backspace": "Bksp", "tab": "Tab", "shift": "Shift",
    "left shift": "LShift", "right shift": "RShift",
    "left ctrl": "LCtrl", "right ctrl": "RCtrl", "left alt": "LAlt",
    "[1]": "Num1", "[2]": "Num2", "[3]": "Num3", "[4]": "Num4", "[5]": "Num5",
    "[6]": "Num6", "[7]": "Num7", "[8]": "Num8", "[9]": "Num9", "[0]": "Num0",
    "[.]": "Num.", "[+]": "Num+", "kp enter": "NumEnter",
    **{f"f{i}": f"F{i}" for i in range(1, 25)},
}

# --------------------------------------------------------------------------
# Описание действий: группа -> список (действие, клавиши по умолчанию)
# --------------------------------------------------------------------------
ACTION_GROUPS: list[tuple[str, list[tuple[str, list[str]]]]] = [
    ("ctl.g.move", [
        ("move_north",  ["w", "k", "up", "[8]"]),
        ("move_south",  ["s", "j", "down", "[2]"]),
        ("move_west",   ["a", "h", "left", "[4]"]),
        ("move_east",   ["d", "l", "right", "[6]"]),
        ("move_nw",     ["y", "[7]"]),
        ("move_ne",     ["u", "[9]"]),
        ("move_sw",     ["b", "[1]"]),
        ("move_se",     ["n", "[3]"]),
        ("wait",        [".", "space", "[5]"]),
        ("rest",        ["shift+b"]),
        ("sleep",       ["shift+r"]),
    ]),
    ("ctl.g.stairs", [
        ("descend",     [">"]),
        ("ascend",      ["<"]),
    ]),
    ("ctl.g.items", [
        ("action_menu", ["tab"]),
        ("workshop", ["f9"]),
        ("interact", ["return"]),
        ("pickup",      ["g"]),
        ("pickup_all",  [","]),
        ("items_here",  ["p"]),
        ("inventory",   ["i"]),
        ("drop",        ["shift+d"]),
        ("eat",         ["e"]),
        ("quaff",       ["q"]),
        ("read",        ["r"]),
        ("wield",       ["x"]),
        ("swap_weapon", ["shift+x"]),
        ("wear",        ["shift+w"]),
        ("takeoff",     ["shift+t"]),
    ]),
    ("ctl.g.combat", [
        ("force_fight", ["shift+f"]),
        ("fire",        ["f"]),
        ("zap",         ["z"]),
        ("throw",       ["t"]),
        ("pick_lock",   ["shift+p"]),
    ]),
    ("ctl.g.world", [
        ("toggle_status", ["f10"]),
        ("passages", ["f1"]),
        ("map_toggle",  ["m", "o"]),
        ("lights",      ["shift+l"]),
        ("rotate_left", ["["]),
        ("rotate_right", ["]"]),
        ("char_sheet",  ["c"]),
        ("help",        ["/"]),
    ]),
    ("ctl.g.system", [
        ("save",        ["shift+s"]),
        ("save_quit",   ["shift+q"]),
        ("settings",    ["f2"]),
        ("lang_toggle", ["f3"]),
        ("sound_toggle", ["f4"]),
    ]),
]

ACTIONS: dict[str, list[str]] = {}
GROUPS: dict[str, list[str]] = {}
for _g, _items in ACTION_GROUPS:
    GROUPS[_g] = [a for a, _ in _items]
    for _a, _keys in _items:
        ACTIONS[_a] = list(_keys)

# клавиши, которые нельзя переназначить (защита от «залипания» в интерфейсе)
LOCKED = {"escape", "f1", "f11"}

# Actions without a shortcut remain available through inventory/action menus.
NEWCOMER = {action: [] for action in ACTIONS}
NEWCOMER.update({
    "move_north": ["w", "up", "[8]"], "move_south": ["s", "down", "[2]"],
    "move_west": ["a", "left", "[4]"], "move_east": ["d", "right", "[6]"],
    "move_nw": ["[7]"], "move_ne": ["[9]"], "move_sw": ["[1]"], "move_se": ["[3]"],
    "wait": ["space", "[5]"], "interact": ["e", "return"],
    "action_menu": ["tab"], "inventory": ["i"], "rest": ["r"], "sleep": ["shift+r"],
    "workshop": ["f9"],
    "passages": ["f1"],
    "swap_weapon": ["x"], "help": ["/"], "settings": ["f2"],
    "save": ["shift+s"], "save_quit": ["shift+q"],
    "toggle_status": ["f10"], "lang_toggle": ["f3"], "sound_toggle": ["f4"],
})
PRESETS = {"classic": ACTIONS, "newcomer": NEWCOMER}


def code_of(name: str) -> int:
    if name in ALIASES:
        return ALIASES[name]
    return pygame.key.key_code(name)


def name_of(code: int) -> str:
    n = pygame.key.name(code)
    if n in ALIASES.values() or n in ("period", "comma", "slash", "question"):
        for alias, c in ALIASES.items():
            if c == code:
                return alias
    return n


def key_label(code: int) -> str:
    n = name_of(code)
    return LABELS.get(n, n)


def parse(text: str):
    """'shift+d' -> (KMOD_SHIFT, K_d)."""
    mod = 0
    parts = text.lower().replace(" ", "").split("+")
    for p in parts[:-1]:
        if p == "shift":
            mod |= pygame.KMOD_SHIFT
        elif p == "ctrl":
            mod |= pygame.KMOD_CTRL
        elif p == "alt":
            mod |= pygame.KMOD_ALT
    try:
        return mod, code_of(parts[-1])
    except ValueError:
        return 0, 0


def fmt(mod: int, code: int) -> str:
    if not code:
        return "-"
    parts = []
    if mod & pygame.KMOD_SHIFT:
        parts.append("shift")
    if mod & pygame.KMOD_CTRL:
        parts.append("ctrl")
    if mod & pygame.KMOD_ALT:
        parts.append("alt")
    parts.append(name_of(code))
    return "+".join(parts)


def label(mod: int, code: int) -> str:
    if not code:
        return "-"
    out = []
    if mod & pygame.KMOD_SHIFT:
        out.append("Shift")
    if mod & pygame.KMOD_CTRL:
        out.append("Ctrl")
    if mod & pygame.KMOD_ALT:
        out.append("Alt")
    out.append(key_label(code))
    return "+".join(out)


class Controls:
    """Набор раскладок с возможностью переназначения."""

    def __init__(self):
        self.preset = "classic"
        self.profiles = {}
        self.bindings: dict[str, list[tuple[int, int]]] = {}
        self.primary: dict[str, tuple[int, int]] = {}
        self._lookup: dict[tuple[int, int], str] = {}
        self.reset()

    # --- исходное состояние ----------------------------------------------
    def reset(self):
        self.bindings = {}
        for action, keys in PRESETS[self.preset].items():
            parsed = [b for b in (parse_safe(k) for k in keys) if b]
            self.bindings[action] = parsed
        self._resolve()

    def load(self, data: dict):
        self.reset()
        if not isinstance(data, dict):
            return
        for action, keys in data.items():
            if action in self.bindings and isinstance(keys, list):
                parsed = [b for b in (parse_safe(k) for k in keys) if b]
                if parsed or not keys:
                    self.bindings[action] = parsed
        self._resolve()

    def save(self) -> dict:
        return {a: [fmt(m, c) for m, c in ks]
                for a, ks in self.bindings.items()}

    def switch_preset(self, name):
        if name not in PRESETS or name == self.preset:
            return
        self.profiles[self.preset] = self.save()
        self.preset = name
        self.load(self.profiles.get(name, {}))

    def load_profiles(self, data):
        name = data.get("control_preset", "classic")
        self.preset = name if name in PRESETS else "classic"
        profiles = data.get("control_profiles", {})
        self.profiles = {k:v for k,v in profiles.items() if k in PRESETS and isinstance(v,dict)} if isinstance(profiles,dict) else {}
        self.load(data.get("keys", self.profiles.get(self.preset, {})))

    def save_profiles(self):
        self.profiles[self.preset] = self.save()
        return dict(self.profiles)

    # --- разрешение -------------------------------------------------------
    def _resolve(self):
        """Первичная клавиша = первый элемент списка."""
        self.primary: dict[str, tuple[int, int]] = {
            a: ks[0] for a, ks in self.bindings.items() if ks
        }
        self._lookup: dict[tuple[int, int], str] = {}
        for a, ks in self.bindings.items():
            for b in ks:
                self._lookup.setdefault(b, a)

    def action_for(self, code: int, mod: int) -> str | None:
        shift = bool(mod & pygame.KMOD_SHIFT)
        ctrl = bool(mod & pygame.KMOD_CTRL)
        if ctrl:
            return None
        # сначала ищем со всеми модификаторами, потом - без shift
        for m in ((pygame.KMOD_SHIFT if shift else 0), 0):
            action = self._lookup.get((m, code))
            if action:
                return action
        return None

    def key_list(self, action: str, limit: int = 3) -> str:
        keys = self.bindings.get(action, [])
        shown = keys[:limit]
        text = ", ".join(label(m, c) for m, c in shown)
        if len(keys) > limit:
            text += f" +{len(keys) - limit}"
        return text or "-"

    def primary_label(self, action: str) -> str:
        mod, code = self.primary.get(action, (0, 0))
        return label(mod, code)

    # --- переназначение ----------------------------------------------------
    def assign(self, action: str, mod: int, code: int) -> str | None:
        """Назначает новую клавишу. Возвращает действие, если была конфликт."""
        if not code:
            return None
        mod = mod & (pygame.KMOD_SHIFT | pygame.KMOD_ALT)
        if name_of(code) in LOCKED:
            return None
        # убираем клавишу у других действий
        for other, keys in self.bindings.items():
            if other != action:
                self.bindings[other] = [k for k in keys if k != (mod, code)]
        self.bindings[action] = [(mod, code)] + [
            key for key in self.bindings[action] if key != (mod, code)]
        self._resolve()
        return None

    def add_alias(self, action: str, mod: int, code: int):
        """Добавляет второстепенную клавишу, не убирая старую у других."""
        if not code:
            return False
        mod = mod & (pygame.KMOD_SHIFT | pygame.KMOD_ALT)
        if name_of(code) in LOCKED:
            return False
        if (mod, code) not in self.bindings[action]:
            self.bindings[action].append((mod, code))
        self._resolve()
        return True


def code_of_safe(name: str) -> bool:
    return parse_safe(name) is not None


def parse_safe(text: str):
    """'shift+d' -> (KMOD_SHIFT, K_d) или None, если имя неизвестно."""
    try:
        mod, code = parse(text)
        return (mod, code) if code else None
    except (ValueError, KeyError):
        return None


class Actions:
    """Таблица «действие -> вызов метода Game»."""

    def __init__(self):
        self.map = {
            "move_north":  ("move", (0, -1)),
            "move_south":  ("move", (0, 1)),
            "move_west":   ("move", (-1, 0)),
            "move_east":   ("move", (1, 0)),
            "move_nw":     ("move", (-1, -1)),
            "move_ne":     ("move", (1, -1)),
            "move_sw":     ("move", (-1, 1)),
            "move_se":     ("move", (1, 1)),
            "wait":        ("wait", ()),
            "rest":        ("rest", ()),
            "workshop":    ("open_workshop", ()),
            "passages":    ("show_level_passages", ()),
            "sleep":       ("sleep", ()),
            "action_menu": ("open_action_wheel", ()),
            "interact": ("interact", ()),
            "toggle_status": ("toggle_status", ()),
            "view_map": ("show_3d_map", ()),
            "swap_weapon": ("swap_weapon", ()),
            "descend":     ("descend", ()),
            "ascend":      ("ascend", ()),
            "pickup":      ("pickup", ()),
            "pickup_all":  ("pickup_all", ()),
            "items_here":  ("open_pick_items", ()),
            "inventory":   ("open_inventory", ()),
            "drop":        ("open_drop", ()),
            "eat":         ("open_eat", ()),
            "quaff":       ("open_quaff", ()),
            "read":        ("open_read", ()),
            "wield":       ("open_wield", ()),
            "wear":        ("open_wear", ()),
            "takeoff":     ("open_takeoff", ()),
            "force_fight": ("force_attack", ()),
            "fire":        ("open_fire", ()),
            "zap":         ("open_zap", ()),
            "throw":       ("open_throw", ()),
            "pick_lock":   ("pick_lock", ()),
            "map_toggle":  ("toggle_map", ()),
            "lights":      ("toggle_lights", ()),
            "rotate_left": ("rotate_view", (-1,)),
            "rotate_right": ("rotate_view", (1,)),
            "char_sheet":  ("show_char", ()),
            "help":        ("show_help", ()),
            "save":        ("save_quiet", ()),
            "save_quit":   ("save_and_quit", ()),
            "settings":    ("open_settings", ()),
            "lang_toggle": ("toggle_language", ()),
            "sound_toggle": ("toggle_mute_sound", ()),
        }

    def run(self, game, action: str) -> bool:
        entry = self.map.get(action)
        if entry is None:
            return False
        name, args = entry
        fn = getattr(game, name)
        try:
            result = fn(*args)
        except Exception:
            game.msg(f"action {action} failed")
            raise
        if result is False:
            game.audio.play("error", 0.4)
        return True
