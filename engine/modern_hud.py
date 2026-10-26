"""Modern pixel-based HUD for the backrooms roguelike.

Replaces ASCII cell-based topbar with a clean, responsive UI inspired by
Neo Scavenger and modern survival games. Designed for wide monitors with
proper scaling support.
"""

from __future__ import annotations

import pygame
import engine.config as C


class HUDTheme:
    """Design tokens for consistent HUD styling."""
    
    # Surface hierarchy (tinted toward amber/backrooms aesthetic)
    SURFACE_0 = (5, 7, 12)      # Deepest background
    SURFACE_1 = (10, 13, 18)    # Panel background
    SURFACE_2 = (15, 19, 28)    # Card background
    SURFACE_3 = (22, 29, 43)    # Elevated element
    SURFACE_4 = (30, 38, 54)    # Hover state
    
    # Accent colors
    ACCENT_CYAN = (56, 189, 248)
    ACCENT_AMBER = (233, 165, 104)
    ACCENT_EMERALD = (110, 231, 183)
    ACCENT_RED = (239, 68, 68)
    
    # Metric colors (status-specific)
    HP_PRIMARY = (220, 38, 38)
    HP_BG = (60, 20, 20)
    
    SATURATION_PRIMARY = (34, 197, 94)
    SATURATION_BG = (20, 50, 30)
    
    STAMINA_PRIMARY = (56, 189, 248)
    STAMINA_BG = (20, 40, 60)
    
    SANITY_PRIMARY = (168, 85, 247)
    SANITY_BG = (45, 25, 65)
    
    RESERVE_PRIMARY = (251, 191, 36)
    RESERVE_BG = (60, 50, 20)
    
    # Typography
    TEXT_PRIMARY = (242, 242, 247)
    TEXT_SECONDARY = (156, 163, 175)
    TEXT_MUTED = (107, 114, 128)
    
    # Borders
    BORDER_DEFAULT = (75, 85, 99)
    BORDER_ACCENT = (156, 163, 175)
    
    # Spacing (base 8px grid)
    SPACING_XS = 4
    SPACING_SM = 8
    SPACING_MD = 12
    SPACING_LG = 16
    SPACING_XL = 24
    
    # Radii
    RADIUS_SM = 4
    RADIUS_MD = 6
    RADIUS_LG = 8
    RADIUS_FULL = 999
    
    # Shadows (rendered as layered rects with alpha)
    SHADOW_COLOR = (0, 0, 0, 128)


