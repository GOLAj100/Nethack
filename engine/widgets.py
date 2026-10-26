"""Экранные виджеты: меню, списки, всплывающие подсказки."""

from __future__ import annotations

import pygame

from . import config as C
from . import glyphs as G


class Menu:
    """Клавиатурное меню с рамкой. Возвращает индекс или None (отмена)."""

    def __init__(self, r, title: str, entries: list[str], width=None,
                 fg=C.WHITE, sel_fg=C.YELLOW, box_color=C.C_WALL_EDGE,
                 start_index: int = 0):
        self.r = r
        self.title = title
        self.entries = entries
        self.fg = fg
        self.sel_fg = sel_fg
        self.box_color = box_color
        self.index = start_index
        self.scroll = 0
        self.x = self.y = 0
        # (код клавиши, сShift) -> (метод Game, тип предмета) для быстрых действий
        self.quick: dict[tuple[int, bool], tuple[str, str]] = {}
        w = width or max([len(title) + 6] + [len(e) + 8 for e in entries]) + 2
        self.w = min(w, r.surface.get_width() // r.cw - 4)
        self.h = min(len(entries) + 4, r.surface.get_height() // r.ch - 2)
        self.inner_h = self.h - 4

    def _clamp(self):
        self.index = max(0, min(self.index, len(self.entries) - 1))
        if self.index < self.scroll:
            self.scroll = self.index
        if self.index >= self.scroll + self.inner_h:
            self.scroll = self.index - self.inner_h + 1

    def draw(self):
        sw = self.r.surface.get_width() // self.r.cw
        sh = self.r.surface.get_height() // self.r.ch
        self.draw_at((sw - self.w) // 2, max(0, (sh - self.h) // 2))

    def draw_at(self, x, y):
        r = self.r
        r.shadow_box(x, y, self.w, self.h, self.box_color, self.title, filled=True)
        self._clamp()
        for i in range(self.inner_h):
            idx = self.scroll + i
            if idx >= len(self.entries):
                break
            ey = y + 2 + i
            marker = G.BOX_ARROW_R if idx == self.index else " "
            color = self.sel_fg if idx == self.index else self.fg
            r.fill_rect(x + 1, ey, self.w - 2, 1, (24, 20, 34) if idx == self.index else C.BLACK)
            r.char(x + 1, ey, marker, self.sel_fg)
            r.text(x + 3, ey, self.entries[idx][: self.w - 5], color, bold=idx == self.index)

    def handle(self, ev) -> str:
        """Возвращает 'ok' | 'cancel' | None (не обработано)."""
        if ev.type != pygame.KEYDOWN:
            return None
        if ev.key in (pygame.K_UP, pygame.K_k):
            self.index = (self.index - 1) % max(1, len(self.entries))
        elif ev.key in (pygame.K_DOWN, pygame.K_j):
            self.index = (self.index + 1) % max(1, len(self.entries))
        elif ev.key == pygame.K_HOME:
            self.index = 0
        elif ev.key == pygame.K_END:
            self.index = len(self.entries) - 1
        elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            return "ok"
        elif ev.key == pygame.K_ESCAPE:
            return "cancel"
        else:
            return None
        return None

    # --- мышь и колесо -----------------------------------------------------
    def entry_at(self, col: int, row: int):
        """Индекс пункта под курсором или None."""
        if not (self.x <= col < self.x + self.w and self.y <= row < self.y + self.h):
            return None
        i = row - (self.y + 2)
        if 0 <= i < self.inner_h:
            idx = self.scroll + i
            if idx < len(self.entries):
                return idx
        return None

    def handle_click(self, col: int, row: int):
        """Один клик - выбор, повторный по тому же пункту - подтверждение."""
        idx = self.entry_at(col, row)
        if idx is None:
            return None
        if idx == self.index:
            return "ok"
        self.index = idx
        return None

    def wheel(self, dy: int):
        if len(self.entries) <= 1:
            return
        self.index = (self.index + dy) % len(self.entries)

    def digit(self, key: int):
        """Цифра 1-9,0 -> индекс 0-9, иначе None."""
        if pygame.K_1 <= key <= pygame.K_9:
            return key - pygame.K_1
        if key == pygame.K_0:
            return 9
        return None


class InventoryPanel:
    """Mouse-friendly inventory panel used by the modern game UI.

    The panel deliberately keeps item operations in ``Game``.  It is only a
    presentation/input layer, so old saves and keyboard actions remain
    compatible while the inventory no longer depends on an ASCII list menu.
    """

    ACTIONS = (
        ("act.info", "show_item_info"),
        ("act.drop", "do_drop"),
        ("act.eat", "do_eat"),
        ("act.quaff", "do_quaff"),
        ("act.read", "do_read"),
        ("act.wear", "do_wear"),
        ("act.wield", "do_wield"),
        ("act.takeoff", "do_takeoff"),
    )

    def __init__(self, renderer, items, translate):
        self.r = renderer
        self.items = list(items)
        self.t = translate
        self.selected = 0 if self.items else None
        self.item_rects = []
        self.action_rects = []
        self.close_rect = pygame.Rect(0, 0, 0, 0)
        self.hover_item = None
        self.hover_action = None
        self.hover_close = False

    @property
    def item(self):
        if self.selected is None or not self.items:
            return None
        return self.items[max(0, min(self.selected, len(self.items) - 1))]

    def _font(self, size, bold=False):
        if not hasattr(self, '_font_cache'):
            self._font_cache = {}
        key = (size, bold)
        font = self._font_cache.get(key)
        if font is None:
            font = pygame.font.SysFont("consolas", size, bold=bold)
            self._font_cache[key] = font
        return font

    def _text(self, surface, text, pos, color, size=16, bold=False):
        surface.blit(self._font(size, bold).render(str(text), True, color), pos)

    def draw(self):
        surface = self.r.surface
        width, height = surface.get_size()
        surface.fill((9, 11, 18))
        margin = max(16, min(width, height) // 32)
        panel = pygame.Rect(margin, margin, width - margin * 2, height - margin * 2)
        pygame.draw.rect(surface, (20, 24, 36), panel, border_radius=8)
        pygame.draw.rect(surface, (92, 112, 142), panel, 2, border_radius=8)
        self._text(surface, self.t("ui.inventory"), (panel.x + 20, panel.y + 14),
                   C.WHITE, 24, True)
        self.close_rect = pygame.Rect(panel.right - 112, panel.y + 12, 88, 32)
        close_color = (64, 82, 106) if self.hover_close else (44, 51, 68)
        pygame.draw.rect(surface, close_color, self.close_rect, border_radius=5)
        pygame.draw.rect(surface, C.CYAN if self.hover_close else (78, 88, 106),
                         self.close_rect, 1, border_radius=5)
        self._text(surface, self.t("ui.close"), (self.close_rect.x + 16, self.close_rect.y + 7),
                   C.WHITE if self.hover_close else C.LIGHT_GRAY, 14)

        left = pygame.Rect(panel.x + 16, panel.y + 60,
                           int(panel.w * .58), panel.h - 78)
        right = pygame.Rect(left.right + 16, left.y, panel.right - left.right - 32, left.h)
        pygame.draw.rect(surface, (13, 16, 25), left, border_radius=5)
        pygame.draw.rect(surface, (13, 16, 25), right, border_radius=5)
        self.item_rects = []
        columns = 4 if left.w >= 500 else 3
        gap = 8
        cell_w = (left.w - gap * (columns + 1)) // columns
        cell_h = 64
        for index, item in enumerate(self.items):
            col, row = index % columns, index // columns
            rect = pygame.Rect(left.x + gap + col * (cell_w + gap),
                               left.y + gap + row * (cell_h + gap), cell_w, cell_h)
            self.item_rects.append(rect)
            selected = index == self.selected
            hovered = index == self.hover_item
            fill = ((62, 82, 104) if hovered else (48, 62, 82)) if selected else ((46, 58, 76) if hovered else (28, 34, 48))
            pygame.draw.rect(surface, fill, rect,
                             border_radius=4)
            pygame.draw.rect(surface, C.CYAN if hovered or selected else (56, 64, 78), rect,
                             2 if hovered or selected else 1,
                             border_radius=4)
            icon = self.r.visual(item.glyph, item.color, size=(42, 42))
            surface.blit(icon, icon.get_rect(center=(rect.x + 28, rect.centery)))
            name = item.display_name()
            if getattr(item, "qty", 1) > 1:
                name += f" x{item.qty}"
            self._text(surface, name[:max(8, (cell_w - 54) // 8)],
                       (rect.x + 52, rect.y + 13), C.WHITE, 13, selected)
            if item.equipped:
                self._text(surface, item.equipped, (rect.x + 52, rect.y + 36), C.GREEN, 11)

        item = self.item
        if item is None:
            self._text(surface, self.t("ui.empty"), (right.x + 18, right.y + 24), C.GRAY, 18)
            self.action_rects = []
            return
        self._text(surface, item.display_name(), (right.x + 18, right.y + 20), C.YELLOW, 19, True)
        self._text(surface, item.label(), (right.x + 18, right.y + 50), C.LIGHT_GRAY, 13)
        self._text(surface, self.t("ui.choose_action"), (right.x + 18, right.y + 82), C.GRAY, 13)
        self.action_rects = []
        button_w = max(100, (right.w - 36) // 2)
        for index, (key, _method) in enumerate(self.ACTIONS):
            col, row = index % 2, index // 2
            rect = pygame.Rect(right.x + 14 + col * (button_w + 8),
                               right.y + 112 + row * 42, button_w, 34)
            self.action_rects.append(rect)
            hovered = index == self.hover_action
            pygame.draw.rect(surface, (62, 82, 104) if hovered else (38, 46, 62), rect,
                             border_radius=4)
            pygame.draw.rect(surface, C.CYAN if hovered else (70, 82, 102), rect,
                             2 if hovered else 1, border_radius=4)
            self._text(surface, self.t(key), (rect.x + 10, rect.y + 8),
                       C.WHITE if hovered else C.LIGHT_GRAY, 12, hovered)

    def handle_event(self, event):
        if event.type == pygame.MOUSEMOTION:
            self.hover_item = next((i for i, rect in enumerate(self.item_rects)
                                    if rect.collidepoint(event.pos)), None)
            self.hover_action = next((i for i, rect in enumerate(self.action_rects)
                                      if rect.collidepoint(event.pos)), None)
            self.hover_close = self.close_rect.collidepoint(event.pos)
            return None
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return "close"
            if event.key in (pygame.K_UP, pygame.K_LEFT):
                self.selected = max(0, (self.selected or 0) - 1)
            elif event.key in (pygame.K_DOWN, pygame.K_RIGHT):
                self.selected = min(len(self.items) - 1, (self.selected or 0) + 1)
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE) and self.item is not None:
                return ("actions", self.item)
            return None
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return None
        if self.close_rect.collidepoint(event.pos):
            return "close"
        for index, rect in enumerate(self.item_rects):
            if rect.collidepoint(event.pos):
                if index == self.selected:
                    return ("actions", self.item)
                self.selected = index
                return None
        for index, rect in enumerate(self.action_rects):
            if rect.collidepoint(event.pos) and self.item is not None:
                return ("action", self.item, self.ACTIONS[index][1])
        return None


def show_lines(r, lines: list[tuple[str, tuple[int, int, int]]], title="",
               width=None, fg=C.WHITE, bg=C.BLACK, hint="[ press any key ]"):
    """Отрисовка блока текста (например, справки)."""
    sw = r.surface.get_width() // r.cw
    sh = r.surface.get_height() // r.ch
    all_lines = list(lines) + [("", fg)]
    if hint:
        all_lines.append((hint, C.DARK_GRAY))
    w = width or min(sw - 4, max([len(t) for t, _ in all_lines] + [len(title) + 6]) + 4)
    h = min(sh - 2, len(all_lines) + 4)
    x = (sw - w) // 2
    y = max(0, (sh - h) // 2)
    r.fill_rect(x, y, w, h, bg)
    r.box(x, y, w, h, C.C_WALL_EDGE, title, filled=False)
    for i, (text, color) in enumerate(all_lines):
        if i + 2 >= h - 1:
            break
        r.text(x + 2, y + 2 + i, text[: w - 4], color)


