"""Запускной тест: окно создаётся, игровой цикл крутится несколько кадров."""

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame

import main as entry

frames = {"n": 0}


def pump():
    frames["n"] += 1
    if frames["n"] == 2:
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN,
                                              mod=0, unicode="\r", scancode=0))
    if frames["n"] == 4:
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RIGHT,
                                              mod=0, unicode="d", scancode=0))
    if frames["n"] == 8:
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SLASH,
                                              mod=0, unicode="/", scancode=0))
    if frames["n"] == 10:
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE,
                                              mod=0, unicode="\x1b", scancode=0))
    if frames["n"] >= 14:
        pygame.event.post(pygame.event.Event(pygame.QUIT))


pygame.init()
r = entry.make_window()
print("window:", pygame.display.get_surface().get_size(), "cell:", r.cw, "x", r.ch,
      "font:", r.font_name)
g = entry.Game(r)
g.resize_window()

orig_handle = g.handle_events


def handle_with_pump():
    pump()
    orig_handle()


g.handle_events = handle_with_pump
g.run()
assert g.crash_tb is None, g.crash_tb
assert g.player is not None

print("frames rendered:", frames["n"])
print("mode:", g.mode, "turns:", g.player.turns if g.player else "-")
print("LAUNCH OK")
