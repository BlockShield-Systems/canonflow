#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import clickhouse_connect


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def stable_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)

    if value is None:
        return default

    normalized = value.strip().lower()

    if normalized in {"1", "true", "yes", "on"}:
        return True

    if normalized in {"0", "false", "no", "off"}:
        return False

    raise ValueError(f"Invalid boolean value for {name}: {value}")


def required(name: str) -> str:
    value = os.getenv(name)

    if not value:
        raise RuntimeError(f"Missing environment variable: {name}")

    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def existing_ids(
    client: Any,
    table: str,
    id_column: str,
    project_id: str,
) -> set[str]:
    result = client.query(
        f"""
        SELECT toString({id_column})
        FROM {table}
        WHERE project_id = {{project_id:UUID}}
        """,
        parameters={"project_id": project_id},
    )

    return {row[0] for row in result.result_rows}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--derived-root", type=Path, required=True)
    parser.add_argument("--quality-review", type=Path, required=True)
    parser.add_argument("--canon-decisions", type=Path, required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    project_id = str(uuid.UUID(args.project_id))
    derived = args.derived_root.resolve()

    documents = read_jsonl(derived / "source-documents.jsonl")
    pages = read_jsonl(derived / "pdf-pages.jsonl")
    chunks = read_jsonl(derived / "source-chunks.jsonl")

    quality_review = json.loads(
        args.quality_review.read_text(encoding="utf-8")
    )
    quality_reviews = quality_review["reviews"]

    decision_files = sorted(args.canon_decisions.glob("*.json"))

    if len(documents) != 11:
        raise RuntimeError(f"Expected 11 documents, found {len(documents)}.")

    if len(pages) != 45:
        raise RuntimeError(f"Expected 45 pages, found {len(pages)}.")

    if len(chunks) != 65:
        raise RuntimeError(f"Expected 65 chunks, found {len(chunks)}.")

    if len(quality_reviews) != 2:
        raise RuntimeError(
            f"Expected 2 quality reviews, found {len(quality_reviews)}."
        )

    decisions = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in decision_files
    ]

    required_decisions = {"YD-CANON-0001", "YD-CANON-0002"}
    found_decisions = {
        decision["decision_id"] for decision in decisions
    }

    missing_decisions = required_decisions - found_decisions

    if missing_decisions:
        raise RuntimeError(
            f"Missing canon decisions: {sorted(missing_decisions)}"
        )

    review_map = {
        (
            item["source_sha256"],
            item["page_number"],
        ): item
        for item in quality_reviews
    }

    database = os.getenv("CLICKHOUSE_DATABASE", "canonflow")

    client = clickhouse_connect.get_client(
        host=required("CLICKHOUSE_HOST"),
        port=int(os.getenv("CLICKHOUSE_PORT", "8443")),
        username=required("CLICKHOUSE_USER"),
        password=required("CLICKHOUSE_PASSWORD"),
        database=database,
        secure=env_bool("CLICKHOUSE_SECURE", True),
        verify=env_bool("CLICKHOUSE_VERIFY", True),
        connect_timeout=int(
            os.getenv("CLICKHOUSE_CONNECT_TIMEOUT", "10")
        ),
        send_receive_timeout=int(
            os.getenv("CLICKHOUSE_SEND_RECEIVE_TIMEOUT", "30")
        ),
    )

    inserted = {
        "source_documents": 0,
        "source_pages": 0,
        "source_chunks": 0,
        "source_quality_dispositions": 0,
        "canon_decisions": 0,
    }
    skipped = {key: 0 for key in inserted}
    timestamp = now_utc()

    try:
        project_result = client.query(
            """
            SELECT title
            FROM projects FINAL
            WHERE project_id = {project_id:UUID}
            LIMIT 1
            """,
            parameters={"project_id": project_id},
        )

        if not project_result.result_rows:
            raise RuntimeError(
                f"Project does not exist: {project_id}"
            )

        print(f"Project: {project_result.result_rows[0][0]}")
        print(f"Project ID: {project_id}")
        print()

        existing_documents = existing_ids(
            client,
            "source_documents",
            "document_id",
            project_id,
        )

        document_rows = []

        for document in documents:
            document_id = document["document_id"]

            if document_id in existing_documents:
                skipped["source_documents"] += 1
                continue

            derived_paths = document["derived_paths"]

            if document["media_type"] == "application/pdf":
                parts = []

                for page_number, relative_path in enumerate(
                    derived_paths,
                    start=1,
                ):
                    text = (derived / relative_path).read_text(
                        encoding="utf-8"
                    )
                    parts.append(
                        f"--- PAGE {page_number} ---\n{text.rstrip()}"
                    )

                content = "\n\n".join(parts) + "\n"
            else:
                if len(derived_paths) != 1:
                    raise RuntimeError(
                        f"Unexpected TXT derived paths: {derived_paths}"
                    )

                content = (derived / derived_paths[0]).read_text(
                    encoding="utf-8"
                )

            metadata = {
                "schema_version": document["schema_version"],
                "canon_status": document["canon_status"],
                "source_media_type": document["media_type"],
                "source_size_bytes": document["source_size_bytes"],
                "extraction_method": document["extraction_method"],
                "encoding": document["encoding"],
                "page_count": document["page_count"],
                "extracted_character_count": document[
                    "extracted_character_count"
                ],
                "chunk_count": document["chunk_count"],
                "derived_paths": derived_paths,
                "warnings": document["warnings"],
                "content_representation": "extracted_utf8_text",
            }

            document_rows.append(
                [
                    document_id,
                    project_id,
                    document["file_name"],
                    document["source_path"],
                    document["media_type"],
                    document["source_sha256"],
                    content,
                    stable_json(metadata),
                    timestamp,
                ]
            )

        if document_rows:
            client.insert(
                "source_documents",
                document_rows,
                column_names=[
                    "document_id",
                    "project_id",
                    "file_name",
                    "source_path",
                    "content_type",
                    "checksum_sha256",
                    "content",
                    "metadata_json",
                    "ingested_at",
                ],
            )
            inserted["source_documents"] = len(document_rows)

        existing_pages = existing_ids(
            client,
            "source_pages",
            "page_id",
            project_id,
        )
        page_rows = []

        for page in pages:
            page_id = str(
                uuid.uuid5(
                    uuid.UUID(page["document_id"]),
                    f'page:{page["page_number"]}',
                )
            )

            if page_id in existing_pages:
                skipped["source_pages"] += 1
                continue

            review = review_map.get(
                (
                    page["source_sha256"],
                    page["page_number"],
                )
            )

            if review:
                content_class = review["content_class"]
                indexable = review["indexable"]
                ocr_required = review["ocr_required"]
            else:
                content_class = "story_source"
                indexable = page["quality"] == "ok"
                ocr_required = page["quality"] == "empty"

            content = (derived / page["derived_path"]).read_text(
                encoding="utf-8"
            )

            metadata = {
                "source_path": page["source_path"],
                "source_sha256": page["source_sha256"],
                "derived_path": page["derived_path"],
                "quality_reviewed": review is not None,
            }

            page_rows.append(
                [
                    page_id,
                    page["document_id"],
                    project_id,
                    page["page_number"],
                    content,
                    page["text_sha256"],
                    page["extraction_method"],
                    page["character_count"],
                    page["visible_character_count"],
                    page["quality"],
                    content_class,
                    indexable,
                    ocr_required,
                    stable_json(metadata),
                    timestamp,
                ]
            )

        if page_rows:
            client.insert(
                "source_pages",
                page_rows,
                column_names=[
                    "page_id",
                    "document_id",
                    "project_id",
                    "page_number",
                    "content",
                    "checksum_sha256",
                    "extraction_method",
                    "character_count",
                    "visible_character_count",
                    "quality",
                    "content_class",
                    "indexable",
                    "ocr_required",
                    "metadata_json",
                    "extracted_at",
                ],
            )
            inserted["source_pages"] = len(page_rows)

        existing_chunks = existing_ids(
            client,
            "source_chunks",
            "chunk_id",
            project_id,
        )
        chunk_rows = []

        for chunk in chunks:
            chunk_id = chunk["chunk_id"]

            if chunk_id in existing_chunks:
                skipped["source_chunks"] += 1
                continue

            review = review_map.get(
                (
                    chunk["source_sha256"],
                    chunk["page_number"],
                )
            )
            indexable = not review or review["indexable"]

            metadata = {
                "source_path": chunk["source_path"],
                "source_sha256": chunk["source_sha256"],
                "quality_disposition_applied": (
                    review["quality_disposition"]
                    if review
                    else None
                ),
            }

            chunk_rows.append(
                [
                    chunk_id,
                    chunk["document_id"],
                    project_id,
                    chunk["sequence"],
                    chunk["locator_type"],
                    chunk["page_number"],
                    chunk["line_start"],
                    chunk["line_end"],
                    chunk["locator"],
                    chunk["text"],
                    sha256_text(chunk["text"]),
                    chunk["character_count"],
                    indexable,
                    stable_json(metadata),
                    timestamp,
                ]
            )

        if chunk_rows:
            client.insert(
                "source_chunks",
                chunk_rows,
                column_names=[
                    "chunk_id",
                    "document_id",
                    "project_id",
                    "sequence",
                    "locator_type",
                    "page_number",
                    "line_start",
                    "line_end",
                    "locator",
                    "content",
                    "checksum_sha256",
                    "character_count",
                    "indexable",
                    "metadata_json",
                    "created_at",
                ],
            )
            inserted["source_chunks"] = len(chunk_rows)

        existing_dispositions = existing_ids(
            client,
            "source_quality_dispositions",
            "disposition_id",
            project_id,
        )
        disposition_rows = []

        for review in quality_reviews:
            disposition_id = str(
                uuid.uuid5(
                    uuid.UUID(review["document_id"]),
                    (
                        f'quality:{review["page_number"]}:'
                        f'{review["quality_disposition"]}'
                    ),
                )
            )

            if disposition_id in existing_dispositions:
                skipped["source_quality_dispositions"] += 1
                continue

            disposition_rows.append(
                [
                    disposition_id,
                    project_id,
                    review["document_id"],
                    review["source_path"],
                    review["source_sha256"],
                    review["page_number"],
                    review["original_quality"],
                    review["quality_disposition"],
                    review["content_class"],
                    review["indexable"],
                    review["ocr_required"],
                    review["reason"],
                    stable_json(review),
                    timestamp,
                ]
            )

        if disposition_rows:
            client.insert(
                "source_quality_dispositions",
                disposition_rows,
                column_names=[
                    "disposition_id",
                    "project_id",
                    "document_id",
                    "source_path",
                    "source_sha256",
                    "page_number",
                    "original_quality",
                    "quality_disposition",
                    "content_class",
                    "indexable",
                    "ocr_required",
                    "reason",
                    "evidence_json",
                    "reviewed_at",
                ],
            )
            inserted["source_quality_dispositions"] = len(
                disposition_rows
            )

        existing_decisions = existing_ids(
            client,
            "canon_decisions",
            "decision_id",
            project_id,
        )
        decision_rows = []

        for decision in decisions:
            decision_id = decision["decision_id"]

            if decision_id in existing_decisions:
                skipped["canon_decisions"] += 1
                continue

            decision_rows.append(
                [
                    decision_id,
                    project_id,
                    decision["entity_type"],
                    decision["entity_id"],
                    decision["field"],
                    decision["status"],
                    stable_json(decision.get("previous_value")),
                    stable_json(decision.get("approved_value")),
                    decision.get("supersedes", []),
                    decision.get("scope", []),
                    decision.get("decision_source", ""),
                    decision.get("approved_by", ""),
                    decision.get("agent_directive", ""),
                    stable_json(decision),
                    parse_datetime(decision["approved_at_utc"]),
                    timestamp,
                ]
            )

        if decision_rows:
            client.insert(
                "canon_decisions",
                decision_rows,
                column_names=[
                    "decision_id",
                    "project_id",
                    "entity_type",
                    "entity_id",
                    "field",
                    "status",
                    "previous_value_json",
                    "approved_value_json",
                    "supersedes",
                    "scope",
                    "decision_source",
                    "approved_by",
                    "agent_directive",
                    "decision_json",
                    "approved_at",
                    "ingested_at",
                ],
            )
            inserted["canon_decisions"] = len(decision_rows)

        counts = {}

        for table in inserted:
            result = client.query(
                f"""
                SELECT count()
                FROM {table}
                WHERE project_id = {{project_id:UUID}}
                """,
                parameters={"project_id": project_id},
            )
            counts[table] = result.result_rows[0][0]

        nonindexable_pages = client.query(
            """
            SELECT count()
            FROM source_pages
            WHERE project_id = {project_id:UUID}
              AND indexable = false
            """,
            parameters={"project_id": project_id},
        ).result_rows[0][0]

        nonindexable_chunks = client.query(
            """
            SELECT count()
            FROM source_chunks
            WHERE project_id = {project_id:UUID}
              AND indexable = false
            """,
            parameters={"project_id": project_id},
        ).result_rows[0][0]

        report = {
            "schema_version": "1.0",
            "project_id": project_id,
            "completed_at_utc": now_utc().isoformat(),
            "inserted": inserted,
            "skipped": skipped,
            "database_counts": counts,
            "nonindexable_pages": nonindexable_pages,
            "nonindexable_chunks": nonindexable_chunks,
        }

        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        for table in inserted:
            print(
                f"{table}: "
                f"inserted={inserted[table]}, "
                f"skipped={skipped[table]}, "
                f"database={counts[table]}"
            )

        print(f"Non-indexable pages : {nonindexable_pages}")
        print(f"Non-indexable chunks: {nonindexable_chunks}")
        print(f"Report: {args.report}")
        print("SOURCE INTELLIGENCE INGESTION: OK")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
