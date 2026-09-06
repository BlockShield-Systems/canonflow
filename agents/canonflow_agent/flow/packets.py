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


# ---------------------------------------------------------------------------
# presentation intro beat P10G-BEAT-000
# NOT a canonical narrative beat. Canonical narrative beat count stays 44.
# Occupies a separate 30 s presentation clock; the 510 s narrative timeline
# and all canonical segment windows remain unchanged.
# ---------------------------------------------------------------------------
INTRO_BEAT_ID = "P10G-BEAT-000"
INTRO_TOTAL_DURATION_S = 30
INTRO_SEGMENT_ID = "intro"

# (shot_order, shot_id, duration_s, camera_preset_index)
_INTRO_SHOT_PLAN = (
    (1, "000-01", 9, 2),
    (2, "000-02", 6, 2),
    (3, "000-03", 4, 2),
    (4, "000-04", 2, 3),
    (5, "000-05", 5, 0),
    (6, "000-06", 4, 1),
)

# Authoritative on-screen text. attribution=None means: no author name,
# no dash prefix, never presented as a quotation.
INTRO_TEXT_CARDS = (
    {
        "card_id": "epigraph_part_1",
        "shot_id": "000-01",
        "text": "Loneliness does not come from having no people about one,",
        "attribution": None,
        "attribution_pending_completion": True,
        "typography": "clean clinical sans-serif or modern monospace, #FFFFFF or #F2F2F2 on #000000",
    },
    {
        "card_id": "epigraph_part_2",
        "shot_id": "000-02",
        "text": "but from being unable to communicate the things that seem important to oneself.",
        "attribution": "C. G. JUNG",
        "attribution_status": "verbatim_primary_source_unverified",
        "attribution_layout": "right-aligned under the quote, prefixed by an en dash",
        "typography": "same face as epigraph_part_1",
    },
    {
        "card_id": "overwrite_line",
        "shot_id": "000-05",
        "text": "...we built machines that simulate the longing - a new spirit, or the abyss of our own unstilled loneliness?",
        "attribution": None,
        "attribution_status": "original_film_text",
        "hold_s": 2.5,
        "typography": "monospace, colder, system-text character; must differ from the epigraph face",
        "policy": "NO author name, NO dash prefix, NO attribution. This is the film's own voice, not a quotation.",
    },
    {
        "card_id": "title",
        "shot_id": "000-05",
        "text": "Y.D. - WHEN PARADISE GLITCHES",
        "attribution": None,
        "typography": "stark, flawless, centered, white/off-white on pure black",
    },
    {
        "card_id": "credit",
        "shot_id": "000-06",
        "text": "Written & Directed by Demian Lienert",
        "attribution": None,
        "typography": "smaller, elegant, centered",
    },
)

_INTRO_NEGATIVE_CONSTRAINTS = [
    "no diegetic location, no set, no environment geometry",
    "no characters on screen, no faces, no bodies, no hands",
    "no canon facts, no plot events, no factions, no history",
    "no reference images, no character asset binding",
    "no content from P10G-BEAT-001 other than the closing audio handoff in 000-06",
    "no invented wording on any text card; card text is verbatim",
]

# Lines in 000.md that describe the handoff INTO beat 001. They must not be
# exported as neighbour exclusions, otherwise beat 001 would receive its own
# core content (Harrison Blake, quad-split documentary) as a forbidden line.
_INTRO_HANDOFF_MARKERS = (
    "harrison blake",
    "quad-split",
    "quad split",
    "historical documentary",
    "crossfade",
    "p10g-beat-001",
)


