"""Shared builders for snapshot export and live API responses.

Read-only. No model calls, no writes to var/runs.
"""
from __future__ import annotations

import datetime as dt
import pathlib
from typing import Any

from . import data

SNAPSHOT = pathlib.Path(__file__).resolve().parent / "snapshot"

SEGMENT_ORDER = ["intro", "prologue", "act_1", "act_2a",
                 "act_2b", "act_3", "epilogue"]


def shot_seconds(shots: list[dict]) -> int:
    return sum(int(s.get("duration_s") or 0) for s in shots)


def beat_summary(r: dict) -> dict:
    return {
        "beat": r["beat"],
        "beat_id": r["beat_id"],
        "run_id": r["run_id"],
        "segment": r["segment"],
        "start_s": r["start_s"],
        "end_s": r["end_s"],
        "verdict": r["verdict"],
        "ctx_state_ok": bool(r["ctx_state_ok"]),
        "shot_count": len(r["shots"]),
        "duration_s": shot_seconds(r["shots"]),
        "media": [p.name for p in r["media"]],
    }


def beat_detail(r: dict) -> dict:
    d = beat_summary(r)
    nodes = pathlib.Path(r["run_dir"]) / "nodes"
    d["shots"] = r["shots"]
    d["prompts"] = r["prompts"]
    d["references"] = r["references"]
    d["validate"] = data._load(nodes / "validate.json") or {}
    d["continuity_delta"] = (data._load(nodes / "merged.json") or {}).get(
        "continuity_delta")
    d["media_urls"] = ["/media/%s/%s" % (r["beat"], p.name) for p in r["media"]]
    return d


def segments(idx: dict[str, dict]) -> list[dict]:
    agg: dict[str, dict[str, Any]] = {}
    for k in sorted(idx):
        r = idx[k]
        seg = r["segment"] or "unbound"
        a = agg.setdefault(seg, {"segment": seg, "beats": 0, "duration_s": 0,
                                 "start_s": None, "end_s": None})
        a["beats"] += 1
        a["duration_s"] += shot_seconds(r["shots"])
        if r["start_s"] is not None:
            a["start_s"] = (r["start_s"] if a["start_s"] is None
                            else min(a["start_s"], r["start_s"]))
        if r["end_s"] is not None:
            a["end_s"] = (r["end_s"] if a["end_s"] is None
                          else max(a["end_s"], r["end_s"]))
    out = []
    for a in agg.values():
        both = a["start_s"] is not None and a["end_s"] is not None
        a["window_s"] = (a["end_s"] - a["start_s"]) if both else None
        a["color"] = data.SEGMENT_COLORS.get(a["segment"], "#6b7280")
        out.append(a)
    out.sort(key=lambda a: (SEGMENT_ORDER.index(a["segment"])
                            if a["segment"] in SEGMENT_ORDER else 99))
    return out


def build(idx: dict[str, dict]) -> tuple[dict, dict]:
    beats = [beat_summary(idx[k]) for k in sorted(idx)]
    verdicts: dict[str, int] = {}
    for b in beats:
        verdicts[b["verdict"]] = verdicts.get(b["verdict"], 0) + 1
    index = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(
            timespec="seconds"),
        "beat_count": len(beats),
        "shot_count": sum(b["shot_count"] for b in beats),
        "total_duration_s": sum(b["duration_s"] for b in beats),
        "media_count": sum(len(b["media"]) for b in beats),
        "verdicts": verdicts,
        "ctx_state_errors": [b["beat_id"] for b in beats
                             if not b["ctx_state_ok"]],
        "segments": segments(idx),
        "beats": beats,
    }
    details = {idx[k]["beat"]: beat_detail(idx[k]) for k in sorted(idx)}
    return index, details


# --- presentation intro (P10G-BEAT-000) ------------------------------------
# The intro is a 30 s title prelude, not one of the 44 canonical narrative
# beats. It must never enter the segment aggregation or the canon totals,
# otherwise beat_count becomes 45 and total_duration_s 540. It is reported
# separately as index["intro"] plus canon_* fields.

INTRO_BEAT_ID = "P10G-BEAT-000"
INTRO_SEGMENT = "intro"

_cf_prev_segments = segments


def segments(idx: dict[str, dict]) -> list[dict]:  # noqa: F811
    canon = {k: v for k, v in idx.items()
             if v.get("beat_id") != INTRO_BEAT_ID}
    return _cf_prev_segments(canon)


_cf_prev_build = build


def build(idx: dict[str, dict]):  # noqa: F811
    index, extra = _cf_prev_build(idx)
    all_beats = index.get("beats") or []
    intro = next((b for b in all_beats if b["beat_id"] == INTRO_BEAT_ID), None)
    canon = [b for b in all_beats if b["beat_id"] != INTRO_BEAT_ID]

    index["intro"] = intro
    index["intro_duration_s"] = intro["duration_s"] if intro else 0
    index["canon_beat_count"] = len(canon)
    index["canon_shot_count"] = sum(b["shot_count"] for b in canon)
    index["canon_duration_s"] = sum(b["duration_s"] for b in canon)
    index["showcase_duration_s"] = (index["canon_duration_s"]
                                    + index["intro_duration_s"])

    # Bound beats carry a segment window; unbound ones do not. The sum of the
    # bound windows is the fixed 510 s story clock and must stay invariant.
    segs = index.get("segments") or []
    index["canon_bound_duration_s"] = sum(
        s["duration_s"] for s in segs if s["segment"] != "unbound")
    index["canon_unbound_duration_s"] = sum(
        s["duration_s"] for s in segs if s["segment"] == "unbound")
    return index, extra
