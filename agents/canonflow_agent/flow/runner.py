"""Declarative graph runner. Loads a workflow JSON, topologically orders the
nodes from depends_on plus implicit expression references, executes them and
writes a hash-addressed run record."""
from __future__ import annotations

import hashlib
import json
import pathlib
import time
import traceback
import uuid
from typing import Any

from . import expr
from . import nodes as _nodes  # registers node kinds
from .nodes import base as noderegistry


class WorkflowError(RuntimeError):
    pass


def _order(nodes: list[dict]) -> list[dict]:
    by_id = {n["id"]: n for n in nodes}
    if len(by_id) != len(nodes):
        raise WorkflowError("duplicate node id")
    deps = {
        n["id"]: (set(n.get("depends_on", [])) | expr.refs(n.get("params", {})))
        & set(by_id)
        for n in nodes
    }
    done: list[dict] = []
    seen: set[str] = set()
    while len(done) < len(nodes):
        ready = [n for n in nodes
                 if n["id"] not in seen and deps[n["id"]] <= seen]
        if not ready:
            stuck = [n["id"] for n in nodes if n["id"] not in seen]
            raise WorkflowError(f"cycle or missing dependency among {stuck}")
        ready.sort(key=lambda n: n["id"])
        for n in ready:
            done.append(n)
            seen.add(n["id"])
    return done


REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]


def run(workflow_path: str, inputs: dict[str, Any], *,
        dry_run: bool = True, run_root: str = "var/runs") -> dict:
    wf = json.loads(pathlib.Path(workflow_path).read_text(encoding="utf-8"))
    run_id = uuid.uuid4().hex[:12]
    root = pathlib.Path(run_root)
    if not root.is_absolute():
        root = REPO_ROOT / root
    run_dir = root / run_id
    (run_dir / "nodes").mkdir(parents=True, exist_ok=True)

    ctx: dict[str, Any] = {
        "input": inputs,
        "config": wf.get("config", {}),
        "nodes": {},
        "run": {"id": run_id, "dir": str(run_dir), "dry_run": dry_run},
    }

    record: dict[str, Any] = {
        "run_id": run_id,
        "workflow": wf.get("name", pathlib.Path(workflow_path).stem),
        "workflow_version": wf.get("version"),
        "workflow_sha256": hashlib.sha256(
            pathlib.Path(workflow_path).read_bytes()).hexdigest(),
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "dry_run": dry_run,
        "inputs": inputs,
        "nodes": [],
        "est_usd_total": 0.0,
        "status": "running",
        "run_dir": str(run_dir),
    }

    for spec in _order(wf["nodes"]):
        nid, kind = spec["id"], spec["kind"]
        impl = noderegistry.get(kind)
        entry: dict[str, Any] = {"id": nid, "kind": kind, "costs": impl.costs}
        t0 = time.time()
        try:
            params = expr.resolve(spec.get("params", {}), ctx)
            if impl.costs and dry_run:
                out = {"skipped": "dry_run", "params": params}
                entry["status"] = "skipped"
            else:
                out = impl.fn(**params)
                entry["status"] = "ok"
            ctx["nodes"][nid] = {"output": out}
            if isinstance(out, dict) and "est_usd" in out:
                record["est_usd_total"] += float(out["est_usd"])
                entry["est_usd"] = out["est_usd"]
            if isinstance(out, dict) and "usage" in out:
                entry["usage"] = out["usage"]
            (run_dir / "nodes" / f"{nid}.json").write_text(
                json.dumps(out, indent=2, ensure_ascii=False, default=str),
                encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            entry.update(status="error", error=f"{type(exc).__name__}: {exc}")
            (run_dir / "nodes" / f"{nid}.error.txt").write_text(
                traceback.format_exc(), encoding="utf-8")
            if spec.get("on_error") == "continue":
                entry["status"] = "tolerated"
                fallback = spec.get("on_error_output", {})
                ctx["nodes"][nid] = {"output": fallback}
                record["nodes"].append(entry)
                continue
            record["nodes"].append(entry)
            record["status"] = "error"
            record["failed_node"] = nid
            record["run_dir"] = str(run_dir)
            _finalize(run_dir, record)
            raise WorkflowError(
                f"node '{nid}' ({kind}) failed: {exc}\n"
                f"run record: {run_dir / 'run.json'}") from exc
        finally:
            entry["seconds"] = round(time.time() - t0, 2)
        record["nodes"].append(entry)

    record["status"] = "ok"
    record["est_usd_total"] = round(record["est_usd_total"], 4)
    _finalize(run_dir, record)
    return record


def _finalize(run_dir: pathlib.Path, record: dict) -> None:
    record["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    blob = json.dumps(record, indent=2, ensure_ascii=False, default=str)
    (run_dir / "run.json").write_text(blob, encoding="utf-8")
    (run_dir / "run.sha256").write_text(
        hashlib.sha256(blob.encode()).hexdigest() + "  run.json\n", encoding="utf-8")
