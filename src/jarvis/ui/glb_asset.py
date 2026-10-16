"""Read the self-contained GLB used by JARVIS's native OpenGL viewport."""
from __future__ import annotations

import json
import struct
import sysconfig
from dataclasses import dataclass
from pathlib import Path

import numpy as np


def model_path() -> Path:
    candidates = (
        Path(__file__).resolve().parents[3] / "assets/3d/jarvis-core.glb",
        Path(sysconfig.get_path("data")) / "share/jarvis/3d/jarvis-core.glb",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("JARVIS 3D model fayli topilmadi.")


@dataclass
class Primitive:
    group: str
    vertices: np.ndarray
    indices: np.ndarray
    material: dict


@dataclass
class Model:
    primitives: list[Primitive]
    images: list[bytes]
    textures: list[int]


def decode_glb(payload: bytes) -> Model:
    if len(payload) < 20:
        raise ValueError("GLB fayli kesilgan.")
    magic, version, size = struct.unpack_from("<4sII", payload)
    if magic != b"glTF" or version != 2 or size != len(payload):
        raise ValueError("GLB sarlavhasi yaroqsiz.")
    chunks = {}
    offset = 12
    while offset < len(payload):
        if offset + 8 > len(payload):
            raise ValueError("GLB bo'lim sarlavhasi kesilgan.")
        length, kind = struct.unpack_from("<I4s", payload, offset)
        offset += 8
        if offset + length > len(payload):
            raise ValueError("GLB bo'limi fayl chegarasidan tashqarida.")
        chunks[kind] = payload[offset:offset + length]
        offset += length
    if b"JSON" not in chunks or b"BIN\0" not in chunks:
        raise ValueError("GLB JSON yoki geometriyasi mavjud emas.")
    doc = json.loads(chunks[b"JSON"])
    binary = chunks[b"BIN\0"]

    def view(index):
        item = doc["bufferViews"][index]
        if item.get("buffer", 0) != 0:
            raise ValueError("Faqat ichiga joylangan GLB buffer qo'llanadi.")
        start = item.get("byteOffset", 0)
        end = start + item["byteLength"]
        if start < 0 or end > len(binary):
            raise ValueError("GLB buffer chegarasi noto'g'ri.")
        return binary[start:end], item

    def accessor(index):
        item = doc["accessors"][index]
        data, buffer_view = view(item["bufferView"])
        dtypes = {5126:"<f4", 5125:"<u4", 5123:"<u2", 5121:"u1"}
        widths = {"SCALAR":1, "VEC2":2, "VEC3":3, "VEC4":4}
        dtype = np.dtype(dtypes[item["componentType"]])
        width = widths[item["type"]]
        count, start = item["count"], item.get("byteOffset", 0)
        stride = buffer_view.get("byteStride", width * dtype.itemsize)
        end = start + max(count - 1, 0) * stride + (width * dtype.itemsize if count else 0)
        if count < 0 or start < 0 or stride < width * dtype.itemsize or end > len(data):
            raise ValueError("GLB accessor geometriya chegarasidan tashqarida.")
        return np.ndarray((count, width), dtype=dtype, buffer=data, offset=start,
                          strides=(stride, dtype.itemsize)).copy()

    images = [view(image["bufferView"])[0] for image in doc.get("images", [])]
    textures = [texture["source"] for texture in doc.get("textures", [])]
    primitives = []
    for node in doc["nodes"]:
        if "mesh" not in node:
            continue
        for primitive in doc["meshes"][node["mesh"]]["primitives"]:
            if primitive.get("mode", 4) != 4:
                raise ValueError("3D yadro uchburchak geometriyasini talab qiladi.")
            attributes = primitive["attributes"]
            positions = accessor(attributes["POSITION"])
            normals = accessor(attributes["NORMAL"])
            uv = accessor(attributes["TEXCOORD_0"]) if "TEXCOORD_0" in attributes else np.zeros((len(positions), 2))
            indices = accessor(primitive["indices"]).reshape(-1).astype(np.uint32)
            if len(normals) != len(positions) or len(uv) != len(positions):
                raise ValueError("3D vertex atributlari mos emas.")
            if len(indices) % 3 or (len(indices) and indices.max() >= len(positions)):
                raise ValueError("GLB uchburchak indekslari yaroqsiz.")
            vertices = np.ascontiguousarray(np.hstack((positions, normals, uv)), dtype=np.float32)
            if not np.isfinite(vertices).all():
                raise ValueError("GLB geometriyasida yaroqsiz raqam bor.")
            material = doc["materials"][primitive["material"]]
            primitives.append(Primitive(node["name"], vertices, indices, material))
    if not primitives:
        raise ValueError("GLB geometriyasi bo'sh.")
    return Model(primitives, images, textures)


def load_model(path: Path | None = None) -> Model:
    return decode_glb((path or model_path()).read_bytes())
