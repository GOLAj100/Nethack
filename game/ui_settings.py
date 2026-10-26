"""Экраны настроек: окно, графика, управление, язык, звук, отладка."""

from __future__ import annotations

import os

import pygame

from engine import config as C
from engine import window as window_geometry
from engine.display import RESOLUTIONS
from engine.widgets import Menu, show_lines
from .controls import ACTION_GROUPS, Actions, Controls
from .lang import LANG_NAMES, other_lang, save_settings, set_lang, t


def open_settings(game):

        """Настройки: язык, звук, управление. Открывается и из меню, и из игры."""
        from .lang import get_lang
        lang = get_lang()
        entries = [
            f"{t('set.language')}: {LANG_NAMES[lang]}",
            f"{t('set.sound')}: {t('set.on' if not game.audio.muted else 'set.off')}",
            t('audio.open'),
            f"{t('set.window')}: {game.resolution[0]}x{game.resolution[1]}"
            + ("" if game.window_mode == "fixed" else " · " + t("set.window_auto")),
            f"{t('set.fullscreen')}: {t('set.fullscreen.on' if game.fullscreen else 'set.fullscreen.off')}",
            t("set.controls"),
            t("gfx.title"),
            f"{t('set.sleep')}: {game.sleep_setting}",
            *([t("set.debug")] if game.player is not None else []),
            t("set.back"),
        ]
        back_index = len(entries) - 1
        debug_index = back_index - 1 if game.player is not None else None

        def cb(idx):
            if idx is None or idx == back_index:
                return
            if idx == 0:
                set_lang(other_lang())
                game.msg(t("set.language") + ": " + LANG_NAMES[get_lang()], C.MSG_GOOD)
                game.audio.play("select", 0.6)
            elif idx == 1:
                game.audio.toggle_mute()
                game.msg(t("set.sound") + ": "
                         + t("set.on" if not game.audio.muted else "set.off"), C.MSG_GOOD)
            elif idx == 2:
                from .audio_settings import AudioSettings
                game._audio_return=game.mode
                game.audio_settings=AudioSettings(game)
                game.mode='audio_settings'
                game._held_move=None
                return
            elif idx == 3:
                game.open_resolution()
                return
            elif idx == 4:
                game.toggle_fullscreen()
            elif idx == 5:
                save_settings(game)
                game.open_control_presets()
                return
            elif idx == 6:
                game.open_graphics()
                return
            elif idx == 7:
                game._slider_start_sleep=False
                game._slider_return=game.mode
                game.mode='sleep_slider'
                game._held_move=None
                return
            elif idx == debug_index:
                game.open_debug()
                return
            save_settings(game)
            game.refresh_title_menu()
            # сразу переоткрываем, чтобы видеть новое значение
            game.open_settings()

        game.show_menu(t("set.title"), entries, cb, width=38)


def open_resolution(game):

        entries = ([t("set.window_auto")]
                   + [f"{w} x {h}" for w, h in RESOLUTIONS]
                   + [t("set.back")])

        def choose(idx):
            if idx is None or idx == len(entries) - 1:
                game.open_settings()
                return
            if idx == 0:
                game.window_mode = "auto"
                game.apply_auto_window()
            else:
                game.window_mode = "fixed"
                game.resolution = RESOLUTIONS[idx - 1]
            game.resize_window()
            save_settings(game)
            game.open_settings()
        game.show_menu(t("set.window"), entries, choose, width=36)


