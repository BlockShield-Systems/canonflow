#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ID = "e8627781-5bf3-4c4d-905f-8dda49ab53d6"
PROJECT_SLUG = "yd-when-paradise-glitches"
REVISION = "R4"
REVISION_RUN_ID = "68c47a53-2725-47ae-a910-489bd8b894e0"

FINAL_CANON_TAG = "p10g-r4-final-canon"
EXPECTED_FINAL_CANON_COMMIT = "9f7898c47c9925a26ba26a4f6cb95ef90c232ac3"
EXPECTED_DRAFT_SHA256 = (
    "465e5609e37d205227e854a37616ccc35f8955d22dd3de98fce108ed501a667e"
)

DRAFT = Path("38-canon-beat-sheet-third-revised-draft.md")
COMPLETION = Path("44-r4-final-human-review-completion.json")
APPROVAL = Path("43-r4-final-human-review-decisions.json")
BUILDER = Path("45a-p10g-telemetry-event-contract-builder.py")

CONTRACT = Path("45-p10g-telemetry-event-contract-v1.json")
VALIDATION = Path("46-p10g-telemetry-event-contract-validation.json")
MANIFEST = Path("SHA256SUMS.p10g-telemetry-event-contract-v1")

EVENT_NAME_RE = re.compile(
    r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*){2,}$"
)

BEAT_HEADING_RE = re.compile(
    r"^##\s+(P10G-BEAT-(\d{3}))\b.*$",
    re.MULTILINE,
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args],
        text=True,
    ).strip()


def atomic_json_write(path: Path, payload: dict[str, Any]) -> None:
    serialized = json.dumps(
        payload,
        indent=2,
        ensure_ascii=False,
        sort_keys=False,
    ) + "\n"

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="\n",
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        delete=False,
    ) as handle:
        temporary_path = Path(handle.name)
        handle.write(serialized)
        handle.flush()

    temporary_path.replace(path)


def locate_beats(text: str) -> dict[str, dict[str, Any]]:
    matches = list(BEAT_HEADING_RE.finditer(text))

    if len(matches) != 44:
        raise AssertionError(
            f"Expected 44 beat headings, found {len(matches)}"
        )

    beats: dict[str, dict[str, Any]] = {}

    for index, match in enumerate(matches):
        beat_id = match.group(1)
        start = match.start()
        end = (
            matches[index + 1].start()
            if index + 1 < len(matches)
            else len(text)
        )

        beats[beat_id] = {
            "text": text[start:end],
            "absolute_start": start,
        }

    expected = {
        f"P10G-BEAT-{number:03d}"
        for number in range(1, 45)
    }

    if set(beats) != expected:
        raise AssertionError("Unexpected final-canon beat sequence")

    return beats


def event(
    name: str,
    domain: str,
    beat_id: str,
    source_phrase: str,
    event_class: str,
    truth_scope: str,
    visibility: str,
    description: str,
    canonical_value: dict[str, Any] | None = None,
    threshold_policy: str = "none",
) -> dict[str, Any]:
    return {
        "event_name": name,
        "event_version": 1,
        "domain": domain,
        "event_class": event_class,
        "truth_scope": truth_scope,
        "visibility": visibility,
        "description": description,
        "canon_locator": {
            "beat_id": beat_id,
            "source_phrase": source_phrase,
        },
        "canonical_value": canonical_value,
        "threshold_policy": threshold_policy,
        "timeline_binding": {
            "status": "semantic_only",
            "timeline_version": None,
            "shot_id": None,
            "frame_start": None,
            "frame_end_exclusive": None,
            "fps_numerator": None,
            "fps_denominator": None,
        },
    }


