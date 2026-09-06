"""Single service: CANONFLOW console (/) + ADK REST API + review console."""
from __future__ import annotations

import os
import pathlib

import uvicorn
from fastapi.staticfiles import StaticFiles
from gradio import mount_gradio_app

from canonflow_agent.ui import api
from canonflow_agent.ui.app import CSS, THEME, build as build_ui

HERE = pathlib.Path(__file__).resolve().parent
AGENTS_DIR = str(HERE)
RUNS_DIR = HERE.parent / "var" / "runs"
WEB_DIR = HERE / "canonflow_agent" / "ui" / "web"

try:
    from google.adk.cli.fast_api import get_fast_api_app
    app = get_fast_api_app(agents_dir=AGENTS_DIR, web=True)
    print("INFO ADK routes mounted")
except Exception as exc:  # noqa: BLE001
    from fastapi import FastAPI
    print("WARN ADK app unavailable (%s); serving console only" % exc)
    app = FastAPI(title="CANONFLOW")

app.include_router(api.router)
print("INFO api source: %s" % ("snapshot" if api.snapshot_ready() else "live"))

_media = api.media_root() or (RUNS_DIR if RUNS_DIR.is_dir() else None)
if _media is not None:
    app.mount("/media", StaticFiles(directory=str(_media)), name="media")
    print("INFO /media -> %s" % _media)

_allowed = [str(p) for p in (_media,) if p is not None]
app = mount_gradio_app(app, build_ui(), path="/review", theme=THEME, css=CSS,
                       allowed_paths=_allowed, show_error=True)

if WEB_DIR.is_dir():
    # ADK claims "/" with a redirect to /dev-ui/. Drop that single route so the
    # product console owns the root; every other ADK route stays intact.
    dropped = [r for r in app.router.routes if getattr(r, "path", None) == "/"]
    for r in dropped:
        app.router.routes.remove(r)
    if dropped:
        print("INFO released root route from ADK (%d)" % len(dropped))
    app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
    print("INFO / -> %s" % WEB_DIR)
else:
    print("INFO no frontend bundle at %s (build pending)" % WEB_DIR)

@app.middleware("http")
async def cf_no_index(request, call_next):
    """Keep the public evaluation surface out of search indexes."""
    response = await call_next(request)
    response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive, nosnippet"
    return response


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8081")))
