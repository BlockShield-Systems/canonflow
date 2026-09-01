"""Cost-bearing nodes. Guarded by the tier gate from pipeline.md 1a.

Request bodies are supplied by the workflow file, not hardcoded, so that a
model-side API change is a config edit and not a code change.
"""
from __future__ import annotations

import base64
import os
import pathlib
import time
from typing import Any

import httpx

from ..auth import headers, project
from .base import node

TIERS = {
    "draft": {"image": "gemini-3.1-flash-lite-image",
              "video": "gemini-omni-1.1-flash-preview",
              "image_res": "1K", "video_res": "360p",
              "usd_image": 0.034, "usd_video_per_s": 0.0338},
    "proof": {"image": "gemini-3-pro-image",
              "video": "gemini-omni-1.1-flash-preview",
              "image_res": "2K", "video_res": "720p",
              "usd_image": 0.134, "usd_video_per_s": 0.1014},
    "final": {"image": "gemini-3-pro-image",
              "video": "gemini-omni-1.1-flash-preview",
              "image_res": "2K", "video_res": "720p",
              "usd_image": 0.134, "usd_video_per_s": 0.1014},
    "hero":  {"image": "gemini-3-pro-image",
              "video": "veo-3.1-generate-001",
              "image_res": "4K", "video_res": "1080p",
              "usd_image": 0.24, "usd_video_per_s": 0.40},
}


def gate(tier: str, batch_id: str) -> None:
    if tier not in TIERS:
        raise ValueError(f"unknown tier: {tier}")
    if tier == "draft":
        return
    ack = os.environ.get("CF_TIER_OK", "")
    if ack != batch_id:
        raise PermissionError(
            f"tier '{tier}' requires CF_TIER_OK={batch_id} (current: '{ack}')")


def _outdir(run_dir: str, name: str) -> pathlib.Path:
    p = pathlib.Path(run_dir) / "media"
    p.mkdir(parents=True, exist_ok=True)
    return p / name


@node("render.image", costs=True)
def render_image(*, tier: str, batch_id: str, prompt: str, name: str,
                 run_dir: str, reference_uris: list[str] | None = None,
                 resolution: str | None = None, **_: Any) -> dict:
    gate(tier, batch_id)
    cfg = TIERS[tier]
    model = cfg["image"]
    res = resolution or cfg["image_res"]

    parts: list[dict] = [{"text": prompt}]
    for uri in (reference_uris or []):
        parts.append({"fileData": {"mimeType": "image/jpeg", "fileUri": uri}})

    url = (f"https://aiplatform.googleapis.com/v1/projects/{project()}"
           f"/locations/global/publishers/google/models/{model}:generateContent")
    body = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
            "imageConfig": {"imageSize": res},
        },
    }
    r = httpx.post(url, headers=headers(), json=body, timeout=600.0)
    if r.status_code != 200:
        raise RuntimeError(f"{model} HTTP {r.status_code}: {r.text[:400]}")
    data = r.json()

    written: list[str] = []
    for i, p in enumerate(data["candidates"][0]["content"]["parts"]):
        blob = p.get("inlineData")
        if not blob:
            continue
        ext = blob.get("mimeType", "image/png").split("/")[-1]
        dst = _outdir(run_dir, f"{name}-{i}.{ext}")
        dst.write_bytes(base64.b64decode(blob["data"]))
        written.append(str(dst))
    if not written:
        raise RuntimeError(f"{model} returned no image part")
    return {"model": model, "tier": tier, "resolution": res,
            "files": written, "est_usd": cfg["usd_image"] * len(written)}


@node("render.video", costs=True)
def render_video(*, tier: str, batch_id: str, request: dict, name: str,
                 run_dir: str, duration_s: int, poll_s: int = 15,
                 timeout_s: int = 1800, **_: Any) -> dict:
    gate(tier, batch_id)
    cfg = TIERS[tier]
    model = cfg["video"]
    location = "us-central1" if model.startswith("veo-") else "global"
    host = (f"https://{location}-aiplatform.googleapis.com"
            if location != "global" else "https://aiplatform.googleapis.com")
    verb = "predictLongRunning" if model.startswith("veo-") else "generateContent"

    url = (f"{host}/v1/projects/{project()}/locations/{location}"
           f"/publishers/google/models/{model}:{verb}")
    r = httpx.post(url, headers=headers(), json=request, timeout=900.0)
    if r.status_code != 200:
        raise RuntimeError(f"{model} HTTP {r.status_code}: {r.text[:400]}")
    data = r.json()

    if verb == "predictLongRunning":
        op = data["name"]
        fetch = (f"{host}/v1/projects/{project()}/locations/{location}"
                 f"/publishers/google/models/{model}:fetchPredictOperation")
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            time.sleep(poll_s)
            pr = httpx.post(fetch, headers=headers(),
                            json={"operationName": op}, timeout=120.0)
            pr.raise_for_status()
            st = pr.json()
            if st.get("done"):
                if "error" in st:
                    raise RuntimeError(f"veo operation failed: {st['error']}")
                data = st.get("response", {})
                break
        else:
            raise TimeoutError(f"veo operation {op} exceeded {timeout_s}s")

    written: list[str] = []
    stack: list[Any] = [data]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            b64 = cur.get("bytesBase64Encoded") or (cur.get("inlineData") or {}).get("data")
            if b64 and isinstance(b64, str) and len(b64) > 1024:
                dst = _outdir(run_dir, f"{name}-{len(written)}.mp4")
                dst.write_bytes(base64.b64decode(b64))
                written.append(str(dst))
            if cur.get("gcsUri"):
                written.append(cur["gcsUri"])
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)
    if not written:
        raise RuntimeError(f"{model} returned no video payload; keys={list(data)[:8]}")
    return {"model": model, "tier": tier, "files": written,
            "est_usd": round(cfg["usd_video_per_s"] * duration_s, 4)}
