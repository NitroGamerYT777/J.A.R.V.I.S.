from __future__ import annotations

import json
import struct
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from jarvis.ui.glb_asset import decode_glb, load_model, model_path
from jarvis.ui.app import JarvisApp


def test_shipped_model_has_independent_parts_and_embedded_textures():
    model=load_model()
    assert {item.group for item in model.primitives}=={"OuterRing","InnerRing","Core","GlassShell"}
    assert len(model.images)==2
    assert all(image.startswith(b"\x89PNG") for image in model.images)
    glass=next(item for item in model.primitives if item.group=="GlassShell")
    assert glass.material["alphaMode"]=="BLEND"


def test_broken_header_is_rejected():
    with pytest.raises(ValueError,match="kesilgan"):
        decode_glb(b"glTF")


def test_out_of_bounds_accessor_is_rejected_before_gpu_upload():
    original=model_path().read_bytes()
    json_size=struct.unpack_from("<I",original,12)[0]
    doc=json.loads(original[20:20+json_size])
    doc["accessors"][0]["byteOffset"]=10**9
    encoded=json.dumps(doc,separators=(",",":")).encode()
    encoded+=b" "*((-len(encoded))%4)
    rest=original[20+json_size:]
    payload=struct.pack("<4sII",b"glTF",2,20+len(encoded)+len(rest))
    payload+=struct.pack("<I4s",len(encoded),b"JSON")+encoded+rest
    with pytest.raises(ValueError,match="accessor"):
        decode_glb(payload)


def test_old_idle_timer_does_not_interrupt_a_new_request():
    callbacks=[]
    reactor=SimpleNamespace(revision=1,set_state=Mock())
    app=SimpleNamespace(reactor=reactor,voice=SimpleNamespace(listening=False,speaking=False),after=lambda delay,callback:callbacks.append(callback))
    JarvisApp._idle_later(app,100)
    reactor.revision=2
    callbacks.pop()()
    reactor.set_state.assert_not_called()
    JarvisApp._idle_later(app,100)
    callbacks.pop()()
    reactor.set_state.assert_called_once_with("idle","TIZIM TAYYOR")
