"""Mouse/keyboard radial action selector; opening it does not advance time."""
import math
import pygame
from engine import config as C
from .lang import t


class ActionWheel:
    OPTIONS = ('inventory', 'food', 'drink', 'equipment', 'combat', 'world', 'character', 'sleep', 'system')

    def __init__(self, renderer, options=None, title='wheel.title'):
        self.r = renderer
        self.options = tuple(options or self.OPTIONS)
        self.title = title
        self.count = len(self.options)
        self.selected = 0
        height = renderer.surface.get_height()
        top = C.TOPBAR_H * renderer.ch
        self.center = (renderer.surface.get_width() // 2, top + (height - top) // 2)
        self.radius = min(renderer.surface.get_width() * 0.32, (height - top) * 0.36)

    def pick(self, pos):
        dx, dy = pos[0] - self.center[0], pos[1] - self.center[1]
        distance = math.hypot(dx, dy)
        if distance < self.radius * 0.25 or distance > self.radius:
            return None
        angle = (math.atan2(dy, dx) + math.pi / 2 + math.pi / self.count) % (2 * math.pi)
        return int(angle / (2 * math.pi / self.count)) % self.count

    def draw(self):
        r = self.r
        overlay = pygame.Surface(r.surface.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200))
        r.surface.blit(overlay, (0, 0))
        cx, cy = self.center
        sector = 2 * math.pi / self.count
        for index, option in enumerate(self.options):
            start = -math.pi / 2 + (index - 0.5) * sector
            points = [self.center] + [(cx + math.cos(start + n * math.pi / 48) * self.radius,
                                      cy + math.sin(start + n * math.pi / 48) * self.radius)
                                     for n in range(13)]
            color = (74, 66, 92) if index == self.selected else (30, 27, 38)
            pygame.draw.polygon(r.surface, color, points)
            pygame.draw.polygon(r.surface, C.C_WALL_EDGE, points, 2)
            angle = -math.pi / 2 + index * sector
            label = f'{index + 1} {t("wheel." + option)}'
            x = cx + math.cos(angle) * self.radius * 0.65
            y = cy + math.sin(angle) * self.radius * 0.65
            r.text(round(x / r.cw - len(label) / 2), round(y / r.ch), label,
                   C.YELLOW if index == self.selected else C.WHITE)
        pygame.draw.circle(r.surface, (20, 18, 28), self.center, round(self.radius * 0.25))
        title = t(self.title)
        r.text(round(cx / r.cw - len(title) / 2), round(cy / r.ch), title, C.CYAN)
        hint = t('wheel.hint')
        hint_row = max(0, r.surface.get_height() // r.ch - 2)
        r.text(2, hint_row, hint, C.WHITE,
               max_cells=r.surface.get_width() // r.cw - 4)
