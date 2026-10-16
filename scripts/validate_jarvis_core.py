"""Validate the generated GLBs with Khronos glTF Validator (download cached in data/).

Requires Node.js. The validator npm package is verified against registry SHA-512.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import shutil
import subprocess
import tarfile
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def validator_cache():
    cache = ROOT / "data" / "gltf-validator"
    if (cache / "index.js").is_file():
        return cache
    with urlopen("https://registry.npmjs.org/gltf-validator/latest", timeout=30) as response:
        metadata = json.load(response)
    dist = metadata["dist"]
    with urlopen(dist["tarball"], timeout=60) as response:
        payload = response.read()
    digest = base64.b64encode(hashlib.sha512(payload).digest()).decode()
    if dist["integrity"] != "sha512-" + digest:
        raise RuntimeError("glTF Validator checksum mismatch.")
    cache.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as package:
        for name in ("index.js", "gltf_validator.dart.js", "package.json", "LICENSE"):
            source = package.extractfile("package/" + name)
            if source:
                (cache / name).write_bytes(source.read())
    return cache


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--node", default=shutil.which("node"))
    args = parser.parse_args()
    if not args.node:
        parser.error("Node.js not found; pass --node with its executable path.")
    cache = validator_cache()
    script = """
      const fs=require('fs'); const validator=require(process.argv[1]);
      (async()=>{const reports={}; for(const file of process.argv.slice(2)) {
        reports[file.split(/[\\\\/]/).pop()]=await validator.validateBytes(new Uint8Array(fs.readFileSync(file)),{uri:file,maxIssues:100});
      } console.log(JSON.stringify(reports));})().catch(e=>{console.error(e);process.exit(1)});
    """
    files = [ROOT / "assets/3d" / name for name in ("jarvis-core.glb", "jarvis-core-animated.glb")]
    result = subprocess.run([args.node, "-e", script, str(cache / "index.js"), *map(str, files)], capture_output=True, text=True, check=True)
    report = json.loads(result.stdout)
    output = ROOT / "assets/3d/previews/gltf-validation.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    for name, entry in report.items():
        issues = entry["issues"]
        print(f"{name}: {issues['numErrors']} errors, {issues['numWarnings']} warnings")
        for issue in issues["messages"]:
            if issue["severity"] < 2:
                print(issue)
    if any(entry["issues"]["numErrors"] for entry in report.values()):
        raise RuntimeError("Generated glTF failed validation.")


if __name__ == "__main__":
    main()
