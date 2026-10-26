"""Real-context rendering regressions. Run: python -m unittest tests.gl_pipeline_test -v"""
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import pygame
from OpenGL import GL

from engine.display import Display
from engine.renderer import Renderer
from engine.gl_compositor import GLCompositor
from engine.gl_sprite_atlas import SpriteAtlas
from engine.modern_hud import ModernHUD, ModernSidebar


class GLPipelineTest(unittest.TestCase):
    def setUp(self):
        pygame.init()
        self.base = Renderer(pygame.Surface((640, 480)))
        self.display = Display(self.base)
        self.display.configure((640, 480), backend='opengl')
        self.r = self.display.gl_renderer
        self.assertIsNotNone(self.r, self.display.error)
        self.base.gl_renderer = self.r

    def tearDown(self):
        self.display.close()
        pygame.quit()

    def pixel(self, x, y):
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, self.r.fbo)
        data = GL.glReadPixels(x, self.r.surface.get_height()-y-1, 1, 1,
                               GL.GL_RGBA, GL.GL_UNSIGNED_BYTE)
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, 0)
        return tuple(bytes(data))

    def test_sprite_colors_orientation_order_and_cache(self):
        image = pygame.Surface((8, 8), pygame.SRCALPHA)
        image.fill((255, 0, 0), (0, 0, 8, 4))
        image.fill((0, 0, 255), (0, 4, 8, 4))
        for frame in range(2):
            self.r.begin()
            self.r.clear((0, 0, 0))
            with patch.object(self.base, 'visual', return_value=image) as visual:
                self.r.draw_visual((20, 20), '@', (255, 255, 255), size=(8, 8))
                self.assertEqual(visual.call_count, int(frame == 0))
            self.r.draw_rect((24, 20, 4, 8), (0, 255, 0))
            self.r.end()
            self.assertEqual(self.pixel(21, 21)[:3], (255, 0, 0))
            self.assertEqual(self.pixel(21, 26)[:3], (0, 0, 255))
            self.assertEqual(self.pixel(26, 21)[:3], (0, 255, 0))

    def test_compositor_restores_target_and_ui_is_on_top(self):
        from engine.gl_renderer import GLRenderer
        scene = GLRenderer(self.base, self.display)
        try:
            self.r.begin()
            self.r.clear((0, 0, 0))
            index = len(self.r.batch.quads)
            scene.begin()
            scene.clear((255, 0, 0))
            scene.draw_rect((0, 240, 640, 240), (0, 0, 255))
            scene.end()
            GLCompositor.compose(self.r, (scene.fbo_texture, pygame.Rect(10, 10, 100, 100)), index)
            self.r.draw_rect((30, 30, 20, 20), (0, 255, 0, 128))
            GL.glViewport(0, 0, 4, 4)
            self.r.end()
            self.assertEqual(self.pixel(15, 15)[:3], (255, 0, 0))
            self.assertEqual(self.pixel(15, 95)[:3], (0, 0, 255))
            red, green, blue, alpha = self.pixel(35, 35)
            self.assertTrue(126 <= red <= 128 and 127 <= green <= 129)
            self.assertEqual((blue, alpha), (0, 255))
            with patch('pygame.image.tostring', side_effect=AssertionError('canvas upload')):
                self.display.present()
        finally:
            scene.close()

    def test_hud_and_sidebar_warm_frame_has_no_surface_upload(self):
        hud = ModernHUD(self.base, lambda key, **kw: key)
        sidebar = ModernSidebar(self.base, lambda key, **kw: key)
        hud._gl = sidebar._gl = self.r
        sidebar.visible = True
        player = SimpleNamespace(hp=25, max_hp=30, saturation=80, stamina=40,
                                 sanity=40, exhaustion_level=0, exhaustion_progress=1,
                                 exhaustion_color=(255, 255, 255), str=12, dex=10,
                                 ac_total=3, lvl=1, gold=4, turns=5, depth=0, kills=0,
                                 wielded=None, status={'confused': 1})
        game = SimpleNamespace(modern_hud=hud)
        def draw():
            self.r.begin()
            self.r.clear()
            hud.draw(player)
            sidebar.draw(player, game)
            self.r.end()
        draw()
        with patch('pygame.image.tostring', side_effect=AssertionError('warm upload')):
            draw()
        self.assertEqual(self.pixel(40, 90)[:3], hud.theme.SURFACE_2)

    def test_temporary_surfaces_are_not_intercepted(self):
        self.r.begin()
        surface = pygame.Surface((12, 12), pygame.SRCALPHA)
        pygame.draw.rect(surface, (255, 0, 0), surface.get_rect())
        pygame.draw.circle(surface, (0, 255, 0), (6, 6), 2)
        self.assertEqual(surface.get_at((0, 0))[:3], (255, 0, 0))
        self.assertEqual(surface.get_at((6, 6))[:3], (0, 255, 0))
        self.assertFalse(self.r.batch.quads)
        self.r.end()

    def test_fill_tile_crops_and_revision_invalidates(self):
        image = pygame.Surface((30, 10), pygame.SRCALPHA)
        image.fill((255, 0, 0))
        image.fill((0, 255, 0), (10, 0, 10, 10))
        for color in ((0, 255, 0), (0, 0, 255)):
            image.fill(color, (10, 0, 10, 10))
            self.base.tileset.revision += 1
            self.r.begin()
            self.r.clear()
            with patch.object(self.base.tileset, 'image', return_value=image):
                self.base.fill_tile(1, 1, '#', (255, 255, 255))
            self.r.end()
            self.assertEqual(self.pixel(self.base.cw + 1, self.base.ch + 1)[:3], color)

    def test_pixel_text_matches_font_size_alignment_and_orientation(self):
        self.r.begin()
        self.r.clear((0, 0, 0))
        rect = self.r.text_pixels((100, 20), 'FЯ', (255, 255, 255), 12, True, 'right')
        self.r.end()
        font = pygame.font.SysFont('consolas', 12, bold=True)
        expected = pygame.Surface(font.size('FЯ'))
        expected.fill((0, 0, 0))
        expected.blit(font.render('FЯ', True, (255, 255, 255)), (0, 0))
        self.assertEqual(rect.size, expected.get_size())
        self.assertEqual(rect.right, 100)
        for y in range(rect.h):
            for x in range(rect.w):
                actual = self.pixel(rect.x+x, rect.y+y)[0]
                wanted = expected.get_at((x, y))[0]
                self.assertLessEqual(abs(actual - wanted), 1, (x, y, actual, wanted))

    def test_resize_and_backend_switch_release_renderer(self):
        self.base.surface = pygame.Surface((320, 240))
        self.r.resize(320, 240)
        self.r.begin()
        self.r.clear((12, 34, 56))
        self.r.end()
        self.assertEqual(self.pixel(319, 239)[:3], (12, 34, 56))
        self.display.configure((320, 240), backend='software')
        self.assertIsNone(self.base.gl_renderer)
        self.base.clear((90, 80, 70))
        self.assertEqual(self.base.surface.get_at((0, 0))[:3], (90, 80, 70))

    def test_game_first_person_cached_scene_and_modal_without_canvas_upload(self):
        from game.app import Game
        with patch('game.app.load_settings'), patch('game.app.Audio'):
            game = Game(self.base, seed=123)
        game.display = self.display
        game.modern_hud._gl = game.modern_sidebar._gl = self.r
        try:
            game.new_game()
            game.views.mode = 'first'
            game.views.quality = 0
            game.sidebar_visible = True
            game.draw()
            self.assertIsNone(self.display.ray_error)
            self.assertIsNotNone(self.display.scene)
            self.assertTrue(self.r.fbo_rendered)
            for mode in ('play', 'modal'):
                game.mode = mode
                if mode == 'modal':
                    game.modal_lines = ('Test', [('Overlay', (255, 255, 255))])
                # Warm a mode-specific scene, then prohibit any canvas upload.
                game.draw()
                with patch('pygame.image.tostring', side_effect=AssertionError('frame upload')):
                    game.draw()
                    self.display.present()
                self.assertIsNone(self.display.ray_error)
            game.mode = 'play'
            game.on_key(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F12, mod=0))
            self.assertTrue(game.debug_overlay.enabled)
            game.draw()
            with patch.object(self.r, 'text_pixels', wraps=self.r.text_pixels) as text:
                game.debug_overlay.draw_panel(game)
            self.assertTrue(any(str(call.args[1]).startswith('Visual objects ') for call in text.call_args_list))
            self.assertEqual(game.debug_overlay.visual_count, len(game.level.visual_manager))
            self.assertGreater(game.debug_overlay.visual_count, 0)
            game.views.mode = 'board'
            game.draw()
            self.assertIsNone(self.display.board_error)
        finally:
            if game.world:
                game.world.storage.cleanup()

    def test_paged_atlas_keeps_old_entries_and_releases_pages(self):
        atlas = SpriteAtlas(GL, page_size=16)
        try:
            image = pygame.Surface((10, 10), pygame.SRCALPHA)
            first = atlas.get('a', lambda: image)
            second = atlas.get('b', lambda: image)
            self.assertNotEqual(first[0], second[0])
            self.assertEqual(atlas.get('a', lambda: self.fail('cache miss')), first)
        finally:
            atlas.close()
        self.assertFalse(atlas.pages)


if __name__ == '__main__':
    unittest.main(argv=[sys.argv[0] or 'gl_pipeline_test'])
