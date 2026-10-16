"""Rebuild the supplied JARVIS reference as an original, editable glTF asset.

Run with the optional asset dependencies: python scripts/build_jarvis_core.py
Geometry is procedural; the reference screenshots are not baked onto the model.
glTF coordinates: Y up, front facing +Z, all animation pivots at the origin.
"""
from __future__ import annotations

import io
import json
import math
import random
import struct
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "3d"
TAU = math.tau


class Geometry:
    def __init__(self):
        self.parts = defaultdict(lambda: {"p": [], "n": [], "uv": [], "i": []})

    def add(self, group, material, points, triangles, normals=None, uv=None):
        points = np.asarray(points, dtype=np.float64)
        triangles = np.asarray(triangles, dtype=np.int32).reshape(-1, 3)
        if normals is None:
            # Duplicate vertices for hard mechanical edges.
            points = points[triangles].reshape(-1, 3)
            face = points.reshape(-1, 3, 3)
            n = np.cross(face[:, 1] - face[:, 0], face[:, 2] - face[:, 0])
            n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
            normals = np.repeat(n, 3, axis=0)
            triangles = np.arange(len(points)).reshape(-1, 3)
        bucket = self.parts[group, material]
        offset = len(bucket["p"])
        bucket["p"].extend(points.tolist())
        bucket["n"].extend(np.asarray(normals).tolist())
        bucket["uv"].extend(np.zeros((len(points), 2)).tolist() if uv is None else np.asarray(uv).tolist())
        bucket["i"].extend((triangles + offset).reshape(-1).tolist())

    def face(self, group, material, points, hint):
        points = np.asarray(points, dtype=float)
        normal = np.cross(points[1] - points[0], points[2] - points[0])
        if np.dot(normal, hint) < 0:
            points = points[::-1]
        self.add(group, material, points, [(0, i, i + 1) for i in range(1, len(points) - 1)])

    def arc(self, group, material, radius, width, depth, start=0, stop=TAU,
            z=0, steps=None, bevel=0.008):
        ri, ro, h = radius - width / 2, radius + width / 2, depth / 2
        b = min(bevel, width / 3, depth / 3)
        cross = [(ri + b, -h), (ro - b, -h), (ro, -h + b), (ro, h - b),
                 (ro - b, h), (ri + b, h), (ri, h - b), (ri, -h + b)]
        if depth < .012:
            cross = [(ri, -h), (ro, -h), (ro, h), (ri, h)]
        steps = steps or max(2, round((stop - start) * radius * 16))
        def point(angle, rz):
            return [rz[0] * math.cos(angle), rz[0] * math.sin(angle), rz[1] + z]
        for a0, a1 in zip(np.linspace(start, stop, steps + 1)[:-1], np.linspace(start, stop, steps + 1)[1:]):
            mid = (a0 + a1) / 2
            for i, c0 in enumerate(cross):
                c1 = cross[(i + 1) % len(cross)]
                nr = (c0[0] + c1[0]) / 2 - radius
                nz = (c0[1] + c1[1]) / 2
                self.face(group, material, [point(a0, c0), point(a1, c0), point(a1, c1), point(a0, c1)],
                          [nr * math.cos(mid), nr * math.sin(mid), nz])
        if stop - start < TAU - 1e-5:
            self.face(group, material, [point(start, c) for c in cross], [math.sin(start), -math.cos(start), 0])
            self.face(group, material, [point(stop, c) for c in cross], [-math.sin(stop), math.cos(stop), 0])

    def halo(self, group, material, radius, width, z, steps=64):
        for a0, a1 in zip(np.linspace(0, TAU, steps + 1)[:-1], np.linspace(0, TAU, steps + 1)[1:]):
            points = [[r*math.cos(a), r*math.sin(a), z]
                      for r, a in ((radius-width/2,a0),(radius+width/2,a0),(radius+width/2,a1),(radius-width/2,a1))]
            self.face(group, material, points, [0, 0, 1 if z>0 else -1])

    def box(self, group, material, center, size, angle=0, bevel=0.012):
        half = np.asarray(size) / 2
        b = min(bevel, min(half) * 0.5)
        rotation = np.array([[math.cos(angle), -math.sin(angle), 0],
                             [math.sin(angle), math.cos(angle), 0], [0, 0, 1]])
        def emit(vertices, hint):
            self.face(group, material, np.asarray(vertices) @ rotation.T + center, rotation @ hint)
        for axis in range(3):
            j, k = [i for i in range(3) if i != axis]
            for sign in (-1, 1):
                vertices = []
                for sj, sk in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                    p = np.zeros(3)
                    p[axis], p[j], p[k] = sign * half[axis], sj * (half[j] - b), sk * (half[k] - b)
                    vertices.append(p)
                hint = np.zeros(3); hint[axis] = sign
                emit(vertices, hint)
        for i, j in ((0, 1), (0, 2), (1, 2)):
            k = 3 - i - j
            for si in (-1, 1):
                for sj in (-1, 1):
                    vertices = []
                    for edge, sk in ((0, -1), (1, -1), (1, 1), (0, 1)):
                        p = np.zeros(3)
                        p[i] = si * (half[i] - (b if edge else 0))
                        p[j] = sj * (half[j] - (0 if edge else b))
                        p[k] = sk * (half[k] - b)
                        vertices.append(p)
                    hint = np.zeros(3); hint[i], hint[j] = si, sj
                    emit(vertices, hint)
        for sx in (-1, 1):
            for sy in (-1, 1):
                for sz in (-1, 1):
                    signs = np.array([sx, sy, sz])
                    vertices = []
                    for axis in range(3):
                        p = signs * (half - b); p[axis] = signs[axis] * half[axis]
                        vertices.append(p)
                    emit(vertices, signs)

    def sphere(self, group, material, radius, center=(0, 0, 0), rings=36, sides=72):
        p, n, uv, faces = [], [], [], []
        for j in range(rings + 1):
            phi = math.pi * j / rings
            for i in range(sides + 1):
                theta = TAU * i / sides
                normal = np.array([math.sin(phi) * math.sin(theta), math.cos(phi), math.sin(phi) * math.cos(theta)])
                p.append(normal * radius + center); n.append(normal); uv.append([i / sides, j / rings])
        for j in range(rings):
            for i in range(sides):
                a = j * (sides + 1) + i; b = a + sides + 1
                if j:
                    faces.append((a, a + 1, b))
                if j < rings - 1:
                    faces.append((a + 1, b + 1, b))
        # Ensure outward winding independent of the chosen spherical coordinates.
        faces = np.asarray(faces)
        points = np.asarray(p)
        f = points[faces]
        orient = np.einsum("ij,ij->i", np.cross(f[:, 1] - f[:, 0], f[:, 2] - f[:, 0]), np.mean(f, axis=1) - center)
        faces[orient < 0] = faces[orient < 0][:, ::-1]
        self.add(group, material, p, faces, n, uv)

    def tube(self, group, material, path, radius=0.003, sides=5):
        path = np.asarray(path)
        p, n, faces = [], [], []
        for i, point in enumerate(path):
            tangent = path[min(i + 1, len(path) - 1)] - path[max(0, i - 1)]
            tangent /= np.linalg.norm(tangent)
            radial = point / np.linalg.norm(point)
            side = np.cross(tangent, radial); side /= np.linalg.norm(side)
            other = np.cross(side, tangent)
            for j in range(sides):
                normal = math.cos(TAU * j / sides) * side + math.sin(TAU * j / sides) * other
                p.append(point + radius * normal); n.append(normal)
            if i:
                for j in range(sides):
                    a = (i - 1) * sides + j; b = (i - 1) * sides + (j + 1) % sides
                    c = i * sides + (j + 1) % sides; d = i * sides + j
                    faces.extend([(a, b, c), (a, c, d)])
        # Tubes use radial normals for a smooth subpixel highlight.
        self.add(group, material, p, faces, n)


