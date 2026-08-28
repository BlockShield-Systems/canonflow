from __future__ import annotations

import hashlib
import json
import re
import uuid
from pathlib import Path
from typing import Any, Mapping, Sequence

from canonflow_agent.production_run import (
    build_production_run,
    validate_canon_authority,
)

SCHEMA_VERSION = "1.0"
CONTRACT_VERSION = "1.0"
ARTIFACT_TYPE = "canonflow_narrative_context_scene_shot_plan"

PROJECT_ID = "e8627781-5bf3-4c4d-905f-8dda49ab53d6"
PROJECT_SLUG = "yd-when-paradise-glitches"

EVIDENCE_61_HEAD = "64622e30de9899317ced36cd74dfbd7f78ef0439"
EVIDENCE_61_TAG = "p10g-production-run-contract-v1-validated"

R4_DRAFT_SHA256 = (
    "465e5609e37d205227e854a37616ccc35f8955d22dd3de98fce108ed501a667e"
)
STORY_BIBLE_SHA256 = (
    "b53c6e01afeb38abf91e8b523cd5237b9d9cf64a949bc0d02713aae05a1e655c"
)
DEMIAN_REFERENCE_SHA256 = (
    "5ba8287cafa2fce14b03f4b505649bfc42a4a7aa916962a8dc2fbd16f0bc8c7f"
)
YD_REFERENCE_SHA256 = (
    "589a886dd5f7fcf86055e6c6aedbafe67ec238bcf3b9f8f06936a63dd7f62ef1"
)

DRAFT_PATH = Path(
    "docs/evidence/p10g-canon-beat-sheet/"
    "38-canon-beat-sheet-third-revised-draft.md"
)
STORY_BIBLE_PATH = Path(
    "docs/evidence/p10f-canon-story-bible/"
    "17-approved-canon-story-bible.md"
)
EVIDENCE_61_PATH = Path(
    "docs/evidence/p10g-canon-beat-sheet/"
    "61-production-run-contract-validation.json"
)
DEMIAN_REFERENCE_PATH = Path(
    "docs/evidence/p10g-canon-beat-sheet/reference-images/r4/"
    "demian-character-reference.jpg"
)
YD_REFERENCE_PATH = Path(
    "docs/evidence/p10g-canon-beat-sheet/reference-images/r4/"
    "yd-character-reference.jpg"
)

BEAT_PATTERN = re.compile(
    r"^##\s+P10G-BEAT-(?P<number>\d{3})\s+[–-]\s+(?P<title>.+?)\s*$"
)
FIELD_PATTERN = re.compile(
    r"^\s*\*\s+\*\*(?P<label>[^*]+?)\*\*\s*:\s*(?P<value>.*)$"
)
SECTION_PATTERN = re.compile(
    r"^(?P<marks>#{2,4})\s+(?P<title>.+?)\s*$"
)

SEGMENT_RANGES: tuple[tuple[str, int, int], ...] = (
    ("prologue", 1, 4),
    ("act_1", 5, 16),
    ("act_2a", 17, 22),
    ("act_2b", 23, 34),
    ("act_3", 35, 41),
    ("epilogue", 42, 44),
)

