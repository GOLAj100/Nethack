"""Real Tk smoke/integration check, writes only inside a temporary mod."""
import os
import sys
import tempfile
import tkinter as tk
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame
from tileset_editor import Editor
from ascii_importer import AsciiImporter

root=tk.Tk()
try:
    editor=Editor(root)
    with tempfile.TemporaryDirectory() as tmp:
        editor.ts.root=tmp
        editor.mod.set('test')
        dialog=AsciiImporter(editor)
        root.update()
        dialog.source=pygame.Surface((64,32),pygame.SRCALPHA)
        dialog.source.fill((255,255,255,255))
        assert dialog.render()
        pygame.draw.rect(dialog.source,(255,0,0),(16,8,32,16))
        dialog.auto_background()
        assert dialog.cleaned.get_at((0,0)).a==0
        assert dialog.cleaned.get_at((25,15)).a==255
        assert dialog.source.get_at((0,0)).a==255
        editor.atlas['%']=[0,0]
        dialog.symbol.set('%')
        dialog.assign()
        assert '%' in editor.mapping and '%' not in editor.atlas
        assert os.path.exists(os.path.join(tmp,'test',editor.mapping['%']))
        dialog.window.destroy()
finally:
    root.destroy()
print('ASCII EDITOR OK')
