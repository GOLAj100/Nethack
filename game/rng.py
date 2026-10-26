"""Генератор случайных чисел с сохранением состояния для save/load."""

from __future__ import annotations

import random


class RNG:
    def __init__(self, seed: int | None = None):
        self.seed = seed if seed is not None else random.randrange(1 << 30)
        self._r = random.Random(self.seed)

    def reseed(self, seed: int | None = None):
        self.seed = seed if seed is not None else random.randrange(1 << 30)
        self._r = random.Random(self.seed)

    def rand(self) -> float:
        return self._r.random()

    def below(self, n: int) -> int:
        return self._r.randrange(n) if n > 0 else 0

    def range(self, a: int, b: int) -> int:
        """Целое в [a, b] включительно."""
        return self._r.randint(a, b)

    def chance(self, p: float) -> bool:
        return self._r.random() < p

    def choice(self, seq):
        return self._r.choice(seq) if len(seq) else None

    def sample(self, seq, k: int):
        k = min(k, len(seq))
        return self._r.sample(list(seq), k) if k else []

    def shuffled(self, seq):
        out = list(seq)
        self._r.shuffle(out)
        return out

    def weighted(self, pairs):
        """pairs: [(item, weight), ...]"""
        total = sum(w for _, w in pairs)
        if total <= 0:
            return None
        roll = self._r.uniform(0, total)
        acc = 0.0
        for item, w in pairs:
            acc += w
            if roll <= acc:
                return item
        return pairs[-1][0]

    def dice(self, n: int, sides: int, bonus: int = 0) -> int:
        return sum(self._r.randint(1, sides) for _ in range(max(0, n))) + bonus

    def state(self) -> dict:
        return {"seed": self.seed, "state": self._r.getstate()}

    def load_state(self, data: dict):
        self.seed = data.get("seed", self.seed)
        st = data.get("state")
        if not st:
            return
        # random.getstate() -> (version, tuple(625 int), gauss_next)
        # JSON превращает кортежи в списки — восстанавливаем форму
        self._r.setstate((int(st[0]), tuple(st[1]), st[2]))

    def __getattr__(self, item):  # проксируем к random.Random
        return getattr(self._r, item)