EDITORIAL_UNITS: tuple[dict[str, Any], ...] = (
    {
        "unit_id": "prologue_foundation",
        "first_beat_id": "P10G-BEAT-001",
        "last_beat_id": "P10G-BEAT-004",
        "depends_on": [],
        "purpose": (
            "Establish historical, political, technological, and lockdown "
            "context without exposing Demian's protected identity."
        ),
    },
    {
        "unit_id": "character_foundation",
        "first_beat_id": "P10G-BEAT-005",
        "last_beat_id": "P10G-BEAT-016",
        "depends_on": ["prologue_foundation"],
        "purpose": (
            "Establish Demian, Y.D., their relationship, humor, dependency, "
            "voice progression, isolation, and the first local escalation."
        ),
    },
    {
        "unit_id": "escalation_bridge",
        "first_beat_id": "P10G-BEAT-017",
        "last_beat_id": "P10G-BEAT-022",
        "depends_on": [
            "prologue_foundation",
            "character_foundation",
        ],
        "purpose": (
            "Bridge the character foundation into the selected survival and "
            "reality-distortion material."
        ),
    },
    {
        "unit_id": "act_2b",
        "first_beat_id": "P10G-BEAT-023",
        "last_beat_id": "P10G-BEAT-034",
        "depends_on": [
            "prologue_foundation",
            "character_foundation",
            "escalation_bridge",
        ],
        "purpose": (
            "Provide the principal reality-distortion and survival escalation."
        ),
    },
    {
        "unit_id": "act_3",
        "first_beat_id": "P10G-BEAT-035",
        "last_beat_id": "P10G-BEAT-041",
        "depends_on": [
            "prologue_foundation",
            "character_foundation",
            "escalation_bridge",
            "act_2b",
        ],
        "purpose": (
            "Deliver the final confrontation and Demian's positive change "
            "without asserting an objective corruption cause."
        ),
    },
    {
        "unit_id": "epilogue",
        "first_beat_id": "P10G-BEAT-042",
        "last_beat_id": "P10G-BEAT-044",
        "depends_on": [
            "prologue_foundation",
            "character_foundation",
            "escalation_bridge",
            "act_2b",
            "act_3",
        ],
        "purpose": (
            "Present the open philosophical resolution and competing faction "
            "interpretations without falsely resolving Y.D.'s status."
        ),
    },
)


class SceneShotCompilerError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SceneShotCompilerError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )


def deterministic_uuid(scope: str, value: Any) -> str:
    namespace = uuid.UUID("3587caae-1d44-4e90-8ea2-d1142843717e")
    payload = f"{PROJECT_ID}:{scope}:{canonical_json(value)}"
    return str(uuid.uuid5(namespace, payload))


def normalize_field_name(value: str) -> str:
    normalized = value.strip().lower()
    normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
    return normalized.strip("_")


def segment_for_beat(number: int) -> str:
    for segment_id, first_number, last_number in SEGMENT_RANGES:
        if first_number <= number <= last_number:
            return segment_id

    raise SceneShotCompilerError(
        f"Beat number is outside the segment catalog: {number}"
    )


def beat_ids(first_number: int = 1, last_number: int = 44) -> list[str]:
    return [
        f"P10G-BEAT-{number:03d}"
        for number in range(first_number, last_number + 1)
    ]


def parse_canon_beats(
    path: Path,
    *,
    source_path: str | None = None,
) -> tuple[dict[str, Any], ...]:
    locator_path = source_path or path.as_posix()
    lines = path.read_text(encoding="utf-8").splitlines()
    beats: list[dict[str, Any]] = []

    current_number: int | None = None
    current_title = ""
    current_start_line = 0
    current_fields: list[dict[str, str]] = []
    current_field_label: str | None = None
    current_field_lines: list[str] = []

    def flush_field() -> None:
        nonlocal current_field_label
        nonlocal current_field_lines

        if current_field_label is None:
            return

        current_fields.append(
            {
                "label": current_field_label,
                "key": normalize_field_name(current_field_label),
                "value": "\n".join(current_field_lines).strip(),
            }
        )
        current_field_label = None
        current_field_lines = []

    def flush_beat(end_line: int) -> None:
        nonlocal current_number
        nonlocal current_title
        nonlocal current_start_line
        nonlocal current_fields

        if current_number is None:
            return

        flush_field()

        beats.append(
            {
                "beat_id": f"P10G-BEAT-{current_number:03d}",
                "beat_number": current_number,
                "title": current_title,
                "segment_id": segment_for_beat(current_number),
                "source_locator": {
                    "path": locator_path,
                    "start_line": current_start_line,
                    "end_line": end_line,
                },
                "field_count": len(current_fields),
                "field_sequence": [
                    field["label"]
                    for field in current_fields
                ],
                "fields": {
                    field["key"]: field["value"]
                    for field in current_fields
                },
            }
        )

        current_number = None
        current_title = ""
        current_start_line = 0
        current_fields = []

    for line_number, line in enumerate(lines, start=1):
        if current_number is not None and line.startswith("# "):
            flush_beat(line_number - 1)
            continue

        beat_match = BEAT_PATTERN.match(line)

        if beat_match:
            flush_beat(line_number - 1)
            current_number = int(beat_match.group("number"))
            current_title = beat_match.group("title").strip()
            current_start_line = line_number
            continue

        if current_number is None:
            continue

        field_match = FIELD_PATTERN.match(line)

        if field_match:
            flush_field()
            current_field_label = field_match.group("label").strip()
            current_field_lines = [field_match.group("value").strip()]
        elif current_field_label is not None:
            current_field_lines.append(line.rstrip())

    flush_beat(len(lines))

    require(len(beats) == 44, f"Expected 44 beats, found {len(beats)}.")
    require(
        [beat["beat_id"] for beat in beats] == beat_ids(),
        "Beat identifiers are incomplete or out of order.",
    )
    require(
        all(beat["field_count"] == 16 for beat in beats),
        "Every beat must contain exactly 16 structured fields.",
    )
    require(
        len({tuple(beat["field_sequence"]) for beat in beats}) == 1,
        "All beats must use one consistent 16-field sequence.",
    )

    return tuple(beats)


