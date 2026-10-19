"""Native Tk/OpenGL renderer for the JARVIS core, with no browser process."""
from __future__ import annotations

import ctypes
import io
import math
import sys
import time

import numpy as np
from OpenGL import GL as gl
from OpenGL import GLU
from OpenGL.GL.shaders import compileProgram, compileShader
from PIL import Image
from pyopengltk import OpenGLFrame

from jarvis.ui.glb_asset import load_model


VERTEX = """#version 120
varying vec3 normalV; varying vec3 positionV; varying vec2 uv;
void main(){
    vec4 p=gl_ModelViewMatrix*gl_Vertex;
    positionV=p.xyz; normalV=normalize(gl_NormalMatrix*gl_Normal);
    uv=gl_MultiTexCoord0.xy; gl_Position=gl_ProjectionMatrix*p;
}
"""
FRAGMENT = """#version 120
varying vec3 normalV; varying vec3 positionV; varying vec2 uv;
uniform vec4 baseColor; uniform vec3 emission;
uniform float metal; uniform float rough; uniform float strength;
uniform float pulse; uniform int textured;
uniform sampler2D baseMap; uniform sampler2D emissionMap;
void main(){
    vec3 n=normalize(normalV), v=normalize(-positionV);
    vec3 light=normalize(vec3(-.5,.8,1.2));
    vec3 fill=normalize(vec3(1.,.2,-.4));
    vec3 albedo=baseColor.rgb;
    vec3 glow=emission;
    if(textured==1){
        albedo*=pow(texture2D(baseMap,uv).rgb,vec3(2.2));
        glow*=pow(texture2D(emissionMap,uv).rgb,vec3(2.2));
    }
    float diffuse=max(dot(n,light),0.);
    float edge=pow(1.-max(dot(n,v),0.),3.);
    float spec=pow(max(dot(n,normalize(light+v)),0.),mix(100.,12.,rough));
    float second=pow(max(dot(n,normalize(fill+v)),0.),24.);
    vec3 f0=mix(vec3(.045),albedo,metal);
    vec3 color=albedo*(.28+diffuse*1.7)*(1.-metal*.6);
    color+=f0*(spec*4.+second*1.5+edge*.65);
    if(textured==1) color+=vec3(.005,.08,.14)*edge;
    gl_FragColor=vec4(color+glow*strength*pulse,baseColor.a);
}
"""
QUAD_VERTEX = """#version 120
varying vec2 uv;
void main(){uv=gl_MultiTexCoord0.xy; gl_Position=gl_Vertex;}
"""
POST_FRAGMENT = """#version 120
varying vec2 uv;
uniform sampler2D sceneMap; uniform vec2 pixel;
uniform float hudTime; uniform vec3 hudColor;
vec3 bright(vec2 p){return max(texture2D(sceneMap,p).rgb-vec3(.8),vec3(0.));}
void main(){
    vec3 c=texture2D(sceneMap,uv).rgb, glow=vec3(0.);
    for(int i=0;i<12;i++){
        float a=float(i)*.5235987756; vec2 d=vec2(cos(a),sin(a))*pixel;
        glow+=bright(uv+d*4.5)+bright(uv+d*9.)*.6;
    }
    c+=glow*(.65/19.2);
    c=clamp((c*(2.51*c+.03))/(c*(2.43*c+.59)+.14),0.,1.);
    // Analytic background HUD: no new geometry or CPU particle allocations.
    float background=1.-smoothstep(.025,.18,max(c.r,max(c.g,c.b)));
    vec2 p=uv-.5;
    vec2 grid=abs(fract(uv*vec2(32.,22.))-.5);
    float fine=(1.-smoothstep(.005,.025,min(grid.x,grid.y)))*.035;
    vec2 cell=floor((uv+vec2(hudTime*.003,0.))*vec2(55.,32.));
    vec2 dotPos=fract((uv+vec2(hudTime*.003,0.))*vec2(55.,32.))-.5;
    float seed=fract(sin(dot(cell,vec2(127.1,311.7)))*43758.5453);
    float star=(1.-smoothstep(.02,.09,length(dotPos)))*step(.91,seed)*(.25+.2*sin(hudTime*2.+seed*35.));
    float radius=length(p*vec2(1.35,1.));
    float ring=(1.-smoothstep(.001,.004,abs(radius-.43)))*(.2+.8*step(.65,fract(atan(p.y,p.x)*8.+hudTime*.15)))*.13;
    float sweep=exp(-abs(uv.y-fract(hudTime*.035))*180.)*.04;
    c+=hudColor*(fine+star+ring+sweep)*background;
    gl_FragColor=vec4(pow(c,vec3(1./2.2)),1.);
}
"""


