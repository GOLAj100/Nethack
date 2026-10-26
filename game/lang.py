"""Локализация: английский и русский, переключение в настройках.

Каждая строка хранится один раз в таблице S как пара (en, ru).
t("key", поле=...) возвращает строку на текущем языке.
"""

from __future__ import annotations

import json
import os

from engine import config as C

LANGS = ("en", "ru")
LANG_NAMES = {"en": "English", "ru": "Русский"}

_current = "en"


def set_lang(code: str):
    global _current
    if code in LANGS:
        _current = code


def get_lang() -> str:
    return _current


def other_lang() -> str:
    return "ru" if _current == "en" else "en"


def t(key: str, **kw) -> str:
    """Перевод по ключу; при отсутствии ключа возвращается сам ключ."""
    entry = S.get(key)
    if entry is None:
        text = key
    else:
        idx = 0 if _current == "en" else 1
        text = entry[idx] if idx < len(entry) and entry[idx] else entry[0]
    if kw:
        try:
            return text.format(**kw)
        except (KeyError, IndexError, ValueError):
            return text
    return text


# ---------------------------------------------------------------------------
# Таблица строк: ключ -> (English, Русский)
# ---------------------------------------------------------------------------
S: dict[str, tuple[str, str]] = {
    "a.action_menu": ("Action wheel", "Круговое меню действий"),
    "a.interact": ("Interact / pick up", "Взаимодействовать / взять"),
    "a.toggle_status": ("Show / hide status panel", "Показать / скрыть состояние"),
    "a.view_map": ("Open 3D map", "Открыть 3D-карту"),
    "wheel.title": ("Actions", "Действия"),
    "wheel.inventory": ("Inventory", "Инвентарь"),
    "wheel.food": ("Food", "Еда"),
    "wheel.drink": ("Drink", "Питьё"),
    "wheel.equipment": ("Equipment", "Снаряжение"),
    "wheel.combat": ("Combat", "Бой"),
    "wheel.world": ("World", "Мир"),
    "wheel.character": ("Character", "Характеристики"),
    "wheel.sleep": ("Rest", "Отдых"),
    "wheel.system": ("System", "Система"),
    "wheel.hint": ("Click / 1-8 choose | arrows + Enter | Tab / Esc close", "Клик / 1–8 выбор | стрелки + Enter | Tab / Esc закрыть"),
    "ui.modern_actions": ("Tab / MMB: actions", "Tab / СКМ: действия"),
    "ui.modern_interact": ("Enter: interact", "Enter: взять / действия"),
    "ui.modern_status": ("F10: hide panel", "F10: скрыть панель"),
    "ui.modern_map": ("F7: 3D map", "F7: 3D-карта"),
    "ui.modern_char": ("C: full character sheet", "C: все характеристики"),
    "ui.modern_hint": ("Tab actions | Enter interact | Shift run | F10 status | F7 map", "Tab действия | Enter взять | Shift бег | F10 состояние | F7 карта"),
    "help.modern": ("Tab / MMB: actions. Enter: pick up. F10: status. Hold two directions for diagonals.", "Tab / СКМ: действия. Enter: взять. F10: состояние. Две клавиши движения — диагональ."),
    # --- меню ------------------------------------------------------------
    "menu.new_game":   ("New game", "Новая игра"),
    "menu.continue":   ("Continue", "Продолжить"),
    "menu.settings":   ("Settings", "Настройки"),
    "menu.quit":       ("Quit", "Выход"),
    "set.title":       ("Settings", "Настройки"),
    "a.passages": ("B-Level passages (F1)", "Переходы B-Level (F1)"),
    "br.passage_at": ("To Level {n}: local cell ({x}, {y})", "На уровень {n}: клетка ({x}, {y}) текущего чанка"),
    "br.passage_z": ("B-Level passages are on Z=0. Return via stairs.", "Переходы B-Level находятся на Z=0. Вернитесь по лестнице."),
    "br.no_passage": ("No B-Level passage in this chunk.", "В этом чанке нет перехода B-Level."),
    "br.passage_help": ("Green E / EXIT marks a B-Level passage. Stand here and press Enter. RMB inspects.", "Зелёная E / EXIT — переход B-Level. Встаньте на клетку и нажмите Enter. ПКМ — осмотр."),
    "debug.performance": ("Performance monitor (F12)", "Монитор производительности (F12)"),
    "debug.overlay": ("Render overlay (F12)", "Оверлей рендера (F12)"),
    "debug.perf_reset": ("Reset performance samples", "Сбросить замеры производительности"),
    "climb.none": ("No reachable ledge above.", "Сверху нет доступного уступа."),
    "climb.ceiling": ("The ceiling blocks your climb.", "Подъём перекрыт потолком."),
    "climb.tired": ("Need at least 5 stamina.", "Нужно хотя бы 5 выносливости."),
    "climb.success": ("You pull yourself onto the ledge.", "Вы подтягиваетесь на уступ."),
    "climb.failed": ("You slip: {n} damage.", "Вы срываетесь: урон {n}."),
    "world.arrive": ("Level 0. Yellow walls, damp carpet, fluorescent lights.", "Level 0. Жёлтые стены, влажный ковролин, люминесцентные лампы."),
    "world.no_exit": ("Find a passage to the next B-Level and interact with it.", "Найдите переход на следующий B-уровень и взаимодействуйте с ним."),
    "br.arrive": ("Level {n}: {name}.", "Уровень {n}: {name}."),
    "br.exit_hint": ("Level {n}; stand here and press Enter", "Уровень {n}; встаньте сюда и нажмите Enter"),
    "br.need_knowledge": ("You must learn this technique from a document first.", "Сначала изучите эту технику по документу."),
    "br.blocked": ("The arrival area is blocked.", "Место прибытия заблокировано."),
    "br.noclip": ("Unstable seam in space", "Нестабильный шов пространства"),
    "br.learn_noclip": ("You learn noclip: stand on an unstable spatial seam and press Enter. Ordinary walls do not work. This guide can be read again.", "Вы изучили ноуклип: встаньте на нестабильный шов пространства и нажмите Enter. Обычные стены не подходят. Документ можно перечитать."),
    "br.stress": ("The surroundings wear down your sanity.", "Окружение подтачивает ваш рассудок."),
    "br.heat": ("The heat drains your stamina.", "Жара отнимает выносливость."),
    "br.hazard.steam": ("Scalding steam from a damaged pipe.", "Обжигающий пар из повреждённой трубы."),
    "br.hazard.wire": ("Exposed live wiring.", "Оголённые провода под напряжением."),
    "br.hazard.sewage": ("Contaminated runoff burns your skin.", "Загрязнённая вода обжигает кожу."),
    "br.hazard.toxic": ("A toxic hospital residue seeps through the floor.", "Через пол просачиваются токсичные больничные выделения."),
    "br.hazard.static": ("The room crackles with a painful static charge.", "Комната потрескивает болезненным статическим зарядом."),
    "br.hazard.electric_water": ("A current runs through the flooded deck.", "По затопленной палубе проходит ток."),
    "br.hazard.deep_water": ("The sea drops away beneath you.", "Под вами резко уходит глубина моря."),
    "br.hazard.cave_cold": ("The underground lake leeches warmth from you.", "Подземное озеро вытягивает из вас тепло."),
    "br.current": ("The current pulls you east.", "Течение тянет вас на восток."),
    "br.black_grass": ("The black grass twists your sense of direction.", "Чёрная трава искажает чувство направления."),
    "br.silence": ("The street falls unnaturally silent.", "Улица погружается в неестественную тишину."),
    "m.observer_watch": ("You feel the Observer watching you.", "Вы чувствуете взгляд Наблюдателя."),
    "m.swim": ("The cold water closes over your legs. You swim forward.", "Холодная вода смыкается над ногами. Вы плывёте вперёд."),
    "t.water": ("cold open water", "холодная открытая вода"),
    "br.cold_water": ("The freezing sea drains your strength.", "Ледяное море отнимает силы."),
    "br.exit.generic": ("A route leads to the next B-Level.", "Путь ведёт на следующий B-уровень."),
    "br.exit.0": ("Stairway out of the yellow rooms", "Лестница из жёлтых комнат"),
    "br.exit.1": ("Maintenance passage", "Проход в технические коридоры"),
    "br.exit.2": ("Passage to the electrical station", "Проход к электростанции"),
    "br.exit.3": ("Office sector elevator", "Лифт в офисный сектор"),
    "br.exit.4": ("Ornate doorway; distant classical music", "Украшенный дверной проём; вдали классическая музыка"),
    "br.exit.5": ("Dark boiler passage", "Тёмный проход за котлами"),
    "br.name.0": ("The Lobby", "Вестибюль"),
    "br.name.1": ("Parking Zone", "Парковочная зона"),
    "br.name.2": ("Pipe Dreams", "Трубные грёзы"),
    "br.name.3": ("Electrical Station", "Электростанция"),
    "br.name.4": ("The Abandoned Office", "Заброшенный офис"),
    "br.name.5": ("Terror Hotel", "Отель ужаса"),
    "br.name.6": ("Lights Out", "Свет погас"),
    "br.info.0": ("Explore the yellow rooms to find the stairway onward.", "Исследуйте жёлтые комнаты в поисках лестницы дальше."),
    "br.info.1": ("Concrete columns, fog and supply crates. Beware of blackouts.", "Бетонные колонны, туман и ящики припасов. Возможны отключения света."),
    "br.info.2": ("Hot utility tunnels. Avoid steam marked with ^.", "Жаркие технические туннели. Обходите пар, отмеченный ^."),
    "br.info.3": ("Electrical rooms. Avoid live wiring marked with ^.", "Электротехнические помещения. Обходите провода, отмеченные ^."),
    "br.info.4": ("Quiet offices offer supplies and a place to rest.", "Тихие офисы дают припасы и место для отдыха."),
    "br.info.5": ("The hotel erodes your sanity. Seek a passage through the boilers.", "Отель разрушает рассудок. Ищите проход через котельную."),
    "br.info.6": ("Light fails here. F5: tactile map. The metal hatch opens onto Level 7.", "Свет здесь не работает. F5: карта на ощупь. Металлический люк ведёт на уровень 7."),
    "br.name.7": ("Thalassophobia", "Талассофобия"),
    "br.name.8": ("Cave System", "Пещерная система"),
    "br.name.9": ("Darkened Suburbs", "Тёмные пригороды"),
    "br.name.10": ("The Bumper Crop", "Бесконечные поля"),
    "br.info.7": ("A cold ocean surrounds a rusted bunker. Swimming drains stamina and prolonged exposure causes hypothermia.", "Холодный океан окружает ржавый бункер. Плавание отнимает выносливость, долгое пребывание вызывает переохлаждение."),
    "br.info.8": ("Echoing caves, deep burrows and freezing pools hide the route onward.", "Эхо пещер, глубокие норы и ледяные водоёмы скрывают дальнейший путь."),
    "br.info.9": ("Fog and endless night turn the suburban streets into a maze.", "Туман и бесконечная ночь превращают пригородные улицы в лабиринт."),
    "br.info.10": ("Overcast fields offer food and shelter, but the roads never seem to end.", "Пасмурные поля дают еду и укрытие, но дороги здесь никогда не заканчиваются."),
    "br.name.11": ("Concrete Jungle", "Бетонные джунгли"),
    "br.name.12": ("The Well", "Колодец"),
    "br.name.13": ("Collectors", "Коллекторы"),
    "br.name.14": ("Inhospitality", "Негостеприимство"),
    "br.name.15": ("J. Barry Mental Asylum", "Психиатрическая больница Дж. Барри"),
    "br.name.16": ("Abandoned Carrier", "Заброшенный авианосец"),
    "br.name.17": ("Nostalgic Memories", "Ностальгические воспоминания"),
    "br.name.18": ("Abyss Inn", "Бездна-отель"),
    "br.name.19": ("Aedificium", "Эдифициум"),
    "br.name.20": ("Extraterrestre", "Инопланетный ландшафт"),
    "br.info.11": ("An empty city of roads, concrete towers and unstable blocks.", "Пустой город дорог, бетонных башен и нестабильных кварталов."),
    "br.info.12": ("A decaying ring of apartments looks inward into a bottomless well.", "Ветхое кольцо квартир смотрит внутрь, в бездонный колодец."),
    "br.info.13": ("Sewage channels, broken platforms and contaminated water make every shortcut costly.", "Канализационные каналы, сломанные помосты и грязная вода делают каждый путь опасным."),
    "br.info.14": ("An abandoned hospital hides hazards behind its clean corridors.", "Заброшенная больница скрывает опасности за чистыми коридорами."),
    "br.info.15": ("The asylum repeats itself while memories and sanity become unreliable.", "Психиатрическая больница повторяется, а память и рассудок становятся ненадёжными."),
    "br.info.16": ("A steel carrier creaks around flooded ballast and failing machinery.", "Стальной авианосец скрипит вокруг затопленного балласта и неисправных механизмов."),
    "br.info.17": ("Rooms from childhood memories drift in a dark, unstable maze.", "Комнаты детских воспоминаний дрейфуют в тёмном нестабильном лабиринте."),
    "br.info.18": ("The inn offers rooms, corridors and a descent that never feels safe.", "Отель предлагает комнаты и коридоры, но спуск здесь никогда не кажется безопасным."),
    "br.info.19": ("The architecture is alive. Darkness and watching eyes make every hallway suspect.", "Архитектура жива. Тьма и наблюдающие глаза делают подозрительным каждый коридор."),
    "br.info.20": ("Alien landscapes shift without warning: shelter matters more than direction.", "Инопланетные ландшафты меняются без предупреждения: укрытие важнее направления."),
    "world.camera": ("F8 layer/volume | ,/. Z | arrows rotate", "F8 слой/объём | ,/. Z | стрелки — поворот"),
    "vertical.fall": ("Fell {n} storeys: {d} damage.", "Падение на {n} этаж: урон {d}."),
    "vertical.air": ("Open shaft (no floor)", "Открытая шахта (нет пола)"),
    "gfx.title": ("Graphics", "Графика"),
    "gfx.keys": ("F5 ASCII | F6 first person | F7 3D map | F11 fullscreen | RMB inspect", "F5 ASCII | F6 от лица | F7 3D-карта | F11 полный экран | ПКМ осмотр"),
    "gfx.camera_keys": ("3D: arrows rotate; PgUp/PgDn tilt; wheel zoom; Home reset; MMB drag", "3D: стрелки — поворот; PgUp/PgDn — наклон; колесо — зум; Home — сброс"),
    "gfx.ceiling": ("Ceiling", "Потолок"),
    "gfx.distance": ("Draw distance", "Дальность прорисовки"),
    "gfx.skybox": ("Skybox color", "Цвет неба"),
    "gfx.view": ("View", "Вид"),
    "gfx.ascii": ("Classic ASCII", "Классический ASCII"),
    "gfx.first": ("First person", "От первого лица"),
    "gfx.board": ("3D dungeon board", "Объёмная карта"),
    "gfx.quality": ("First person: ray quality", "От лица: качество лучей"),
    "gfx.q":        ("Quality", "Качество"),
    "gfx.q0": ("Low", "Низкое"),
    "gfx.q1": ("Medium", "Среднее"),
    "gfx.q2": ("High", "Высокое"),
    "gfx.lighting": ("Shader lighting", "Шейдерное освещение"),
    "gfx.fog": ("First person: distance fog", "От лица: туман расстояния"),
    "gfx.outlines": ("Map: geometry outlines", "Карта: контуры геометрии"),
    "gfx.full_map": ("Map: reveal unexplored terrain", "Карта: раскрыть неисследованное"),
    "gfx.single_layer": ("Map: selected Z only", "Карта: только выбранный Z"),
    "gfx.backend": ("Presentation backend", "Графический backend"),
    "gfx.adapter": ("GPU preference", "Предпочтение GPU"),
    "gfx.target": ("Click target; Enter confirms, Esc cancels", "Выберите цель мышью; Enter — подтвердить, Esc — отмена"),
    "gfx.tileset": ("Tileset", "Tileset-графика"),
    "gfx.tileset.on": ("Tileset", "Tileset"),
    "gfx.tileset.off": ("ASCII fallback", "ASCII fallback"),
    "gfx.autocolor": ("Auto-color sprites", "Автоперекраска спрайтов"),
    "set.language":    ("Language", "Язык"),
    "set.sound":       ("Sound", "Звук"),
    "set.volume":      ("Volume", "Громкость"),
    "set.window":      ("Window size", "Размер окна"),
    "set.window_auto": ("Auto (fit screen)", "Авто (по экрану)"),
    "set.window_manual": ("Manual resize", "Ручной размер"),
    "set.fullscreen":  ("Fullscreen", "Полный экран"),
    "set.fullscreen.on": ("on", "вкл"),
    "set.fullscreen.off": ("off", "выкл"),
    "set.controls":    ("Controls", "Управление"),
    "set.back":        ("Back", "Назад"),
    "set.debug":       ("Debug tools", "Инструменты отладки"),
    "debug.map":       ("Reveal full terrain", "Открыть весь рельеф карты"),
    "debug.map_done":  ("Terrain revealed.", "Весь рельеф открыт."),
    "debug.immortal":  ("Immortality", "Бессмертие"),
    "debug.get_item":  ("Add any item to inventory", "Получить любой предмет"),
    "debug.spawn_item": ("Spawn any item on floor", "Создать предмет на полу"),
    "debug.light":     ("Toggle lighting override", "Переключить отладочное освещение"),
    "debug.fly":       ("Fly mode", "Режим полёта"),
    "debug.noclip":    ("No clip", "Проход сквозь стены"),
    "debug.z_up":      ("Move one floor up", "Перейти на этаж выше"),
    "debug.z_down":    ("Move one floor down", "Перейти на этаж ниже"),
    "debug.no_z":      ("No such Z-level.", "Такого Z-уровня нет."),
    "debug.z_changed": ("Moved to Z {z}.", "Переход на Z {z}."),
    "debug.skybox": ("Change skybox color", "Изменить цвет неба"),
    "debug.choose_item": ("Choose object", "Выберите объект"),
    "debug.item_added": ("Added: {item}", "Добавлено: {item}"),
    "debug.item_spawned": ("Spawned: {item}", "Создано: {item}"),
    "set.on":          ("on", "вкл"),
    "set.off":         ("off", "выкл"),
    "set.reset":       ("Reset to defaults", "Сбросить настройки"),
    "set.language.en": ("English", "Английский"),
    "set.language.ru": ("Russian", "Русский"),

    # --- настройки управления ---------------------------------------------
    "ctl.title":       ("Controls", "Управление"),
    "ctl.active":      ("Control preset", "Набор управления"),
    "ctl.preset.newcomer": ("For new players", "Для новых игроков"),
    "ctl.preset.classic": ("Old-school", "Олдскульный"),
    "ctl.customize": ("Customize current preset", "Настроить клавиши текущего набора"),
    "ctl.rebind":      ("Press a new key for: {a}", "Нажмите новую клавишу: {a}"),
    "ctl.rebind_hint": ("Enter - assign   Esc - cancel", "Enter - назначить   Esc - отмена"),
    "ctl.assigned":    ("{a} is now {k}", "{a} теперь {k}"),
    "ctl.locked":      ("This key cannot be reassigned.",
                        "Эту клавишу нельзя переназначить."),
    "ctl.esc_always":  ("Esc and F1 cannot be reassigned.",
                        "Esc и F1 переназначить нельзя."),
    "ctl.more":        ("+{n} more", "ещё {n}"),
    "ctl.g.move":      ("Movement", "Движение"),
    "ctl.g.stairs":    ("Stairs", "Лестницы"),
    "ctl.g.items":     ("Items", "Предметы"),
    "ctl.g.combat":    ("Combat", "Бой"),
    "ctl.g.world":     ("World", "Мир"),
    "ctl.g.system":    ("System", "Система"),
    "a.move_north":    ("Move up", "Идти вверх"),
    "a.move_south":    ("Move down", "Идти вниз"),
    "a.move_west":     ("Move left", "Идти влево"),
    "a.move_east":     ("Move right", "Идти вправо"),
    "a.move_nw":       ("Move up-left", "Идти вверх-влево"),
    "a.move_ne":       ("Move up-right", "Идти вверх-вправо"),
    "a.move_sw":       ("Move down-left", "Идти вниз-влево"),
    "a.move_se":       ("Move down-right", "Идти вниз-вправо"),
    "a.wait":          ("Wait one turn", "Ждать ход"),
    "a.rest":          ("Rest for 10 turns", "Отдыхать 10 ходов"),
    "a.sleep":         ("Sleep", "Спать"),
    "a.workshop":      ("Furniture / workshop", "Мебель / мастерская"),
    "kind.material":   ("material", "материал"),
    "a.swap_weapon":   ("Quick weapon swap", "Быстрая смена оружия"),
    "m.rest_stop":     ("Rest interrupted.", "Отдых прерван."),
    "m.rest_done":     ("You finish resting.", "Вы закончили отдых."),
    "m.no_spare_weapon": ("No spare weapon.", "Нет запасного оружия."),
    "m.sleep_start": ("You fall asleep for up to {n} turns.", "Вы засыпаете на срок до {n} ходов."),
    "m.sleep_wake": ("You hear movement nearby. Wake up?", "Вы слышите движение рядом. Проснуться?"),
    "m.sleep_wake_legs": ("You hear footsteps on four legs. Wake up?", "Вы слышите шаги на четырёх ногах. Проснуться?"),
    "m.sleep_wake_slap": ("You hear footsteps like wet slaps. Wake up?", "Вы слышите шаги, словно шлепки по полу. Проснуться?"),
    "m.sleep_wake_unknown": ("It is coming here. It. It. It. Wake up?", "Оно идёт сюда. Оно. Оно. Оно. Проснуться?"),
    "sleep.wake": ("Wake up", "Проснуться"),
    "sleep.start": ("Start sleeping", "Начать сон"),
    "sleep.apply": ("Apply", "Применить"),
    "sleep.continue": ("Keep sleeping", "Продолжить сон"),
    "set.sleep": ("Sleep duration", "Длительность сна"),
    "audio.title": ("Sound settings", "Настройки звука"),
    "audio.volume": ("Master volume", "Общая громкость"),
    "audio.music_volume": ("Music volume", "Громкость музыки"),
    "audio.effects_volume": ("Effects volume", "Громкость эффектов"),
    "audio.ui_volume": ("Interface volume", "Громкость интерфейса"),
    "audio.environment_volume": ("Environment: steps, doors", "Окружение: шаги, двери"),
    "audio.alarm_volume": ("Alarms and warnings", "Тревоги и предупреждения"),
    "audio.open": ("Sound: volume sliders", "Звук: ползунки громкости"),
    "audio.test": ("Test sound", "Проверить звук"),
    "audio.hint": ("Arrows / mouse: sliders   Tab: buttons   Esc: back", "Стрелки / мышь: ползунки   Tab: кнопки   Esc: назад"),
    "audio.unavailable": ("Audio device unavailable", "Аудиоустройство недоступно"),
    "m.took_off":      ("You take off {it}.", "Вы снимаете: {it}."),
    "a.descend":       ("Go down the stairs", "Спуститься по лестнице"),
    "a.ascend":        ("Go up the stairs", "Подняться по лестнице"),
    "a.pickup":        ("Pick up an item", "Взять предмет"),
    "a.pickup_all":    ("Pick up everything", "Взять всё с пола"),
    "a.items_here":    ("List items on the floor", "Список предметов на полу"),
    "a.inventory":     ("Open the inventory", "Открыть инвентарь"),
    "a.drop":          ("Drop an item", "Выбросить предмет"),
    "a.eat":           ("Eat food", "Съесть"),
    "a.quaff":         ("Drink a bottled liquid", "Выпить жидкость из бутылки"),
    "a.read":          ("Read a document", "Прочитать документ"),
    "a.wield":         ("Wield a weapon", "Взять оружие в руки"),
    "a.wear":          ("Wear armour", "Надеть броню"),
    "a.takeoff":       ("Take off equipment", "Снять снаряжение"),
    "a.force_fight":   ("Fight an adjacent enemy", "Ударить соседа"),
    "a.fire":          ("Fire a missile", "Выстрелить"),
    "a.zap":           ("Activate an artifact", "Активировать артефакт"),
    "a.throw":         ("Throw an item", "Бросить предмет"),
    "a.pick_lock":     ("Pick a nearby lock", "Вскрыть ближайший замок"),
    "a.map_toggle":    ("Toggle the area map", "Карта области"),
    "a.lights":        ("Toggle room lighting", "Свет в комнатах"),
    "a.char_sheet":    ("Character sheet", "Лист персонажа"),
    "a.help":          ("This help screen", "Эта справка"),
    "a.save":          ("Save the game", "Сохранить игру"),
    "a.save_quit":     ("Save and quit", "Сохранить и выйти"),
    "a.settings":      ("Open the settings", "Открыть настройки"),
    "a.lang_toggle":   ("Switch language", "Сменить язык"),
    "a.sound_toggle":  ("Toggle sound", "Вкл/выкл звук"),

    # --- панели ----------------------------------------------------------
    "ui.status":       ("STATUS", "СОСТОЯНИЕ"),
    "ui.area":         ("AREA", "ОБЛАСТЬ"),
    "ui.messages":     ("MESSAGES", "СООБЩЕНИЯ"),
    "ui.targeting":    ("TARGETING", "ПРИЦЕЛИВАНИЕ"),
    "ui.depth_of":     ("Depth {d} / {m}", "Глубина {d} / {m}"),
    "ui.items":        ("{n} items  {k} kills", "{n} вещей  {k} убийств"),
    "ui.bars":         ("HP", "ЗДОРОВЬЕ"),
    "ui.bars.short":   ("HP", "HP"),
    "ui.food":         ("FOOD", "СЫТОСТЬ"),
    "ui.food.short":   ("SAT", "НС"),
    "ui.stamina.short": ("STA", "ВН"),
    "ui.sanity.short": ("SAN", "РС"),
    "ui.reserve.short": ("BODY", "ЗАПАС"),
    "ui.lbl.ac":       ("AC", "БРОНЯ"),
    "ui.lbl.str":      ("STR", "СИЛ"),
    "ui.lbl.dex":      ("DEX", "ЛОВ"),
    "ui.lbl.lvl":      ("Level", "Ур."),
    "ui.lbl.gold":     ("Gold", "Золото"),
    "ui.lbl.wpn":      ("Hand", "Рука"),

    # --- предметы: действия ---------------------------------------------
    "act.info":        ("Info", "Свойства"),
    "act.drop":        ("Drop it", "Бросить"),
    "act.eat":         ("Eat it", "Съесть"),
    "act.quaff":       ("Quaff it", "Выпить"),
    "act.read":        ("Read it", "Прочитать"),
    "act.wear":        ("Wear it", "Надеть"),
    "act.wield":       ("Wield it", "Взять в руки"),
    "act.takeoff":     ("Take off", "Снять"),
    "act.fire":        ("Fire it", "Выстрелить"),
    "act.zap":         ("Activate it", "Активировать"),
    "act.throw":       ("Throw it", "Бросить в цель"),

    # --- предметы: выбор -------------------------------------------------
    "pick.drop":       ("Drop what?", "Что бросить?"),
    "pick.eat":        ("Eat what?", "Что съесть?"),
    "pick.quaff":      ("Quaff what?", "Что выпить?"),
    "pick.read":       ("Read what?", "Что прочитать?"),
    "pick.wield":      ("Wield what?", "Что взять в руки?"),
    "pick.wear":       ("Wear what?", "Что надеть?"),
    "pick.takeoff":    ("Take off what?", "Что снять?"),
    "pick.identify":   ("Identify what?", "Что опознать?"),
    "pick.lock":       ("Which lock?", "Какой замок?"),
    "pick.fight":      ("Fight what?", "Кого бить?"),
    "ui.items_here":   ("Items here", "Предметы здесь"),
    "ui.inventory":    ("Inventory", "Инвентарь"),
    "ui.close":        ("Close", "Закрыть"),
    "ui.empty":        ("Nothing carried", "Ничего нет"),
    "ui.choose_action": ("Choose an action", "Выберите действие"),
    "ui.quick_actions": ("Actions", "Действия"),
    "ui.quick_interact": ("Interact", "Взаимодействие"),
    "ui.quick_inventory": ("Inventory", "Инвентарь"),
    "ui.quick_map": ("Map", "Карта"),
    "ui.quick_character": ("Character", "Персонаж"),
    "ui.quick_hide": ("Hide", "Скрыть"),
    "need.pickup":     ("You have to pick it up first.", "Сначала нужно поднять."),
    "need.suitable":   ("Nothing suitable here.", "Нечего выбрать."),
    "item.none":       ("nothing", "ничего"),
    "item.bare_hands": ("bare hands", "голыми руками"),
    "item.blessed":    ("stable", "стабильное"),
    "item.cursed":     ("unstable", "нестабильное"),
    "m.liquid_pending": ("This liquid cannot be used yet.", "Эту жидкость пока нельзя использовать."),
    "item.info":       ("Item info", "Свойства предмета"),
    "item.value":      ("value ~{v} gold", "ценность ~{v} зол."),
    "item.damage":     ("damage {n}d{s}", "урон {n}d{s}"),
    "item.to_hit":     ("to-hit {n}", "точность {n}"),
    "item.range":      ("range {n}", "дальность {n}"),
    "item.ac":         ("armor class {n}", "класс брони {n}"),
    "item.bonus":      ("special bonus", "особый бонус"),
    "item.charges":    ("charges {a}/{b}", "заряды {a}/{b}"),
    "item.nutrition":  ("saturation +{n}", "насыщение +{n}"),
    "item.food_tags": ("food types: {tags}", "типы еды: {tags}"),
    "item.hydrating": ("Drinking water: doubles a meal's saturation.", "Питьевая вода: удваивает насыщение блюда."),
    "food.salty": ("salty", "солёная"),
    "food.sweet": ("sweet", "сладкая"),
    "food.dry": ("dry", "сухая"),
    "food.moist": ("moist", "влажная"),
    "food.fried": ("fried", "жареная"),
    "m.nourished": ("Saturation +{gain} (combination bonus +{bonus}).", "Насыщение +{gain} (бонус сочетания +{bonus})."),
    "m.exhaustion_relief": ("Balanced food and water reduce exhaustion by {n}.", "Еда с водой уменьшает истощение на {n}."),
    "body.exhausted": ("exhaustion", "истощение"),
    "body.neutral": ("balanced", "равновесие"),
    "body.plump": ("slight fullness", "лёгкая полнота"),
    "body.reserve": ("energy reserve", "запас энергии"),
    "body.obese": ("obesity: movement slowed", "ожирение: движение замедлено"),
    "sheet.saturation": ("Saturation {n}/100", "Насыщение {n}/100"),
    "sheet.stamina": ("Stamina {n}/50", "Выносливость {n}/50"),
    "sheet.sanity": ("Sanity {n}/50", "Рассудок {n}/50"),
    "sheet.reserve": ("Body {level:+d}, {n}/50: {state}", "Запас/истощение {level:+d}, {n}/50: {state}"),
    "sheet.base_hp": ("Base maximum health: {n}", "Базовый максимум здоровья: {n}"),
    "help.sprint": ("Shift + movement: sprint 2-3 cells; shifted item commands take priority.", "Shift + движение: бег на 2–3 клетки; команды предметов с Shift имеют приоритет."),
    "help.nutrition": ("Combine food types within 30 turns; drinking water doubles the meal bonus.", "Сочетайте типы еды за 30 ходов; питьевая вода удваивает насыщение блюда."),
    "help.sleep": ("Sleep restores stamina; health regeneration scales with saturation.", "Сон возвращает выносливость; регенерация здоровья зависит от насыщения."),
    "e.salt_water": ("Salt water makes you thirstier: saturation -5, stamina -2.", "Солёная вода усиливает жажду: насыщение -5, выносливость -2."),
    "e.stagnant_water": ("The stale water barely sustains you; it will not improve a meal.", "Застоявшаяся вода почти не насыщает и не улучшает сочетание еды."),
    "item.label.bc":   ("{c} {n}", "{c} {n}"),
    "item.label.cnt":  (" x{n}", " x{n}"),
    "item.unident":    ("unidentified {k}", "неопознанное ({k})"),
    "kind.potion":     ("bottled liquid", "бутылка с жидкостью"),
    "kind.scroll":     ("document", "документ"),
    "kind.wand":       ("artifact", "артефакт"),
    "kind.ring":       ("ring", "кольцо"),
    "kind.weapon":     ("weapon", "оружие"),
    "kind.armor":      ("armor", "броня"),
    "kind.missile":    ("missile", "снаряд"),
    "kind.food":       ("food", "еда"),
    "kind.gold":       ("gold pieces", "золотых"),
    "kind.tool":       ("tool", "инструмент"),

    # --- сообщения: игрок ------------------------------------------------
    "m.descend":       ("You descend into the dungeon. Beware.",
                        "Вы спускаетесь в подземелье. Берегитесь."),
    "m.help_hint":     ("Press ? for help, m for the full map, S to save.",
                        "? - справка, m - карта, Shift+S - сохранить."),
    "m.loaded":        ("Game loaded.", "Игра загружена."),
    "m.no_save":       ("No save found.", "Сохранение не найдено."),
    "m.saved":         ("Game saved.", "Игра сохранена."),
    "m.save_err":      ("Could not save the game.", "Не удалось сохранить игру."),
    "m.save_quit":     ("Game saved. Goodbye.", "Игра сохранена. До свидания."),
    "m.return":        ("You return to level {d}.", "Вы вернулись на уровень {d}."),
    "m.nothing_here":  ("There is nothing here.", "Здесь ничего нет."),
    "m.pack_full":     ("Your pack is full.", "Рюкзак полон."),
    "m.pickup_gold":   ("You pick up {n} gold pieces.",
                        "Вы подбираете {n} золотых."),
    "m.pickup":        ("You pick up {it}.", "Вы подбираете: {it}."),
    "m.pickup_many":   ("You pick up {n} item(s).",
                        "Вы подбираете {n} предм. с пола."),
    "m.wall":          ("The wall is solid.", "Стена глухая."),
    "m.hedge":         ("The hedge resists you.", "Живая изгородь не пускает."),
    "m.open_door":     ("You open the door.", "Вы открываете дверь."),
    "m.corpse":        ("You step over a corpse.", "Вы переступаете через труп."),
    "m.wait":          ("You wait.", "Вы ждёте."),
    "m.stumble":       ("You stumble...", "Вы спотыкаетесь..."),
    "m.confused_off":  ("You feel less confused.", "Путаница в голове проходит."),
    "m.wake":          ("You wake up.", "Вы просыпаетесь."),
    "m.die":           ("You die...", "Вы погибли..."),
    "m.starving":      ("Saturation is empty; your body uses its reserves.", "Насыщение на нуле: организм расходует запасы."),
    "m.need_light_source": ("You need an equipped light source.", "Нужен надетый источник света."),
    "m.no_stairs":     ("There are no stairs here.", "Здесь нет лестницы."),
    "m.descend_to":    ("You descend to level {d}.",
                        "Вы спускаетесь на уровень {d}."),
    "m.ascend_to":     ("You climb to level {d}.",
                        "Вы поднимаетесь на уровень {d}."),
    "m.no_stairs_up":  ("You refuse to climb back into the sunlight.",
                        "Вы не хотите возвращаться к солнцу."),
    "m.bottom":        ("You have reached the bottom of the dungeon!",
                        "Вы дошли до самого дна подземелья!"),
    "m.map_fade":      ("The map fades.", "Карта стирается из памяти."),
    "m.map_memorize":  ("You memorize the whole level ({d} z).",
                        "Вы запоминаете весь уровень ({d} з)."),
    "m.lights_off":    ("The rooms fade into darkness.",
                        "Комнаты погружаются во тьму."),
    "m.lights_on":     ("You light every room you can see.",
                        "Вы зажигаете свет во всех комнатах."),
    "m.no_lock":       ("There is no locked door nearby.",
                        "Рядом нет запертых дверей."),
    "m.pick_lock":     ("You pick the lock.", "Вы вскрываете замок."),
    "m.lock_at":       ("{what} at ({x},{y})", "{what} в ({x},{y})"),
    "m.nothing_adj":   ("There is nothing adjacent to fight.",
                        "Рядом некого бить."),
    "m.trap":          ("You fall into a trap! {d} damage.",
                        "Вы проваливаетесь в ловушку! -{d} здоровья."),
    "m.fountain":      ("The fountain water heals you.",
                        "Вода из фонтана лечит вас."),
    "m.xp":            ("{src} (+{n} xp)", "{src} (+{n} опыта)"),
    "m.src.descend":   ("You descend.", "Вы спускаетесь."),
    "m.src.ascend":    ("You climb up.", "Вы поднимаетесь."),
    "m.level_up":      ("Welcome to experience level {n}!",
                        "Достигнут {n} уровень опыта!"),
    "m.cancelled":     ("Cancelled.", "Отменено."),
    "m.not_carrying":  ("You are not carrying anything.",
                        "У вас ничего нет."),
    "m.not_wearing":   ("You are not wearing anything.",
                        "На вас ничего не надето."),
    "m.no_armor":      ("You are not wearing armor.",
                        "На вас нет брони."),
    "m.no_ammo":       ("You have nothing to fire.",
                        "Некому стрелять."),
    "m.no_bow":        ("You have no bow or crossbow.",
                        "У вас нет лука или арбалета."),
    "m.no_throw":      ("You have nothing to throw.",
                        "Нечего бросать."),
    "m.no_wands":      ("You have no artifacts.", "У вас нет артефактов."),
    "m.wand_spent":    ("The artifact is spent.", "Артефакт разряжен."),
    "m.put_away":      ("You put the document away.", "Вы убираете документ."),
    "m.know":          ("You now know: {it}.", "Теперь вы знаете: {it}."),
    "m.wield":         ("You are now wielding {it}.",
                        "Вы берёте в руки: {it}."),
    "m.wear":          ("You are now wearing {it}.",
                        "Вы надеваете: {it}."),
    "m.takeoff":       ("You take off {it}.", "Вы снимаете: {it}."),
    "m.cold":          ("You feel a chill. Something is wrong.",
                        "Вас бьёт холод. Что-то не так."),
    "m.cannot_wield":  ("You cannot wield {it}.", "Нельзя взять в руки: {it}."),
    "m.cannot_wear":   ("You cannot wear {it}.", "Нельзя надеть: {it}."),
    "m.cannot_eat":    ("You cannot eat {it}.", "Нельзя съесть: {it}."),
    "m.cannot_quaff":  ("You cannot drink {it}.", "Нельзя выпить: {it}."),
    "m.cannot_read":   ("You cannot read {it}.", "Нельзя прочитать: {it}."),
    "m.gold_swallow":  ("You swallow a gold piece. That was a mistake.",
                        "Вы проглатываете золотую монету. Это была ошибка."),
    "m.no_room_drop":  ("There is no room to drop it.",
                        "Некуда это деть."),
    "m.drop_it":       ("You drop {it}.", "Вы бросаете: {it}."),
    "m.eat_it":        ("You eat {it}.", "Вы съедаете: {it}."),
    "m.feel_worse":    ("You feel a little worse.",
                        "Вам становится немного хуже."),
    "m.hunger.0":      ("Saturation is high.", "Высокое насыщение."),
    "m.hunger.1":      ("Saturation is moderate.", "Умеренное насыщение."),
    "m.hunger.2":      ("Saturation is low.", "Низкое насыщение."),
    "m.hunger.3":      ("Saturation is empty; reserves sustain you.", "Насыщение на нуле; организм использует запасы."),

    # --- сообщения: бой --------------------------------------------------
    "c.miss":          ("You miss the {name}.", "Промах мимо {name}."),
    "c.hit":           ("You hit the {name} for {d} damage.",
                        "Вы бьёте {name} на {d} урона."),
    "c.flash":         (" It flashes!", " Оружие вспыхивает!"),
    "c.kill":          (" The {name} dies!", " {name} погибает!"),
    "c.hurt":          ("The {name} hits you for {d} damage.",
                        "{name} наносит вам {d} урона."),
    "c.you_die":       (" You die!", " Вы погибаете!"),
    "c.missile_miss":  ("Your missile misses the {name}.",
                        "Ваш снаряд пролетает мимо {name}."),
    "c.missile_hit":   ("Your missile hits the {name} for {d} damage.",
                        "Ваш снаряд попадает в {name} на {d} урона."),
    "c.whistle":       ("The missile whistles off into the darkness.",
                        "Снаряд уносится в темноту со свистом."),

    # --- сообщения: монстры ----------------------------------------------
    "m.wake_up":       ("The {name} wakes up.", "{name} просыпается."),
    "m.picks_lock":    ("The {name} picks the lock.",
                        "{name} вскрывает замок."),
    "m.opens_door":    ("The {name} opens the door.", "{name} открывает дверь."),
    "m.breaks_door":   ("The {name} breaks down the door!",
                        "{name} ломает дверь!"),
    "m.no_confused":   ("The {name} is no longer confused.",
                        "{name} больше не путается."),

    # --- сообщения: эффекты ----------------------------------------------
    "e.heal_little":   ("You feel a little better.", "Вам стало чуть лучше."),
    "e.heal":          ("You feel better. (+{n} HP)",
                        "Вам стало лучше. (+{n} здоровья)"),
    "e.warmth":        ("Warmth spreads through you.", "По телу разливается тепло."),
    "e.flood":         ("A flood of vitality!", "Вас наполняет жизненная сила!"),
    "e.full_heal":     ("You feel completely healed.",
                        "Вы полностью исцелены."),
    "e.experienced":   ("You feel more experienced!",
                        "Вы чувствуете себя опытнее!"),
    "e.powerful":      ("You suddenly feel much more powerful!",
                        "Внезапно вы чувствуете себя могущественнее!"),
    "e.stronger":      ("You feel stronger. (STR {n})",
                        "Вы чувствуете себя сильнее. (СИЛ {n})"),
    "e.burns":         ("The liquid burns! You take {d} damage.",
                        "Жидкость обжигает! -{d} здоровья."),
    "e.sears":         ("The liquid sears your flesh! {d} damage.",
                        "Жидкость разъедает плоть! -{d} здоровья."),
    "e.spinning":      ("Everything starts spinning...",
                        "Всё вокруг плывёт..."),
    "e.breathe":       ("The walls breathe. What was there a moment ago is not now.",
                        "Стены дышат. То, что было секунду назад, исчезло."),
    "e.heavy":         ("Your eyelids grow heavy. You fall asleep.",
                        "Веки наливаются тяжестью. Вы засыпаете."),
    "e.tilts":         ("The world tilts. (STR -1)",
                        "Мир кренится. (СИЛ -1)"),
    "e.water":         ("The water is lukewarm and clean.",
                        "Вода тёплая и чистая."),
    "e.tasteless":     ("It tastes like nothing.", "Вкуса нет."),
    "e.map_area":      ("The map around you is etched in your mind ({d} z).",
                        "Карта местности отпечаталась в памяти ({d} з)."),
    "e.magic_map":     ("You sense the layout of the whole level.",
                        "Вы чувствуете планировку всего уровня."),
    "e.blink":         ("You blink out and reappear somewhere else.",
                        "Вас охватывает ореол, и вы оказываетесь в другом месте."),
    "e.malice":        ("You feel a surge of malice. ({n} monsters rouse)",
                        "Вас охватывает злоба. (проснулось монстров: {n})"),
    "e.forget":        ("Everything suddenly looks unfamiliar. ({n} items forgotten)",
                        "Всё вдруг кажется чужим. (забыто вещей: {n})"),
    "e.armor_crumb":   ("Your armor crumbles to dust!",
                        "Ваша броня рассыпается в пыль!"),
    "e.fire_around":   ("Fire erupts around you! {n} creatures burn.",
                        "Вокруг вас вспыхивает пламя! Обожжено существ: {n}."),
    "e.fear":          ("A wave of fear rolls out. {n} creatures flee.",
                        "Волна страха расходится. Спаслись существ: {n}."),
    "e.recharge":      ("The artifact crackles with renewed energy. ({it})",
                        "Артефакт трещит, наполняясь энергией. ({it})"),
    "e.surge":         ("You feel a surge of energy, but nothing happens.",
                        "Вас охватывает волна энергии, но ничего не происходит."),
    "e.lucky":         ("Fortune smiles upon you.", "Удача вам улыбается."),
    "e.blank":         ("This paper seems to be blank.",
                        "Этот лист бумаги кажется пустым."),
    "e.crumble":       ("The paper crumbles to dust.",
                        "Бумага рассыпается в пыль."),
    "e.wand_light":    ("A blaze of light illuminates the area!",
                        "Вспышка света заливает область!"),
    "e.puff":          ("A harmless puff of air.", "Безобидное облачко воздуха."),
    "e.dig":           ("You bore into the rock.",
                        "Вы долбите породу."),
    "e.no_soft":       ("Nothing soft to dig here.",
                        "Здесь нечего копать."),
    "e.wand_hit":      ("The artifact cracks! {name} takes {d} damage.",
                        "Артефакт разряжается! {name} получает {d} урона."),
    "e.wand_air":      ("The artifact discharges into empty air.",
                        "Разряд уходит в пустоту."),
    "e.elem":          ("{what}, hitting {n} creature(s).",
                        "{what}: задеты существа ({n})."),
    "e.elem.flames":   ("Flames bloom", "Вспыхивает пламя"),
    "e.elem.frost":    ("Frost spreads", "Расползается мороз"),
    "e.elem.lightning":("Lightning forks", "Раскалывается молния"),
    "e.elem.drowsy":   ("a drowsy haze", "сонная пелена"),
    "e.elem_empty":    ("{what}... into empty air.", "{what}... впустую."),
    "e.fizzle":        ("The {kind} fizzles strangely ({err}).",
                        "{kind} странно вспыхивает ({err})."),
    "e.nothing":       ("Nothing seems to happen.",
                        "Ничего не происходит."),

    # --- описание тайлов -------------------------------------------------
    "t.wall":          ("solid rock wall", "каменная стена"),
    "t.hedge":         ("a thick hedge", "густая изгородь"),
    "t.locked":        ("a locked door", "запертая дверь"),
    "t.closed":        ("a closed door", "закрытая дверь"),
    "t.open":          ("an open door", "открытая дверь"),
    "t.down":          ("a staircase leading down", "лестница вниз"),
    "t.up":            ("a staircase leading up", "лестница наверх"),
    "t.altar":         ("a stone altar", "каменный алтарь"),
    "t.fountain":      ("a bubbling fountain", "бурлящий фонтан"),
    "t.rubble":        ("a pile of rubble", "груда обломков"),
    "t.trapdoor":      ("a suspicious trapdoor", "подозрительный люк"),
    "t.floor":         ("floor", "пол"),

    # --- лист персонажа ---------------------------------------------------
    "sheet.title":      ("Character sheet", "Лист персонажа"),
    "sheet.name":       ("Name: the dungeon delver", "Имя: искатель подземелий"),
    "sheet.lvl":        ("Level: {n}", "Уровень опыта: {n}"),
    "sheet.xp":         ("XP: {a}/{b}", "Опыт: {a}/{b}"),
    "sheet.hp":         ("HP: {a}/{b}", "Здоровье: {a}/{b}"),
    "sheet.ac":         ("AC: {n}", "Класс брони: {n}"),
    "sheet.str":        ("STR: {n}", "СИЛ: {n}"),
    "sheet.dex":        ("DEX: {n}", "ЛОВ: {n}"),
    "sheet.con":        ("CON: {n}", "ТЕЛ: {n}"),
    "sheet.dmg":        ("Damage bonus: {n:+d}", "Бонус урона: {n:+d}"),
    "sheet.hit":        ("To-hit: {n:+d}", "Бонус точности: {n:+d}"),
    "sheet.deepest":    ("Deepest: {n}", "Глубина рекорда: {n}"),
    "sheet.gold":       ("Gold: {n}", "Золото: {n}"),
    "sheet.kills":      ("Kills: {n}", "Убийств: {n}"),
    "sheet.turns":      ("Turns: {n}", "Ходов: {n}"),
    "sheet.wielding":   ("Wielding:", "В руках:"),
    "sheet.wearing":    ("Wearing:", "Надето:"),
    "sheet.carrying":   ("Carrying:", "В сумке:"),
    "sheet.more":       ("... and {n} more", "... и ещё {n}"),
    "sheet.status":     ("Statuses: {s}", "Состояния: {s}"),
    "st.confused":      ("confused", "путаница"),
    "st.hallucinating": ("seeing things", "галлюцинации"),
    "st.asleep":       ("asleep", "сон"),
    "st.lucky":        ("lucky", "удачливый"),
    "st.flee":         ("fleeing", "бежит"),
    "st.stunned":      ("stunned", "оглушён"),

    # --- смерть ----------------------------------------------------------
    "death.win":        ("YOU ESCAPED THE DUNGEON", "ВЫ ВЫШЛИ ИЗ ПОДЗЕМЕЛЬЯ"),
    "death.lose":       ("YOU HAVE DIED", "ВЫ ПОГИБЛИ"),
    "death.depth":      ("Reached depth:    {a} / {b}",
                         "Достигнутая глубина: {a} / {b}"),
    "death.xl":         ("Experience level: {a}", "Уровень опыта: {a}"),
    "death.gold":       ("Gold:             {a}", "Золото:             {a}"),
    "death.kills":      ("Kills:            {a}", "Убийств:            {a}"),
    "death.turns":      ("Turns taken:      {a}", "Ходов сделано:      {a}"),
    "death.deepest":    ("Deepest level:    {a}", "Макс. глубина:       {a}"),
    "death.back":       ("[ Enter - back to title ]", "[ Enter - в меню ]"),

    # --- прицеливание ----------------------------------------------------
    "tgt.target":       ("({x},{y}) {what}", "({x},{y}) {what}"),
    "tgt.monster":      ("{name} - hp {a}/{b} - ac {c}",
                         "{name} - здоровье {a}/{b} - броня {c}"),
    "tgt.keys":         ("arrows aim - Enter confirm - Esc cancel",
                         "стрелки - прицел, Enter - подтвердить, Esc - отмена"),

    # --- справка ---------------------------------------------------------
    "help.title":       ("Help", "Справка"),
    "help.1":  ("Movement   y u / h j k l / b n   or arrows, WASD, numpad",
                "Движение   y u / h j k l / b n   или стрелки, WASD, numpad"),
    "help.2":  ("           . or space   wait one turn",
                "           . или пробел   ждать ход"),
    "help.3":  ("Actions    g pick up     , pick up all    p items here",
                "Действия  g взять     , взять всё     p предметы здесь"),
    "help.4":  ("           i inventory    d drop           c character sheet",
                "           i инвентарь    d выбросить      c лист персонажа"),
    "help.5":  ("           Shift+F  force fight an adjacent enemy",
                "           Shift+F  ударить соседнего врага"),
    "help.6":  ("Stairs     > descend      < climb up       (stand on the stairs)",
                "Лестница  > вниз          < наверх          (встаньте на лестницу)"),
    "help.7":  ("Doors      walk into to open,   Shift+P  pick a nearby lock",
                "Двери     войдите чтобы открыть,   Shift+P  вскрыть замок"),
    "help.8":  ("Items      e eat    q quaff   r read    w wield   Shift+W wear",
                "Вещи      e съесть  q выпить  r прочесть  w в руки  Shift+W надеть"),
    "help.9":  ("           Shift+T take off   f fire    z activate     t throw",
                "           Shift+T снять      f выстрел  z артефакт  t бросить"),
     "help.10": ("Light      l toggle the light in every room",
                 "Свет      l включить/выключить свет во всех комнатах"),
     "help.rotate": ("View       [ ] rotate the ASCII camera (mouse wheel also works)",
                     "Обзор     [ ] повернуть ASCII-камеру (также колесо мыши)"),
    "help.11": ("Map        m or o  memorize the whole level",
                "Карта     m  запомнить весь уровень"),
    "help.12": ("System     Shift+S save and quit    s save      Esc cancel",
                "Система   Shift+S сохранить и выйти    s сохранить   Esc отмена"),
    "help.13": ("Other      ? help       Ctrl+Q quit",
                "Прочее     ? справка     F2 настройки   Ctrl+Q выход"),
    "help.14": ("Legend     @ you     > stairs down    < stairs up    + door",
                "Обозначения @ вы    > вниз    < наверх    + дверь"),
    "help.15": ("           Entity roster is empty at this stage.",
                "           На этом этапе список сущностей пуст."),
    "help.16": ("           : rubble   ~ water   ≈ fountain",
                "           : обломки   ~ вода   ≈ фонтан"),
    "help.17": ("           ! bottle  ? document  / artifact  = ring  ) weapon  [ armor  $ gold",
                "           ! бутылка  ? документ  / артефакт  = кольцо  ) оружие  [ броня"),
    "help.18": ("Dark rooms are barely lit. Press l if you need to see.",
                "Тёмные комнаты почти не освещены. Нажмите l, если нужно видеть."),
    "help.19": ("Goal: reach the bottom of the dungeon - level {m}.",
                "Цель: дойти до самого дна подземелья - уровень {m}."),

    # --- прочее ----------------------------------------------------------
    "title.subtitle":   ("a primitive descent", "примитивное нисхождение"),
    "title.footer":     ("arrows/WASD to move - ? for help - Ctrl+Q to quit",
                         "стрелки/WASD - движение, ? - справка, Ctrl+Q - выход"),
    "error.hint":       ("[ any key ]", "[ любая клавиша ]"),

    # --- мышь и быстрые действия -------------------------------------------
    "mouse.title":      ("Click travel / right-click look",
                         "ЛКМ - идти, ПКМ - осмотреть"),
    "mouse.can_hit":    ("you can hit it now", "можно ударить прямо сейчас"),
    "mouse.far":        ("too far - walk there first",
                         "далеко - сначала подойдите"),
    "mouse.blocked":    ("no way there from here", "туда нет пути"),
    "mouse.hover_hint": ("hover - look   click - walk / attack   right-click - details",
                         "наведение - осмотр   ЛКМ - идти/бить   ПКМ - подробно"),
    "mouse.menu_hint":  ("click - select   click again - confirm   wheel - scroll",
                         "клик - выбор   повторный клик - подтвердить   колесо - прокрутка"),
    "quick.hint":       ("q drink   e eat   r read   z activate   x wield   W wear   "
                         "T take off   d drop   i info   1-9 select",
                         "q выпить   e съесть   r прочесть   z артефакт   x в руки   "
                         "W надеть   T снять   d выбросить   i инфо   1-9 выбор"),
    "error.screen":     ("GAME ERROR", "ОШИБКА ИГРЫ"),
    "error.log":        ("crash.log written to the game folder",
                         "лог падения записан в папку игры"),
}