def _intro_packet() -> dict:
    shots, cursor = [], 0
    for order, shot_id, dur, preset in _INTRO_SHOT_PLAN:
        framing, movement, lens_intent = CAMERA_PRESETS[preset]
        cards = [c["card_id"] for c in INTRO_TEXT_CARDS if c["shot_id"] == shot_id]
        shots.append(
            {
                "shot_order": order,
                "shot_id": shot_id,
                "scene_id": "SC-000",
                "scene_order": 0,
                "segment_id": INTRO_SEGMENT_ID,
                "phase": "presentation_intro",
                "duration_s": dur,
                "timeline_start_s": cursor,
                "timeline_end_s": cursor + dur,
                "timeline_clock": "presentation",
                "framing": framing,
                "movement": movement,
                "lens_intent": lens_intent,
                "hero_render": False,
                "dialogue_or_voice_constraints": {
                    "dialogue_allowed": False,
                    "voice_over_allowed": shot_id == "000-06",
                    "yd_voice_stage": None,
                    "authoritative_canon_mutation_allowed": False,
                },
                "negative_constraints": list(_INTRO_NEGATIVE_CONSTRAINTS),
                "style_constraints": [
                    "pure black background, no imagery",
                    "typography and post effects only",
                ],
                "location_state": {
                    "location_id": "absolute_digital_void",
                    "diegetic": False,
                    "description": "black screen, no spatial content",
                },
                "character_states": [],
                "blocking_policy": "no physical blocking; on-screen text only",
                "text_card_ids": cards,
            }
        )
        cursor += dur
    assert cursor == INTRO_TOTAL_DURATION_S, f"intro duration drift: {cursor}"
    return {
        "beat_id": INTRO_BEAT_ID,
        "bound": True,
        "presentation_intro": True,
        "canonical_narrative_beat": False,
        "scene_order": 0,
        "shot_count": len(shots),
        "total_duration_s": cursor,
        "shots": shots,
        "text_cards": [dict(c) for c in INTRO_TEXT_CARDS],
        "reference_policy": {
            "transmit_reference_images": False,
            "character_assets": [],
            "rag_bulk_dump": False,
            "state_json_ingestion": False,
            "note": "Intro carries no character or location assets. Resolve nothing.",
        },
        "handoff_exception": {
            "shot_id": "000-06",
            "allowed": "audio-only crossfade into Harrison Blake's voice-over",
            "forbidden": "any image content, dialogue line or documentary material from P10G-BEAT-001",
        },
        "note": (
            "AUTHORITATIVE SKELETON for the presentation intro. shot_count, "
            "scene_order, duration_s, framing, movement and lens_intent are fixed "
            "and MUST be reproduced exactly. text_cards are verbatim on-screen "
            "text; do not reword, translate, merge or re-attribute them. This beat "
            "adds no narrative canon and does not alter the 44 canonical beats or "
            "the 510 s narrative timeline."
        ),
    }


def _beat_file(n: int):  # noqa: F811
    """Supersedes the n<1 guard so 000.md is a valid neighbour of 001."""
    if n < 0:
        return None
    p = BEAT_DIR / f"{n:03d}.md"
    return p if p.is_file() else None


_content_lines_pre_intro = _content_lines


def _content_lines(path: _Path) -> list:  # noqa: F811
    lines = _content_lines_pre_intro(path)
    if path.name != f"{_beat_no(INTRO_BEAT_ID):03d}.md":
        return lines
    return [
        l for l in lines
        if not any(m in l.lower() for m in _INTRO_HANDOFF_MARKERS)
    ]


_segment_of_pre_intro = _segment_of


def _segment_of(beat_id: str) -> dict:  # noqa: F811
    if beat_id == INTRO_BEAT_ID:
        ix = _segment_index()
        return {
            "segment_id": INTRO_SEGMENT_ID,
            "index": 0,
            "of": len(ix["order"]),
            "start_seconds": 0.0,
            "end_seconds": float(INTRO_TOTAL_DURATION_S),
            "timeline_clock": "presentation",
            "note": (
                "Presentation intro. index 0 means pre-roll BEFORE narrative "
                "segment 1; the intro is not one of the six narrative segments. "
                "Its window lives on a separate 30 s presentation clock and does "
                "not consume or shift the 510 s narrative timeline."
            ),
        }
    return _segment_of_pre_intro(beat_id)


_bind_packets_pre_intro = bind_packets


