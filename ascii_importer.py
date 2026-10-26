"""Image-to-ASCII dialog for the tileset editor."""
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser
import pygame
from engine.ascii_art import convert, PALETTES
from engine.background import remove_background


class AsciiImporter:
    def __init__(self, editor):
        self.editor=editor
        self.window=tk.Toplevel(editor.root)
        self.window.title('Картинка → ASCII-спрайт')
        self.window.geometry('900x660')
        self.source=None
        self.result=None
        self.text=''
        self.columns=tk.IntVar(value=16)
        self.palette=tk.StringVar(value='Классика')
        self.colored=tk.BooleanVar(value=True)
        self.invert=tk.BooleanVar(value=False)
        self.contrast=tk.DoubleVar(value=1.0)
        self.status=tk.StringVar(value='Откройте PNG/JPG. Прозрачный PNG лучше подходит для игровых объектов.')
        self.symbol=tk.StringVar(value=editor.char.get())
        self.photos=[]
        self.remove_bg=tk.BooleanVar(value=False)
        self.edges_only=tk.BooleanVar(value=True)
        self.tolerance=tk.DoubleVar(value=30)
        self.bg_color=None
        self._bg_key=None
        self.cleaned=None
        toolbar=ttk.Frame(self.window)
        toolbar.pack(fill='x',padx=8,pady=8)
        ttk.Button(toolbar,text='Открыть картинку…',command=self.open).pack(side='left')
        ttk.Label(toolbar,text='Символ игры:').pack(side='left')
        ttk.Entry(toolbar,textvariable=self.symbol,width=4).pack(side='left')
        ttk.Label(toolbar,text='Столбцы:').pack(side='left')
        ttk.Spinbox(toolbar,from_=4,to=96,textvariable=self.columns,width=5).pack(side='left')
        ttk.Combobox(toolbar,textvariable=self.palette,values=list(PALETTES),state='readonly',width=12).pack(side='left')
        options=ttk.Frame(self.window)
        options.pack(fill='x',padx=8)
        ttk.Checkbutton(options,text='Цвета картинки',variable=self.colored).pack(side='left')
        ttk.Checkbutton(options,text='Инверсия плотности',variable=self.invert).pack(side='left')
        ttk.Label(options,text='Контраст:').pack(side='left')
        ttk.Scale(options,from_=0.4,to=2.5,variable=self.contrast).pack(side='left')
        ttk.Button(options,text='Преобразовать / обновить',command=self.render).pack(side='left')
        bg=ttk.LabelFrame(self.window,text='Удаление однотонного фона (до конвертации)')
        bg.pack(fill='x',padx=8,pady=6)
        ttk.Checkbutton(bg,text='Удалить фон',variable=self.remove_bg,command=self.render).pack(side='left')
        ttk.Checkbutton(bg,text='Только от краёв',variable=self.edges_only,command=self.render).pack(side='left')
        ttk.Label(bg,text='Допуск').pack(side='left')
        ttk.Scale(bg,from_=0,to=150,variable=self.tolerance).pack(side='left')
        ttk.Button(bg,text='Цвет фона…',command=self.choose_background).pack(side='left')
        ttk.Button(bg,text='Авто по углам',command=self.auto_background).pack(side='left')
        panels=ttk.Frame(self.window)
        panels.pack(fill='both',expand=True)
        self.canvases=[]
        for title in ('Изображение после обработки фона','ASCII из множества символов'):
            group=ttk.LabelFrame(panels,text=title)
            group.pack(side='left',fill='both',expand=True,padx=8,pady=8)
            canvas=tk.Canvas(group,width=400,height=350,bg='#101018')
            canvas.pack(fill='both',expand=True)
            self.canvases.append(canvas)
        buttons=ttk.Frame(self.window)
        buttons.pack(fill='x',padx=8,pady=8)
        for label,fn in (('Назначить символу',self.assign),('Экспорт PNG',self.export_png),('Экспорт текста',self.export_text),('PNG без фона',self.export_cleaned)):
            ttk.Button(buttons,text=label,command=fn).pack(side='left')
        ttk.Label(self.window,textvariable=self.status,wraplength=860).pack(padx=8,pady=8)
        ttk.Label(self.window,text='Это ASCII-мозаика внутри спрайта. В клетке 16–64 px мелкие символы сольются: начните с 4–12 столбцов.',wraplength=860).pack(padx=8,pady=8)

    def open(self):
        path=filedialog.askopenfilename(parent=self.window,filetypes=[('Картинки','*.png *.jpg *.jpeg *.bmp *.webp')])
        if not path: return
        try:
            source=pygame.image.load(path)
            if source.get_width()*source.get_height()>16_000_000:
                raise ValueError('Изображение слишком большое: максимум 16 мегапикселей.')
            self.source=source
            self._bg_key=None
            self.render()
        except (OSError,ValueError,pygame.error) as exc:
            messagebox.showerror('Импорт',str(exc),parent=self.window)

    def render(self):
        if self.source is None: return False
        try:
            key=(id(self.source),self.bg_color,round(self.tolerance.get()),self.edges_only.get(),self.remove_bg.get())
            if key!=self._bg_key:
                source=self.source
                if self.remove_bg.get():
                    # Bound Python floodfill cost for large photographs.
                    scale=min(1,1024/max(source.get_size()))
                    if scale<1:
                        source=pygame.transform.smoothscale(source,(max(1,round(source.get_width()*scale)),max(1,round(source.get_height()*scale))))
                    source=remove_background(source,self.bg_color,self.tolerance.get(),self.edges_only.get())
                self.cleaned=source
                self._bg_key=key
            self.result,self.text=convert(self.cleaned,self.columns.get(),PALETTES[self.palette.get()],
                                         self.colored.get(),self.invert.get(),self.contrast.get())
            self.photos=[]
            for canvas,image in zip(self.canvases,(self.cleaned,self.result)):
                w,h=max(100,canvas.winfo_width()),max(100,canvas.winfo_height())
                factor=min((w-12)/image.get_width(),(h-12)/image.get_height())
                scaled=pygame.transform.scale(image,(max(1,int(image.get_width()*factor)),max(1,int(image.get_height()*factor))))
                background=pygame.Surface(scaled.get_size())
                background.fill((42,42,48))
                for yy in range(0,background.get_height(),12):
                    for xx in range(0,background.get_width(),12):
                        if (xx//12+yy//12)%2:
                            pygame.draw.rect(background,(65,65,72),(xx,yy,12,12))
                background.blit(scaled,(0,0))
                sw,sh=background.get_size()
                photo=tk.PhotoImage(data=f'P6\n{sw} {sh}\n255\n'.encode()+pygame.image.tobytes(background,'RGB'),format='PPM')
                self.photos.append(photo)
                canvas.delete('all'); canvas.create_image(w//2,h//2,image=photo)
            self.status.set(f'{self.columns.get()} × {len(self.text.splitlines())} символов; PNG {self.result.get_width()}×{self.result.get_height()} px. Белый вариант поддерживает автоперекраску.')
            return True
        except (ValueError,KeyError,tk.TclError,pygame.error) as exc:
            self.status.set(str(exc)); return False

    def choose_background(self):
        color=colorchooser.askcolor(parent=self.window,title='Цвет удаляемого фона')[0]
        if color is not None:
            self.bg_color=tuple(map(int,color))
            self.remove_bg.set(True)
            self.render()

    def auto_background(self):
        self.bg_color=None
        self.remove_bg.set(True)
        self.render()

    def export_cleaned(self):
        if not self.render(): return
        path=filedialog.asksaveasfilename(parent=self.window,defaultextension='.png',filetypes=[('PNG','*.png')])
        if path:
            try: pygame.image.save(self.cleaned,path)
            except (OSError,pygame.error) as exc: messagebox.showerror('Экспорт',str(exc),parent=self.window)

    def assign(self):
        char=self.symbol.get()
        if len(char)!=1:
            self.status.set('Выберите ровно один игровой символ.'); return
        if not self.render(): return
        try:
            folder=self.editor.folder()
            os.makedirs(folder,exist_ok=True)
            name=f'ascii_u{ord(char):04x}.png'
            path=os.path.join(folder,name)
            if os.path.exists(path) and not messagebox.askyesno('Перезаписать?',name,parent=self.window): return
            pygame.image.save(self.result,path)
            self.editor.mapping[char]=name
            self.editor.native_symbols.add(char)
            self.editor.atlas.pop(char,None)
            self.editor.char.set(char)
            self.editor.refresh()
            self.status.set('Назначено. Нажмите «Сохранить» в основном редакторе, затем включите tileset в игре.')
        except (OSError,ValueError,pygame.error) as exc:
            messagebox.showerror('Сохранение',str(exc),parent=self.window)

    def export_png(self):
        if not self.render(): return
        path=filedialog.asksaveasfilename(parent=self.window,defaultextension='.png',filetypes=[('PNG','*.png')])
        if path:
            try: pygame.image.save(self.result,path)
            except (OSError,pygame.error) as exc: messagebox.showerror('Экспорт',str(exc),parent=self.window)

    def export_text(self):
        if not self.render(): return
        path=filedialog.asksaveasfilename(parent=self.window,defaultextension='.txt',filetypes=[('Текст','*.txt')])
        if path:
            try:
                with open(path,'w',encoding='utf-8') as f: f.write(self.text)
            except OSError as exc: messagebox.showerror('Экспорт',str(exc),parent=self.window)
