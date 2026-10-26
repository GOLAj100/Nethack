"""Editable CPU material shader. Return an RGB tuple; no GPU/GLSL required.

shade(color, distance, normal, base_light, lighting, fog) is called for 3D faces.
Change this function to create your own material/light palette, then restart.
Geometry is created with pygame.draw.polygon/line in views.py.
"""
def shade(color, distance=0, normal=1.0, base_light=1.0,
          lighting=True, fog=True, profile=None):
    # Backrooms Level 0 uses flat fluorescent lighting: the whole level is
    # lit evenly by ceiling panels, so distance falloff is minimal and fog
    # is barely visible.  Other levels fall back to the dramatic default.
    flat = (profile or {}).get('flat_lighting', False)
    if flat:
        strength = max(0.5, float(base_light) * (1.0 - distance * 0.01) * normal)
        mist = min(0.3, max(0, distance - 12) / 40) if fog else 0
        return tuple(max(0, min(255, int(c * strength * (1 - mist) + f * mist)))
                     for c, f in zip(color, (20, 22, 30)))
    strength = 1.0
    if lighting:
        strength = max(0.12, float(base_light) * (1.12 - distance * 0.055) * normal)
    mist = min(0.85, max(0, distance - 4) / 24) if fog else 0
    return tuple(max(0, min(255, int(c * strength * (1 - mist) + f * mist)))
                 for c, f in zip(color, (13, 19, 32)))
