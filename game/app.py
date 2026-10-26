"""Игровой цикл: состояния, ввод, отрисовка карты, панели, действия игрока."""

from __future__ import annotations

import os
import math
import random
import time
import traceback

import pygame

from engine import config as C
from engine import fov as F
from engine import glyphs as G
from engine.renderer import Renderer
from engine.display import Display, RESOLUTIONS
from engine import window as window_geometry
from engine.views import Views
from engine.widgets import InventoryPanel, Menu, show_lines
from engine.modern_hud import ModernHUD, ModernSidebar
from engine.debug_overlay import DebugOverlay, layout_chat, layout_viewport
from . import ai
from . import ui_settings as _ui_settings
from . import ui_inventory as _ui_inventory
from . import turn_flow as _turn_flow
from . import world_flow as _world_flow
from . import combat
from . import effects
from . import mapgen as MG
from . import monsters as MON
from .audio import Audio
from .entities import Player
from .items import ITEMS, Item, make_random_item
from .level import Level, populate
from .world import World
from .workshop import Workshop
from .rng import RNG
from .lang import (LANG_NAMES, load_settings, other_lang, save_settings,
                   set_lang, t, item_name)
from .controls import ACTION_GROUPS, Actions, Controls
from .action_wheel import ActionWheel
from .save import has_save, load_game, save_game

TITLE = "NET HACK"


