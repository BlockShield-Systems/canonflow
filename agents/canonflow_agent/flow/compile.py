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


# ---------------------------------------------------------------------------
# presentation intro overrides (P10G-BEAT-000)
# The global negatives list contains "on-screen text". The intro consists of
# nothing but on-screen text, so the global list must not be applied verbatim.
# ---------------------------------------------------------------------------
INTRO_BEAT_ID = "P10G-BEAT-000"

INTRO_NEGATIVES = [
    "photographic imagery of any kind",
    "human faces, bodies or hands",
    "environments, sets, rooms or landscapes",
    "props, furniture, vehicles or screens as objects",
    "logos, watermarks or UI chrome",
    "any colour other than pure black and white or off-white",
]


def _intro_negatives(negatives: list[str] | None) -> list[str]:
    """Drop text-hostile negatives, add void-specific ones."""
    keep = [n for n in (negatives or [])
            if "text" not in n.lower() and "typograph" not in n.lower()]
    out = list(keep)
    for n in INTRO_NEGATIVES:
        if n not in out:
            out.append(n)
    return out


_resolve_references_pre_intro = resolve_references


def resolve_references(*, plan: dict, character_map: dict[str, str]) -> dict:
    """Hard deny: the intro transmits no reference assets."""
    if plan.get("beat_id") != INTRO_BEAT_ID:
        return _resolve_references_pre_intro(plan=plan,
                                            character_map=character_map)
    p = BeatPlan.model_validate(plan)
    offenders = [(s.scene_no, s.shot_no, s.characters_present)
                 for s in p.shots if s.characters_present]
    if offenders:
        raise ValueError(
            f"{INTRO_BEAT_ID}: presentation intro must have no characters, got "
            + "; ".join(f"{sc}/{sh}: {ch}" for sc, sh, ch in offenders)
        )
    for s in p.shots:
        s.reference_assets = []
    print(f"INFO {INTRO_BEAT_ID}: reference resolution denied "
          f"({len(p.shots)} shots, 0 assets)", file=sys.stderr)
    return p.model_dump()


_compile_prompts_pre_intro = compile_prompts


def compile_prompts(*, plan: dict, negatives: list[str] | None = None) -> dict:
    if plan.get("beat_id") != INTRO_BEAT_ID:
        return _compile_prompts_pre_intro(plan=plan, negatives=negatives)
    neg = _intro_negatives(negatives)
    print(f"INFO {INTRO_BEAT_ID}: intro negatives applied ({len(neg)} entries, "
          f"text-hostile entries removed)", file=sys.stderr)
    out = _compile_prompts_pre_intro(plan=plan, negatives=neg)
    for s in out["shots"]:
        for k in ("image_prompt", "video_prompt"):
            low = s.get(k, "").lower()
            if "do not show on-screen text" in low:
                raise ValueError(
                    f"{INTRO_BEAT_ID}/{s['scene_no']}/{s['shot_no']}: "
                    f"{k} still forbids on-screen text")
    return out


# --- intro normalization (P10G-BEAT-000) ------------------------------------
# The model must not author verbatim card text. Any retyped variant (wrong dash,
# straight quotes, collapsed spaces) is rewritten to the canonical string, and
# audio.dialogue is coerced to real null.

import re as _cf_re
from canonflow_agent.flow.packets import (  # noqa: E402
    INTRO_BEAT_ID as _CF_INTRO_ID,
    INTRO_CARD_TEXT as _CF_CARDS,
    INTRO_CARD_ATTRIBUTION as _CF_ATTR,
    INTRO_TEXT_STATE as _CF_STATE,
)

_CF_DASH = "-\u2013\u2014\u2212"
_CF_DQ = "\"\u201c\u201d"
_CF_NULLISH = ("", "null", "none", "n/a", "-")