# ---------------------------------------------------------------------------
# Имена предметов и монстров
# ---------------------------------------------------------------------------
ITEM_NAMES = {
    'cardboard': ('cardboard','картон'),
    'scrap metal': ('scrap metal','металлолом'), 'cord': ('cord','шнур'),
    'fuel': ('fuel portion','порция топлива'), 'potato': ('potato','картофель'),
    'salt': ('salt','соль'), 'cooking pot': ('cooking pot','котелок'),
    'lighter': ('lighter','зажигалка'), 'improvised spear': ('improvised spear','самодельное копьё'),
    'nailed club': ('nailed club','дубинка с гвоздями'),
    'vegetable soup': ('vegetable soup','овощной суп'), 'trail mix': ('trail mix','походная смесь'),
    'wood plank': ('wood plank','деревянная доска'),
    'nails': ('nails','гвозди'),
    'rag': ('rag','тряпка'),
    'thread': ('thread','нитки'),
    'needle': ('needle','игла'),
    'crafted jacket': ('handmade jacket','самодельная куртка'),
    "dagger": ("utility knife", "хозяйственный нож"),
    "short sword": ("machete", "мачете"),
    "long sword": ("crowbar", "лом"),
    "axe": ("axe", "топор"),
    "mace": ("pipe wrench", "трубный ключ"),
    "war hammer": ("hammer", "молоток"),
    "quarterstaff": ("wooden pole", "деревянный шест"),
    "staff": ("metal pipe", "металлическая труба"),
    "spear": ("sharpened rod", "заточенный прут"),
    "orcish axe": ("fire axe", "пожарный топор"),
    "bow": ("bow", "лук"),
    "crossbow": ("crossbow", "арбалет"),
    "leather armor": ("leather jacket", "кожаная куртка"),
    "studded leather": ("reinforced jacket", "усиленная куртка"),
    "ring mail": ("protective vest", "защитный жилет"),
    "scale mail": ("ballistic vest", "бронежилет"),
    "chain mail": ("heavy ballistic vest", "тяжёлый бронежилет"),
    "orcish helm": ("military helm", "военный шлем"),
    "wooden shield": ("plywood shield", "фанерный щит"),
    "cloak": ("raincoat", "плащ-дождевик"),
    "arrow": ("arrow", "стрела"),
    "crossbow bolt": ("crossbow bolt", "болт арбалета"),
    "potion of healing": ("almond water", "миндальная вода"),
    "potion of extra healing": ("concentrated almond water", "концентрированная миндальная вода"),
    "potion of full healing": ("purified almond water", "очищенная миндальная вода"),
    "potion of gain level": ("bottled memory extract", "бутылка экстракта воспоминаний"),
    "potion of strength": ("bottled stimulant", "бутылка стимулятора"),
    "potion of poison": ("liquid pain", "жидкая боль"),
    "potion of acid": ("bottled corrosive liquid", "бутылка едкой жидкости"),
    "potion of confusion": ("bottled cloudy liquid", "бутылка мутной жидкости"),
    "potion of hallucination": ("bottled iridescent liquid", "бутылка переливающейся жидкости"),
    "potion of booze": ("bottled alcohol", "бутылка алкоголя"),
    "potion of sleeping": ("bottled sedative", "бутылка снотворного"),
    "water": ("bottled water", "бутылка воды"),
    "distilled water": ("bottled distilled water", "бутылка дистиллированной воды"),
    "salt water": ("bottled salt water", "бутылка солёной воды"),
    "stagnant water": ("bottled stagnant water", "бутылка застоявшейся воды"),
    "noclip guide": ("noclip field guide", "полевое руководство по ноуклипу"),
    "scroll of identify": ("object identification document", "документ об идентификации предметов"),
    "scroll of mapping": ("area plan", "план местности"),
    "scroll of magic mapping": ("flickering floor plan", "мерцающий план этажа"),
    "scroll of teleport": ("displacement instructions", "инструкция по перемещению"),
    "scroll of aggravate monster": ("entity provocation report", "доклад о провокации сущностей"),
    "scroll of amnesia": ("redacted memory document", "документ с вымаранными воспоминаниями"),
    "scroll of destroy armor": ("equipment decay report", "отчёт о распаде снаряжения"),
    "scroll of fire": ("smoldering paper", "тлеющая бумага"),
    "scroll of scare monster": ("entity deterrence instructions", "инструкция по отпугиванию сущностей"),
    "scroll of charging": ("artifact charging instructions", "инструкция по зарядке артефактов"),
    "scroll of luck": ("flickering paper", "мерцающая бумага"),
    "scroll of nothing": ("blank paper", "чистый лист бумаги"),
    "wand of light": ("light artifact", "артефакт света"),
    "wand of dig": ("excavation artifact", "артефакт прохода"),
    "wand of striking": ("impact artifact", "артефакт удара"),
    "wand of fire": ("heat artifact", "артефакт жара"),
    "wand of cold": ("frost artifact", "артефакт холода"),
    "wand of sleep": ("sleep artifact", "артефакт сна"),
    "wand of lightning": ("discharge artifact", "артефакт разряда"),
    "wand of nothing": ("inert artifact", "инертный артефакт"),
    "ring of strength": ("orange anomalous ring", "оранжевое аномальное кольцо"),
    "ring of dexterity": ("green anomalous ring", "зелёное аномальное кольцо"),
    "ring of protection": ("cyan anomalous ring", "бирюзовое аномальное кольцо"),
    "ring of constitution": ("pink anomalous ring", "розовое аномальное кольцо"),
    "ring of damage": ("red anomalous ring", "красное аномальное кольцо"),
    "ring of hunger": ("dark green anomalous ring", "тёмно-зелёное аномальное кольцо"),
    "food ration": ("food ration", "рацион"),
    "tripe ration": ("canned meat", "мясные консервы"),
    "apple": ("apple", "яблоко"),
    "crackers": ("crackers", "сухари"),
    "salted nuts": ("salted nuts", "солёные орешки"),
    "chocolate": ("chocolate", "шоколад"),
    "cucumber": ("cucumber", "огурец"),
    "carrot": ("carrot", "морковь"),
    "fried potatoes": ("fried potatoes", "жареная картошка"),
    "borscht": ("bowl of borscht", "тарелка борща"),
    "gold piece": ("gold piece", "золотая монета"),
    "pick-axe": ("pick-axe", "кирка"),
    "lantern": ("lantern", "фонарь"),
}