class ModernHUD:
    """Pixel-based HUD panel for player status and stats.
    
    Renders horizontally at the top of the screen, scaling gracefully
    from 1280px to ultrawide. Uses absolute pixel positioning instead
    of cell-grid coordinates.
    """
    
    def __init__(self, renderer, translate):
        self.r = renderer
        self.t = translate
        self.theme = HUDTheme()
        
        # Hover state for interactive elements
        self.hover_stat = None
        self.last_width = 0
        
        # Cached layout
        self.panel_rect = None
        self.stats_rect = None
        self.metric_rects = []
        self.stat_rects = {}
        
        # GL renderer injected by Game when the backend supports it.
        self._gl = None
        
        # Initialize layout with default screen width
        screen_width = renderer.surface.get_width()
        self.calculate_layout(screen_width)
    
    def _rect(self, surface, rect, color, border_radius=0, outline=False, thickness=1):
        """Draw a rect through GLRenderer when available, else pygame."""
        gl = self._gl
        if gl is not None and gl.gl_enabled:
            if outline:
                gl.draw_rect_outline(rect, color, thickness, border_radius)
            else:
                gl.draw_rect(rect, color, border_radius)
        else:
            if outline:
                pygame.draw.rect(surface, color, rect, thickness, border_radius=border_radius)
            else:
                pygame.draw.rect(surface, color, rect, border_radius=border_radius)
    
    def _text_gl(self, surface, text, pos, color, size=14, bold=False, align="left"):
        """Render text through GLRenderer when available, else pygame."""
        gl = self._gl
        if gl is not None and gl.gl_enabled:
            return gl.text_pixels(pos, text, color, size, bold, align)
        return self._text(surface, text, pos, color, size, bold, align)
    
    def _font(self, size, bold=False):
        """Get system font with fallback.  SysFont goes through the Windows
        registry on every call, which makes it the dominant per-frame cost
        on some systems.  Cache aggressively."""
        if not hasattr(self, '_font_cache'):
            self._font_cache = {}
        key = (size, bold)
        font = self._font_cache.get(key)
        if font is None:
            font = pygame.font.SysFont("consolas", size, bold=bold)
            self._font_cache[key] = font
        return font
    
    def _text(self, surface, text, pos, color, size=14, bold=False, align="left"):
        """Render text with alignment support."""
        if self._gl is not None and self._gl.gl_enabled:
            return self._gl.text_pixels(pos, text, color, size, bold, align)
        rendered = self._font(size, bold).render(str(text), True, color)
        rect = rendered.get_rect()
        
        if align == "center":
            rect.centerx = pos[0]
            rect.y = pos[1]
        elif align == "right":
            rect.right = pos[0]
            rect.y = pos[1]
        else:
            rect.topleft = pos
        
        surface.blit(rendered, rect)
        return rect
    
    def _draw_bar(self, surface, rect, value, maximum, fg_color, bg_color):
        """Draw a modern progress bar with smooth fill."""
        # Background
        self._rect(surface, rect, bg_color, border_radius=self.theme.RADIUS_FULL)
        
        # Fill
        if maximum > 0:
            fill_width = min(rect.width, max(0, int(rect.width * (value / maximum))))
            if fill_width > 0:
                fill_rect = pygame.Rect(rect.x, rect.y, fill_width, rect.height)
                self._rect(surface, fill_rect, fg_color, border_radius=self.theme.RADIUS_FULL)
        
        # Subtle border
        self._rect(surface, rect, self.theme.BORDER_DEFAULT, border_radius=self.theme.RADIUS_FULL, outline=True, thickness=1)
    
    def _draw_metric_card(self, surface, rect, label, value, maximum, color, bg_color, 
                          show_percentage=False, warning_threshold=0.33):
        """Draw a metric card (HP, Stamina, etc) with bar and text."""
        th = self.theme
        
        # Card background
        self._rect(surface, rect, th.SURFACE_2, border_radius=th.RADIUS_MD)
        
        # Dim border
        self._rect(surface, rect, th.BORDER_DEFAULT, border_radius=th.RADIUS_MD, outline=True, thickness=1)
        
        # Label
        label_y = rect.y + th.SPACING_SM
        self._text_gl(surface, label, (rect.x + th.SPACING_SM, label_y), 
                   th.TEXT_SECONDARY, size=12, bold=False)
        
        # Value text
        value_text = f"{max(0, value)}/{maximum}"
        if show_percentage and maximum > 0:
            pct = int(100 * value / maximum)
            value_text += f" ({pct}%)"
        
        # Warning color for low values
        text_color = th.TEXT_PRIMARY
        if maximum > 0 and (value / maximum) < warning_threshold:
            text_color = th.ACCENT_RED
        
        value_y = rect.y + th.SPACING_SM + 16
        self._text_gl(surface, value_text, (rect.x + th.SPACING_SM, value_y),
                   text_color, size=14, bold=True)
        
        # Progress bar
        bar_height = 8
        bar_margin = th.SPACING_SM
        bar_rect = pygame.Rect(
            rect.x + bar_margin,
            rect.bottom - bar_margin - bar_height,
            rect.width - bar_margin * 2,
            bar_height
        )
        self._draw_bar(surface, bar_rect, value, maximum, color, bg_color)
    
    def _draw_stat_item(self, surface, x, y, label, value, color=None):
        """Draw a small stat item (STR, AC, LVL, etc)."""
        th = self.theme
        if color is None:
            color = th.TEXT_PRIMARY
        
        # Label in muted color
        label_rect = self._text(surface, f"{label}:", (x, y), th.TEXT_MUTED, size=12)
        
        # Value in bright color
        value_x = x + label_rect.width + 6
        self._text(surface, str(value), (value_x, y), color, size=12, bold=True)
    
    def _draw_status_flag(self, surface, x, y, text, color):
        """Draw a status effect pill (confused, hallucinating, etc)."""
        th = self.theme
        
        # Measure text
        font = self._font(11, bold=True)
        text_rect = pygame.Rect((0, 0), font.size(text))
        
        # Pill background
        pill_width = text_rect.width + th.SPACING_SM * 2
        pill_height = text_rect.height + 6
        pill_rect = pygame.Rect(x, y, pill_width, pill_height)
        
        # Colored background with transparency
        if self._gl is not None and self._gl.gl_enabled:
            self._rect(surface, pill_rect, (*color, 80), th.RADIUS_FULL)
            self._rect(surface, pill_rect, (*color, 180), th.RADIUS_FULL, outline=True)
        else:
            pill_surface = pygame.Surface((pill_width, pill_height), pygame.SRCALPHA)
            pygame.draw.rect(pill_surface, (*color, 80), pill_surface.get_rect(), border_radius=th.RADIUS_FULL)
            pygame.draw.rect(pill_surface, (*color, 180), pill_surface.get_rect(), 1, border_radius=th.RADIUS_FULL)
            surface.blit(pill_surface, pill_rect)
        
        # Text
        text_x = x + th.SPACING_SM
        text_y = y + 3
        self._text(surface, text, (text_x, text_y), th.TEXT_PRIMARY, size=11, bold=True)
        
        return pill_rect
    
    def calculate_layout(self, screen_width):
        """Calculate HUD layout based on screen width."""
        th = self.theme
        
        # Panel dimensions
        panel_height = 128
        panel_margin = th.SPACING_MD
        panel_width = screen_width - panel_margin * 2
        
        self.panel_rect = pygame.Rect(panel_margin, panel_margin, panel_width, panel_height)
        
        # Metric cards (HP, Saturation, Stamina, Sanity)
        # Each gets equal space with gaps
        metric_count = 4
        card_gap = th.SPACING_SM
        card_padding = th.SPACING_MD
        
        # Available space for cards
        cards_width = panel_width - card_padding * 2
        card_width = (cards_width - card_gap * (metric_count - 1)) // metric_count
        card_height = panel_height - card_padding * 2
        
        self.metric_rects = []
        for i in range(metric_count):
            x = self.panel_rect.x + card_padding + i * (card_width + card_gap)
            y = self.panel_rect.y + card_padding
            self.metric_rects.append(pygame.Rect(x, y, card_width, card_height))
    
    def draw(self, player):
        """Draw the complete HUD."""
        surface = self.r.surface
        width, height = surface.get_size()
        
        # Recalculate layout if width changed
        if width != self.last_width:
            self.calculate_layout(width)
            self.last_width = width
        
        if self.panel_rect is None:
            return
        
        th = self.theme
        t = self.t
        
        # Main panel background
        self._rect(surface, self.panel_rect, th.SURFACE_1, border_radius=th.RADIUS_LG)
        self._rect(surface, self.panel_rect, th.BORDER_DEFAULT, border_radius=th.RADIUS_LG, outline=True, thickness=1)
        
        # Draw metric cards
        if len(self.metric_rects) >= 4:
            # HP
            self._draw_metric_card(
                surface, self.metric_rects[0],
                t('ui.bars.short'), player.hp, player.max_hp,
                th.HP_PRIMARY, th.HP_BG, warning_threshold=0.33
            )
            
            # Saturation (Food)
            self._draw_metric_card(
                surface, self.metric_rects[1],
                t('ui.food.short'), player.saturation, 100,
                th.SATURATION_PRIMARY, th.SATURATION_BG, warning_threshold=0.25
            )
            
            # Stamina
            self._draw_metric_card(
                surface, self.metric_rects[2],
                t('ui.stamina.short'), player.stamina, 50,
                th.STAMINA_PRIMARY, th.STAMINA_BG, warning_threshold=0.20
            )
            
            # Sanity
            self._draw_metric_card(
                surface, self.metric_rects[3],
                t('ui.sanity.short'), player.sanity, 50,
                th.SANITY_PRIMARY, th.SANITY_BG, warning_threshold=0.30
            )
        
        # Secondary stats bar (below metric cards)
        stats_y = self.panel_rect.bottom + th.SPACING_SM
        stats_bg_height = 38
        stats_rect = pygame.Rect(
            self.panel_rect.x,
            stats_y,
            self.panel_rect.width,
            stats_bg_height
        )
        self.stats_rect = stats_rect
        
        self._rect(surface, stats_rect, th.SURFACE_1, th.RADIUS_MD)
        self._rect(surface, stats_rect, th.BORDER_DEFAULT, th.RADIUS_MD, outline=True)
        
        # Reserve/Exhaustion
        reserve_x = stats_rect.x + th.SPACING_MD
        reserve_y = stats_rect.y + th.SPACING_SM
        reserve_text = f"{t('ui.reserve.short')} {player.exhaustion_level:+d} {player.exhaustion_progress}/50"
        self._text(surface, reserve_text, (reserve_x, reserve_y), player.exhaustion_color, size=12, bold=True)
        
        # Secondary stats in a row
        stat_x = reserve_x + 240
        stat_spacing = 80
        
        self._draw_stat_item(surface, stat_x, reserve_y, "STR", player.str, 
                            th.TEXT_PRIMARY if player.str >= 10 else th.ACCENT_RED)
        stat_x += stat_spacing
        
        self._draw_stat_item(surface, stat_x, reserve_y, "AC", player.ac_total, th.ACCENT_CYAN)
        stat_x += stat_spacing
        
        self._draw_stat_item(surface, stat_x, reserve_y, "LVL", player.lvl, th.TEXT_PRIMARY)
        stat_x += stat_spacing
        
        self._draw_stat_item(surface, stat_x, reserve_y, "$", player.gold, th.ACCENT_AMBER)
        stat_x += stat_spacing
        
        self._draw_stat_item(surface, stat_x, reserve_y, "T", player.turns, th.TEXT_MUTED)
        
        # Status flags (right side)
        flags_x = stats_rect.right - th.SPACING_MD
        flags_y = reserve_y
        
        flags = []
        if player.status.get("confused", 0) > 0:
            flags.append((t("st.confused"), C.PURPLE))
        if player.status.get("hallucinating", 0) > 0:
            flags.append((t("st.hallucinating"), C.CYAN))
        if player.status.get("asleep", 0) > 0:
            flags.append((t("st.asleep"), C.BLUE))
        if player.status.get("lucky", 0) > 0:
            flags.append((t("st.lucky"), C.GREEN))
        
        for text, color in reversed(flags):
            pill_rect = self._draw_status_flag(surface, flags_x - 100, flags_y, text, color)
            flags_x = pill_rect.x - th.SPACING_SM
    
    def get_height(self):
        """Pixel height of the top HUD, including its outer margin.

        The first-person viewport starts on the next pixel.  A cell-rounded
        offset used to leave a black strip under the cards on wide canvases.
        """
        if self.stats_rect is not None:
            return self.stats_rect.bottom + self.theme.SPACING_SM
        th = self.theme
        return th.SPACING_MD + 128 + th.SPACING_SM + 38 + th.SPACING_SM
    
    def handle_mouse_motion(self, pos):
        """Update hover state for interactive elements."""
        self.hover_stat = None
        
        if self.metric_rects:
            for i, rect in enumerate(self.metric_rects):
                if rect.collidepoint(pos):
                    self.hover_stat = i
                    break
    
    def handle_click(self, pos):
        """Handle click on HUD elements (for future interactions)."""
        if self.hover_stat is not None:
            # Future: show detailed stat breakdown
            pass