def index_markdown_sections(
    path: Path,
    *,
    source_path: str | None = None,
) -> tuple[dict[str, Any], ...]:
    locator_path = source_path or path.as_posix()
    lines = path.read_text(encoding="utf-8").splitlines()
    headings: list[tuple[int, int, str]] = []

    for line_number, line in enumerate(lines, start=1):
        match = SECTION_PATTERN.match(line)

        if match:
            headings.append(
                (
                    line_number,
                    len(match.group("marks")),
                    match.group("title").strip(),
                )
            )

    sections: list[dict[str, Any]] = []

    for index, (start_line, level, title) in enumerate(headings):
        end_line = (
            headings[index + 1][0] - 1
            if index + 1 < len(headings)
            else len(lines)
        )
        content = "\n".join(lines[start_line - 1:end_line]).strip()

        locator = {
            "path": locator_path,
            "start_line": start_line,
            "end_line": end_line,
        }

        sections.append(
            {
                "section_id": deterministic_uuid(
                    "story-bible-section",
                    {
                        "title": title,
                        "heading_level": level,
                        "source_locator": locator,
                    },
                ),
                "title": title,
                "heading_level": level,
                "source_locator": locator,
                "content_sha256": hashlib.sha256(
                    content.encode("utf-8")
                ).hexdigest(),
            }
        )

    require(sections, "No Story Bible sections were detected.")
    return tuple(sections)


def matching_section_ids(
    sections: Sequence[Mapping[str, Any]],
    keywords: Sequence[str],
) -> list[str]:
    normalized_keywords = tuple(keyword.lower() for keyword in keywords)

    return [
        str(section["section_id"])
        for section in sections
        if any(
            keyword in str(section["title"]).lower()
            for keyword in normalized_keywords
        )
    ]


