#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ID = "e8627781-5bf3-4c4d-905f-8dda49ab53d6"
PROJECT_SLUG = "yd-when-paradise-glitches"

PARENT_REVISION_RUN_ID = "a8f16e58-7316-4415-b1a8-83131f96f7c7"
PARENT_DRAFT_SHA256 = (
    "1b99ba8d6a3c5dddf68883ad95ffec926e858c79162b054515495caa19bbd6a3"
)

SOURCE_DEMIAN = Path(
    "/mnt/c/Users/Administrator/Downloads/"
    "Demian (Y.D. - When Paradise Glitches).jpg"
)
SOURCE_YD = Path(
    "/mnt/c/Users/Administrator/Downloads/"
    "Y.D (Y.D. - When Paradise Glitches).jpg"
)

OUTPUT_DIRECTORY = Path("reference-images/r4")
OUTPUT_DEMIAN = OUTPUT_DIRECTORY / "demian-character-reference.jpg"
OUTPUT_YD = OUTPUT_DIRECTORY / "yd-character-reference.jpg"

PROVENANCE_PATH = Path("37-r4-reference-image-provenance.json")
MANIFEST_PATH = Path("SHA256SUMS.r4-reference-images")
IMPORTER_PATH = Path("37a-r4-reference-image-importer.py")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def require_jpeg(path: Path) -> bytes:
    if not path.is_file():
        raise RuntimeError(f"Required reference image does not exist: {path}")

    data = path.read_bytes()

    if len(data) < 4:
        raise RuntimeError(f"Reference image is too small: {path}")

    if not data.startswith(b"\xff\xd8\xff"):
        raise RuntimeError(f"Invalid JPEG opening signature: {path}")

    if not data.endswith(b"\xff\xd9"):
        raise RuntimeError(f"Invalid JPEG closing signature: {path}")

    return data


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def write_atomic_new(path: Path, data: bytes) -> None:
    if path.exists():
        raise RuntimeError(f"Refusing to overwrite existing artifact: {path}")

    path.parent.mkdir(parents=True, exist_ok=True)

    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")

    try:
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o640,
        )

        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
        except Exception:
            try:
                os.close(descriptor)
            except OSError:
                pass
            raise

        os.replace(temporary, path)

    finally:
        if temporary.exists():
            temporary.unlink()