class ModernSidebar:
    """Optional sidebar with detailed stats and quick actions.
    
    Replaces the ASCII sidebar with a cleaner pixel-based version.
    Toggleable with Tab key.
    """
    
    def __init__(self, renderer, translate):
        self.r = renderer
        self.t = translate
        self.theme = HUDTheme()
        self.visible = False
        self.width = 280  # Sidebar width
        self._font_cache = {}
        self._gl = None  # Injected by Game when backend supports it
        
        self.action_rects = []
        self.hover_action = None
        self.rect = None
    
    def _rect(self, surface, rect, color, border_radius=0, outline=False, thickness=1):
        """Draw a rect through GLRenderer when available, else pygame."""
        gl = self._gl
        if gl is not None and gl.gl_enabled:
            if outline:
                gl.draw_rect_outline(rect, color, thickness, border_radius)
            else:
                gl.draw_rect(rect, color, border_radius)
        else:
            if outline:
                pygame.draw.rect(surface, color, rect, thickness, border_radius=border_radius)
            else:
                pygame.draw.rect(surface, color, rect, border_radius=border_radius)
    
    def _text_gl(self, surface, text, pos, color, size=14, bold=False):
        """Render text through GLRenderer when available, else pygame."""
        gl = self._gl
        if gl is not None and gl.gl_enabled:
            return gl.text_pixels(pos, text, color, size, bold)
        font = self._font(size, bold)
        surface.blit(font.render(str(text), True, color), pos)
        return pygame.Rect(pos[0], pos[1], font.size(str(text))[0], font.size(str(text))[1])
    
    def get_width(self):
        """Get sidebar width in pixels."""
        return self.width if self.visible else 0
    
    def toggle(self):
        """Toggle sidebar visibility."""
        self.visible = not self.visible
    
    def draw(self, player, game):
        """Draw the sidebar if visible."""
        if not self.visible:
            self.rect = None
            return []
        
        surface = self.r.surface
        width, height = surface.get_size()
        th = self.theme
        t = self.t
        
        # Sidebar dimensions
        sidebar_width = self.width
        sidebar_x = width - sidebar_width - th.SPACING_MD
        sidebar_y = game.modern_hud.get_height() + th.SPACING_MD
        sidebar_height = height - sidebar_y - th.SPACING_MD
        
        sidebar_rect = pygame.Rect(sidebar_x, sidebar_y, sidebar_width, sidebar_height)
        self.rect = sidebar_rect
        
        # Background with transparency
        if self._gl is not None and self._gl.gl_enabled:
            self._rect(surface, sidebar_rect, (*th.SURFACE_1, 240), th.RADIUS_LG)
            self._rect(surface, sidebar_rect, th.BORDER_ACCENT, th.RADIUS_LG, outline=True)
        else:
            sidebar_surface = pygame.Surface((sidebar_width, max(1, sidebar_height)), pygame.SRCALPHA)
            pygame.draw.rect(sidebar_surface, (*th.SURFACE_1, 240), sidebar_surface.get_rect(), border_radius=th.RADIUS_LG)
            pygame.draw.rect(sidebar_surface, th.BORDER_ACCENT, sidebar_surface.get_rect(), 1, border_radius=th.RADIUS_LG)
            surface.blit(sidebar_surface, sidebar_rect)
        
        # Title
        title_y = sidebar_y + th.SPACING_MD
        self._text_gl(surface, t("ui.status"), (sidebar_x + th.SPACING_MD, title_y),
                   th.TEXT_PRIMARY, size=16, bold=True)
        
        # Stats list
        content_y = title_y + 30
        line_height = 18
        
        wname = player.wielded.display_name() if player.wielded else t("item.bare_hands")
        
        stats = [
            (f"{t('ui.bars')}:", f"{player.hp}/{player.max_hp}", 
             C.WHITE if player.hp > player.max_hp // 3 else C.RED),
            (f"{t('ui.food.short')}:", f"{player.saturation}/100", C.GREEN),
            (f"{t('ui.stamina.short')}:", f"{player.stamina}/50", C.CYAN),
            (f"{t('ui.sanity.short')}:", f"{player.sanity}/50", C.PURPLE),
            ("", "", None),  # Spacer
            (f"{t('ui.lbl.ac')}:", str(player.ac_total), C.CYAN),
            (f"{t('ui.lbl.str')}:", str(player.str), C.WHITE if player.str >= 10 else C.RED),
            (f"{t('ui.lbl.dex')}:", str(player.dex), C.WHITE),
            (f"{t('ui.lbl.lvl')}:", str(player.lvl), C.WHITE),
            (t("ui.depth_of", d=player.depth, m=C.MAX_LEVEL), "", C.YELLOW),
            (f"{t('ui.lbl.gold')}:", f"${player.gold}", C.YELLOW),
            (t("sheet.kills", n=player.kills), "", C.WHITE),
            (f"{t('ui.lbl.wpn')}:", wname[:20], C.LIGHT_GRAY),
        ]
        
        for label, value, color in stats:
            if color is None:
                content_y += line_height // 2
                continue
            
            self._text_gl(surface, label, (sidebar_x + th.SPACING_MD, content_y),
                      th.TEXT_SECONDARY, size=12)
            if value:
                self._text_gl(surface, value, (sidebar_x + sidebar_width - th.SPACING_MD - 80, content_y),
                          color, size=12, bold=True)
            content_y += line_height
        
        # Quick actions
        actions_y = sidebar_y + sidebar_height - 160
        self._text_gl(surface, t("wheel.title"), (sidebar_x + th.SPACING_MD, actions_y),
                   th.TEXT_PRIMARY, size=14, bold=True)
        
        quick = [
            ('ui.quick_actions', 'action_menu'),
            ('ui.quick_interact', 'interact'),
            ('ui.quick_inventory', 'inventory'),
            ('ui.quick_map', 'view_map'),
            ('ui.quick_character', 'char_sheet'),
            ('ui.quick_hide', 'toggle_status'),
        ]
        
        self.action_rects = []
        button_y = actions_y + 30
        button_height = 32
        button_spacing = 8
        
        for i, (label_key, action) in enumerate(quick):
            button_rect = pygame.Rect(
                sidebar_x + th.SPACING_MD,
                button_y + i * (button_height + button_spacing),
                sidebar_width - th.SPACING_MD * 2,
                button_height
            )
            
            # Button background
            is_hover = (self.hover_action == i)
            bg_color = th.SURFACE_4 if is_hover else th.SURFACE_3
            self._rect(surface, button_rect, bg_color, border_radius=th.RADIUS_MD)
            self._rect(surface, button_rect, th.BORDER_DEFAULT, border_radius=th.RADIUS_MD, outline=True, thickness=1)
            
            # Button text
            self._text_gl(surface, t(label_key), 
                      (button_rect.x + th.SPACING_SM, button_rect.y + 8),
                      th.TEXT_PRIMARY, size=12, bold=is_hover)
            
            self.action_rects.append((button_rect, action))
        
        return self.action_rects
    
    def _font(self, size, bold=False):
        key = (size, bold)
        font = self._font_cache.get(key)
        if font is None:
            font = pygame.font.SysFont("consolas", size, bold=bold)
            self._font_cache[key] = font
        return font

    def _text(self, surface, text, pos, color, size=14, bold=False):
        """Helper to render text."""
        font = self._font(size, bold)
        surface.blit(font.render(str(text), True, color), pos)
    
    def handle_mouse_motion(self, pos):
        """Update hover state."""
        self.hover_action = None
        for i, (rect, _) in enumerate(self.action_rects):
            if rect.collidepoint(pos):
                self.hover_action = i
                break
    
    def handle_click(self, pos):
        """Handle click on action buttons."""
        for rect, action in self.action_rects:
            if rect.collidepoint(pos):
                return action
        return None
