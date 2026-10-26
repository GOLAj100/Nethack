"""Глобальная конфигурация игры: пути, размеры, палитра, настройки баланса."""

from __future__ import annotations

import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOUND_DIR = os.path.join(BASE_DIR, "sound")
SAVE_DIR = os.path.join(BASE_DIR, "save")
SAVE_PATH = os.path.join(SAVE_DIR, "slot1.json")

TITLE = "NET HACK"
SUBTITLE = "a primitive descent"

# --- Окно и шрифт -------------------------------------------------------
FONT_SIZE = 18
FONT_CANDIDATES = ("consolas", "cascadiamono", "couriernew", "lucida console")
USE_OPENGL = True  # Stage 2: Full GPU render

# --- Размеры мира и вьюпорта -------------------------------------------
MAP_W = 80
MAP_H = 50
CAMERA_W = 50
CAMERA_H = 30

TOPBAR_H = 2          # здоровье/питание и уровневый запас
SIDEBAR_W = 30        # панель справа
LOG_H = 6             # строк снизу: сообщения + строка подсказки
STATUS_H = 16         # высота блока статуса в сайдбаре
MINIMAP_W = 20
MINIMAP_H = 11

# --- Поле зрения --------------------------------------------------------
FOV_RADIUS = 13

# --- Правила ------------------------------------------------------------
MAX_LEVEL = 30
DESCEND_XP = 20           # опыта за спуск

# --- Палитра ------------------------------------------------------------
BLACK = (10, 8, 14)
WHITE = (222, 222, 234)
LIGHT_GRAY = (156, 156, 172)
GRAY = (104, 104, 122)
DARK_GRAY = (62, 62, 76)
RED = (204, 62, 62)
DARK_RED = (128, 34, 34)
GREEN = (86, 186, 96)
DARK_GREEN = (38, 96, 52)
BLUE = (78, 124, 204)
CYAN = (86, 186, 194)
YELLOW = (222, 190, 78)
ORANGE = (216, 130, 56)
PURPLE = (156, 92, 200)
BROWN = (140, 96, 56)
DARK_BROWN = (86, 60, 36)
PINK = (216, 140, 176)

# цвета тулов
C_WALL = (96, 92, 128)
C_WALL_DARK = (68, 64, 96)
C_WALL_EDGE = (132, 128, 168)
C_FLOOR = (78, 74, 104)
C_FLOOR_ALT = (92, 88, 120)
C_CORRIDOR = (64, 60, 88)
C_DOOR = (168, 130, 70)
C_STAIR = (222, 190, 78)
C_GRASS = (66, 130, 78)

HP_BAR = (188, 54, 54)
HP_BAR_BG = (52, 22, 26)

MSG_FILL = "█"
MSG_EMPTY = "░"

# Сообщения по приоритету
MSG_INFO = WHITE
MSG_GOOD = GREEN
MSG_BAD = RED
MSG_WARN = YELLOW
MSG_HINT = GRAY
