"""Exercise JARVIS's embedded 3D viewport; capture only its own framebuffer."""
from __future__ import annotations

import json
import time
import traceback
from pathlib import Path

from jarvis.ui.app import JarvisApp

ROOT=Path(__file__).resolve().parents[1]


def main():
    output=ROOT/"assets/3d/previews"
    output.mkdir(parents=True,exist_ok=True)
    app=JarvisApp()
    app.voice_enabled=False
    app.geometry("1280x800")
    errors=[]
    report={"states":[]}
    start=time.monotonic()
    modes=iter(("idle","thinking","speaking","listening"))

    def failed(kind,error,tb):
        errors.append("".join(traceback.format_exception(kind,error,tb)))
        app._close()
    app.report_callback_exception=failed

    def wait_ready():
        if app.reactor.error:
            raise RuntimeError(app.reactor.error)
        if app.reactor.ready and app.reactor.viewport.frame_count>3:
            # Exercise resize after initialization as well as all four states.
            app.geometry("1360x820")
            app.after(250,next_state)
        elif time.monotonic()-start>20:
            raise RuntimeError("Native 3D viewport did not become ready.")
        else:
            app.after(60,wait_ready)

    def next_state():
        mode=next(modes,None)
        if mode is None:
            view=app.reactor.viewport
            report.update(renderer=view.renderer_info,frameCount=view.frame_count,
                          meshPrimitives=len(view.meshes),size=list(view.target_size),errors=errors)
            app.geometry("980x620")
            app.after(250,finish)
            return
        app.reactor.set_state(mode,"3D YADRO · "+mode.upper())
        app.after(450,lambda: capture(mode))

    def capture(mode):
        view=app.reactor.viewport
        assert view.ready and view.mode==mode
        assert view.frame_count>0
        view.capture(output/f"native-{mode}.png")
        report["states"].append(mode)
        app.after(50,next_state)

    def finish():
        bottom=app.prompt.winfo_rooty()-app.winfo_rooty()+app.prompt.winfo_height()
        assert app.prompt.winfo_ismapped() and bottom<=app.winfo_height(), f"Input bottom={bottom}, window height={app.winfo_height()}"
        report["inputVisibleAtMinimumSize"]=True
        app.reactor._failed(RuntimeError("Simulated renderer failure"))
        assert app.reactor.fallback is not None
        app.reactor.set_state("thinking","FALLBACK TEST")
        report["fallbackVerified"]=True
        (output/"native-verification.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
        app._close()

    app.after(100,wait_ready)
    app.mainloop()
    if errors:
        raise RuntimeError("\n".join(errors))
    print(json.dumps(report,indent=2))


if __name__=="__main__":
    main()
