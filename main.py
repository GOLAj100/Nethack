"""NET HACK - точка входа.

Запуск:  python main.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pygame

from engine import config as C
from engine.renderer import Renderer
from game.app import Game


def make_window():
    """Создаёт окно нужного размера (в ячейках символьной сетки)."""
    probe = pygame.display.set_mode((64, 64))
    r = Renderer(probe)
    cols = C.CAMERA_W + C.SIDEBAR_W
    rows = C.TOPBAR_H + C.CAMERA_H + C.LOG_H
    size = (cols * r.cw, rows * r.ch)
    screen = pygame.display.set_mode(size)
    screen.fill(C.BLACK)
    r.surface = screen
    return r


def main():
    pygame.init()
    pygame.display.set_caption(C.TITLE)
    r = make_window()
    game = Game(r)
    game.resize_window()
    try:
        game.run()
    finally:
        if game.display:
            game.display.close()
        pygame.quit()


if __name__ == "__main__":
    main()