def circuit_textures():
    rng = random.Random(23081)
    w, h = 2048, 1024
    small_noise = np.random.default_rng(42).normal(0, 1.6, (128, 256)).astype(np.float32)
    noise = np.array(Image.fromarray(small_noise).resize((w, h), Image.Resampling.BILINEAR))
    base = np.empty((h, w, 3), dtype=np.uint8)
    for channel, level in enumerate((5, 22, 36)):
        base[:, :, channel] = np.clip(level + noise * (channel + 1), 0, 255)
    lines = Image.new("RGB", (w, h), (0, 0, 0)); draw = ImageDraw.Draw(lines)
    for x in range(0, w, 64):
        draw.line((x, 0, x, h), fill=(1, 28, 44), width=1)
    for y in range(0, h, 64):
        draw.line((0, y, w, y), fill=(1, 36, 56), width=1)
    for _ in range(430):
        x, y = rng.randrange(w), rng.randrange(36, h - 36)
        path = [(x, y)]
        for step in range(rng.randrange(2, 6)):
            if step % 2:
                y = max(20, min(h - 20, y + rng.choice((-1, 1)) * rng.randrange(8, 55)))
            else:
                x += rng.choice((-1, 1)) * rng.randrange(12, 120)
            path.append((x, y))
        brightness = rng.uniform(.25, 1)
        color = tuple(round(v * brightness) for v in (22, 148, 192))
        draw.line(path, fill=color, width=rng.choice((1, 1, 2, 3)))
        if rng.random() < .5:
            r = rng.choice((1, 2, 3)); draw.ellipse((x-r, y-r, x+r, y+r), fill=(75, 205, 240))
    for y in (256, 512, 768):
        draw.line((0, y, w, y), fill=(12, 120, 168), width=2)
        for x in range(0, w, 24):
            draw.rectangle((x, y - 7, x + 2, y + 7), fill=(12, 96, 135))
    glow = lines.filter(ImageFilter.GaussianBlur(6))
    emission = Image.fromarray(np.clip(np.array(lines, dtype=float) + np.array(glow) * 1.7, 0, 255).astype(np.uint8))
    surface = Image.fromarray(np.clip(base.astype(float) + np.array(lines) * .45, 0, 255).astype(np.uint8))
    return surface, emission


