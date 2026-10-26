"""Quick test to verify game launches correctly."""

import os
import sys
import time

import pygame

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
SHOTS = os.path.join(ROOT, "artifacts")

from engine import config as C
from engine.renderer import Renderer
from game.app import Game


def main():
    pygame.init()
    pygame.display.set_caption(C.TITLE)
    
    # Create window
    screen = pygame.display.set_mode((1280, 720))
    r = Renderer(screen)
    
    # Create game
    game = Game(r)
    game.resize_window()
    
    print(f"Game initialized: mode={game.mode}, running={game.running}")
    
    # Draw first frame
    game.draw()
    pygame.display.flip()
    os.makedirs(SHOTS, exist_ok=True)
    title_shot = os.path.join(SHOTS, "quick_test_title.png")
    pygame.image.save(screen, title_shot)
    print(f"Screenshot saved: {title_shot}")
    
    # Simulate new game
    game.new_game()
    print(f"New game started: mode={game.mode}")
    
    # Draw gameplay frame
    game.draw()
    pygame.display.flip()
    play_shot = os.path.join(SHOTS, "quick_test_play.png")
    pygame.image.save(screen, play_shot)
    print(f"Screenshot saved: {play_shot}")
    
    # Run a few frames
    clock = pygame.time.Clock()
    for i in range(5):
        for event in pygame.event.get():
            pass
        dt = clock.tick(60) / 1000.0
        game.handle_events()
        if game.mode == "play":
            game.tick_floats()
            game.update(dt)
        game.draw()
        pygame.display.flip()
        print(f"Frame {i+1}: OK")
    
    print("\n[OK] All tests passed! Game is working correctly.")
    print(f"Check {title_shot} and {play_shot}")
    
    # Cleanup
    if game.display:
        game.display.close()
    pygame.quit()


if __name__ == "__main__":
    main()
