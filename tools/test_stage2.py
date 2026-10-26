"""Stage 2 test: verify GL renderer is active."""
import os
import pygame
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

def test_gl_renderer():
    """Check if GL renderer initializes correctly."""
    pygame.init()
    
    # Import engine parts
    from engine.renderer import Renderer
    from engine.display import Display
    from engine import config as C
    
    print(f"USE_OPENGL: {C.USE_OPENGL}")
    
    # Create font and canvas
    try:
        font = pygame.font.SysFont(C.FONT_CANDIDATES, C.FONT_SIZE)
    except Exception as e:
        print(f"ERROR Font load failed: {e}")
        return 1
    
    # Grid dimensions: same as app.py
    grid_w = C.CAMERA_W + C.SIDEBAR_W
    grid_h = C.TOPBAR_H + C.CAMERA_H + C.LOG_H
    canvas_w = grid_w * C.FONT_SIZE
    canvas_h = grid_h * C.FONT_SIZE
    
    canvas = pygame.Surface((canvas_w, canvas_h))
    print(f"Canvas: {canvas_w}x{canvas_h}")
    
    # Create renderer (this will trigger Display internally)
    renderer = Renderer(canvas, C.FONT_SIZE)
    
    # Create display
    display = Display(renderer)
    display.configure((1280, 720), False)
    
    print(f"Backend: {display.backend}")
    print(f"GL enabled: {display.gl_renderer is not None}")
    
    if display.gl_renderer:
        print(f"GL state: gl_enabled={display.gl_renderer.gl_enabled}")
        print("[OK] Stage 2: GL renderer active")
        
        # Draw test
        display.gl_renderer.clear((0.1, 0.1, 0.2))
        display.gl_renderer.text(1, 1, "Stage 2 Test", (255, 255, 255))
        display.present()
        
        time.sleep(2)
        return 0
    else:
        print(f"[FAIL] GL renderer not initialized: {display.error}")
        return 1

if __name__ == "__main__":
    exit_code = test_gl_renderer()
    pygame.quit()
    sys.exit(exit_code)
