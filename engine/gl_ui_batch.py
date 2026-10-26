"""Batched UI rendering: text, rectangles, lines.

All draw calls accumulate in CPU buffers. ``end()`` uploads once and renders
with a single shader pass, avoiding per-glyph state changes.
"""
from __future__ import annotations


class UIBatch:
    """Batched OpenGL UI renderer: text quads + colored rectangles."""
    
    MAX_QUADS = 8192  # vertices = MAX_QUADS * 4
    
    def __init__(self, gl, atlas):
        self.gl = gl
        self.atlas = atlas
        self.vbo = None
        self.program = None
        self.width = 1280
        self.height = 720
        self.quads = []  # [(x, y, w, h, r, g, b, a, u0, v0, u1, v1), ...]
        self.materials = []
    
    def init(self):
        """Compile shader and create VBO."""
        gl = self.gl
        
        # Vertex shader: position + color + UV
        vs_src = """
        #version 110
        attribute vec2 position;
        attribute vec4 color;
        attribute vec2 texcoord;
        varying vec4 v_color;
        varying vec2 v_texcoord;
        uniform vec2 resolution;
        
        void main() {
            // Map pixel coords to [-1, 1] (Y is flipped: top = 1, bottom = -1)
            vec2 ndc = vec2(
                2.0 * position.x / resolution.x - 1.0,
                1.0 - 2.0 * position.y / resolution.y
            );
            gl_Position = vec4(ndc, 0.0, 1.0);
            v_color = color;
            v_texcoord = texcoord;
        }
        """
        
        # Fragment shader: multiply texture alpha by color alpha
        fs_src = """
        #version 110
        varying vec4 v_color;
        varying vec2 v_texcoord;
        uniform sampler2D tex;
        uniform int use_texture;
        
        void main() {
            if (use_texture == 1) {
                vec4 t = texture2D(tex, v_texcoord);
                gl_FragColor = v_color * t;
            } else {
                gl_FragColor = v_color;
            }
        }
        """
        
        vs = gl.glCreateShader(gl.GL_VERTEX_SHADER)
        gl.glShaderSource(vs, vs_src)
        gl.glCompileShader(vs)
        if not gl.glGetShaderiv(vs, gl.GL_COMPILE_STATUS):
            raise RuntimeError(f"VS compile failed: {gl.glGetShaderInfoLog(vs)}")
        
        fs = gl.glCreateShader(gl.GL_FRAGMENT_SHADER)
        gl.glShaderSource(fs, fs_src)
        gl.glCompileShader(fs)
        if not gl.glGetShaderiv(fs, gl.GL_COMPILE_STATUS):
            raise RuntimeError(f"FS compile failed: {gl.glGetShaderInfoLog(fs)}")
        
        self.program = gl.glCreateProgram()
        gl.glAttachShader(self.program, vs)
        gl.glAttachShader(self.program, fs)
        gl.glLinkProgram(self.program)
        if not gl.glGetProgramiv(self.program, gl.GL_LINK_STATUS):
            raise RuntimeError(f"Link failed: {gl.glGetProgramInfoLog(self.program)}")
        
        gl.glDeleteShader(vs)
        gl.glDeleteShader(fs)
        
        self.vbo = gl.glGenBuffers(1)
    
    def resize(self, width, height):
        self.width = width
        self.height = height
    
    def begin(self):
        """Start a new batch."""
        self.quads.clear()
        self.materials.clear()
    
    def rect(self, x, y, w, h, color, border_radius=0, alpha=None):
        """Add a solid rectangle (no texture)."""
        if len(color) == 4:
            r, g, b, a = color[0] / 255, color[1] / 255, color[2] / 255, color[3] / 255
        else:
            r, g, b = color[0] / 255, color[1] / 255, color[2] / 255
            a = 1.0 if alpha is None else alpha / 255
        if w <= 0 or h <= 0:
            return
        radius = min(max(0, border_radius), w / 2, h / 2)
        if radius:
            import math
            for row in range(int(h)):
                dy = max(radius - row - 0.5, row + 0.5 - (h - radius), 0)
                inset = radius - math.sqrt(max(0, radius * radius - dy * dy))
                self.rect(x + inset, y + row, w - 2 * inset, 1, color, alpha=alpha)
            return
        # u/v = -1 signals "no texture" in the shader via use_texture uniform
        self.quads.append((x, y, w, h, r, g, b, a, -1, -1, -1, -1))
        self.materials.append(0)
    
    def rect_outline(self, x, y, w, h, color, thickness=1, border_radius=0):
        """Add a rectangle outline (four thin rects)."""
        if border_radius:
            import math
            radius = min(border_radius, w / 2, h / 2)
            for row in range(int(h)):
                dy = max(radius - row - 0.5, row + 0.5 - (h - radius), 0)
                inset = radius - math.sqrt(max(0, radius * radius - dy * dy))
                if row < thickness or row >= h - thickness:
                    self.rect(x + inset, y + row, w - 2 * inset, 1, color)
                else:
                    self.rect(x + inset, y + row, thickness, 1, color)
                    self.rect(x + w - inset - thickness, y + row, thickness, 1, color)
            return
        # Top
        self.rect(x, y, w, thickness, color)
        # Bottom
        self.rect(x, y + h - thickness, w, thickness, color)
        # Left
        self.rect(x, y + thickness, thickness, h - 2 * thickness, color)
        # Right
        self.rect(x + w - thickness, y + thickness, thickness, h - 2 * thickness, color)
    
    def line(self, x0, y0, x1, y1, color, thickness=1):
        """Add a line as a rotated rectangle."""
        import math
        dx, dy = x1 - x0, y1 - y0
        length = math.sqrt(dx * dx + dy * dy)
        if length < 0.01:
            return
        # Draw a thin rectangle along the line
        angle = math.atan2(dy, dx)
        # For simplicity, just draw axis-aligned lines for now
        if abs(dx) > abs(dy):
            # Horizontal-ish
            self.rect(min(x0, x1), y0 - thickness // 2, abs(dx), thickness, color)
        else:
            # Vertical-ish
            self.rect(x0 - thickness // 2, min(y0, y1), thickness, abs(dy), color)
    
    def text(self, x, y, char, color, size=18, bold=False):
        """Add a single glyph quad."""
        uv_data = self.atlas.uv(char, bold)
        if uv_data is None:
            return  # Glyph not in atlas
        u0, v0, u1, v1, gw, gh = uv_data
        r, g, b = color[0] / 255, color[1] / 255, color[2] / 255
        a = 1.0
        scale = size / self.atlas.size
        self.quads.append((x, y, gw * scale, gh * scale, r, g, b, a, u0, v0, u1, v1))
        self.materials.append(self.atlas.texture)

    def image(self, texture, rect, uv=(0, 0, 1, 1), color=(255, 255, 255, 255), index=None):
        rgba = tuple(c / 255 for c in color)
        if len(rgba) == 3:
            rgba += (1.0,)
        quad = (*rect, *rgba, *uv)
        if index is None:
            self.quads.append(quad)
            self.materials.append(texture)
        else:
            self.quads.insert(index, quad)
            self.materials.insert(index, texture)
    
    def end(self):
        """Upload and render all quads."""
        if not self.quads:
            return
        
        gl = self.gl
        gl.glUseProgram(self.program)
        
        # Set resolution uniform
        res_loc = gl.glGetUniformLocation(self.program, b"resolution")
        gl.glUniform2f(res_loc, float(self.width), float(self.height))
        
        # Vertex format: [x, y, r, g, b, a, u, v] * 4 vertices per quad
        vertices = []
        for quad in self.quads:
            x, y, w, h, r, g, b, a, u0, v0, u1, v1 = quad
            textured = u0 >= 0
            # Top-left, top-right, bottom-right, bottom-left (CCW winding)
            for vx, vy, u, v in ((x, y, u0, v0), (x + w, y, u1, v0),
                                  (x + w, y + h, u1, v1), (x, y + h, u0, v1)):
                vertices.extend([vx, vy, r, g, b, a, u, v])
        
        import ctypes
        import array
        data = array.array("f", vertices)
        
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, len(data) * 4, data.tobytes(), gl.GL_STREAM_DRAW)
        
        pos_loc = gl.glGetAttribLocation(self.program, b"position")
        col_loc = gl.glGetAttribLocation(self.program, b"color")
        tex_loc = gl.glGetAttribLocation(self.program, b"texcoord")
        
        stride = 8 * 4  # 8 floats per vertex, 4 bytes per float
        gl.glEnableVertexAttribArray(pos_loc)
        gl.glVertexAttribPointer(pos_loc, 2, gl.GL_FLOAT, False, stride, ctypes.c_void_p(0))
        gl.glEnableVertexAttribArray(col_loc)
        gl.glVertexAttribPointer(col_loc, 4, gl.GL_FLOAT, False, stride, ctypes.c_void_p(2 * 4))
        gl.glEnableVertexAttribArray(tex_loc)
        gl.glVertexAttribPointer(tex_loc, 2, gl.GL_FLOAT, False, stride, ctypes.c_void_p(6 * 4))
        
        # Bind font atlas texture
        tex_uniform = gl.glGetUniformLocation(self.program, b"tex")
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.atlas.texture)
        gl.glUniform1i(tex_uniform, 0)
        
        # Render all quads (each quad = 4 vertices, drawn as GL_QUADS or two triangles)
        # GL 1.x compatibility: use glDrawArrays with GL_QUADS
        use_tex_loc = gl.glGetUniformLocation(self.program, b"use_texture")
        
        # Preserve painter order; merge only adjacent commands with one material.
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDisable(gl.GL_SCISSOR_TEST)
        gl.glDisable(gl.GL_CULL_FACE)
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFuncSeparate(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA,
                               gl.GL_ONE, gl.GL_ONE_MINUS_SRC_ALPHA)
        start = 0
        while start < len(self.materials):
            texture = self.materials[start]
            stop = start + 1
            while stop < len(self.materials) and self.materials[stop] == texture:
                stop += 1
            gl.glUniform1i(use_tex_loc, int(bool(texture)))
            gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
            gl.glDrawArrays(gl.GL_QUADS, start * 4, (stop - start) * 4)
            start = stop
        gl.glDisable(gl.GL_BLEND)
        
        gl.glDisableVertexAttribArray(pos_loc)
        gl.glDisableVertexAttribArray(col_loc)
        gl.glDisableVertexAttribArray(tex_loc)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)
        gl.glUseProgram(0)
        self.begin()
    
    def close(self):
        if self.vbo:
            self.gl.glDeleteBuffers(1, [self.vbo])
            self.vbo = None
        if self.program:
            self.gl.glDeleteProgram(self.program)
            self.program = None