def open_graphics(game, index=0):

        v = game.views
        ts = game.r.tileset
        modes = ("ascii", "first", "board")
        toggles = ("lighting", "fog", "outlines", "full_map", "single_layer")
        entries = [f"{t('gfx.view')}: {t('gfx.' + v.mode)}",
                   f"{t('gfx.quality')}: {t('gfx.q' + str(v.quality))}"]
        entries += [f"{t('gfx.' + key)}: {t('set.on' if getattr(v, key) else 'set.off')}" for key in toggles]
        entries += [f"{t('gfx.tileset')}: {t('gfx.tileset.on' if ts.enabled else 'gfx.tileset.off')}",
                    f"{t('gfx.autocolor')}: {t('set.on' if ts.auto_color else 'set.off')}",
                    f"Tile size: {ts.tile_size}px",
                    f"Graphics mod: {ts.mod_name}"]
        entries += [f"{t('gfx.distance')}: {v.draw_distance}",
                     f"{t('gfx.ceiling')}: {t('set.on' if v.show_ceiling else 'set.off')}" ]
        entries += [f"GPU output: {game.display.requested_backend if game.display else 'software'}",
                    "GPU: Windows graphics settings",
                    "Vulkan device: enumerate"]
        entries += [t("set.back")]

        def choose(idx):
            if idx is None or idx == len(entries)-1:
                game.open_settings()
                return
            if idx == 0:
                v.mode = modes[(modes.index(v.mode)+1) % 3]
            elif idx == 1:
                v.quality = (v.quality+1) % 3
            else:
                toggle_idx = idx - 2
                if toggle_idx < len(toggles):
                    key = toggles[toggle_idx]
                    setattr(v, key, not getattr(v, key))
                elif toggle_idx == len(toggles):
                    ts.configure(enabled=not ts.enabled)
                elif toggle_idx == len(toggles) + 1:
                    ts.configure(auto_color=not ts.auto_color)
                elif toggle_idx == len(toggles) + 2:
                    sizes = (16, 24, 32, 48, 64)
                    ts.configure(tile_size=sizes[(sizes.index(ts.tile_size) + 1) % len(sizes)])
                elif toggle_idx == len(toggles) + 3:
                    mods = ts.mods() or ["default"]
                    current = mods.index(ts.mod_name) if ts.mod_name in mods else -1
                    chosen = mods[(current + 1) % len(mods)]
                    ts.configure(mod_name=chosen, enabled=True)
                    game.msg(f"Graphics mod: {chosen} — {t('gfx.tileset.on')}", C.MSG_INFO)

                elif toggle_idx == len(toggles) + 4:
                    v.draw_distance = 13 if v.draw_distance > 30 else 52
                elif toggle_idx == len(toggles) + 5:
                    v.show_ceiling = not v.show_ceiling
                elif toggle_idx == len(toggles) + 6:
                    if game.display is None:
                        game.resize_window()
                    cycle = ('software','opengl','vulkan')
                    backend = cycle[(cycle.index(game.display.requested_backend)+1)%len(cycle)]
                    game.display.configure(game.resolution,game.fullscreen,backend=backend)
                    if hasattr(game.views, 'invalidate'):
                        game.views.invalidate()
                    game.msg(game.display.error or game.display.gpu_name,C.MSG_INFO)
                elif toggle_idx == len(toggles) + 7:
                    if os.name == 'nt':
                        os.startfile('ms-settings:display-advancedgraphics')
                elif toggle_idx == len(toggles) + 8:
                    from engine.vulkan_backend import VulkanBackend
                    devices = VulkanBackend().enumerate_devices()
                    game.msg(', '.join(devices) if devices else 'Vulkan unavailable', C.MSG_INFO)
            save_settings(game)
            game.open_graphics(idx)
        game.show_menu(t("gfx.title"), entries, choose, start_index=index, width=46)


def open_control_presets(game):

        entries = [t('ctl.preset.newcomer'), t('ctl.preset.classic'),
                   t('ctl.customize'), t('set.back')]
        def choose(idx):
            if idx is None or idx == 3:
                return
            if idx == 2:
                game.open_controls()
                return
            game.ctl.switch_preset(('newcomer','classic')[idx])
            save_settings(game)
            game.msg(t('ctl.active') + ': ' + t('ctl.preset.'+game.ctl.preset), C.MSG_GOOD)
            game.open_control_presets()
        game.show_menu(t('ctl.active')+': '+t('ctl.preset.'+game.ctl.preset),entries,choose,width=48)


def open_controls(game, start_index=0):

        flat = [a for _g, items in ACTION_GROUPS for a, _ in items]
        width = max(len(t("a." + a)) for a in flat) + 12
        entries = [f"{game.ctl.primary_label(a):<7} {t('a.' + a)}" for a in flat]
        entries.append(t("set.reset"))

        def cb(idx):
            if idx is None:
                return
            if idx == len(entries) - 1:
                game.ctl.reset()
                save_settings(game)
                game.msg(t("set.reset"), C.MSG_GOOD)
                game.open_controls(start_index=idx)
                return
            game.start_rebind(flat[idx], idx)

        game.show_menu(t("ctl.title"), entries, cb, width=min(width + 6, 46),
                       start_index=start_index)


def start_rebind(game, action: str, index: int = 0):

        game.rebind = action
        game.rebind_index = index
        game.rebind_return = game.mode   # 'title' или 'play'
        game.mode = "rebind"
        game.audio.play("menu", 0.5)


def _finish_rebind(game):

        """Возврат к списку управления с прежним выделением."""
        idx = getattr(game, "rebind_index", 0)
        game.rebind = None
        game.mode = getattr(game, "rebind_return", "title")
        game.open_controls(start_index=idx)


