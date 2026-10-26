"""Debugging script to verify game initialization and rendering."""

import os
import pygame
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import config as C
from engine.renderer import Renderer
from game.app import Game


def main():
    print("Initializing pygame...")
    pygame.init()
    
    print("Creating window...")
    screen = pygame.display.set_mode((1280, 720), pygame.RESIZABLE)
    pygame.display.set_caption(C.TITLE)
    
    print("Creating renderer...")
    r = Renderer(screen)
    print(f"Cell size: {r.cw}x{r.ch}")
    
    print("Creating game...")
    game = Game(r)
    print(f"Game mode: {game.mode}")
    print(f"Use modern HUD: {game.use_modern_hud}")
    
    print("Resizing window...")
    game.resize_window()
    
    print("\nStarting game loop...")
    print("Press ESC or close window to quit")
    print("Press N to start new game")
    print("-" * 50)
    
    clock = pygame.time.Clock()
    frame_count = 0
    
    try:
        while game.running:
            # Handle events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    game.running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        game.running = False
                    elif event.key == pygame.K_n and game.mode == "title":
                        print("Starting new game...")
                        game.new_game()
                        print(f"Player created: HP={game.player.hp}/{game.player.max_hp}")
            
            # Handle game events
            game.handle_events()
            
            # Update game state
            game.tick()
            
            # Draw
            game.draw()
            
            # Update display
            pygame.display.flip()
            
            # Log first few frames
            frame_count += 1
            if frame_count <= 5:
                print(f"Frame {frame_count}: mode={game.mode}, running={game.running}")
            elif frame_count == 10:
                print("Game loop running normally (frame logging disabled)")
            
            # Cap at 60 FPS
            clock.tick(60)
    
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if game.display:
            game.display.close()
        pygame.quit()
        print("\nGame closed successfully")


if __name__ == "__main__":
    main()