def _cf_flex(text: str) -> str:
    out = []
    for ch in text:
        if ch in _CF_DASH:
            out.append(f"[{_cf_re.escape(_CF_DASH)}]")
        elif ch in _CF_DQ:
            out.append(f"[{_cf_re.escape(_CF_DQ)}]?")
        elif ch.isspace():
            out.append(r"\s+")
        else:
            out.append(_cf_re.escape(ch))
    return "".join(out)


_CF_PATTERNS = [(_cf_re.compile(f"[{_cf_re.escape(_CF_DQ)}]?" + _cf_flex(t) +
                                f"[{_cf_re.escape(_CF_DQ)}]?"), t)
                for t in sorted(_CF_CARDS.values(), key=len, reverse=True)]
_CF_PATTERNS += [(_cf_re.compile(_cf_flex(a)), a) for a in _CF_ATTR.values()]


def _cf_fix_text(value):
    if isinstance(value, str):
        for pat, canon in _CF_PATTERNS:
            value = pat.sub(lambda _m, c=canon: c, value)
        return value
    if isinstance(value, list):
        return [_cf_fix_text(v) for v in value]
    if isinstance(value, dict):
        return {k: _cf_fix_text(v) for k, v in value.items()}
    return value


def _cf_shot_get(shot, key, default=None):
    return shot.get(key, default) if isinstance(shot, dict) else getattr(shot, key, default)


def _cf_shot_set(shot, key, value):
    if isinstance(shot, dict):
        shot[key] = value
    else:
        object.__setattr__(shot, key, value)


def _cf_normalize_intro(plan):
    shots = plan.get("shots") if isinstance(plan, dict) else getattr(plan, "shots", None)
    if not shots:
        return plan
    for i, s in enumerate(shots):
        sid = _cf_shot_get(s, "shot_id") or f"000-{i + 1:02d}"
        state = _CF_STATE.get(sid)
        if state is None:
            raise ValueError(f"intro normalization: unknown shot id {sid!r}")

        for field in ("subject", "blocking", "intent", "continuity_notes",
                      "atmosphere", "look", "performance", "frames"):
            cur = _cf_shot_get(s, field)
            if cur is not None:
                _cf_shot_set(s, field, _cf_fix_text(cur))

        audio = _cf_shot_get(s, "audio")
        if isinstance(audio, dict):
            dlg = audio.get("dialogue")
            if dlg is None or (isinstance(dlg, str) and dlg.strip().lower() in _CF_NULLISH):
                audio["dialogue"] = None
            else:
                raise ValueError(f"intro shot {sid}: audio.dialogue must be null, got {dlg!r}")
            for k, v in list(audio.items()):
                if k != "dialogue":
                    audio[k] = _cf_fix_text(v)

        _cf_shot_set(s, "shot_id", sid)
        _cf_shot_set(s, "text_card_ids", list(state["text_card_ids"]))
        _cf_shot_set(s, "text_state", state["text_state"])
        _cf_shot_set(s, "visible_text_carry_over", list(state["visible_text_carry_over"]))
        _cf_shot_set(s, "text_render", [
            {"card_id": cid, "text": _CF_CARDS[cid], "attribution": _CF_ATTR.get(cid)}
            for cid in state["text_card_ids"]
        ])
        _cf_shot_set(s, "characters_present", [])
        _cf_shot_set(s, "reference_assets", [])
        _cf_shot_set(s, "hero_render", False)
    return plan


_cf_prev_merge = merge


def merge(*args, **kwargs):  # noqa: F811
    plan = _cf_prev_merge(*args, **kwargs)
    beat_id = plan.get("beat_id") if isinstance(plan, dict) else getattr(plan, "beat_id", None)
    if beat_id == _CF_INTRO_ID:
        plan = _cf_normalize_intro(plan)
        print(f"INFO intro normalization applied ({_CF_INTRO_ID})", flush=True)
    return plan


# --- intro prompt composition (P10G-BEAT-000) -------------------------------
# The generic composer builds prompts from location/time_of_day/subject/blocking.
# For the intro that yields literal "N/A", audio noise inside the image prompt and
# leaked machine syntax (text_card_ids=[...]) from the decomposer's blocking text.
# The intro is pure typography on black, so its prompts are composed from
# structured data only: canonical card text plus a per-shot motion/audio spec.

