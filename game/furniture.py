"""Furniture registry and persistent instances. Coordinates are chunk-local.

Footprints cannot straddle chunk boundaries in this version; pushing can move
the entire instance into a neighbour when all its cells fit there.
"""
from dataclasses import dataclass, field
from .items import Item
from . import mapgen as MG

FURNITURE = {
    'box': dict(name='Картонная коробка',size=(1,1),material='картон',capacity=6,portable=True,comfort=0,work=0,opaque=False,glyph='□',color=(162,126,78)),
    'nightstand': dict(name='Тумбочка',size=(1,1),material='дерево',capacity=10,portable=False,comfort=0,work=0,opaque=False,glyph='▣',color=(145,105,62)),
    'wardrobe': dict(name='Шкаф',size=(1,2),material='дерево',capacity=24,portable=False,comfort=0,work=0,opaque=True,glyph='▥',color=(120,82,48)),
    'chair': dict(name='Стул',size=(1,1),material='дерево',capacity=0,portable=False,comfort=1,work=0,opaque=False,glyph='h',color=(156,115,70)),
    'sofa': dict(name='Диван',size=(2,1),material='ткань',capacity=0,portable=False,comfort=2,work=0,opaque=False,glyph='∩',color=(101,128,101)),
    'bed': dict(name='Кровать',size=(1,2),material='металл/ткань',capacity=0,portable=False,comfort=3,work=0,opaque=False,glyph='π',color=(161,163,174)),
    'table': dict(name='Рабочий стол',size=(2,1),material='дерево',capacity=0,portable=False,comfort=0,work=2,opaque=False,glyph='╤',color=(170,130,75)),
    'barricade': dict(name='Деревянная баррикада',size=(1,1),material='доски',capacity=0,portable=False,comfort=0,work=0,opaque=True,glyph='≡',color=(153,111,59)),
    'spikes': dict(name='Шипастые колья',size=(1,1),material='дерево/металл',capacity=0,portable=False,comfort=0,work=0,opaque=False,glyph='^',color=(162,142,111),damage=4),
    'pump': dict(name='Насос',size=(1,1),material='металл',capacity=0,portable=False,comfort=0,work=2,opaque=False,glyph='¤',color=(102,126,137)),
    'medical cart': dict(name='Медицинская тележка',size=(1,1),material='металл',capacity=8,portable=False,comfort=0,work=0,opaque=False,glyph='▤',color=(190,205,204)),
    'generator': dict(name='Аварийный генератор',size=(2,1),material='металл',capacity=4,portable=False,comfort=0,work=3,opaque=True,glyph='▦',color=(181,145,67)),
    'valve': dict(name='Запорный вентиль',size=(1,1),material='металл',capacity=0,portable=False,comfort=0,work=1,opaque=False,glyph='⊙',color=(139,157,164)),
    'barn': dict(name='Сарай',size=(2,2),material='дерево',capacity=20,portable=False,comfort=0,work=0,opaque=True,glyph='▥',color=(133,94,52)),
    'lamp post': dict(name='Уличный фонарь',size=(1,1),material='металл',capacity=0,portable=False,comfort=0,work=0,opaque=False,glyph='†',color=(205,190,110)),
}


@dataclass
class Furniture:
    kind: str
    x: int
    y: int
    rotated: bool = False
    contents: list = field(default_factory=list)

    @property
    def spec(self): return FURNITURE[self.kind]

    def cells(self, x=None, y=None, rotated=None):
        x=self.x if x is None else x
        y=self.y if y is None else y
        rotated=self.rotated if rotated is None else rotated
        w,h=self.spec['size']
        if rotated: w,h=h,w
        return {(x+dx,y+dy) for dx in range(w) for dy in range(h)}

    def near(self, x,y):
        return min(max(abs(x-a),abs(y-b)) for a,b in self.cells())<=1

    def serialize(self):
        return dict(kind=self.kind,x=self.x,y=self.y,rotated=self.rotated,
                    contents=[it.to_dict() for it in self.contents])

    @classmethod
    def deserialize(cls,data):
        return cls(data['kind'],data['x'],data['y'],bool(data.get('rotated',False)),
                   [Item.from_dict(it) for it in data.get('contents',[])])


def can_place(level, furniture, x,y, rotated=None, player=None):
    for pos in furniture.cells(x,y,rotated):
        if not level.in_bounds(*pos) or level.at(*pos) not in (MG.FLOOR,MG.RUBBLE):
            return False
        other=level.furniture_at(*pos)
        if other is not None and other is not furniture: return False
        if level.monster_at(*pos) or pos in level.items or pos==player: return False
    return True


def populate(level,rng):
    """Sparse fixtures and enough basic supplies to try the first recipes."""
    kinds=('box','nightstand','wardrobe','chair','sofa','bed','table')
    for index,room in enumerate(level.rooms[1::4]):
        obj=Furniture(kinds[index%len(kinds)],room.x1+1,room.y1+1)
        if can_place(level,obj,obj.x,obj.y):
            level.furniture.append(obj)
            if obj.spec['capacity']:
                fill_loot(obj,rng)


LOOT = {
    'box': [('wood plank',5,1,3),('nails',5,1,4),('scrap metal',4,1,2),('cord',4,1,2),('fuel',3,1,2),('crackers',3,1,1),('potato',3,1,2),('cardboard',4,1,3)],
    'nightstand': [('thread',5,1,3),('needle',3,1,1),('lighter',2,1,1),('water',4,1,1),('chocolate',3,1,1),('salt',3,1,2),('cooking pot',1,1,1)],
    'wardrobe': [('rag',6,1,4),('cord',4,1,2),('wood plank',3,1,2),('war hammer',2,1,1),('food ration',2,1,1),('salted nuts',3,1,1),('carrot',2,1,2)],
}

def fill_loot(obj,rng):
    """Seeded once during generation, empty containers are intentional."""
    if rng.random()<.25: return
    pool=LOOT.get(obj.kind,[])
    for _ in range(rng.randint(1,4)):
        remaining=obj.spec['capacity']-sum(it.count for it in obj.contents)
        if remaining<=0 or not pool: break
        roll=rng.uniform(0,sum(row[1] for row in pool))
        chosen=pool[-1]
        for row in pool:
            roll-=row[1]
            if roll<=0: chosen=row; break
        name,weight,low,high=chosen
        obj.contents.append(Item(name,count=min(remaining,rng.randint(low,high)),rng=rng))
