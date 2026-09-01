"""Deterministic merge, reference resolution and prompt compilation."""
from __future__ import annotations

import json
import pathlib
import sys
from typing import Any

from .schema import BeatPlan, Shot

REF_ROOT = "docs/evidence/p10g-canon-beat-sheet/reference-images/r4"


def merge(*, decomposed: dict, cinematography: dict, dialogue: dict,
          beat_id: str, shot_context: dict | None = None) -> dict:
    sc = shot_context or {}
    bound = bool(sc.get("bound"))
    pk_shots = sc.get("shots") or []
    by_key = {(s.get("scene_order"), s.get("shot_order")): s for s in pk_shots}
    by_order = {s.get("shot_order"): s for s in pk_shots}
    cine = {(c["scene_no"], c["shot_no"]): c for c in cinematography["shots"]}
    dial = {(d["scene_no"], d["shot_no"]): d for d in dialogue["shots"]}
    shots: list[Shot] = []
    for raw in decomposed["shots"]:
        key = (raw["scene_no"], raw["shot_no"])
        merged: dict[str, Any] = dict(raw)
        merged["beat_id"] = beat_id
        c = cine.get(key, {})
        merged["camera"] = c.get("camera", {})
        merged["light"] = c.get("light", {})
        merged["look"] = c.get("look", {})
        d = dial.get(key, {})
        merged["audio"] = d.get("audio", {})
        if bound:
            pk = by_key.get(key) or by_order.get(raw["shot_no"])
            if pk is None:
                raise ValueError(
                    f"{beat_id} scene {raw['scene_no']} shot {raw['shot_no']}: "
                    f"no bound packet shot (packet has "
                    f"{sorted(by_order)})")
            want = int(pk["duration_s"])
            if int(merged.get("duration_s") or 0) != want:
                print(f"FIX {beat_id}/{raw['scene_no']}/{raw['shot_no']}: "
                      f"duration_s {merged.get('duration_s')} -> {want}",
                      file=sys.stderr)
            merged["duration_s"] = want
        elif merged.get("hero_render") and int(merged.get("duration_s") or 0) == 10:
            print(f"WARN clamp {beat_id}/{raw['scene_no']}/{raw['shot_no']}: "
                  "hero_render=True with duration_s=10 -> 8",
                  file=sys.stderr)
            merged["duration_s"] = 8
        shots.append(Shot.model_validate(merged))
    plan = BeatPlan(beat_id=beat_id, shots=shots,
                    continuity_delta=decomposed.get("continuity_delta", ""))
    issues = plan.issues()
    if issues:
        raise ValueError("shot validation failed: " + "; ".join(issues))
    return plan.model_dump()


def resolve_references(*, plan: dict, character_map: dict[str, str]) -> dict:
    p = BeatPlan.model_validate(plan)
    for s in p.shots:
        uris: list[str] = []
        for ch in s.characters_present:
            uri = character_map.get(ch)
            if uri and uri not in uris:
                uris.append(uri)
        if len(uris) > 14:
            raise ValueError(f"{s.beat_id}/{s.scene_no}/{s.shot_no}: "
                             f"{len(uris)} references exceeds the limit of 14")
        s.reference_assets = uris
    return p.model_dump()


def _join(*chunks: str) -> str:
    return " ".join(c.strip() for c in chunks if c and c.strip())


def compile_prompts(*, plan: dict, negatives: list[str] | None = None) -> dict:
    p = BeatPlan.model_validate(plan)
    neg = negatives or []
    for s in p.shots:
        cam = s.camera
        cam_txt = _join(
            f"{cam.shot_size}." if cam.shot_size else "",
            f"{cam.type} on a {cam.lens_mm}mm lens at {cam.aperture}."
            if cam.lens_mm else f"{cam.type}.",
            f"Camera {cam.height}, {cam.angle} angle." if cam.angle else "",
        )
        look_txt = _join(
            f"Lighting: {s.light.key}, {s.light.mood}.",
            f"Practicals: {s.light.practicals}." if s.light.practicals else "",
            f"Palette: {s.look.palette}.",
            f"Texture: {s.look.filter_grain}." if s.look.filter_grain else "",
        )
        scene_txt = _join(
            f"{s.location}, {s.time_of_day}.",
            f"{s.atmosphere}." if s.atmosphere else "",
            f"{s.subject}.",
            f"Blocking: {s.blocking}." if s.blocking else "",
            f"Performance: {s.performance}." if s.performance else "",
        )
        s.frames.first_frame_prompt = _join(
            scene_txt, cam_txt, look_txt,
            f"Aspect ratio {s.look.aspect_ratio}. Single still frame, no motion blur.",
            *(f"Do not show {n}." for n in neg),
        )
        s.frames.last_frame_prompt = _join(
            scene_txt, cam_txt, look_txt,
            f"End of the shot after {s.duration_s} seconds "
            f"of {cam.movement or 'a locked-off frame'}.",
            f"Aspect ratio {s.look.aspect_ratio}.",
            *(f"Do not show {n}." for n in neg),
        )
        s.image_prompt = s.frames.first_frame_prompt
        a = s.audio
        s.video_prompt = _join(
            scene_txt, cam_txt,
            f"Camera movement: {cam.movement}." if cam.movement else "",
            look_txt,
            f"Dialogue: {a.dialogue}" if a.dialogue else "",
            f"Delivery: {a.voice_direction}." if a.voice_direction else "",
            f"Score: {a.score_cue}." if a.score_cue else "",
            f"Sound effects: {a.sfx}." if a.sfx else "",
            f"Ambience: {a.ambience}." if a.ambience else "",
            f"Duration {s.duration_s} seconds. Aspect ratio {s.look.aspect_ratio}.",
            *(f"Do not show {n}." for n in neg),
        )
    return p.model_dump()


def write_plan(*, plan: dict, run_dir: str, beat_id: str) -> dict:
    dst = pathlib.Path(run_dir) / f"plan-{beat_id}.json"
    dst.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"path": str(dst), "shot_count": len(plan["shots"])}