def bind_packets(beat_id: str, **kwargs):  # noqa: F811
    import json as _json
    if beat_id != INTRO_BEAT_ID:
        return _bind_packets_pre_intro(beat_id=beat_id, **kwargs)
    out = _intro_packet()
    out["narrative_segment"] = _segment_of(beat_id)
    out["neighbour_exclusions"] = _neighbour_exclusions(beat_id)
    out["prompt_block"] = _json.dumps(out, ensure_ascii=False, indent=2)
    return out


# ---------------------------------------------------------------------------
# Curated neighbour exclusions for the intro.
# Exporting the raw 000.md as forbidden lines pushed ~45 lines of typographic
# craft direction ("No camera movement", colour codes, face choices) into
# beat 001's prompt. Only the content that must not bleed is listed here.
# ---------------------------------------------------------------------------
INTRO_EXCLUSION_LINES = (
    'Presentation-intro on-screen epigraph: "Loneliness does not come from having no '
    'people about one, but from being unable to communicate the things that seem '
    'important to oneself." attributed on screen to C. G. JUNG.',
    'Presentation-intro on-screen unattributed line: "...we built machines that '
    'simulate the longing - a new spirit, or the abyss of our own unstilled loneliness?"',
    'Presentation-intro main title card: "Y.D. - WHEN PARADISE GLITCHES"',
    'Presentation-intro credit card: "Written & Directed by Demian Lienert"',
    "Presentation-intro glitch rupture of on-screen text: red/cyan chroma split, "
    "severe chromatic aberration, datamosh smear, frame tearing, harsh digital static "
    "burst panning left to right.",
    "Presentation-intro void staging: pure black screen with white typography as the "
    "only visible element, low-frequency server hum rising out of total silence, "
    "erratic digital clicking, single clean cinematic bass impact on the title reveal.",
)

_INTRO_FILE_NAME = f"{_beat_no(INTRO_BEAT_ID):03d}.md"
_content_lines_pre_curated = _content_lines


def _content_lines(path: _Path) -> list:  # noqa: F811
    if path.name == _INTRO_FILE_NAME:
        return list(INTRO_EXCLUSION_LINES)
    return _content_lines_pre_curated(path)


# --- intro text-state binding (P10G-BEAT-000) -------------------------------
# The intro displays text across several shots: a card is *introduced* in one
# shot and may remain on screen ("hold") or be destroyed by the glitch.
# Without this the Canon Validator reads a holding shot as unauthorised text.

INTRO_TEXT_STATE = {
    "000-01": {"text_card_ids": ["epigraph_part_1"], "text_state": "introduce",
               "visible_text_carry_over": []},
    "000-02": {"text_card_ids": ["epigraph_part_2"], "text_state": "introduce",
               "visible_text_carry_over": ["epigraph_part_1"]},
    "000-03": {"text_card_ids": [], "text_state": "hold",
               "visible_text_carry_over": ["epigraph_part_1", "epigraph_part_2"]},
    "000-04": {"text_card_ids": [], "text_state": "destroy",
               "visible_text_carry_over": ["epigraph_part_1", "epigraph_part_2"]},
    "000-05": {"text_card_ids": ["overwrite_line", "title"], "text_state": "introduce",
               "visible_text_carry_over": []},
    "000-06": {"text_card_ids": ["credit"], "text_state": "introduce",
               "visible_text_carry_over": []},
}

INTRO_DIALOGUE_RULE = (
    "audio.dialogue MUST be null for every shot of this beat. This beat contains "
    "no speech, no narration and no speaker. The hand-off to the next beat is an "
    "audio bed cross-fade only."
)

_cf_prev_bind_packets = bind_packets


