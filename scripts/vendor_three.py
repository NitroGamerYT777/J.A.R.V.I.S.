"""Fetch the pinned MIT-licensed viewer engine; verify npm's SHA-512 checksum."""
from __future__ import annotations

import base64
import hashlib
import io
import json
import tarfile
from pathlib import Path
from urllib.request import urlopen

VERSION = "0.180.0"
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "3d" / "vendor" / "three"
FILES = [
    "LICENSE", "build/three.core.js", "build/three.module.js",
    "examples/jsm/loaders/GLTFLoader.js", "examples/jsm/controls/OrbitControls.js",
    "examples/jsm/utils/BufferGeometryUtils.js",
    "examples/jsm/environments/RoomEnvironment.js",
    "examples/jsm/postprocessing/EffectComposer.js",
    "examples/jsm/postprocessing/RenderPass.js",
    "examples/jsm/postprocessing/UnrealBloomPass.js",
    "examples/jsm/postprocessing/ShaderPass.js",
    "examples/jsm/postprocessing/MaskPass.js",
    "examples/jsm/postprocessing/Pass.js",
    "examples/jsm/postprocessing/OutputPass.js",
    "examples/jsm/shaders/CopyShader.js",
    "examples/jsm/shaders/LuminosityHighPassShader.js",
    "examples/jsm/shaders/OutputShader.js",
]


def main():
    with urlopen(f"https://registry.npmjs.org/three/{VERSION}", timeout=30) as response:
        metadata = json.load(response)
    dist = metadata["dist"]
    with urlopen(dist["tarball"], timeout=60) as response:
        payload = response.read()
    expected = dist["integrity"].removeprefix("sha512-")
    actual = base64.b64encode(hashlib.sha512(payload).digest()).decode()
    if actual != expected:
        raise RuntimeError("The three.js package integrity check failed.")
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as package:
        for name in FILES:
            source = package.extractfile("package/" + name)
            if source is None:
                raise RuntimeError(f"Missing vendor file: {name}")
            destination = OUT / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(source.read())
    (OUT / "package-info.json").write_text(json.dumps({
        "name": "three", "version": VERSION, "license": "MIT",
        "source": dist["tarball"], "integrity": dist["integrity"], "files": FILES,
    }, indent=2), encoding="utf-8")
    print(f"Verified and installed three.js {VERSION}: {len(FILES)} files.")


if __name__ == "__main__":
    main()
