"""OpenGL drop-in replacement for pygame.draw functions.

Intercepts pygame.draw.* calls and routes them through GLRenderer batch
when GL is enabled, otherwise falls back to pygame.draw.
"""
from __future__ import annotations

import pygame


class GLDrawWrapper:
    """Wrapper that redirects pygame.draw calls to GLRenderer."""
    
    def __init__(self, gl_renderer):
        self.gl_renderer = gl_renderer
        self._orig_draw = pygame.draw
    
    def rect(self, surface, color, rect, width=0, border_radius=0):
        """Draw rectangle: filled if width=0, outline otherwise."""
        if self.gl_renderer and self.gl_renderer.active and surface is self.gl_renderer.surface:
            if width == 0:
                # Filled
                self.gl_renderer.draw_rect(rect, color, border_radius)
            else:
                # Outline
                self.gl_renderer.draw_rect_outline(rect, color, width, border_radius)
            return rect  # pygame.draw returns the drawn rect
        else:
            return self._orig_draw.rect(surface, color, rect, width, border_radius=border_radius)
    
    def line(self, surface, color, start_pos, end_pos, width=1):
        """Draw a line."""
        if self.gl_renderer and self.gl_renderer.active and surface is self.gl_renderer.surface:
            self.gl_renderer.draw_line(start_pos, end_pos, color, width)
            return pygame.Rect(min(start_pos[0], end_pos[0]), 
                             min(start_pos[1], end_pos[1]),
                             abs(end_pos[0] - start_pos[0]) or 1,
                             abs(end_pos[1] - start_pos[1]) or 1)
        else:
            return self._orig_draw.line(surface, color, start_pos, end_pos, width)
    
    def circle(self, surface, color, center, radius, width=0):
        """Draw circle. Fall back to pygame for now (TODO: SDF shader)."""
        return self._orig_draw.circle(surface, color, center, radius, width)
    
    def polygon(self, surface, color, points, width=0):
        """Draw polygon. Fall back to pygame for now."""
        return self._orig_draw.polygon(surface, color, points, width)
    
    def __getattr__(self, name):
        """Pass through any other pygame.draw functions."""
        return getattr(self._orig_draw, name)


def install_gl_draw_wrapper(gl_renderer):
    """Replace pygame.draw with GLDrawWrapper globally."""
    wrapper = GLDrawWrapper(gl_renderer)
    # Monkey-patch pygame.draw module
    import sys
    sys.modules['pygame'].draw = wrapper
    return wrapper


def uninstall_gl_draw_wrapper():
    """Restore original pygame.draw."""
    import sys
    wrapper = sys.modules['pygame'].draw
    if isinstance(wrapper, GLDrawWrapper):
        sys.modules['pygame'].draw = wrapper._orig_draw