MONSTER_NAMES = {}
MONSTER_NAMES.update({
    "the thing": ("The Thing", "Существо"),
    "mortisdoptera swarm": ("Mortisdoptera swarm", "Рой мортиздоптер"),
    "the observer": ("The Observer", "Наблюдатель"),
    "burrowing worm": ("Burrowing worm", "Подземный червь"),
})


try:
    from .items import ITEMS as _ITEM_REGISTRY
    for _key in _ITEM_REGISTRY:
        ITEM_NAMES.setdefault(_key, (_key, _key))
except (ImportError, AttributeError):
    pass


def item_name(key: str) -> str:
    from .equipment_catalog import NAMES
    if key in NAMES:
        return NAMES[key][0 if _current == 'en' else 1]
    entry = ITEM_NAMES.get(key)
    if entry is None:
        return key
    return entry[0] if _current == "en" else entry[1]


def monster_name(key: str) -> str:
    entry = MONSTER_NAMES.get(key)
    if entry is None:
        return key
    return entry[0] if _current == "en" else entry[1]


def kind_name(kind: str) -> str:
    return t("kind." + kind)


# ---------------------------------------------------------------------------
# Сохранение настроек
# ---------------------------------------------------------------------------
SETTINGS_PATH = os.path.join(C.SAVE_DIR, "settings.json")