def key_rebind(game, ev):

        from .controls import name_of
        if name_of(ev.key) in ("escape", "return", "kp enter"):
            game._finish_rebind()
            return
        action = game.rebind
        if not game.ctl.assign(action, ev.mod, ev.key):
            game._finish_rebind()
            game.msg(t("ctl.locked"), C.MSG_BAD)
            return
        save_settings(game)
        game.audio.play("select", 0.6)
        game.msg(t("ctl.assigned", a=t("a." + action),
                   k=game.ctl.primary_label(action)), C.MSG_GOOD)
        game._finish_rebind()


def draw_rebind(game):

        r = game.r
        sw = r.surface.get_width() // r.cw
        sh = r.surface.get_height() // r.ch
        r.fill_rect(0, 0, sw + 1, sh + 1, (10, 8, 16))
        r.box(sw // 2 - 22, sh // 2 - 5, 44, 10, C.C_WALL_EDGE,
              t("ctl.title"), filled=True)
        text = t("ctl.rebind", a=t("a." + (game.rebind or "")))
        r.text(sw // 2 - len(text) // 2, sh // 2 - 2, text, C.WHITE)
        r.text(sw // 2 - len(t("ctl.rebind_hint")) // 2, sh // 2,
               t("ctl.rebind_hint"), C.GRAY)
        r.text(sw // 2 - len(t("ctl.esc_always")) // 2, sh // 2 + 2,
               t("ctl.esc_always"), C.DARK_GRAY)


def toggle_mute_sound(game):

        game.audio.toggle_mute()
        save_settings(game)
        game.msg(t("set.sound") + ": "
                 + t("set.on" if not game.audio.muted else "set.off"), C.MSG_GOOD)


def toggle_language(game):

        from .lang import get_lang
        set_lang(other_lang())
        save_settings(game)
        game.refresh_title_menu()
        game.msg(t("set.language") + ": " + LANG_NAMES[get_lang()], C.MSG_GOOD)


def open_debug(game):

        entries = [t('debug.map'),
                   f"{t('debug.immortal')}: {t('set.on' if game.player.god_mode else 'set.off')}",
                   t('debug.get_item'), t('debug.spawn_item'), t('debug.light'),
                   f"{t('debug.fly')}: {t('set.on' if game.player.debug_fly else 'set.off')}",
                   f"{t('debug.noclip')}: {t('set.on' if game.player.debug_noclip else 'set.off')}",
                   t('debug.z_up'), t('debug.z_down'), t('debug.skybox'),
                   t('debug.performance')+': '+t('set.on' if game.performance.enabled else 'set.off'),
                   t('debug.perf_reset'),
                   t('debug.overlay')+': '+t('set.on' if game.debug_overlay.enabled else 'set.off'),
                   t('set.back')]

        def cb(index):
            if index is None or index == len(entries) - 1:
                game.open_settings()
                return
            if index == 0:
                game.level.magic_map()
                game.msg(t('debug.map_done'), C.MSG_GOOD)
            elif index == 1:
                game.player.god_mode = not game.player.god_mode
            elif index in (2, 3):
                def choose_item(item_index):
                    if item_index is None:
                        game.open_debug()
                        return
                    name = list(ITEMS)[item_index]
                    item = Item(name)
                    if index == 2:
                        game.player.items.append(item)
                        game.msg(t('debug.item_added', item=item.display_name()), C.MSG_GOOD)
                    else:
                        spot = game.level.random_open_tile()
                        if spot:
                            game.level.items[spot] = item
                            game.msg(t('debug.item_spawned', item=item.display_name()), C.MSG_GOOD)
                    game.open_debug()
                game.show_menu(t('debug.choose_item'), [item_name(n) for n in ITEMS], choose_item, width=54)
                return
            elif index == 4:
                game.views.lighting = not game.views.lighting
                game.update_lighting()
            elif index == 5:
                game.player.debug_fly = not game.player.debug_fly
            elif index == 6:
                game.player.debug_noclip = not game.player.debug_noclip
            elif index == 7:
                game.debug_change_z(1)
            elif index == 8:
                game.debug_change_z(-1)
            elif index == 9:
                skies = ((13, 19, 32), (4, 6, 14), (32, 24, 38), (8, 22, 30))
                game.views.skybox = skies[(skies.index(game.views.skybox) + 1) % len(skies)]
            elif index == 10:
                game.performance.enabled=not game.performance.enabled
                game.performance.reset()
            elif index == 11:
                game.performance.reset()
            elif index == 12:
                game.debug_overlay.toggle()
            game.open_debug()

        game.show_menu(t('set.debug'), entries, cb, width=48)
