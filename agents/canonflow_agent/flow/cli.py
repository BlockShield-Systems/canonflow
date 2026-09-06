"""python -m canonflow_agent.flow.cli run <workflow.json> --input k=v [--execute]"""
from __future__ import annotations

import argparse
import json
import sys

from .runner import run


def _kv(pairs: list[str]) -> dict:
    out: dict = {}
    for p in pairs:
        k, _, v = p.partition("=")
        if not k or not _:
            raise SystemExit(f"bad --input '{p}', expected key=value")
        if v.startswith("@"):
            v = open(v[1:], encoding="utf-8").read()
        out[k] = v
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="canonflow-flow")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run")
    r.add_argument("workflow")
    r.add_argument("--input", action="append", default=[])
    r.add_argument("--execute", action="store_true",
                   help="run cost-bearing nodes; default is dry-run")
    r.add_argument("--run-root", default="var/runs")

    g = sub.add_parser("graph")
    g.add_argument("workflow")

    a = ap.parse_args(argv)

    if a.cmd == "graph":
        wf = json.load(open(a.workflow, encoding="utf-8"))
        from . import expr
        for n in wf["nodes"]:
            deps = sorted(set(n.get("depends_on", [])) | expr.refs(n.get("params", {})))
            print(f"{n['id']:16s} {n['kind']:20s} <- {', '.join(deps) or '(entry)'}")
        return 0

    rec = run(a.workflow, _kv(a.input), dry_run=not a.execute, run_root=a.run_root)
    print(json.dumps({k: v for k, v in rec.items() if k != "inputs"},
                     indent=2, ensure_ascii=False))
    return 0 if rec["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
