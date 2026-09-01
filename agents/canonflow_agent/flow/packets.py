"""Bind shot_context_packets from evidence-64 to a beat, if present."""
from __future__ import annotations

import json
import pathlib
from typing import Any

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
EVIDENCE_64 = (
    REPO_ROOT
    / "docs/evidence/p10g-canon-beat-sheet"
    / "64-six-segment-showcase-selection-validation.json"
)
CAMERA_PRESETS = (
    ("wide_establishing", "controlled_push", "spatial_context"),
    ("medium_character", "restrained_tracking", "performance_and_relationship"),
    ("close_detail", "locked_or_micro_dolly", "state_prop_or_system_detail"),
    ("subjective_or_reaction", "motivated_handheld", "bounded_character_experience"),
)


def _load() -> list[dict[str, Any]]:
    if not EVIDENCE_64.is_file():
        raise FileNotFoundError(f"evidence-64 missing: {EVIDENCE_64}")
    doc = json.loads(EVIDENCE_64.read_text(encoding="utf-8"))
    packets = doc.get("shot_context_packets")
    if not isinstance(packets, list):
        raise ValueError("evidence-64: shot_context_packets is not a list")
    return packets


def bind_packets(*, beat_id: str) -> dict[str, Any]:
    """Return the authoritative shot skeleton for beat_id, or an unbound marker."""
    bound = [p for p in _load() if beat_id in (p.get("source_beat_ids") or [])]
    if not bound:
        return {
            "beat_id": beat_id,
            "bound": False,
            "camera_vocabulary": [
                {"framing": f, "movement": m, "lens_intent": l}
                for f, m, l in CAMERA_PRESETS
            ],
            "note": (
                "No shot_context_packet exists for this beat. Camera framing, "
                "movement, lens_intent, duration and scene_order are NOT "
                "externally constrained; decompose them from the beat text. "
                "Use only values from camera_vocabulary."
            ),
        }

    bound.sort(key=lambda p: p.get("shot_order", 0))
    shots = []
    for p in bound:
        cam = p.get("camera") or {}
        shots.append(
            {
                "shot_order": p.get("shot_order"),
                "shot_id": p.get("shot_id"),
                "scene_id": p.get("scene_id"),
                "scene_order": p.get("scene_order"),
                "segment_id": p.get("segment_id"),
                "phase": p.get("phase"),
                "duration_s": p.get("duration_seconds"),
                "timeline_start_s": p.get("timeline_start_seconds"),
                "timeline_end_s": p.get("timeline_end_seconds"),
                "framing": cam.get("framing"),
                "movement": cam.get("movement"),
                "lens_intent": cam.get("lens_intent"),
                "dialogue_or_voice_constraints": p.get("dialogue_or_voice_constraints"),
                "negative_constraints": p.get("negative_constraints"),
                "style_constraints": p.get("style_constraints"),
                "location_state": p.get("location_state"),
                "character_states": p.get("character_states"),
                "blocking_policy": (p.get("blocking") or {}).get("policy"),
            }
        )
    orders = [s["scene_order"] for s in shots if s["scene_order"] is not None]
    return {
        "beat_id": beat_id,
        "bound": True,
        "scene_order": orders[0] if orders else None,
        "shot_count": len(shots),
        "total_duration_s": sum(s["duration_s"] or 0 for s in shots),
        "shots": shots,
        "note": (
            "AUTHORITATIVE SKELETON. shot_count, scene_order, duration_s, "
            "framing, movement and lens_intent are fixed per shot and MUST be "
            "reproduced exactly. Generate only blocking, dialogue and prompt "
            "content inside this skeleton."
        ),
    }


# ---------------------------------------------------------------------------
# narrative segment derivation + neighbour-beat exclusions
# ---------------------------------------------------------------------------
import os as _os
import re as _re
from functools import lru_cache as _lru_cache
from pathlib import Path as _Path

BEAT_DIR = _Path(_os.environ.get("CF_BEAT_DIR", "/tmp/cf-beats"))
_MAX_EXCL_LINES = 14
_MAX_EXCL_CHARS = 220


def _beat_no(beat_id: str) -> int:
    m = _re.search(r"(\d+)\s*$", beat_id or "")
    return int(m.group(1)) if m else -1


@_lru_cache(maxsize=1)
def _segment_map() -> dict:
    """Derive the six narrative segments from timeline gaps in evidence 64."""
    import json as _json
    doc = _json.loads(EVIDENCE_64.read_text(encoding="utf-8"))
    pk = doc.get("shot_context_packets") or []
    rows = []
    for p in pk:
        so = p.get("scene_order")
        tl = p.get("timeline") or {}
        start = tl.get("start_seconds", p.get("start_seconds"))
        end = tl.get("end_seconds", p.get("end_seconds"))
        beats = p.get("source_beat_ids") or ([p["beat_id"]] if p.get("beat_id") else [])
        if so is None or start is None or end is None:
            continue
        rows.append((so, float(start), float(end), list(beats)))
    rows.sort(key=lambda r: (r[0], r[1]))

    out, seg, prev_end = {}, 1, None
    bounds = {}
    for so, start, end, beats in rows:
        if prev_end is not None and start > prev_end + 1e-6:
            seg += 1
        prev_end = max(prev_end or end, end)
        lo, hi = bounds.get(seg, (start, end))
        bounds[seg] = (min(lo, start), max(hi, end))
        for b in beats:
            out[b] = seg
    return {
        "beat_to_segment": out,
        "segment_count": seg,
        "segment_windows": {k: {"start_seconds": v[0], "end_seconds": v[1]}
                            for k, v in bounds.items()},
    }


