"""Deterministic before/after render benchmark (no saves or user settings)."""
import os
import sys
import statistics
import time
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame
from engine.renderer import Renderer
from game.app import Game


def run():
    pygame.init()
    with patch('game.app.load_settings'), patch('game.app.Audio'):
        game = Game(Renderer(pygame.Surface((1280, 720))), seed=123)
    game.resolution = (1280, 720)
    game.resize_window()
    game.new_game()
    game.views.mode = 'first'
    game.views.quality = 0
    try:
        for backend in ('opengl', 'software'):
            game.display.configure(game.resolution, backend=backend)
            game.views.invalidate()
            for rotating in (False, True):
                samples = []
                for repeat in range(3):
                    game.views.yaw = -1.57
                    for i in range(40):
                        if rotating:
                            game.views.yaw += .04
                        start = time.perf_counter()
                        game.draw()
                        game.display.present()
                        elapsed = time.perf_counter() - start
                        if i >= 10:
                            samples.append(elapsed)
                ms = statistics.median(samples) * 1000
                print(f'{backend} {"rotation" if rotating else "static"}: {ms:.3f} ms, {1000/ms:.1f} FPS')
    finally:
        game.display.close()
        game.world.storage.cleanup()
        pygame.quit()


if __name__ == '__main__':
    run()