def build_geometry():
    g = Geometry()
    for group, radius, width, panels in (("OuterRing", 1.94, .19, 28), ("InnerRing", 1.47, .105, 24)):
        outer = group == "OuterRing"
        g.arc(group, "graphite", radius, width, .17 if outer else .13, steps=100)
        for i in range(panels):
            gap = .014 if outer else .018
            start, stop = i * TAU / panels + gap, (i + 1) * TAU / panels - gap
            g.arc(group, "armor" if i % 4 else "silver", radius + .009, width - .022,
                  .205 if outer else .159, start, stop, bevel=.013)
            for z in (-.112, .112) if outer else (-.088, .088):
                g.arc(group, "edge", radius - width / 2 + .024, .009, .008, start, stop, z=z, bevel=.001)
            if i % 2 == 0 and i % (panels // 4) != 0:
                mid = (start + stop) / 2
                for z in (-.112, .112) if outer else (-.088, .088):
                    g.arc(group, "cyan", radius - width * .15, .012 if outer else .009, .007,
                          mid - .065, mid + .065, z=z, bevel=.001)
            if i % 2:
                angle = (start + stop) / 2
                for z in (-.113, .113) if outer else (-.089, .089):
                    center = [radius * math.cos(angle), radius * math.sin(angle), z]
                    g.box(group, "fastener", center, [.035, .018, .012], angle=angle, bevel=.003)
        for i in range(4):
            angle = i * math.pi / 2
            center = [radius * math.cos(angle), radius * math.sin(angle), 0]
            g.box(group, "graphite", center, [width + .095, .19 if outer else .15, .29 if outer else .24], angle, .021)
            for sign in (-1, 1):
                z = sign * (.153 if outer else .128)
                g.box(group, "edge", [*center[:2], z], [width + .045, .115, .018], angle, .006)
                g.box(group, "cyan", [*center[:2], z + sign*.012], [width-.01, .018, .012], angle, .004)
        # Hinge assemblies belong to their ring, with the same central pivot.
        angles = (math.pi/2, 3*math.pi/2) if outer else (0, math.pi/2, math.pi, 3*math.pi/2)
        for angle in angles:
            r = 1.72 if outer else 1.245
            length = .24 if outer else .27
            g.box(group, "graphite", [r*math.cos(angle), r*math.sin(angle), 0], [length, .075, .105], angle, .009)
            r = 1.62 if outer else 1.145
            g.box(group, "armor", [r*math.cos(angle), r*math.sin(angle), 0], [.10, .15, .19], angle, .014)
            for sign in (-1, 1):
                g.box(group, "cyan_dim", [r*math.cos(angle), r*math.sin(angle), sign*.101], [.045, .08, .009], angle, .003)

    g.sphere("Core", "circuit", 1.035, rings=40, sides=80)
    g.sphere("GlassShell", "glass", 1.065, rings=32, sides=64)
    for lat in (-math.pi/3, -math.pi/6, 0, math.pi/6, math.pi/3):
        path = [[1.049*math.cos(lat)*math.sin(t), 1.049*math.sin(lat), 1.049*math.cos(lat)*math.cos(t)] for t in np.linspace(0, TAU, 97)]
        g.tube("Core", "grid", path, radius=.0025 if lat else .004, sides=4)
    for lon in np.linspace(0, TAU, 8, endpoint=False):
        path = [[1.051*math.sin(t)*math.sin(lon), 1.051*math.cos(t), 1.051*math.sin(t)*math.cos(lon)] for t in np.linspace(.02, math.pi-.02, 49)]
        g.tube("Core", "grid", path, radius=.0024, sides=4)
    # Mirrored focal rings make the rear view intentional rather than empty.
    for sign in (-1, 1):
        for index, radius in enumerate((.105, .155, .225, .29, .365, .45, .53)):
            z = sign * (math.sqrt(1.049**2 - radius**2) + .006)
            g.halo("Core", "cyan" if index in (0, 2, 5) else "grid", radius,
                   .006 if index % 2 else .009, z)
        g.sphere("Core", "heart", .062, [0, 0, sign*1.047], rings=12, sides=24)
        for angle in np.linspace(0, TAU, 24, endpoint=False):
            radius = .42
            z = sign * (math.sqrt(1.052**2-radius**2) + .008)
            g.box("Core", "cyan_dim", [radius*math.cos(angle), radius*math.sin(angle), z], [.036, .008, .006], angle, .001)
    rng = random.Random(11)
    for _ in range(72):
        z = rng.uniform(-1, 1); angle = rng.random()*TAU
        xyz = np.array([math.sqrt(1-z*z)*math.cos(angle), z, math.sqrt(1-z*z)*math.sin(angle)]) * 1.053
        g.sphere("Core", "spark", rng.uniform(.003, .007), xyz, rings=4, sides=6)
    return g


class Glb:
    def __init__(self):
        self.bin = bytearray()
        self.doc = {"asset": {"version": "2.0", "generator": "JARVIS reference reconstruction / procedural Python"},
                    "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [], "meshes": [],
                    "buffers": [], "bufferViews": [], "accessors": [], "materials": [],
                    "images": [], "textures": [], "samplers": [{"magFilter":9729,"minFilter":9987,"wrapS":10497,"wrapT":33071}],
                    "extensionsUsed": ["KHR_materials_emissive_strength", "KHR_materials_ior", "KHR_materials_clearcoat"]}

    def view(self, data, target=None):
        while len(self.bin) % 4:
            self.bin.append(0)
        view = {"buffer": 0, "byteOffset": len(self.bin), "byteLength": len(data)}
        if target:
            view["target"] = target
        self.bin.extend(data); self.doc["bufferViews"].append(view)
        return len(self.doc["bufferViews"]) - 1

    def accessor(self, values, kind, integer=False, vertex=True):
        a = np.asarray(values, dtype="<u4" if integer else "<f4")
        if kind == "SCALAR": a = a.reshape(-1, 1)
        if not np.isfinite(a).all(): raise ValueError("Non-finite geometry")
        index = self.view(a.tobytes(), (34963 if integer else 34962) if vertex else None)
        entry = {"bufferView": index, "componentType":5125 if integer else 5126,
                 "count":len(a), "type":kind, "min":a.min(axis=0).tolist(), "max":a.max(axis=0).tolist()}
        self.doc["accessors"].append(entry)
        return len(self.doc["accessors"])-1

    def texture(self, image, name):
        buf=io.BytesIO(); image.save(buf, format="PNG", optimize=True)
        self.doc["images"].append({"name":name,"mimeType":"image/png","bufferView":self.view(buf.getvalue())})
        self.doc["textures"].append({"sampler":0,"source":len(self.doc["images"])-1})
        return len(self.doc["textures"])-1

    def save(self, path):
        self.doc["buffers"] = [{"byteLength":len(self.bin)}]
        encoded=json.dumps(self.doc,separators=(",",":"),ensure_ascii=False).encode()
        encoded += b" "*((-len(encoded))%4)
        binary=bytes(self.bin)+b"\0"*((-len(self.bin))%4)
        size=12+8+len(encoded)+8+len(binary)
        path.write_bytes(struct.pack("<4sII",b"glTF",2,size)+struct.pack("<I4s",len(encoded),b"JSON")+encoded+struct.pack("<I4s",len(binary),b"BIN\0")+binary)


def export(g, base, emission):
    glb = Glb()
    base_id, emit_id = glb.texture(base,"Core surface"), glb.texture(emission,"Core circuitry emission")
    materials = {
        "graphite": {"base":[.012,.018,.025,1],"metal":.86,"rough":.36},
        "armor": {"base":[.05,.06,.07,1],"metal":.88,"rough":.3},
        "silver": {"base":[.12,.14,.16,1],"metal":.94,"rough":.28},
        "edge": {"base":[.18,.22,.25,1],"metal":.95,"rough":.24},
        "fastener": {"base":[.014,.02,.025,1],"metal":.8,"rough":.44},
        "cyan": {"base":[.01,.3,.4,1],"emission":[.008,.55,.75],"strength":2.2},
        "cyan_dim": {"base":[.008,.1,.14,1],"emission":[.008,.38,.6],"strength":1.8},
        "grid": {"base":[.005,.05,.09,1],"emission":[.008,.22,.45],"strength":1.8},
        "heart": {"base":[.08,.65,.8,1],"emission":[.18,.88,1],"strength":5.5},
        "spark": {"base":[.02,.2,.3,1],"emission":[.06,.46,.7],"strength":2},
        "circuit": {"base":[.4,.68,.86,1],"metal":.38,"rough":.3,"emission":[.08,.5,.85],"strength":1.9},
        "glass": {"base":[.06,.25,.38,.12],"metal":0,"rough":.16},
    }
    ids={}
    for name,spec in materials.items():
        pbr={"baseColorFactor":spec["base"],"metallicFactor":spec.get("metal",.15),"roughnessFactor":spec.get("rough",.25)}
        material={"name":name,"pbrMetallicRoughness":pbr}
        if "emission" in spec:
            material["emissiveFactor"]=spec["emission"]
            material["extensions"]={"KHR_materials_emissive_strength":{"emissiveStrength":spec["strength"]}}
        if name=="circuit":
            pbr["baseColorTexture"]={"index":base_id}
            material["emissiveTexture"]={"index":emit_id}
        if name=="glass":
            material["alphaMode"]="BLEND"
            material["extensions"]={"KHR_materials_ior":{"ior":1.18},
                                    "KHR_materials_clearcoat":{"clearcoatFactor":.4,"clearcoatRoughnessFactor":.16}}
        ids[name]=len(glb.doc["materials"]); glb.doc["materials"].append(material)
    glb.doc["nodes"]=[{"name":"JARVIS_Core","children":[],"extras":{"frontAxis":"+Z","upAxis":"+Y","referenceReconstruction":True}}]
    groups={}
    exported_vertices=0
    for (group,material),bucket in g.parts.items():
        if group not in groups:
            groups[group]=len(glb.doc["nodes"])
            glb.doc["nodes"].append({"name":group,"mesh":len(glb.doc["meshes"]),"extras":{"pivot":[0,0,0]}})
            glb.doc["meshes"].append({"name":group,"primitives":[]})
            glb.doc["nodes"][0]["children"].append(groups[group])
        assert min(bucket["i"])>=0 and max(bucket["i"])<len(bucket["p"])
        # Weld identical position/normal/UV tuples without smoothing sharp edges.
        packed=np.hstack([bucket["p"],bucket["n"],bucket["uv"]]).astype(np.float32)
        unique,reverse=np.unique(packed,axis=0,return_inverse=True)
        exported_vertices+=len(unique)
        attributes={"POSITION":glb.accessor(unique[:,:3],"VEC3"),"NORMAL":glb.accessor(unique[:,3:6],"VEC3")}
        if material=="circuit": attributes["TEXCOORD_0"]=glb.accessor(unique[:,6:8],"VEC2")
        indices=reverse[np.asarray(bucket["i"])].tolist()
        primitive={"attributes":attributes,"indices":glb.accessor(indices,"SCALAR",True),"material":ids[material]}
        mesh_id=glb.doc["nodes"][groups[group]]["mesh"]
        glb.doc["meshes"][mesh_id]["primitives"].append(primitive)
    # The clear shell shares the central sphere's pivot and motion.
    glb.doc["nodes"][groups["Core"]]["children"]=[groups["GlassShell"]]
    glb.doc["nodes"][0]["children"].remove(groups["GlassShell"])
    glb.save(OUT/"jarvis-core.glb")
    animation={"name":"Idle_24s","samplers":[],"channels":[]}
    times=np.linspace(0,24,25)
    def track(node,path,values,kind):
        sample={"input":glb.accessor(times,"SCALAR",vertex=False),"output":glb.accessor(values,kind,vertex=False),"interpolation":"LINEAR"}
        animation["samplers"].append(sample)
        animation["channels"].append({"sampler":len(animation["samplers"])-1,"target":{"node":groups[node],"path":path}})
    track("OuterRing","rotation",[[0,0,math.sin(t/24*math.pi),math.cos(t/24*math.pi)] for t in times],"VEC4")
    track("InnerRing","rotation",[[0,math.sin(math.radians(25)*math.sin(t/24*TAU)/2),0,math.cos(math.radians(25)*math.sin(t/24*TAU)/2)] for t in times],"VEC4")
    track("Core","rotation",[[0,math.sin(t/24*math.pi),0,math.cos(t/24*math.pi)] for t in times],"VEC4")
    track("Core","scale",[[1+.008*math.sin(t/24*TAU*3)]*3 for t in times],"VEC3")
    glb.doc["animations"]=[animation]
    glb.save(OUT/"jarvis-core-animated.glb")
    return {"triangles":sum(len(b["i"])//3 for b in g.parts.values()),"vertices":exported_vertices,
            "objects":list(groups),"materials":list(materials),"pivot":[0,0,0],"units":"meters (outer diameter approximately 4.2)",
            "static":"jarvis-core.glb","animated":"jarvis-core-animated.glb","animation":"Idle_24s", "textureSize":[2048,1024]}


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    base,emission=circuit_textures()
    base.save(OUT/"core-base-color.png", optimize=True)
    emission.save(OUT/"core-emissive.png", optimize=True)
    report=export(build_geometry(),base,emission)
    (OUT/"model-info.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))


if __name__=="__main__": main()