class Game:
    def __init__(self, renderer: Renderer, seed=None):
        self.r = renderer
        self.screen = renderer.surface
        self.clock = pygame.time.Clock()
        self.running = True
        self.rng = RNG(seed)
        self.audio = Audio()
        self.audio.init()

        self.player: Player | None = None
        self.level: Level | None = None
        self.world = None
        self.mode = "title"
        self.log: list[tuple[str, tuple]] = []
        self.floats: list[tuple[int, int, str, tuple]] = []
        self.menu: Menu | None = None
        self.menu_cb = None
        self.modal_lines = None
        self.targeting = None
        self.target_pos = (0, 0)
        self.rebind = None
        self.rebind_index = 0
        self.rebind_return = "title"
        self.menu_items = None
        self.tooltip = None
        self.action_wheel = None
        self.inventory_panel = None
        # Alt duplicates middle-mouse camera rotation in 3D/first-person.
        self.alt_camera = False
        self.sidebar_visible = False
        self.hud_action_rects = []
        
        # Modern HUD components
        self.modern_hud = ModernHUD(renderer, t)
        self.modern_sidebar = ModernSidebar(renderer, t)
        self.use_modern_hud = True  # Toggle for testing
        self.debug_enabled = False
        self.debug_overlay = DebugOverlay()
        self.chat_rect = None
        self.viewport_rect = None
        # Поворот ASCII-камеры: 0/90/180/270 градусов по часовой стрелке.
        self.view_rotation = 0
        self.title_index = 0
        self.depth_of_death = 0
        self.start_time = time.time()
        self.crash_tb = None
        self.window_scale = 1
        self.fullscreen = False
        self.window_mode = "auto"
        self.resolution = (1280, 720)
        self.display = None
        self._applying_window = False
        self._window_save_at = 0.0
        self.views = Views()
        from engine.performance import Performance
        self.performance=Performance()
        self.workshop = Workshop(self)
        self._held_move = None
        self._held_move_time = 0.0
        self._held_move_initial_delay = 3.0
        self._held_move_repeat_delay = 0.16
        self._rest_tint_until = 0
        self._slider_start_sleep = False
        self.sleep_setting = 120
        self.sleep_prompt = None
        self.sleep_frame = 0
        self._sleep_timer = 0.0
        self._sleep_auto = False
        self._sleep_ignored = set()
        self._visible_world_key = None
        self.visible_world = {}
        self.views.draw_distance = C.FOV_RADIUS * 4
        self.lamp_flicker_modifier = 1.0
        self._lamp_flicker_timer = 0.0
        self._lamp_flicker_drop = 0.0
        self.msg("", C.MSG_INFO)

        self.ctl = Controls()
        self.actions = Actions()
        load_settings(self)
        self.apply_auto_window()
        self.title_menu = Menu(
            self.r, C.TITLE,
            [t("menu.new_game"), t("menu.continue"), t("menu.settings"),
             t("menu.quit")],
            width=44, box_color=C.C_WALL_EDGE,
        )
        self.refresh_title_menu()

    # ------------------------------------------------------------------
    # Инфраструктура
    # ------------------------------------------------------------------
    def msg(self, text: str, color=C.MSG_INFO):
        if not text:
            return
        self.log.append((text, color))
        if len(self.log) > 220:
            del self.log[:-220]

    def messages(self, text, color=C.MSG_INFO):
        self.msg(text, color)

    def new_game(self):
        self.workshop=Workshop(self)
        self._held_move=None
        self._sleep_auto=False
        self.sleep_prompt=None
        self.player = Player(0, 0)
        self.player.max_hp = self.player.hp = 27
        self._dead = False
        self.win = False
        self.log.clear()
        for world in getattr(self,'worlds',{}).values():
            world.storage.cleanup()
        if self.world is not None and self.world not in getattr(self,'worlds',{}).values():
            self.world.storage.cleanup()
        self.world = World(self.rng.seed)
        self.worlds = {0:self.world}
        self.player.depth = self.player.b_level = 0
        self.player.world_z = 0
        self.player.chunk_x = self.player.chunk_y = 0
        self.level = self.world.chunk(0, 0, 0, visit=True)
        self.views.free_camera = False
        self.views.world_camera = [0, 0, 0]
        lv = self.level
        rooms = lv.rooms
        start = rooms[0].center() if rooms else (5, 5)
        self.player.x, self.player.y = start
        lv.set_player_pos(*start)
        if rooms:
            rooms[0].lit = True
        lv.recompute_fov(*start)
        self.update_lighting(0.0)
        self.msg(t("world.arrive"), C.MSG_GOOD)
        self.msg(t("m.help_hint"), C.MSG_HINT)
        self.msg(t('br.info.0'), C.MSG_HINT)
        self.audio.play_music("game")
        self.mode = "play"

    def make_level(self, depth: int) -> Level:
        lv = Level(depth, C.MAP_W, C.MAP_H, self.rng)
        populate(lv, self.rng)
        # состояние дверей: часть закрыта, часть заперта
        door_tiles = [(x, y) for y in range(lv.h) for x in range(lv.w)
                      if lv.at(x, y) == MG.DOOR]
        vault_doors = []
        for r in lv.rooms:
            if r.purpose == "vault":
                vault_doors = lv.door_tiles(r)
        for pos in door_tiles:
            locked = pos in vault_doors or self.rng.random() < 0.10 + depth * 0.004
            lv.doors[pos] = {"open": False if locked else self.rng.random() < 0.55,
                             "locked": locked, "broken": False}
        if depth > 1:
            lv.set(*lv.stairs_down, MG.STAIR_UP)
        return lv

    # ------------------------------------------------------------------
    # Главный цикл
    # ------------------------------------------------------------------
    def run(self):
        self.r.surface.fill(C.BLACK)
        if self.display:
            self.display.present()
        else:
            pygame.display.update()
        while self.running:
            try:
                dt = self.clock.tick(60) / 1000.0
                timing=time.perf_counter()
                self.handle_events()
                self.flush_window_save()
                self.audio.update_context(self)
                if self.mode == "play":
                    self.tick_floats()
                    self.update(dt)
                else:
                    self.update_menus(dt)
                updated=time.perf_counter()
                self.debug_overlay.begin_frame()
                self.draw()
                self.debug_overlay.tick_fps(dt*1000)
                self.debug_overlay.draw_markers(self)
                self.debug_overlay.draw_panel(self)
                self.performance.draw(self)
                drawn=time.perf_counter()
                if self.display:
                    self.display.present()
                else:
                    pygame.display.flip()
                present_ms=(time.perf_counter()-drawn)*1000
                self.debug_overlay.mark('update', (updated-timing)*1000)
                self.debug_overlay.mark('draw', (drawn-updated)*1000)
                self.debug_overlay.mark('present', present_ms)
                self.performance.record(dt*1000,(updated-timing)*1000,
                                        (drawn-updated)*1000,present_ms)
            except Exception:  # noqa: BLE001 - окно не должно падать молча
                self.crash(traceback.format_exc())
        self.audio.stop_music()

    def crash(self, tb: str):
        """Показываем ошибку вместо молчаливого закрытия окна."""
        self.crash_tb = tb
        self.mode = "crash"
        try:
            path = os.path.join(C.BASE_DIR, "crash.log")
            with open(path, "w", encoding="utf-8") as f:
                f.write(tb)
        except OSError:
            pass
        print(tb)

    def draw_crash(self):
        r = self.r
        sw = r.surface.get_width() // r.cw
        sh = r.surface.get_height() // r.ch
        r.clear((18, 4, 6))
        r.text(sw // 2 - 10, 2, t("error.screen"), C.RED, bold=True)
        r.text(sw // 2 - 20, 3, t("error.log"), C.DARK_GRAY)
        lines = [ln.rstrip() for ln in (self.crash_tb or "").splitlines()]
        for i, line in enumerate(lines[: sh - 8]):
            r.text(1, 5 + i, line[: sw - 2], C.LIGHT_GRAY)
        r.text(sw // 2 - 12, sh - 2, "Esc - title    Q - quit", C.YELLOW)

    def update(self, dt):
        if self._sleep_auto and self.player.is_asleep():
            self._sleep_timer -= dt
            if self._sleep_timer <= 0:
                self._sleep_timer = .15
                self.end_turn()
        elif self._sleep_auto:
            self._sleep_auto = False
        self._held_move_time -= dt
        if self._held_move and not self.player.is_asleep() and self.views.mode != 'board' and self._held_move_time <= 0 and self.mode == 'play':
            action, mod = self._held_move
            entry = self.actions.map.get(action)
            if entry and entry[0] == 'move':
                self._held_move_time = self._held_move_repeat_delay
                self.move(*entry[1], running=bool(mod & pygame.KMOD_SHIFT))
        # Освещение обновляется один раз за кадр, до draw(), а не для каждой
        # грани. Это сохраняет предсказуемое мерцание и не замедляет DDA.
        self._lamp_flicker_timer -= dt
        if self._lamp_flicker_timer <= 0.0:
            self._lamp_flicker_timer = random.uniform(0.35, 2.2)
            self._lamp_flicker_drop = random.uniform(0.08, 0.22) if random.random() < 0.18 else 0.0
        self.lamp_flicker_modifier = max(
            0.1, min(1.0, 0.94 + 0.045 * math.sin(time.time() * 5.2) - self._lamp_flicker_drop)
        )
        # Per-lamp flicker: each fluorescent panel gets its own noisy pattern
        # so the level never blinks in sync.  Level 0 is the only profile
        # that opts in via `lamp_flicker` in levels/*.json.
        profile = getattr(self.level, 'profile', {}) if self.level else {}
        if profile.get('lamp_flicker', False) and self.level is not None:
            t_now = time.time()
            states = getattr(self, '_lamp_states', None)
            if states is None or states.get('_level_id') != id(self.level):
                states = {'_level_id': id(self.level)}
                self._lamp_states = states
            for lamp in self.level.ceiling_lamps:
                # Deterministic per-lamp seed so a specific panel always has
                # the same personality (some strobe, some stay dead).
                seed = hash((lamp, id(self.level))) & 0xFFFF
                rng = random.Random(seed)
                personality = rng.choice(('steady', 'steady', 'hum', 'strobe', 'dying'))
                phase = rng.uniform(0, math.tau)
                if personality == 'steady':
                    value = 1.0
                elif personality == 'hum':
                    value = 0.92 + 0.08 * math.sin(t_now * 5.2 + phase)
                elif personality == 'strobe':
                    # Hard on/off strobe every ~0.6s with a slow drift.
                    value = 1.0 if (t_now * 1.7 + phase) % 1.0 < 0.85 else 0.1
                else:  # dying
                    # Mostly dark, occasionally sputters.
                    cycle = (t_now * 0.3 + phase) % 4.0
                    value = 0.9 if cycle < 0.15 else (0.15 if cycle < 3.0 else 0.0)
                states[lamp] = value
        else:
            self._lamp_states = None
        self.update_lighting(dt)

    def update_lighting(self, dt=0.0):
        if self.level is None or self.player is None:
            return
        weapon = self.player.wielded
        has_lantern = any(it.name == "lantern" and it.equipped for it in self.player.items)
        lamp_states = getattr(self, '_lamp_states', None)
        if lamp_states is not None:
            lamp_states = {k: v for k, v in lamp_states.items() if k != '_level_id'}
        if getattr(self, 'world', None) is not None:
            self.world.update_lighting(self.player, has_lantern, self.lamp_flicker_modifier,
                                       lamp_states=lamp_states)
            return
        self.level.update_lighting(self.player.x, self.player.y, has_lantern,
                                   self.lamp_flicker_modifier, lamp_states=lamp_states)

    def update_menus(self, dt):
        if self.mode=='work':
            self.workshop.update(dt)
            self.update_lighting(dt)
        self._held_move=None

    # ------------------------------------------------------------------
    # Ввод
    # ------------------------------------------------------------------
    def handle_events(self):
        for ev in pygame.event.get():
            if self.display and hasattr(ev, "pos"):
                attrs = dict(ev.dict)
                attrs["pos"] = self.display.position(ev.pos)
                ev = pygame.event.Event(ev.type, attrs)
            if ev.type == pygame.QUIT:
                self.running = False
            elif ev.type == pygame.VIDEORESIZE and not self.fullscreen:
                self.on_window_resize(ev.w, ev.h)
                save_settings(self)
            elif ev.type == pygame.KEYDOWN:
                if getattr(ev,'repeat',False):
                    continue
                if ev.key == pygame.K_q and (ev.mod & pygame.KMOD_CTRL):
                    self.running = False
                    continue
                self.on_key(ev)
            elif ev.type == pygame.KEYUP:
                if ev.key==getattr(self,'_held_move_key',None):
                    self._held_move=None
                action = self.ctl.action_for(ev.key, 0)
                if action and self.actions.map.get(action, (None,))[0] == 'move':
                    self._held_move = None
                if ev.key in (pygame.K_LALT,pygame.K_RALT):
                    self.alt_camera=False
            elif ev.type == pygame.WINDOWFOCUSLOST:
                self._held_move=None
            elif ev.type == pygame.KEYUP and ev.key in (pygame.K_LALT, pygame.K_RALT):
                self.alt_camera = False
            elif ev.type == pygame.TEXTINPUT and self.mode == "text_input":
                self.on_text(ev)
            elif ev.type == pygame.MOUSEBUTTONDOWN:
                self.on_mouse(ev)
            elif ev.type == pygame.MOUSEBUTTONUP and self.mode=='audio_settings':
                self.on_mouse(ev)
            elif ev.type == pygame.MOUSEMOTION:
                self.on_mouse(ev)
            elif ev.type == pygame.MOUSEWHEEL:
                self.on_mouse(ev)

    def on_text(self, ev):
        if self.text_cb:
            self.text_cb(ev.text)
            self.text_cb = None
            self.mode = self.text_mode

    def on_key(self, ev):
        if ev.key==pygame.K_F1 and self.mode=='play' and self.world is not None:
            self.show_level_passages()
            return
        if ev.key==pygame.K_F12:
            self.debug_overlay.toggle()
            return
        if ev.key==pygame.K_F8 and self.mode=='play' and self.debug_overlay.enabled:
            self.debug_overlay.corner = "left" if self.debug_overlay.corner == "right" else "right"
            return
        if ev.key==pygame.K_F9 and self.mode=='play':
            if ev.mod & pygame.KMOD_SHIFT:
                from engine.debug_overlay import MODES
                self.debug_overlay.modes = set(MODES)
                self.debug_overlay.enabled = True
            else:
                self.debug_overlay.cycle_mode()
                self.debug_overlay.enabled = True
            return
        if self.mode in ('build_puzzle','work'):
            self.workshop.key(ev)
            return
        if self.mode=='audio_settings':
            self.audio_settings.key(ev)
            return
        if self.mode=='sleep_slider':
            if ev.key in (pygame.K_LEFT,pygame.K_RIGHT):
                self.sleep_setting=max(10,min(360,self.sleep_setting+(-10 if ev.key==pygame.K_LEFT else 10)))
            elif ev.key in (pygame.K_RETURN,pygame.K_ESCAPE):
                self.finish_sleep_slider(ev.key == pygame.K_RETURN)
            return
        if ev.type == pygame.KEYUP and ev.key in (pygame.K_LALT, pygame.K_RALT):
            self.alt_camera = False
            return
        if (self.mode == 'play' and ev.key in (pygame.K_LALT, pygame.K_RALT)
                and self.views.mode in ('first', 'board')):
            self.alt_camera = True
            return
        if self.mode == 'action_wheel':
            self.key_action_wheel(ev)
            return
        if self.mode == 'inventory':
            if self.key_inventory(ev):
                return
            result = self.inventory_panel.handle_event(ev)
            self.handle_inventory_result(result)
            return
        if self.mode == "play" and self.world is not None and self.views.mode == "board":
            if ev.key in (pygame.K_COMMA, pygame.K_PERIOD):
                if not self.views.free_camera:
                    self.views.world_camera = [self.player.chunk_x,self.player.chunk_y,self.player.world_z]
                self.views.free_camera = True
                z = self.views.world_camera[2] + (-1 if ev.key==pygame.K_COMMA else 1)
                if self.world.exists(z):
                    self.views.world_camera[2] = z
                return
            if ev.key == pygame.K_F8:
                self.views.single_layer = not getattr(self.views,'single_layer',False)
                save_settings(self)
                return
            if self.views.free_camera:
                directions = {}
                if ev.key in directions:
                    candidate = [a+b for a,b in zip(self.views.world_camera, directions[ev.key])]
                    if self.world.exists(candidate[2]):
                        self.views.world_camera = candidate
                    return
        if self.mode == 'play' and self.views.mode != 'board' and self.player.debug_fly and ev.key in (pygame.K_PAGEUP, pygame.K_PAGEDOWN):
            self.debug_change_z(1 if ev.key == pygame.K_PAGEUP else -1)
            return
        if ev.key == pygame.K_F11:
            self.toggle_fullscreen()
            save_settings(self)
            return
        if self.mode == "play":
            if ev.key in (pygame.K_F5, pygame.K_F6, pygame.K_F7):
                self.views.mode = {pygame.K_F5: "ascii", pygame.K_F6: "first", pygame.K_F7: "board"}[ev.key]
                self.tooltip = None
                save_settings(self)
                return
            if self.views.mode != "ascii" and getattr(getattr(self, "display", None), "backend", None):
                if ev.key in (pygame.K_LEFT, pygame.K_RIGHT):
                    self._held_move=None
                    self.views.turn(-math.pi / 12 if ev.key == pygame.K_LEFT else math.pi / 12)
                    return
                if ev.key in (pygame.K_PAGEUP, pygame.K_PAGEDOWN):
                    if self.views.mode == 'first':
                        self.views.pitch = max(-1.45, min(1.45, self.views.pitch + (0.12 if ev.key == pygame.K_PAGEUP else -0.12)))
                    else:
                        self.views.tilt = max(-1.57, min(1.57, self.views.tilt + (0.12 if ev.key == pygame.K_PAGEUP else -0.12)))
                    return
                if ev.key == pygame.K_HOME:
                    self.views.zoom, self.views.tilt, self.views.orbit = 1.0, 0.85, 0.65
                    self.views.pitch = 0.0
                    return
        if self.mode == "title":
            self.key_title(ev)
        elif self.mode == "modal":
            self.key_modal(ev)
        elif self.mode == "target":
            self.key_target(ev)
        elif self.mode == "rebind":
            self.key_rebind(ev)
        elif self.mode == "text_input":
            if ev.key == pygame.K_ESCAPE:
                self.text_cb = None
                self.mode = "play"
        elif self.mode == "play":
            self.key_play(ev)
        elif self.mode == "dead":
            if ev.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE):
                self.audio.stop_music()
                self.mode = "title"
                self.title_index = 0
        elif self.mode == "crash":
            if ev.key == pygame.K_ESCAPE:
                self.audio.stop_music()
                self.crash_tb = None
                self.mode = "title"
                self.title_index = 0
            elif ev.key in (pygame.K_q, pygame.K_ESCAPE + 1000):
                self.running = False

    def refresh_title_menu(self):
        from .lang import get_lang
        lang = get_lang()
        self.title_menu.entries = [
            t("menu.new_game"),
            t("menu.continue"),
            t("menu.settings"),
            t("menu.quit"),
        ]
        self.title_menu.index = min(self.title_menu.index, len(self.title_menu.entries) - 1)

    def open_settings(self):

        return _ui_settings.open_settings(self)

    def open_debug(self):

        return _ui_settings.open_debug(self)

    def debug_change_z(self, delta):

        return _world_flow.debug_change_z(self, delta)

    def apply_auto_window(self):
        """Автоматический режим: окно подгоняется под экран при запуске."""
        if self.window_mode != "auto" or self.fullscreen:
            return
        self.resolution = window_geometry.fit_window_size(window_geometry.desktop_size())

    def center_window(self):
        """Ставит окно по центру экрана, не выходя за его края."""
        try:
            size = tuple(self.display.size)
            x, y = window_geometry.center_position(size, window_geometry.desktop_size())
            pygame.display.set_window_position((x, y))
        except Exception:
            pass

    def on_window_resize(self, width, height):
        """Живое изменение размера окна: канва и viewport без set_mode."""
        if self._applying_window or self.display is None:
            return
        size = (max(320, int(width)), max(240, int(height)))
        self.resolution = size
        self.window_mode = "fixed"
        changed = self.display.apply_window_resize(size)
        self.screen = self.r.surface
        if changed:
            self.r.gl_renderer = self.display.gl_renderer
            gl = getattr(self.display, "gl_renderer", None)
            if gl is not None:
                self.modern_hud._gl = gl
                self.modern_sidebar._gl = gl
            recalc = getattr(self.modern_hud, "calculate_layout", None)
            if recalc is not None:
                recalc(self.r.surface.get_width())
            self.modern_sidebar.get_width()
            if hasattr(self.views, "invalidate"):
                self.views.invalidate()
        self._window_save_at = time.time() + 0.6

    def flush_window_save(self):
        """Сохраняет геометрию окна один раз, когда пользователь закончил тянуть."""
        if self._window_save_at and time.time() >= self._window_save_at:
            self._window_save_at = 0.0
            save_settings(self)

    def resize_window(self):
        if self.display is None:
            self.display = Display(self.r)
            self.display.backend = getattr(self,'presentation_backend','software')
        self._applying_window = True
        try:
            self.display.configure(self.resolution, self.fullscreen)
        finally:
            self._applying_window = False
        self.fullscreen = self.display.fullscreen
        self.screen = self.r.surface
        if not self.fullscreen:
            self.resolution = tuple(self.display.size)
            self.center_window()
        # Rebuild HUD with GL-accelerated renderer if available.
        renderer = self.display.gl_renderer or self.r
        # Inject gl_renderer into base renderer so it can delegate calls
        self.r.gl_renderer = self.display.gl_renderer
        self.modern_hud = ModernHUD(renderer, t)
        self.modern_sidebar = ModernSidebar(renderer, t)
        # GLRenderer injection for pixel-based HUD drawing.
        gl = getattr(self.display, 'gl_renderer', None)
        if gl is not None:
            self.modern_hud._gl = gl
            self.modern_sidebar._gl = gl
        if hasattr(self.views, 'invalidate'):
            self.views.invalidate()

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        self.resize_window()

    def open_resolution(self):

        return _ui_settings.open_resolution(self)

    def open_graphics(self, index=0):

        return _ui_settings.open_graphics(self, index)

    # --- настройка управления ---------------------------------------------
    def open_control_presets(self):

        return _ui_settings.open_control_presets(self)

    def open_controls(self, start_index=0):

        return _ui_settings.open_controls(self, start_index)

    def start_rebind(self, action: str, index: int = 0):

        return _ui_settings.start_rebind(self, action, index)

    def _finish_rebind(self):

        return _ui_settings._finish_rebind(self)

    def key_rebind(self, ev):

        return _ui_settings.key_rebind(self, ev)

    def draw_rebind(self):

        return _ui_settings.draw_rebind(self)

    def toggle_mute_sound(self):

        return _ui_settings.toggle_mute_sound(self)

    def toggle_language(self):

        return _ui_settings.toggle_language(self)

    # --- заголовок --------------------------------------------------------
    def key_title(self, ev):
        res = self.title_menu.handle(ev)
        self.audio.play("menu", 0.4)
        if res == "ok":
            choice = self.title_menu.index
            if choice == 0:
                self.new_game()
            elif choice == 1:
                if load_game(C.SAVE_PATH, self):
                    self.msg(t("m.loaded"), C.MSG_GOOD)
                    self.audio.play_music("game")
                else:
                    self.msg(t("m.no_save"), C.MSG_BAD)
            elif choice == 2:
                self.open_settings()
            elif choice == 3:
                self.running = False
        elif ev.key == pygame.K_ESCAPE:
            self.running = False

    # --- модальные окна ----------------------------------------------------
    def key_modal(self, ev):
        if self.modal_kind == "menu":
            res = self.menu.handle(ev)
            if res == "ok":
                idx = self.menu.index
                cb, self.menu_cb = self.menu_cb, None
                self.close_modal()
                if cb:
                    cb(idx)
            elif res == "cancel":
                cb, self.menu_cb = self.menu_cb, None
                self.close_modal()
                if cb:
                    cb(None)
            else:
                self.audio.play("select", 0.25)
            # быстрые действия и цифровой выбор
            self.modal_quick(ev)
        else:
            if ev.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE):
                self.close_modal()

    def modal_quick(self, ev):
        """Цифры выбирают пункт, буквы выполняют быстрые действия меню."""
        menu = self.menu
        if menu is None:
            return
        idx = menu.digit(ev.key)
        if idx is not None and idx < len(menu.entries):
            cb, self.menu_cb = self.menu_cb, None
            menu.index = idx
            self.close_modal()
            if cb:
                cb(idx)
            self.audio.play("select", 0.5)
            return
        quick = menu.quick.get((ev.key, bool(ev.mod & pygame.KMOD_SHIFT)))
        if quick is None:
            return
        action, kind = quick
        items = getattr(self, "menu_items", None) or []
        item = self._find_item(items, kind)
        if item is None:
            self.audio.play("error", 0.4)
            return
        self.menu_items = None
        self.menu_cb = None
        self.close_modal()
        getattr(self, action)(item)

    def _find_item(self, items, kind: str):
        if not items:
            return None
        if kind == "any":
            return items[0]
        if kind == "equipped":
            for it in items:
                if it.equipped:
                    return it
            return None
        for it in items:
            if it.kind == kind:
                return it

    INVENTORY_QUICK = {
        (pygame.K_q, False): ("do_quaff", "potion"),
        (pygame.K_e, False): ("do_eat", "food"),
        (pygame.K_r, False): ("do_read", "scroll"),
        (pygame.K_z, False): ("open_zap", "wand"),
        (pygame.K_x, False): ("do_wield", "weapon"),
        (pygame.K_w, True): ("do_wear", "armor"),
        (pygame.K_t, True): ("do_takeoff", "equipped"),
        (pygame.K_d, True): ("do_drop", "any"),
        (pygame.K_i, False): ("show_item_info", "any"),
    }

    DIGIT_KEYS = {
        pygame.K_1: 0, pygame.K_2: 1, pygame.K_3: 2, pygame.K_4: 3, pygame.K_5: 4,
        pygame.K_6: 5, pygame.K_7: 6, pygame.K_8: 7, pygame.K_9: 8, pygame.K_0: 9,
    }

    def key_inventory(self, ev) -> bool:
        """Быстрые клавиши и цифровой выбор в современном инвентаре."""
        if ev.type != pygame.KEYDOWN:
            return False
        panel = self.inventory_panel
        if panel is None:
            return False
        digit = self.DIGIT_KEYS.get(ev.key)
        if digit is not None and not ev.mod & pygame.KMOD_SHIFT:
            if digit < len(panel.items):
                panel.selected = digit
                self.audio.play("select", 0.5)
                self.handle_inventory_result(("actions", panel.items[digit]))
            return True
        quick = self.INVENTORY_QUICK.get((ev.key, bool(ev.mod & pygame.KMOD_SHIFT)))
        if quick is None:
            return False
        action, kind = quick
        item = self._find_item(panel.items, kind)
        if item is None:
            self.audio.play("error", 0.4)
            return True
        self.handle_inventory_result("close")
        if action.startswith("open_"):
            getattr(self, action)(pre=item)
        elif action == "show_item_info":
            self.show_item_info(item)
        else:
            getattr(self, action)(item)
        return True

    def close_modal(self):
        self.menu = None
        self.modal_lines = None
        self.mode = self.modal_return
        self.modal_kind = None
        if hasattr(self.views, 'invalidate'):
            self.views.invalidate()

    def show_menu(self, title, entries, cb, start_index=0, width=None):
        self._held_move=None
        self.menu = Menu(self.r, title, entries, width=width, start_index=start_index)
        self.menu_cb = cb
        self.modal_return = self.mode
        self.modal_kind = "menu"
        self.mode = "modal"
        if hasattr(self.views, 'invalidate'):
            self.views.invalidate()
        self.audio.play("menu", 0.5)

    def show_text(self, title, lines):
        self._held_move=None
        self.modal_lines = (title, lines)
        self.modal_return = self.mode
        self.modal_kind = "text"
        self.mode = "modal"

    def ask_text(self, prompt, cb):
        """Однострочный ввод текста (например, имя героя)."""
        self.prompt = prompt
        self.text_cb = cb
        self.text_mode = "play"
        self.mode = "text_input"

    # --- прицеливание ------------------------------------------------------
    def key_target(self, ev):
        p = self.player
        action = self.ctl.action_for(ev.key, ev.mod)
        entry = self.actions.map.get(action) if action else None
        if entry and entry[0] == "move":
            dx, dy = entry[1]
        else:
            dx, dy = (0, 0)
        if dx or dy:
            nx = min(self.level.w - 1, max(0, self.target_pos[0] + dx))
            ny = min(self.level.h - 1, max(0, self.target_pos[1] + dy))
            self.target_pos = (nx, ny)
            self.audio.play("select", 0.2)
        elif ev.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
            pos = self.target_pos
            purpose, cb = self.targeting, None
            self.targeting = None
            self.mode = "play"
            cb = getattr(self, "_do_" + purpose)
            cb(pos[0], pos[1])
        elif ev.key == pygame.K_ESCAPE:
            self.targeting = None
            self.mode = "play"
            self.msg(t("m.cancelled"), C.MSG_HINT)

    def start_target(self, purpose):
        self._held_move=None
        self.targeting = purpose
        self.target_pos = (self.player.x, self.player.y)
        self.mode = "target"

    # ------------------------------------------------------------------
    # Игровые клавиши
    # ------------------------------------------------------------------
    def key_play(self, ev):
        if self.views.mode == 'board':
            action = self.ctl.action_for(ev.key, ev.mod)
            if action not in {'settings','help','inventory','char_sheet','save','save_quit',
                              'lang_toggle','sound_toggle','toggle_status'}:
                return
        p = self.player
        if not p.alive:
            self.mode = "dead"
            return

        action = self.ctl.action_for(ev.key, ev.mod)
        if action is None:
            return
        entry = self.actions.map.get(action)
        if ev.type == pygame.KEYDOWN and entry and entry[0] == 'move':
            self._held_move = (action, ev.mod)
            self._held_move_key=ev.key
            self._held_move_time = self._held_move_initial_delay
        safe_actions = {"settings", "help", "inventory", "char_sheet", "save",
                        "save_quit", "lang_toggle", "sound_toggle",
                        "rotate_left", "rotate_right", "action_menu", "toggle_status"}
        if p.status.get("asleep", 0) > 0 and action not in safe_actions:
            self.audio.play("select", 0.3)
            self.end_turn()
            return

        # движение вызывает конец хода само, остальные команды - нет
        action = self.ctl.action_for(ev.key, ev.mod)
        if action is None:
            return
        entry = self.actions.map.get(action)
        if entry and entry[0] == 'move':
            # Diagonals can use two held ordinary directions instead of dedicated keys.
            pressed = pygame.key.get_pressed()
            dx, dy = entry[1]
            for direction, (mx, my) in (('move_north', (0, -1)), ('move_south', (0, 1)),
                                         ('move_west', (-1, 0)), ('move_east', (1, 0))):
                if direction == action:
                    continue
                if any(pressed[key] for mod, key in self.ctl.bindings.get(direction, ())
                       if mod == 0):
                    if dx == 0 and mx:
                        dx = mx
                    if dy == 0 and my:
                        dy = my
            self.move(dx, dy, running=bool(ev.mod & pygame.KMOD_SHIFT))
            return
        self.actions.run(self, action)

    # ------------------------------------------------------------------
    # Действия игрока
    # ------------------------------------------------------------------
    def move(self, dx, dy, running=False):
        # Camera-relative walking only applies once a window is presented.
        if self.views.mode == "first" and getattr(getattr(self, "display", None), "backend", None):
            angle = round(self.views.yaw / (math.pi / 4)) * math.pi / 4
            fx, fy = round(math.cos(angle)), round(math.sin(angle))
            dx, dy = max(-1, min(1, -dy*fx-dx*fy)), max(-1, min(1, -dy*fy+dx*fx))
        if self.player.status.get("confused", 0) > 0:
            self.player.status["confused"] -= 1
            if self.player.status["confused"] == 0:
                self.msg(t("m.confused_off"), C.MSG_INFO)
            if self.rng.random() < 0.5:
                dx, dy = -dx, -dy
            self.msg(t("m.stumble"), C.MSG_WARN)
        if not running:
            return self.step_to(self.player.x + dx, self.player.y + dy)
        from . import survival
        count = survival.sprint_length(self.player, self.rng)
        self._movement_batch = True
        self._running_step = True
        try:
            for _ in range(count):
                p = self.player
                before = (p.chunk_x, p.chunk_y, p.x, p.y)
                self.step_to(p.x + dx, p.y + dy)
                after = (p.chunk_x, p.chunk_y, p.x, p.y)
                if before == after or not p.alive or p.is_asleep() or self.mode != 'play':
                    break
        finally:
            self._movement_batch = False
            self._running_step = False
        self.end_turn()
        return True

    def step_to(self, nx, ny) -> bool:
        """Перешагнуть в клетку: бой, двери, стены, пол."""
        p, lv = self.player, self.level
        if lv.furniture_at(nx,ny) is not None and not lv.furniture_at(nx,ny).spec.get('damage'):
            self._held_move=None
            self.msg('Здесь мебель. Tab → Мир → Мастерская.',C.MSG_HINT)
            return False
        if p.is_asleep():
            self.end_turn()
            return True
        if getattr(self, "world", None) is not None and lv.depth == 0 and not lv.in_bounds(nx, ny):
            return self.cross_chunk(nx, ny)
        if not lv.in_bounds(nx, ny) and not p.debug_fly:
            self.msg(t("m.wall"), C.MSG_HINT)
            self.audio.play("door_bump", 0.4)
            self.end_turn()
            return True
        target = lv.monster_at(nx, ny)
        if target is not None:
            self.player_attack(target)
            self.end_turn()
            return True
        if lv.is_wall(nx, ny) and not p.debug_noclip:
            if p.wielded is not None and p.wielded.name == "pick-axe":
                if lv.dig_near(p.x, p.y, radius=2, target=(nx, ny)):
                    self.audio.play("door")
                    self.end_turn()
                    self.update_lighting()
                    return True
            if lv.at(nx, ny) == MG.HEDGE:
                self.msg(t("m.hedge"), C.MSG_WARN)
            else:
                self.msg(t("m.wall"), C.MSG_HINT)
            self.audio.play("door_bump", 0.35)
            self.end_turn()
            return True
        if lv.at(nx, ny) == MG.DOOR:
            d = lv.doors.setdefault((nx, ny),
                                    {"open": False, "locked": False, "broken": False})
            if not d.get("open") and not d.get("broken"):
                d["open"] = True
                lv.geometry_revision += 1
                self.msg(t("m.open_door"), C.MSG_INFO)
                self.audio.play("door")
                self.end_turn()
                return True
        if (nx, ny) in lv.corpses and self.rng.random() < 0.3:
            self.msg(t("m.corpse"), C.MSG_HINT)
        p.x, p.y = nx, ny
        from . import survival
        swimming = lv.at(nx, ny) == MG.WATER
        if swimming:
            p.status['swimming'] = 1
            p.stamina = max(-survival.STAMINA_MAX, p.stamina - (2 if getattr(self, '_running_step', False) else 1))
        else:
            p.status.pop('swimming', None)
        survival.movement(p, running=getattr(self, '_running_step', False))
        lv.set_player_pos(nx, ny)
        self.audio.play("step", 0.18)
        lv.recompute_fov(nx, ny)
        self.update_lighting(0.0)
        if p.alive:
            self.check_tile(nx, ny)
        self.end_turn()
        return True

    # --- управление мышью ---------------------------------------------------
    def on_mouse(self, ev):
        if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==3 and self.mode in ('modal','target','rebind','sleep_slider','audio_settings','work','action_wheel'):
            self.on_key(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_ESCAPE,mod=0))
            return
        if self.mode=='title' and ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1:
            if self.title_menu.handle_click(*self.r.cell_at(*ev.pos))=='ok':
                self.key_title(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_RETURN,mod=0))
            return
        if self.mode == 'inventory':
            panel = self.inventory_panel
            if ev.type == pygame.MOUSEWHEEL and panel is not None:
                if panel.items:
                    step = 1 if ev.y > 0 else -1
                    panel.selected = max(0, min(len(panel.items) - 1,
                                                (panel.selected or 0) + step))
                return
            result = panel.handle_event(ev)
            self.handle_inventory_result(result)
            return
        if (self.mode == 'play' and ev.type == pygame.MOUSEBUTTONDOWN
                and ev.button == 1):
            for rect, action in getattr(self, 'hud_action_rects', ()):
                if rect.collidepoint(ev.pos):
                    self.actions.run(self, action)
                    return
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button not in (1,3):
            # Legacy wheel buttons 4/5 and middle click are never actions.
            # Camera drag uses MOUSEMOTION; scrolling uses MOUSEWHEEL.
            return
        if self.mode in ('build_puzzle','work'):
            self.workshop.mouse(ev)
            return
        if self.mode=='audio_settings':
            self.audio_settings.mouse(ev)
            return
        if self.mode=='sleep_slider':
            if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1:
                if self.r.cell_rect(3,8,24,2).collidepoint(ev.pos):
                    self.finish_sleep_slider(True)
                    return
            if ev.type==pygame.MOUSEBUTTONDOWN or (ev.type==pygame.MOUSEMOTION and getattr(ev,'buttons',(0,))[0]):
                bar=self.sleep_slider_rect()
                if bar.inflate(0,40).collidepoint(ev.pos):
                    self.sleep_setting=max(10,min(360,round((10+350*(ev.pos[0]-bar.x)/bar.w)/10)*10))
            return
        if self.mode == 'action_wheel':
            if ev.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN):
                selected = self.action_wheel.pick(ev.pos)
                if selected is not None:
                    self.action_wheel.selected = selected
                if ev.type == pygame.MOUSEBUTTONDOWN:
                    if ev.button == 1 and selected is not None:
                        self.choose_wheel(selected)
                    elif ev.button in (2, 3):
                        self.close_action_wheel()
            elif ev.type == pygame.MOUSEWHEEL:
                self.action_wheel.selected = (self.action_wheel.selected - ev.y) % self.action_wheel.count
            return
        if ev.type == pygame.MOUSEWHEEL:
            if self.menu is not None:
                self.menu.wheel(ev.y)
            elif self.mode == "play":
                if self.views.mode == "board":
                    self.views.zoom = max(0.5, min(5, self.views.zoom * 1.15 ** ev.y))
                elif self.views.mode == "first":
                    self._held_move=None
                    self.views.turn(ev.y * math.pi / 12)
                elif ev.y:
                    self.rotate_view(1 if ev.y > 0 else -1)
            return
        if self.mode in ("play", "target") and self.views.mode != "ascii":
            if ev.type == pygame.MOUSEMOTION:
                if getattr(ev, "buttons", (0, 0, 0))[1] or getattr(self, 'alt_camera', False):
                    self._held_move=None
                    if self.views.mode == 'first':
                        self.views.turn(ev.rel[0] * 0.008)
                        self.views.pitch = max(-1.45, min(1.45, self.views.pitch - ev.rel[1] * 0.006))
                    else:
                        self.views.turn(ev.rel[0] * 0.008)
                        self.views.tilt = max(-1.57, min(1.57, self.views.tilt + ev.rel[1] * 0.008))
                return
            if ev.type == pygame.MOUSEBUTTONDOWN and self.in_view(*self.r.cell_at(*ev.pos)):
                pos = self.views.board_pick(ev.pos) if self.views.mode == "board" else self.views.pick(ev.pos)
                if pos:
                    if ev.button == 3:
                        self.inspect(*pos, ttl=300)
                        if self.tooltip is not None:
                            self.tooltip["anchor"] = self.r.cell_at(*ev.pos)
                    elif ev.button == 1:
                        if self.views.mode == 'board':
                            return
                        if self.mode == "target":
                            self.target_pos = pos
                return
        if ev.type != pygame.MOUSEBUTTONDOWN:
            if ev.type == pygame.MOUSEMOTION and self.mode == "play":
                # Update hover states for modern HUD
                if self.use_modern_hud:
                    self.modern_hud.handle_mouse_motion(ev.pos)
                self.modern_sidebar.handle_mouse_motion(ev.pos)
                
                col, row = self.r.cell_at(ev.pos[0], ev.pos[1])
                if self.in_view(col, row):
                    wx, wy = self.screen_to_world(col, row - self.map_offset_y)
                    if self.level.in_bounds(wx, wy) and (wx, wy) in self.level.visible:
                        self.inspect(wx, wy, ttl=8)
                return
            return
        col, row = self.r.cell_at(ev.pos[0], ev.pos[1])
        if self.menu is not None:
            if ev.button != 1:
                return
            res = self.menu.handle_click(col, row)
            if res == "ok":
                idx = self.menu.index
                cb, self.menu_cb = self.menu_cb, None
                self.close_modal()
                if cb:
                    cb(idx)
                self.audio.play("select", 0.5)
            else:
                self.audio.play("select", 0.2)
            return
        if self.mode == "target":
            if ev.button == 1 and self.in_view(col, row):
                self.target_pos = self.screen_to_world(col, row - self.map_offset_y)
            return
        if self.mode != "play":
            return
        
        # Handle clicks on modern sidebar action buttons
        if self.use_modern_hud and self.modern_sidebar.visible:
            action = self.modern_sidebar.handle_click(ev.pos)
            if action:
                self.audio.play("select", 0.3)
                method = getattr(self, action, None)
                if callable(method):
                    method()
                return
        
        if not self.in_view(col, row):
            return
        wx, wy = self.screen_to_world(col, row - self.map_offset_y)
        if ev.button == 3:
            self.inspect(wx, wy, ttl=150)

    def in_view(self, col, row):
        # Calculate top offset based on HUD mode
        top_offset = self.map_offset_y
        return 0 <= col < self.camera_w and top_offset <= row < top_offset + self.camera_h

    def _sync_layout(self):
        rect, cols, rows = layout_viewport(self)
        self.viewport_rect = rect
        self._layout_cols = cols
        self._layout_rows = rows
        return rect, cols, rows

    @property
    def camera_w(self):
        return self._sync_layout()[1]

    @property
    def camera_h(self):
        """ASCII rows that fit under the HUD. The pixel view uses the rest."""
        return self._sync_layout()[2]

    @property
    def map_offset_y(self):
        """First map row. Modern HUD uses its real pixel height, not a guess."""
        if self.use_modern_hud:
            return max(0, self.modern_hud.get_height() // self.r.ch)
        return C.TOPBAR_H

    def toggle_status(self):
        self.sidebar_visible = not self.sidebar_visible
        # Sync with modern sidebar
        if self.use_modern_hud and self.modern_sidebar:
            self.modern_sidebar.visible = self.sidebar_visible
        self.tooltip = None
        self.views.picks.clear()
        save_settings(self)

    def interact(self):
        if self.player.is_asleep():
            self.end_turn()
            return
        if self.use_level_exit():
            return
        if self.workshop.neighbours():
            self.workshop.open_nearby()
            return
        tile = self.level.at(self.player.x,self.player.y)
        if self.ctl.preset == 'newcomer' and tile in (MG.STAIR_UP, MG.STAIR_DOWN):
            if tile == MG.STAIR_UP:
                self.ascend()
            else:
                self.descend()
            return
        if self.level.item_at(self.player.x, self.player.y):
            if self.pickup():
                self.end_turn()
        else:
            self.open_action_wheel()

    def open_action_wheel(self):
        self.tooltip = None
        self.action_wheel = ActionWheel(self.r)
        self.mode = 'action_wheel'
        if hasattr(self.views, 'invalidate'):
            self.views.invalidate()

    def close_action_wheel(self):
        self.action_wheel = None
        self.mode = 'play'
        if hasattr(self.views, 'invalidate'):
            self.views.invalidate()

    def key_action_wheel(self, ev):
        if ev.key in (pygame.K_ESCAPE, pygame.K_TAB):
            self.close_action_wheel()
        elif pygame.K_1 <= ev.key <= pygame.K_9:
            self.choose_wheel(ev.key - pygame.K_1)
        elif ev.key in (pygame.K_RETURN, pygame.K_SPACE):
            self.choose_wheel(self.action_wheel.selected)
        elif ev.key in (pygame.K_LEFT, pygame.K_UP, pygame.K_RIGHT, pygame.K_DOWN):
            delta = -1 if ev.key in (pygame.K_LEFT, pygame.K_UP) else 1
            self.action_wheel.selected = (self.action_wheel.selected + delta) % self.action_wheel.count

    def choose_wheel(self, index):
        option = self.action_wheel.options[index]
        self.close_action_wheel()
        direct = {'inventory': 'inventory', 'food': 'eat',
                  'drink': 'quaff', 'character': 'char_sheet'}
        if option in direct:
            self.key_play_action(direct[option])
            return
        groups = {
            'equipment': ('wield', 'wear', 'takeoff', 'drop', 'swap_weapon', 'read'),
            'combat': ('force_fight', 'fire', 'throw', 'zap'),
            'world': ('passages', 'workshop', 'interact', 'pickup_all', 'items_here', 'pick_lock',
                      'view_map', 'lights', 'descend', 'ascend', 'toggle_status'),
            'system': ('settings', 'save', 'save_quit'),
            'sleep': ('sleep', 'rest', 'wait'),
        }
        actions = groups[option]

        def choose(idx):
            if idx is not None:
                self.key_play_action(actions[idx])

        self.show_menu(t('wheel.' + option), [t('a.' + action) for action in actions], choose)

    def key_play_action(self, action):
        if self.views.mode == 'board' and action not in ('toggle_status','settings','save',
                                                        'inventory','char_sheet','help','view_map'):
            return
        # Menu commands share the same sleep restriction as keyboard commands.
        if self.player.is_asleep() and action not in ('toggle_status', 'settings', 'save',
                                                     'inventory', 'char_sheet'):
            self.end_turn()
            return
        self.actions.run(self, action)

    def open_workshop(self):
        self.workshop.open()

    def show_3d_map(self):
        self.views.mode = 'board'
        self.tooltip = None
        save_settings(self)

    def click_map(self, wx, wy):
        if self.views.mode == 'board':
            return
        """Левый клик по карте: пройти туда или ударить."""
        p, lv = self.player, self.level
        if p.is_asleep():
            self.end_turn()
            return
        if (wx, wy) not in lv.visible:
            return
        if (wx, wy) == (p.x, p.y):
            self.wait()
            return
        if max(abs(wx - p.x), abs(wy - p.y)) <= 1:
            m = lv.monster_at(wx, wy)
            if m is not None:
                self.player_attack(m)
                self.end_turn()
                return
        step = lv.next_step(p.x, p.y, wx, wy)
        if step is None:
            self.msg(t("mouse.blocked"), C.MSG_HINT)
            self.audio.play("error", 0.3)
            return
        self.step_to(*step)

    def inspect(self, wx, wy, ttl=150):
        """Правый клик: показать, что в клетке."""
        lv, p = self.level, self.player
        display_x, display_y = wx, wy
        if getattr(self,'world',None) is not None:
            cell = getattr(self, "visible_world", {}).get((wx,wy))
            if cell is not None:
                lv, wx, wy = cell
        if not lv.in_bounds(wx, wy):
            self.tooltip = None
            return
        lines = []
        if (wx, wy) in lv.visible:
            m = lv.monster_at(wx, wy)
            if m is not None:
                lines.append((f"{m.title}  {t('ui.bars')} {m.hp}/{m.max_hp}  "
                              f"{t('ui.lbl.ac')} {m.ac_total}", m.color))
                near = max(abs(display_x - p.x), abs(display_y - p.y)) <= 1
                lines.append((t("mouse.can_hit" if near else "mouse.far"),
                              C.WHITE if near else C.GRAY))
            it = lv.item_at(wx, wy)
            if it is not None:
                lines.append((it.label(), it.color))
        lines.append((lv.describe_tile(wx, wy), C.GRAY))
        lines.append((f"({wx},{wy})", C.DARK_GRAY))
        self.tooltip = {"lines": lines, "x": display_x, "y": display_y, "ttl": ttl}

    def draw_tooltip(self):
        tip = self.tooltip
        if tip is None:
            return
        r = self.r
        sw = r.surface.get_width() // r.cw
        sh = r.surface.get_height() // r.ch
        pos = self.world_to_screen(tip["x"], tip["y"]) if self.views.mode == "ascii" else (2, 3)
        if pos is None:
            return
        col = pos[0] + 2
        row = pos[1] + self.map_offset_y - 2
        if "anchor" in tip:
            col, row = tip["anchor"]
        w = max(len(txt) for txt, _ in tip["lines"]) + 4
        h = len(tip["lines"]) + 2
        col = max(1, min(col, sw - w - 2))
        row = max(self.map_offset_y, min(row, sh - h - 1))
        r.fill_rect(col, row, w, h, (20, 16, 26))
        r.box(col, row, w, h, C.C_WALL_EDGE)
        for i, (txt, color) in enumerate(tip["lines"]):
            r.text(col + 2, row + 1 + i, txt[: w - 4], color)

    def player_attack(self, monster, level=None):

        return _turn_flow.player_attack(self, monster, level)

    def force_attack(self) -> bool:

        return _turn_flow.force_attack(self)

    def on_kill(self, monster, level=None):

        return _turn_flow.on_kill(self, monster, level)

    def wait(self):

        return _turn_flow.wait(self)

    def rest(self):

        return _turn_flow.rest(self)

    def sleep(self):

        return _turn_flow.sleep(self)

    def finish_sleep_slider(self, confirm):

        return _turn_flow.finish_sleep_slider(self, confirm)

    def start_sleep(self):

        return _turn_flow.start_sleep(self)

    def swap_weapon(self):
        current = self.player.wielded
        weapon = next((it for it in self.player.items
                       if it.kind == "weapon" and it is not current), None)
        if weapon is None:
            self.msg(t("m.no_spare_weapon"), C.MSG_HINT)
            return False
        self.do_wield(weapon)

    # --- предметы ----------------------------------------------------------
    def pickup(self) -> bool:
        p, lv = self.player, self.level
        it = lv.item_at(p.x, p.y)
        if it is None:
            self.msg(t("m.nothing_here"), C.MSG_HINT)
            return False
        if len(p.items) >= 26:
            self.msg(t("m.pack_full"), C.MSG_BAD)
            return False
        lv.items.pop((p.x, p.y), None)
        p.items.append(it)
        if it.kind == "gold":
            p.gold += it.qty
            self.msg(t("m.pickup_gold", n=it.qty), C.MSG_GOOD)
            self.audio.play("gold")
        else:
            self.msg(t("m.pickup", it=it.label()), C.MSG_GOOD)
            self.audio.play("pickup")
        return True

    def cross_chunk(self, nx, ny):

        return _world_flow.cross_chunk(self, nx, ny)

    def move_monster_cross_chunk(self, monster, nx, ny, source=None):

        return _world_flow.move_monster_cross_chunk(self, monster, nx, ny, source)

    def pickup_all(self) -> bool:
        p, lv = self.player, self.level
        here = [it for (x, y), it in list(lv.items.items()) if (x, y) == (p.x, p.y)]
        if not here:
            self.msg(t("m.nothing_here"), C.MSG_HINT)
            return False
        for it in here:
            lv.items.pop((p.x, p.y), None)
            if it.kind == "gold":
                p.gold += it.qty
            else:
                p.items.append(it)
        self.msg(t("m.pickup_many", n=len(here)), C.MSG_GOOD)
        self.audio.play("pickup")
        return True

    def _item_labels(self, items):

        return _ui_inventory._item_labels(self, items)

    def open_inventory(self):

        return _ui_inventory.open_inventory(self)

    def handle_inventory_result(self, result):

        return _ui_inventory.handle_inventory_result(self, result)

    # быстрые клавиши на экране «предметы под ногами»
    FLOOR_QUICK = {
        (pygame.K_g, False): ("pickup_item", "any"),
        (pygame.K_i, False): ("show_item_info", "any"),
    }

    ITEM_ACTIONS = (
        ("act.info", "show_item_info"),
        ("act.drop", "do_drop"),
        ("act.eat", "do_eat"),
        ("act.quaff", "do_quaff"),
        ("act.read", "do_read"),
        ("act.wear", "do_wear"),
        ("act.wield", "do_wield"),
        ("act.takeoff", "do_takeoff"),
        ("act.fire", "open_fire"),
        ("act.zap", "open_zap"),
        ("act.throw", "open_throw"),
    )

    def show_item_actions(self, item):

        return _ui_inventory.show_item_actions(self, item)

    def show_item_info(self, item):

        return _ui_inventory.show_item_info(self, item)

    def open_drop(self):

        return _ui_inventory.open_drop(self)

    def open_eat(self):

        return _ui_inventory.open_eat(self)

    def open_quaff(self):

        return _ui_inventory.open_quaff(self)

    def open_read(self):

        return _ui_inventory.open_read(self)

    def open_wield(self):

        return _ui_inventory.open_wield(self)

    def open_wear(self):

        return _ui_inventory.open_wear(self)

    def open_takeoff(self):

        return _ui_inventory.open_takeoff(self)

    def _pick_carried(self, title, fn, kinds=None):

        return _ui_inventory._pick_carried(self, title, fn, kinds)

    def _pick_from(self, items, title, fn):

        return _ui_inventory._pick_from(self, items, title, fn)

    def pickup_item(self, item):

        return _ui_inventory.pickup_item(self, item)

    def open_pick_items(self):

        return _ui_inventory.open_pick_items(self)

    # --- конкретные операции ------------------------------------------------
    def _carried(self, item) -> bool:

        return _ui_inventory._carried(self, item)

    def do_drop(self, item):

        return _ui_inventory.do_drop(self, item)

    def do_eat(self, item):

        return _ui_inventory.do_eat(self, item)

    def do_quaff(self, item):

        return _ui_inventory.do_quaff(self, item)

    def do_read(self, item):

        return _ui_inventory.do_read(self, item)

    def identify(self, idx):

        return _ui_inventory.identify(self, idx)

    def do_wield(self, item):

        return _ui_inventory.do_wield(self, item)

    def do_wear(self, item):

        return _ui_inventory.do_wear(self, item)

    def do_takeoff(self, item):

        return _ui_inventory.do_takeoff(self, item)

    # --- оружие -------------------------------------------------------------
    def open_fire(self, pre=None):

        return _ui_inventory.open_fire(self, pre)

    def _do_fire_pick(self, item):

        return _ui_inventory._do_fire_pick(self, item)

    def _do_fire(self, x, y):

        return _ui_inventory._do_fire(self, x, y)

    def player_has_bow(self):

        return _ui_inventory.player_has_bow(self)

    def open_throw(self, pre=None):

        return _ui_inventory.open_throw(self, pre)

    def _do_throw_pick(self, item):

        return _ui_inventory._do_throw_pick(self, item)

    def _do_throw(self, x, y):

        return _ui_inventory._do_throw(self, x, y)

    def open_zap(self, pre=None):

        return _ui_inventory.open_zap(self, pre)

    def _do_zap_pick(self, item):

        return _ui_inventory._do_zap_pick(self, item)

    def _do_zap(self, x, y):

        return _ui_inventory._do_zap(self, x, y)

    # --- уровни -------------------------------------------------------------
    def use_level_exit(self):

        return _world_flow.use_level_exit(self)

    def show_level_passages(self):

        return _world_flow.show_level_passages(self)

    def travel_to_level(self, target):

        return _world_flow.travel_to_level(self, target)

    def descend(self):

        return _world_flow.descend(self)

    def climb(self):

        return _world_flow.climb(self)

    def use_world_stairs(self, delta):

        return _world_flow.use_world_stairs(self, delta)

    def ascend(self):

        return _world_flow.ascend(self)

    def toggle_lights(self):

        return _world_flow.toggle_lights(self)

    def rotate_view(self, direction=1):
        self._held_move=None
        """Поворачивает вид сверху, не меняя мировые координаты героя."""
        if self.views.mode != "ascii":
            self.views.turn(direction * math.pi / 12)
            return
        self.view_rotation = (self.view_rotation + int(direction)) % 4
        self.tooltip = None
        self.audio.play("select", 0.2)

    def toggle_map(self):

        return _world_flow.toggle_map(self)

    def check_tile(self, x, y):

        return _world_flow.check_tile(self, x, y)

    def pick_lock(self):

        return _world_flow.pick_lock(self)

    # --- ход ---------------------------------------------------------------
    def report_nourishment(self, result):

        return _turn_flow.report_nourishment(self, result)

    def end_turn(self, resting=False):

        return _turn_flow.end_turn(self, resting)

    def _advance_turn(self, resting=False):

        return _turn_flow._advance_turn(self, resting)

    def _sleep_choice(self, idx):

        return _turn_flow._sleep_choice(self, idx)

    def monster_turn(self):

        return _turn_flow.monster_turn(self)

    def on_death(self):

        return _turn_flow.on_death(self)

    # ------------------------------------------------------------------
    # Сохранение
    # ------------------------------------------------------------------
    def save_quiet(self) -> bool:
        if save_game(C.SAVE_PATH, self):
            self.msg(t("m.saved"), C.MSG_GOOD)
            self.audio.play("select", 0.5)
            return True
        self.msg(t("m.save_err"), C.MSG_BAD)
        return False

    def save_and_quit(self) -> bool:
        if save_game(C.SAVE_PATH, self):
            self.msg(t("m.save_quit"), C.MSG_GOOD)
            self.audio.play("select", 0.5)
            self.audio.stop_music()
            self.mode = "title"
            self.title_index = 0
            return True
        self.msg(t("m.save_err"), C.MSG_BAD)
        return False

    # ------------------------------------------------------------------
    # Экраны
    # ------------------------------------------------------------------
    def show_char(self):
        p = self.player
        lines = [
            (t("sheet.name"), C.WHITE),
            (f"{t('sheet.lvl', n=p.lvl)}   {t('sheet.xp', a=p.xp, b=p.xp_for_next_level())}", C.WHITE),
            (f"{t('sheet.hp', a=p.hp, b=p.max_hp)}   {t('sheet.ac', n=p.ac_total)}", C.WHITE),
            (f"{t('sheet.str', n=p.str)}  {t('sheet.dex', n=p.dex)}  {t('sheet.con', n=p.con)}", C.WHITE),
            (f"{t('sheet.dmg', n=p.damage_bonus)}  {t('sheet.hit', n=p.hit_bonus)}", C.WHITE),
            (f"{t('ui.depth_of', d=p.depth, m=C.MAX_LEVEL)}   {t('sheet.deepest', n=p.deepest)}", C.WHITE),
            (t("sheet.gold", n=p.gold), C.YELLOW),
            (f"{t('sheet.kills', n=p.kills)}   {t('sheet.turns', n=p.turns)}", C.WHITE),
            (t('sheet.saturation', n=p.saturation), C.GREEN),
            (t('sheet.stamina', n=p.stamina), C.CYAN),
            (t('sheet.sanity', n=p.sanity), C.PURPLE),
            (t('sheet.reserve', level=p.exhaustion_level, n=p.exhaustion_progress,
               state=p.exhaustion_state()), p.exhaustion_color),
            (t('sheet.base_hp', n=p.base_max_hp), C.GRAY),
            (p.nutrition_state(), C.WHITE if p.saturation > 0 else C.PURPLE),
            ("", C.WHITE),
            (t("sheet.wielding"), C.GRAY),
        ]
        w = p.wielded
        lines.append((f"  {w.display_name() if w else t('item.bare_hands')}", C.WHITE))
        lines.append((t("sheet.wearing"), C.GRAY))
        for it in p.items:
            if it.equipped in ("armor", "ring"):
                lines.append((f"  {it.display_name()}", C.WHITE))
        if not p.equipped_of("armor") and not p.equipped_of("ring"):
            lines.append((f"  {t('item.none')}", C.GRAY))
        lines.append(("", C.WHITE))
        lines.append((t("sheet.carrying"), C.GRAY))
        for it in p.items[:10]:
            lines.append((f"  {it.label()}", C.LIGHT_GRAY))
        if len(p.items) > 10:
            lines.append((f"  {t('sheet.more', n=len(p.items) - 10)}", C.DARK_GRAY))
        statuses = [f"{t('st.' + k)} {v}" for k, v in p.status.items() if v > 0]
        if statuses:
            lines.append(("", C.WHITE))
            lines.append((t("sheet.status", s=", ".join(statuses)), C.YELLOW))
        self.show_text(t("sheet.title"), lines)

    def show_help(self):
        """Справка строится из текущих раскладок - всегда актуальна."""
        ctl = self.ctl
        lines = []
        lines.append((t('help.modern'), C.YELLOW))
        lines.append((t('help.sprint'), C.YELLOW))
        lines.append((t('help.nutrition'), C.GREEN))
        lines.append((t('help.sleep'), C.CYAN))
        for group, items in ACTION_GROUPS:
            lines.append((t(group), C.CYAN))
            for action, _ in items:
                name = t("a." + action)
                keys = ctl.key_list(action, limit=3)
                pad = max(1, 18 - len(name))
                lines.append(("   " + name + " " * pad + keys, C.WHITE))
            lines.append(("", C.WHITE))
        lines.append((t("help.14"), C.WHITE))
        lines.append((t("help.15"), C.WHITE))
        lines.append((t("help.16"), C.WHITE))
        lines.append((t("help.17"), C.WHITE))
        lines.append((t("mouse.title"), C.GRAY))
        lines.append((t("mouse.menu_hint"), C.GRAY))
        lines.append(("", C.WHITE))
        lines.append((t("quick.hint"), C.GRAY))
        lines.append(("", C.WHITE))
        lines.append((t("help.18"), C.GRAY))
        lines.append((t("help.rotate"), C.CYAN))
        lines.append((t("gfx.keys"), C.CYAN))
        lines.append((t("gfx.camera_keys"), C.CYAN))
        lines.append((t("help.19", m=C.MAX_LEVEL), C.YELLOW))
        self.show_text(t("help.title"), lines)

    # ------------------------------------------------------------------
    # Отрисовка
    # ------------------------------------------------------------------
    # раскладка окна (в ячейках символьной сетки):
    #   строка 0                 - верхняя панель
    #   строки 1..CAMERA_H       - карта (шириной CAMERA_W) + сайдбар
    #   строки CAMERA_H+1..      - журнал сообщений
    def draw(self):
        if self.mode in ('build_puzzle','work'):
            self.workshop.draw()
            return
        if self.mode=='audio_settings':
            self.audio_settings.draw()
            return
        if self.mode == 'inventory':
            self.inventory_panel.draw()
            if self.display:
                self.display.scene = None
            return
        if self.mode=='sleep_slider':
            self.r.clear()
            bar=self.sleep_slider_rect()
            pygame.draw.rect(self.r.surface,C.DARK_GRAY,bar)
            x=bar.x+int(bar.w*(self.sleep_setting-10)/350)
            pygame.draw.circle(self.r.surface,C.CYAN,(x,bar.centery),10)
            self.r.text(3,3,t('set.sleep')+f': {self.sleep_setting}',C.WHITE)
            self.r.text(3,5,'10                         360',C.GRAY)
            self.r.text(3,7,'Enter / Esc',C.GRAY)
            self.r.fill_rect(3,8,24,2,C.DARK_BLUE if hasattr(C,'DARK_BLUE') else (30,40,65))
            self.r.text(4,8,t('sleep.start' if self._slider_start_sleep else 'sleep.apply'),C.WHITE)
            if self.display: self.display.scene=None
            return
        if self.display:
            self.display.scene=None
        
        # Begin GL batch rendering if available
        renderer = self.display.gl_renderer if self.display else None
        if renderer and renderer.gl_enabled:
            renderer.begin()
        
        # на титульном экране (и в модальных окнах поверх него) игрока нет
        if self.mode == "title" or self.player is None:
            self.draw_title()
            if self.mode == "modal":
                self.draw_modal()
            elif self.mode == "rebind":
                self.draw_rebind()
            elif self.mode == "crash":
                self.draw_crash()
            
            # End GL batch rendering if available
            if renderer and renderer.gl_enabled:
                renderer.end()
            return
        
        self.r.clear(C.BLACK)
        
        # Use modern HUD or legacy ASCII HUD
        if self.use_modern_hud:
            self.modern_hud.draw(self.player)
        else:
            self.draw_topbar()
        
        if not self.player.is_asleep():
            scene_index = len(renderer.batch.quads) if renderer and renderer.gl_enabled else 0
            self.draw_map()
            if renderer and renderer.gl_enabled:
                from engine.gl_compositor import GLCompositor
                GLCompositor.compose(renderer, self.display.scene, scene_index)
                if self.display.scene is not None and self.views.mode == 'first':
                    area = self.display.scene[1]
                    from engine.volume import CROSS
                    renderer.draw_line((area.centerx-4, area.centery), (area.centerx+4, area.centery), CROSS)
                    renderer.draw_line((area.centerx, area.centery-4), (area.centerx, area.centery+4), CROSS)
        if self.display:
            self.display.scene_roll=0
        
        # Use modern sidebar or legacy ASCII sidebar
        if self.use_modern_hud:
            self.modern_sidebar.visible = self.sidebar_visible
            action_rects = self.modern_sidebar.draw(self.player, self)
            if action_rects:
                self.hud_action_rects = action_rects
        else:
            self.draw_sidebar()
        
        self.draw_log()
        
        if self.player.is_asleep():
            # Use renderer instead of direct surface access
            renderer = self.display.gl_renderer if self.display else None
            if renderer and renderer.gl_enabled:
                renderer.fill((0, 0, 0))
            else:
                self.r.surface.fill((0, 0, 0))
            zzz = ('Zzz','ZZZ','Zzz')[(pygame.time.get_ticks()//400)%3]
            self.r.text(self.r.surface.get_width()//self.r.cw//2-2,
                        self.map_offset_y+3, zzz, C.LIGHT_GRAY, bold=True)
        elif pygame.time.get_ticks()<self._rest_tint_until and self.mode=='play':
            # Use GL overlay if available
            renderer = self.display.gl_renderer if self.display else None
            if renderer and renderer.gl_enabled:
                renderer.overlay((25, 65, 150, 45))
            else:
                shade = pygame.Surface(self.r.surface.get_size(), pygame.SRCALPHA)
                shade.fill((25,65,150,45))
                self.r.surface.blit(shade,(0,0))
        
        if self.mode == "play" and not self.player.is_asleep():
            self.draw_tooltip()
        if self.mode == "modal":
            self.draw_modal()
        elif self.mode == "target":
            self.draw_target_hint()
        elif self.mode == "rebind":
            self.draw_rebind()
        elif self.mode == "text_input":
            self.draw_prompt()
        elif self.mode == "dead":
            self.draw_death()
        elif self.mode == "crash":
            self.draw_crash()
        elif self.mode == 'action_wheel':
            self.action_wheel.draw()
        
        # End GL batch at the very end (after all drawing)
        renderer = self.display.gl_renderer if self.display else None
        if renderer and renderer.gl_enabled:
            renderer.end()

    def draw_prompt(self):
        prompt = getattr(self, "prompt", "")
        self.r.text(self.r.cw, self.log_top() + 1, prompt, C.WHITE)
        self.r.char(self.r.cw + len(prompt) + 2, self.log_top() + 1, "_", C.YELLOW)

    def draw_title(self):
        r = self.r
        r.gradient_bg((8, 6, 14), (30, 12, 36))
        sw = r.surface.get_width() // r.cw
        sh = r.surface.get_height() // r.ch
        top = 4
        iw = 30
        room = [
            "█" * iw,
            "█" + "░" * 28 + "█",
            "█" + "░" * 13 + "@" + "░" * 14 + "█",
            "█" + "░" * 20 + "█" + "·" * 6 + "█",
            "█" + "░" * 26 + "█" + ">" + "·",
            "█" * iw,
        ]
        self.draw_emblem(top, iw, room)
        r.text(sw // 2 - len(C.TITLE) // 2, top - 2, C.TITLE, C.YELLOW, bold=True)
        r.text(sw // 2 - len(C.SUBTITLE) // 2, top + len(room) + 4,
               t("title.subtitle"), C.GRAY)
        self.title_menu.draw_at(sw // 2 - self.title_menu.w // 2, top + len(room) + 6)
        r.text(sw // 2 - 30, sh - 2,
               self.audio.status() + f"   seed {self.rng.seed}", C.DARK_GRAY)
        r.text(sw // 2 - 30, sh - 1, t("title.footer"), C.DARK_GRAY)

    def draw_emblem(self, top, iw, room):
        """Рамка с фрагментом подземелья - простая линейная графика."""
        r = self.r
        sw = r.surface.get_width() // r.cw
        left = sw // 2 - (iw + 2) // 2
        edge, wall, floor = C.C_WALL_EDGE, C.C_WALL, C.C_FLOOR
        r.text(left, top, G.BOX_TL + G.BOX_H * iw + G.BOX_TR, edge)
        for i, row in enumerate(room):
            y = top + 1 + i
            r.text(left, y, G.BOX_V, edge)
            for j, ch in enumerate(row):
                color = wall if ch == "█" else floor
                if ch == "·":
                    color = C.C_WALL_DARK
                r.char(left + 1 + j, y, ch, color)
            if "@" in row:
                r.char(left + 1 + row.index("@"), y, "@", C.WHITE, bold=True)
            if ">" in row:
                r.char(left + 1 + row.index(">"), y, ">", C.C_STAIR, bold=True)
            r.char(left + iw + 1, y, G.BOX_V, edge)
        r.text(left, top + len(room) + 1, G.BOX_BL + G.BOX_H * iw + G.BOX_BR, edge)

    def log_top(self):
        if self.chat_rect is not None:
            return max(0, self.chat_rect.y // self.r.ch)
        return self.map_offset_y + self.camera_h

    def draw_topbar(self):
        # Skip old topbar if using modern HUD
        if self.use_modern_hud:
            return
        
        r, p = self.r, self.player
        cols = r.surface.get_width() // r.cw
        r.fill_rect(0, 0, cols + 1, C.TOPBAR_H, (17, 20, 30))
        r.fill_rect(0, 1, cols + 1, 1, (24, 27, 40))
        r.hline(0, 0, cols, (61, 72, 96))

        # Responsive metric cards: each card receives a share of the logical
        # width instead of relying on fixed columns that become unreadable at
        # narrow resolutions and leave empty space on wide screens.
        meters = ((t('ui.bars.short'), p.hp, p.max_hp, C.HP_BAR),
                  (t('ui.food.short'), p.saturation, 100, C.GREEN),
                  (t('ui.stamina.short'), p.stamina, 50, C.CYAN),
                  (t('ui.sanity.short'), p.sanity, 50, C.PURPLE))
        card_w = max(14, cols // 4)
        for index, (label, value, maximum, color) in enumerate(meters):
            x = index * card_w + 1
            width = card_w - 2 if index < 3 else cols - x - 1
            bar_w = max(3, min(10, width - len(label) - 8))
            r.text(x, 0, label, C.LIGHT_GRAY, max_cells=max(1, width - 2))
            bar_x = x + len(label) + 1
            r.bar(bar_x, 0, bar_w, max(0, value) / max(1, maximum), color)
            r.text(bar_x + bar_w + 1, 0, f'{value}/{maximum}', C.WHITE,
                   max_cells=max(1, width - bar_x - bar_w - 1))

        reserve = f"{t('ui.reserve.short')} {p.exhaustion_level:+d} {p.exhaustion_progress}/50"
        r.text(1, 1, reserve, p.exhaustion_color, max_cells=max(1, cols // 3))
        stats_x = max(1, cols // 3 + 2)
        stats = f'STR {p.str}   AC {p.ac_total}   LVL {p.lvl}   ${p.gold}   T {p.turns}'
        r.text(stats_x, 1, stats, C.LIGHT_GRAY, max_cells=max(1, cols - stats_x - 1))

        sx = cols - 1
        flags = []
        if p.status.get("confused", 0) > 0:
            flags.append((t("st.confused"), C.PURPLE))
        if p.status.get("hallucinating", 0) > 0:
            flags.append((t("st.hallucinating"), C.CYAN))
        if p.status.get("asleep", 0) > 0:
            flags.append((t("st.asleep"), C.BLUE))
        if p.status.get("lucky", 0) > 0:
            flags.append((t("st.lucky"), C.GREEN))
        for text, col in reversed(flags):
            sx -= len(text) + 2
            if sx >= 62:
                r.text(sx, 1, text, col)

    def cam(self):
        p = self.player
        cam_x = p.x - self.camera_w // 2
        cam_y = p.y - self.camera_h // 2
        if self.world is not None:
            return cam_x, cam_y
        cam_x = max(0, min(cam_x, max(0, self.level.w - self.camera_w)))
        cam_y = max(0, min(cam_y, max(0, self.level.h - self.camera_h)))
        return cam_x, cam_y

    def screen_to_world(self, sx, sy):
        """Координаты клетки экрана (относительно карты) -> координаты мира."""
        p = self.player
        if self.view_rotation == 0:
            cx, cy = self.cam()
            return cx + sx, cy + sy
        dx, dy = sx - self.camera_w // 2, sy - self.camera_h // 2
        if self.view_rotation == 1:
            dx, dy = dy, -dx
        elif self.view_rotation == 2:
            dx, dy = -dx, -dy
        elif self.view_rotation == 3:
            dx, dy = -dy, dx
        return p.x + dx, p.y + dy

    def world_to_screen(self, wx, wy):
        """Координаты мира -> клетка повернутой карты или None."""
        if self.world is None and not self.level.in_bounds(wx, wy):
            return None
        if self.view_rotation == 0:
            cx, cy = self.cam()
            sx, sy = wx - cx, wy - cy
            if not (0 <= sx < self.camera_w and 0 <= sy < self.camera_h):
                return None
            return sx, sy
        dx, dy = wx - self.player.x, wy - self.player.y
        if self.view_rotation == 1:
            dx, dy = -dy, dx
        elif self.view_rotation == 2:
            dx, dy = -dx, -dy
        elif self.view_rotation == 3:
            dx, dy = dy, -dx
        sx, sy = self.camera_w // 2 + dx, self.camera_h // 2 + dy
        if not (0 <= sx < self.camera_w and 0 <= sy < self.camera_h):
            return None
        return sx, sy

    def draw_map(self):
        if self.world is not None:
            p = self.player
            # geometry_revision растёт в Level.set(), поэтому копировать
            # список тайлов чанка в ключ каждый кадр не нужно.
            key = (id(self.level), p.chunk_x, p.chunk_y, p.world_z, p.x, p.y, p.turns,
                   tuple(sorted((id(lv), lv.geometry_revision,
                          tuple(sorted((pos, tuple(sorted(d.items()))) for pos,d in lv.doors.items())))
                         for lv in self.world.chunks.values() if lv.world_z == p.world_z)),
                   tuple(sorted((id(lv),tuple((f.kind,f.x,f.y,f.rotated) for f in lv.furniture))
                                for lv in self.world.chunks.values() if lv.world_z==p.world_z)))

            if key != self._visible_world_key:
                self.visible_world = self.world.view_cells(p, self.lamp_flicker_modifier)
                self._visible_world_key = key
        if self.views.mode != "ascii":
            self.views.draw(self)
            return
        r, lv, p = self.r, self.level, self.player
        vis = lv.visible
        expl = lv.explored
        mapped = lv.mapped
        full_map = len(mapped) > len(expl)
        known = mapped if full_map else expl
        style = lv.style
        off_y = self.map_offset_y
        draw_glyph = self.r.fill_tile if self.r.tileset.enabled else self.r.char
        draw_sprite = self.r.sprite


        for row in range(self.camera_h):
            for col in range(self.camera_w):
                wx, wy = self.screen_to_world(col, row)
                lv = self.level
                if self.world is not None:
                    dx, wx = divmod(wx, self.world.w)
                    dy, wy = divmod(wy, self.world.h)
                    lv = self.world.chunk(p.chunk_x+dx, p.chunk_y+dy, p.world_z)
                    known = lv.explored if self.world.profile.get('absolute_darkness') else lv.explored | lv.mapped
                    vis = lv.visible
                if not lv.in_bounds(wx, wy):
                    continue
                sx = col
                sy = off_y + row
                seen = (wx, wy) in known
                is_vis = (wx, wy) in vis
                if not seen:
                    continue
                tile = lv.at(wx, wy)
                var = lv.variant[lv.idx(wx, wy)]
                glyph, color = self.tile_glyph(lv, tile, wx, wy, var, full_map)
                light = max(0.05, min(1.0, lv.light_grid[wx][wy]))
                if getattr(lv,'profile',{}).get('absolute_darkness'):
                    light = .5  # ASCII is the tactile map, not a working light source.
                if is_vis:
                    color = tuple(int(c * light) for c in color)
                if not is_vis:
                    color = tuple(int(c * 0.42) for c in color)
                draw_glyph(sx, sy, glyph, color)

                if is_vis and (wx, wy) in lv.corpses:
                    cc = getattr(lv, "corpses_color", {}).get((wx, wy), C.DARK_RED)
                    if is_vis:
                        cc = tuple(int(c * light) for c in cc)
                    else:
                        cc = tuple(int(c * 0.42) for c in cc)
                    draw_sprite(sx, sy, "%", cc)

                item = lv.items.get((wx, wy))
                if item is not None and is_vis:
                    icol = item.color
                    if is_vis:
                        icol = tuple(int(c * light) for c in icol)
                    else:
                        icol = tuple(int(c * 0.45) for c in icol)
                    draw_sprite(sx, sy, item.glyph, icol)

                if is_vis:
                    m = lv.monster_at(wx, wy)
                    if m is not None:
                        gcol = m.color
                        if p.status.get("hallucinating", 0) > 0:
                            mg, gcol = self.phantasm(m)
                        else:
                            mg = m.glyph
                        gcol = tuple(int(c * light) for c in gcol)
                        draw_sprite(sx, sy, mg, gcol, bold=m.awake)

        # игрок поверх всего
        player_screen = self.world_to_screen(p.x, p.y)
        if player_screen is not None:
            draw_sprite(player_screen[0], off_y + player_screen[1], "@", C.WHITE, bold=True)


        self.draw_floats(off_y)

    def phantasm(self, m):
        """Галлюцинация: возвращает (глиф, цвет)."""
        letters = "abcdefghijklmnopqrstuvwxyz"
        return (random.choice(letters),
                random.choice([C.PURPLE, C.CYAN, C.GREEN, C.ORANGE]))

    def tile_glyph(self, lv, tile, x, y, var, full_map):
        if tile == MG.WINDOW: return '□', (75,145,190)
        if tile == MG.PIPE: return 'O', (100,108,112)
        if tile == MG.WINDOW: return '□', (75,145,190)
        if tile == MG.PIPE: return 'O', (100,108,112)
        if (x,y) in lv.exits:
            return ('?',C.PURPLE) if lv.exits[x,y]['method']=='noclip' else ('E',C.GREEN)
        if (x,y) in lv.hazards:
            return '^', C.ORANGE
        furniture=lv.furniture_at(x,y)
        if furniture is not None:
            return furniture.spec['glyph'],furniture.spec['color']
        if tile == MG.AIR:
            return '○', (60,65,80)
        if tile == MG.BLACK_GRASS:
            return '░', (35, 48, 28)
        if getattr(lv,'profile',None):
            profile = getattr(lv, "profile", {})
            if tile == MG.WALL:
                return G.wall_glyph(var, 0), tuple(profile.get("wall_color", (190, 171, 89)))
            if tile == MG.FLOOR:
                return G.T_FLOOR, tuple(profile.get("floor_color", (118, 104, 62)))
        if tile == MG.WALL:
            return G.wall_glyph(var, lv.style), G.WALL_STYLES[lv.style]["color"]
        if tile == MG.HEDGE:
            return G.T_HEDGE, (44, 92, 52)
        if tile == MG.FLOOR:
            return (G.T_FLOOR_ALT if var % 11 == 0 else G.T_FLOOR), C.C_FLOOR
        if tile == MG.DOOR:
            d = lv.doors.get((x, y))
            if d and d.get("broken"):
                return G.T_FLOOR, C.C_FLOOR
            if d and not d.get("open"):
                return G.T_DOOR, C.C_DOOR
            return G.T_DOOR_OPEN, (120, 96, 60)
        if tile == MG.STAIR_DOWN:
            return G.T_STAIR_DOWN, C.C_STAIR
        if tile == MG.STAIR_UP:
            return G.T_STAIR_UP, (120, 160, 220)
        if tile == MG.ALTAR:
            return G.T_ALTAR, (222, 210, 180)
        if tile == MG.FOUNTAIN:
            return G.T_FOUNTAIN, C.CYAN
        if tile == MG.WATER:
            return G.T_WATER, (86, 145, 180)
        if tile == MG.RUBBLE:
            return G.T_RUBBLE, (110, 100, 96)
        if tile == MG.TRAPDOOR:
            return G.T_TRAP_DOOR, (150, 110, 70)
        return " ", C.BLACK

    def draw_minimap(self):
        r, lv, p = self.r, self.level, self.player
        mw, mh = C.MINIMAP_W, C.MINIMAP_H
        x0 = C.CAMERA_W + 1
        y0 = C.TOPBAR_H + C.STATUS_H + 2
        step_x = max(1, lv.w // mw)
        step_y = max(1, lv.h // mh)
        for gy in range(mh):
            for gx in range(mw):
                wx, wy = gx * step_x, gy * step_y
                if not lv.in_bounds(wx, wy):
                    continue
                if (wx, wy) in lv.explored:
                    col = (52, 48, 70) if lv.is_wall(wx, wy) else (110, 106, 140)
                    r.char(x0 + gx, y0 + gy, G.BOX_DOT, col)
                elif (wx, wy) in lv.mapped and not lv.is_wall(wx, wy):
                    r.char(x0 + gx, y0 + gy, G.BOX_DOT, (44, 42, 60))
        stx, sty = x0 + lv.stairs_down[0] // step_x, y0 + lv.stairs_down[1] // step_y
        if lv.depth != 0 and x0 <= stx < x0 + mw and y0 <= sty < y0 + mh:
            r.char(stx, sty, G.BOX_ARROW_R, C.C_STAIR)
        sx, sy = x0 + p.x // step_x, y0 + p.y // step_y
        if x0 <= sx < x0 + mw and y0 <= sy < y0 + mh:
            r.sprite(sx, sy, "@", C.YELLOW)

    def draw_sidebar(self):
        # Skip old sidebar if using modern HUD
        if self.use_modern_hud:
            return
        
        self.hud_action_rects = []
        if not self.sidebar_visible:
            return
        r, p = self.r, self.player
        x0 = self.camera_w
        w = C.SIDEBAR_W
        r.fill_rect(x0, self.map_offset_y, w, C.CAMERA_H, (18, 15, 26))
        r.vline(x0, self.map_offset_y, C.CAMERA_H, C.C_WALL_EDGE)

        y = self.map_offset_y
        r.box(x0, y, w, C.STATUS_H, C.C_WALL_EDGE, t("ui.status"))
        wname = p.wielded.display_name() if p.wielded else t("item.bare_hands")
        lines = [
            (f"{t('ui.bars')}    {p.hp}/{p.max_hp}",
              C.WHITE if p.hp > p.max_hp // 3 else C.RED),
            (t('sheet.saturation', n=p.saturation), C.GREEN),
            (t('sheet.stamina', n=p.stamina), C.CYAN),
            (f"{t('ui.reserve.short')} {p.exhaustion_level:+d} {p.exhaustion_progress}/50", p.exhaustion_color),
            (p.exhaustion_state(), p.exhaustion_color),
            (f"{t('ui.lbl.ac')}    {p.ac_total}", C.CYAN),
            (f"{t('ui.lbl.str')}   {p.str}", C.WHITE if p.str >= 10 else C.RED),
            (f"{t('ui.lbl.dex')}   {p.dex}", C.WHITE),
            (f"{t('ui.lbl.lvl')} {p.lvl}", C.WHITE),
            (t("ui.depth_of", d=p.depth, m=C.MAX_LEVEL), C.YELLOW),
            (f"{t('ui.lbl.gold')}  {p.gold}", C.YELLOW),
            (t("sheet.kills", n=p.kills), C.WHITE),
            (f"{t('ui.lbl.wpn')} {wname[: w - 8]}", C.LIGHT_GRAY),
        ]
        for i, (txt, col) in enumerate(lines):
            r.text(x0 + 2, y + 2 + i, txt[: w - 4], col)

        map_y = self.map_offset_y + C.STATUS_H
        map_h = C.CAMERA_H - C.STATUS_H
        r.box(x0, map_y, w, map_h, C.C_WALL_EDGE, t('wheel.title'))
        quick = (
            ('ui.quick_actions', 'action_menu'),
            ('ui.quick_interact', 'interact'),
            ('ui.quick_inventory', 'inventory'),
            ('ui.quick_map', 'view_map'),
            ('ui.quick_character', 'char_sheet'),
            ('ui.quick_hide', 'toggle_status'),
        )
        button_w = max(8, (w - 5) // 2)
        button_h = 2
        for i, (key, action) in enumerate(quick):
            col, row = i % 2, i // 2
            bx = x0 + 1 + col * (button_w + 1)
            by = map_y + 1 + row * button_h
            rect = r.cell_rect(bx, by, button_w, 1)
            self.hud_action_rects.append((rect, action))
            r.fill_rect(bx, by, button_w, 1, (48, 58, 76))
            r.text(bx + 1, by, t(key)[:button_w - 2], C.WHITE, max_cells=button_w - 2)

    def sleep_slider_rect(self):
        return pygame.Rect(3*self.r.cw,6*self.r.ch,30*self.r.cw,12)

    def draw_log(self):
        r = self.r
        # Overlay chat: it sits on the scene and does not reserve a footer.
        panel = layout_chat(self)
        overlay = getattr(self.debug_overlay, "panel_rect", None) if getattr(self.debug_overlay, "enabled", False) else None
        if overlay is not None and panel.colliderect(overlay):
            panel.y = min(panel.y, max(0, overlay.bottom + 8))
            if panel.bottom > r.surface.get_height() - 12:
                panel.bottom = r.surface.get_height() - 12
        self.chat_rect = panel
        gl = self.display.gl_renderer if self.display else None
        if gl is not None and gl.active:
            gl.draw_rect(panel, (8, 10, 17, 210), 6)
            gl.draw_rect_outline(panel, (132, 128, 168), border_radius=6)
            gl.text_pixels((panel.x + 12, panel.y + 6), t("ui.messages"), (200, 206, 220), 15)
            avail = max(1, (panel.h - 48) // 18)
            # Clip at glyph boundaries without rasterising a temporary surface.
            for i, (text, color) in enumerate(self.log[-avail:]):
                font = self.modern_hud._font(15)
                while text and font.size(text)[0] > panel.w - 24:
                    text = text[:-1]
                gl.text_pixels((panel.x + 12, panel.y + 26 + i * 18), text, color, 15)
            hint = t("ui.modern_hint")
            font = self.modern_hud._font(13)
            while hint and font.size(hint)[0] > panel.w - 24:
                hint = hint[:-1]
            gl.text_pixels((panel.x + 12, panel.bottom - 22), hint, (86, 186, 194), 13)
            return
        bg = pygame.Surface((panel.w, panel.h), pygame.SRCALPHA)
        bg.fill((8, 10, 17, 210))
        pygame.draw.rect(bg, (132, 128, 168), bg.get_rect(), 1, border_radius=6)
        r.surface.blit(bg, panel)
        font = pygame.font.SysFont("consolas", 15)
        title = font.render(t("ui.messages"), True, (200, 206, 220))
        r.surface.blit(title, (panel.x + 12, panel.y + 6))
        body = pygame.Rect(panel.x + 12, panel.y + 26, panel.w - 24, panel.h - 48)
        old = r.surface.get_clip()
        r.surface.set_clip(body)
        y = body.y
        avail = max(1, body.h // 18)
        shown = []
        for text, col in self.log[-(avail + 4):]:
            shown.append((text, col))
        for text, col in shown[-avail:]:
            line = font.render(text, True, col)
            r.surface.blit(line, (body.x, y))
            y += 18
        r.surface.set_clip(old)
        hint = pygame.font.SysFont("consolas", 13).render(t("ui.modern_hint"), True, (86, 186, 194))
        r.surface.blit(hint, (panel.x + 12, panel.bottom - 22), pygame.Rect(0, 0, panel.w - 24, hint.get_height()))

    def draw_modal(self):
        if self.menu is not None:
            self.menu.draw()
        elif self.modal_lines is not None:
            title, lines = self.modal_lines
            show_lines(self.r, lines, title, fg=C.WHITE, hint=t("error.hint"))

    def draw_target_hint(self):
        r, lv = self.r, self.level
        if self.views.mode != "ascii":
            r.text(1, self.log_top()+1, t("gfx.target"), C.YELLOW, max_cells=76)
            r.text(1, self.log_top()+2, str(self.target_pos), C.WHITE)
            return
        off_y = self.map_offset_y
        tx, ty = self.target_pos
        screen_pos = self.world_to_screen(tx, ty)
        if screen_pos is None:
            return
        sx, sy = screen_pos[0], screen_pos[1] + off_y
        color = C.RED if lv.monster_at(tx, ty) else C.YELLOW
        r.char(sx - 1, sy - 1, G.BOX_TL, color)
        r.char(sx + 1, sy - 1, G.BOX_TR, color)
        r.char(sx - 1, sy + 1, G.BOX_BL, color)
        r.char(sx + 1, sy + 1, G.BOX_BR, color)
        mon = lv.monster_at(tx, ty)
        desc = (t("tgt.monster", name=mon.title, a=mon.hp, b=mon.max_hp, c=mon.ac_total)
                if mon else lv.describe_tile(tx, ty))
        cols = r.surface.get_width() // r.cw
        y = self.log_top()
        r.fill_rect(0, y, cols + 1, C.LOG_H, C.BLACK)
        r.box(0, y, cols, C.LOG_H, C.RED, t("ui.targeting"))
        r.text(2, y + 2, t("tgt.target", x=tx, y=ty, what=desc), C.WHITE)
        r.text(2, y + 3, t("tgt.keys"), C.GRAY)

    def draw_death(self):
        r = self.r
        sw = r.surface.get_width() // r.cw
        sh = r.surface.get_height() // r.ch
        p = self.player
        win = getattr(self, "win", False)
        r.clear((8, 4, 8))
        title = t("death.win") if win else t("death.lose")
        r.text(sw // 2 - len(title) // 2, sh // 2 - 9, title,
               C.GREEN if win else C.RED, bold=True)
        rows = [
            t("death.depth", a=p.depth, b=C.MAX_LEVEL),
            t("death.xl", a=p.lvl),
            t("death.gold", a=p.gold),
            t("death.kills", a=p.kills),
            t("death.turns", a=p.turns),
            t("death.deepest", a=p.deepest),
        ]
        for i, txt in enumerate(rows):
            r.text(sw // 2 - 16, sh // 2 - 6 + i, txt, C.WHITE)
        r.text(sw // 2 - len(t("death.back")) // 2, sh // 2 + 2, t("death.back"),
               C.DARK_GRAY)

    # ------------------------------------------------------------------
    def tick_floats(self, dt=0.0):
        """Старение всплывающих чисел урона и подсказки (x, y, текст, цвет, ttl).

        Записи приходят кортежами, поэтому обновляем ttl пересборкой,
        а не присваиванием по индексу.
        """
        alive = []
        for f in self.floats:
            if len(f) < 5:
                continue
            ttl = f[4] - 1
            if ttl > 0:
                alive.append([f[0], f[1], f[2], f[3], ttl])
        self.floats = alive
        if self.tooltip is not None:
            self.tooltip["ttl"] -= 1
            if self.tooltip["ttl"] <= 0:
                self.tooltip = None

    def draw_floats(self, off_y):
        r = self.r
        for x, y, text, col, ttl in self.floats:
            pos = self.world_to_screen(x, y)
            if pos is not None:
                sx, sy = pos[0], pos[1] + off_y - 1
                shade = col if ttl > 8 else tuple(int(c * 0.6) for c in col)
                r.text(sx, sy, text, shade, bold=True)