def load_settings(obj=None):
    data = {}
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {}
    set_lang(data.get("lang", "en"))
    if obj is not None:
        obj.audio.muted = not data.get("sound", True)
        obj.sleep_setting = max(10,min(360,int(data.get('sleep_turns',120))))
        obj.audio.set_volume(data.get("volume", 0.45))
        obj.audio.music_volume=max(0,min(1,float(data.get('music_volume',.55))))
        obj.audio.effects_volume=max(0,min(1,float(data.get('effects_volume',1))))
        obj.audio.ui_volume=max(0,min(1,float(data.get('ui_volume',1))))
        obj.audio.environment_volume=max(0,min(1,float(data.get('environment_volume',1))))
        obj.audio.alarm_volume=max(0,min(1,float(data.get('alarm_volume',1))))
        obj.audio.set_volume(obj.audio.volume)
        obj.window_scale = int(data.get("window_scale", 1))
        obj.fullscreen = bool(data.get("fullscreen", False))
        obj.presentation_backend = data.get("backend", "software")
        display = getattr(obj, "display", None)
        if display is not None:
            display.backend = data.get("backend", "software")
            display.adapter = data.get("adapter", "auto")
        obj.sidebar_visible = bool(data.get('sidebar_visible', False))
        size = data.get("resolution", [1280, 720])
        if isinstance(size, list) and len(size) == 2 and all(isinstance(n, int) for n in size):
            obj.resolution = (max(680, min(2560, size[0])), max(240, min(1440, size[1])))
        from engine import window as _window
        obj.window_mode = _window.normalize_mode(
            data.get("window_mode", getattr(obj, "window_mode", "auto")), "auto")
        if hasattr(obj, "views"):
            graphics = data.get("graphics", {})
            if isinstance(graphics, dict):
                for key in ("lighting", "fog", "outlines", "full_map", "single_layer"):
                    if isinstance(graphics.get(key), bool):
                        setattr(obj.views, key, graphics[key])
                if isinstance(graphics.get('show_ceiling'), bool):
                    obj.views.show_ceiling = graphics['show_ceiling']
                if isinstance(graphics.get('pitch'), (int, float)):
                    obj.views.pitch = max(-1.0, min(1.0, float(graphics['pitch'])))
                if graphics.get('draw_distance') in (13, 52):
                    obj.views.draw_distance = graphics['draw_distance']
                if isinstance(graphics.get('skybox'), list) and len(graphics['skybox']) == 3:
                    obj.views.skybox = tuple(int(max(0, min(255, n))) for n in graphics['skybox'])
                if graphics.get("mode") in ("ascii", "first", "board"):
                    obj.views.mode = graphics["mode"]
                if graphics.get("quality") in (0, 1, 2):
                    obj.views.quality = graphics["quality"]
        if hasattr(obj, "r"):
            tiles = data.get("tileset", {})
            if isinstance(tiles, dict):
                obj.r.tileset.configure(tiles.get("enabled", False),
                                        tiles.get("auto_color", True),
                                        tiles.get("tile_size", 32),
                                        tiles.get("mod", "default"))
                obj.r._visual_cache.clear()
        keys = data.get("keys")
        if hasattr(obj, "ctl"):
            obj.ctl.load_profiles(data)
    return data