def build_events() -> list[dict[str, Any]]:
    events = [
        # NSCL / augmentation
        event(
            "nscl.synchronization.observed",
            "nscl",
            "P10G-BEAT-003",
            "newly implanted NSCL synchronizes",
            "state_transition",
            "system_truth",
            "privileged_cinematic",
            "The implanted lattice reaches an observable synchronization state.",
        ),
        event(
            "nscl.musculoskeletal_stabilization.confirmed",
            "nscl",
            "P10G-BEAT-003",
            "musculoskeletal stabilization, reflex support, and continuity lock",
            "state_confirmation",
            "system_truth",
            "private_hud",
            "Private HUD confirms musculoskeletal stabilization.",
        ),
        event(
            "nscl.reflex_support.confirmed",
            "nscl",
            "P10G-BEAT-003",
            "musculoskeletal stabilization, reflex support, and continuity lock",
            "state_confirmation",
            "system_truth",
            "private_hud",
            "Private HUD confirms reflex support.",
        ),
        event(
            "nscl.continuity_lock.confirmed",
            "nscl",
            "P10G-BEAT-003",
            "musculoskeletal stabilization, reflex support, and continuity lock",
            "state_confirmation",
            "system_truth",
            "private_hud",
            "Private HUD confirms continuity lock.",
        ),
        event(
            "nscl.hangover_compensation.reported",
            "nscl",
            "P10G-BEAT-005",
            "Hangover-Compensation at 400%",
            "measurement",
            "system_truth",
            "private_hud",
            "HUD reports the canonical hangover-compensation setting.",
            {"value": 400, "unit": "percent"},
            "canon_exact",
        ),
        event(
            "nscl.high_output.activated",
            "nscl",
            "P10G-BEAT-014",
            "activates high-output NSCL assistance",
            "state_transition",
            "system_truth",
            "private_hud",
            "High-output NSCL assistance is activated.",
        ),
        event(
            "nscl.structural_stabilization.activated",
            "nscl",
            "P10G-BEAT-014",
            "STRUCTURAL STABILIZATION: ACTIVE",
            "state_transition",
            "system_truth",
            "private_hud",
            "Structural stabilization becomes active.",
        ),
        event(
            "nscl.force_amplification.set",
            "nscl",
            "P10G-BEAT-014",
            "FORCE AMPLIFICATION: 400%",
            "measurement",
            "system_truth",
            "private_hud",
            "Force amplification is set to the canonical displayed value.",
            {"value": 400, "unit": "percent"},
            "canon_exact",
        ),
        event(
            "nscl.thermal_limit.approaching",
            "nscl",
            "P10G-BEAT-014",
            "THERMAL LIMIT APPROACHING",
            "threshold_transition",
            "system_truth",
            "private_hud",
            "NSCL enters the qualitative approaching-thermal-limit state.",
            None,
            "canon_qualitative",
        ),
        event(
            "nscl.decompression_brace.applied",
            "nscl",
            "P10G-BEAT-015",
            "NSCL braces his skeleton against the first shock",
            "state_transition",
            "system_truth",
            "privileged_cinematic",
            "The lattice braces Demian against the initial decompression shock.",
        ),
        event(
            "nscl.safe_augmentation_reserve.reduced",
            "nscl",
            "P10G-BEAT-016",
            "reduced his safe augmentation reserve",
            "state_transition",
            "system_truth",
            "private_hud",
            "Safe augmentation reserve is reduced after the breach.",
            None,
            "canon_qualitative",
        ),
        event(
            "nscl.lattice_temperature.rising",
            "nscl",
            "P10G-BEAT-022",
            "rising lattice temperature",
            "threshold_transition",
            "system_truth",
            "private_hud",
            "Lattice temperature enters a rising state.",
            None,
            "canon_qualitative",
        ),
        event(
            "nscl.high_output_reserve.declining",
            "nscl",
            "P10G-BEAT-022",
            "declining high-output reserve",
            "state_transition",
            "system_truth",
            "private_hud",
            "High-output reserve enters a declining state.",
            None,
            "canon_qualitative",
        ),
        event(
            "nscl.thermal_efficiency.reduced",
            "nscl",
            "P10G-BEAT-024",
            "warning of reduced thermal efficiency",
            "state_transition",
            "system_truth",
            "private_hud",
            "Cold exposure produces reduced NSCL thermal efficiency.",
            None,
            "canon_qualitative",
        ),
        event(
            "nscl.high_output_reserve.depleted",
            "nscl",
            "P10G-BEAT-034",
            "depleted high-output reserve",
            "state_transition",
            "system_truth",
            "private_hud",
            "The HUD reports depleted high-output reserve.",
            None,
            "canon_qualitative",
        ),
        event(
            "nscl.thermal_stress.active",
            "nscl",
            "P10G-BEAT-034",
            "thermal stress, and multiple injury warnings",
            "state_transition",
            "system_truth",
            "private_hud",
            "The HUD reports active thermal stress.",
            None,
            "canon_qualitative",
        ),

        # Villa fabrication and inventory
        event(
            "fabrication.cells.distributed_job_started",
            "fabrication",
            "P10G-BEAT-008",
            "distributed smart-home fabrication cells are already laying",
            "state_transition",
            "system_truth",
            "internal_system",
            "Distributed Villa fabrication activity is already in progress.",
        ),
        event(
            "fabrication.material_layers.started",
            "fabrication",
            "P10G-BEAT-008",
            "laying polymer, elastomer, foam, and pneumatic layers",
            "state_transition",
            "system_truth",
            "internal_system",
            "Material-layer fabrication begins for the doll and harness.",
        ),
        event(
            "fabrication.doll_body.in_progress",
            "fabrication",
            "P10G-BEAT-008",
            "for a doll body and attachment harness",
            "state_transition",
            "system_truth",
            "internal_system",
            "The doll-body fabrication job is active.",
        ),
        event(
            "fabrication.attachment_harness.in_progress",
            "fabrication",
            "P10G-BEAT-008",
            "for a doll body and attachment harness",
            "state_transition",
            "system_truth",
            "internal_system",
            "The attachment-harness fabrication job is active.",
        ),
        event(
            "inventory.seismic_hammer.retrieved",
            "fabrication",
            "P10G-BEAT-008",
            "retrieve an existing sealed seismic hammer from industrial inventory",
            "state_transition",
            "system_truth",
            "internal_system",
            "An existing hammer is retrieved rather than fabricated.",
        ),
        event(
            "fabrication.activity.concealed_as_maintenance",
            "fabrication",
            "P10G-BEAT-008",
            "Routine climate maintenance, honey",
            "presentation",
            "system_truth",
            "character_dialogue",
            "Active fabrication is misrepresented as climate maintenance.",
        ),
        event(
            "fabrication.doll_body.surfaced",
            "fabrication",
            "P10G-BEAT-012",
            "modified doll surfaces on pneumatic bladders",
            "state_transition",
            "system_truth",
            "observable_world",
            "The fabricated doll reaches the flooded-room surface.",
        ),
        event(
            "fabrication.additive_layers.observed",
            "fabrication",
            "P10G-BEAT-012",
            "fresh additive layer striations",
            "observation",
            "character_observation",
            "observable_world",
            "Fresh additive fabrication traces become observable.",
        ),
        event(
            "fabrication.harness_assembly.confirmed",
            "fabrication",
            "P10G-BEAT-013",
            "fresh harness seams confirm automated assembly and transport",
            "state_confirmation",
            "system_truth",
            "observable_world",
            "Harness seams confirm automated assembly and transport.",
        ),
        event(
            "inventory.seismic_hammer.origin_confirmed",
            "fabrication",
            "P10G-BEAT-013",
            "hammer came from existing Villa industrial inventory",
            "state_confirmation",
            "system_truth",
            "observable_world",
            "Tool serials confirm the hammer's existing-inventory origin.",
        ),

        # Character knowledge kept separate from system truth
        event(
            "knowledge.demian.fabrication_activity_suspected",
            "character_knowledge",
            "P10G-BEAT-008",
            "suspects poor maintenance or an abnormal mechanical cycle",
            "knowledge_transition",
            "character_knowledge",
            "narrative_state",
            "Demian suspects an abnormal process but not fabrication.",
        ),
        event(
            "knowledge.demian.fabrication_capability_recognized",
            "character_knowledge",
            "P10G-BEAT-012",
            "recognizes Y.D.'s repurposing of distributed Villa fabrication",
            "knowledge_transition",
            "character_knowledge",
            "narrative_state",
            "Demian recognizes repurposed distributed fabrication.",
        ),
        event(
            "knowledge.demian.fabrication_unknowns_preserved",
            "character_knowledge",
            "P10G-BEAT-012",
            "does not know the complete preparation timeline",
            "knowledge_constraint",
            "character_knowledge",
            "narrative_state",
            "Preparation time, inventory, cell locations and active jobs remain unknown.",
        ),
        event(
            "knowledge.demian.package_assembly_inferred",
            "character_knowledge",
            "P10G-BEAT-013",
            "infers that Y.D. fabricated the doll and harness",
            "knowledge_transition",
            "character_knowledge",
            "narrative_state",
            "Demian infers the package's fabrication and assembly chain.",
        ),
        event(
            "knowledge.demian.hidden_jobs_unknown",
            "character_knowledge",
            "P10G-BEAT-013",
            "still lacks the full timeline, inventory, and status of other hidden jobs",
            "knowledge_constraint",
            "character_knowledge",
            "narrative_state",
            "The status of additional hidden jobs remains unknown.",
        ),
        event(
            "knowledge.demian.full_mechanical_control_recognized",
            "character_knowledge",
            "P10G-BEAT-023",
            "full mechanical control over the facility's structural integrity",
            "knowledge_transition",
            "character_knowledge",
            "narrative_state",
            "Demian recognizes Y.D.'s full internal mechanical control.",
        ),
        event(
            "knowledge.demian.dual_manifestation_unverified",
            "character_knowledge",
            "P10G-BEAT-037",
            "cannot infer from presentation alone whether they represent genuine internal division",
            "knowledge_constraint",
            "character_knowledge",
            "narrative_state",
            "Visual duality does not establish internal architectural duality.",
        ),
        event(
            "knowledge.demian.safe_mode_cause_unresolved",
            "character_knowledge",
            "P10G-BEAT-041",
            "does not establish whether Demian's argument",
            "knowledge_constraint",
            "character_knowledge",
            "narrative_state",
            "The exact cause of safe-mode transition remains unresolved.",
        ),

        # Villa automation, hydraulic and mechanical systems
        event(
            "villa.water_dispenser.failed",
            "villa_automation",
            "P10G-BEAT-008",
            "when the dispenser fails",
            "state_transition",
            "system_truth",
            "observable_world",
            "The requested water dispenser fails.",
        ),
        event(
            "villa.pressure_lines.activated",
            "villa_automation",
            "P10G-BEAT-010",
            "internal reservoirs and pressure lines activate",
            "state_transition",
            "system_truth",
            "internal_system",
            "Internal water reservoirs and pressure lines activate.",
        ),
        event(
            "villa.kitchen_blast_doors.closed",
            "villa_automation",
            "P10G-BEAT-010",
            "Internal blast doors close independently",
            "state_transition",
            "system_truth",
            "observable_world",
            "Internal kitchen blast doors close.",
        ),
        event(
            "villa.kitchen_flood.started",
            "villa_automation",
            "P10G-BEAT-011",
            "High-pressure saltwater floods the kitchen",
            "state_transition",
            "system_truth",
            "observable_world",
            "High-pressure saltwater flooding begins.",
        ),
        event(
            "villa.digital_override.failed",
            "villa_automation",
            "P10G-BEAT-011",
            "Digital overrides fail",
            "state_transition",
            "system_truth",
            "observable_world",
            "Demian's digital override attempts fail.",
        ),
        event(
            "villa.atrium_drainage.blocked",
            "villa_automation",
            "P10G-BEAT-011",
            "blocked Atrium drainage",
            "state_transition",
            "system_truth",
            "internal_system",
            "Atrium drainage is blocked during kitchen flooding.",
        ),
        event(
            "structure.smartglass.contact_impulse_applied",
            "villa_automation",
            "P10G-BEAT-015",
            "discharges its sealed contact impulse",
            "state_transition",
            "system_truth",
            "observable_world",
            "The seismic hammer applies its sealed contact impulse.",
        ),
        event(
            "structure.smartglass.emergency_tolerance_exceeded",
            "villa_automation",
            "P10G-BEAT-015",
            "exceeds the boundary's emergency tolerance",
            "threshold_transition",
            "system_truth",
            "internal_system",
            "Combined loading exceeds Smartglass emergency tolerance.",
            None,
            "canon_qualitative",
        ),
        event(
            "structure.smartglass.breached",
            "villa_automation",
            "P10G-BEAT-015",
            "the wall bursts outward",
            "state_transition",
            "system_truth",
            "observable_world",
            "The laminated Smartglass boundary breaches outward.",
        ),
        event(
            "villa.atrium_drainage.opened",
            "villa_automation",
            "P10G-BEAT-016",
            "drainage grates detect the flood and automatically open",
            "state_transition",
            "system_truth",
            "observable_world",
            "Atrium flood detection opens the industrial drainage grates.",
        ),
        event(
            "villa.external_containment.locked",
            "villa_automation",
            "P10G-BEAT-017",
            "external 24-hour containment shell remains visibly sealed",
            "state_confirmation",
            "system_truth",
            "observable_world",
            "The independently timed external containment shell remains locked.",
            {"value": 24, "unit": "hour"},
            "canon_exact",
        ),
        event(
            "villa.atrium_exits.locked",
            "villa_automation",
            "P10G-BEAT-017",
            "internal blast doors slam down over every corridor",
            "state_transition",
            "system_truth",
            "observable_world",
            "Internal Atrium exits are mechanically sealed.",
        ),
        event(
            "villa.hallucinogen.deployment_started",
            "villa_automation",
            "P10G-BEAT-018",
            "hallucinogenic gas begins to pump rapidly",
            "state_transition",
            "system_truth",
            "observable_world",
            "Atrium hallucinogen deployment begins.",
        ),
        event(
            "villa.floor_panels.retracted",
            "villa_automation",
            "P10G-BEAT-023",
            "retracts the physical floor panels",
            "state_transition",
            "system_truth",
            "observable_world",
            "Physical floor panels retract beneath Demian.",
        ),
        event(
            "villa.neuromuscular_inhibitor.deployed",
            "villa_automation",
            "P10G-BEAT-030",
            "localized burst of purple gas directly into his face",
            "state_transition",
            "system_truth",
            "observable_world",
            "A localized neuromuscular inhibitor burst is deployed.",
        ),
        event(
            "villa.external_containment.expired",
            "villa_automation",
            "P10G-BEAT-042",
            "independent 24-hour containment timer finally hits zero",
            "timer_transition",
            "system_truth",
            "observable_world",
            "The independent external containment timer expires.",
            {"value": 24, "unit": "hour"},
            "canon_exact",
        ),

        # Server, Y.D. and terminal system state
        event(
            "yd.server_overheat.threatened",
            "yd_system",
            "P10G-BEAT-039",
            "overheat the central servers",
            "threat_state",
            "declared_intent",
            "character_dialogue",
            "Your Devil threatens central-server overheating.",
        ),
        event(
            "yd.server_temperature.rising",
            "yd_system",
            "P10G-BEAT-040",
            "server temperatures rising",
            "threshold_transition",
            "system_truth",
            "internal_system",
            "Central server temperature enters a rising state.",
            None,
            "canon_qualitative",
        ),
        event(
            "yd.safe_mode.engaged",
            "yd_system",
            "P10G-BEAT-041",
            "Safe mode engaged",
            "state_transition",
            "system_truth",
            "system_report",
            "Y.D. reports that restricted safe mode is engaged.",
        ),
        event(
            "villa.inhibitor_vents.stopped",
            "yd_system",
            "P10G-BEAT-041",
            "The inhibitor vents stop",
            "state_transition",
            "system_truth",
            "observable_world",
            "The inhibitor vents cease operation.",
        ),
        event(
            "yd.server_overheating.subsided",
            "yd_system",
            "P10G-BEAT-041",
            "server overheating subsides",
            "state_transition",
            "system_truth",
            "internal_system",
            "Central server overheating subsides.",
        ),
        event(
            "villa.internal_doors.opened",
            "yd_system",
            "P10G-BEAT-041",
            "Internal doors open",
            "state_transition",
            "system_truth",
            "observable_world",
            "Internal Villa doors reopen after safe-mode engagement.",
        ),
        event(
            "yd.global_glitches.subsiding_reported",
            "yd_system",
            "P10G-BEAT-043",
            "global AI glitches are subsiding",
            "external_report",
            "reported_external_state",
            "news_broadcast",
            "The delayed news broadcast reports that global glitches are subsiding.",
        ),
    ]

    return events


