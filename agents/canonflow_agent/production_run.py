from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


SCHEMA_VERSION = "1.0"
CONTRACT_VERSION = "1.0"
ARTIFACT_TYPE = "canonflow_production_run"

PROJECT_ID = "e8627781-5bf3-4c4d-905f-8dda49ab53d6"
PROJECT_SLUG = "yd-when-paradise-glitches"

R4_DRAFT_SHA256 = (
    "465e5609e37d205227e854a37616ccc35f8955d22dd3de98fce108ed501a667e"
)
R4_FINAL_CANON_TAG = "p10g-r4-final-canon"
R4_FINAL_CANON_COMMIT = "9f7898c47c9925a26ba26a4f6cb95ef90c232ac3"

EVIDENCE_DIRECTORY = Path(
    "docs/evidence/p10g-canon-beat-sheet"
)
DRAFT_PATH = (
    EVIDENCE_DIRECTORY
    / "38-canon-beat-sheet-third-revised-draft.md"
)
SEMANTIC_VALIDATION_PATH = (
    EVIDENCE_DIRECTORY
    / "41-r4-semantic-validation.json"
)
HUMAN_REVIEW_PATH = (
    EVIDENCE_DIRECTORY
    / "42-r4-human-review.md"
)
HUMAN_DECISIONS_PATH = (
    EVIDENCE_DIRECTORY
    / "43-r4-final-human-review-decisions.json"
)
HUMAN_COMPLETION_PATH = (
    EVIDENCE_DIRECTORY
    / "44-r4-final-human-review-completion.json"
)
TELEMETRY_CONTRACT_PATH = (
    EVIDENCE_DIRECTORY
    / "45-p10g-telemetry-event-contract-v1.json"
)

REQUIRED_CANON_PATHS = (
    DRAFT_PATH,
    SEMANTIC_VALIDATION_PATH,
    HUMAN_REVIEW_PATH,
    HUMAN_DECISIONS_PATH,
    HUMAN_COMPLETION_PATH,
    TELEMETRY_CONTRACT_PATH,
)

SEGMENT_RANGES: Mapping[str, tuple[int, int]] = {
    "prologue": (1, 4),
    "act_1": (5, 16),
    "act_2a": (17, 22),
    "act_2b": (23, 34),
    "act_3": (35, 41),
    "epilogue": (42, 44),
}

SEGMENT_TITLES: Mapping[str, str] = {
    "prologue": "Prologue",
    "act_1": "Act 1",
    "act_2a": "Act 2A",
    "act_2b": "Act 2B",
    "act_3": "Act 3",
    "epilogue": "Epilogue",
}

SEGMENT_ORDER = tuple(SEGMENT_RANGES)

PROFILE_SEGMENTS: Mapping[str, tuple[str, ...]] = {
    "full_feature": SEGMENT_ORDER,
    "showcase": SEGMENT_ORDER,
}

PROFILE_PRESENTATION_UNITS: Mapping[str, tuple[str, ...]] = {
    "full_feature": (),
    "showcase": (
        "cinematic_intro",
        "project_claims",
        "agentic_workflow_claims",
        "technology_stack",
        "cinematic_text_overlays",
        "classical_end_credits",
    ),
}

BEAT_PATTERN = re.compile(
    r"^##\s+P10G-BEAT-(\d{3})\s+[–-]\s+(.+?)\s*$"
)


