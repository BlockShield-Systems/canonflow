"""Read-only JSON API over the frozen snapshot, with live fallback."""
from __future__ import annotations

import functools
import json
import os
import pathlib

from fastapi import APIRouter, HTTPException

from . import build, data

router = APIRouter(prefix="/api", tags=["canonflow"])
SNAPSHOT = build.SNAPSHOT


def snapshot_ready() -> bool:
    return (SNAPSHOT / "index.json").is_file()


def media_root() -> pathlib.Path | None:
    if (SNAPSHOT / "media").is_dir():
        return SNAPSHOT / "media"
    return None


def _norm(beat: str) -> str:
    b = beat.strip().upper()
    if b.startswith("P10G-BEAT-"):
        b = b[len("P10G-BEAT-"):]
    if not (len(b) == 3 and b.isdigit()):
        raise HTTPException(400, "beat must be NNN or P10G-BEAT-NNN")
    return b


@functools.lru_cache(maxsize=1)
def _index() -> dict:
    if snapshot_ready():
        return json.loads((SNAPSHOT / "index.json").read_text(encoding="utf-8"))
    idx, _ = build.build(data.scan())
    return idx


@functools.lru_cache(maxsize=64)
def _detail(beat: str) -> dict:
    if snapshot_ready():
        f = SNAPSHOT / "beats" / ("%s.json" % beat)
        if not f.is_file():
            raise HTTPException(404, "unknown beat %s" % beat)
        return json.loads(f.read_text(encoding="utf-8"))
    scanned = data.scan()
    if beat not in scanned:
        raise HTTPException(404, "unknown beat %s" % beat)
    return build.beat_detail(scanned[beat])


@functools.lru_cache(maxsize=1)
def _tiers() -> dict:
    try:
        from canonflow_agent.flow.nodes.render import TIERS
    except Exception as exc:  # noqa: BLE001
        return {"error": "TIERS unavailable: %s" % type(exc).__name__}
    return {k: dict(v) for k, v in TIERS.items()}


@router.get("/health")
def health() -> dict:
    ix = _index()
    return {
        "status": "ok",
        "source": "snapshot" if snapshot_ready() else "live",
        "generated_at": ix.get("generated_at"),
        "beat_count": ix.get("beat_count"),
        "verdicts": ix.get("verdicts"),
        "media_count": ix.get("media_count"),
        "env": {
            "CF_PROJECT": bool(os.environ.get("CF_PROJECT")),
            "CANONFLOW_MCP_URL": bool(os.environ.get("CANONFLOW_MCP_URL")),
            "GOOGLE_CLOUD_PROJECT": os.environ.get("GOOGLE_CLOUD_PROJECT"),
        },
    }


@router.get("/timeline")
def timeline() -> dict:
    return _index()


@router.get("/segments")
def seg_list() -> list[dict]:
    return _index().get("segments", [])


@router.get("/beats")
def beat_list() -> list[dict]:
    return _index().get("beats", [])


@router.get("/beats/{beat}")
def beat_get(beat: str) -> dict:
    return _detail(_norm(beat))


@router.get("/beats/{beat}/validate")
def beat_validate(beat: str) -> dict:
    d = _detail(_norm(beat))
    return {"beat_id": d["beat_id"], "verdict": d["verdict"],
            "validate": d.get("validate", {})}


@router.get("/beats/{beat}/prompts")
def beat_prompts(beat: str) -> dict:
    d = _detail(_norm(beat))
    return {"beat_id": d["beat_id"], "prompts": d.get("prompts", {})}


@router.get("/tiers")
def tiers() -> dict:
    return _tiers()
