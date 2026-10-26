"""Питание, запасы организма, усталость и сон; без зависимости от pygame."""
SATURATION_MAX = 100
RESERVE_STEP = 50
STAMINA_MAX = 50
MEAL_WINDOW = 30
DEPLETION_INTERVAL = 20
EXHAUSTION_GRACE = 1000
FOOD_PAIRS = (frozenset(('salty', 'sweet')), frozenset(('dry', 'moist')),
              frozenset(('fried', 'moist')))
WARM_COLORS = ((222, 190, 78), (216, 130, 56), (222, 222, 234), (204, 62, 62))
COLD_COLORS = ((156, 92, 200), (92, 48, 140), (42, 52, 120))


def initialize(p):
    p.saturation = SATURATION_MAX
    p.body_reserve = RESERVE_STEP  # +1, 0/50
    p.stamina = STAMINA_MAX
    p.sanity = 50
    p.awake_turns = 0
    p.sleep_recovery = 0
    p.last_nourished_turn = 0
    p.meal = None
    p.walk_steps = 0
    p.sleep_healing = 0
    p.moved_this_turn = False
    p.movement_delay = 0


def advance_sanity(p, sleeping=False, threatened=False, hurt=False):
    """Turn-based mental fatigue; never advances while merely rendering."""
    if sleeping:
        p.awake_turns=max(0,p.awake_turns-10)
        p.sleep_recovery+=1
        if p.sleep_recovery>=5:
            p.sanity=min(50,p.sanity+1)
            p.sleep_recovery=0
    else:
        p.sleep_recovery=0
        p.awake_turns+=1
        if p.awake_turns>=600 and p.awake_turns%100==0:
            p.sanity-=1
    if threatened and p.turns%20==0:
        p.sanity-=1
    if hurt:
        p.sanity-=1
    p.sanity=max(-50,min(50,p.sanity))


def reserve_level(p):
    magnitude = abs(p.body_reserve) // RESERVE_STEP
    return magnitude if p.body_reserve >= 0 else -magnitude


def reserve_color(p):
    colors = WARM_COLORS if p.body_reserve > 0 else COLD_COLORS
    return colors[max(0, abs(reserve_level(p)) - 1) % len(colors)]


def change_reserve(p, amount):
    p.body_reserve += int(amount)
    # Истощение меняет потолок здоровья, а не наносит удар/урон от голода.
    p.hp = min(p.hp, p.max_hp)


def add_saturation(p, amount):
    amount = int(amount)
    overflow = max(0, p.saturation + amount - SATURATION_MAX)
    p.saturation = max(0, min(SATURATION_MAX, p.saturation + amount))
    if overflow:
        change_reserve(p, overflow)
    if amount > 0:
        p.last_nourished_turn = p.turns
    return overflow


def nourish(p, spec):
    """Начисляет только прирост общего бонуса блюда, без повторного бонуса воды."""
    value = spec.get('saturation', 0)
    if value <= 0:
        return dict(gain=0, bonus=0, relief=0)
    if p.meal is None or p.turns - p.meal['started'] >= MEAL_WINDOW:
        p.meal = dict(started=p.turns, raw=0, credited=0, food=False,
                      water=False, tags=[], relief=0)
    meal = p.meal
    old_raw, old_credit = meal['raw'], meal['credited']
    meal['raw'] += value
    meal['food'] |= spec.get('kind') == 'food'
    meal['water'] |= bool(spec.get('hydrating'))
    tags = set(meal['tags']) | set(spec.get('food_tags', ()))
    meal['tags'] = sorted(tags)
    # Теги внутри одного продукта не дают бонуса: сочетать надо разные продукты.
    previous = set(meal.get('previous_tags', ()))
    current = set(spec.get('food_tags', ()))
    completed = set(meal.get('pairs', ()))
    for index, pair in enumerate(FOOD_PAIRS):
        a, b = sorted(pair)
        if (a in previous and b in current) or (b in previous and a in current):
            completed.add(index)
    meal['pairs'] = sorted(completed)
    meal['pair_count'] = len(completed)
    multiplier = min(2.0, 1.0 + 0.5 * meal['pair_count'])
    if meal['water'] and meal['food']:
        multiplier *= 2
    credit = int(meal['raw'] * multiplier)
    gain = credit - old_credit
    meal['credited'] = credit
    meal['previous_tags'] = sorted(tags)
    relief = 0
    if meal['water'] and meal['food'] and tags & {'dry', 'salty'}:
        # Одна порция воды снимает до пяти единиц дефицита за одно блюдо.
        relief = min(max(0, -p.body_reserve), 5 - meal['relief'])
        if relief:
            change_reserve(p, relief)
            meal['relief'] += relief
    add_saturation(p, gain)
    return dict(gain=gain, bonus=max(0, gain - (meal['raw'] - old_raw)), relief=relief)


def sprint_length(p, rng):
    threshold = rng.randint(2, 42) if p.sanity <= 0 else 21
    level = reserve_level(p)
    stamina = max(0, p.stamina)
    score = p.hp - stamina if level < 0 or level >= 10 else p.hp + stamina + p.clothing_mobility
    length = 3 if score > threshold else 2
    if level >= 10:
        return 1
    if level >= 5:
        return min(2, length)
    return length


def movement(p, running=False):
    p.moved_this_turn = True
    if running:
        if p.clothing_weight>4:
            p.stamina=max(-STAMINA_MAX,p.stamina-1)
        if p.stamina > 0:
            p.stamina -= 1
        else:
            p.take_damage(1, cause='overexertion')
    else:
        p.walk_steps += 1
        if p.walk_steps % 10 == 0:
            p.stamina = max(-STAMINA_MAX, p.stamina - 1)
    level = reserve_level(p)
    if level >= 5:
        # Ожирение: дополнительный мировой ход каждые 5 клеток, при +10 каждые 2.
        interval = 2 if level >= 10 else 5
        p.slow_steps = getattr(p, 'slow_steps', 0) + 1
        if p.slow_steps % interval == 0:
            p.movement_delay += 1


def advance(p, sleeping=False, resting=False):
    interval = DEPLETION_INTERVAL
    if any(it.name == 'ring of hunger' for it in p.equipped_of('ring')):
        interval *= 2
    if p.turns % interval == 0:
        if p.saturation > 0:
            p.saturation -= 1
        elif p.body_reserve > 0:
            change_reserve(p, -1)
        elif p.turns - p.last_nourished_turn >= EXHAUSTION_GRACE:
            change_reserve(p, -1)
    if sleeping or resting:
        p.stamina = min(STAMINA_MAX, p.stamina + 3)
        p.sleep_healing += p.saturation
        heal, p.sleep_healing = divmod(p.sleep_healing, SATURATION_MAX)
        if heal:
            p.heal(heal)
        if p.hp == p.max_hp:
            p.sleep_healing = 0
    elif not p.moved_this_turn and p.turns % 5 == 0:
        p.stamina = min(STAMINA_MAX, p.stamina + 1)
    p.moved_this_turn = False