def bind_packets(*args, **kwargs):  # noqa: F811
    packet = _cf_prev_bind_packets(*args, **kwargs)
    beat_id = None
    if isinstance(packet, dict):
        beat_id = packet.get("beat_id")
    if beat_id != INTRO_BEAT_ID:
        return packet

    shots = packet.get("shots") or []
    for s in shots:
        sid = s.get("id") or s.get("shot_id") or f"000-{int(s.get('order', 0)):02d}"
        state = INTRO_TEXT_STATE.get(sid)
        if state is None:
            raise ValueError(f"intro shot without text state: {sid}")
        s.update(state)
        audio = s.get("audio")
        if isinstance(audio, dict):
            audio["dialogue"] = None
        else:
            s["audio"] = {"dialogue": None}

    nc = packet.setdefault("negative_constraints", [])
    if INTRO_DIALOGUE_RULE not in nc:
        nc.append(INTRO_DIALOGUE_RULE)
    packet["text_state_contract"] = (
        "introduce = render exactly text_card_ids verbatim; "
        "hold = render no new text, visible_text_carry_over stays on screen unchanged; "
        "destroy = render no new text, visible_text_carry_over is corrupted/torn apart."
    )
    return packet


# --- canonical intro card text (single source of truth) ---------------------
# Exact codepoints. Attribution uses EN DASH U+2013 (spec prose is normative).
# overwrite_line uses EM DASH U+2014 as internal punctuation and is rendered
# without quotation marks. Title uses EN DASH U+2013.

INTRO_CARD_TEXT = {
    "epigraph_part_1": "\u201cLoneliness does not come from having no people about one,",
    "epigraph_part_2": "but from being unable to communicate the things that seem important to oneself.\u201d",
    "overwrite_line": "...we built machines that simulate the longing \u2014 a new spirit, or the abyss of our own unstilled loneliness?",
    "title": "Y.D. \u2013 WHEN PARADISE GLITCHES",
    "credit": "Written & Directed by Demian Lienert",
}
INTRO_CARD_ATTRIBUTION = {"epigraph_part_2": "\u2013 C. G. JUNG"}
INTRO_CARD_ORDER = ["epigraph_part_1", "epigraph_part_2", "overwrite_line", "title", "credit"]

INTRO_AUDIO_HANDOFF = (
    "Audio transition only: the pitch-dropped hum crossfades into the voiceover and "
    "quad-split documentary bed of P10G-BEAT-001. audio.dialogue stays null; no spoken "
    "line, speaker name or documentary content of the next beat is written into this beat."
)

_cf_prev_bind_packets_2 = bind_packets


def bind_packets(*args, **kwargs):  # noqa: F811
    packet = _cf_prev_bind_packets_2(*args, **kwargs)
    if not isinstance(packet, dict) or packet.get("beat_id") != INTRO_BEAT_ID:
        return packet

    cards = packet.get("text_cards") or []
    id_key = next((k for k in ("id", "card_id", "cid", "name")
                   if cards and k in cards[0]), None)
    for i, card in enumerate(cards):
        cid = card.get(id_key) if id_key else None
        if cid not in INTRO_CARD_TEXT:
            cid = INTRO_CARD_ORDER[i] if i < len(INTRO_CARD_ORDER) else None
        if cid is None:
            raise ValueError(f"intro card {i} not identifiable (keys: {sorted(card.keys())})")
        card[id_key or "id"] = cid
        card["text"] = INTRO_CARD_TEXT[cid]
        card["attribution"] = INTRO_CARD_ATTRIBUTION.get(cid)
        card["verbatim"] = True
    missing = set(INTRO_CARD_TEXT) - {c.get(id_key or "id") for c in cards}
    if missing:
        raise ValueError(f"intro cards missing from packet: {sorted(missing)}")

    by_id = {c[id_key or "id"]: c for c in cards}
    for s in packet.get("shots") or []:
        s["text_render"] = [
            {"card_id": cid, "text": INTRO_CARD_TEXT[cid],
             "attribution": INTRO_CARD_ATTRIBUTION.get(cid)}
            for cid in (s.get("text_card_ids") or []) if cid in by_id
        ]
        if s.get("shot_id") == "000-06":
            s["audio_handoff"] = INTRO_AUDIO_HANDOFF
    return packet
