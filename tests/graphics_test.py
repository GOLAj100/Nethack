"""Headless graphics integration checks; does not alter user saves/settings."""
import os
import sys
import tempfile
import math
from unittest.mock import patch

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame
from main import make_window
from game.app import Game
from game import lang
from game.items import Item
from engine.display import RESOLUTIONS
from engine import config as C

pygame.init()
with tempfile.TemporaryDirectory() as tmp, patch.object(lang, "SETTINGS_PATH", os.path.join(tmp, "settings.json")):
    game = Game(make_window(), seed=42)
    game.new_game()
    game.resize_window()
    canvas_size = game.r.surface.get_size()
    game.views.pitch = 0.63
    lang.save_settings(game)
    restored_pitch = Game(make_window(), seed=7)
    assert abs(restored_pitch.views.pitch - 0.63) < 1e-6
    for size in RESOLUTIONS:
        game.resolution = size
        game.resize_window()
        game.draw()
        game.display.present()
        assert pygame.display.get_surface().get_size() == size
        from engine.display import Display
        expected_canvas = (min(size[0], Display.CANVAS_MAX[0]),
                           min(size[1], Display.CANVAS_MAX[1]))
        assert game.r.surface.get_size() == expected_canvas
        rect = game.display.rect
        assert rect.size == size
        mapped = game.display.position(rect.center)
        canvas_w, canvas_h = game.r.surface.get_size()
        assert abs(mapped[0] - canvas_w / 2) <= 2
        assert abs(mapped[1] - canvas_h / 2) <= 2
    game.toggle_fullscreen()
    game.draw()
    game.display.present()
    game.toggle_fullscreen()
    before = game.player.turns
    for mode in ("ascii", "first", "board"):
        game.views.mode = mode
        for angle in (0, math.pi/2, math.pi, math.pi*1.5):
            game.views.yaw = game.views.orbit = angle
            for tilt in (-1.57, -0.6, 0.6, 1.57):
                game.views.tilt = tilt
                game.draw()
        assert game.player.turns == before
    p = game.player
    game.level.items[(p.x, p.y)] = Item("apple")
    game.views.mode = "board"
    game.draw()
    rect, pos = game.views.picks[-1]
    assert pos == (p.x, p.y)
    game.on_mouse(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=rect.center, button=3))
    assert game.tooltip and any("apple" in text for text, _ in game.tooltip["lines"])
    game.draw()
    # Inverse window mapping must reach the real event loop, not just helpers.
    game.views.mode = "ascii"
    game.draw()
    sx, sy = game.world_to_screen(p.x, p.y)
    canvas_now = game.r.surface.get_size()
    logical = ((sx+0.5)*game.r.cw, (sy+game.map_offset_y+0.5)*game.r.ch)
    area = game.display.rect
    pixel = (int(area.x + logical[0]*area.w/canvas_now[0]),
             int(area.y + logical[1]*area.h/canvas_now[1]))
    pygame.event.clear()
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pixel, button=3))
    game.handle_events()
    assert (game.tooltip["x"], game.tooltip["y"]) == (p.x, p.y)
    # A sprite in front of a wall is pickable; behind it is fully occluded.
    lv = game.level
    p.x, p.y = 5, 5
    lv.monsters.clear()
    lv.items.clear()
    for y in range(lv.h):
        for x in range(lv.w):
            lv.set(x, y, 0 if x in (0, 8, lv.w-1) or y in (0, lv.h-1) else 1)
    lv.doors.clear()
    lv.items[(7, 5)] = Item("apple")
    lv.visible = {(7, 5), (9, 5)}
    game.views.mode, game.views.yaw = "first", 0
    game.draw()
    assert any(pos == (7, 5) for _, pos in game.views.picks)
    lv.items = {(9, 5): Item("apple")}
    game.draw()
    assert not any(pos == (9, 5) for _, pos in game.views.picks)
    with patch.object(game, "step_to") as step:
        game.move(0, -1)
        step.assert_called_once_with(6, 5)
    game.resolution = (1920, 1080)
    game.window_mode = "fixed"
    game.views.mode = "board"
    game.views.quality = 0
    game.views.fog = False
    lang.save_settings(game)
    restored = Game(make_window(), seed=7)
    assert restored.resolution == (1920, 1080)
    assert restored.views.mode == "board" and not restored.views.fog and restored.views.quality == 0
pygame.quit()
print("GRAPHICS OK: resolutions, fullscreen, all cameras, below-board view, picking, persistence")
