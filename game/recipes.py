"""Data-driven recipes, resource accounting and construction puzzle model."""
import math
from collections import Counter

RECIPES = {
    'jacket': dict(name='Куртка',materials={'rag':2,'thread':1},tools=['needle'],
                   result='crafted jacket',turns=20,skill='crafting',xp=25),
    'barricade': dict(name='Деревянная баррикада',materials={'wood plank':3,'nails':4},tools=['war hammer'],
                      furniture='barricade',turns=16,skill='building',xp=25),
}

RECIPES.update({
    'trail_mix': dict(name='Походная смесь',materials={'salted nuts':1,'chocolate':1},tools=[],result='trail mix',turns=4,skill='crafting',xp=10,category='food'),
    'soup': dict(name='Овощной суп',materials={'carrot':1,'potato':1,'water':1,'fuel':1},tools=['cooking pot','lighter'],result='vegetable soup',turns=18,skill='crafting',xp=20,category='food'),
    'fried_potatoes': dict(name='Жареная картошка',materials={'potato':2,'salt':1,'fuel':1},tools=['cooking pot','lighter'],result='fried potatoes',turns=14,skill='crafting',xp=15,category='food'),
    'spear': dict(name='Самодельное копьё',materials={'wood plank':1,'scrap metal':1,'cord':1},tools=['war hammer'],result='improvised spear',turns=18,skill='crafting',xp=25,category='weapons'),
    'club': dict(name='Дубинка с гвоздями',materials={'wood plank':1,'nails':3},tools=['war hammer'],result='nailed club',turns=12,skill='crafting',xp=20,category='weapons'),
})
RECIPES['jacket']['category']='equipment'
RECIPES['barricade']['category']='defense'
for _kind,_name,_materials,_turns in (
    ('box','Коробка',{'cardboard':3,'cord':1},8),
    ('chair','Стул',{'wood plank':2,'nails':3},16),
    ('table','Стол',{'wood plank':4,'nails':6},24),
    ('nightstand','Тумбочка',{'wood plank':3,'nails':5},22),
    ('wardrobe','Шкаф',{'wood plank':6,'nails':8},32),
    ('bed','Кровать',{'wood plank':4,'nails':6,'rag':4,'cord':2},28),
    ('sofa','Диван',{'wood plank':4,'nails':5,'rag':6,'thread':2},30),
    ('spikes','Шипастые колья',{'wood plank':3,'scrap metal':2,'cord':1},20)):
    RECIPES['build_'+_kind]=dict(name=_name,materials=_materials,tools=['war hammer'],furniture=_kind,
        turns=_turns,skill='building',xp=25,category='defense' if _kind=='spikes' else 'furniture')

def skill_level(player,name):
    return min(10,player.skills.get(name,0)//100)

def duration(player,recipe,work=0):
    return max(2,math.ceil(recipe['turns']/(1+.2*skill_level(player,recipe['skill'])+.25*work)))

def missing(player,recipe):
    amounts=Counter()
    for item in player.items:
        amounts[item.name]+=item.count
    return [f'{name}: {n-amounts[name]}' for name,n in recipe['materials'].items() if amounts[name]<n] + [name for name in recipe['tools'] if not amounts[name]]

def consume(player,recipe):
    """Called only on successful completion; tools are never consumed."""
    if missing(player,recipe): return False
    for name,n in recipe['materials'].items():
        for item in list(player.items):
            if item.name!=name: continue
            used=min(n,item.count)
            item.count-=used; n-=used
            if item.count==0: player.items.remove(item)
            if not n: break
    return True

def fits_result(player,recipe):
    """Check capacity after consumed stacks disappear, without mutating them."""
    remaining=dict(recipe['materials'])
    slots=len(player.items)
    for item in player.items:
        used=min(item.count,remaining.get(item.name,0))
        remaining[item.name]=remaining.get(item.name,0)-used
        if used==item.count: slots-=1
    return slots<26


class PackingPuzzle:
    # Distinct shapes, guaranteed solvable on an 8x8 grid, no timer.
    shapes=(((0,0),(1,0),(2,0),(3,0)),
            ((0,0),(1,0),(2,0),(3,0),(4,0)),
            ((0,0),(0,1),(0,2),(1,2)),
            ((0,0),(1,0),(0,1),(1,1)),
            ((0,0),(1,0),(2,0),(1,1)),
            ((0,0),(1,0),(1,1),(2,1)))

    def __init__(self):
        self.placements={}

    def shape(self,index,rotation=0):
        points=self.shapes[index]
        for _ in range(rotation%4):
            points=tuple((-y,x) for x,y in points)
        mx=min(x for x,y in points); my=min(y for x,y in points)
        return {(x-mx,y-my) for x,y in points}

    def place(self,index,x,y,rotation=0):
        cells={(x+dx,y+dy) for dx,dy in self.shape(index,rotation)}
        occupied=set().union(*(v for k,v in self.placements.items() if k!=index))
        if cells & occupied or any(not(0<=a<8 and 0<=b<8) for a,b in cells): return False
        self.placements[index]=cells
        return True

    @property
    def complete(self): return len(self.placements)==len(self.shapes)
