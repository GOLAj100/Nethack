"""Тест авто-размера окна: engine.window (fit/center/mode/restore),
engine.display.Display.apply_window_resize и круговая проверка настроек окна.

Модули engine/window.py, engine/display.py, game/lang.py пишет ведущий.
Если game/lang.save_settings ещё не пишет window_mode (не интегрировано),
круговая проверка упрощается до проверки записи настроек в JSON — см. отчёт.
"""

import json
import os
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame

from engine import window as W
from engine.display import Display
from game import lang

MIN_W, MIN_H = W.MIN_WINDOW
FAILURES = []


def check(label, cond):
    if not cond:
        FAILURES.append(label)


def assert_close(label, value, expected, tol=1):
    if abs(value - expected) > tol:
        FAILURES.append(f"{label}: {value} != {expected} (±{tol})")


def aspect_ok(w, h, base_w, base_h, tol=2):
    # |w/h - base_w/base_h| <= tol / min(w,h)  -> |w*base_h - h*base_w| <= tol*base_h
    return abs(w * base_h - h * base_w) <= max(1, tol * base_h)


# --- 1. fit_window_size для desktop (1920,1080) -----------------------------
fit = W.fit_window_size((1920, 1080))
f_w, f_h = fit
check("fit1920 внутри desktop", f_w <= 1920 and f_h <= 1080)
check("fit1920 не больше 0.87*desktop",
      f_w <= 0.87 * 1920 and f_h <= 0.87 * 1080)
check("fit1920 не меньше MIN_WINDOW", f_w >= MIN_W and f_h >= MIN_H)
check("fit1920 сохраняет пропорции 16:9", aspect_ok(f_w, f_h, 1280, 720))

# --- 2. маленький desktop (800,600) ----------------------------------------
fit_s = W.fit_window_size((800, 600))
s_w, s_h = fit_s
check("fit800/600 >= MIN_WINDOW", s_w >= MIN_W and s_h >= MIN_H)
check("fit800/600 <= desktop", s_w <= 800 and s_h <= 600)
check("fit800/600 сохраняет пропорции 16:9", aspect_ok(s_w, s_h, 1280, 720))

# --- 3. maximum не превышается (3840x2160) ----------------------------------
fit_b = W.fit_window_size((3840, 2160))
b_w, b_h = fit_b
check("fit3840/2160 <= maximum", b_w <= 1920 and b_h <= 1080)
check("fit3840/2160 сохраняет пропорции 16:9", aspect_ok(b_w, b_h, 1280, 720))

# --- 4. center_position ------------------------------------------------------
check("center classic", W.center_position((1280, 720), (1920, 1080)) == (320, 180))
check("center окно больше экрана",
      W.center_position((2000, 1200), (1920, 1080)) == (0, 0))

# --- 5. normalize_mode --------------------------------------------------------
check("norm AUTO", W.normalize_mode("AUTO") == "auto")
check("norm ' fixed '", W.normalize_mode(" fixed ") == "fixed")
check("norm None->auto", W.normalize_mode(None) == "auto")
check("norm мусор->auto", W.normalize_mode("чепуха") == "auto")
check("norm None,default=fixed", W.normalize_mode(None, "fixed") == "fixed")

# --- 6. restore_geometry ------------------------------------------------------
DESK = (1920, 1080)
mode_a, size_a = W.restore_geometry({"window_mode": "auto"}, DESK)
check("restore auto->fit", mode_a == "auto" and size_a == W.fit_window_size(DESK))

mode_f, size_f = W.restore_geometry(
    {"window_mode": "fixed", "resolution": [1000, 700]}, DESK)
check("restore fixed 1000x700", mode_f == "fixed" and size_f == (1000, 700))

mode_c, size_c = W.restore_geometry(
    {"window_mode": "fixed", "resolution": [4000, 3000]}, DESK)
check("restore fixed прижат к desktop",
      mode_c == "fixed" and size_c == (1920, 1080))

mode_e, size_e = W.restore_geometry({}, DESK)
check("restore пустой dict->auto+fit",
      mode_e == "auto" and size_e == W.fit_window_size(DESK))

