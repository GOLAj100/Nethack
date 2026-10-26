"""Тест поля зрения: радиус в чистом поле и непроницаемость стен."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import fov as F

blocked = set()


def is_blocking(x, y):
    return (x, y) in blocked


vis = F.compute_fov(0, 0, 9, is_blocking)
expected = sum(1 for x in range(-9, 10) for y in range(-9, 10) if x * x + y * y <= 81)
print(f"open field: {len(vis)} visible, expected >= {expected - 30}")
assert len(vis) >= expected - 30, "FOV too small"

# сплошная стена на линии y=0 должна прятать всё, что за ней на этой линии
blocked = {(x, 0) for x in range(1, 10)}
vis = F.compute_fov(0, 0, 9, is_blocking)
behind = sorted(p for p in vis if p[1] == 0 and p[0] >= 2)
print("through solid wall:", behind, "(1,0) should stay visible)")
assert not behind, "light leaks through a wall"

# стена во всю высоту карты: ничего справа не видно
blocked = {(x, y) for x in range(1, 10) for y in range(-9, 10)}
vis = F.compute_fov(0, 0, 9, is_blocking)
right = [p for p in vis if p[0] >= 2]
print("full wall:", right[:8], "count:", len(right))
assert not right, "light leaks through a full wall"

# симметрия
blocked = set()
a = F.compute_fov(5, 5, 8, is_blocking)
b = F.compute_fov(5, 5, 8, is_blocking)
assert a == b
assert (5, 5) in a
print("symmetry ok, size:", len(a))

# единственная линия обзора
blocked = {(x, 0) for x in range(1, 20)} | {(x, 0) for x in range(-20, 0)}
vis = F.compute_fov(0, 0, 15, is_blocking)
print("corridor visibility:", sorted([p for p in vis if abs(p[1]) < 3])[:12])
print("FOV OK")
