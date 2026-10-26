"""Питание, бонусы, дефицит, сон и реальное движение за один мировой ход."""
import os
import sys
import tempfile
from unittest.mock import Mock, patch

os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
from main import make_window
from game import lang, mapgen as MG, survival as S
from game.app import Game
from game.entities import Player, Actor
from game.items import ITEMS, Item
from game.save import save_game, load_game


def feed(p, *names):
    return [p.nourish(ITEMS[name]) for name in names]


p = Player()
assert (p.hp, p.max_hp, p.saturation, p.stamina, p.exhaustion_level) == (27, 27, 100, 50, 1)
p.saturation = 0
feed(p, 'crackers', 'water')
assert p.saturation == 20  # 5 + 5 = 20
for order in (('crackers', 'water'), ('water', 'crackers')):
    p = Player()
    p.saturation = 0
    feed(p, *order)
    assert p.saturation == 20
p = Player()
p.saturation = 0
feed(p, 'salted nuts', 'apple')
assert p.saturation == 20  # солёная+сладкая и сухая+влажная
feed(p, 'water')
assert p.saturation == 60  # (5+5+5)*2*2, начисляется только разница
feed(p, 'water')
assert p.saturation == 80  # дополнительная бутылка, без повторной выплаты 60
p = Player()
p.saturation = 0
feed(p, 'fried potatoes', 'cucumber')
assert p.saturation == 22
p = Player()
p.saturation = 0
feed(p, 'crackers')
p.turns = 30
feed(p, 'water')
assert p.saturation == 10  # окно блюда закончилось
p = Player()
p.saturation = 0
feed(p, 'borscht', 'borscht', 'borscht')
assert p.saturation == 100 and p.body_reserve == 100  # старт +1 и лишние 50 -> +2
assert (p.exhaustion_level, p.exhaustion_progress) == (2, 0)
p.consume(1)
assert (p.exhaustion_level, p.exhaustion_progress) == (2, 1)
p = Player()
p.body_reserve = -50
p.saturation = 0
feed(p, 'crackers', 'water')
assert p.body_reserve == -45
feed(p, 'water')
assert p.body_reserve == -45  # снятие дефицита ограничено одним блюдом
assert p.base_max_hp == 27

# Насыщение само по себе не наносит урон; отсрочка отрицательного дефицита 1000 ходов.
p = Player()
p.saturation = 0
p.body_reserve = 0
p.hp = 10
for turn in range(1, 1000):
    p.turns = turn
    S.advance(p)
assert p.hp == 10 and p.body_reserve == 0
p.turns = 1000
S.advance(p)
assert p.body_reserve == -1 and p.hp == 10
S.change_reserve(p, -49)
assert p.exhaustion_level == -1 and p.max_hp == 24 and p.hp == 10
S.change_reserve(p, 50)
assert p.max_hp == 27 and p.hp == 10  # восстановление потолка не лечит бесплатно
colors = []
for points in (50, 100, 150, 200, 250):
    p.body_reserve = points
    colors.append(p.exhaustion_color)
assert colors[:4] == list(S.WARM_COLORS) and colors[4] == colors[0]

# Регенерация во сне: полная/половинная/нулевая, включая дробный накопитель.
for sat, expected in ((100, 10), (50, 5), (0, 0)):
    p = Player()
    p.hp = 1
    p.saturation = sat
    p.stamina = -5
    for turn in range(1, 11):
        p.turns = turn
        S.advance(p, sleeping=True)
    assert p.hp == 1 + expected and p.stamina == 25
p = Player()
for _ in range(10):
    S.movement(p)
assert p.stamina == 49
p.stamina = 0
hp = p.hp
for _ in range(10):
    S.movement(p)
assert p.stamina == -1 and p.hp == hp
S.movement(p, running=True)
assert p.hp == hp - 1 and p.stamina == -1

p = Player()
rng = Mock()
assert S.sprint_length(p, rng) == 3
rng.randint.assert_not_called()
p.hp, p.stamina, p.sanity = 10, 20, 0
rng.randint.return_value = 42
assert S.sprint_length(p, rng) == 2
rng.randint.assert_called_with(2, 42)
rng.randint.return_value = 2
assert S.sprint_length(p, rng) == 3
p.sanity = 50
p.body_reserve = -50
assert S.sprint_length(p, rng) == 2
p.body_reserve = 500
assert S.sprint_length(p, rng) == 1

# Сохранения: новые поля и продолжающееся блюдо; миграция старого nutrition.
p = Player()
p.saturation = 0
feed(p, 'crackers')
data = p.to_dict()
loaded = Player()
loaded.load_dict(data)
feed(loaded, 'water')
assert loaded.saturation == 20 and loaded.meal['credited'] == 20
legacy = dict(data)
for key in ('saturation', 'body_reserve', 'stamina', 'sanity', 'base_max_hp', 'meal'):
    legacy.pop(key)