INTRO_BASE_VISUAL = (
    "Pure black frame, hex #000000. Absolute digital void: no environment, no set, "
    "no objects, no people, no photographic content of any kind."
)
INTRO_TYPOGRAPHY = (
    "Typography only: clean clinical sans-serif or modern monospace, "
    "hex #FFFFFF or #F2F2F2 on #000000, centered, generous margins, "
    "flawless kerning, no decorative effects."
)

INTRO_RENDER_SPEC = {
    "000-01": {
        "still": "The text sits centered at full opacity, perfectly sharp and static.",
        "first": "Near-black frame, the text barely visible at very low opacity.",
        "last": "The text at full opacity, centered, perfectly still.",
        "motion": "The only motion is a slow 3-second opacity ramp of the text from 0 to 100 percent. Locked-off frame, no camera movement.",
        "audio": "A faint low-frequency server hum begins to build. No voice, no music.",
    },
    "000-02": {
        "still": "The second line of the quote is centered at full opacity, with the attribution line right-aligned beneath it.",
        "first": "The second line appears at full opacity, attribution not yet visible.",
        "last": "Second line and right-aligned attribution both fully visible, static.",
        "motion": "The attribution fades in beneath the quote. No camera movement, no text movement.",
        "audio": "Low server hum with erratic digital clicking bleeding into it. No voice, no music.",
    },
    "000-03": {
        "still": "The complete quote holds perfectly still, sharp and unmoving.",
        "first": "The complete quote, static and pristine.",
        "last": "The complete quote, unchanged and still pristine.",
        "motion": "Absolutely no motion: no camera movement, no text movement, no flicker, no drift for the full duration.",
        "audio": "Server hum plus faint unstable digital clicking. No voice, no music.",
    },
    "000-04": {
        "still": "The pristine text violently torn apart: red and cyan chromatic split, severe chromatic aberration, datamosh smear, frame tearing, a static burst sweeping left to right.",
        "first": "The text intact for a single frame before the rupture.",
        "last": "The text destroyed and unreadable, dissolving into static.",
        "motion": "Violent glitch rupture: red/cyan chroma split, severe chromatic aberration, datamosh smear, frame tearing, static burst travelling left to right. The text is destroyed, not moved.",
        "audio": "Harsh digital static and grinding artifacts, aggressively panning left to right. No voice, no music.",
    },
    "000-05": {
        "still": "First the system-like monotype line alone on black, rendered without quotation marks; then the main title stark and centered.",
        "first": "Snap to pure black, completely empty frame.",
        "last": "The main title centered, stark and flawless, beginning to fade out.",
        "motion": "Snap to black and micro-silence, then the monotype line holds about 2.5 seconds, then the title crashes hard into the center of the frame, holds briefly and fades smoothly over 2 seconds.",
        "audio": "Micro-silence, then a massive clean cinematic bass impact. No voice, no music.",
    },
    "000-06": {
        "still": "A smaller, elegant, centered director credit on pure black.",
        "first": "Pure black frame, the credit barely emerging.",
        "last": "Pure black frame, the credit fully faded out.",
        "motion": "The credit fades in and out gently, then the frame fades to black. No camera movement.",
        "audio": "The server hum returns pitch-dropped and dissonant, then crossfades into the voiceover and documentary bed of the following beat. No spoken line in this shot.",
    },
}


def _intro_text_lines(shot) -> list[str]:
    lines = []
    for card in (getattr(shot, "text_render", None) or []):
        lines.append("Exact on-screen text, render verbatim, character for character, "
                     f"nothing added and nothing omitted: {card['text']}")
        if card.get("attribution"):
            lines.append("Attribution line, right-aligned beneath the quote, "
                         f"render verbatim: {card['attribution']}")
    carry = getattr(shot, "visible_text_carry_over", None) or []
    if carry and not lines:
        held = " ".join(INTRO_CARD_TEXT_MAP[c] for c in carry if c in INTRO_CARD_TEXT_MAP)
        state = getattr(shot, "text_state", "")
        verb = ("This text is already on screen and is destroyed in this shot"
                if state == "destroy" else
                "This text is already on screen and must remain unchanged")
        lines.append(f"{verb}, render verbatim: {held}")
    return lines


