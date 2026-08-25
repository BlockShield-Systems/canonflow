#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXCLUDED_PARTS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    "dist",
    "build",
}

INVENTORY_SUFFIXES = {
    ".py",
    ".toml",
    ".json",
    ".yaml",
    ".yml",
    ".md",
    ".sql",
}

SIGNAL_PATTERN = re.compile(
    r"("
    r"\bAgent\s*\(|"
    r"\bLlmAgent\s*\(|"
    r"\bRunner\s*\(|"
    r"\bMCPToolset\b|"
    r"\bMcpToolset\b|"
    r"\bFastMCP\b|"
    r"@[\w.]*tool\b|"
    r"\bget_client\s*\(|"
    r"\brun_query\b|"
    r"\btool_context\b|"
    r"\bToolContext\b|"
    r"\bgemini[-\w.]*|"
    r"\bgoogle[-_.]adk\b|"
    r"\bcontinuity_findings\b|"
    r"\bsource_documents\b|"
    r"\bsource_chunks\b"
    r")",
    re.IGNORECASE,
)

SENSITIVE_PATTERN = re.compile(
    r"(?i)"
    r"(password|passwd|secret|api[_-]?key|access[_-]?token|bearer)"
    r"(\s*[=:]\s*)"
    r"([^\s,;]+)"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)

    return digest.hexdigest()


def is_excluded(path: Path) -> bool:
    return any(part in EXCLUDED_PARTS for part in path.parts)


def redact(value: str) -> str:
    return SENSITIVE_PATTERN.sub(
        lambda match: (
            f"{match.group(1)}{match.group(2)}<REDACTED>"
        ),
        value,
    )


def git_info(root: Path) -> dict[str, Any]:
    def run(*args: str) -> str | None:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            return None

        return result.stdout.strip()

    return {
        "repository_root": run("rev-parse", "--show-toplevel"),
        "branch": run("branch", "--show-current"),
        "commit": run("rev-parse", "HEAD"),
        "status_short": run("status", "--short"),
    }


def load_pyproject(path: Path) -> dict[str, Any]:
    import tomllib

    data = tomllib.loads(path.read_text(encoding="utf-8"))
    project = data.get("project", {})

    dependencies = project.get("dependencies", [])

    optional_dependencies = project.get(
        "optional-dependencies",
        {},
    )

    return {
        "path": str(path),
        "name": project.get("name"),
        "version": project.get("version"),
        "requires_python": project.get("requires-python"),
        "dependencies": dependencies,
        "optional_dependencies": optional_dependencies,
        "dependency_groups": data.get("dependency-groups", {}),
    }


def inspect_root(project_root: Path, root: Path) -> dict[str, Any]:
    if not root.exists():
        return {
            "path": str(root),
            "exists": False,
            "files": [],
            "pyprojects": [],
            "integration_signals": [],
        }

    files = []
    pyprojects = []
    signals = []

    for path in sorted(root.rglob("*")):
        if not path.is_file() or is_excluded(path):
            continue

        relative = path.relative_to(project_root)

        if path.suffix.lower() not in INVENTORY_SUFFIXES:
            continue

        if path.stat().st_size > 2 * 1024 * 1024:
            continue

        files.append(
            {
                "path": relative.as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )

        if path.name == "pyproject.toml":
            try:
                pyprojects.append(load_pyproject(path))
            except Exception as error:
                pyprojects.append(
                    {
                        "path": str(path),
                        "error": str(error),
                    }
                )

        if path.suffix.lower() not in {
            ".py",
            ".toml",
            ".yaml",
            ".yml",
            ".json",
            ".sql",
        }:
            continue

        try:
            text = path.read_text(
                encoding="utf-8",
                errors="replace",
            )
        except OSError:
            continue

        for line_number, line in enumerate(
            text.splitlines(),
            start=1,
        ):
            if SIGNAL_PATTERN.search(line):
                signals.append(
                    {
                        "path": relative.as_posix(),
                        "line": line_number,
                        "text": redact(line.strip())[:1000],
                    }
                )

    return {
        "path": str(root),
        "exists": True,
        "file_count": len(files),
        "files": files,
        "pyprojects": pyprojects,
        "integration_signals": signals,
    }


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()
    project_root = args.project_root.resolve()
    output = args.output.resolve()

    inspected_roots = [
        project_root / "agents" / "canonflow_agent",
        project_root / "services" / "mcp-clickhouse",
        project_root / "services" / "source-pipeline",
    ]

    report = {
        "schema_version": "1.0",
        "inspection_type": "p10_agent_stack_inventory",
        "generated_at_utc": utc_now(),
        "project_root": str(project_root),
        "git": git_info(project_root),
        "roots": [
            inspect_root(project_root, root)
            for root in inspected_roots
        ],
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Project root: {project_root}")
    print(f"Git branch  : {report['git']['branch']}")
    print(f"Git commit  : {report['git']['commit']}")
    print()

    for root in report["roots"]:
        print(f'Root: {root["path"]}')
        print(f'  Exists : {root["exists"]}')
        print(f'  Files  : {root.get("file_count", 0)}')
        print(f'  Signals: {len(root["integration_signals"])}')

        for pyproject in root["pyprojects"]:
            print(f'  Package: {pyproject.get("name")}')
            print(f'  Version: {pyproject.get("version")}')
            print(
                "  Python : "
                f'{pyproject.get("requires_python")}'
            )

            for dependency in pyproject.get("dependencies", []):
                print(f"    dependency: {dependency}")

        print()

    print(f"Report: {output}")
    print("P10 AGENT STACK INVENTORY: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
