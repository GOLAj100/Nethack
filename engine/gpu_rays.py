"""GLSL voxel traversal. Optional GPU terrain pass; sprites retain CPU depth tests."""
import ctypes
import math
import struct
from array import array
import pygame

VERT = '''#version 330 compatibility
void main() { gl_Position = gl_Vertex; }
'''
FRAG = '''#version 330 compatibility
uniform sampler3D terrain;
uniform sampler3D materials;
uniform sampler2DArray atlas;
uniform vec3 origin;
uniform vec3 forward_dir;
uniform vec3 right_dir;
uniform vec3 up_dir;
uniform vec3 offset;
uniform ivec3 dimensions;
uniform vec2 resolution;
uniform float focal;
uniform float max_distance;
uniform bool ceiling;
uniform bool lighting;
uniform bool fog;
uniform float flicker;
uniform vec3 sky;
uniform vec3 floor_color;
uniform vec3 ceiling_color;
uniform int wall_layer;
uniform int floor_layer;
uniform int ceiling_layer;
uniform bool flat_light;
uniform bool wet_floor;
uniform float vignette_strength;
uniform float grain_strength;
uniform float grain_seed;
layout(location=0) out vec4 color;
layout(location=1) out vec4 info;
float tile(ivec3 p) {
 if(any(lessThan(p,ivec3(0))) || any(greaterThanEqual(p,dimensions))) return -1.;
 return texelFetch(terrain,p,0).r;
}
float hash(vec2 p){ return fract(sin(dot(p,vec2(12.9898,78.233)))*43758.5453); }
void main() {
 vec2 pixel=vec2(gl_FragCoord.x,resolution.y-gl_FragCoord.y);
 vec2 uv=(pixel-resolution*.5)/focal;
 vec3 ray=forward_dir+uv.x*right_dir-uv.y*up_dir;
 vec3 start=origin-offset;
 ivec3 p=ivec3(floor(start));
 ivec3 step=ivec3(sign(ray));
 vec3 delta=1./max(abs(ray),vec3(.0000001));
 vec3 next=(mix(start-vec3(p),vec3(p)+1.-start,greaterThanEqual(ray,vec3(0))))*delta;
 color=vec4(sky,1); info=vec4(1e6,0,0,0);
 for(int iteration=0;iteration<160;iteration++) {
  int axis=next.x<next.y && next.x<next.z ? 0 : (next.y<next.z ? 1:2);
  float distance=next[axis];
  if(distance>max_distance) return;
  next[axis]+=delta[axis];
  ivec3 old=p; p[axis]+=step[axis];
  float target=tile(p);
  ivec3 owner=p;
  bool roof=false; bool hit=false;
  if(axis==2) {
   ivec3 upper=ray.z>0. ? p:old;
   if(tile(upper)!=10. && (ray.z<0. || ceiling)) {
    owner=ray.z>0. ? old:upper;
    roof=ray.z>0.; hit=true;
   }
  }
  if(!hit && target<0.) return;
  if(!hit && target==0.) hit=true;
  if(hit) {
   if(tile(owner)<0.) return;
   vec4 mat=texelFetch(materials,owner,0);
   vec3 hit_pos=start+ray*distance;
   vec2 tuv;
   int layer=wall_layer;
   if(axis==2) {
    layer=roof ? ceiling_layer:floor_layer;
    tuv=vec2(hit_pos.x,hit_pos.y);
   } else if(axis==0) {
    tuv=vec2(hit_pos.y,hit_pos.z);
   } else {
    tuv=vec2(hit_pos.x,hit_pos.z);
   }
   vec3 tex=texture(atlas,vec3(fract(tuv),float(layer))).rgb;
   vec3 base=tex;
   if(axis==2) base=mix(tex,roof?ceiling_color:floor_color,0.25);
   float strength;
   if(!lighting) strength=1.;
   else if(flat_light) strength=max(.5,mat.a*(1.-distance*.01)*(axis==1?.85:1.));
   else strength=max(.12,mat.a*flicker*(1.12-distance*.055)*(axis==1?.8:1.));
   float mist;
   if(!fog) mist=0.;
   else if(flat_light) mist=clamp((distance-12.)/40.,0.,.3);
   else mist=clamp((distance-4.)/24.,0.,.85);
   vec3 fog_col=flat_light?vec3(20.,22.,30.)/255.:vec3(13.,19,32)/255.;
   vec3 shaded=clamp(mix(base*strength,fog_col,mist),0.,1.);
   // Wet-floor sheen: light pools under the ceiling lamps reflect on the
   // carpet at grazing angles.  Mirrors the CPU compose() term.
   if(wet_floor && axis==2 && !roof && mat.a>0.35) {
    float grazing=1.-min(1.,abs(ray.z)*2.2);
    float spec=mat.a*mat.a*grazing;
    if(spec>0.02) shaded+=vec3(0.353,0.331,0.247)*spec;
   }
   // Post-processing matches the CPU PostFX so both backends look alike.
   vec2 vc=(gl_FragCoord.xy/resolution)*2.-1.;
   float vig=clamp((length(vc)-0.55)/0.9,0.,1.);
   shaded*=1.-vig*vig*vignette_strength;
   if(grain_strength>0.){
    float n=hash(gl_FragCoord.xy+grain_seed*vec2(37.,91.));
    shaded+=(n-.5)*grain_strength*.06;
   }
   color=vec4(clamp(shaded,0.,1.),1.);
   info=vec4(distance,vec3(owner)+offset);
   return;
  }
 }
}
'''

