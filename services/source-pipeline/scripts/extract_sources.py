#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import unicodedata
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pypdf import PdfReader


SCHEMA_VERSION = "1.0"
EXTRACTOR_VERSION = "0.1.0"
MAX_CHUNK_CHARS = 6000
CHUNK_LINE_OVERLAP = 6
LOW_TEXT_THRESHOLD = 80


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)

    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(
                json.dumps(record, ensure_ascii=False, separators=(",", ":"))
                + "\n"
            )


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\x00", "")

    lines = [line.rstrip() for line in text.split("\n")]

    while lines and not lines[-1]:
        lines.pop()

    return "\n".join(lines) + "\n" if lines else ""


def visible_character_count(text: str) -> int:
    return sum(1 for character in text if not character.isspace())


def decode_text_file(path: Path) -> tuple[str, str]:
    data = path.read_bytes()
    attempts = ("utf-8-sig", "utf-16", "cp1252")

    for encoding in attempts:
        try:
            return normalize_text(data.decode(encoding)), encoding
        except UnicodeDecodeError:
            continue

    raise ValueError(f"Unable to decode text file: {path}")


def safe_component(value: str) -> str:
    value = value.replace("\\", "/")
    value = re.sub(r"[^A-Za-z0-9._/-]+", "-", value)
    value = re.sub(r"-+", "-", value)
    return value.strip("-/")


def extract_pdf_page(page: Any) -> tuple[str, str]:
    try:
        text = page.extract_text(
            extraction_mode="layout",
            layout_mode_space_vertically=False,
        )
        method = "pypdf-layout"
    except Exception:
        text = page.extract_text()
        method = "pypdf-plain-fallback"

    return normalize_text(text or ""), method


