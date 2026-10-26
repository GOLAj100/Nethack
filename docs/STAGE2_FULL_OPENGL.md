# Этап 2: Полный OpenGL-рендер (без tostring)

## Статус: реализованы GPU HUD/Sidebar, sprite atlas и композитор

Проверено `python -m unittest tests.gl_pipeline_test -v`: 9 тестов на реальном
OpenGL-контексте. Основной игровой путь не загружает полный CPU canvas каждый
кадр. Software backend и старые экраны с прямыми Surface-blit сохраняют CPU-путь.

## Цель
Убрать CPU-копирование canvas в GPU каждый кадр через `pygame.image.tostring()`. Это главное узкое место производительности.

## Архитектура

### До (Этап 1)
```
pygame.Surface (canvas) → tostring() → GL texture → экран
     ↑ CPU рисует текст/UI
```

### После (Этап 2)
```
gpu_rays FBO ───────┐
                   ↓ (текстурированный quad на позиции карты)
UI / glyph atlas / sprite atlas → GLRenderer FBO → экран
```

- **3D-сцена** рендерится через `gpu_rays` (уже готов) в FBO
- **UI** рисуется напрямую в OpenGL: текст через bitmap-font atlas, панели — rect'ы через shader
- **Canvas** остаётся для software backend и legacy Surface API; тайлы игрового GL-пути берутся из атласа
- **Композитинг** — 3D-сцена + UI объединяются в одном framebuffer без CPU-копирования

## Реализация

### ✅ Выполнено

#### 1. Font Atlas (`engine/gl_font_atlas.py`)
- ASCII, кириллица, рамки и основные символы интерфейса в текстуре с вычисляемым размером
- Текст рисуется через quads с UV-координатами
- Кэш глифов: один раз генерируется через pygame.font, загружается в GL
- **Использование:** `atlas.uv('A', bold=False)` → UV и размеры глифа

#### 2. UI Batch (`engine/gl_ui_batch.py`)
- Простые rect'ы и lines через один shader
- Один буфер вершин; соседние команды с одинаковой текстурой объединяются в draw call
- Порядок команд сохраняется: фон больше не перекрывает ранее сгруппированный текст
- RGBA-текстуры, alpha blending, скруглённые панели и рамки
- Ортографическая проекция в пиксельных координатах (как pygame)
- **Использование:** `batch.begin()` → `rect()` / `text()` / `image()` → `batch.end()`

#### 3. GLRenderer (`engine/gl_renderer.py`)
- Drop-in замена для `Renderer`
- Методы `text()`, `fill_rect()`, `clear()`, `box()`, `bar()` идентичны по API, но рисуют через OpenGL
- **FBO для off-screen рендера:** весь UI рисуется в текстуру, которая потом компонуется с 3D-сценой
- **Fallback:** если GL недоступен, все вызовы падают на CPU-рендерер (совместимость с software backend)

#### 4. Интеграция в Display (`engine/display.py`)
- `gl_renderer` создаётся при `backend="opengl"`
- `_present_opengl()` теперь:
  1. Если `gl_renderer.fbo_rendered == True`: использует GL-текстуру
  2. Иначе: fallback на `tostring(canvas)` для legacy CPU-кадров
  3. Уже скомпонованная сцена не рисуется повторно поверх интерфейса

#### 5. Тесты (`tests/stage2_opengl_test.py`)
- Проверка инициализации GLRenderer
- Сравнение FPS (OpenGL vs Software)
- Скриншот UI для визуальной проверки

### Завершённая интеграция

#### Интеграция в Game
- [x] `Game.draw()` вызывает `begin()` / `end()` для GL-кадров
- [x] HUD/Sidebar: пиксельный текст с размером, жирностью и выравниванием; панели и status pills напрямую через GL
- [x] Журнал сообщений рисуется через GL поверх сцены
- [x] После gpu_rays восстанавливаются FBO и viewport перед рисованием UI

#### Убрать покадровый canvas upload
- [x] `tile`, `sprite`, `fill_tile`, `draw_visual` используют `SpriteAtlas`
- [x] ASCII-карта использует атлас глифов
- [x] Кэшированная GPU-сцена не копируется в CPU Surface
- [x] Композитор вставляет сцену перед прицелом, чатом, sidebar и модальными окнами

### Детали реализации

1. **ModernHUD / ModernSidebar**
   - `draw_rect()` / `draw_rect_outline()` работают в пикселях
   - `text_pixels()` использует атласы Consolas по размерам; растеризация только при создании атласа

