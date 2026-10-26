"""Render/UI diagnostics. Off by default; never changes gameplay state."""
from __future__ import annotations

import time

import pygame

from . import config as C


MODES = (
    "canvas",
    "hud",
    "viewport",
    "chat",
    "grid",
    "chunks",
    "fov",
    "lights",
    "sprites",
    "gpu",
)


class DebugOverlay:
    def __init__(self):
        self.enabled = False
        self.modes = set()
        self.font = None
        self.passes = {}
        self.warnings = []
        self.sprite_boxes = []
        self.sprite_count = 0
        self.visible_entities = 0
        self.visual_count = 0
        self.fov_cells = 0
        self.light_sources = 0
        self.lighting_on = True
        self.absolute_darkness = False
        self.fps = 0.0
        self.corner = "right"
        self.panel_rect = None
        self.fbo_size = None
        self.ray_iterations = 0
        self.uploads = 0
        self._fps_frames = 0
        self._fps_mark = time.perf_counter()

    def toggle(self):
        self.enabled = not self.enabled

    def cycle_mode(self):
        if not self.modes:
            self.modes.add(MODES[0])
            return
        active = [name for name in MODES if name in self.modes]
        nxt = MODES[(MODES.index(active[-1]) + 1) % len(MODES)]
        self.modes = {nxt}

    def toggle_mode(self, name):
        if name in self.modes:
            self.modes.discard(name)
        else:
            self.modes.add(name)

    def begin_frame(self):
        self.passes = {}
        self.warnings = []
        self.sprite_boxes = []
        self.sprite_count = 0
        self.visible_entities = 0

    def mark(self, name, ms):
        self.passes[name] = self.passes.get(name, 0.0) + float(ms)

    def note_sprites(self, count, boxes=None):
        self.sprite_count = int(count)
        if boxes:
            self.sprite_boxes = list(boxes)

    def tick_fps(self, dt_ms):
        self._fps_frames += 1
        now = time.perf_counter()
        elapsed = now - self._fps_mark
        if elapsed >= 0.25:
            self.fps = self._fps_frames / elapsed
            self._fps_frames = 0
            self._fps_mark = now
        elif self.fps <= 0 and dt_ms > 0:
            self.fps = 1000.0 / dt_ms

    def collect(self, game):
        surface = game.r.surface
        cw, ch = surface.get_size()
        display = game.display
        window = display.size if display else (cw, ch)
        rect = display.rect if display else pygame.Rect(0, 0, *window)
        backend = display.backend if display else "software"
        gpu = display.gpu_name if display else "Software"
        view = getattr(game.views, "rect", None)
        hud = game.modern_hud.panel_rect if game.modern_hud else None
        stats = game.modern_hud.stats_rect if game.modern_hud else None
        chat = getattr(game, "chat_rect", None)
        sidebar = game.modern_sidebar.rect if game.modern_sidebar and game.modern_sidebar.visible else None
        player = game.player
        level = game.level
        self.visual_count = len(level.visual_manager) if level is not None else 0
        self.visible_entities = len(getattr(game, "visible_world", {}) or {})
        if not self.visible_entities and level is not None:
            self.visible_entities = len(getattr(level, "visible", ()) or ())
        self.fov_cells = len(getattr(level, "visible", ()) or ()) if level else 0
        self.light_sources = len(getattr(level, "light_sources", ()) or ()) if level else 0
        self.lighting_on = bool(game.views.lighting)
        profile = getattr(level, "profile", {}) or {}
        self.absolute_darkness = bool(profile.get("absolute_darkness"))
        self.warnings = []
        canvas = pygame.Rect(0, 0, cw, ch)
        for name, box in (("viewport", view), ("hud", hud), ("hud-stats", stats), ("chat", chat), ("sidebar", sidebar)):
            if box is None:
                continue
            if not canvas.contains(box):
                self.warnings.append(f"{name} outside canvas {box}")
        if view is not None and view.bottom < ch - 2 and game.views.mode == "ascii":
            self.warnings.append(f"viewport stops {ch - view.bottom}px above canvas")
        if view is not None and hud is not None and view.top < (stats.bottom if stats else hud.bottom):
            self.warnings.append("viewport overlaps HUD")
        if display is not None and display.rect.w and display.rect.h and display.canvas:
            scale_x = display.rect.w / display.canvas.get_width()
            scale_y = display.rect.h / display.canvas.get_height()
            if abs(scale_x - scale_y) > 0.02:
                self.warnings.append(f"non-uniform scale x{scale_x:.3f} y{scale_y:.3f}")
        fbo = getattr(display, "fbo_size", None) if display else None
        scene = getattr(display, "scene", None) if display else None
        if fbo and scene and (scene[1].w <= 0 or abs(fbo[0] / max(1, fbo[1]) - scene[1].w / max(1, scene[1].h)) > 0.08):
            self.warnings.append(f"FBO {fbo[0]}x{fbo[1]} != scene {scene[1].size}")
        return {
            "window": window,
            "canvas": (cw, ch),
            "rect": rect,
            "backend": backend,
            "gpu": gpu,
            "view": view,
            "hud": hud,
            "stats": stats,
            "chat": chat,
            "sidebar": sidebar,
            "player": player,
            "level": level,
        }

    def _font(self):
        if self.font is None:
            self.font = pygame.font.SysFont("consolas", 14)
        return self.font

    def _outline(self, surface, rect, color, width=2):
        if rect is None or rect.w <= 0 or rect.h <= 0:
            return
        pygame.draw.rect(surface, color, rect, width)

    def draw_markers(self, game):
        if not self.enabled or not self.modes or game.player is None:
            return
        if game.mode not in ("play", "target"):
            return
        info = self.collect(game)
        surface = game.r.surface
        if "canvas" in self.modes:
            self._outline(surface, pygame.Rect(1, 1, info["canvas"][0] - 2, info["canvas"][1] - 2), (80, 220, 255), 2)
        if "hud" in self.modes:
            self._outline(surface, info["hud"], (255, 196, 64), 2)
            self._outline(surface, info["stats"], (255, 140, 40), 2)
            self._outline(surface, info["sidebar"], (255, 120, 180), 2)
        if "viewport" in self.modes and info["view"] is not None:
            self._outline(surface, info["view"], (64, 220, 120), 2)
        if "chat" in self.modes and info["chat"] is not None:
            self._outline(surface, info["chat"], (120, 170, 255), 2)
        if "grid" in self.modes and game.views.mode == "ascii":
            self._draw_grid(game, info["view"])
        if "chunks" in self.modes and game.views.mode == "ascii":
            self._draw_chunks(game)
        if "fov" in self.modes and game.views.mode == "ascii":
            self._draw_fov(game)
        if "lights" in self.modes and game.views.mode == "ascii":
            self._draw_lights(game)
        if "sprites" in self.modes:
            for box in self.sprite_boxes:
                self._outline(surface, box, (255, 80, 80), 1)
        if "gpu" in self.modes:
            self._draw_gpu(game, info)

    def _cell_rect(self, game, col, row):
        return game.r.cell_rect(col, row + game.map_offset_y)

    def _draw_grid(self, game, view):
        if view is None:
            return
        surface = game.r.surface
        step_x = max(game.r.cw, view.w // 16)
        step_y = max(game.r.ch, view.h // 12)
        color = (70, 90, 70)
        x = view.left
        while x < view.right:
            pygame.draw.line(surface, color, (x, view.top), (x, view.bottom))
            x += step_x
        y = view.top
        while y < view.bottom:
            pygame.draw.line(surface, color, (view.left, y), (view.right, y))
            y += step_y

    def _draw_chunks(self, game):
        world = game.world
        if world is None:
            return
        surface = game.r.surface
        p = game.player
        origin_x = p.chunk_x * world.w
        origin_y = p.chunk_y * world.h
        for row in range(game.camera_h):
            for col in range(game.camera_w):
                wx, wy = game.screen_to_world(col, row)
                if (wx - origin_x) % world.w in (0, world.w - 1) or (wy - origin_y) % world.h in (0, world.h - 1):
                    rect = self._cell_rect(game, col, row)
                    pygame.draw.rect(surface, (180, 120, 40), rect, 1)

    def _draw_fov(self, game):
        surface = game.r.surface
        for row in range(game.camera_h):
            for col in range(game.camera_w):
                wx, wy = game.screen_to_world(col, row)
                lv, lx, ly = self._resolve(game, wx, wy)
                if lv is None or (lx, ly) not in lv.visible:
                    continue
                rect = self._cell_rect(game, col, row)
                shade = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
                shade.fill((80, 180, 255, 48))
                surface.blit(shade, rect)

    def _draw_lights(self, game):
        surface = game.r.surface
        for row in range(game.camera_h):
            for col in range(game.camera_w):
                wx, wy = game.screen_to_world(col, row)
                lv, lx, ly = self._resolve(game, wx, wy)
                if lv is None:
                    continue
                sources = getattr(lv, "light_sources", ()) or ()
                lamps = getattr(lv, "ceiling_lamps", ()) or ()
                if (lx, ly) not in sources and (lx, ly) not in lamps:
                    continue
                rect = self._cell_rect(game, col, row)
                pygame.draw.circle(surface, (255, 220, 80), rect.center, max(3, min(rect.w, rect.h) // 2), 1)

    def _draw_gpu(self, game, info):
        display = game.display
        scene = getattr(display, "scene", None) if display else None
        if not scene:
            return
        _texture, area = scene
        self._outline(game.r.surface, area, (180, 80, 255), 1)

    def _resolve(self, game, wx, wy):
        world = game.world
        if world is None:
            lv = game.level
            if lv is None or not lv.in_bounds(wx, wy):
                return None, 0, 0
            return lv, wx, wy
        p = game.player
        cx, lx = divmod(wx, world.w)
        cy, ly = divmod(wy, world.h)
        lv = world.chunk(p.chunk_x + cx, p.chunk_y + cy, p.world_z)
        if lv is None:
            return None, 0, 0
        return lv, lx, ly

    def draw_panel(self, game):
        if not self.enabled or game.player is None:
            self.panel_rect = None
            return
        if game.mode in ("title", "inventory", "build_puzzle", "work", "audio_settings", "sleep_slider"):
            self.panel_rect = None
            return
        info = self.collect(game)
        p = info["player"]
        view = info["view"]
        chat = info["chat"]
        hud = info["hud"]
        fbo = getattr(game.display, "fbo_size", None) if game.display else None
        sidebar = info["sidebar"]
        lines = [
            f"FPS {self.fps:4.1f}  {info['backend']}  {info['gpu'][:28]}",
            f"win {info['window'][0]}x{info['window'][1]}  canvas {info['canvas'][0]}x{info['canvas'][1]}",
            f"scale {self._box(info['rect'])}",
            f"view {self._box(view)}  {game.views.mode}",
            f"HUD {self._box(hud)}  chat {self._box(chat)}",
            f"side {self._box(sidebar)}  off {game.map_offset_y}  cam {game.camera_w}x{game.camera_h}",
            f"player {p.x},{p.y}  chunk {p.chunk_x},{p.chunk_y} z={p.world_z} d={getattr(game.level, 'depth', '?')}",
            f"vis {self.visible_entities} spr {self.sprite_count} fov {self.fov_cells} lights {self.light_sources}",
            f"Visual objects {self.visual_count} (active chunk)",
            f"light {'on' if self.lighting_on else 'off'} fog {'on' if game.views.fog else 'off'} dark {'yes' if self.absolute_darkness else 'no'}",
            f"FBO {fbo[0]}x{fbo[1]}" if fbo else "FBO -",
        ]
        if self.passes:
            parts = [f"{name} {ms:.1f}" for name, ms in list(self.passes.items())[:6]]
            lines.append("ms " + " ".join(parts))
        lines.append("F12 hide  F8 corner  F9 marker  Sh+F9 all")
        for warning in self.warnings[:3]:
            lines.append("! " + warning)
        font = self._font()
        limit = min(460, max(220, info["canvas"][0] // 3))
        wrapped = []
        for line in lines:
            wrapped.extend(self._wrap(font, line, limit - 16) or [""])
        gl = game.display.gl_renderer if game.display else None
        if gl is not None and gl.fbo_rendered:
            lines = wrapped[:17]
            width = min(limit, max((font.size(line)[0] for line in lines), default=80) + 16)
            height = min(info['canvas'][1]-16, len(lines)*16+10)
            x = 8 if self.corner == 'left' else max(8, info['canvas'][0]-width-8)
            self.panel_rect = pygame.Rect(x, 8, width, height)
            gl.draw_rect(self.panel_rect, (6, 10, 16, 188))
            gl.draw_rect_outline(self.panel_rect, (90, 140, 180))
            for i, line in enumerate(lines):
                gl.text_pixels((x+8, 13+i*16), line, (230, 236, 244), 14)
            gl.end()
            return
        rendered = [font.render(line, True, (230, 236, 244)) for line in wrapped[:16]]
        width = min(limit, max((s.get_width() for s in rendered), default=80) + 16)
        height = min(info["canvas"][1] - 16, len(rendered) * 16 + 10)
        panel = pygame.Surface((width, height), pygame.SRCALPHA)
        panel.fill((6, 10, 16, 188))
        pygame.draw.rect(panel, (90, 140, 180), panel.get_rect(), 1)
        for i, surf in enumerate(rendered):
            panel.blit(surf, (8, 5 + i * 16))
        margin = 8
        if self.corner == "left":
            pos = (margin, margin)
        else:
            pos = (max(margin, info["canvas"][0] - width - margin), margin)
        self.panel_rect = pygame.Rect(*pos, width, height)
        game.r.surface.blit(panel, pos)

    @staticmethod
    def _box(rect):
        if rect is None:
            return "-"
        return f"{rect.x},{rect.y} {rect.w}x{rect.h}"

    @staticmethod
    def _wrap(font, text, width):
        if font.size(text)[0] <= width:
            return [text]
        lines, cur = [], ""
        for word in text.split(" "):
            trial = word if not cur else cur + " " + word
            if font.size(trial)[0] <= width:
                cur = trial
            else:
                if cur:
                    lines.append(cur)
                cur = word if font.size(word)[0] <= width else word[:max(8, width // 8)]
        if cur:
            lines.append(cur)
        return lines


class Layout:
    """One geometry for canvas, HUD, scene, sidebar and chat."""

    def __init__(self, canvas, hud, stats, viewport, sidebar, chat, cols, rows):
        self.canvas = canvas
        self.hud = hud
        self.stats = stats
        self.viewport = viewport
        self.sidebar = sidebar
        self.chat = chat
        self.cols = cols
        self.rows = rows

    @property
    def canvas_rect(self):
        return self.canvas

    @property
    def hud_rect(self):
        return self.hud

    @property
    def viewport_rect(self):
        return self.viewport

    @property
    def chat_rect(self):
        return self.chat

    @property
    def sidebar_rect(self):
        return self.sidebar


def compute_layout(game):
    """HUD, scene and chat share one canvas. The 3D frame is scaled inside it."""
    surface = game.r.surface
    width, height = surface.get_size()
    canvas = pygame.Rect(0, 0, width, height)
    top = game.modern_hud.get_height() if game.use_modern_hud else C.TOPBAR_H * game.r.ch
    top = max(0, min(top, max(0, height - game.r.ch)))
    sidebar_w = 0
    if game.sidebar_visible and game.use_modern_hud and game.modern_sidebar is not None:
        sidebar_w = game.modern_sidebar.get_width() + game.modern_hud.theme.SPACING_MD * 2
    elif game.sidebar_visible:
        sidebar_w = C.SIDEBAR_W * game.r.cw
    sidebar_w = min(sidebar_w, max(0, width - game.r.cw))
    available = max(game.r.cw, width - sidebar_w)
    view_h = max(game.r.ch, height - top)
    viewport = pygame.Rect(0, top, available, view_h)
    sidebar = None
    if sidebar_w:
        sidebar = pygame.Rect(width - sidebar_w, top, sidebar_w, view_h)
    margin = max(16, game.r.ch)
    chat_w = min(max(280, width // 3), max(160, width - margin * 2))
    chat_h = min(max(120, game.r.ch * 6), max(80, height // 3))
    chat = pygame.Rect(max(0, width - chat_w - margin), max(0, height - chat_h - margin), chat_w, chat_h)
    # Safe access to panel_rect/stats_rect (they may not be initialized yet)
    hud = getattr(game.modern_hud, 'panel_rect', None) if game.use_modern_hud else pygame.Rect(0, 0, width, top)
    if hud is None:
        hud = pygame.Rect(0, 0, width, top)
    stats = getattr(game.modern_hud, 'stats_rect', None) if game.use_modern_hud else None
    cols = max(1, available // game.r.cw)
    rows = max(1, view_h // game.r.ch)
    return Layout(canvas, hud, stats, viewport, sidebar, chat, cols, rows)


def layout_viewport(game):
    layout = compute_layout(game)
    game.layout = layout
    return layout.viewport, layout.cols, layout.rows


def layout_chat(game):
    layout = getattr(game, "layout", None) or compute_layout(game)
    return layout.chat.copy()