def save_settings(obj=None):
    data = {"lang": _current}
    if obj is not None:
        data["sound"] = not obj.audio.muted
        data['sleep_turns'] = getattr(obj,'sleep_setting',120)
        data["volume"] = obj.audio.volume
        data['music_volume']=obj.audio.music_volume
        data['effects_volume']=obj.audio.effects_volume
        data['ui_volume']=obj.audio.ui_volume
        data['environment_volume']=obj.audio.environment_volume
        data['alarm_volume']=obj.audio.alarm_volume
        data["window_scale"] = getattr(obj, "window_scale", 1)
        data["fullscreen"] = getattr(obj, "fullscreen", False)
        if getattr(obj, "display", None) is not None:
            data["backend"] = obj.display.backend
            data["adapter"] = obj.display.adapter
        else:
            data["backend"] = getattr(obj, "presentation_backend", "software")
        data['sidebar_visible'] = getattr(obj, 'sidebar_visible', False)
        data["resolution"] = list(getattr(obj, "resolution", (1280, 720)))
        data["window_mode"] = getattr(obj, "window_mode", "auto")
        if hasattr(obj, "views"):
            data["graphics"] = {key: getattr(obj.views, key) for key in
                                 ("mode", "quality", "lighting", "fog", "outlines", "full_map", "show_ceiling", "single_layer")}
            data['graphics']['draw_distance'] = obj.views.draw_distance
            data['graphics']['pitch'] = float(obj.views.pitch)
        if hasattr(obj, "r"):
            ts = obj.r.tileset
            data["tileset"] = {"enabled": ts.enabled, "auto_color": ts.auto_color,
                                "tile_size": ts.tile_size, "mod": ts.mod_name}
        if hasattr(obj, "ctl"):
            data["keys"] = obj.ctl.save()
            data["control_preset"] = obj.ctl.preset
            data["control_profiles"] = obj.ctl.save_profiles()
    try:
        os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
    except OSError:
        pass
    return data