def _segment_of(beat_id: str) -> dict:
    m = _segment_map()
    idx = m["beat_to_segment"].get(beat_id)
    if idx is None:
        return {"index": None, "of": m["segment_count"],
                "note": "beat is not part of the six-segment showcase timeline"}
    w = m["segment_windows"].get(idx, {})
    return {"index": idx, "of": m["segment_count"], **w}


def _beat_file(n: int):
    if n < 1:
        return None
    p = BEAT_DIR / f"{n:03d}.md"
    return p if p.is_file() else None


def _content_lines(path: _Path) -> list:
    lines, seen = [], set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        s = raw.strip()
        if not s or s.startswith(("#", "---", "```", "|")):
            continue
        s = _re.sub(r"^[-*+]\s+", "", s)
        s = s[:_MAX_EXCL_CHARS]
        if s.lower() in seen:
            continue
        seen.add(s.lower())
        lines.append(s)
        if len(lines) >= _MAX_EXCL_LINES:
            break
    return lines


def _neighbour_exclusions(beat_id: str) -> dict:
    n = _beat_no(beat_id)
    res = {"beat_dir": str(BEAT_DIR), "previous": None, "next": None}
    if n < 0:
        return res
    for key, num in (("previous", n - 1), ("next", n + 1)):
        p = _beat_file(num)
        if not p:
            continue
        res[key] = {
            "beat_id": _re.sub(r"\d+$", f"{num:03d}", beat_id),
            "forbidden_lines": _content_lines(p),
        }
    res["rule"] = (
        "Content listed under previous/next belongs to an ADJACENT beat. "
        "It must NOT appear in this beat's shots, dialogue, action or staging, "
        "neither verbatim nor paraphrased."
    )
    return res


_bind_packets_base = bind_packets


def bind_packets(beat_id: str, **kwargs):  # noqa: F811
    out = _bind_packets_base(beat_id=beat_id, **kwargs)
    if isinstance(out, dict):
        out["narrative_segment"] = _segment_of(beat_id)
        out["neighbour_exclusions"] = _neighbour_exclusions(beat_id)
    return out


# ---------------------------------------------------------------------------
# supersedes _segment_map/_segment_of/_content_lines above:
# packets carry segment_id + flat timeline_{start,end}_seconds; no caps.
# ---------------------------------------------------------------------------
@_lru_cache(maxsize=1)
def _segment_index() -> dict:
    import json as _json
    doc = _json.loads(EVIDENCE_64.read_text(encoding="utf-8"))
    wins, beat2seg = {}, {}
    for p in doc.get("shot_context_packets") or []:
        sid = p.get("segment_id")
        s, e = p.get("timeline_start_seconds"), p.get("timeline_end_seconds")
        if not sid or s is None or e is None:
            continue
        lo, hi = wins.get(sid, (s, e))
        wins[sid] = (min(lo, s), max(hi, e))
        for b in p.get("source_beat_ids") or []:
            beat2seg[b] = sid
    order = sorted(wins, key=lambda k: wins[k][0])
    return {"beat_to_segment": beat2seg, "windows": wins, "order": order}


def _segment_of(beat_id: str) -> dict:  # noqa: F811
    ix = _segment_index()
    sid = ix["beat_to_segment"].get(beat_id)
    if sid is None:
        return {"segment_id": None, "index": None, "of": len(ix["order"]),
                "note": "beat has no shot packet in the showcase timeline"}
    lo, hi = ix["windows"][sid]
    return {"segment_id": sid, "index": ix["order"].index(sid) + 1,
            "of": len(ix["order"]), "start_seconds": lo, "end_seconds": hi}


def _content_lines(path: _Path) -> list:  # noqa: F811
    lines, seen = [], set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        s = raw.strip()
        if not s or s.startswith(("#", "---", "```", "|")):
            continue
        s = _re.sub(r"^[-*+]\s+", "", s)
        if s.lower() in seen:
            continue
        seen.add(s.lower())
        lines.append(s)
    return lines


# ---------------------------------------------------------------------------
# pre-rendered JSON block for prompt interpolation (avoids str(dict) repr)
# ---------------------------------------------------------------------------
_bind_packets_prev = bind_packets


def bind_packets(beat_id: str, **kwargs):  # noqa: F811
    import json as _json
    out = _bind_packets_prev(beat_id=beat_id, **kwargs)
    if isinstance(out, dict):
        out["prompt_block"] = _json.dumps(out, ensure_ascii=False, indent=2)
    return out