def build_identity_packs(
    repository_root: Path,
) -> list[dict[str, Any]]:
    demian_path = repository_root / DEMIAN_REFERENCE_PATH
    yd_path = repository_root / YD_REFERENCE_PATH

    require(demian_path.is_file(), "Demian reference image is missing.")
    require(yd_path.is_file(), "Y.D. reference image is missing.")
    require(
        sha256_file(demian_path) == DEMIAN_REFERENCE_SHA256,
        "Demian reference image SHA-256 mismatch.",
    )
    require(
        sha256_file(yd_path) == YD_REFERENCE_SHA256,
        "Y.D. reference image SHA-256 mismatch.",
    )

    return [
        {
            "identity_pack_id": "P10G-IDENTITY-DEMIAN-V1",
            "character_id": "demian",
            "character_version": "r4-final-canon",
            "authority": "Demian",
            "asset": {
                "path": DEMIAN_REFERENCE_PATH.as_posix(),
                "sha256": DEMIAN_REFERENCE_SHA256,
                "mime_type": "image/jpeg",
                "width": 2752,
                "height": 1536,
                "view_layout": "multi_view_reference_sheet",
            },
            "stable_traits": [
                "recognizable facial structure",
                "core physical identity",
                "approved creator-owned likeness",
            ],
            "state_dependent_traits": [
                "wardrobe",
                "hair styling",
                "expression",
                "injury state",
                "dehydration state",
                "wetness",
                "lighting",
                "environment",
            ],
            "usage_policy": {
                "automatic_public_export_allowed": False,
                "external_model_submission_allowed": False,
                "explicit_workflow_approval_required": True,
                "identity_and_character_state_are_separate": True,
            },
        },
        {
            "identity_pack_id": "P10G-IDENTITY-YD-V1",
            "character_id": "yd",
            "character_version": "r4-final-canon",
            "authority": "Demian",
            "asset": {
                "path": YD_REFERENCE_PATH.as_posix(),
                "sha256": YD_REFERENCE_SHA256,
                "mime_type": "image/jpeg",
                "width": 2752,
                "height": 1536,
                "view_layout": "multi_view_reference_sheet",
            },
            "stable_traits": [
                "approved facial identity",
                "approved core visual identity",
            ],
            "state_dependent_traits": [
                "Your Dear presentation",
                "Your Devil presentation",
                "dual manifestation",
                "interface presentation",
                "holographic presentation",
                "voice stage",
                "lighting",
                "glitch intensity",
            ],
            "forbidden_traits": [
                'visible non-canon label UNIT "ELISE"',
                "unapproved physical embodiment claim",
                "confirmed objective internal architecture",
            ],
            "usage_policy": {
                "automatic_public_export_allowed": False,
                "external_model_submission_allowed": False,
                "explicit_workflow_approval_required": True,
                "identity_persona_and_voice_stage_are_separate": True,
            },
        },
    ]


def build_editorial_scope() -> dict[str, Any]:
    units = []

    for source_unit in EDITORIAL_UNITS:
        unit = dict(source_unit)
        first_number = int(unit["first_beat_id"].rsplit("-", 1)[1])
        last_number = int(unit["last_beat_id"].rsplit("-", 1)[1])
        unit["candidate_beat_ids"] = beat_ids(first_number, last_number)
        unit["selection_status"] = "candidate"
        units.append(unit)

    return {
        "status": "candidate_requires_human_approval",
        "presentation_scope": ["intro", "claim", "credits"],
        "required_narrative_units": [
            unit["unit_id"]
            for unit in EDITORIAL_UNITS
        ],
        "units": units,
        "candidate_beat_ids": beat_ids(),
        "selected_beat_ids": [],
        "selected_scene_ids": [],
        "target_runtime_seconds": None,
        "final_scene_count": None,
        "final_shot_count": None,
        "selection_locked": False,
    }


def build_dependency_closure() -> dict[str, Any]:
    dependencies = {
        str(unit["unit_id"]): [
            str(value)
            for value in unit["depends_on"]
        ]
        for unit in EDITORIAL_UNITS
    }

    def resolve(unit_id: str, result: set[str]) -> None:
        for dependency in dependencies[unit_id]:
            if dependency not in result:
                result.add(dependency)
                resolve(dependency, result)

    closure: dict[str, list[str]] = {}

    for unit_id in dependencies:
        resolved: set[str] = set()
        resolve(unit_id, resolved)
        closure[unit_id] = [
            candidate
            for candidate in dependencies
            if candidate in resolved
        ]

    return {
        "algorithm": "deterministic_editorial_unit_transitive_closure",
        "unit_dependencies": dependencies,
        "unit_dependency_closure": closure,
        "context_transfer_policy": (
            "Dependencies transfer compact state summaries and source "
            "locators, not complete prior beat text."
        ),
    }


