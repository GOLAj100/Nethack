"""Test script for Stage 2: Full OpenGL render without tostring."""
import os
import sys
import time
import threading
import pygame

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import config as C
from engine.renderer import Renderer
from game.app import Game


def auto_quit_after(seconds):
    """Quit pygame after N seconds."""
    time.sleep(seconds)
    pygame.event.post(pygame.event.Event(pygame.QUIT))
    print(f"\nAuto-quit after {seconds}s")


def make_window():
    """Create window (same as main.py)."""
    probe = pygame.display.set_mode((64, 64))
    r = Renderer(probe)
    cols = C.CAMERA_W + C.SIDEBAR_W
    rows = C.TOPBAR_H + C.CAMERA_H + C.LOG_H
    size = (cols * r.cw, rows * r.ch)
    screen = pygame.display.set_mode(size)
    screen.fill(C.BLACK)
    r.surface = screen
    return r


if __name__ == "__main__":
    print("Starting game with OpenGL renderer...")
    print("Testing Stage 2: Full GPU render (no tostring copy)")
    
    # Start auto-quit timer
    threading.Thread(target=auto_quit_after, args=(3,), daemon=True).start()
    
    # Initialize pygame
    pygame.init()
    pygame.display.set_caption(C.TITLE)
    
    # Create renderer and game
    r = make_window()
    game = Game(r)
    game.resize_window()
    
    try:
        game.run()
    except KeyboardInterrupt:
        pass
    finally:
        if game.display:
            game.display.close()
        pygame.quit()
    
    # Check if GL renderer was used
    if game.display and game.display.gl_renderer:
        if game.display.gl_renderer.gl_enabled:
            print("\n[OK] GL Renderer active")
            print(f"[OK] FBO rendered: {game.display.gl_renderer.fbo_rendered}")
        else:
            print("\n[FAIL] GL Renderer disabled")
    else:
        print("\n[FAIL] GL Renderer not initialized")
    
    print("\nStage 2 test complete.")
