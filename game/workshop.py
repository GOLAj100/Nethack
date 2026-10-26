"""Furniture interactions, recipe menus and paced, interruptible work."""
import math
import pygame
from engine import config as C
from .furniture import Furniture, can_place
from .recipes import RECIPES, PackingPuzzle, missing, duration, consume, skill_level, fits_result
from .items import Item
from .lang import item_name


class Workshop:
    def __init__(self,game):
        self.g=game
        self.job=None
        self.timer=0
        self.seated=None
        self.puzzle=None
        self.selected=0
        self.rotation=0
        self.cursor=(0,0)
        self.build_site=None
        self.notice=''

    def available(self):
        g=self.g
        return g.player is not None and g.player.alive and not g.player.is_asleep() and g.views.mode!='board'

    def neighbours(self):
        g=self.g; p=g.player
        levels=[g.level]
        if g.world:
            w=g.world
            levels=[w.chunk(cx,cy,p.world_z)
                    for cy in range((p.chunk_y*w.h+p.y-2)//w.h,(p.chunk_y*w.h+p.y+2)//w.h+1)
                    for cx in range((p.chunk_x*w.w+p.x-2)//w.w,(p.chunk_x*w.w+p.x+2)//w.w+1)]
        result=[]
        for lv in levels:
            px=p.x+(p.chunk_x-lv.chunk_x)*lv.w
            py=p.y+(p.chunk_y-lv.chunk_y)*lv.h
            result.extend((lv,obj) for obj in lv.furniture if obj.near(px,py))
        return result

    def touch(self,lv):
        lv._furniture_index_size=-1
        if self.g.world:
            self.g.world.visited.add((lv.chunk_x,lv.chunk_y,lv.world_z))
        self.g._visible_world_key=None
        self.g.update_lighting()

    def comfort(self):
        if self.seated is None: return 0
        lv,obj,where=self.seated
        p=self.g.player
        if (p.chunk_x,p.chunk_y,p.world_z,p.x,p.y)!=where or obj not in lv.furniture or (p.x,p.y) not in obj.cells():
            self.seated=None
            return 0
        return obj.spec['comfort']

    def open(self):
        if not self.available(): return
        g=self.g
        entries=['Мебель рядом','Поставить переносимую мебель','Создать предмет / готовка','Строительство',
                 f"Строитель: {skill_level(g.player,'building')} | Ремесло: {skill_level(g.player,'crafting')}",'Назад']
        def choose(i):
            if i==0: self.open_nearby()
            elif i==1: self.open_carried()
            elif i==2: self.open_recipes(False)
            elif i==3: self.open_recipes(True)
            elif i==4:
                g.show_text('Навыки',[(f'{k}: {v} XP (уровень {skill_level(g.player,k)})',C.WHITE) for k,v in g.player.skills.items()]+[('100 XP за уровень; пропуск пазла с уровня 3.',C.GRAY)])
        g.show_menu('Мастерская и мебель',entries,choose,width=52)

    def open_nearby(self):
        entries=self.neighbours()
        if not entries:
            self.g.msg('Рядом нет мебели.',C.MSG_HINT); return
        self.g.show_menu('Мебель рядом',[obj.spec['name'] for lv,obj in entries],
                         lambda i: self.open_object(*entries[i]) if i is not None else None,width=44)

    def nearby(self,lv,obj):
        return obj in lv.furniture and any(a is lv and b is obj for a,b in self.neighbours())

    def open_object(self,lv,obj):
        if not self.nearby(lv,obj): return
        spec=obj.spec
        actions=[]
        if spec['capacity']: actions += [('Открыть контейнер',lambda:self.container(lv,obj))]
        if spec['comfort']:
            def sit():
                self.sit(lv,obj)
            actions += [('Лечь / сесть',sit)]
        actions += [('Сдвинуть',lambda:self.move_object(lv,obj)),('Повернуть',lambda:self.rotate(lv,obj))]
        actions += [('Сбросить в соседний проём',lambda:self.choose_drop(lv,obj))]
        if spec['portable']: actions += [('Взять в инвентарь',lambda:self.pack(lv,obj))]
        actions += [('Свойства',lambda:self.g.show_text(spec['name'],[(f"Материал: {spec['material']}",C.WHITE),
                    (f"Размер: {spec['size']} | Вместимость: {spec['capacity']}",C.WHITE),
                    (f"Комфорт: {spec['comfort']} | Работа: {spec['work']}",C.WHITE)]))]
        self.g.show_menu(spec['name'],[label for label,fn in actions],lambda i:actions[i][1]() if i is not None else None,width=48)

    def container(self,lv,obj):
        if not self.nearby(lv,obj): return
        g=self.g
        def choose(i):
            if i==0:
                items=list(obj.contents)
                def take(index):
                    if index is None or not self.nearby(lv,obj): return
                    item=items[index]
                    if item in obj.contents and len(g.player.items)<26:
                        obj.contents.remove(item); g.player.items.append(item)
                        self.touch(lv); g.end_turn()
                    else: g.msg('Инвентарь заполнен.',C.MSG_WARN)
                if items: g.show_menu('Взять',[it.label() for it in items],take,width=48)
                else: g.msg('Контейнер пуст.',C.MSG_HINT)
            elif i==1:
                items=[it for it in g.player.items if not it.equipped]
                def put(index):
                    if index is None or not self.nearby(lv,obj): return
                    item=items[index]
                    used=sum(it.count for it in obj.contents)
                    if item in g.player.items and used+item.count<=obj.spec['capacity']:
                        g.player.items.remove(item); obj.contents.append(item)
                        self.touch(lv); g.end_turn()
                    else: g.msg('Не хватает места в контейнере.',C.MSG_WARN)
                if items: g.show_menu('Положить',[it.label() for it in items],put,width=48)
        self.g.show_menu(f"{obj.spec['name']} ({sum(it.count for it in obj.contents)}/{obj.spec['capacity']})",['Взять','Положить','Назад'],choose,width=48)

    def player_cell(self,lv):
        p=self.g.player
        return (p.x,p.y) if lv is self.g.level else None

    def occupied(self,lv,obj):
        return self.g.level is lv and (self.g.player.x,self.g.player.y) in obj.cells()

    def sit(self,lv,obj):
        if not self.nearby(lv,obj) or not obj.spec['comfort']: return False
        g=self.g; p=g.player
        px=p.x+(p.chunk_x-lv.chunk_x)*lv.w
        py=p.y+(p.chunk_y-lv.chunk_y)*lv.h
        cells=[pos for pos in obj.cells() if max(abs(pos[0]-px),abs(pos[1]-py))<=1
               and not lv.monster_at(*pos)]
        if not cells:
            g.msg('Нет доступного места.',C.MSG_WARN); return False
        x,y=min(cells,key=lambda pos:abs(pos[0]-px)+abs(pos[1]-py))
        if g.world: g.level=g.world.chunk(lv.chunk_x,lv.chunk_y,lv.world_z,visit=True)
        p.x,p.y=x,y
        p.chunk_x,p.chunk_y,p.world_z=lv.chunk_x,lv.chunk_y,lv.world_z
        lv.set_player_pos(x,y); lv.recompute_fov(x,y)
        g._visible_world_key=None; g._held_move=None
        self.seated=(lv,obj,(p.chunk_x,p.chunk_y,p.world_z,p.x,p.y))
        g.end_turn(); g.update_lighting()
        g.msg(f"Вы устроились: {obj.spec['name']}. Комфорт +{obj.spec['comfort']}.",C.MSG_GOOD)
        return True

    def work_bonus(self):
        return max((obj.spec['work'] for _,obj in self.neighbours()),default=0)

    def choose_drop(self,lv,obj):
        self.g.show_menu('В какую сторону сбросить?',['Север','Восток','Юг','Запад'],
                        lambda i:self.drop_down(lv,obj,*((0,-1),(1,0),(0,1),(-1,0))[i]) if i is not None else None,width=46)

    def drop_down(self,lv,obj,dx,dy):
        from . import mapgen as MG
        if not self.nearby(lv,obj) or self.occupied(lv,obj) or not self.g.world: return False
        w=self.g.world
        cx,x=divmod(obj.x+dx,lv.w); cy,y=divmod(obj.y+dy,lv.h)
        cx+=lv.chunk_x; cy+=lv.chunk_y
        upper=w.chunk(cx,cy,lv.world_z)
        footprint=obj.cells(x,y)
        if any(not upper.in_bounds(*pos) or upper.at(*pos)!=MG.AIR or upper.furniture_at(*pos)
               or upper.monster_at(*pos) or pos in upper.items or pos==self.player_cell(upper) for pos in footprint):
            self.g.msg('Вся мебель должна помещаться над открытым проёмом.',C.MSG_WARN); return False
        z=lv.world_z-1
        while w.exists(z):
            target=w.chunk(cx,cy,z)
            if any(target.furniture_at(*pos) or target.monster_at(*pos) or pos==self.player_cell(target) for pos in footprint): break
            if all(target.at(*pos)==MG.AIR for pos in footprint):
                z-=1; continue
            if can_place(target,obj,x,y,player=self.player_cell(target)):
                lv.furniture.remove(obj); target.furniture.append(obj); obj.x,obj.y=x,y
                self.seated=None; self.touch(lv); self.touch(target)
                self.g.end_turn()
                self.g.msg(f"{obj.spec['name']} упала на Z={z}.",C.MSG_INFO)
                return True
            break
        self.g.msg('Нет свободной площадки для приземления.',C.MSG_WARN)
        return False

    def move_object(self,lv,obj):
        directions=((0,-1),(1,0),(0,1),(-1,0))
        def choose(i):
            if i is None or not self.nearby(lv,obj): return
            if self.occupied(lv,obj):
                self.g.msg('Сначала встаньте с мебели.',C.MSG_WARN); return
            dx,dy=directions[i]
            x,y=obj.x+dx,obj.y+dy
            target=lv
            if self.g.world and not lv.in_bounds(x,y):
                cx,x=divmod(x,lv.w); cy,y=divmod(y,lv.h)
                target=self.g.world.chunk(lv.chunk_x+cx,lv.chunk_y+cy,lv.world_z)
            if not can_place(target,obj,x,y,player=self.player_cell(target)):
                self.g.msg('Вся площадь мебели должна быть свободна.',C.MSG_WARN); return
            if target is not lv: lv.furniture.remove(obj); target.furniture.append(obj)
            obj.x,obj.y=x,y
            self.seated=None
            self.touch(lv); self.touch(target); self.g.end_turn()
        self.g.show_menu('Сдвинуть на клетку',['Север','Восток','Юг','Запад'],choose,width=38)

    def rotate(self,lv,obj):
        if self.occupied(lv,obj): return
        if self.nearby(lv,obj) and can_place(lv,obj,obj.x,obj.y,not obj.rotated,self.player_cell(lv)):
            obj.rotated=not obj.rotated; self.seated=None; self.touch(lv); self.g.end_turn()
        else: self.g.msg('Недостаточно места для поворота.',C.MSG_WARN)

    def pack(self,lv,obj):
        if self.occupied(lv,obj): return
        if not self.nearby(lv,obj): return
        if len(self.g.player.carried_furniture)>=2:
            self.g.msg('Можно нести не больше двух небольших коробок.',C.MSG_WARN); return
        self.g.player.carried_furniture.append(obj.serialize()); lv.furniture.remove(obj)
        self.touch(lv); self.g.end_turn()

    def open_carried(self):
        cargo=self.g.player.carried_furniture
        if not cargo: self.g.msg('Переносимой мебели нет.',C.MSG_HINT); return
        def choose(i):
            if i is None: return
            data=cargo[i]; obj=Furniture.deserialize(data)
            def place(lv,x,y):
                if data not in cargo or not can_place(lv,obj,x,y,player=self.player_cell(lv)):
                    self.g.msg('Место занято.',C.MSG_WARN); return
                obj.x,obj.y=x,y; lv.furniture.append(obj); cargo.remove(data)
                self.touch(lv); self.g.end_turn()
            self.choose_site(place)
        self.g.show_menu('Поставить',[Furniture.deserialize(d).spec['name'] for d in cargo],choose,width=44)

    def choose_site(self,callback):
        p=self.g.player; lv=self.g.level
        sites=[(p.x,p.y-1),(p.x+1,p.y),(p.x,p.y+1),(p.x-1,p.y)]
        def choose(i):
            if i is None: return
            x,y=sites[i]; target=lv
            if self.g.world:
                cx,x=divmod(x,lv.w); cy,y=divmod(y,lv.h)
                target=self.g.world.chunk(lv.chunk_x+cx,lv.chunk_y+cy,lv.world_z)
            callback(target,x,y)
        self.g.show_menu('Выбрать соседнюю клетку',['Север','Восток','Юг','Запад'],choose,width=44)

    def open_recipes(self,building,category=None):
        if category is None:
            categories=[('furniture','Мебель'),('defense','Оборона'),('disassembly','Разбор окружения')] if building else [('food','Еда и готовка'),('weapons','Оружие'),('equipment','Одежда'),('disassembly','Разбор одежды')]
            self.g.show_menu('Категория',[label for key,label in categories],
                lambda i:self.open_recipes(building,categories[i][0]) if i is not None else None,width=44)
            return
        names=[name for name,r in RECIPES.items() if bool(r.get('furniture'))==building and r.get('category')==category]
        def choose(i):
            if i is None: return
            name=names[i]; recipe=RECIPES[name]
            lines=[(recipe['name'],C.CYAN)]
            lines += [(f'{item_name(k)} ×{v}',C.WHITE) for k,v in recipe['materials'].items()]
            lines += [('Инструмент: '+item_name(k),C.GRAY) for k in recipe['tools']]
            work=max((obj.spec['work'] for _,obj in self.neighbours()),default=0)
            labels=[f"Начать — {duration(self.g.player,recipe,work)} ходов",'Показать требования','Назад']
            def confirm(idx):
                if idx==1: self.g.show_text('Рецепт',lines)
                elif idx==0:
                    absent=missing(self.g.player,recipe)
                    if absent: self.g.msg('Не хватает: '+', '.join(absent),C.MSG_WARN); return
                    if building: self.choose_site(lambda lv,x,y:self.start_puzzle(name,lv,x,y))
                    else: self.start_job(name)
            self.g.show_menu(recipe['name'],labels,confirm,width=52)
        self.g.show_menu('Строительство' if building else 'Крафт',[RECIPES[n]['name'] for n in names],choose,width=48)

    def start_puzzle(self,name,lv,x,y):
        obj=Furniture(RECIPES[name]['furniture'],x,y)
        if not can_place(lv,obj,x,y,player=self.player_cell(lv)):
            self.g.msg('Место занято.',C.MSG_WARN); return
        self.build_site=(name,lv,x,y)
        self.puzzle=PackingPuzzle(); self.selected=0; self.rotation=0; self.cursor=(0,0); self.notice=''
        self.g.mode='build_puzzle'; self.g._held_move=None

    def start_job(self,name,site=None):
        if missing(self.g.player,RECIPES[name]): return
        work=max((obj.spec['work'] for _,obj in self.neighbours()),default=0)
        p=self.g.player
        self.job=dict(name=name,remaining=duration(p,RECIPES[name],work),site=site,
                      location=(p.chunk_x,p.chunk_y,p.world_z,p.x,p.y),work=work)
        self.timer=.15; self.g.mode='work'; self.g._held_move=None

    def cancel_job(self):
        self.job=None; self.g.mode='play'
        self.g.msg('Работа остановлена. Материалы сохранены.',C.MSG_HINT)

    def threat(self):
        g=self.g; p=g.player
        cells=g.world.view_cells(p) if g.world else {pos:(g.level,*pos) for pos in g.level.visible}
        return any(lv.monster_at(x,y) is not None for lv,x,y in cells.values())

    def update(self,dt):
        if self.job is None: return
        self.timer-=dt
        if self.timer>0: return
        self.timer=.15
        g=self.g; p=g.player
        if (p.chunk_x,p.chunk_y,p.world_z,p.x,p.y)!=self.job['location'] or self.work_bonus()<self.job['work']:
            self.cancel_job(); return
        if not p.alive or p.is_asleep() or self.threat(): self.cancel_job(); return
        hp=p.hp; g.end_turn()
        if not p.alive: self.job=None; return
        if p.hp<hp or p.is_asleep() or self.threat(): self.cancel_job(); return
        self.job['remaining']-=1
        if self.job['remaining']>0: return
        recipe=RECIPES[self.job['name']]
        site=self.job['site']
        if site:
            lv,x,y=site; obj=Furniture(recipe['furniture'],x,y)
            if not can_place(lv,obj,x,y,player=self.player_cell(lv)): self.cancel_job(); return
        if not site and not fits_result(p,recipe): self.cancel_job(); return
        if not consume(p,recipe): self.cancel_job(); return
        if site:
            lv.furniture.append(obj); self.touch(lv)
        else: p.items.append(Item(recipe['result'],rng=g.rng))
        p.skills[recipe['skill']]=p.skills.get(recipe['skill'],0)+recipe['xp']
        g.msg('Готово: '+recipe['name'],C.MSG_GOOD)
        self.job=None; g.mode='play'

    def board(self):
        r=self.g.r
        step=max(16,min(r.surface.get_width()//14,r.surface.get_height()//14))
        return pygame.Rect(2*r.cw,4*r.ch,step*8,step*8),step

    def confirm_puzzle(self,skip=False):
        if self.puzzle.complete or (skip and skill_level(self.g.player,'building')>=3):
            name,lv,x,y=self.build_site
            self.start_job(name,(lv,x,y))
        else: self.notice='Уложите все детали без пересечений.'

    def key(self,event):
        if event.key==pygame.K_ESCAPE:
            if self.g.mode=='work': self.cancel_job()
            else: self.g.mode='play'
            return
        if self.g.mode=='work': return
        if pygame.K_1<=event.key<=pygame.K_6: self.selected=event.key-pygame.K_1
        elif event.key==pygame.K_r: self.rotation=(self.rotation+1)%4
        elif event.key in (pygame.K_LEFT,pygame.K_RIGHT,pygame.K_UP,pygame.K_DOWN):
            dx,dy={pygame.K_LEFT:(-1,0),pygame.K_RIGHT:(1,0),pygame.K_UP:(0,-1),pygame.K_DOWN:(0,1)}[event.key]
            self.cursor=(max(0,min(7,self.cursor[0]+dx)),max(0,min(7,self.cursor[1]+dy)))
        elif event.key==pygame.K_SPACE: self.place_piece(*self.cursor)
        elif event.key in (pygame.K_DELETE,pygame.K_BACKSPACE): self.puzzle.placements.pop(self.selected,None)
        elif event.key==pygame.K_RETURN: self.confirm_puzzle()
        elif event.key==pygame.K_s: self.confirm_puzzle(True)

    def place_piece(self,x,y):
        self.notice='' if self.puzzle.place(self.selected,x,y,self.rotation) else 'Деталь выходит за край или пересекается.'

    def mouse(self,event):
        if self.g.mode!='build_puzzle' or event.type!=pygame.MOUSEBUTTONDOWN: return
        rect,step=self.board()
        if rect.collidepoint(event.pos):
            self.cursor=((event.pos[0]-rect.x)//step,(event.pos[1]-rect.y)//step)
            if event.button==1: self.place_piece(*self.cursor)
            elif event.button==3:
                for i,cells in list(self.puzzle.placements.items()):
                    if self.cursor in cells: self.puzzle.placements.pop(i)
        elif event.button==1:
            for i in range(6):
                if self.piece_rect(i).collidepoint(event.pos): self.selected=i

    def piece_rect(self,i):
        rect,step=self.board()
        return pygame.Rect(rect.right+20,rect.y+i*step*1.3,step*4,step)

    def draw(self):
        g=self.g; r=g.r
        if g.display: g.display.scene=None
        r.clear()
        if g.mode=='work':
            if self.job:
                r.text(3,4,'Работа: '+RECIPES[self.job['name']]['name'],C.WHITE)
                r.text(3,6,f"Осталось {self.job['remaining']} ходов. Esc — остановить.",C.CYAN)
            return
        rect,step=self.board()
        colors=(C.ORANGE,C.CYAN,C.GREEN,C.PURPLE,C.YELLOW,C.PINK)
        r.text(2,1,'Уложите все детали в поле 8×8',C.WHITE)
        for x in range(8):
            for y in range(8): pygame.draw.rect(r.surface,C.DARK_GRAY,(rect.x+x*step,rect.y+y*step,step,step),1)
        for i,cells in self.puzzle.placements.items():
            for x,y in cells: pygame.draw.rect(r.surface,colors[i],(rect.x+x*step+2,rect.y+y*step+2,step-4,step-4))
        x,y=self.cursor
        for dx,dy in self.puzzle.shape(self.selected,self.rotation):
            if x+dx<8 and y+dy<8: pygame.draw.rect(r.surface,C.WHITE,(rect.x+(x+dx)*step,rect.y+(y+dy)*step,step,step),2)
        for i in range(6):
            box=self.piece_rect(i)
            pygame.draw.rect(r.surface,C.WHITE if i==self.selected else C.GRAY,box,1)
            small=max(4,step//5)
            for x,y in self.puzzle.shape(i): pygame.draw.rect(r.surface,colors[i],(box.x+4+x*small,box.y+4+y*small,small-1,small-1))
            r.text(box.x//r.cw+box.w//r.cw-2,box.y//r.ch,str(i+1),C.WHITE)
        row=rect.bottom//r.ch+1
        for i,text in enumerate(('1–6: деталь | R: поворот | ЛКМ/Space: положить',
                                 'ПКМ/Delete: убрать | Enter: начать | Esc: отмена',
                                 'S: пропустить (строитель 3+)',self.notice)):
            r.text(2,row+i,text,C.YELLOW if i==3 else C.GRAY,max_cells=r.surface.get_width()//r.cw-4)
