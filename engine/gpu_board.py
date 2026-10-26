"""Cached world-space board mesh; OpenGL transforms and rasterizes on rotation."""
import math
import pygame


class GPUBoard:
    def __init__(self,gl):
        self.gl=gl
        self.mesh=None
        self.key=None
        self.texture=int(gl.glGenTextures(1))
        self.depth=int(gl.glGenRenderbuffers(1))
        self.fbo=int(gl.glGenFramebuffers(1))
        self.size=None

    def pick(self,view,game,pos):
        if not view.rect.collidepoint(pos) or self.size is None: return None
        from OpenGL.GLU import gluUnProject
        gl=self.gl
        x=int(pos[0]-view.rect.x); y=self.size[1]-1-int(pos[1]-view.rect.y)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER,self.fbo)
        try:
            import struct
            depth=struct.unpack('f',bytes(gl.glReadPixels(x,y,1,1,gl.GL_DEPTH_COMPONENT,gl.GL_FLOAT)))[0]
        finally:
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER,0)
        if depth>=1: return None
        wx,wy,wz=gluUnProject(x+.5,y+.5,depth,self.model,self.projection,(0,0,*self.size))
        layer=math.floor((wz+.3)/4)
        if layer!=game.player.world_z: return None
        return math.floor(wx),math.floor(wy)

    def close(self):
        gl=self.gl
        if self.mesh is not None: gl.glDeleteLists(self.mesh,1)
        gl.glDeleteTextures([self.texture])
        gl.glDeleteRenderbuffers(1,[self.depth])
        gl.glDeleteFramebuffers(1,[self.fbo])

    def draw(self,view,game,layers,focus_z,scale):
        gl=self.gl
        size=view.rect.size
        grids = {lv: lv.visual_manager.grid() for lv in layers}
        key=(id(game.world),view.full_map,view.outlines,
             tuple((lv.chunk_x,lv.chunk_y,lv.world_z,lv.visual_manager.revision,tuple((f.kind,f.x,f.y,f.rotated) for f in lv.furniture),frozenset(lv.explored),frozenset(lv.mapped),
                    tuple(sorted((pos,tuple(sorted(d.items()))) for pos,d in lv.doors.items()))) for lv in layers))
        if key!=self.key:
            if self.mesh is not None: gl.glDeleteLists(self.mesh,1)
            self.mesh=int(gl.glGenLists(1))
            gl.glNewList(self.mesh,gl.GL_COMPILE)
            gl.glBegin(gl.GL_QUADS)
            edges=[]
            for lv in layers:
                grid = grids[lv]
                known=lv.explored|lv.mapped
                for y in range(lv.h):
                    for x in range(lv.w):
                        if grid.tiles[y*lv.w+x]==10 or (not view.full_map and (x,y) not in known): continue
                        wall=bool(grid.walls[y*lv.w+x])
                        z=lv.world_z*4
                        top=z+(.85 if wall else 0)
                        if grid.fixtures[y*lv.w+x] is not None and not wall: top=z+.5
                        _,color=game.tile_glyph(lv,grid.tiles[y*lv.w+x],x,y,0,True)
                        corners=[(x,y),(x+1,y),(x+1,y+1),(x,y+1)]
                        polys=[([(a,b,top) for a,b in corners],color),
                               ([(a,b,z-.25) for a,b in reversed(corners)],color)]
                        for i,(nx,ny) in enumerate(((x,y-1),(x+1,y),(x,y+1),(x-1,y))):
                            if wall and lv.in_bounds(nx,ny) and grid.walls[ny*lv.w+nx]: continue
                            if not wall and grid.fixtures[y*lv.w+x] is None and lv.in_bounds(nx,ny) and grid.tiles[ny*lv.w+nx]!=10: continue
                            a,b=corners[i],corners[(i+1)%4]
                            polys.append(([(a[0],a[1],top),(b[0],b[1],top),(b[0],b[1],z-.25),(a[0],a[1],z-.25)],tuple(int(c*.65) for c in color)))
                        for poly,c in polys:
                            gl.glColor3ub(*c)
                            for point in poly: gl.glVertex3f(*point)
                            if view.outlines: edges.append(poly)
            gl.glEnd()
            if view.outlines:
                gl.glColor3ub(40,36,24)
                gl.glBegin(gl.GL_LINES)
                for poly in edges:
                    for a,b in zip(poly,poly[1:]+poly[:1]):
                        gl.glVertex3f(*a); gl.glVertex3f(*b)
                gl.glEnd()
            gl.glEndList()
            self.key=key
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER,self.fbo)
        if self.size!=size:
            gl.glBindTexture(gl.GL_TEXTURE_2D,self.texture)
            gl.glTexImage2D(gl.GL_TEXTURE_2D,0,gl.GL_RGBA8,*size,0,gl.GL_RGBA,gl.GL_UNSIGNED_BYTE,None)
            gl.glTexParameteri(gl.GL_TEXTURE_2D,gl.GL_TEXTURE_MIN_FILTER,gl.GL_LINEAR)
            gl.glTexParameteri(gl.GL_TEXTURE_2D,gl.GL_TEXTURE_MAG_FILTER,gl.GL_LINEAR)
            gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER,gl.GL_COLOR_ATTACHMENT0,gl.GL_TEXTURE_2D,self.texture,0)
            gl.glBindRenderbuffer(gl.GL_RENDERBUFFER,self.depth)
            gl.glRenderbufferStorage(gl.GL_RENDERBUFFER,gl.GL_DEPTH_COMPONENT24,*size)
            gl.glFramebufferRenderbuffer(gl.GL_FRAMEBUFFER,gl.GL_DEPTH_ATTACHMENT,gl.GL_RENDERBUFFER,self.depth)
            self.size=size
        gl.glDrawBuffer(gl.GL_COLOR_ATTACHMENT0)
        if gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER)!=gl.GL_FRAMEBUFFER_COMPLETE: raise RuntimeError('Board framebuffer incomplete')
        gl.glUseProgram(0); gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glDisable(gl.GL_TEXTURE_2D); gl.glDisable(gl.GL_BLEND)
        gl.glEnable(gl.GL_DEPTH_TEST); gl.glDepthFunc(gl.GL_LEQUAL)
        gl.glViewport(0,0,*size)
        gl.glClearColor(13/255,19/255,32/255,1)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT|gl.GL_DEPTH_BUFFER_BIT)
        gl.glMatrixMode(gl.GL_PROJECTION); gl.glLoadIdentity()
        gl.glOrtho(-size[0]/(2*scale),size[0]/(2*scale),-size[1]/(2*scale),size[1]/(2*scale),-500,500)
        gl.glMatrixMode(gl.GL_MODELVIEW); gl.glLoadIdentity()
        # Match CPU orthographic projection, using a real Z-buffer.
        ca,sa=math.cos(view.orbit),math.sin(view.orbit)
        st,ct=math.sin(view.tilt),math.cos(view.tilt)
        gl.glMultMatrixf((ca,-sa*st,sa*ct,0, -sa,-ca*st,ca*ct,0, 0,ct,st,0, 0,0,0,1))
        gl.glTranslatef(-game.world.w/2,-game.world.h/2,-focus_z*4)
        self.model=gl.glGetDoublev(gl.GL_MODELVIEW_MATRIX)
        self.projection=gl.glGetDoublev(gl.GL_PROJECTION_MATRIX)
        if view.outlines:
            gl.glEnable(gl.GL_POLYGON_OFFSET_FILL); gl.glPolygonOffset(1,1)
        gl.glCallList(self.mesh)
        gl.glDisable(gl.GL_POLYGON_OFFSET_FILL); gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER,0)
        game.display.scene=(self.texture,view.rect.copy())
        game.r.surface.fill((0, 0, 0), view.rect)