def build_scene_packet(
    beat: Mapping[str, Any],
    story_context_ids: Mapping[str, Sequence[str]],
) -> dict[str, Any]:
    fields = dict(beat["fields"])
    beat_hash = hashlib.sha256(
        canonical_json(beat).encode("utf-8")
    ).hexdigest()

    return {
        "scene_context_packet_id": deterministic_uuid(
            "scene-context-packet",
            {
                "beat_id": beat["beat_id"],
                "beat_sha256": beat_hash,
                "draft_sha256": R4_DRAFT_SHA256,
            },
        ),
        "status": "source_context_compiled",
        "beat_id": beat["beat_id"],
        "segment_id": beat["segment_id"],
        "title": beat["title"],
        "source_locator": beat["source_locator"],
        "source_sha256": beat_hash,
        "source_field_count": beat["field_count"],
        "source_fields": fields,
        "required_context_references": {
            key: list(value)
            for key, value in story_context_ids.items()
        },
        "continuity_state": {
            "input_state": "must_be_resolved_before_generation",
            "output_state": "must_be_recorded_after_approved_generation",
            "identity_and_character_state_are_separate": True,
            "yd_identity_persona_and_voice_stage_are_separate": True,
        },
        "knowledge_boundary_policy": {
            "future_knowledge_injection_allowed": False,
            "corruption_cause_may_be_resolved": False,
        },
        "provider_context_status": "not_materialized",
        "generation_authorized": False,
    }


def build_clarification_requests() -> list[dict[str, Any]]:
    return [
        {
            "question_id": "P10G-QUESTION-001",
            "scope": "editorial_render_scope",
            "field": "selection_strategy",
            "question": (
                "Which editorial selection strategy should be used for the "
                "showcase?"
            ),
            "options": [
                {
                    "value": "balanced_narrative_showcase",
                    "label": "Balanced narrative showcase",
                    "effect": (
                        "Balances foundation, relationship, escalation, "
                        "confrontation, and epilogue."
                    ),
                },
                {
                    "value": "character_arc_priority",
                    "label": "Character arc priority",
                    "effect": (
                        "Allocates more runtime to Demian and Y.D.'s "
                        "relationship and emotional progression."
                    ),
                },
                {
                    "value": "visual_spectacle_priority",
                    "label": "Visual spectacle priority",
                    "effect": (
                        "Allocates more runtime to the Villa, survival set "
                        "pieces, and reality distortion."
                    ),
                },
            ],
            "recommended_value": "balanced_narrative_showcase",
            "allow_custom_answer": True,
            "blocking": True,
        },
        {
            "question_id": "P10G-QUESTION-002",
            "scope": "editorial_render_scope",
            "field": "target_runtime_seconds",
            "question": "What target runtime should the showcase use?",
            "options": [
                {
                    "value": 480,
                    "label": "8 minutes",
                    "effect": "Requires aggressive editorial compression.",
                },
                {
                    "value": 600,
                    "label": "10 minutes",
                    "effect": (
                        "Balances narrative clarity and production scope."
                    ),
                },
                {
                    "value": 720,
                    "label": "12 minutes",
                    "effect": (
                        "Allows more character, dialogue, and transition time."
                    ),
                },
            ],
            "recommended_value": 600,
            "allow_custom_answer": True,
            "blocking": True,
        },
        {
            "question_id": "P10G-QUESTION-003",
            "scope": "provider_workflows",
            "field": "external_model_submission",
            "question": (
                "May the private character reference sheets be sent to an "
                "explicitly selected Google media-generation workflow?"
            ),
            "options": [
                {
                    "value": "approve_selected_google_workflow_only",
                    "label": "Approve selected Google workflow only",
                    "effect": (
                        "Allows reference submission only to a later "
                        "explicitly named and approved workflow."
                    ),
                },
                {
                    "value": "do_not_submit_reference_images",
                    "label": "Do not submit reference images",
                    "effect": (
                        "Uses text-only identity guidance with reduced "
                        "identity consistency."
                    ),
                },
            ],
            "recommended_value": "approve_selected_google_workflow_only",
            "allow_custom_answer": True,
            "blocking": True,
        },
    ]