from canonflow_agent.flow.packets import INTRO_CARD_TEXT as INTRO_CARD_TEXT_MAP  # noqa: E402

_compile_prompts_pre_structured = compile_prompts


def compile_prompts(*, plan: dict, negatives: list[str] | None = None) -> dict:  # noqa: F811
    if plan.get("beat_id") != INTRO_BEAT_ID:
        return _compile_prompts_pre_structured(plan=plan, negatives=negatives)

    neg = _intro_negatives(negatives)
    p = BeatPlan.model_validate(plan)
    for i, s in enumerate(p.shots):
        sid = getattr(s, "shot_id", None) or f"000-{s.shot_no:02d}"
        spec = INTRO_RENDER_SPEC.get(sid)
        if spec is None:
            raise ValueError(f"intro prompt composition: unknown shot id {sid!r}")
        text_lines = _intro_text_lines(s)
        s.look.aspect_ratio = INTRO_ASPECT_RATIO
        ar = INTRO_ASPECT_RATIO
        deny = [f"Do not show {n}." for n in neg]

        s.frames.first_frame_prompt = _join(
            INTRO_BASE_VISUAL, INTRO_TYPOGRAPHY, *text_lines, spec["first"],
            f"Aspect ratio {ar}. Single still frame, no motion blur.", *deny)
        s.frames.last_frame_prompt = _join(
            INTRO_BASE_VISUAL, INTRO_TYPOGRAPHY, *text_lines, spec["last"],
            f"End of the shot after {s.duration_s} seconds. Aspect ratio {ar}. "
            "Single still frame, no motion blur.", *deny)
        still_lines = (INTRO_STILL_TEXT_OVERRIDE[sid]
                       if sid in INTRO_STILL_TEXT_OVERRIDE else text_lines)
        s.image_prompt = _join(
            INTRO_BASE_VISUAL, INTRO_TYPOGRAPHY, *still_lines, spec["still"],
            f"Aspect ratio {ar}. Single still frame, no motion blur.", *deny)
        s.video_prompt = _join(
            INTRO_BASE_VISUAL, INTRO_TYPOGRAPHY, *text_lines,
            f"Motion: {spec['motion']}", f"Audio: {spec['audio']}",
            "No spoken dialogue, no narration, no voice in this shot.",
            f"Duration {s.duration_s} seconds. Aspect ratio {ar}.", *deny)

    out = p.model_dump()
    blob = json.dumps(out, ensure_ascii=False).lower()
    for bad in ("n/a", "text_card_ids", "text_state=", "do not show on-screen text"):
        for sh in out["shots"]:
            for key in ("image_prompt", "video_prompt"):
                if bad in (sh.get(key) or "").lower():
                    raise ValueError(f"intro prompt still contains {bad!r} in {key}")
    print(f"INFO {INTRO_BEAT_ID}: structured intro prompts composed "
          f"({len(out['shots'])} shots, {len(neg)} negatives)", flush=True)
    return out


# --- intro determinism: ratio pin and single-state still frames -------------
INTRO_ASPECT_RATIO = "2.39:1"

# A still frame can only show one text state. Shot 000-05 introduces two cards
# in sequence (monotype line, then the title), so its still shows the end state.
INTRO_STILL_TEXT_OVERRIDE = {
    "000-05": [
        "Exact on-screen text, render verbatim, character for character, "
        "nothing added and nothing omitted: "
        + INTRO_CARD_TEXT_MAP["title"],
        "This is the final state of the shot: the preceding monotype line has "
        "already faded and is not visible.",
    ],
}