def main() -> None:
    expected_outputs = [
        OUTPUT_DEMIAN,
        OUTPUT_YD,
        PROVENANCE_PATH,
        MANIFEST_PATH,
    ]

    existing_outputs = [path for path in expected_outputs if path.exists()]
    if existing_outputs:
        formatted = ", ".join(str(path) for path in existing_outputs)
        raise RuntimeError(
            "Reference-image package already exists; refusing overwrite: "
            f"{formatted}"
        )

    if not IMPORTER_PATH.is_file():
        raise RuntimeError(f"Importer script not found: {IMPORTER_PATH}")

    demian_bytes = require_jpeg(SOURCE_DEMIAN)
    yd_bytes = require_jpeg(SOURCE_YD)

    demian_sha = sha256_bytes(demian_bytes)
    yd_sha = sha256_bytes(yd_bytes)

    if demian_sha == yd_sha:
        raise RuntimeError(
            "Demian and Y.D. reference images unexpectedly have identical hashes"
        )

    r4_revision_run_id = str(uuid.uuid4())
    generated_at = utc_now()

    provenance = {
        "schema_version": "1.0",
        "artifact_type": "p10g_r4_character_reference_provenance",
        "project": {
            "project_id": PROJECT_ID,
            "project_slug": PROJECT_SLUG,
        },
        "revision": {
            "revision": "R4",
            "revision_run_id": r4_revision_run_id,
            "parent_revision_run_id": PARENT_REVISION_RUN_ID,
            "parent_draft_sha256": PARENT_DRAFT_SHA256,
            "status": "controlled_revision_in_progress",
        },
        "created_at_utc": generated_at,
        "rights_and_provenance": {
            "creator_owned": True,
            "generated_with": "Google Gemini Pro",
            "third_party_character_claim": False,
            "public_export_authorized": False,
            "repository_scope": "private_development_and_evidence",
        },
        "references": [
            {
                "character_id": "demian",
                "display_name": "Demian",
                "source_filename": SOURCE_DEMIAN.name,
                "controlled_path": OUTPUT_DEMIAN.as_posix(),
                "media_type": "image/jpeg",
                "byte_length": len(demian_bytes),
                "sha256": demian_sha,
                "creation_provenance": "creator_owned_generated_with_gemini_pro",
                "identity_context": "creator_self_reference",
                "intended_use": [
                    "private_character_reference",
                    "r4_visual_continuity",
                    "nscl_visual_design",
                ],
                "public_export": False,
            },
            {
                "character_id": "yd",
                "display_name": "Y.D.",
                "source_filename": SOURCE_YD.name,
                "controlled_path": OUTPUT_YD.as_posix(),
                "media_type": "image/jpeg",
                "byte_length": len(yd_bytes),
                "sha256": yd_sha,
                "creation_provenance": "creator_owned_generated_with_gemini_pro",
                "identity_context": "fictional_composite_character",
                "intended_use": [
                    "private_character_reference",
                    "r4_visual_continuity",
                    "yd_character_design",
                ],
                "public_export": False,
            },
        ],
        "policy": {
            "preserve_original_bytes": True,
            "automatic_publication": False,
            "automatic_canon_release": False,
            "provider_calls_executed": False,
            "clickhouse_mutation_executed": False,
            "frozen_r3_artifacts_modified": False,
        },
    }

    provenance_bytes = canonical_json_bytes(provenance)

    manifest_entries = [
        (
            sha256_file(IMPORTER_PATH),
            IMPORTER_PATH.as_posix(),
        ),
        (
            demian_sha,
            OUTPUT_DEMIAN.as_posix(),
        ),
        (
            yd_sha,
            OUTPUT_YD.as_posix(),
        ),
        (
            sha256_bytes(provenance_bytes),
            PROVENANCE_PATH.as_posix(),
        ),
    ]

    manifest_bytes = "".join(
        f"{digest}  {filename}\n"
        for digest, filename in manifest_entries
    ).encode("utf-8")

    created_paths: list[Path] = []

    try:
        write_atomic_new(OUTPUT_DEMIAN, demian_bytes)
        created_paths.append(OUTPUT_DEMIAN)

        write_atomic_new(OUTPUT_YD, yd_bytes)
        created_paths.append(OUTPUT_YD)

        write_atomic_new(PROVENANCE_PATH, provenance_bytes)
        created_paths.append(PROVENANCE_PATH)

        write_atomic_new(MANIFEST_PATH, manifest_bytes)
        created_paths.append(MANIFEST_PATH)

    except Exception:
        for path in reversed(created_paths):
            path.unlink(missing_ok=True)
        raise

    print(f"R4 Revision Run ID: {r4_revision_run_id}")
    print(f"Parent Revision Run ID: {PARENT_REVISION_RUN_ID}")
    print(f"Parent Draft SHA-256: {PARENT_DRAFT_SHA256}")
    print(f"Demian image SHA-256: {demian_sha}")
    print(f"Demian image bytes: {len(demian_bytes)}")
    print(f"Y.D. image SHA-256: {yd_sha}")
    print(f"Y.D. image bytes: {len(yd_bytes)}")
    print("Creator owned: True")
    print("Generated with: Google Gemini Pro")
    print("Public export authorized: False")
    print("Provider calls executed: False")
    print("ClickHouse mutation executed: False")
    print("Frozen R3 artifacts modified: False")
    print("P10G R4 REFERENCE IMAGE IMPORT: OK")


if __name__ == "__main__":
    main()