class ProductionRunError(ValueError):
    """Raised when a production run violates the frozen contract."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ProductionRunError(
            f"Required canon artifact is missing: {path}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise ProductionRunError(
            f"Invalid JSON artifact {path}: {exc}"
        ) from exc

    if not isinstance(value, dict):
        raise ProductionRunError(
            f"Expected JSON object in {path}."
        )

    return value


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def deterministic_uuid(scope: str, value: Any) -> str:
    material = f"{scope}:{canonical_json(value)}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, material))


def _require(
    condition: bool,
    message: str,
) -> None:
    if not condition:
        raise ProductionRunError(message)


def _relative(path: Path) -> str:
    return path.as_posix()


def validate_canon_authority(
    repository_root: Path,
) -> dict[str, Any]:
    root = repository_root.resolve()

    resolved_paths = {
        relative_path: root / relative_path
        for relative_path in REQUIRED_CANON_PATHS
    }

    for relative_path, absolute_path in resolved_paths.items():
        _require(
            absolute_path.is_file(),
            f"Required canon artifact is missing: {relative_path}",
        )

    draft_path = resolved_paths[DRAFT_PATH]
    semantic_path = resolved_paths[SEMANTIC_VALIDATION_PATH]
    review_path = resolved_paths[HUMAN_REVIEW_PATH]
    decisions_path = resolved_paths[HUMAN_DECISIONS_PATH]
    completion_path = resolved_paths[HUMAN_COMPLETION_PATH]
    telemetry_path = resolved_paths[TELEMETRY_CONTRACT_PATH]

    actual_draft_sha256 = sha256_file(draft_path)

    _require(
        actual_draft_sha256 == R4_DRAFT_SHA256,
        "The frozen R4 draft SHA-256 does not match.",
    )

    semantic = load_json(semantic_path)
    semantic_result = semantic.get("result")

    _require(
        isinstance(semantic_result, dict),
        "Evidence 41 has no result object.",
    )
    _require(
        semantic.get("draft") == DRAFT_PATH.name,
        "Evidence 41 references an unexpected R4 draft.",
    )
    _require(
        semantic.get("draft_sha256") == R4_DRAFT_SHA256,
        "Evidence 41 has an unexpected draft SHA-256.",
    )
    _require(
        semantic.get("project_id") == PROJECT_ID,
        "Evidence 41 has an unexpected project_id.",
    )
    _require(
        semantic.get("project_slug") == PROJECT_SLUG,
        "Evidence 41 has an unexpected project_slug.",
    )
    _require(
        semantic.get("revision") == "R4",
        "Evidence 41 does not validate revision R4.",
    )
    _require(
        semantic_result.get("strict_local_validation_passed") is True,
        "R4 strict local validation did not pass.",
    )
    _require(
        semantic_result.get(
            "independent_semantic_validation_passed"
        )
        is True,
        "R4 independent semantic validation did not pass.",
    )

    decisions = load_json(decisions_path)
    decision_summary = decisions.get("summary")
    review_items = decisions.get("review_items")

    _require(
        decisions.get("draft_sha256") == R4_DRAFT_SHA256,
        "Evidence 43 is not bound to the frozen R4 draft.",
    )
    _require(
        isinstance(decision_summary, dict),
        "Evidence 43 has no summary object.",
    )
    _require(
        isinstance(review_items, list),
        "Evidence 43 has no review_items array.",
    )
    _require(
        len(review_items) == 25,
        "Evidence 43 must contain exactly 25 review items.",
    )
    _require(
        all(
            isinstance(item, dict)
            and item.get("disposition") == "approve"
            for item in review_items
        ),
        "Not all R4 human-review items are approved.",
    )
    _require(
        decision_summary.get("approved") == 25,
        "Evidence 43 must report 25 approved review items.",
    )
    _require(
        decision_summary.get("human_review_completed") is True,
        "Evidence 43 does not complete human review.",
    )
    _require(
        decision_summary.get("approved_as_final_canon") is True,
        "Evidence 43 does not approve R4 as final canon.",
    )
    _require(
        decision_summary.get("final_disposition") == "approve",
        "Evidence 43 final disposition is not approve.",
    )

    completion = load_json(completion_path)
    bindings = completion.get("bindings")

    _require(
        completion.get("status") == "completed",
        "Evidence 44 is not completed.",
    )
    _require(
        completion.get("human_review_completed") is True,
        "Evidence 44 does not confirm completed human review.",
    )
    _require(
        completion.get("approved_as_final_canon") is True,
        "Evidence 44 does not approve final canon.",
    )
    _require(
        completion.get("final_disposition") == "approve",
        "Evidence 44 final disposition is not approve.",
    )
    _require(
        isinstance(bindings, dict),
        "Evidence 44 has no bindings object.",
    )

    decisions_binding = bindings.get("human_review_decisions")
    matrix_binding = bindings.get("human_review_matrix")

    _require(
        isinstance(decisions_binding, dict),
        "Evidence 44 has no human-review decisions binding.",
    )
    _require(
        isinstance(matrix_binding, dict),
        "Evidence 44 has no human-review matrix binding.",
    )
    _require(
        decisions_binding.get("path") == HUMAN_DECISIONS_PATH.name,
        "Evidence 44 references unexpected review decisions.",
    )
    _require(
        decisions_binding.get("sha256")
        == sha256_file(decisions_path),
        "Evidence 44 review-decisions SHA-256 binding failed.",
    )
    _require(
        matrix_binding.get("path") == HUMAN_REVIEW_PATH.name,
        "Evidence 44 references an unexpected review matrix.",
    )
    _require(
        matrix_binding.get("sha256") == sha256_file(review_path),
        "Evidence 44 review-matrix SHA-256 binding failed.",
    )

    telemetry = load_json(telemetry_path)
    canon_binding = telemetry.get("canon_binding")

    _require(
        isinstance(canon_binding, dict),
        "Evidence 45 has no canon_binding object.",
    )
    _require(
        canon_binding.get("draft_path") == DRAFT_PATH.name,
        "Evidence 45 references an unexpected canon draft.",
    )
    _require(
        canon_binding.get("draft_sha256") == R4_DRAFT_SHA256,
        "Evidence 45 has an unexpected canon SHA-256.",
    )
    _require(
        canon_binding.get("human_review_completed") is True,
        "Evidence 45 does not confirm human review.",
    )
    _require(
        canon_binding.get("approved_as_final_canon") is True,
        "Evidence 45 does not bind approved final canon.",
    )
    _require(
        canon_binding.get("final_disposition") == "approve",
        "Evidence 45 final disposition is not approve.",
    )
    _require(
        canon_binding.get("tag") == R4_FINAL_CANON_TAG,
        "Evidence 45 has an unexpected final-canon tag.",
    )
    _require(
        canon_binding.get("commit_sha") == R4_FINAL_CANON_COMMIT,
        "Evidence 45 has an unexpected final-canon commit.",
    )

    return {
        "revision": "R4",
        "draft_path": _relative(DRAFT_PATH),
        "draft_sha256": actual_draft_sha256,
        "semantic_validation": {
            "path": _relative(SEMANTIC_VALIDATION_PATH),
            "sha256": sha256_file(semantic_path),
            "strict_local_validation_passed": True,
            "independent_semantic_validation_passed": True,
        },
        "human_review": {
            "matrix_path": _relative(HUMAN_REVIEW_PATH),
            "matrix_sha256": sha256_file(review_path),
            "decisions_path": _relative(HUMAN_DECISIONS_PATH),
            "decisions_sha256": sha256_file(decisions_path),
            "completion_path": _relative(HUMAN_COMPLETION_PATH),
            "completion_sha256": sha256_file(completion_path),
            "approved_items": 25,
            "human_review_completed": True,
            "approved_as_final_canon": True,
            "final_disposition": "approve",
        },
        "final_canon": {
            "tag": R4_FINAL_CANON_TAG,
            "commit_sha": R4_FINAL_CANON_COMMIT,
        },
        "telemetry_contract": {
            "path": _relative(TELEMETRY_CONTRACT_PATH),
            "sha256": sha256_file(telemetry_path),
        },
    }


def parse_frozen_beats(
    repository_root: Path,
) -> tuple[dict[str, Any], ...]:
    draft_path = repository_root.resolve() / DRAFT_PATH

    try:
        text = draft_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ProductionRunError(
            f"Frozen R4 draft is missing: {DRAFT_PATH}"
        ) from exc

    parsed: list[dict[str, Any]] = []

    for line_number, line in enumerate(
        text.splitlines(),
        start=1,
    ):
        match = BEAT_PATTERN.match(line.strip())

        if match is None:
            continue

        number = int(match.group(1))
        title = match.group(2).strip()

        parsed.append(
            {
                "beat_id": f"P10G-BEAT-{number:03d}",
                "beat_number": number,
                "title": title,
                "source_line": line_number,
            }
        )

    expected_numbers = list(range(1, 45))
    actual_numbers = [
        item["beat_number"]
        for item in parsed
    ]

    _require(
        actual_numbers == expected_numbers,
        "The R4 beat sequence must be exactly 001 through 044.",
    )

    assigned: list[dict[str, Any]] = []

    for beat in parsed:
        segment_id = next(
            (
                candidate
                for candidate, boundaries in SEGMENT_RANGES.items()
                if boundaries[0]
                <= beat["beat_number"]
                <= boundaries[1]
            ),
            None,
        )

        _require(
            segment_id is not None,
            f"No segment mapping for {beat['beat_id']}.",
        )

        assigned.append(
            {
                **beat,
                "segment_id": segment_id,
                "segment_title": SEGMENT_TITLES[segment_id],
            }
        )

    return tuple(assigned)


def resolve_selection(
    *,
    profile: str | None = None,
    segments: Iterable[str] | None = None,
) -> dict[str, Any]:
    requested_segments = tuple(segments or ())

    if profile is not None and requested_segments:
        raise ProductionRunError(
            "Use either a profile or explicit segments, not both."
        )

    if profile is None and not requested_segments:
        raise ProductionRunError(
            "A profile or at least one segment is required."
        )

    if profile is not None:
        if profile not in PROFILE_SEGMENTS:
            raise ProductionRunError(
                f"Unknown production profile: {profile}"
            )

        selected_segments = PROFILE_SEGMENTS[profile]
        presentation_units = PROFILE_PRESENTATION_UNITS[profile]
        selection_mode = "profile"
        selection_name = profile
    else:
        unknown = set(requested_segments) - set(SEGMENT_ORDER)

        if unknown:
            raise ProductionRunError(
                f"Unknown production segments: {sorted(unknown)}"
            )

        if len(set(requested_segments)) != len(requested_segments):
            raise ProductionRunError(
                "Duplicate production segments are not allowed."
            )

        requested_set = set(requested_segments)
        selected_segments = tuple(
            item
            for item in SEGMENT_ORDER
            if item in requested_set
        )
        presentation_units = ()
        selection_mode = "segments"
        selection_name = "custom"

    return {
        "mode": selection_mode,
        "name": selection_name,
        "presentation_units": list(presentation_units),
        "segments": list(selected_segments),
    }


def build_production_run(
    repository_root: Path,
    *,
    profile: str | None = None,
    segments: Sequence[str] | None = None,
) -> dict[str, Any]:
    canon_binding = validate_canon_authority(repository_root)
    all_beats = parse_frozen_beats(repository_root)
    selection = resolve_selection(
        profile=profile,
        segments=segments,
    )

    selected_segment_ids = set(selection["segments"])
    selected_beats = [
        beat
        for beat in all_beats
        if beat["segment_id"] in selected_segment_ids
    ]

    _require(
        bool(selected_beats),
        "The production selection contains no beats.",
    )

    segment_catalog = []

    for segment_id in SEGMENT_ORDER:
        start, end = SEGMENT_RANGES[segment_id]
        segment_catalog.append(
            {
                "segment_id": segment_id,
                "title": SEGMENT_TITLES[segment_id],
                "first_beat_id": f"P10G-BEAT-{start:03d}",
                "last_beat_id": f"P10G-BEAT-{end:03d}",
                "beat_count": end - start + 1,
            }
        )

    selection_identity = {
        "project_id": PROJECT_ID,
        "canon_draft_sha256": R4_DRAFT_SHA256,
        "profile": profile,
        "segments": selection["segments"],
        "presentation_units": selection["presentation_units"],
        "beat_ids": [
            beat["beat_id"]
            for beat in selected_beats
        ],
    }
    selection_id = deterministic_uuid(
        "canonflow-production-selection-v1",
        selection_identity,
    )
    production_run_id = deterministic_uuid(
        "canonflow-production-run-v1",
        {
            "contract_version": CONTRACT_VERSION,
            "selection_id": selection_id,
            "canon_draft_sha256": R4_DRAFT_SHA256,
        },
    )
    contract_id = deterministic_uuid(
        "canonflow-production-run-contract-v1",
        {
            "project_id": PROJECT_ID,
            "canon_draft_sha256": R4_DRAFT_SHA256,
            "segment_ranges": dict(SEGMENT_RANGES),
        },
    )

    generated_at_utc = datetime.now(timezone.utc).isoformat()

    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_type": ARTIFACT_TYPE,
        "contract_version": CONTRACT_VERSION,
        "contract_id": contract_id,
        "production_run_id": production_run_id,
        "selection_id": selection_id,
        "generated_at_utc": generated_at_utc,
        "status": "planned",
        "project": {
            "project_id": PROJECT_ID,
            "project_slug": PROJECT_SLUG,
        },
        "canon_binding": canon_binding,
        "segment_catalog": segment_catalog,
        "selection": {
            **selection,
            "source_scope_policy": (
                "The showcase profile defines approved source regions. "
                "Shot-level excerpting is performed by the later "
                "scene-to-shot compiler without changing canon."
                if profile == "showcase"
                else "All selected beats are eligible production sources."
            ),
            "selected_beat_count": len(selected_beats),
            "first_beat_id": selected_beats[0]["beat_id"],
            "last_beat_id": selected_beats[-1]["beat_id"],
            "beats": selected_beats,
        },
        "controls": {
            "canon_mutation_allowed": False,
            "database_access_performed": False,
            "database_mutation_performed": False,
            "executor_invoked": False,
            "external_tools_used": False,
            "gemini_request_performed": False,
            "http_request_performed": False,
            "identity_token_requested": False,
            "network_access_performed": False,
            "production_execution_performed": False,
            "human_approval_required_before_external_execution": True,
            "output_overwrite_allowed": False,
        },
        "next_controlled_action": {
            "operation": "compile_selected_beats_to_scene_and_shot_specs",
            "requires_new_human_approval_before_external_generation": True,
        },
    }


def write_production_run(
    output_path: Path,
    production_run: Mapping[str, Any],
) -> None:
    path = output_path.resolve()

    if path.exists():
        raise ProductionRunError(
            f"Refusing to overwrite production run: {path}"
        )

    path.parent.mkdir(
        mode=0o750,
        parents=True,
        exist_ok=True,
    )

    content = (
        json.dumps(
            production_run,
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")

    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL

    try:
        descriptor = os.open(
            path,
            flags,
            0o644,
        )
    except FileExistsError as exc:
        raise ProductionRunError(
            f"Refusing to overwrite production run: {path}"
        ) from exc

    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise
