"""Compose scene textures into the UI FBO at the map's painter-order slot."""


class GLCompositor:
    @staticmethod
    def compose(renderer, scene, index):
        if scene is None:
            return
        texture, area = scene
        # Render targets have bottom-up UVs; uploaded sprite atlases are top-down.
        renderer.batch.image(texture, area, (0, 1, 1, 0), index=index)
