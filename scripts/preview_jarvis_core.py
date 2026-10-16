"""Serve the 3D model viewer locally, without uploading images or model data."""
from __future__ import annotations

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    folder = ROOT / "assets" / "3d"
    handler = partial(SimpleHTTPRequestHandler, directory=str(folder))
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    print(f"JARVIS 3D preview: http://127.0.0.1:{args.port}/", flush=True)
    print("Press Ctrl+C to stop. Drag to rotate; scroll to zoom.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
