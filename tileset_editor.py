"""Standalone tileset mapping editor: python tileset_editor.py."""
import json
import os
import shutil
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser
import pygame
from engine.renderer import Renderer
from engine.tileset import TilesetManager
from engine.tile_catalog import entries as catalog_entries

PAD = 8                 # отступ картинки в полотне
MIN_ZOOM, MAX_ZOOM = 0.25, 4.0
ZOOM_STEP = 0.05        # шаг зума: округление даёт попадания в кэш
ATLAS_CACHE = 8         # сколько уровней зума держим готовыми
ATLAS_PIXEL_BUDGET = 12_000_000   # предохранитель от 100+ МБ PPM на кадр
GRID = (70, 150, 190)


class Editor:
    def __init__(self, root):
        self.root = root
        root.title("Tileset editor — ASCII / Custom")
        pygame.font.init()
        self.r = Renderer(pygame.Surface((64, 64)))
        self.ts = self.r.tileset
        self.color = (222, 190, 78)
        self.mod = tk.StringVar(value="default")
        self.char = tk.StringVar(value="@")
        self.size = tk.IntVar(value=32)
        self.tint = tk.BooleanVar(value=True)
        self.atlas_col = tk.IntVar(value=0)
        self.atlas_row = tk.IntVar(value=0)
        self.atlas_zoom = 1.0
        self.atlas_origin = (PAD, PAD)
        self.atlas_photo = None
        self.mapping = {}
        self.native_symbols = set()
        self.native = tk.BooleanVar(value=False)
        self.atlas = {}
        self.sheet = ""
        self.photos = []
        # состояние отрисовки atlas
        self._sheet_cache = {}
        self._baked = {}
        self._drawn_key = None
        self._img_item = None
        self._sel_item = None
        self._hint_item = None
        self._atlas_size = (0, 0)
        self._atlas_cell = 0
        self._eff_zoom = 1.0
        self._drag = None
        self._wheel_acc = 0.0
        self._wheel_job = None

        bar = ttk.Frame(root)
        bar.pack(fill="x", padx=12, pady=12)
        ttk.Label(bar, text="Мод").pack(side="left")
        ttk.Entry(bar, textvariable=self.mod, width=20).pack(side="left")
        ttk.Button(bar, text="Открыть…", command=self.load).pack(side="left", padx=(6, 0))
        ttk.Button(bar, text="Создать", command=self.create).pack(side="left", padx=(4, 0))
        ttk.Label(bar, text="Символ").pack(side="left", padx=(12, 0))
        ttk.Entry(bar, textvariable=self.char, width=4).pack(side="left")
        ttk.Combobox(bar, textvariable=self.size, values=(16, 24, 32, 48, 64),
                     width=5, state="readonly").pack(side="left")
        ttk.Checkbutton(bar, text="Автоцвет", variable=self.tint, command=self.preview).pack(side="left")
        ttk.Checkbutton(root,text="ASCII-мозаика: исходное разрешение выбранного символа",
                        variable=self.native,command=self.toggle_native).pack()
        ttk.Label(bar, text="Atlas X/Y").pack(side="left", padx=(12, 0))
        ttk.Spinbox(bar, from_=0, to=4095, textvariable=self.atlas_col, width=5).pack(side="left")
        ttk.Spinbox(bar, from_=0, to=4095, textvariable=self.atlas_row, width=5).pack(side="left")

        panels = ttk.Frame(root)
        panels.pack(fill="both", expand=True)
        self.canvases = []
        for title in ("Оригинал ASCII", "Кастомный tileset"):
            frame = ttk.LabelFrame(panels, text=title)
            frame.pack(side="left", fill="both", expand=True, padx=10)
            canvas = tk.Canvas(frame, width=320, height=320, bg="#101018")
            canvas.pack()
            self.canvases.append(canvas)

        atlas_frame = ttk.LabelFrame(
            root, text="Atlas: ЛКМ назначает клетку, СКМ+drag двигает, стрелки сдвигают")
        atlas_frame.pack(fill="both", expand=True, padx=10, pady=6)
        self.atlas_canvas = tk.Canvas(atlas_frame, width=720, height=300,
                                      bg="#080b12", cursor="crosshair")
        self.atlas_canvas.pack(fill="both", expand=True)
        self.atlas_canvas.bind("<Button-1>", self.atlas_click)
        self.atlas_canvas.bind("<MouseWheel>", self.atlas_wheel)
        self.atlas_canvas.bind("<Button-4>", lambda e: self.queue_zoom(0.1))
        self.atlas_canvas.bind("<Button-5>", lambda e: self.queue_zoom(-0.1))
        self.atlas_canvas.bind("<ButtonPress-2>", self.pan_start)
        self.atlas_canvas.bind("<B2-Motion>", self.pan_move)
        self.atlas_canvas.bind("<ButtonRelease-2>", self.pan_end)
        self.atlas_canvas.bind("<Motion>", lambda e: self.pan_end(e))
        self.atlas_canvas.bind("<Left>", lambda e: self.pan_key(e, (-PAD * 4, 0)))
        self.atlas_canvas.bind("<Right>", lambda e: self.pan_key(e, (PAD * 4, 0)))
        self.atlas_canvas.bind("<Up>", lambda e: self.pan_key(e, (0, -PAD * 4)))
        self.atlas_canvas.bind("<Down>", lambda e: self.pan_key(e, (0, PAD * 4)))
        self.atlas_canvas.bind("<Configure>", lambda e: self._place())
        self.atlas_canvas.focus_set()

        tools = ttk.Frame(root)
        tools.pack(pady=12)
        ttk.Button(root,text="Картинка → ASCII-спрайт…",command=self.import_ascii).pack(pady=4)
        for text, cmd in (("Импорт PNG", self.import_image),
                          ("Импорт atlas", self.import_sheet),
                          ("Назначить atlas-клетку", self.assign_atlas),
                          ("Удалить привязку", self.remove),
                          ("Сбросить вид", self.reset_view),
                          ("Цвет предпросмотра", self.pick_color),
                          ("Сохранить", self.save),
                          ("Включить в игре", self.activate)):
            ttk.Button(tools, text=text, command=cmd).pack(side="left")

        catalog_frame = ttk.LabelFrame(root, text="Справочник символов игры")
        catalog_frame.pack(fill="x", padx=12, pady=(0, 6))
        self.catalog = tk.Listbox(catalog_frame, height=7)
        self.catalog.pack(fill="x")
        for char, name in catalog_entries():
            self.catalog.insert("end", f"{char} — {name}")
        self.catalog.bind("<<ListboxSelect>>", self.select_catalog)
        self.list = tk.Listbox(root, height=6)
        self.list.pack(fill="x", padx=12)
        self.list.bind("<<ListboxSelect>>", self.select)
        self.status = tk.StringVar()
        ttk.Label(root, textvariable=self.status).pack()
        self.char.trace_add("write", lambda *_: self.preview())
        self.size.trace_add("write", lambda *_: self.preview())
        self.atlas_col.trace_add("write", lambda *_: self._move_selection())
        self.atlas_row.trace_add("write", lambda *_: self._move_selection())
        self.bootstrap()

    # ------------------------------------------------------------------
    # Работа с набором
    # ------------------------------------------------------------------
    def folder(self):
        name = self.mod.get().strip()
        if not name or name in (".", "..") or any(c in name for c in '/\\:'):
            raise ValueError("Введите имя папки мода")
        return os.path.join(self.ts.root, name)

    def import_ascii(self):
        from ascii_importer import AsciiImporter
        AsciiImporter(self)

    def toggle_native(self):
        char=self.char.get()
        if self.native.get(): self.native_symbols.add(char)
        else: self.native_symbols.discard(char)
        self.preview()

    def bootstrap(self):
        """Тихая загрузка при старте: без диалогов, при ошибке — пустое состояние."""
        try:
            folder = self.folder()
        except ValueError:
            self.refresh()
            return
        if not os.path.isdir(folder):
            self.refresh()
            return
        self._read_manifest(folder, quiet=True)
        self.invalidate()
        self.refresh()

    def _read_manifest(self, folder, quiet=False, keep_sheet=False):
        """Читает manifest.json в поля редактора. False — читать нечего.

        keep_sheet=True — текстуру не трогать: её только что выбрал пользователь.
        """
        path = os.path.join(folder, "manifest.json")
        if not os.path.exists(path):
            return False
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError, TypeError) as exc:
            if not quiet:
                messagebox.showerror("Ошибка", f"Не удалось прочитать manifest.json:\n{exc}")
            return False
        self.mapping = dict(data.get("tiles", {}))
        self.native_symbols = set(data.get("native_symbols", []))
        self.atlas = dict(data.get("atlas", {}))
        if not keep_sheet:
            sheet = data.get("sheet")
            # текстуру из манифеста берём только если файл реально на месте
            if isinstance(sheet, str) and sheet and os.path.exists(os.path.join(folder, sheet)):
                self.sheet = sheet
        try:
            size = data.get("tile_size", 32)
            if int(size) in (16, 24, 32, 48, 64):
                self.size.set(size)
        except (TypeError, ValueError):
            pass
        return True

    def _import_texture(self, filename):
        """Копирует картинку в папку мода как sheet.<ext> и цепляет её."""
        folder = self.folder()
        os.makedirs(folder, exist_ok=True)
        ext = os.path.splitext(filename)[1].lower() or ".png"
        name = "sheet" + ext
        dest = os.path.join(folder, name)
        if os.path.abspath(filename) != os.path.abspath(dest):
            shutil.copyfile(filename, dest)
        # старую текстуру НЕ удаляем здесь: манифест ещё указывает на неё.
        # Подчистка произойдёт в save(), уже после записи нового имени.
        self.sheet = name
        self._sheet_cache.clear()
        self.invalidate()

    def _purge_stale_sheet(self, folder):
        """Убирает прошлые sheet.* — вызывается только из save(), после записи манифеста."""
        try:
            entries = os.listdir(folder)
        except OSError:
            return
        for name in entries:
            if name.lower().startswith("sheet.") and name != self.sheet:
                try:
                    os.remove(os.path.join(folder, name))
                except OSError:
                    pass

    def load(self):
        """Открыть набор: проводник с выбором текстуры, затем привязки из манифеста."""
        try:
            folder = self.folder()
        except ValueError as exc:
            messagebox.showerror("Ошибка", str(exc))
            return
        start = folder if os.path.isdir(folder) else self.ts.root
        if not os.path.isdir(start):
            start = os.getcwd()
        filename = filedialog.askopenfilename(
            title="Укажите текстуру набора (atlas)",
            filetypes=[("Текстуры", "*.png *.bmp *.jpg *.jpeg"),
                       ("PNG", "*.png"), ("Все файлы", "*.*")],
            initialdir=start)
        if not filename:
            self.status.set("Открытие отменено, набор не изменён")
            return
        if (self.mapping or self.atlas) and not messagebox.askyesno(
                "Открыть другой набор",
                "Несохранённые привязки текущего набора будут потеряны.\nПродолжить?"):
            return
        try:
            self._import_texture(filename)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Ошибка", f"Не удалось импортировать текстуру:\n{exc}")
            return
        self._read_manifest(folder, quiet=True, keep_sheet=True)
        self.refresh()
        self.status.set(f"Набор «{os.path.basename(folder)}», текстура {self.sheet}")

    def create(self):
        """Создать новый пустой набор в папке мода."""
        try:
            folder = self.folder()
        except ValueError as exc:
            messagebox.showerror("Ошибка", str(exc))
            return
        path = os.path.join(folder, "manifest.json")
        if os.path.exists(path) and not messagebox.askyesno(
                "Набор уже существует",
                f"«{os.path.basename(folder)}» уже содержит manifest.json.\n"
                "Создать заново? Несохранённые изменения будут потеряны."):
            return
        self.mapping = {}
        self.atlas = {}
        self.sheet = ""
        try:
            os.makedirs(folder, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"tile_size": 32, "tiles": {}}, f, ensure_ascii=False, indent=2)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Ошибка", str(exc))
            return
        self.invalidate()
        self.refresh()
        self.status.set(f"Создан пустой набор «{os.path.basename(folder)}»")

    def invalidate(self):
        """Сбросить кэш отрисовки: сменился sheet, размер клетки, зум или файл на диске."""
        self._drawn_key = None
        self._atlas_size = (0, 0)
        self._atlas_cell = 0
        self.atlas_origin = (PAD, PAD)

    def refresh(self):
        self.list.delete(0, "end")
        for char in sorted(self.mapping):
            self.list.insert("end", f"{char}  →  {self.mapping[char]}")
        self.preview()

    def select(self, event):
        if self.list.curselection():
            self.char.set(sorted(self.mapping)[self.list.curselection()[0]])

    def select_catalog(self, event):
        selected = self.catalog.curselection()
        if selected:
            self.char.set(catalog_entries()[selected[0]][0])

    def preview(self):
        char = self.char.get()
        if len(char) != 1:
            return
        try:
            self.ts.enabled = True
            self.native.set(char in self.native_symbols)
            self.ts.native_symbols=set(self.native_symbols)
            self.ts.tile_size = self.size.get()
            self.ts.auto_color = self.tint.get()
            self.ts.tiles = {c: os.path.join(self.folder(), f) for c, f in self.mapping.items()}
            self.ts.sheet = os.path.join(self.folder(), self.sheet) if self.sheet else None
            self.ts.atlas = self.atlas
            self.ts.cache.clear()
            self.ts.originals.clear()
            sprite = self.ts.image(char, self.color)
            self.photos = []
            fallback = self.r.glyph(char, self.color)
            for canvas, image in zip(self.canvases, (fallback, sprite if sprite is not None else fallback)):
                factor=min(300/image.get_width(),300/image.get_height())
                image = pygame.transform.scale(image, (max(1,round(image.get_width()*factor)),max(1,round(image.get_height()*factor))))
                bg = pygame.Surface((300, 300))
                bg.fill((16, 16, 24))
                bg.blit(image, (0, 0))
                data = b"P6\n300 300\n255\n" + pygame.image.tobytes(bg, "RGB")
                photo = tk.PhotoImage(data=data, format="PPM")
                self.photos.append(photo)
                canvas.delete("all")
                canvas.create_image(160, 160, image=photo)
            self.status.set("Спрайт загружен" if sprite is not None
                            else "ASCII fallback: спрайт отсутствует или повреждён")
            self.preview_atlas()
        except (ValueError, tk.TclError, OSError, pygame.error) as exc:
            self.status.set(str(exc))

    # ------------------------------------------------------------------
    # Импорт
    # ------------------------------------------------------------------
    def import_image(self):
        if len(self.char.get()) != 1:
            return
        filename = filedialog.askopenfilename(filetypes=[("Изображения", "*.png *.bmp *.jpg")])
        if filename:
            try:
                folder = self.folder()
                os.makedirs(folder, exist_ok=True)
                name = f"u{ord(self.char.get()):04x}" + os.path.splitext(filename)[1]
                dest = os.path.join(folder, name)
                if os.path.abspath(filename) != os.path.abspath(dest):
                    shutil.copyfile(filename, dest)
                self.mapping[self.char.get()] = name
                self.invalidate()
                self.refresh()
            except (OSError, ValueError) as exc:
                messagebox.showerror("Ошибка", str(exc))

    def remove(self):
        self.mapping.pop(self.char.get(), None)
        self.atlas.pop(self.char.get(), None)
        self.refresh()

    def import_sheet(self):
        """Импорт текстуры сразу с сохранением манифеста — без подтверждений."""
        filename = filedialog.askopenfilename(
            title="Импорт текстуры (atlas)",
            filetypes=[("Текстуры", "*.png *.bmp *.jpg *.jpeg"), ("Все файлы", "*.*")])
        if not filename:
            return
        try:
            self._import_texture(filename)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Ошибка", str(exc))
            return
        self.save()
        self.refresh()
        self.status.set("Текстура импортирована. Клик по сетке задаёт координаты.")

    # ------------------------------------------------------------------
    # Отрисовка atlas: кэш + панорамирование
    # ------------------------------------------------------------------
    def _sheet_surface(self, path):
        """Декодированный PNG в кэше — на диск за кадр не ходим."""
        hit = self._sheet_cache.get(path)
        if hit is not None:
            return hit
        # без convert_alpha(): дальше берётся только RGB, а конвертация
        # требует созданного окна display и без него роняет редактор
        surface = pygame.image.load(path)
        self._sheet_cache[path] = surface
        return surface

    def _atlas_key(self, path):
        try:
            stamp = os.path.getmtime(path)
        except OSError:
            return None
        return (path, stamp, self.size.get(), round(self.atlas_zoom, 3))

    def _bake(self, path):
        """Готовит PhotoImage с картинкой и сеткой. Результат кэшируется по уровням зума."""
        key = self._atlas_key(path)
        if key is None:
            return None
        hit = self._baked.get(key)
        if hit is not None:
            return hit
        try:
            src = self._sheet_surface(path)
        except (pygame.error, OSError):
            return None
        zoom = self.atlas_zoom
        w = max(1, int(src.get_width() * zoom))
        h = max(1, int(src.get_height() * zoom))
        # предохранитель: не даём выпечь сотню мегабайт на кадр
        while w * h > ATLAS_PIXEL_BUDGET and zoom > MIN_ZOOM:
            zoom *= 0.9
            w = max(1, int(src.get_width() * zoom))
            h = max(1, int(src.get_height() * zoom))
        cell = max(1, int(self.size.get() * zoom))
        try:
            image = pygame.transform.smoothscale(src, (w, h)) if (w, h) != src.get_size() else src.copy()
            surface = pygame.Surface((w, h))
            surface.blit(image, (0, 0))
            for x in range(0, w + 1, cell):
                pygame.draw.line(surface, GRID, (x, 0), (x, h), 1)
            for y in range(0, h + 1, cell):
                pygame.draw.line(surface, GRID, (0, y), (w, y), 1)
            blob = b"P6\n" + str(w).encode() + b" " + str(h).encode() + b"\n255\n" + \
                pygame.image.tobytes(surface, "RGB")
            photo = tk.PhotoImage(data=blob, format="PPM")
        except (OSError, ValueError, pygame.error, tk.TclError):
            return None
        result = (photo, w, h, cell, zoom)
        if len(self._baked) >= ATLAS_CACHE:
            self._baked.pop(next(iter(self._baked)))
        self._baked[key] = result
        return result

    def _clear_atlas(self, text):
        self.atlas_canvas.delete("all")
        self.atlas_canvas.create_text(12, 12, anchor="nw", fill="#aab4c8", text=text)
        self._img_item = self._sel_item = self._hint_item = None
        self._drawn_key = None
        self._atlas_size = (0, 0)
        self._atlas_cell = 0

    def preview_atlas(self):
        """Перепекает только когда сменился ключ (файл/размер/зум), иначе merely двигает."""
        canvas = self.atlas_canvas
        if not self.sheet:
            self._clear_atlas("Импортируйте atlas PNG, чтобы увидеть сетку")
            return
        try:
            path = os.path.join(self.folder(), self.sheet)
        except ValueError as exc:
            self._clear_atlas(str(exc))
            return
        key = self._atlas_key(path)
        if key != self._drawn_key:
            canvas.delete("all")
            self._img_item = self._sel_item = self._hint_item = None
            baked = self._bake(path)
            if baked is None:
                self._drawn_key = None
                self._atlas_size = (0, 0)
                self._atlas_cell = 0
                canvas.create_text(12, 12, anchor="nw", fill="#ff7777",
                                   text="Не удалось прочитать atlas")
                return
            photo, w, h, cell, zoom = baked
            self.atlas_photo = photo
            self._atlas_size = (w, h)
            self._atlas_cell = cell
            self._eff_zoom = zoom
            self._img_item = canvas.create_image(PAD, PAD, anchor="nw", image=photo)
            self._sel_item = canvas.create_rectangle(0, 0, 0, 0, outline="#ffd237", width=2)
            self._hint_item = canvas.create_text(12, PAD + h + 8, anchor="nw",
                                                fill="#dce5f4", text="")
            self._drawn_key = key
        self._update_hint()
        self._place()

    def _update_hint(self):
        if self._hint_item is None:
            return
        extra = "" if abs(self._eff_zoom - self.atlas_zoom) < 0.01 \
            else f"  (фактический {self._eff_zoom:.2f}x, уменьшено ради лимита)"
        self.atlas_canvas.itemconfig(self._hint_item, text=(
            f"X={self.atlas_col.get()}  Y={self.atlas_row.get()}"
            f"  клетка={self.size.get()}px  масштаб={self.atlas_zoom:.2f}x{extra}"
            "   — ЛКМ назначить, СКМ+drag двигать, колесо зум"))

    def _clamp(self, ox, oy):
        """Не даём утащить картинку за экран. До раскладки окна размеры равны 1 —
        тогда ограничивать нечем, поэтому пропускаем."""
        w, h = self._atlas_size
        cw = self.atlas_canvas.winfo_width()
        ch = self.atlas_canvas.winfo_height()
        if cw < 2 * PAD or ch < 2 * PAD:
            return (ox, oy)
        # если картинка уже помещается, диапазон свободный; если нет - прижимаем к краю
        x_lo, x_hi = sorted((PAD, cw - PAD - w))
        y_lo, y_hi = sorted((PAD, ch - PAD - h))
        return (max(min(ox, x_hi), x_lo), max(min(oy, y_hi), y_lo))

    def _place(self):
        """Сдвигает картинку и рамку выделения — без перепечки."""
        if self._img_item is None:
            return
        ox, oy = self._clamp(*self.atlas_origin)
        self.atlas_origin = (ox, oy)
        self.atlas_canvas.coords(self._img_item, ox, oy)
        if self._hint_item is not None:
            self.atlas_canvas.coords(self._hint_item, 12, oy + self._atlas_size[1] + 8)
        self._move_selection()

    def _move_selection(self):
        if self._sel_item is None:
            return
        cell = self._atlas_cell or max(1, self.size.get())
        ox, oy = self.atlas_origin
        x = ox + self.atlas_col.get() * cell
        y = oy + self.atlas_row.get() * cell
        self.atlas_canvas.coords(self._sel_item, x, y, x + cell, y + cell)
        self._update_hint()

    # --- зум ---------------------------------------------------------------
    def set_zoom(self, value):
        self.atlas_zoom = max(MIN_ZOOM, min(MAX_ZOOM, round(value / ZOOM_STEP) * ZOOM_STEP))
        self.preview_atlas()

    def queue_zoom(self, amount):
        """Колесо шлёт пачку событий — копим и применяем один раз за кадр."""
        self._wheel_acc += amount
        if self._wheel_job is None:
            self._wheel_job = self.root.after_idle(self._flush_zoom)

    def _flush_zoom(self):
        self._wheel_job = None
        step, self._wheel_acc = self._wheel_acc, 0.0
        if step:
            self.set_zoom(self.atlas_zoom + step)

    def change_zoom(self, amount):
        self.set_zoom(self.atlas_zoom + amount)

    def atlas_wheel(self, event):
        self.queue_zoom(0.1 if event.delta > 0 else -0.1)

    def reset_view(self):
        self.atlas_zoom = 1.0
        self.atlas_origin = (PAD, PAD)
        self.preview_atlas()

    # --- панорамирование ---------------------------------------------------
    def pan_start(self, event):
        self._drag = (event.x, event.y)
        self.atlas_canvas.configure(cursor="fleur")

    def pan_move(self, event):
        if self._drag is None:
            return
        dx, dy = event.x - self._drag[0], event.y - self._drag[1]
        if dx or dy:
            self._drag = (event.x, event.y)
            self.pan(dx, dy)

    def pan_end(self, event):
        self._drag = None
        self.atlas_canvas.configure(cursor="crosshair")

    def pan_key(self, event, delta):
        self.pan(*delta)
        return "break"

    def pan(self, dx, dy):
        if self._img_item is None:
            return
        ox, oy = self.atlas_origin
        self.atlas_origin = (ox + dx, oy + dy)
        self._place()

    # --- назначение клетки -------------------------------------------------
    def atlas_click(self, event):
        if not self.sheet:
            return
        w, h = self._atlas_size
        if not w or not h:
            return
        cell = self._atlas_cell or max(1, self.size.get())
        ox, oy = self.atlas_origin
        px, py = event.x - ox, event.y - oy
        if not (0 <= px < w and 0 <= py < h):
            self.status.set("Клик вне изображения atlas")
            return
        col, row = px // cell, py // cell
        self.atlas_col.set(col)
        self.atlas_row.set(row)
        self.assign_atlas()
        self.status.set(f"Выбрана клетка atlas X={col}, Y={row} для символа '{self.char.get()}'")

    def assign_atlas(self):
        if len(self.char.get()) != 1:
            return
        w, h = self._atlas_size
        if self.sheet and w and h:
            cell = self._atlas_cell or max(1, self.size.get())
            cols, rows = -(-w // cell), -(-h // cell)
            col, row = self.atlas_col.get(), self.atlas_row.get()
            if not (0 <= col < cols and 0 <= row < rows):
                self.status.set(f"Координаты ({col},{row}) вне атласа {cols}x{rows} клеток")
                return
        self.atlas[self.char.get()] = [self.atlas_col.get(), self.atlas_row.get()]
        self.mapping.pop(self.char.get(), None)
        self.refresh()

    # ------------------------------------------------------------------
    def pick_color(self):
        color = colorchooser.askcolor()[0]
        if color:
            self.color = tuple(map(int, color))
            self.preview()

    def save(self):
        try:
            folder = self.folder()
            os.makedirs(folder, exist_ok=True)
            with open(os.path.join(folder, "manifest.json"), "w", encoding="utf-8") as f:
                data = {"tile_size": self.size.get(), "tiles": self.mapping}
                data['native_symbols']=sorted(self.native_symbols)
                if self.sheet:
                    data["sheet"] = self.sheet
                if self.atlas:
                    data["atlas"] = self.atlas
                json.dump(data, f, ensure_ascii=False, indent=2)
            self._purge_stale_sheet(folder)
            self.status.set("Набор сохранён")
            return True
        except (OSError, ValueError) as exc:
            messagebox.showerror("Ошибка", str(exc))
            return False

    def activate(self):
        if not self.save():
            return
        from game.lang import SETTINGS_PATH
        try:
            data = json.load(open(SETTINGS_PATH, encoding="utf-8")) if os.path.exists(SETTINGS_PATH) else {}
            data["tileset"] = {"enabled": True, "auto_color": self.tint.get(),
                               "tile_size": self.size.get(), "mod": self.mod.get().strip()}
            os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
            with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.status.set("Включено. Перезапустите игру.")
        except (OSError, ValueError) as exc:
            messagebox.showerror("Ошибка", str(exc))


if __name__ == "__main__":
    root = tk.Tk()
    Editor(root)
    root.mainloop()