SPRITE_VERT = '''#version 330 compatibility
out vec2 uv;
void main() { gl_Position=gl_Vertex; uv=gl_MultiTexCoord0.xy; }
'''
SPRITE_FRAG = '''#version 330 compatibility
uniform sampler2D sprite_image;
uniform sampler2D terrain_depth;
uniform float sprite_depth;
uniform vec3 world_cell;
in vec2 uv;
layout(location=0) out vec4 color;
layout(location=1) out vec4 info;
void main() {
 vec4 c=texture(sprite_image,uv);
 if(c.a<.05 || sprite_depth>=texelFetch(terrain_depth,ivec2(gl_FragCoord.xy),0).r) discard;
 color=c; info=vec4(sprite_depth,world_cell);
}
'''


class GPURays:
    def __init__(self, gl):
        from OpenGL.GL.shaders import compileProgram, compileShader
        self.gl=gl
        self.program=compileProgram(compileShader(VERT,gl.GL_VERTEX_SHADER),compileShader(FRAG,gl.GL_FRAGMENT_SHADER))
        self.textures=[int(gl.glGenTextures(1)) for _ in range(4)]
        self.fbo=int(gl.glGenFramebuffers(1))
        self.key=None
        self.size=None
        self.chunk_cache={}
        self.region=None
        self.sprite_program=compileProgram(compileShader(SPRITE_VERT,gl.GL_VERTEX_SHADER),compileShader(SPRITE_FRAG,gl.GL_FRAGMENT_SHADER))
        self.sprite_textures={}
        self.depth_copy=int(gl.glGenTextures(1))
        self.depth_size=None
        # Texture array upload is one-shot: the procedural atlases never
        # change at runtime.
        self.atlas_texture = int(gl.glGenTextures(1))
        self._upload_atlas()

    def _upload_atlas(self):
        """Upload the procedural texture set as a 2D array texture."""
        from . import textures
        gl = self.gl
        layers = textures.atlas_layers()          # (n, 64, 64, 3) uint8
        n, w, h, _ = layers.shape
        gl.glBindTexture(gl.GL_TEXTURE_2D_ARRAY, self.atlas_texture)
        gl.glTexImage3D(gl.GL_TEXTURE_2D_ARRAY, 0, gl.GL_RGB8, w, h, n,
                        0, gl.GL_RGB, gl.GL_UNSIGNED_BYTE, layers.tobytes())
        gl.glTexParameteri(gl.GL_TEXTURE_2D_ARRAY, gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST)
        gl.glTexParameteri(gl.GL_TEXTURE_2D_ARRAY, gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST)
        gl.glTexParameteri(gl.GL_TEXTURE_2D_ARRAY, gl.GL_TEXTURE_WRAP_S, gl.GL_REPEAT)
        gl.glTexParameteri(gl.GL_TEXTURE_2D_ARRAY, gl.GL_TEXTURE_WRAP_T, gl.GL_REPEAT)

    def close(self):
        gl=self.gl
        gl.glDeleteTextures(self.textures + [self.depth_copy, self.atlas_texture] + list(self.sprite_textures.values()))
        gl.glDeleteFramebuffers(1,[self.fbo])
        gl.glDeleteProgram(self.program)
        gl.glDeleteProgram(self.sprite_program)

    def pick(self, sx, sy, area, game):
        if not self.size or not area.collidepoint(sx,sy):
            return None
        gl=self.gl
        width,height=self.size
        x=min(width-1,int((sx-area.x)*width/area.w))
        y=height-1-min(height-1,int((sy-area.y)*height/area.h))
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER,self.fbo)
        gl.glDisable(gl.GL_BLEND)
        gl.glDisable(gl.GL_DEPTH_TEST)
        try:
            gl.glReadBuffer(gl.GL_COLOR_ATTACHMENT1)
            d,wx,wy,wz=struct.unpack('ffff',bytes(gl.glReadPixels(x,y,1,1,gl.GL_RGBA,gl.GL_FLOAT)))
        finally:
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER,0)
        if d>=1e5 or round(wz)!=game.player.world_z:
            return None
        bx=game.player.chunk_x*game.level.w if game.world else 0
        by=game.player.chunk_y*game.level.h if game.world else 0
        return round(wx)-bx,round(wy)-by

    def draw_sprites(self, view, game, width, height, forward, right, up):
        """Depth-test billboards on GPU; never sample an attached render texture."""
        gl=self.gl
        p=game.player
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D,self.depth_copy)
        gl.glReadBuffer(gl.GL_COLOR_ATTACHMENT1)
        if self.depth_size!=(width,height):
            gl.glTexImage2D(gl.GL_TEXTURE_2D,0,gl.GL_RGBA32F,width,height,0,gl.GL_RGBA,gl.GL_FLOAT,None)
            gl.glTexParameteri(gl.GL_TEXTURE_2D,gl.GL_TEXTURE_MIN_FILTER,gl.GL_NEAREST)
            gl.glTexParameteri(gl.GL_TEXTURE_2D,gl.GL_TEXTURE_MAG_FILTER,gl.GL_NEAREST)
            self.depth_size=width,height
        gl.glCopyTexSubImage2D(gl.GL_TEXTURE_2D,0,0,0,0,0,width,height)
        gl.glUseProgram(self.sprite_program)
        def loc(name): return gl.glGetUniformLocation(self.sprite_program,name)
        gl.glUniform1i(loc('sprite_image'),0)
        gl.glUniform1i(loc('terrain_depth'),1)
        gl.glActiveTexture(gl.GL_TEXTURE1)
        gl.glBindTexture(gl.GL_TEXTURE_2D,self.depth_copy)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        from .volume import collect_sprites
        sprites=collect_sprites(game, getattr(view, 'visual_objects', None))
        projected=[]
        focal=width/(2*0.66)
        overlay=getattr(game,'debug_overlay',None)
        boxes=[]
        for x,y,glyph,color,z,h,light in sprites:
            offset=(x-p.x,y-p.y,z-.45)
            d=sum(a*b for a,b in zip(offset,forward))
            if d<=.1: continue
            projected.append((d,x,y,glyph,color,h,light,offset))
        for d,x,y,glyph,color,h,light,offset in sorted(projected,reverse=True):
            cx=width/2+sum(a*b for a,b in zip(offset,right))*focal/d
            cy=height/2-sum(a*b for a,b in zip(offset,up))*focal/d
            size=max(1,min(height*2,int(h*focal/d)))
            left,top=int(cx-size/2),int(cy-size/2)
            if overlay is not None and overlay.enabled and 'sprites' in overlay.modes:
                area=getattr(view,'rect',None)
                if area is not None and area.w and area.h:
                    boxes.append(pygame.Rect(
                        area.x+int(left*area.w/max(1,width)),
                        area.y+int((height-top-size)*area.h/max(1,height)),
                        max(1,int(size*area.w/max(1,width))),
                        max(1,int(size*area.h/max(1,height)))))
            if left>=width or top>=height or left+size<=0 or top+size<=0: continue
            tint=view.color(color,d,light=light)
            image=game.r.visual(glyph,tint,True,size=(256,256))
            # Renderer returns immutable cached glyphs/sprites; bounded GPU cache.
            key=(glyph,tuple(tint),id(image))
            if key not in self.sprite_textures:
                if len(self.sprite_textures)>=512:
                    gl.glDeleteTextures(list(self.sprite_textures.values()))
                    self.sprite_textures.clear()
                texture=int(gl.glGenTextures(1))
                gl.glBindTexture(gl.GL_TEXTURE_2D,texture)
                gl.glTexImage2D(gl.GL_TEXTURE_2D,0,gl.GL_RGBA8,*image.get_size(),0,gl.GL_RGBA,gl.GL_UNSIGNED_BYTE,pygame.image.tobytes(image,'RGBA',True))
                gl.glTexParameteri(gl.GL_TEXTURE_2D,gl.GL_TEXTURE_MIN_FILTER,gl.GL_NEAREST)
                gl.glTexParameteri(gl.GL_TEXTURE_2D,gl.GL_TEXTURE_MAG_FILTER,gl.GL_NEAREST)
                self.sprite_textures[key]=texture
            gl.glBindTexture(gl.GL_TEXTURE_2D,self.sprite_textures[key])
            gl.glUniform1f(loc('sprite_depth'),d)
            bx=p.chunk_x*game.level.w if game.world else 0
            by=p.chunk_y*game.level.h if game.world else 0
            gl.glUniform3f(loc('world_cell'),bx+x,by+y,p.world_z)
            x0,x1=2*left/width-1,2*(left+size)/width-1
            y0,y1=1-2*top/height,1-2*(top+size)/height
            gl.glBegin(gl.GL_QUADS)
            for u,v,xx,yy in ((0,1,x0,y0),(1,1,x1,y0),(1,0,x1,y1),(0,0,x0,y1)):
                gl.glTexCoord2f(u,v); gl.glVertex2f(xx,yy)
            gl.glEnd()
        if overlay is not None:
            overlay.note_sprites(len(sprites), boxes)

    def render(self, view, game, width, height, origin, forward, right, up, direct=False):
        gl=self.gl
        world=game.world
        p=game.player
        radius=min(32,int(view.draw_distance))+1
        ox,oy,oz=math.floor(origin[0])-radius,math.floor(origin[1])-radius,p.world_z-2
        dims=(2*radius+1,2*radius+1,5)
        region=(id(world),ox,oy,oz,dims)
        if region!=self.region:
            self.chunk_cache={}
            self.region=region
        chunks={}
        # Snapshot live levels before ray-volume loading evicts chunks from
        # the world's five-entry LRU. Otherwise the same frame can reload a
        # neighbour with a fresh ambient-only grid and render a dark seam.
        live=dict(world.chunks) if world else {}
        if world:
            live.update(getattr(world,'_lighting_levels',{}))
        if world and hasattr(world,'_light_fields'):
            for lv,x,y in world._light_fields[0].values():
                live.setdefault((lv.chunk_x,lv.chunk_y,lv.world_z),lv)
        for z in range(oz,oz+5):
            if world and not world.exists(z): continue
            if not world and z!=0: continue
            for cy in range(oy//game.level.h,(oy+dims[1]-1)//game.level.h+1):
                for cx in range(ox//game.level.w,(ox+dims[0]-1)//game.level.w+1):
                    if world:
                        key=cx,cy,z
                        lv=live.get(key) or self.chunk_cache.get(key)
                        if lv is None:
                            lv=world.chunk(*key)
                        chunks[key]=lv
                        self.chunk_cache[key]=lv
                    elif cx==0 and cy==0: chunks[cx,cy,z]=game.level
        grids = {key: lv.visual_manager.grid() for key, lv in chunks.items()}
        key=(ox,oy,oz,dims,round(game.lamp_flicker_modifier*32),
             tuple((k,id(lv),lv.geometry_revision,lv.visual_manager.geometry_revision,tuple((f.kind,f.x,f.y,f.rotated) for f in lv.furniture),lv.lighting_revision,tuple(lv.light_sources),tuple(r.lit for r in lv.rooms),
                    tuple(sorted((pos,tuple(sorted(d.items()))) for pos,d in lv.doors.items()))) for k,lv in chunks.items()))
        if key!=self.key:
            tiles=array('f'); colors=array('f')
            for z in range(oz,oz+5):
                for y in range(oy,oy+dims[1]):
                    for x in range(ox,ox+dims[0]):
                        cx,lx=divmod(x,game.level.w); cy,ly=divmod(y,game.level.h)
                        lv=chunks.get((cx,cy,z))
                        if lv is None:
                            tiles.append(-1); colors.extend((0,0,0,0)); continue
                        grid = grids[cx, cy, z]
                        index = ly*lv.w+lx
                        tile = grid.tiles[index]
                        tiles.append(0 if grid.walls[index] else tile)
                        _,base=game.tile_glyph(lv,tile,lx,ly,0,False)
                        light=lv.light_grid[lx][ly]
                        colors.extend((*[c/255 for c in base],light))
            for tex,data,internal,fmt in ((self.textures[0],tiles,gl.GL_R32F,gl.GL_RED),(self.textures[1],colors,gl.GL_RGBA32F,gl.GL_RGBA)):
                gl.glBindTexture(gl.GL_TEXTURE_3D,tex)
                gl.glTexImage3D(gl.GL_TEXTURE_3D,0,internal,*dims,0,fmt,gl.GL_FLOAT,data.tobytes())
                gl.glTexParameteri(gl.GL_TEXTURE_3D,gl.GL_TEXTURE_MIN_FILTER,gl.GL_NEAREST)
                gl.glTexParameteri(gl.GL_TEXTURE_3D,gl.GL_TEXTURE_MAG_FILTER,gl.GL_NEAREST)
            self.key=key
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER,self.fbo)
        if self.size!=(width,height):
            for i,tex in enumerate(self.textures[2:]):
                gl.glBindTexture(gl.GL_TEXTURE_2D,tex)
                gl.glTexImage2D(gl.GL_TEXTURE_2D,0,gl.GL_RGBA32F if i else gl.GL_RGBA8,width,height,0,gl.GL_RGBA,gl.GL_FLOAT,None)
                gl.glTexParameteri(gl.GL_TEXTURE_2D,gl.GL_TEXTURE_MIN_FILTER,gl.GL_NEAREST)
                gl.glTexParameteri(gl.GL_TEXTURE_2D,gl.GL_TEXTURE_MAG_FILTER,gl.GL_NEAREST)
                gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER,gl.GL_COLOR_ATTACHMENT0+i,gl.GL_TEXTURE_2D,tex,0)
            self.size=width,height
        gl.glDrawBuffers(2,(ctypes.c_uint*2)(gl.GL_COLOR_ATTACHMENT0,gl.GL_COLOR_ATTACHMENT1))
        if gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER)!=gl.GL_FRAMEBUFFER_COMPLETE: raise RuntimeError('GPU framebuffer incomplete')
        gl.glViewport(0,0,width,height)
        gl.glUseProgram(self.program)
        def loc(name): return gl.glGetUniformLocation(self.program,name)
        profile=getattr(game.level,'profile',{})
        gl.glUniform3f(loc('floor_color'),*(c/255 for c in profile.get('floor_color',(118,104,62))))
        gl.glUniform3f(loc('ceiling_color'),*(c/255 for c in profile.get('ceiling_color',(150,147,120))))
        # Material layers come from the level profile; defaults match Level 0.
        from . import textures
        gl.glUniform1i(loc('wall_layer'), textures.layer_index(profile.get('wall_texture','wallpaper')))
        gl.glUniform1i(loc('floor_layer'), textures.layer_index(profile.get('floor_texture','carpet')))
        gl.glUniform1i(loc('ceiling_layer'), textures.layer_index(profile.get('ceiling_texture','ceiling')))
        gl.glUniform1i(loc('flat_light'), 1 if profile.get('flat_lighting') else 0)
        gl.glUniform1i(loc('wet_floor'), 1 if profile.get('wet_floor') else 0)
        # Post-processing mirrors PostFX: vignette + grain only when the
        # level opts in, so the GPU path matches the CPU look.
        effects = set(profile.get('postfx') or ())
        gl.glUniform1f(loc('vignette_strength'), 1.0 if 'vignette' in effects else 0.0)
        gl.glUniform1f(loc('grain_strength'), 1.0 if 'grain' in effects else 0.0)
        gl.glUniform1f(loc('grain_seed'), (game.clock.get_time() % 997) / 997.0)
        for name,values in (('origin',origin),('offset',(ox,oy,oz)),('forward_dir',forward),('right_dir',right),('up_dir',up),('sky',tuple(c/255 for c in view.skybox))):
            gl.glUniform3f(loc(name),*values)
        gl.glUniform3i(loc('dimensions'),*dims)
        gl.glUniform2f(loc('resolution'),width,height)
        gl.glUniform1f(loc('focal'),width/(2*0.66))
        gl.glUniform1f(loc('max_distance'),min(32,view.draw_distance))
        # light_grid already includes lamp flicker. Applying it again also
        # incorrectly dims the player's lantern and ambient light.
        gl.glUniform1f(loc('flicker'),1.0)
        for name,value in (('ceiling',view.show_ceiling),('lighting',view.lighting),('fog',view.fog)):
            gl.glUniform1i(loc(name),value)
        for i,name in enumerate(('terrain','materials')):
            gl.glActiveTexture(gl.GL_TEXTURE0+i); gl.glBindTexture(gl.GL_TEXTURE_3D,self.textures[i]); gl.glUniform1i(loc(name),i)
        gl.glActiveTexture(gl.GL_TEXTURE2)
        gl.glBindTexture(gl.GL_TEXTURE_2D_ARRAY,self.atlas_texture)
        gl.glUniform1i(loc('atlas'),2)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBegin(gl.GL_QUADS)
        for x,y in ((-1,-1),(1,-1),(1,1),(-1,1)): gl.glVertex2f(x,y)
        gl.glEnd()
        if direct:
            self.draw_sprites(view,game,width,height,forward,right,up)
            gl.glUseProgram(0); gl.glActiveTexture(gl.GL_TEXTURE0); gl.glBindFramebuffer(gl.GL_FRAMEBUFFER,0)
            return self.textures[2]
        gl.glReadBuffer(gl.GL_COLOR_ATTACHMENT0)
        raw=gl.glReadPixels(0,0,width,height,gl.GL_RGBA,gl.GL_UNSIGNED_BYTE)
        image=pygame.image.frombytes(bytes(raw),(width,height),'RGBA',True)
        gl.glReadBuffer(gl.GL_COLOR_ATTACHMENT1)
        raw=bytes(gl.glReadPixels(0,0,width,height,gl.GL_RGBA,gl.GL_FLOAT))
        values=list(struct.iter_unpack('ffff',raw))
        depths=[]; hits=[]
        bx=p.chunk_x*game.level.w if world else 0
        by=p.chunk_y*game.level.h if world else 0
        for y in range(height-1,-1,-1):
            for d,x,yy,z in values[y*width:(y+1)*width]:
                depths.append(d)
                hits.append((round(x)-bx,round(yy)-by) if d<1e5 and round(z)==p.world_z else None)
        gl.glUseProgram(0); gl.glActiveTexture(gl.GL_TEXTURE0); gl.glBindFramebuffer(gl.GL_FRAMEBUFFER,0)
        return image,depths,hits
