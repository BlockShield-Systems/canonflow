from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types


MINIMUM_CHARACTERS = 12_000
MAX_OUTPUT_TOKENS = 32_768
TEMPERATURE = 0.2

EXPECTED_IDS = [
    "YD-CANON-0001",
    "YD-CANON-0002",
    "YD-CANON-0003",
    "YD-CANON-0004",
    "YD-CANON-0005",
    "YD-CANON-0006",
]

END_MARKER = "P10F CANON STORY BIBLE DRAFT END"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def json_safe(value: Any) -> Any:
    if value is None:
        return None

    if isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, dict):
        return {
            str(key): json_safe(child)
            for key, child in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [json_safe(child) for child in value]

    if hasattr(value, "model_dump"):
        try:
            return value.model_dump(
                mode="json",
                exclude_none=True,
            )
        except TypeError:
            return value.model_dump(exclude_none=True)

    name = getattr(value, "name", None)

    if isinstance(name, str):
        return name

    return str(value)


def extract_text(response: Any) -> str:
    try:
        text = response.text
    except Exception:
        text = None

    if isinstance(text, str) and text.strip():
        return text.strip()

    fragments: list[str] = []

    for candidate in getattr(response, "candidates", None) or []:
        content = getattr(candidate, "content", None)

        for part in getattr(content, "parts", None) or []:
            part_text = getattr(part, "text", None)

            if isinstance(part_text, str) and part_text:
                fragments.append(part_text)

    return "\n".join(fragments).strip()


def response_metadata(response: Any) -> dict[str, Any]:
    candidates = getattr(response, "candidates", None) or []

    candidate_data = []

    for candidate in candidates:
        candidate_data.append(
            {
                "finish_reason": json_safe(
                    getattr(candidate, "finish_reason", None)
                ),
                "finish_message": json_safe(
                    getattr(candidate, "finish_message", None)
                ),
                "safety_ratings": json_safe(
                    getattr(candidate, "safety_ratings", None)
                ),
            }
        )

    return {
        "response_id": json_safe(
            getattr(response, "response_id", None)
        ),
        "model_version": json_safe(
            getattr(response, "model_version", None)
        ),
        "usage_metadata": json_safe(
            getattr(response, "usage_metadata", None)
        ),
        "prompt_feedback": json_safe(
            getattr(response, "prompt_feedback", None)
        ),
        "candidates": candidate_data,
    }


def archive_rejected_response(
    output_dir: Path,
    run_id: str,
    text: str,
    metadata: dict[str, Any],
    failures: list[str],
) -> Path:
    failed_dir = (
        output_dir
        / f"failed-draft-{run_id}-contract-rejection"
    )

    failed_dir.mkdir(parents=False, exist_ok=False)

    rejected_path = failed_dir / "model-response.md"
    metadata_path = failed_dir / "rejection.json"

    rejected_path.write_text(
        text + ("\n" if text else ""),
        encoding="utf-8",
    )

    metadata_path.write_text(
        json.dumps(
            {
                "status": "rejected_generation_contract",
                "run_id": run_id,
                "failures": failures,
                "response": metadata,
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    checksums = failed_dir / "SHA256SUMS"
    checksums.write_text(
        f"{sha256(rejected_path)}  model-response.md\n"
        f"{sha256(metadata_path)}  rejection.json\n",
        encoding="utf-8",
    )

    return failed_dir


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--input",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--contract",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--model",
        required=True,
    )

    args = parser.parse_args()

    input_path = args.input.resolve()
    contract_path = args.contract.resolve()
    output_dir = args.output_dir.resolve()

    draft_path = output_dir / "10-canon-story-bible-draft.md"
    summary_path = (
        output_dir
        / "11-canon-story-bible-generation-summary.json"
    )

    for path in [
        input_path,
        contract_path,
    ]:
        if not path.is_file():
            raise SystemExit(f"Required file missing: {path}")

    for path in [
        draft_path,
        summary_path,
    ]:
        if path.exists():
            raise SystemExit(
                f"Refusing to overwrite existing output: {path}"
            )

    api_key = os.environ.get("GOOGLE_API_KEY")

    if not api_key:
        raise SystemExit("GOOGLE_API_KEY is not exported")

    contract = json.loads(
        contract_path.read_text(encoding="utf-8")
    )

    if contract.get("status") != (
        "awaiting_controlled_draft_generation"
    ):
        raise SystemExit(
            "Generation contract is not awaiting generation"
        )

    authority = contract.get("authority", {})

    if authority.get("database_mutation_permitted") is not False:
        raise SystemExit(
            "Generation contract permits database mutation"
        )

    if authority.get(
        "autonomous_canon_changes_permitted"
    ) is not False:
        raise SystemExit(
            "Generation contract permits autonomous canon changes"
        )

    required_sections = contract.get("required_sections", [])

    if len(required_sections) != 17:
        raise SystemExit(
            f"Expected 17 required sections, "
            f"found {len(required_sections)}"
        )

    generation_input = input_path.read_text(encoding="utf-8")

    run_id = str(uuid.uuid4())
    started_at = datetime.now(
        timezone.utc
    ).isoformat(timespec="milliseconds")
    started = time.monotonic()

    client = genai.Client(api_key=api_key)

    response = client.models.generate_content(
        model=args.model,
        contents=generation_input,
        config=types.GenerateContentConfig(
            system_instruction=(
                "You are producing a controlled Canon Story Bible "
                "review draft. Follow the embedded generation "
                "contract exactly. Never claim human approval, never "
                "invent unsupported canon, never resolve explicitly "
                "unresolved mysteries, and never request or perform "
                "database mutations. Return Markdown only."
            ),
            response_mime_type="text/plain",
            temperature=TEMPERATURE,
            max_output_tokens=MAX_OUTPUT_TOKENS,
        ),
    )

    duration_ms = int(
        (time.monotonic() - started) * 1000
    )
    completed_at = datetime.now(
        timezone.utc
    ).isoformat(timespec="milliseconds")

    text = extract_text(response)
    metadata = response_metadata(response)

    failures: list[str] = []

    if not text:
        failures.append("MODEL_RETURNED_NO_TEXT")

    if len(text) < MINIMUM_CHARACTERS:
        failures.append(
            f"DRAFT_TOO_SHORT:{len(text)}"
        )

    if END_MARKER not in text:
        failures.append("END_MARKER_MISSING")

    for section in required_sections:
        if section not in text:
            failures.append(
                f"REQUIRED_SECTION_MISSING:{section}"
            )

    for decision_id in EXPECTED_IDS:
        if decision_id not in text:
            failures.append(
                f"CANON_DECISION_REFERENCE_MISSING:"
                f"{decision_id}"
            )

    if failures:
        failed_dir = archive_rejected_response(
            output_dir=output_dir,
            run_id=run_id,
            text=text,
            metadata=metadata,
            failures=failures,
        )

        print(
            f"Rejected model output archived: {failed_dir}",
            file=sys.stderr,
        )

        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)

        return 1

    if not text.endswith(END_MARKER):
        text = text.rstrip() + "\n\n" + END_MARKER

    draft_path.write_text(
        text.rstrip() + "\n",
        encoding="utf-8",
    )

    summary = {
        "schema_version": 1,
        "workflow": "P10F Canon Story Bible",
        "stage": "controlled_draft_generation",
        "status": "generated_awaiting_validation",
        "run_id": run_id,
        "started_at_utc": started_at,
        "completed_at_utc": completed_at,
        "duration_ms": duration_ms,
        "model": args.model,
        "sdk": {
            "name": "google-genai",
            "version": importlib.metadata.version(
                "google-genai"
            ),
        },
        "generation_config": {
            "temperature": TEMPERATURE,
            "max_output_tokens": MAX_OUTPUT_TOKENS,
            "response_mime_type": "text/plain",
            "streaming": False,
            "tools": False,
            "database_access": False,
        },
        "authority": {
            "human_authority": "Demian",
            "database_mutation_performed": False,
            "autonomous_canon_change_performed": False,
            "draft_is_approved_canon": False,
            "human_review_required": True,
        },
        "input": {
            "path": str(input_path),
            "bytes": input_path.stat().st_size,
            "sha256": sha256(input_path),
        },
        "contract": {
            "path": str(contract_path),
            "bytes": contract_path.stat().st_size,
            "sha256": sha256(contract_path),
        },
        "output": {
            "path": str(draft_path),
            "bytes": draft_path.stat().st_size,
            "characters": len(
                draft_path.read_text(encoding="utf-8")
            ),
            "sha256": sha256(draft_path),
            "required_sections_found": 17,
            "canon_decision_references_found": 6,
            "end_marker_found": True,
        },
        "response": metadata,
    }

    summary_path.write_text(
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    print(f"Run ID: {run_id}")
    print(f"Model: {args.model}")
    print(f"Draft characters: {summary['output']['characters']}")
    print("Required sections: 17")
    print("Canon decision references: 6")
    print(f"Draft: {draft_path}")
    print(f"Summary: {summary_path}")
    print("P10F CANON STORY BIBLE GENERATION: OK")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