legacy['nutrition'] = 500
loaded = Player()
loaded.load_dict(legacy)
assert loaded.saturation == 50 and loaded.stamina == 50 and loaded.exhaustion_level == 1


def prepare(g, x=30, y=25):
    g.new_game()
    p = g.player
    p.x, p.y = x, y
    for cx in (0, 1):
        lv = g.world.chunk(cx, 0)
        lv.tiles = [MG.FLOOR] * (lv.w * lv.h)
        lv.monsters.clear()
        lv.items.clear()
        lv.doors.clear()
    g.views.mode = 'ascii'
    g.level.set_player_pos(x, y)
    return p


pygame.init()
with tempfile.TemporaryDirectory() as tmp, patch.object(
        lang, 'SETTINGS_PATH', os.path.join(tmp, 'settings.json')):
    g = Game(make_window(), seed=44)
    p = prepare(g)
    with patch.object(g, 'monster_turn', wraps=g.monster_turn) as turn:
        g.on_key(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RIGHT, mod=pygame.KMOD_SHIFT))
        assert (p.x, p.turns, p.stamina) == (33, 1, 47)
        assert turn.call_count == 1
    p = prepare(g)
    g.level.set(32, 25, MG.WALL)
    g.move(1, 0, running=True)
    assert (p.x, p.turns, p.stamina) == (31, 1, 49)
    p = prepare(g)
    g.level.set(31, 25, MG.DOOR)
    g.level.doors[31, 25] = {'open': False}
    g.move(1, 0, running=True)
    assert p.x == 30 and p.turns == 1 and p.stamina == 50
    assert g.level.doors[31, 25]['open']
    p = prepare(g, x=79)
    g.move(1, 0, running=True)
    assert (p.chunk_x, p.x, p.turns, p.stamina) == (1, 2, 1, 47)
    p = prepare(g)
    g.views.mode = 'first'
    g.views.yaw = 0
    from types import SimpleNamespace
    real_display = g.display
    g.display = SimpleNamespace(backend='gl')
    try:
        g.on_key(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_KP8, mod=pygame.KMOD_SHIFT))
    finally:
        g.display = real_display
    assert (p.x, p.y, p.turns, p.stamina) == (33, 25, 1, 47)
    p = prepare(g)
    g.level.set(31, 25, MG.TRAPDOOR)
    g.level.set(32, 25, MG.FOUNTAIN)
    p.hp = 2
    with patch('game.app.random.randint', return_value=2):
        g.move(1, 0, running=True)
    assert p.x == 31 and not p.alive and g.mode == 'dead'
    p = prepare(g)
    m = Actor(32, 25, name='test entity', hp=100, max_hp=100)
    g.level.monsters.append(m)
    with patch.object(g, 'player_attack') as attack:
        g.move(1, 0, running=True)
        assert (p.x, p.turns, p.stamina) == (31, 1, 49)
        attack.assert_called_once_with(m)
    p = prepare(g)
    p.stamina = 1
    g.move(1, 0, running=True)
    assert (p.x, p.stamina, p.hp) == (33, 0, 25)
    p = prepare(g)
    p.stamina = 0
    p.hp = 1
    g.move(1, 0, running=True)
    assert p.x == 31 and not p.alive and g.mode == 'dead'
    assert not g._movement_batch and not g._running_step
    p = prepare(g)
    p.body_reserve = 250
    for _ in range(5):
        g.move(1, 0)
    assert p.x == 35 and p.turns == 6
    p = prepare(g)
    p.hp = 1
    p.saturation = 50
    p.stamina = 0
    p.status['asleep'] = 3
    g.click_map(p.x + 1, p.y)
    assert p.x == 30 and p.turns == 1 and p.status['asleep'] == 2
    g.end_turn()
    assert p.hp == 2 and p.stamina == 6 and p.status['asleep'] == 1
    g.end_turn()
    assert p.status['asleep'] == 0
    p = prepare(g)
    p.saturation = 0
    p.items = [Item('crackers'), Item('water')]
    for it in p.items:
        it.cursed = False
    g.do_eat(p.items[0])
    g.do_quaff(p.items[0])
    assert p.saturation == 20 and not p.items and p.turns == 2
    salt = Item('salt water')
    salt.cursed = False
    p.items.append(salt)
    g.do_quaff(salt)
    assert p.saturation == 15 and p.stamina == 48
    p.sanity = -2
    assert save_game(os.path.join(tmp, 'survival.json'), g)
    assert load_game(os.path.join(tmp, 'survival.json'), g)
    assert (g.player.saturation, g.player.stamina, g.player.sanity) == (15, 48, -2)
    g.draw()
    g.show_char()
    g.draw()
    g.world.storage.cleanup()
pygame.quit()
print('NUTRITION AND STAMINA OK')