mode_b, size_b = W.restore_geometry(
    {"window_mode": "fixed", "resolution": "abc"}, DESK)
check("restore битый resolution->auto+fit",
      mode_b == "auto" and size_b == W.fit_window_size(DESK))

# --- 7. Display.apply_window_resize ------------------------------------------
pygame.init()
surf = pygame.Surface((640, 480))
from engine.renderer import Renderer
rr = Renderer(surf)
disp = Display(rr)
with patch.object(pygame.display, "set_mode", Mock()) as mock_set_mode:
    changed = disp.apply_window_resize((900, 700))
check("apply_window_resize вернул True при смене размера", changed is True)
check("apply_window_resize НЕ вызывает set_mode", mock_set_mode.call_count == 0)
check("apply_window_resize обновил size", disp.size == (900, 700))
cw, ch = disp.canvas.get_size()
check("канва не больше CANVAS_MAX", cw <= 1920 and ch <= 1080)
check("канва сохраняет пропорции окна", aspect_ok(cw, ch, 900, 700, tol=1))
disp_canvas = disp.canvas.get_size()
check("канва реально изменилась", disp_canvas != (640, 480))

# повторный вызов с тем же размером -> False
with patch.object(pygame.display, "set_mode", Mock()) as mock_set_mode2:
    changed2 = disp.apply_window_resize((900, 700))
check("повторный вызов возвращает False", changed2 is False)
check("повторный вызов НЕ вызывает set_mode", mock_set_mode2.call_count == 0)

# --- 8. круговая проверка настроек окна --------------------------------------
def make_stub(window_mode="auto", resolution=(1280, 720)):
    audio = SimpleNamespace(
        muted=False, volume=0.45, music_volume=0.55, effects_volume=1.0,
        ui_volume=1.0, environment_volume=1.0, alarm_volume=1.0,
    )
    audio.set_volume = lambda v: setattr(audio, "volume", v)
    # views/r/ctl сознательно НЕ задаём: и save_settings, и load_settings
    # обращаются к ним только через hasattr(...), поэтому их отсутствие
    # заставляет код пропускать эти блоки (вместо падения на None).
    return SimpleNamespace(
        audio=audio, fullscreen=False, window_mode=window_mode,
        resolution=list(resolution), display=None, sidebar_visible=True,
        sleep_setting=120, window_scale=1, presentation_backend="software",
    )

settings_roundtrip = False
with tempfile.TemporaryDirectory() as tmp, patch.object(
        lang, "SETTINGS_PATH", os.path.join(tmp, "settings.json")):
    stub = make_stub(window_mode="auto", resolution=[1000, 700])
    lang.save_settings(stub)
    written = json.load(open(os.path.join(tmp, "settings.json"), encoding="utf-8"))
    check("save_settings записал файл", isinstance(written, dict))
    if "window_mode" in written and written.get("resolution") == [1000, 700]:
        stub2 = make_stub(window_mode="fixed", resolution=[1280, 720])
        try:
            lang.load_settings(stub2)
            check("window_mode восстановился",
                  getattr(stub2, "window_mode", None) == "auto")
            check("resolution восстановился", getattr(stub2, "resolution", None) == (1000, 700))
            settings_roundtrip = True
        except Exception as exc:  # noqa: BLE001
            check("load_settings не падает", False)
            FAILURES.append(f"load_settings бросил исключение: {exc!r}")
    else:
        # window_mode ещё не интегрирован в game/lang.save_settings — упрощаем
        check("save_settings записал resolution", written.get("resolution") == [1000, 700])
pygame.quit()

print(f"проверок выполнено: fit={fit}, restore auto={size_a}, fixed={size_f}, "
      f"apply_window_resize canvas={disp_canvas}")

if FAILURES:
    print(f"ОШИБОК: {len(FAILURES)}")
    for f in FAILURES:
        print(" -", f)
    raise SystemExit(1)

if not settings_roundtrip:
    print("ПРИМЕЧАНИЕ: game/lang.save_settings пока не пишет 'window_mode' "
          "(контракт не интегрирован) — полная круговая проверка settings пропущена, "
          "проверена только запись настроек в JSON.")
print("WINDOW AUTOSIZE OK")