class CoreViewport(OpenGLFrame):
    def __init__(self, parent, on_error):
        self.on_error = on_error
        self.ready = False
        self.closed = False
        self.mode = "idle"
        self.motion_enabled = True
        self.renderer_info = ""
        self.frame_count = 0
        self.meshes = []
        self.textures = []
        self.fbo = self.color_buffer = self.depth_buffer = 0
        self.target_size = (0, 0)
        self.program = self.post = 0
        self._context = self._dc = None
        self.yaw, self.pitch, self.distance = .24, .08, 8.0
        self.elapsed = self.spin = 0.
        self.speed = 1.
        self.last_frame = time.perf_counter()
        self.drag = None
        super().__init__(parent, width=400, height=250, highlightthickness=0)
        self.animate = 33
        self.bind("<ButtonPress-1>", self._start_drag)
        self.bind("<B1-Motion>", self._drag)
        self.bind("<MouseWheel>", self._zoom)
        self.bind("<Double-Button-1>", self._reset_view)

    def tkMap(self, event):
        try:
            super().tkMap(event)
        except Exception as error:
            self._fail(error)

    def tkResize(self, event):
        self.width, self.height = max(event.width, 1), max(event.height, 1)

    def _display(self):
        if self.closed or not self.winfo_exists():
            return
        if not self.ready:
            return
        try:
            super()._display()
        except Exception as error:
            self._fail(error)

    def _fail(self, error):
        self.animate = 0
        self.after_idle(self.on_error, error)

    def initgl(self):
        if self.ready:
            return
        if sys.platform == "win32":
            from OpenGL import WGL
            self._context, self._dc = WGL.wglGetCurrentContext(), WGL.wglGetCurrentDC()
        version = gl.glGetString(gl.GL_VERSION)
        renderer = gl.glGetString(gl.GL_RENDERER)
        self.renderer_info = f"{renderer.decode()} / OpenGL {version.decode()}"
        self.program = compileProgram(compileShader(VERTEX, gl.GL_VERTEX_SHADER), compileShader(FRAGMENT, gl.GL_FRAGMENT_SHADER))
        self.post = compileProgram(compileShader(QUAD_VERTEX, gl.GL_VERTEX_SHADER), compileShader(POST_FRAGMENT, gl.GL_FRAGMENT_SHADER))
        self.uniforms = {name:gl.glGetUniformLocation(self.program, name) for name in
                         ("baseColor", "emission", "metal", "rough", "strength", "pulse", "textured", "baseMap", "emissionMap")}
        self.post_uniforms = {name:gl.glGetUniformLocation(self.post, name) for name in ("sceneMap", "pixel", "hudTime", "hudColor")}
        model = load_model()
        for encoded in model.images:
            pixels = np.asarray(Image.open(io.BytesIO(encoded)).convert("RGBA"))
            texture = int(gl.glGenTextures(1)); self.textures.append(texture)
            gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
            gl.glTexImage2D(gl.GL_TEXTURE_2D,0,gl.GL_RGBA,pixels.shape[1],pixels.shape[0],0,gl.GL_RGBA,gl.GL_UNSIGNED_BYTE,pixels)
            gl.glGenerateMipmap(gl.GL_TEXTURE_2D)
            gl.glTexParameteri(gl.GL_TEXTURE_2D,gl.GL_TEXTURE_MIN_FILTER,gl.GL_LINEAR_MIPMAP_LINEAR)
            gl.glTexParameteri(gl.GL_TEXTURE_2D,gl.GL_TEXTURE_MAG_FILTER,gl.GL_LINEAR)
            gl.glTexParameteri(gl.GL_TEXTURE_2D,gl.GL_TEXTURE_WRAP_S,gl.GL_REPEAT)
            gl.glTexParameteri(gl.GL_TEXTURE_2D,gl.GL_TEXTURE_WRAP_T,gl.GL_CLAMP_TO_EDGE)
        for primitive in model.primitives:
            vbo, ebo = map(int, gl.glGenBuffers(2))
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER,vbo)
            gl.glBufferData(gl.GL_ARRAY_BUFFER,primitive.vertices.nbytes,primitive.vertices,gl.GL_STATIC_DRAW)
            gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER,ebo)
            gl.glBufferData(gl.GL_ELEMENT_ARRAY_BUFFER,primitive.indices.nbytes,primitive.indices,gl.GL_STATIC_DRAW)
            material = primitive.material
            pbr = material.get("pbrMetallicRoughness", {})
            base_tex = pbr.get("baseColorTexture", {}).get("index")
            emit_tex = material.get("emissiveTexture", {}).get("index")
            self.meshes.append({"group":primitive.group,"vbo":vbo,"ebo":ebo,"count":len(primitive.indices),
                                "material":material,"pbr":pbr,
                                "base_texture":self.textures[model.textures[base_tex]] if base_tex is not None else 0,
                                "emission_texture":self.textures[model.textures[emit_tex]] if emit_tex is not None else 0})
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER,0); gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER,0)
        gl.glEnable(gl.GL_DEPTH_TEST); gl.glDepthFunc(gl.GL_LEQUAL)
        self.ready = True
        self.last_frame = time.perf_counter()

    def _resize_target(self, width, height):
        if (width, height) == self.target_size:
            return
        if not self.fbo:
            self.fbo = int(gl.glGenFramebuffers(1))
            self.color_buffer = int(gl.glGenTextures(1))
            self.depth_buffer = int(gl.glGenRenderbuffers(1))
        gl.glBindTexture(gl.GL_TEXTURE_2D,self.color_buffer)
        gl.glTexImage2D(gl.GL_TEXTURE_2D,0,gl.GL_RGBA16F,width,height,0,gl.GL_RGBA,gl.GL_FLOAT,None)
        for axis in (gl.GL_TEXTURE_WRAP_S,gl.GL_TEXTURE_WRAP_T):
            gl.glTexParameteri(gl.GL_TEXTURE_2D,axis,gl.GL_CLAMP_TO_EDGE)
        for direction in (gl.GL_TEXTURE_MIN_FILTER,gl.GL_TEXTURE_MAG_FILTER):
            gl.glTexParameteri(gl.GL_TEXTURE_2D,direction,gl.GL_LINEAR)
        gl.glBindRenderbuffer(gl.GL_RENDERBUFFER,self.depth_buffer)
        gl.glRenderbufferStorage(gl.GL_RENDERBUFFER,gl.GL_DEPTH_COMPONENT24,width,height)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER,self.fbo)
        gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER,gl.GL_COLOR_ATTACHMENT0,gl.GL_TEXTURE_2D,self.color_buffer,0)
        gl.glFramebufferRenderbuffer(gl.GL_FRAMEBUFFER,gl.GL_DEPTH_ATTACHMENT,gl.GL_RENDERBUFFER,self.depth_buffer)
        if gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER) != gl.GL_FRAMEBUFFER_COMPLETE:
            raise RuntimeError("3D render bufferini yaratib bo'lmadi.")
        self.target_size = (width,height)

    def redraw(self):
        if self.closed or not self.ready:
            return
        if not self.winfo_viewable():
            self.animate = 150
            self.last_frame = time.perf_counter()
            return
        self.animate = 33 if self.motion_enabled else 150
        now=time.perf_counter(); delta=min(now-self.last_frame,.1); self.last_frame=now
        if not self.motion_enabled:
            delta=0.
        self.elapsed+=delta
        target={"idle":1.,"listening":1.2,"thinking":3.5,"speaking":1.65}.get(self.mode,1.)
        self.speed+=(target-self.speed)*min(1.,delta*3)
        self.spin+=delta*self.speed
        width,height=max(self.winfo_width(),1),max(self.winfo_height(),1)
        # Render above display resolution to smooth rings and fine circuitry.
        sampling=min(1.5,math.sqrt(1_200_000/max(width*height,1)))
        render_width,render_height=max(1,round(width*sampling)),max(1,round(height*sampling))
        self._resize_target(render_width,render_height)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER,self.fbo)
        gl.glViewport(0,0,render_width,render_height)
        gl.glClearColor(.002,.008,.021,1.)
        gl.glDepthMask(True); gl.glClear(gl.GL_COLOR_BUFFER_BIT|gl.GL_DEPTH_BUFFER_BIT)
        gl.glEnable(gl.GL_DEPTH_TEST); gl.glEnable(gl.GL_CULL_FACE)
        gl.glMatrixMode(gl.GL_PROJECTION); gl.glLoadIdentity()
        GLU.gluPerspective(35.,width/height,.1,50.)
        gl.glMatrixMode(gl.GL_MODELVIEW); gl.glLoadIdentity()
        GLU.gluLookAt(self.distance*math.sin(self.yaw)*math.cos(self.pitch),self.distance*math.sin(self.pitch),
                      self.distance*math.cos(self.yaw)*math.cos(self.pitch),0,0,0,0,1,0)
        gl.glUseProgram(self.program)
        gl.glUniform1i(self.uniforms["baseMap"],0); gl.glUniform1i(self.uniforms["emissionMap"],1)
        gl.glEnableClientState(gl.GL_VERTEX_ARRAY); gl.glEnableClientState(gl.GL_NORMAL_ARRAY)
        gl.glClientActiveTexture(gl.GL_TEXTURE0); gl.glEnableClientState(gl.GL_TEXTURE_COORD_ARRAY)
        pulse=self._pulse()
        # Transparent shell is drawn after all opaque geometry.
        for mesh in self.meshes:
            self._draw_mesh(mesh,pulse)
        gl.glDisableClientState(gl.GL_VERTEX_ARRAY); gl.glDisableClientState(gl.GL_NORMAL_ARRAY)
        gl.glDisableClientState(gl.GL_TEXTURE_COORD_ARRAY)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER,0); gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER,0)
        gl.glActiveTexture(gl.GL_TEXTURE1); gl.glBindTexture(gl.GL_TEXTURE_2D,0)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glDepthMask(True); gl.glDisable(gl.GL_BLEND); gl.glDisable(gl.GL_CULL_FACE); gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER,0)
        gl.glViewport(0,0,width,height)
        gl.glUseProgram(self.post)
        gl.glBindTexture(gl.GL_TEXTURE_2D,self.color_buffer)
        gl.glUniform1i(self.post_uniforms["sceneMap"],0)
        gl.glUniform2f(self.post_uniforms["pixel"],1/width,1/height)
        gl.glUniform1f(self.post_uniforms['hudTime'], self.elapsed)
        color = {'thinking': (1.,.58,.1), 'speaking': (.1,1.,.65)}.get(self.mode, (.1,.75,1.))
        gl.glUniform3f(self.post_uniforms['hudColor'], *color)
        gl.glBegin(gl.GL_QUADS)
        for u,v,x,y in ((0,0,-1,-1),(1,0,1,-1),(1,1,1,1),(0,1,-1,1)):
            gl.glTexCoord2f(u,v); gl.glVertex2f(x,y)
        gl.glEnd(); gl.glUseProgram(0)
        self.frame_count+=1

    def _pulse(self):
        t=self.elapsed
        if self.mode=="speaking": return .5+.26*math.sin(t*13)+.18*math.sin(t*21)
        return .5+.5*math.sin(t*({"idle":1.8,"listening":4.5,"thinking":7}.get(self.mode,1.8)))

    def _draw_mesh(self,mesh,pulse):
        material,pbr=mesh["material"],mesh["pbr"]
        gl.glPushMatrix()
        group=mesh["group"]
        if group=="OuterRing":
            gl.glRotatef(math.sin(self.elapsed*.23)*3.,1,0,0)
            gl.glRotatef(self.spin*3.15,0,0,1)
        elif group=="InnerRing":
            gl.glRotatef(math.sin(self.elapsed*.33)*15.,0,1,0)
            gl.glRotatef(-self.spin*4.,0,0,1)
        elif group in {"Core","GlassShell"}:
            gl.glRotatef(self.spin*6.3,0,1,0)
            scale=1.+pulse*(.004 if self.mode=="idle" else .015)
            gl.glScalef(scale,scale,scale)
        alpha=material.get("alphaMode")=="BLEND"
        if alpha:
            gl.glEnable(gl.GL_BLEND); gl.glBlendFunc(gl.GL_SRC_ALPHA,gl.GL_ONE_MINUS_SRC_ALPHA)
            gl.glDepthMask(False)
        else:
            gl.glDisable(gl.GL_BLEND); gl.glDepthMask(True)
        strength=material.get("extensions",{}).get("KHR_materials_emissive_strength",{}).get("emissiveStrength",1.)
        gl.glUniform4f(self.uniforms["baseColor"],*pbr.get("baseColorFactor",[1,1,1,1]))
        gl.glUniform3f(self.uniforms["emission"],*material.get("emissiveFactor",[0,0,0]))
        gl.glUniform1f(self.uniforms["metal"],pbr.get("metallicFactor",1.))
        gl.glUniform1f(self.uniforms["rough"],pbr.get("roughnessFactor",1.))
        gl.glUniform1f(self.uniforms["strength"],strength)
        gl.glUniform1f(self.uniforms["pulse"],.88+pulse*(.14 if self.mode=="idle" else .65))
        gl.glUniform1i(self.uniforms["textured"],int(bool(mesh["base_texture"])))
        gl.glActiveTexture(gl.GL_TEXTURE0); gl.glBindTexture(gl.GL_TEXTURE_2D,mesh["base_texture"])
        gl.glActiveTexture(gl.GL_TEXTURE1); gl.glBindTexture(gl.GL_TEXTURE_2D,mesh["emission_texture"])
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER,mesh["vbo"])
        gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER,mesh["ebo"])
        gl.glVertexPointer(3,gl.GL_FLOAT,32,ctypes.c_void_p(0))
        gl.glNormalPointer(gl.GL_FLOAT,32,ctypes.c_void_p(12))
        gl.glTexCoordPointer(2,gl.GL_FLOAT,32,ctypes.c_void_p(24))
        gl.glDrawElements(gl.GL_TRIANGLES,mesh["count"],gl.GL_UNSIGNED_INT,ctypes.c_void_p(0))
        gl.glPopMatrix()

    def _start_drag(self,event):
        self.drag=(event.x,event.y)

    def _drag(self,event):
        if self.drag:
            self.yaw-=(event.x-self.drag[0])*.009
            self.pitch=max(-.8,min(.8,self.pitch+(event.y-self.drag[1])*.008))
        self.drag=(event.x,event.y)

    def _zoom(self,event):
        self.distance=max(5.1,min(12.,self.distance-event.delta/120*.4))

    def _reset_view(self,_event=None):
        self.yaw,self.pitch,self.distance=.24,.08,8.

    def capture(self,path):
        """Capture only the OpenGL model area for visual verification."""
        self.tkMakeCurrent()
        self.redraw()
        gl.glReadBuffer(gl.GL_BACK)
        width,height=max(self.winfo_width(),1),max(self.winfo_height(),1)
        pixels=gl.glReadPixels(0,0,width,height,gl.GL_RGBA,gl.GL_UNSIGNED_BYTE)
        Image.frombytes("RGBA",(width,height),pixels).transpose(Image.Transpose.FLIP_TOP_BOTTOM).save(path)

    def destroy(self):
        if self.closed:
            return
        self.closed=True; self.animate=0
        if self.cb:
            self.after_cancel(self.cb); self.cb=None
        try:
            if self._context or self.ready:
                self.tkMakeCurrent()
                buffers=[value for mesh in self.meshes for value in (mesh["vbo"],mesh["ebo"])]
                if buffers: gl.glDeleteBuffers(len(buffers),buffers)
                if self.textures: gl.glDeleteTextures(self.textures)
                if self.color_buffer: gl.glDeleteTextures([self.color_buffer])
                if self.fbo: gl.glDeleteFramebuffers(1,[self.fbo])
                if self.depth_buffer: gl.glDeleteRenderbuffers(1,[self.depth_buffer])
                if self.program: gl.glDeleteProgram(self.program)
                if self.post: gl.glDeleteProgram(self.post)
                if sys.platform=="win32" and self._context:
                    from OpenGL import WGL
                    WGL.wglMakeCurrent(0,0); WGL.wglDeleteContext(self._context)
                    release=ctypes.windll.user32.ReleaseDC
                    release.argtypes=[ctypes.c_void_p,ctypes.c_void_p]
                    release.restype=ctypes.c_int
                    release(self.winfo_id(),self._dc)
        finally:
            self.ready=False
            super().destroy()
