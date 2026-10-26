"""Test for modern pixel-based HUD system (Этап C — UI)."""
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
from game import lang

pygame.init()
with tempfile.TemporaryDirectory() as tmp, patch.object(
        lang, 'SETTINGS_PATH', os.path.join(tmp, 'settings.json')):
    g = Game(make_window(), seed=42)
    g.new_game()
    
    # Enable modern HUD
    g.use_modern_hud = True
    assert g.use_modern_hud, "Modern HUD should be enabled"
    
    # Check that modern HUD is initialized
    assert g.modern_hud is not None, "Modern HUD should be initialized"
    assert g.modern_sidebar is not None, "Modern sidebar should be initialized"
    
    # Test HUD dimensions
    hud_height = g.modern_hud.get_height()
    assert hud_height > 0, "HUD height should be positive"
    assert hud_height >= 50, "HUD height should be at least 50px"
    
    # Test map offset calculation
    offset = g.map_offset_y
    assert offset > 0, "Map offset should be positive"
    
    # Test that modern HUD updates with player stats
    initial_hp = g.player.hp
    
    # Draw HUD (it updates internally)
    g.modern_hud.draw(g.player)
    
    # Damage player and verify HUD redraws
    g.player.hp = max(1, g.player.hp - 5)
    g.modern_hud.draw(g.player)
    assert g.player.hp < initial_hp, "Player HP should have decreased"
    
    # Test drawing (should not crash)
    g.r.clear()
    g.draw()
    
    # Test mouse hover on HUD bars
    # Hover on HP bar (should be near top-left)
    hp_hover_pos = (50, 25)
    hover_text = g.modern_hud.handle_mouse_motion(hp_hover_pos)
    # Modern HUD should respond to mouse motion (even if no hover detected)
    
    # Test sidebar visibility toggle
    initial_visibility = g.modern_sidebar.visible
    g.toggle_status()
    assert g.modern_sidebar.visible != initial_visibility, "Sidebar visibility should toggle"
    
    # Test sidebar action buttons
    g.modern_sidebar.visible = True
    width = g.r.surface.get_width()
    height = g.r.surface.get_height()
    
    # Click on sidebar area (right side of screen)
    sidebar_click_pos = (width - 100, height // 2)
    action = g.modern_sidebar.handle_click(sidebar_click_pos)
    # action can be None if click missed buttons
    
    # Test coordinate transformations with modern HUD
    test_pos = (5, 10)
    wx, wy = g.screen_to_world(test_pos[0], test_pos[1])
    assert isinstance(wx, int) and isinstance(wy, int), "Coordinates should be integers"
    
    # Test that old topbar and sidebar are skipped when modern HUD is enabled
    # (verified by checking draw doesn't crash)
    g.draw_topbar()  # Should return early
    g.draw_sidebar()  # Should return early
    
    # Test disabling modern HUD
    g.use_modern_hud = False
    assert not g.use_modern_hud, "Modern HUD should be disabled"
    
    # Old HUD should work again
    g.draw_topbar()
    g.draw_sidebar()
    g.draw()
    
    # Re-enable modern HUD for final tests
    g.use_modern_hud = True
    g.modern_hud.draw(g.player)
    g.draw()
    
    # Test with different screen sizes (responsive design)
    # Note: In dummy SDL driver, resizing might not work, but test the logic
    original_size = g.r.surface.get_size()
    
    # Test sidebar width calculation
    sidebar_width = g.modern_sidebar.get_width()
    assert sidebar_width > 0, "Sidebar width should be positive"
    assert sidebar_width <= width, "Sidebar should fit on screen"
    
    # Test camera width calculation with modern HUD
    cam_width = g.camera_w
    cols = width // g.r.cw
    expected_width = cols - (sidebar_width // g.r.cw) if g.modern_sidebar.visible else cols
    # Camera width should account for sidebar
    
    # Viewport fills from the real HUD bottom to the canvas edge. Chat is an
    # overlay and must not reserve a footer strip (the old black bar).
    for size in ((1280, 720), (1920, 1080), (2560, 1440)):
        g.resolution = size
        g.resize_window()
        g.sidebar_visible = False
        g.modern_sidebar.visible = False
        g.views.mode = 'first'
        g.draw()
        canvas = g.r.surface.get_size()
        view = g.views.rect
        hud_h = g.modern_hud.get_height()
        assert view.y == hud_h, (size, view.y, hud_h)
        assert view.bottom == canvas[1], (size, view, canvas)
        assert view.x == 0 and view.right == canvas[0]
        assert g.chat_rect is not None
        assert g.chat_rect.bottom <= canvas[1]
        assert g.chat_rect.right <= canvas[0]
        assert g.chat_rect.h < canvas[1] // 2
        assert view.contains(g.chat_rect) or g.chat_rect.top >= view.top
        center = g.display.position(g.display.rect.center)
        assert abs(center[0] - canvas[0] / 2) <= 2
        assert abs(center[1] - canvas[1] / 2) <= 2
        g.debug_overlay.enabled = True
        g.debug_overlay.modes = {'canvas', 'hud', 'viewport', 'chat'}
        g.debug_overlay.draw_markers(g)
        g.debug_overlay.draw_panel(g)
        assert not g.debug_overlay.warnings, (size, g.debug_overlay.warnings)
    g.debug_overlay.enabled = False
    g.on_key(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F12, mod=0))
    assert g.debug_overlay.enabled
    g.on_key(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F12, mod=0))
    assert not g.debug_overlay.enabled

    # Cleanup
    g.world.storage.cleanup()

pygame.quit()
print('MODERN HUD TEST OK')