2. **Делегирование**
   - Базовый `Renderer` делегирует рисование только внутри активного GL-кадра
   - Перехват `pygame.draw` не затрагивает временные поверхности ресурсов

3. **Sprite cache**
   - Ленивая загрузка используемых тайлов в страницы атласа 1024×1024
   - Ключ включает ревизию tileset, цвет, размер и параметры модов
   - `fill_tile()` обрезает UV с сохранением пропорций
   - При превышении 8 страниц кэш очищается на следующей границе кадра

4. **Композитинг 3D + UI**
   - `gpu_rays` рисует 3D-сцену в свой FBO
   - `GLRenderer` рисует UI в свой FBO
   - `GLCompositor` вставляет текстуру сцены в очередь UI; GLRenderer FBO служит финальным framebuffer

5. **Презентация**
   - `Display._present_opengl()` выводит готовую FBO-текстуру без canvas upload
   - Первичная загрузка ресурсов в атлас всё ещё использует CPU → GPU передачу

## Результаты

### Исторические измерения базовой инфраструктуры (до этих изменений)
- **Software:** ~107 FPS
- **OpenGL:** ~114 FPS (+6% speedup)
- **Примечание:** полное ускорение будет видно после переноса всех тайлов/спрайтов на GPU

Новый FPS-бенчмарк не выполнялся; гарантии FPS отсутствуют. Проверки запрещают
`pygame.image.tostring()` на прогретых кадрах HUD и игрового first-person пути.

## Известные ограничения

1. `visual()` по контракту возвращает Surface для CPU-потребителей; GPU-потребители используют `draw_visual()`.
2. Legacy-экраны с произвольными `surface.blit()` не становятся GPU-экранами автоматически.
3. Первая загрузка новых шрифтов/спрайтов требует растеризации и upload. Это не покадровая загрузка canvas.
4. Используется совместимый OpenGL-контекст (GLSL 110 / GL_QUADS), как и у существующего gpu_rays.

## API

### GLRenderer (drop-in замена Renderer)

```python
from engine.gl_renderer import GLRenderer

# Инициализация (после Display.configure("opengl"))
gl = GLRenderer(renderer, display)

# Цикл рисования
gl.begin()  # Начать рендер в FBO
gl.clear((10, 10, 20))  # Очистить экран
gl.text(10, 10, "Hello", (255, 255, 255))  # Нарисовать текст
gl.fill_rect(5, 5, 20, 3, (50, 50, 80))  # Нарисовать прямоугольник
gl.box(0, 0, 80, 30, (100, 120, 150), "Title")  # Рамка с заголовком
gl.bar(10, 15, 10, 0.75, (200, 50, 50))  # Полоска здоровья
gl.end()  # Завершить рендер (FBO готов)

# Display._present_opengl() выведет FBO на экран
```

### Font Atlas

```python
from engine.gl_font_atlas import GlyphAtlas

atlas = GlyphAtlas(GL, "consolas")
uv = atlas.uv('A')  # UV и размеры для текстурированного quad
```

### UI Batch

```python
from engine.gl_ui_batch import UIBatch

batch = UIBatch(GL, atlas)
batch.init()
batch.begin()
batch.rect(0, 0, 100, 50, (50, 50, 80))
batch.text(10, 10, "A", (255, 255, 255))  # Один глиф
batch.end()
```

## Тестирование

```bash
# Запустить тест Этапа 2
python -m unittest tests.gl_pipeline_test -v

# Нужен настоящий оконный OpenGL-контекст, не SDL dummy driver.
```

## Файлы

### Новые
- `engine/gl_renderer.py` — OpenGL-рендерер (drop-in замена)
- `engine/gl_font_atlas.py` — атлас глифов
- `engine/gl_ui_batch.py` — батчинг UI-элементов
- `engine/gl_sprite_atlas.py` — страничный кэш спрайтов
- `engine/gl_compositor.py` — включение scene FBO в очередь композиции
- `tests/gl_pipeline_test.py` — проверка пикселей, atlas cache, композиции и Game.draw
- `tests/stage2_opengl_test.py` — тест производительности
- `docs/STAGE2_FULL_OPENGL.md` — эта документация

### Изменённые
- `engine/display.py` — интеграция `gl_renderer`, FBO-композитинг
- `game/app.py` — GL HUD, журнал и композиция сцены

## Дальнейшая работа

Профилирование batched UI и отдельная миграция остальных legacy Surface-экранов.
Sprite Cache и Compositor входят в завершённые пункты этого этапа.
