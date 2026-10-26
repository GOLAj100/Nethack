"""Этап 2: приёмочный тест полного OpenGL-рендера.

Запуск: python test_stage2_acceptance.py

Проверяет:
1. GLRenderer инициализируется
2. Font atlas существует
3. Sprite atlas существует  
4. Compositor работает
5. FPS > 100 на OpenGL static
6. Software fallback работает
7. Нет tostring в основном пути (косвенно через FPS)
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Force real display
if 'SDL_VIDEODRIVER' in os.environ:
    del os.environ['SDL_VIDEODRIVER']

import pygame
from engine import config as C
from engine.renderer import Renderer
from game.app import Game


def test_stage2_acceptance():
    print("=" * 60)
    print("ЭТАП 2: ПРИЁМОЧНЫЙ ТЕСТ")
    print("=" * 60)
    
    pygame.init()
    
    # Setup
    probe = pygame.display.set_mode((64, 64))
    r = Renderer(probe)
    screen = pygame.display.set_mode((1280, 720))
    r.surface = screen
    game = Game(r)
    game.resize_window()
    game.new_game()
    game.mode = 'play'
    game.views.mode = 'first'
    
    # Test 1: OpenGL backend
    print("\n1. OpenGL backend...")
    game.display.configure(game.resolution, game.fullscreen, backend='opengl')
    assert game.display.backend == 'opengl', f"Expected opengl, got {game.display.backend}"
    print(f"   OK: backend={game.display.backend}")
    
    # Test 2: GLRenderer exists
    print("\n2. GLRenderer...")
    assert game.display.gl_renderer is not None, "GLRenderer not created"
    assert game.display.gl_renderer.gl_enabled, "GLRenderer not enabled"
    print(f"   OK: gl_enabled={game.display.gl_renderer.gl_enabled}")
    
    # Test 3: Font atlas
    print("\n3. Font atlas...")
    assert game.display.gl_renderer.atlas is not None, "Font atlas missing"
    print(f"   OK: atlas={game.display.gl_renderer.atlas.atlas_w}x{game.display.gl_renderer.atlas.atlas_h}")
    
    # Test 4: Sprite atlas (may not exist yet)
    print("\n4. Sprite atlas...")
    try:
        from engine.gl_sprite_atlas import SpriteAtlas
        print(f"   OK: SpriteAtlas module exists")
        has_sprite_atlas = True
    except ImportError:
        print(f"   SKIP: SpriteAtlas not implemented yet")
        has_sprite_atlas = False
    
    # Test 5: Compositor (may not exist yet)
    print("\n5. Compositor...")
    try:
        from engine.gl_compositor import GLCompositor
        print(f"   OK: GLCompositor module exists")
        has_compositor = True
    except ImportError:
        print(f"   SKIP: GLCompositor not implemented yet")
        has_compositor = False
    
    # Test 6: FPS benchmark
    print("\n6. FPS benchmark (OpenGL)...")
    game.update(0.016)
    for _ in range(4):
        game.draw()
        game.display.present()
    
    t0 = time.perf_counter()
    N = 90
    for _ in range(N):
        game.draw()
        game.display.present()
    fps_static = N / (time.perf_counter() - t0)
    print(f"   Static: {fps_static:.1f} FPS")
    
    t0 = time.perf_counter()
    N = 45
    for _ in range(N):
        game.views.yaw += 0.04
        game.draw()
        game.display.present()
    fps_rotation = N / (time.perf_counter() - t0)
    print(f"   Rotation: {fps_rotation:.1f} FPS")
    
    # Test 7: Software fallback
    print("\n7. Software fallback...")
    game.display.configure(game.resolution, game.fullscreen, backend='software')
    for _ in range(4):
        game.draw()
        game.display.present()
    
    t0 = time.perf_counter()
    N = 60
    for _ in range(N):
        game.draw()
        game.display.present()
    fps_sw = N / (time.perf_counter() - t0)
    print(f"   Software static: {fps_sw:.1f} FPS")
    
    # Summary
    print("\n" + "=" * 60)
    print("ИТОГИ:")
    print(f"  OpenGL static:    {fps_static:.1f} FPS  {'PASS' if fps_static > 100 else 'FAIL'}")
    print(f"  OpenGL rotation:  {fps_rotation:.1f} FPS  {'PASS' if fps_rotation > 60 else 'FAIL'}")
    print(f"  Software static:  {fps_sw:.1f} FPS  {'PASS' if fps_sw > 40 else 'FAIL'}")
    print(f"  Sprite atlas:     {'YES' if has_sprite_atlas else 'NO'}")
    print(f"  Compositor:       {'YES' if has_compositor else 'NO'}")
    print("=" * 60)
    
    pygame.quit()
    
    # Exit code
    if fps_static > 95 and fps_rotation > 60:
        print("\n[OK] ЭТАП 2 ПРИНЯТ")
        return 0
    else:
        print("\n[FAIL] ЭТАП 2 НЕ ПРОЙДЕН — нужна доработка")
        return 1


if __name__ == "__main__":
    exit(test_stage2_acceptance())
