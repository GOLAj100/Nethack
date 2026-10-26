"""Автоматический подбор размера окна под экран и разбор сохранённой геометрии."""

from __future__ import annotations

import pygame

MIN_WINDOW = (680, 240)
DEFAULT_WINDOW = (1280, 720)
MAX_WINDOW = (1920, 1080)
EDGE_MARGIN = 0.85
MODES = ("auto", "fixed")


def desktop_size():
    """Размер основного монитора; при любой ошибке — размер по умолчанию."""
    try:
        sizes = pygame.display.get_desktop_sizes()
        if sizes:
            width, height = sizes[0]
            if width > 0 and height > 0:
                return (int(width), int(height))
    except Exception:
        pass
    try:
        info = pygame.display.Info()
        if info.current_w > 0 and info.current_h > 0:
            return (int(info.current_w), int(info.current_h))
    except Exception:
        pass
    return DEFAULT_WINDOW


def _clamp(value, low, high):
    return max(low, min(high, value))


def fit_window_size(desktop, base=DEFAULT_WINDOW, margin=EDGE_MARGIN,
                    minimum=MIN_WINDOW, maximum=MAX_WINDOW):
    """Наибольшее окно с пропорциями ``base``, влезающее в экран с полями."""
    dw = max(1, int(desktop[0]))
    dh = max(1, int(desktop[1]))
    bw, bh = base
    limit_w = min(max(minimum[0], int(dw * margin)), dw, max(minimum[0], min(int(maximum[0]), dw)))
    limit_h = min(max(minimum[1], int(dh * margin)), dh, max(minimum[1], min(int(maximum[1]), dh)))
    scale = min(limit_w / bw, limit_h / bh)
    width = max(minimum[0], int(round(bw * scale)))
    height = max(minimum[1], int(round(bh * scale)))
    width = min(width, dw)
    height = min(height, dh)
    if width > limit_w:
        width = limit_w
        height = max(minimum[1], int(round(width * bh / bw)))
    if height > limit_h:
        height = limit_h
        width = max(minimum[0], int(round(height * bw / bh)))
    return (min(width, dw), min(height, dh))


def center_position(size, desktop):
    """Координаты окна, центрированного на экране (не выходит за края)."""
    dx = max(0, (int(desktop[0]) - int(size[0])) // 2)
    dy = max(0, (int(desktop[1]) - int(size[1])) // 2)
    return (dx, dy)


def normalize_mode(value, default="auto"):
    """Приводит режим окна к 'auto' или 'fixed'."""
    if isinstance(value, str):
        cleaned = value.strip().lower()
        if cleaned in MODES:
            return cleaned
    return default if default in MODES else "auto"


def restore_geometry(data, desktop):
    """Возвращает (режим, размер окна) из сохранённых настроек."""
    if not isinstance(data, dict):
        data = {}
    mode = normalize_mode(data.get("window_mode"), "auto")
    if mode == "auto":
        return ("auto", fit_window_size(desktop))
    raw = data.get("resolution")
    size = None
    if isinstance(raw, (list, tuple)) and len(raw) == 2:
        try:
            size = (int(raw[0]), int(raw[1]))
        except (TypeError, ValueError):
            size = None
    if size is None:
        return ("auto", fit_window_size(desktop))
    width = _clamp(size[0], MIN_WINDOW[0], max(MIN_WINDOW[0], int(desktop[0])))
    height = _clamp(size[1], MIN_WINDOW[1], max(MIN_WINDOW[1], int(desktop[1])))
    return ("fixed", (width, height))
