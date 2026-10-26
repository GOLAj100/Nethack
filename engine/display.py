"""Logical canvas, uniform presentation and inverse mouse mapping."""
import pygame

RESOLUTIONS = ((680, 240), (800, 600), (1024, 768), (1280, 720),
               (1366, 768), (1600, 900), (1920, 1080), (2560, 1440))
# First-person projection uses this horizontal FOV.  A wider canvas must not
# stretch the same rays across more pixels.
RAY_PLANE = 0.66


def fit_rect(content, frame):
    """Largest uniform rectangle of ``content`` aspect inside ``frame``."""
    cw, ch = content
    fw, fh = frame
    if cw <= 0 or ch <= 0 or fw <= 0 or fh <= 0:
        return pygame.Rect(0, 0, max(1, fw), max(1, fh))
    if fw * ch < fh * cw:
        width, height = fw, max(1, round(fw * ch / cw))
    else:
        height, width = fh, max(1, round(fh * cw / ch))
    return pygame.Rect((fw - width) // 2, (fh - height) // 2, width, height)


class Display:
    # Internal canvas is capped at this resolution.  Larger windows upscale
    # the canvas through the presentation path (GPU does this for free,
    # software mode does it once per frame which is still cheaper than
    # drawing the whole UI at native 4K).
    CANVAS_MAX = (1920, 1080)

    def __init__(self, renderer):
        self.r = renderer
        # Logical size follows the cell grid.  Presentation letterboxes with a
        # uniform scale so a 16:9 canvas is never stretched onto a taller window.
        self.canvas = renderer.surface
        self.size = (1280, 720)
        self.fullscreen = False
        self.smooth = True
        self.rect = pygame.Rect(0, 0, *self.size)
        from . import config as C
        self.backend = "opengl" if C.USE_OPENGL else "software"
        self.requested_backend = self.backend
        self.adapter = "auto"
        self.gl = None
        self.gl_texture = None
        self._gl_texture_size = None
        self.gl_draw_wrapper = None  # Wrapper for pygame.draw interception
        # Canvas version.  Renderer bumps this on every draw call; present()
        # skips the GPU upload if the canvas has not changed since last time.
        self._canvas_version = 0
        self._presented_version = -1
        self.gpu_name = "Software"
        self.error = ""
        self.vulkan = None
        self.vulkan_devices = []
        self.rays = None
        self.board = None
        self.board_error = None
        self.ray_error = None
        self.scene = None
        self.scene_roll = 0
        self.generation = 0
        self.gl_renderer = None  # Initialized after configure() sets backend

    def close(self):
        self.r.gl_renderer = None
        # Restore original pygame.draw if wrapper was installed
        if self.gl_draw_wrapper is not None:
            from .gl_draw_wrapper import uninstall_gl_draw_wrapper
            uninstall_gl_draw_wrapper()
            self.gl_draw_wrapper = None
        
        if self.vulkan is not None:
            self.vulkan.close()
            self.vulkan = None
        # gl resources belong to the GL context owned by the pygame window.
        # Deleting textures after the context died (backend switch) crashes,
        # so simply drop references — the context teardown frees GPU memory.
        for name in ('rays','board','gl_renderer'):
            resource=getattr(self,name,None)
            if resource is not None:
                try:
                    resource.close()
                except Exception:
                    pass
                setattr(self,name,None)
        self.gl_texture=None
        self._gl_texture_size=None
        self.gl=None
        self.scene=None

    @staticmethod
    def backends():
        return ("software", "opengl", "vulkan")

    @staticmethod
    def adapters():
        # Adapter selection is performed by Windows for the Python executable.
        return ("auto",)

    def configure(self, size, fullscreen=False, backend=None, adapter=None):
        self.close()
        self.generation += 1
        if backend:
            self.requested_backend = backend
            self.backend = backend
        if adapter:
            self.adapter = adapter
        flags = pygame.FULLSCREEN if fullscreen else pygame.RESIZABLE
        self.error = ""
        if self.backend == "vulkan":
            from .vulkan_backend import VulkanBackend
            self.vulkan = VulkanBackend(self.adapter)
            self.vulkan_devices = self.vulkan.enumerate_devices()
            if not self.vulkan.initialize():
                self.error = self.vulkan.error
                self.backend = "opengl"
            else:
                self.error = "Vulkan device ready; using OpenGL presentation until swapchain backend is enabled"
                self.backend = "opengl"
        if self.backend == "opengl":
            try:
                from OpenGL import GL
                self.gl = GL
                flags |= pygame.OPENGL | pygame.DOUBLEBUF
            except ImportError:
                self.error = "Install PyOpenGL to enable GPU presentation"
                self.backend = "software"
                self.gl = None
        try:
            screen = pygame.display.set_mode(size, flags)
        except pygame.error as exc:
            # Keep the requested size: falling back to a fixed resolution loses
            # the user's window geometry every time a driver rejects GL flags.
            self.error = str(exc)
            self.backend = "software"
            self.gl = None
            fallback_flags = pygame.FULLSCREEN if fullscreen else pygame.RESIZABLE
            try:
                screen = pygame.display.set_mode(size, fallback_flags)
            except pygame.error:
                screen = pygame.display.set_mode((1280, 720), pygame.RESIZABLE)
                fullscreen = False
        self.size = screen.get_size()
        self.fullscreen = fullscreen
        self.sync_canvas()
        self.gl_texture = None
        self._gl_texture_size = None
        # Stale scene from a previous backend would be drawn on top of the
        # new canvas with an unrelated viewport.  Drop it; the next draw
        # call rebuilds the scene against the new backend.
        self.scene = None
        if self.backend == "opengl":
            try:
                self.gpu_name = self.gl.glGetString(self.gl.GL_RENDERER).decode(errors="replace")
            except Exception as exc:
                self.error = f"GL query failed: {exc}"
                self.backend = "software"
                self.gl = None
                self.gpu_name = "Software"
        else:
            self.gpu_name = "Software"
        self.rays = None
        self.board = None
        self.board_error = None
        self.ray_error = None
        self.gl_renderer = None
        self.gl_draw_wrapper = None  # Wrapper for pygame.draw interception
        if self.backend == "opengl" and self.gl is not None:
            # Created after set_mode(): the GL context must exist before any
            # shader/VAO is compiled.  Failure keeps the CPU canvas path.
            try:
                from .gl_renderer import GLRenderer
                from .gl_draw_wrapper import install_gl_draw_wrapper
                renderer = GLRenderer(self.r, self)
                if renderer.gl_enabled:
                    self.gl_renderer = renderer
                    self.gl_draw_wrapper = install_gl_draw_wrapper(renderer)
                else:
                    self.gl_renderer = None
            except Exception as exc:  # noqa: BLE001
                self.error = f"GL UI unavailable: {exc}"
                self.gl_renderer = None
        self.layout()

    @classmethod
    def canvas_size_for(cls, size):
        """Логический размер канвы для окна: не больше CANVAS_MAX, те же пропорции."""
        sw = max(1, int(size[0]))
        sh = max(1, int(size[1]))
        mw, mh = cls.CANVAS_MAX
        scale = min(1.0, mw / sw, mh / sh)
        return (max(1, int(sw * scale)), max(1, int(sh * scale)))

    def sync_canvas(self, size=None):
        """Match the logical canvas to the window, keeping the cell grid.

        The internal canvas is capped at CANVAS_MAX.  On a 4K window the
        renderer still draws at 1080p and the presentation step upscales,
        which keeps CPU rasterisation affordable.
        """
        screen = pygame.display.get_surface()
        if size is None:
            if screen is None:
                return
            size = screen.get_size()
        target = self.canvas_size_for(size)
        current = self.r.surface.get_size()
        # Canvas must be a separate off-screen surface.  Reusing the display
        # surface makes present() erase the frame it just drew: present fills
        # the screen (== canvas) with the backdrop colour and then blits the
        # canvas onto itself.
        needs_new = (
            current != target
            or self.canvas is not self.r.surface
            or (screen is not None and self.r.surface is screen)
        )
        if needs_new:
            # Opaque canvas.  SRCALPHA made the whole UI invisible after a
            # restart because software blit treats its alpha as transparency.
            surface = pygame.Surface(target)
            surface.fill((0, 0, 0))
            self.r.surface = surface
            self._canvas_version += 1
        self.canvas = self.r.surface
        self.size = (max(1, int(size[0])), max(1, int(size[1])))
        if self.gl_renderer:
            self.gl_renderer.resize(*self.canvas.get_size())

    def apply_window_resize(self, size):
        """Подгонка под новый размер окна без пересоздания GL-контекста.

        Вызывается на pygame.VIDEORESIZE: set_mode уже не нужен, SDL сам
        изменил поверхность окна.  Пересчитываются канва, viewport и
        масштаб презентации.
        """
        size = (max(1, int(size[0])), max(1, int(size[1])))
        changed = self.canvas.get_size() != self.canvas_size_for(size)
        if not changed:
            self.size = size
            self.layout()
            return False
        self.sync_canvas(size)
        self.layout()
        return True

    def layout(self):
        # Canvas already matches the window, so the presented rect is 1:1.
        # fit_rect remains the contract if a caller presents a different size.
        self.rect = fit_rect(self.canvas.get_size(), self.size)

    def position(self, pos):
        self.layout()
        if not self.rect.collidepoint(pos):
            return (-1, -1)
        return (int((pos[0] - self.rect.x) * self.canvas.get_width() / self.rect.w),
                int((pos[1] - self.rect.y) * self.canvas.get_height() / self.rect.h))

    def present(self):
        self.layout()
        screen = pygame.display.get_surface()
        if screen is None:
            return
        if self.backend == "opengl" and self.gl is not None:
            try:
                self._present_opengl(screen)
                return
            except Exception as exc:
                # GL context lost or texture upload failed — fall back to
                # software presentation so the frame still appears.
                self.error = f"GL present failed: {exc}"
                self.backend = "software"
                self.gl = None
        screen.fill((3, 5, 10))
        # Skip the resample entirely when the canvas already matches the
        # target rect — most common case for ≤1080p windows.
        if self.canvas.get_size() == self.rect.size:
            screen.blit(self.canvas, self.rect)
        else:
            scale = pygame.transform.smoothscale if self.smooth else pygame.transform.scale
            screen.blit(scale(self.canvas, self.rect.size), self.rect)
        pygame.display.flip()

    def _present_opengl(self, screen):
        """GPU texture presentation; gameplay drawing remains safe CPU fallback."""
        gl = self.gl
        w, h = self.canvas.get_size()
        gl.glViewport(0,0,*screen.get_size())
        gl.glClearColor(3/255,5/255,10/255,1)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT)
        gl.glViewport(self.rect.x,screen.get_height()-self.rect.bottom,self.rect.w,self.rect.h)
        gl.glMatrixMode(gl.GL_PROJECTION)
        gl.glLoadIdentity()
        gl.glMatrixMode(gl.GL_MODELVIEW)
        gl.glLoadIdentity()
        gl.glEnable(gl.GL_TEXTURE_2D)
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDisable(gl.GL_BLEND)
        gl.glDisable(gl.GL_ALPHA_TEST)
        gl.glColor4f(1,1,1,1)
        
        # Stage 2: If GLRenderer handled the frame, its FBO already contains
        # the entire UI + 3D scene. Just blit the FBO to screen without tostring.
        composed = bool(self.gl_renderer and self.gl_renderer.fbo_rendered)
        if composed:
            gl.glBindTexture(gl.GL_TEXTURE_2D, self.gl_renderer.fbo_texture)
            filtering = gl.GL_LINEAR if self.smooth else gl.GL_NEAREST
            gl.glTexParameteri(gl.GL_TEXTURE_2D,gl.GL_TEXTURE_MIN_FILTER,filtering)
            gl.glTexParameteri(gl.GL_TEXTURE_2D,gl.GL_TEXTURE_MAG_FILTER,filtering)
            gl.glColor4f(1,1,1,1)
            gl.glBegin(gl.GL_QUADS)
            for u,v,x,y in ((0,0,-1,-1),(1,0,1,-1),(1,1,1,1),(0,1,-1,1)):
                gl.glTexCoord2f(u,v)
                gl.glVertex2f(x,y)
            gl.glEnd()
            # Mark as consumed
            self.gl_renderer.fbo_rendered = False
        else:
            # Legacy path: copy canvas through tostring (for tiles/sprites not yet in GL)
            data = pygame.image.tostring(self.canvas, "RGB", True)
            
            # Tell the driver rows are tightly packed; the default 4-byte
            # alignment silently corrupts RGB uploads whose pitch is not a
            # multiple of 4 (canvas widths like 1366 hit this).
            gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, 1)
            if self.gl_texture is None or self._gl_texture_size != (w, h):
                if self.gl_texture is not None:
                    gl.glDeleteTextures([self.gl_texture])
                self.gl_texture = gl.glGenTextures(1)
                self._gl_texture_size = (w, h)
                gl.glBindTexture(gl.GL_TEXTURE_2D,self.gl_texture)
                gl.glTexImage2D(gl.GL_TEXTURE_2D,0,gl.GL_RGB,w,h,0,gl.GL_RGB,gl.GL_UNSIGNED_BYTE,data)
            else:
                gl.glBindTexture(gl.GL_TEXTURE_2D,self.gl_texture)
                gl.glTexSubImage2D(gl.GL_TEXTURE_2D,0,0,0,w,h,gl.GL_RGB,gl.GL_UNSIGNED_BYTE,data)
            filtering = gl.GL_LINEAR if self.smooth else gl.GL_NEAREST
            gl.glTexParameteri(gl.GL_TEXTURE_2D,gl.GL_TEXTURE_MIN_FILTER,filtering)
            gl.glTexParameteri(gl.GL_TEXTURE_2D,gl.GL_TEXTURE_MAG_FILTER,filtering)
            gl.glColor4f(1,1,1,1)
            gl.glBegin(gl.GL_QUADS)
            for u,v,x,y in ((0,0,-1,-1),(1,0,1,-1),(1,1,1,1),(0,1,-1,1)):
                gl.glTexCoord2f(u,v)
                gl.glVertex2f(x,y)
            gl.glEnd()
        
        if self.scene is not None and not composed:
            texture,area=self.scene
            gl.glEnable(gl.GL_SCISSOR_TEST)
            gl.glScissor(self.rect.x+int(area.x*self.rect.w/w),
                         screen.get_height()-self.rect.y-int(area.bottom*self.rect.h/h),
                         max(1,int(area.w*self.rect.w/w)),max(1,int(area.h*self.rect.h/h)))
            gl.glBindTexture(gl.GL_TEXTURE_2D,texture)
            x0,x1=2*area.left/w-1,2*area.right/w-1
            y0,y1=1-2*area.top/h,1-2*area.bottom/h
            import math
            angle=math.radians(self.scene_roll)
            center=area.center
            gl.glBegin(gl.GL_QUADS)
            for u,v,x,y in ((0,1,x0,y0),(1,1,x1,y0),(1,0,x1,y1),(0,0,x0,y1)):
                if self.scene_roll:
                    px=(x+1)*w/2-center[0]; py=(1-y)*h/2-center[1]
                    xx=px*math.cos(angle)-py*math.sin(angle)+center[0]
                    yy=px*math.sin(angle)+py*math.cos(angle)+center[1]
                    x,y=2*xx/w-1,1-2*yy/h
                gl.glTexCoord2f(u,v); gl.glVertex2f(x,y)
            gl.glEnd()
            gl.glDisable(gl.GL_SCISSOR_TEST)
        gl.glDisable(gl.GL_TEXTURE_2D)
        pygame.display.flip()