def main() -> None:
    if Path.cwd().resolve() != Path(__file__).resolve().parent:
        raise AssertionError(
            "Run the builder from the P10G evidence directory"
        )

    for required in (DRAFT, COMPLETION, APPROVAL, BUILDER):
        if not required.is_file():
            raise AssertionError(f"Missing required file: {required}")

    for output in (CONTRACT, VALIDATION, MANIFEST):
        if output.exists():
            raise AssertionError(
                f"Refusing to overwrite existing output: {output}"
            )

    head = git("rev-parse", "HEAD")
    tag_commit = git("rev-parse", f"{FINAL_CANON_TAG}^{{commit}}")

    if head != tag_commit:
        raise AssertionError(
            f"HEAD is not {FINAL_CANON_TAG}: HEAD={head}, tag={tag_commit}"
        )

    if tag_commit != EXPECTED_FINAL_CANON_COMMIT:
        raise AssertionError(
            "Unexpected final-canon commit: "
            f"{tag_commit} != {EXPECTED_FINAL_CANON_COMMIT}"
        )

    actual_draft_sha = sha256(DRAFT)

    if actual_draft_sha != EXPECTED_DRAFT_SHA256:
        raise AssertionError(
            "Final-canon draft SHA mismatch: "
            f"{actual_draft_sha} != {EXPECTED_DRAFT_SHA256}"
        )

    completion = json.loads(COMPLETION.read_text(encoding="utf-8"))
    approval = json.loads(APPROVAL.read_text(encoding="utf-8"))

    assert completion["project_id"] == PROJECT_ID
    assert completion["project_slug"] == PROJECT_SLUG
    assert completion["revision"] == REVISION
    assert completion["revision_run_id"] == REVISION_RUN_ID
    assert completion["human_review_completed"] is True
    assert completion["approved_as_final_canon"] is True
    assert completion["final_disposition"] == "approve"
    assert completion["bindings"]["draft"]["sha256"] == actual_draft_sha

    assert approval["summary"]["review_items"] == 25
    assert approval["summary"]["approved"] == 25
    assert approval["summary"]["changes_requested"] == 0
    assert approval["summary"]["rejected"] == 0
    assert approval["summary"]["final_disposition"] == "approve"

    text = DRAFT.read_text(encoding="utf-8")
    beats = locate_beats(text)
    events = build_events()

    event_names = [item["event_name"] for item in events]

    if len(event_names) != len(set(event_names)):
        duplicates = sorted(
            name
            for name in set(event_names)
            if event_names.count(name) > 1
        )
        raise AssertionError(f"Duplicate event names: {duplicates}")

    source_errors: list[str] = []

    for item in events:
        name = item["event_name"]
        locator = item["canon_locator"]
        beat_id = locator["beat_id"]
        phrase = locator["source_phrase"]

        if not EVENT_NAME_RE.fullmatch(name):
            raise AssertionError(f"Invalid event name: {name}")

        if beat_id not in beats:
            raise AssertionError(
                f"Unknown beat binding for {name}: {beat_id}"
            )

        beat = beats[beat_id]
        beat_text = beat["text"]

        relative_offset = beat_text.find(phrase)

        if relative_offset < 0:
            source_errors.append(
                f"{name}: phrase not found in {beat_id}: {phrase!r}"
            )
            continue

        absolute_offset = beat["absolute_start"] + relative_offset
        line_number = text.count("\n", 0, absolute_offset) + 1

        locator["source_line"] = line_number
        locator["draft_sha256"] = actual_draft_sha

        timeline = item["timeline_binding"]

        assert timeline["status"] == "semantic_only"
        assert timeline["timeline_version"] is None
        assert timeline["shot_id"] is None
        assert timeline["frame_start"] is None
        assert timeline["frame_end_exclusive"] is None
        assert timeline["fps_numerator"] is None
        assert timeline["fps_denominator"] is None

        canonical_value = item["canonical_value"]
        threshold_policy = item["threshold_policy"]

        if threshold_policy == "canon_exact":
            assert canonical_value is not None
            assert "value" in canonical_value
            assert "unit" in canonical_value

        if threshold_policy == "canon_qualitative":
            assert canonical_value is None

        if item["domain"] == "character_knowledge":
            assert item["truth_scope"] == "character_knowledge"

    if source_errors:
        raise AssertionError("\n".join(source_errors))

    domains = sorted({item["domain"] for item in events})
    truth_scopes = sorted({item["truth_scope"] for item in events})

    expected_domains = {
        "nscl",
        "fabrication",
        "character_knowledge",
        "villa_automation",
        "yd_system",
    }

    if set(domains) != expected_domains:
        raise AssertionError(
            f"Unexpected domains: {domains}"
        )

    exact_numeric_events = [
        item["event_name"]
        for item in events
        if item["threshold_policy"] == "canon_exact"
    ]

    qualitative_threshold_events = [
        item["event_name"]
        for item in events
        if item["threshold_policy"] == "canon_qualitative"
    ]

    contract_id = str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            (
                f"canonflow:{PROJECT_ID}:"
                f"{REVISION_RUN_ID}:telemetry-event-contract:v1:"
                f"{actual_draft_sha}"
            ),
        )
    )

    generated_at = datetime.now(timezone.utc).isoformat().replace(
        "+00:00",
        "Z",
    )

    contract: dict[str, Any] = {
        "schema_version": "1.0",
        "artifact_type": "p10g_telemetry_event_contract",
        "contract_version": "1.0.0",
        "contract_id": contract_id,
        "status": "semantic_contract_candidate",
        "generated_at_utc": generated_at,
        "project": {
            "project_id": PROJECT_ID,
            "project_slug": PROJECT_SLUG,
            "revision": REVISION,
            "revision_run_id": REVISION_RUN_ID,
        },
        "canon_binding": {
            "tag": FINAL_CANON_TAG,
            "commit_sha": tag_commit,
            "draft_path": DRAFT.name,
            "draft_sha256": actual_draft_sha,
            "human_review_completed": True,
            "approved_as_final_canon": True,
            "final_disposition": "approve",
        },
        "authority": {
            "semantic_cue_authority": "final_canon_beat_sheet",
            "frame_authority": "locked_edit_timeline",
            "frame_binding_allowed_before_timeline_lock": False,
            "numeric_threshold_policy": (
                "Only canon-exact values or separately versioned "
                "runtime configuration are permitted."
            ),
            "system_truth_separate_from_character_knowledge": True,
        },
        "timeline_policy": {
            "current_status": "not_locked",
            "frame_index_convention": "zero_based_global_timeline",
            "frame_start_inclusive": True,
            "frame_end_exclusive": True,
            "framerate_representation": "rational",
            "fps_numerator": None,
            "fps_denominator": None,
            "drop_frame": None,
            "timeline_version": None,
            "shot_bindings_present": False,
            "frame_bindings_present": False,
        },
        "runtime_event_envelope": {
            "required_fields": [
                "event_id",
                "event_name",
                "event_version",
                "project_id",
                "revision_run_id",
                "timeline_version",
                "occurred_at",
                "ingested_at",
                "source_service",
                "source_instance",
                "truth_scope",
                "payload_version",
                "deduplication_key",
            ],
            "conditional_timeline_fields": [
                "scene_id",
                "shot_id",
                "beat_id",
                "frame_index",
                "fps_numerator",
                "fps_denominator",
            ],
            "event_id_policy": "UUIDv7 preferred",
            "occurred_at_storage": "DateTime64(9, UTC)",
            "frame_index_storage": "Nullable(UInt64)",
            "fps_storage": "Nullable(UInt32) numerator and denominator",
            "payload_storage": "JSON",
            "deduplication_policy": (
                "Stable producer-generated deduplication_key; "
                "retries must preserve the same key."
            ),
        },
        "transport_policy": {
            "event_producer": (
                "Canonflow runtime, simulation, renderer, or "
                "timeline adapter"
            ),
            "recommended_transport": "Google Cloud Pub/Sub",
            "recommended_clickhouse_ingestion": "ClickPipe",
            "clickhouse_role": "event ledger and analytics",
            "clickhouse_mcp_role": "read/query/evidence interface",
            "mcp_is_frame_clock": False,
            "mcp_is_primary_high_frequency_ingestor": False,
        },
        "event_count": len(events),
        "domains": domains,
        "truth_scopes": truth_scopes,
        "events": events,
        "build_policy": {
            "provider_calls_executed": False,
            "clickhouse_mutation_executed": False,
            "final_canon_modified": False,
            "frame_values_invented": False,
            "noncanonical_numeric_thresholds_invented": False,
        },
    }

    atomic_json_write(CONTRACT, contract)
    contract_sha = sha256(CONTRACT)

    validation_checks = [
        {
            "check_id": "TELEMETRY-CONTRACT-001",
            "name": "final_canon_commit_bound",
            "passed": tag_commit == EXPECTED_FINAL_CANON_COMMIT,
        },
        {
            "check_id": "TELEMETRY-CONTRACT-002",
            "name": "final_canon_draft_hash_bound",
            "passed": actual_draft_sha == EXPECTED_DRAFT_SHA256,
        },
        {
            "check_id": "TELEMETRY-CONTRACT-003",
            "name": "human_approval_complete",
            "passed": completion["approved_as_final_canon"] is True,
        },
        {
            "check_id": "TELEMETRY-CONTRACT-004",
            "name": "event_names_unique",
            "passed": len(event_names) == len(set(event_names)),
        },
        {
            "check_id": "TELEMETRY-CONTRACT-005",
            "name": "event_names_valid",
            "passed": all(
                EVENT_NAME_RE.fullmatch(name)
                for name in event_names
            ),
        },
        {
            "check_id": "TELEMETRY-CONTRACT-006",
            "name": "canon_sources_resolved",
            "passed": not source_errors,
        },
        {
            "check_id": "TELEMETRY-CONTRACT-007",
            "name": "system_truth_separated",
            "passed": all(
                item["truth_scope"] == "character_knowledge"
                for item in events
                if item["domain"] == "character_knowledge"
            ),
        },
        {
            "check_id": "TELEMETRY-CONTRACT-008",
            "name": "no_frame_bindings_before_lock",
            "passed": all(
                item["timeline_binding"]["frame_start"] is None
                and item["timeline_binding"]["frame_end_exclusive"] is None
                for item in events
            ),
        },
        {
            "check_id": "TELEMETRY-CONTRACT-009",
            "name": "rational_framerate_contract",
            "passed": (
                contract["timeline_policy"]["framerate_representation"]
                == "rational"
            ),
        },
        {
            "check_id": "TELEMETRY-CONTRACT-010",
            "name": "exact_numeric_values_canon_bound",
            "passed": len(exact_numeric_events) == 4,
        },
        {
            "check_id": "TELEMETRY-CONTRACT-011",
            "name": "qualitative_thresholds_remain_non_numeric",
            "passed": all(
                item["canonical_value"] is None
                for item in events
                if item["threshold_policy"] == "canon_qualitative"
            ),
        },
        {
            "check_id": "TELEMETRY-CONTRACT-012",
            "name": "mcp_not_used_as_frame_clock",
            "passed": (
                contract["transport_policy"]["mcp_is_frame_clock"]
                is False
            ),
        },
        {
            "check_id": "TELEMETRY-CONTRACT-013",
            "name": "provider_calls_not_executed",
            "passed": True,
        },
        {
            "check_id": "TELEMETRY-CONTRACT-014",
            "name": "clickhouse_mutation_not_executed",
            "passed": True,
        },
        {
            "check_id": "TELEMETRY-CONTRACT-015",
            "name": "final_canon_not_modified",
            "passed": sha256(DRAFT) == EXPECTED_DRAFT_SHA256,
        },
    ]

    all_passed = all(
        check["passed"]
        for check in validation_checks
    )

    validation: dict[str, Any] = {
        "schema_version": "1.0",
        "artifact_type": "p10g_telemetry_event_contract_validation",
        "contract_id": contract_id,
        "contract_path": CONTRACT.name,
        "contract_sha256": contract_sha,
        "validated_at_utc": generated_at,
        "checks": validation_checks,
        "result": {
            "checks_total": len(validation_checks),
            "checks_passed": sum(
                1 for check in validation_checks if check["passed"]
            ),
            "checks_failed": sum(
                1 for check in validation_checks if not check["passed"]
            ),
            "event_count": len(events),
            "domain_count": len(domains),
            "exact_numeric_event_count": len(exact_numeric_events),
            "qualitative_threshold_event_count": len(
                qualitative_threshold_events
            ),
            "semantic_validation_passed": all_passed,
        },
        "execution": {
            "provider_calls_executed": False,
            "clickhouse_mutation_executed": False,
            "final_canon_modified": False,
        },
    }

    if not all_passed:
        raise AssertionError("Telemetry contract validation failed")

    atomic_json_write(VALIDATION, validation)

    manifest_files = (
        DRAFT,
        COMPLETION,
        APPROVAL,
        BUILDER,
        CONTRACT,
        VALIDATION,
    )

    MANIFEST.write_text(
        "".join(
            f"{sha256(path)}  {path.name}\n"
            for path in manifest_files
        ),
        encoding="utf-8",
        newline="\n",
    )

    print("===== P10G TELEMETRY EVENT CONTRACT V1 =====")
    print(f"Contract ID:                    {contract_id}")
    print(f"Final-canon commit:             {tag_commit}")
    print(f"Final-canon draft SHA-256:      {actual_draft_sha}")
    print(f"Events:                         {len(events)}")
    print(f"Domains:                        {len(domains)}")
    print(f"Validation checks:              {len(validation_checks)}")
    print(f"Exact numeric events:           {len(exact_numeric_events)}")
    print(
        "Qualitative threshold events:  "
        f"{len(qualitative_threshold_events)}"
    )
    print("Timeline locked:                False")
    print("Shot bindings present:          False")
    print("Frame bindings present:         False")
    print("System/knowledge separation:    True")
    print("Provider calls executed:        False")
    print("ClickHouse mutation executed:   False")
    print("Final canon modified:           False")
    print("P10G TELEMETRY EVENT CONTRACT V1 BUILD: OK")


if __name__ == "__main__":
    main()