def build_scene_shot_plan(repository_root: Path) -> dict[str, Any]:
    repository_root = repository_root.resolve()

    draft_path = repository_root / DRAFT_PATH
    story_bible_path = repository_root / STORY_BIBLE_PATH
    evidence_61_path = repository_root / EVIDENCE_61_PATH

    require(draft_path.is_file(), "R4 Canon Beat Sheet is missing.")
    require(story_bible_path.is_file(), "Approved Story Bible is missing.")
    require(evidence_61_path.is_file(), "Evidence 61 is missing.")

    require(
        sha256_file(draft_path) == R4_DRAFT_SHA256,
        "R4 Canon Beat Sheet SHA-256 mismatch.",
    )
    require(
        sha256_file(story_bible_path) == STORY_BIBLE_SHA256,
        "Approved Story Bible SHA-256 mismatch.",
    )

    evidence_61 = json.loads(
        evidence_61_path.read_text(encoding="utf-8")
    )

    require(
        evidence_61.get("status") == "validated",
        "Evidence 61 is not validated.",
    )
    require(
        evidence_61.get("canon_binding", {}).get("draft_sha256")
        == R4_DRAFT_SHA256,
        "Evidence 61 does not bind the expected R4 draft.",
    )

    canon_authority = validate_canon_authority(repository_root)
    production_run = build_production_run(
        repository_root,
        profile="full_feature",
    )

    beats = parse_canon_beats(
        draft_path,
        source_path=DRAFT_PATH.as_posix(),
    )
    story_sections = index_markdown_sections(
        story_bible_path,
        source_path=STORY_BIBLE_PATH.as_posix(),
    )

    story_context_ids = {
        "premise_genre_tone_themes": matching_section_ids(
            story_sections,
            ("premise", "genre", "tone", "themes"),
        ),
        "character_bible": matching_section_ids(
            story_sections,
            ("character bible",),
        ),
        "relationship_arc": matching_section_ids(
            story_sections,
            ("relationship arc",),
        ),
        "visual_production_language": matching_section_ids(
            story_sections,
            ("visual and production language",),
        ),
        "dialogue_voice_sound_performance": matching_section_ids(
            story_sections,
            ("dialogue", "voice", "sound", "performance"),
        ),
        "unresolved_and_approval_boundaries": matching_section_ids(
            story_sections,
            ("unresolved", "approval"),
        ),
    }

    for category in (
        "premise_genre_tone_themes",
        "character_bible",
        "relationship_arc",
        "visual_production_language",
        "dialogue_voice_sound_performance",
    ):
        require(
            bool(story_context_ids[category]),
            f"Required Story Bible context is missing: {category}",
        )

    scene_packets = [
        build_scene_packet(beat, story_context_ids)
        for beat in beats
    ]
    identity_packs = build_identity_packs(repository_root)
    clarification_requests = build_clarification_requests()

    context_index = {
        "index_type": "deterministic_source_locator_index",
        "vector_index_is_canon_authority": False,
        "story_bible_sections": list(story_sections),
        "beat_index": [
            {
                "beat_id": beat["beat_id"],
                "segment_id": beat["segment_id"],
                "title": beat["title"],
                "source_locator": beat["source_locator"],
                "field_keys": list(beat["fields"]),
            }
            for beat in beats
        ],
        "retrieval_policy": {
            "required_exact_filters": [
                "project_id",
                "canon_version",
                "beat_id_or_editorial_unit",
                "character_id",
                "timeline_scope",
                "knowledge_boundary",
            ],
            "exact_filters_precede_semantic_retrieval": True,
            "semantic_retrieval_allowed_after_exact_filters": True,
            "provider_packet_must_use_minimum_required_context": True,
            "complete_canon_dump_to_media_model_allowed": False,
        },
    }

    plan_basis = {
        "project_id": PROJECT_ID,
        "draft_sha256": R4_DRAFT_SHA256,
        "story_bible_sha256": STORY_BIBLE_SHA256,
        "evidence_61_sha256": sha256_file(evidence_61_path),
        "identity_sha256s": [
            DEMIAN_REFERENCE_SHA256,
            YD_REFERENCE_SHA256,
        ],
        "editorial_units": EDITORIAL_UNITS,
        "beat_parser_boundary_policy": (
            "top_level_heading_terminates_active_beat"
        ),
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "contract_version": CONTRACT_VERSION,
        "artifact_type": ARTIFACT_TYPE,
        "status": "compiled_pending_human_clarification",
        "plan_id": deterministic_uuid("scene-shot-plan", plan_basis),
        "project": {
            "project_id": PROJECT_ID,
            "project_slug": PROJECT_SLUG,
        },
        "baseline": {
            "evidence_61_head": EVIDENCE_61_HEAD,
            "evidence_61_tag": EVIDENCE_61_TAG,
            "evidence_61_path": EVIDENCE_61_PATH.as_posix(),
            "evidence_61_sha256": sha256_file(evidence_61_path),
        },
        "canon_binding": {
            "draft_path": DRAFT_PATH.as_posix(),
            "draft_sha256": R4_DRAFT_SHA256,
            "story_bible_path": STORY_BIBLE_PATH.as_posix(),
            "story_bible_sha256": STORY_BIBLE_SHA256,
            "story_bible_git_state": "must_be_committed_with_evidence_62",
            "authority_validation": canon_authority,
        },
        "production_run_binding": {
            "profile": "full_feature",
            "production_run": production_run,
        },
        "narrative_context_scope": {
            "beat_count": 44,
            "first_beat_id": "P10G-BEAT-001",
            "last_beat_id": "P10G-BEAT-044",
            "beat_ids": beat_ids(),
            "field_count_per_beat": 16,
            "field_sequence": list(beats[0]["field_sequence"]),
            "beat_boundary_policy": (
                "top_level_heading_terminates_active_beat"
            ),
            "all_approved_canon_available": True,
            "complete_canon_sent_to_media_models": False,
        },
        "editorial_render_scope": build_editorial_scope(),
        "dependency_closure": build_dependency_closure(),
        "character_identity_packs": identity_packs,
        "canonical_context_index": context_index,
        "scene_context_packets": scene_packets,
        "shot_context_packet_contract": {
            "status": "schema_defined_instances_deferred",
            "instance_count": 0,
            "required_fields": [
                "shot_id",
                "scene_id",
                "source_beat_ids",
                "duration_seconds",
                "camera",
                "blocking",
                "character_states",
                "location_state",
                "identity_asset_bindings",
                "continuity_input",
                "continuity_output",
                "style_constraints",
                "dialogue_or_voice_constraints",
                "negative_constraints",
                "provider_adapter",
                "source_hashes",
            ],
            "creation_preconditions": [
                "editorial selection approved",
                "target runtime approved",
                "scene boundaries approved",
                "identity workflow approved",
            ],
        },
        "retrieval_trace": {
            "status": "deterministic_index_compiled",
            "provider_retrieval_not_performed": True,
            "network_retrieval_not_performed": True,
            "trace_required_for_each_future_provider_request": True,
        },
        "excluded_context": {
            "future_knowledge_must_not_be_injected": True,
            "superseded_facts_must_not_be_retrieved": True,
            "unapproved_story_facts_must_not_be_generated": True,
            "yd_corruption_cause_must_not_be_confirmed": True,
            "complete_canon_dump_to_media_models_forbidden": True,
        },
        "ambiguity_report": {
            "status": "clarification_required",
            "blocking_issue_count": 3,
            "issues": [
                {
                    "issue_id": "P10G-CLR-001",
                    "field": "selected_beat_ids",
                    "severity": "blocking",
                },
                {
                    "issue_id": "P10G-CLR-002",
                    "field": "target_runtime_seconds",
                    "severity": "blocking",
                },
                {
                    "issue_id": "P10G-CLR-003",
                    "field": "external_model_submission",
                    "severity": "blocking",
                },
            ],
        },
        "clarification_requests": clarification_requests,
        "human_approval": {
            "required": True,
            "status": "pending",
            "approved_question_ids": [],
        },
        "security": {
            "network_access_performed": False,
            "http_request_performed": False,
            "gemini_request_performed": False,
            "media_generation_performed": False,
            "database_access_performed": False,
            "database_mutation_performed": False,
            "executor_invoked": False,
            "credentials_persisted": False,
            "reference_images_transmitted": False,
        },
        "generation_authorized": False,
    }


def write_scene_shot_plan(
    output_path: Path,
    plan: Mapping[str, Any],
) -> None:
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    payload = json.dumps(
        plan,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
    )

    with output_path.open("x", encoding="utf-8", newline="\n") as target:
        target.write(payload)
        target.write("\n")
