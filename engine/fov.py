"""Расчёт поля зрения: рекурсивный shadowcasting.

Реализация: Björn Bergström, "Recursive shadowcasting".
"""

from __future__ import annotations

import math

# (xx, xy, yx, yy) — поворот базовой полуплоскости на 90°
OCTANTS = (
    (1, 0, 0, 1),
    (0, 1, 1, 0),
    (-1, 0, 0, -1),
    (0, -1, -1, 0),
)


def _cast_light(ox, oy, radius, radius_sq, row, start, end,
                is_blocking, visit, xx, xy, yx, yy):
    if start < end:
        return
    next_start = start
    for i in range(row, radius + 1):
        blocked = False
        for dx in range(-i, i + 1):
            dy = -i
            l_slope = (dx - 0.5) / (dy + 0.5)
            r_slope = (dx + 0.5) / (dy - 0.5)
            if start < r_slope:
                continue
            if end > l_slope:
                break
            cx = ox + dx * xx + dy * xy
            cy = oy + dx * yx + dy * yy
            if dx * dx + dy * dy <= radius_sq:
                visit(cx, cy)
            op = is_blocking(cx, cy)
            if blocked:
                if op:
                    next_start = r_slope
                else:
                    blocked = False
                    start = next_start
            elif op and i < radius:
                blocked = True
                # +EPS убирает попадание ровно на границу тени
                _cast_light(ox, oy, radius, radius_sq, i + 1, start,
                            l_slope + 1e-6, is_blocking, visit, xx, xy, yx, yy)
                next_start = r_slope
        if blocked:
            break


def _run_fov(ox, oy, radius, radius_sq, is_blocking, start, end):
    visible = {(ox, oy)}

    def visit(x, y):
        visible.add((x, y))

    for xx, xy, yx, yy in OCTANTS:
        _cast_light(ox, oy, radius, radius_sq, 1, start, end,
                    is_blocking, visit, xx, xy, yx, yy)
    return visible


def compute_fov(ox, oy, radius, is_blocking, light_walls=True):
    """Возвращает множество (x, y) в поле зрения.

    Считается в два прохода: прямой и зеркальный. Пересечение убирает
    односторонние "протечки" на границе теней, делая обзор симметричным.

    is_blocking(x, y) -> True, если клетка перекрывает обзор.
    """
    radius = max(1, int(radius))
    radius_sq = radius * radius

    direct = _run_fov(ox, oy, radius, radius_sq, is_blocking, 1.0, -1.0)
    mirrored = _run_fov(-ox, -oy, radius, radius_sq,
                        lambda x, y: is_blocking(-x, -y), 1.0, -1.0)
    visible = direct & {(-x, -y) for (x, y) in mirrored}

    if not light_walls:
        visible = {p for p in visible if not is_blocking(*p)}
    return visible


def has_los(is_blocking, x0, y0, x1, y1):
    """Быстрая проверка прямой видимости по линии Брезенхэма."""
    for x, y in line(x0, y0, x1, y1):
        if (x, y) == (x0, y0):
            continue
        if is_blocking(x, y):
            return False
    return True






def line(x0, y0, x1, y1):
    """Линия Брезенхэма между двумя точками."""
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    pts = []
    while True:
        pts.append((x0, y0))
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy
    return pts


def distance(x0, y0, x1, y1):
    return math.hypot(x1 - x0, y1 - y0)


def chebyshev(x0, y0, x1, y1):
    return max(abs(x1 - x0), abs(y1 - y0))


def manhattan(x0, y0, x1, y1):
    return abs(x1 - x0) + abs(y1 - y0)
