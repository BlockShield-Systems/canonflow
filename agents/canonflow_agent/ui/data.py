"""Read-only index over var/runs. No writes, no model calls."""
from __future__ import annotations

import json
import pathlib
import re
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[3]
RUNS = ROOT / "var" / "runs"
BEAT_RE = re.compile(r"P10G-BEAT-(\d{3})")

SEGMENT_COLORS = {
    "intro": "#9aa0a6",
    "prologue": "#5b8def", "act_1": "#48c78e", "act_2a": "#f0b429",
    "act_2b": "#e8743b", "act_3": "#d9435f", "epilogue": "#8b5cf6",
}


def _unwrap(obj: Any) -> Any:
    while isinstance(obj, dict) and "output" in obj and len(obj) <= 4:
        obj = obj["output"]
    return obj


def _load(path: pathlib.Path) -> Any:
    if not path.exists():
        return None
    try:
        return _unwrap(json.loads(path.read_text(encoding="utf-8")))
    except json.JSONDecodeError:
        return None


def scan() -> dict[str, dict]:
    """Latest run per beat id that produced merged.json."""
    found: dict[str, dict] = {}
    if not RUNS.is_dir():
        return found
    for d in sorted(RUNS.iterdir(), key=lambda p: p.stat().st_mtime):
        nodes = d / "nodes"
        merged = _load(nodes / "merged.json")
        if not merged:
            continue
        pk = nodes / "packets.json"
        raw = pk.read_text(encoding="utf-8") if pk.exists() else ""
        m = BEAT_RE.search(raw)
        if not m:
            continue
        packets = _load(pk) or {}
        validate = _load(nodes / "validate.json") or {}
        seg = packets.get("narrative_segment") or {}
        media = sorted((d / "media").glob("*")) if (d / "media").is_dir() else []
        found[m.group(1)] = {
            "beat": m.group(1),
            "beat_id": "P10G-BEAT-" + m.group(1),
            "run_id": d.name,
            "run_dir": d,
            "segment": seg.get("segment_id"),
            "start_s": seg.get("start_seconds"),
            "end_s": seg.get("end_seconds"),
            "verdict": validate.get("verdict", "?"),
            "ctx_state_ok": not (nodes / "ctx_state.error.txt").exists(),
            "shots": merged.get("shots", []),
            "prompts": _load(nodes / "prompts.json") or {},
            "references": _load(nodes / "references.json") or {},
            "media": media,
        }
    return found


def overview_rows(idx: dict[str, dict]) -> list[list]:
    rows = []
    for k in sorted(idx):
        r = idx[k]
        shots = r["shots"]
        rows.append([
            r["beat_id"], r["segment"] or "-", len(shots),
            sum(int(s.get("duration_s") or 0) for s in shots),
            r["verdict"], "ok" if r["ctx_state_ok"] else "ERR",
            len(r["media"]), r["run_id"],
        ])
    return rows


def timeline_html(idx: dict[str, dict]) -> str:
    total = sum(sum(int(s.get("duration_s") or 0) for s in r["shots"])
                for r in idx.values())
    cells = []
    for k in sorted(idx):
        r = idx[k]
        col = SEGMENT_COLORS.get(r["segment"] or "", "#666")
        bad = r["verdict"] != "PASS"
        for s in r["shots"]:
            d = int(s.get("duration_s") or 0)
            tip = "{} shot {}.{} - {}s - {}".format(
                r["beat_id"], s.get("scene_no"), s.get("shot_no"),
                d, r["verdict"])
            mark = "outline:2px solid #ff3860;outline-offset:-2px;" if bad else ""
            cells.append(
                '<div title="{}" style="flex:{} 0 auto;height:34px;'
                'background:{};border-right:1px solid #111;{}"></div>'.format(
                    tip, max(d, 1), col, mark))
    legend = " ".join(
        '<span style="display:inline-flex;align-items:center;gap:6px;'
        'margin-right:14px"><i style="width:12px;height:12px;background:{};'
        'display:inline-block;border-radius:2px"></i>{}</span>'.format(c, n)
        for n, c in SEGMENT_COLORS.items())
    return (
        '<div style="font:13px system-ui;color:#ddd">'
        '<div style="display:flex;width:100%;border-radius:4px;'
        'overflow:hidden">{}</div>'
        '<div style="margin-top:8px">{}'
        '<b style="float:right">{} s / {} beats</b></div></div>'.format(
            "".join(cells), legend, total, len(idx)))
