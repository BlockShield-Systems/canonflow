"""Free diagnostics for the flow layer. No billable calls.

Usage:
  uv run python -m canonflow_agent.flow.diagnose
  uv run python -m canonflow_agent.flow.diagnose --query "text" --top-k 5
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

from .nodes.retrieval import rag_list_corpora, rag_retrieve

WF_DIR = pathlib.Path(__file__).resolve().parent / "workflows"


def corpus_id(name: str) -> str:
    """Last path segment. A corpus resource name is valid with either the
    project number or the project id, so only the trailing id is comparable."""
    return name.rstrip("/").rsplit("/", 1)[-1]


def corpus_from_workflow(name: str = "beat_to_prompts.json") -> str:
    cfg = json.loads((WF_DIR / name).read_text(encoding="utf-8")).get("config", {})
    corpus = cfg.get("rag_corpus")
    if not corpus:
        raise SystemExit(f"config.rag_corpus missing in {name}")
    return corpus


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="canonflow-diagnose")
    ap.add_argument("--workflow", default="beat_to_prompts.json")
    ap.add_argument("--corpus", default=None)
    ap.add_argument("--query", default="Y.D. character canon and continuity")
    ap.add_argument("--top-k", type=int, default=3)
    ap.add_argument("--threshold", type=float, default=0.6)
    a = ap.parse_args(argv)

    target = a.corpus or corpus_from_workflow(a.workflow)

    listed = rag_list_corpora()
    want = corpus_id(target)
    match = next((c for c in listed["corpora"] if corpus_id(c["name"]) == want), None)

    print(f"corpora in project: {listed['count']}")
    for c in listed["corpora"]:
        mark = "->" if corpus_id(c["name"]) == want else "  "
        print(f" {mark} {c['name']}")
        print(f"      display_name: {c['display_name']}")

    if match is None:
        print(f"\nERROR: corpus id {want} not found in this project or location")
        return 1

    if match["name"] != target:
        print(f"\nnote: same corpus id, different projection")
        print(f"  configured: {target}")
        print(f"  canonical : {match['name']}")
    target = match["name"]

    out = rag_retrieve(query=a.query, corpus=target,
                       top_k=a.top_k, distance_threshold=a.threshold)
    print(f"\nquery: {a.query}\ncontexts: {out['count']}")
    for c in out["contexts"]:
        d = f"{c['distance']:.4f}" if c["distance"] is not None else "-"
        print(f"   {d}  {c['source'][:90]}")
        print(f"      {c['text'][:140].replace(chr(10), ' ')}")
    if out["count"] == 0:
        print("\nWARNING: zero contexts. Raise --threshold or check ingestion.")
        return 1
    print("\nRESULT=PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