def split_into_chunks(
    text: str,
    *,
    document_id: str,
    source_path: str,
    source_sha256: str,
    locator_type: str,
    page_number: int | None,
    max_chars: int,
    line_overlap: int,
) -> list[dict[str, Any]]:
    lines = text.splitlines()

    if not lines:
        return []

    chunks: list[dict[str, Any]] = []
    start = 0
    sequence = 1

    while start < len(lines):
        end = start
        current_chars = 0

        while end < len(lines):
            line_size = len(lines[end]) + 1

            if end > start and current_chars + line_size > max_chars:
                break

            current_chars += line_size
            end += 1

        selected_lines = lines[start:end]
        chunk_text = "\n".join(selected_lines).strip()

        if chunk_text:
            line_start = start + 1
            line_end = end
            locator = (
                f"page:{page_number}:lines:{line_start}-{line_end}"
                if page_number is not None
                else f"lines:{line_start}-{line_end}"
            )

            chunk_id = str(
                uuid.uuid5(
                    uuid.UUID(document_id),
                    f"{locator}:{sequence}",
                )
            )

            chunks.append(
                {
                    "schema_version": SCHEMA_VERSION,
                    "chunk_id": chunk_id,
                    "document_id": document_id,
                    "sequence": sequence,
                    "source_path": source_path,
                    "source_sha256": source_sha256,
                    "locator_type": locator_type,
                    "page_number": page_number,
                    "line_start": line_start,
                    "line_end": line_end,
                    "locator": locator,
                    "text": chunk_text,
                    "character_count": len(chunk_text),
                }
            )

            sequence += 1

        if end >= len(lines):
            break

        next_start = max(start + 1, end - line_overlap)

        if next_start <= start:
            next_start = end

        start = next_start

    return chunks


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract verified CanonFlow PDF/TXT sources."
    )
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--max-chunk-chars", type=int, default=MAX_CHUNK_CHARS)
    parser.add_argument(
        "--chunk-line-overlap",
        type=int,
        default=CHUNK_LINE_OVERLAP,
    )
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()

    source_root = args.source_root.resolve()
    source_manifest_path = args.source_manifest.resolve()
    output_root = args.output_root.resolve()

    if not source_root.is_dir():
        raise SystemExit(f"Source root does not exist: {source_root}")

    if not source_manifest_path.is_file():
        raise SystemExit(
            f"Source manifest does not exist: {source_manifest_path}"
        )

    try:
        project_uuid = uuid.UUID(args.project_id)
    except ValueError as error:
        raise SystemExit(f"Invalid project UUID: {args.project_id}") from error

    source_manifest = json.loads(
        source_manifest_path.read_text(encoding="utf-8")
    )
    entries = source_manifest.get("entries", [])

    if not entries:
        raise SystemExit("Source manifest contains no entries.")

    temporary_root = output_root.with_name(output_root.name + ".tmp")

    if temporary_root.exists():
        shutil.rmtree(temporary_root)

    temporary_root.mkdir(parents=True)

    documents: list[dict[str, Any]] = []
    chunks: list[dict[str, Any]] = []
    page_records: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    pdf_count = 0
    txt_count = 0
    total_pages = 0

    try:
        for manifest_entry in sorted(
            entries,
            key=lambda item: str(item["relative_path"]).casefold(),
        ):
            relative_path = str(manifest_entry["relative_path"])
            expected_sha256 = str(manifest_entry["sha256"])
            source_file = source_root / relative_path

            if not source_file.is_file():
                raise RuntimeError(f"Missing source file: {source_file}")

            actual_sha256 = sha256_file(source_file)

            if actual_sha256 != expected_sha256:
                raise RuntimeError(
                    "Source hash mismatch:\n"
                    f"File: {source_file}\n"
                    f"Expected: {expected_sha256}\n"
                    f"Actual:   {actual_sha256}"
                )

            document_id = str(
                uuid.uuid5(
                    project_uuid,
                    f"{relative_path}:{actual_sha256}",
                )
            )

            suffix = source_file.suffix.lower()
            derived_base = Path("documents") / safe_component(relative_path)
            document_chunks: list[dict[str, Any]] = []
            derived_paths: list[str] = []
            document_warnings: list[str] = []
            extracted_characters = 0
            page_count: int | None = None
            encoding: str | None = None
            extraction_method: str

            if suffix == ".pdf":
                pdf_count += 1
                extraction_method = "pypdf-6.16.2"

                reader = PdfReader(str(source_file))

                if reader.is_encrypted:
                    decrypt_result = reader.decrypt("")

                    if not decrypt_result:
                        raise RuntimeError(
                            f"Encrypted PDF cannot be opened: {relative_path}"
                        )

                page_count = len(reader.pages)
                total_pages += page_count
                pages_dir = temporary_root / (
                    str(derived_base) + ".pages"
                )
                pages_dir.mkdir(parents=True, exist_ok=True)

                for page_index, page in enumerate(reader.pages, start=1):
                    text, page_method = extract_pdf_page(page)
                    page_file = pages_dir / f"page-{page_index:04d}.txt"
                    page_file.write_text(text, encoding="utf-8", newline="\n")

                    final_relative = page_file.relative_to(
                        temporary_root
                    ).as_posix()
                    derived_paths.append(final_relative)

                    visible_chars = visible_character_count(text)
                    extracted_characters += len(text)

                    if visible_chars == 0:
                        quality = "empty"
                        warning = (
                            f"PDF page {page_index} contains no extractable text."
                        )
                        document_warnings.append(warning)
                    elif visible_chars < LOW_TEXT_THRESHOLD:
                        quality = "low_text"
                        warning = (
                            f"PDF page {page_index} contains only "
                            f"{visible_chars} visible characters."
                        )
                        document_warnings.append(warning)
                    else:
                        quality = "ok"

                    page_record = {
                        "schema_version": SCHEMA_VERSION,
                        "document_id": document_id,
                        "source_path": relative_path,
                        "source_sha256": actual_sha256,
                        "page_number": page_index,
                        "extraction_method": page_method,
                        "derived_path": final_relative,
                        "text_sha256": sha256_file(page_file),
                        "character_count": len(text),
                        "visible_character_count": visible_chars,
                        "quality": quality,
                    }
                    page_records.append(page_record)

                    document_chunks.extend(
                        split_into_chunks(
                            text,
                            document_id=document_id,
                            source_path=relative_path,
                            source_sha256=actual_sha256,
                            locator_type="pdf_page_lines",
                            page_number=page_index,
                            max_chars=args.max_chunk_chars,
                            line_overlap=args.chunk_line_overlap,
                        )
                    )

            elif suffix == ".txt":
                txt_count += 1
                text, encoding = decode_text_file(source_file)
                extraction_method = f"text-decode:{encoding}"

                output_file = temporary_root / (
                    str(derived_base) + ".normalized.txt"
                )
                output_file.parent.mkdir(parents=True, exist_ok=True)
                output_file.write_text(text, encoding="utf-8", newline="\n")

                final_relative = output_file.relative_to(
                    temporary_root
                ).as_posix()
                derived_paths.append(final_relative)
                extracted_characters = len(text)

                if visible_character_count(text) == 0:
                    document_warnings.append(
                        "Text source contains no visible characters."
                    )

                document_chunks.extend(
                    split_into_chunks(
                        text,
                        document_id=document_id,
                        source_path=relative_path,
                        source_sha256=actual_sha256,
                        locator_type="text_lines",
                        page_number=None,
                        max_chars=args.max_chunk_chars,
                        line_overlap=args.chunk_line_overlap,
                    )
                )

            else:
                raise RuntimeError(
                    f"Unsupported source type: {relative_path}"
                )

            for warning in document_warnings:
                warnings.append(
                    {
                        "document_id": document_id,
                        "source_path": relative_path,
                        "warning": warning,
                    }
                )

            document_record = {
                "schema_version": SCHEMA_VERSION,
                "document_id": document_id,
                "project_id": str(project_uuid),
                "source_path": relative_path,
                "file_name": source_file.name,
                "media_type": manifest_entry["media_type"],
                "source_sha256": actual_sha256,
                "source_size_bytes": source_file.stat().st_size,
                "extraction_method": extraction_method,
                "encoding": encoding,
                "page_count": page_count,
                "extracted_character_count": extracted_characters,
                "chunk_count": len(document_chunks),
                "derived_paths": derived_paths,
                "warnings": document_warnings,
                "canon_status": "source",
            }

            documents.append(document_record)
            chunks.extend(document_chunks)

            print(
                f'OK  {relative_path} | '
                f'{len(document_chunks)} chunks | '
                f'{extracted_characters} chars'
            )

        write_jsonl(
            temporary_root / "source-documents.jsonl",
            documents,
        )
        write_jsonl(
            temporary_root / "source-chunks.jsonl",
            chunks,
        )
        write_jsonl(
            temporary_root / "pdf-pages.jsonl",
            page_records,
        )

        quality_report = {
            "schema_version": SCHEMA_VERSION,
            "extractor_version": EXTRACTOR_VERSION,
            "generated_at_utc": utc_now(),
            "project_id": str(project_uuid),
            "source_manifest": str(source_manifest_path),
            "source_document_count": len(documents),
            "pdf_document_count": pdf_count,
            "text_document_count": txt_count,
            "pdf_page_count": total_pages,
            "chunk_count": len(chunks),
            "warning_count": len(warnings),
            "warnings": warnings,
        }
        write_json(
            temporary_root / "quality-report.json",
            quality_report,
        )

        report_lines = [
            "# CanonFlow Source Extraction Quality Report",
            "",
            f"- Project ID: `{project_uuid}`",
            f"- Documents: **{len(documents)}**",
            f"- PDF documents: **{pdf_count}**",
            f"- TXT documents: **{txt_count}**",
            f"- PDF pages: **{total_pages}**",
            f"- Chunks: **{len(chunks)}**",
            f"- Warnings: **{len(warnings)}**",
            "",
            "## Warnings",
            "",
        ]

        if warnings:
            for warning in warnings:
                report_lines.append(
                    f'- `{warning["source_path"]}`: {warning["warning"]}'
                )
        else:
            report_lines.append("- None")

        report_lines.append("")
        (temporary_root / "quality-report.md").write_text(
            "\n".join(report_lines),
            encoding="utf-8",
            newline="\n",
        )

        artifact_records = []

        for artifact in sorted(
            (
                path
                for path in temporary_root.rglob("*")
                if path.is_file()
            ),
            key=lambda path: path.as_posix().casefold(),
        ):
            artifact_records.append(
                {
                    "relative_path": artifact.relative_to(
                        temporary_root
                    ).as_posix(),
                    "size_bytes": artifact.stat().st_size,
                    "sha256": sha256_file(artifact),
                }
            )

        extraction_manifest = {
            "schema_version": SCHEMA_VERSION,
            "extractor_version": EXTRACTOR_VERSION,
            "generated_at_utc": utc_now(),
            "project_id": str(project_uuid),
            "source_root": str(source_root),
            "source_manifest": str(source_manifest_path),
            "source_manifest_sha256": sha256_file(source_manifest_path),
            "document_count": len(documents),
            "chunk_count": len(chunks),
            "artifact_count": len(artifact_records),
            "artifacts": artifact_records,
        }
        write_json(
            temporary_root / "extraction-manifest.json",
            extraction_manifest,
        )

        if output_root.exists():
            shutil.rmtree(output_root)

        temporary_root.replace(output_root)

    except Exception:
        if temporary_root.exists():
            shutil.rmtree(temporary_root)
        raise

    print()
    print(f"Documents : {len(documents)}")
    print(f"PDF files : {pdf_count}")
    print(f"TXT files : {txt_count}")
    print(f"PDF pages : {total_pages}")
    print(f"Chunks    : {len(chunks)}")
    print(f"Warnings  : {len(warnings)}")
    print(f"Output    : {output_root}")
    print()
    print("SOURCE EXTRACTION: OK")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
