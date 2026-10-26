"""Radial input, full-width views, layout persistence and walking stamina cadence."""
import math
import os
import sys
import tempfile
from unittest.mock import patch

os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame
from main import make_window
from engine import config as C
from game.app import Game
from game import lang, survival as S
from game.entities import Player
from game.items import Item

p = Player()
for i in range(1, 31):
    S.movement(p)
    assert p.stamina == 50 - i // 10

pygame.init()
with tempfile.TemporaryDirectory() as tmp, patch.object(
        lang, 'SETTINGS_PATH', os.path.join(tmp, 'settings.json')):
    g = Game(make_window(), seed=44)
    g.new_game()

    def key(code, mod=0):
        g.on_key(pygame.event.Event(pygame.KEYDOWN, key=code, mod=mod))

    cols = g.r.surface.get_width() // g.r.cw
    assert not g.sidebar_visible and g.camera_w == cols
    turns = g.player.turns
    key(pygame.K_TAB)
    assert g.mode == 'action_wheel' and g.player.turns == turns
    g.draw()
    wheel = g.action_wheel
    for index in range(9):
        angle = -math.pi / 2 + index * 2 * math.pi / 9
        pos = (wheel.center[0] + math.cos(angle) * wheel.radius * 0.7,
               wheel.center[1] + math.sin(angle) * wheel.radius * 0.7)
        assert wheel.pick(pos) == index
    assert wheel.pick(wheel.center) is None
    key(pygame.K_ESCAPE)
    assert g.mode == 'play' and g.player.turns == turns
    g.views.mode = 'board'
    key(pygame.K_LALT)
    assert g.mode == 'play' and g.alt_camera
    before_camera = g.views.orbit
    g.on_mouse(pygame.event.Event(pygame.MOUSEMOTION, pos=(100, 100), rel=(20, 0), buttons=(0, 0, 0)))
    assert g.views.orbit != before_camera
    g.on_key(pygame.event.Event(pygame.KEYUP, key=pygame.K_LALT, mod=0))
    assert not g.alt_camera
    g.views.mode = 'ascii'
    g.player.items = [Item('apple')]
    key(pygame.K_TAB)
    key(pygame.K_2)
    assert g.mode == 'modal' and g.menu is not None
    cb = g.menu_cb
    g.close_modal()
    cb(0)
    assert not g.player.items and g.player.turns == turns + 1
    turns = g.player.turns
    key(pygame.K_TAB)
    key(pygame.K_4)
    assert g.mode == 'modal' and len(g.menu.entries) == 6
    g.close_modal()
    key(pygame.K_TAB)
    key(pygame.K_7)
    assert g.mode == 'modal' and g.modal_lines
    assert g.player.turns == turns
    g.close_modal()
    # Mouse selection of the top sector opens inventory; outside clicks do nothing.
    g.player.items.append(Item('apple'))
    g.on_mouse(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(1, 1), button=2))
    assert g.mode == 'play'  # MMB belongs to the 3D/first-person camera.
    key(pygame.K_TAB)
    assert g.mode == 'action_wheel'
    wheel = g.action_wheel
    pos = (wheel.center[0], int(wheel.center[1] - wheel.radius * 0.7))
    g.on_mouse(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(1, 1), button=1))
    assert g.mode == 'action_wheel'
    g.on_mouse(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1))
    assert g.mode == 'inventory' and g.inventory_panel is not None
    g.inventory_panel = None
    g.mode = 'play'
    # No minimap is drawn; toggling status changes view width and survives settings load.
    key(pygame.K_F10)
    assert g.sidebar_visible
    assert g.camera_w < cols
    with patch.object(g, 'draw_minimap') as minimap:
        g.draw()
        minimap.assert_not_called()
    restored = Game(make_window(), seed=44)
    assert restored.sidebar_visible
    for mode in ('ascii', 'first', 'board'):
        g.views.mode = mode
        for visible in (True, False):
            g.sidebar_visible = visible
            g.draw()
            if mode != 'ascii':
                assert g.views.rect.bottom == g.r.surface.get_height()
                assert g.views.rect.w <= g.r.surface.get_width()
            if mode == 'ascii':
                for rotation in range(4):
                    g.view_rotation = rotation
                    pos = g.world_to_screen(g.player.x, g.player.y)
                    assert g.screen_to_world(*pos) == (g.player.x, g.player.y)
    g.views.mode = 'ascii'
    g.view_rotation = 0
    # Two ordinary direction keys can form diagonals; dedicated diagonal keys are optional.
    with patch('pygame.key.get_pressed', return_value={pygame.K_d: True}):
        # Use a defaultdict-like mapping for unpressed keys.
        from collections import defaultdict
        with patch('pygame.key.get_pressed', return_value=defaultdict(bool, {pygame.K_d: True})), \
                patch.object(g, 'move') as move:
            key(pygame.K_w)
            move.assert_called_once_with(1, -1, running=False)
    # Interaction picks up current tile items; opening an empty-tile wheel costs no turn.
    g.level.items[g.player.x, g.player.y] = Item('apple')
    before = g.player.turns
    key(pygame.K_RETURN)
    assert g.player.items and g.player.turns == before + 1
    key(pygame.K_RETURN)
    assert g.mode == 'action_wheel' and g.player.turns == before + 1
    g.close_action_wheel()
    g.player.status['asleep'] = 3
    before = g.player.turns
    key(pygame.K_TAB)
    key(pygame.K_2)
    assert g.mode == 'play' and g.player.turns == before + 1
    g.world.storage.cleanup()
pygame.quit()
print('MODERN UI OK')
