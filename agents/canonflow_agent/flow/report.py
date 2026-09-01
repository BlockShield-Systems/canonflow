"""Summarise the latest (or a given) workflow run under var/runs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
RUNS_DIR = REPO_ROOT / "var" / "runs"


def latest_run(root: Path) -> Path:
    cands = sorted(root.glob("*/run.json"), key=lambda p: p.stat().st_mtime)
    if not cands:
        raise SystemExit(f"no run.json under {root}")
    return cands[-1]


def as_items(nodes: Any) -> list[tuple[str, dict]]:
    if isinstance(nodes, dict):
        return [(k, v if isinstance(v, dict) else {"value": v}) for k, v in nodes.items()]
    if isinstance(nodes, list):
        out = []
        for i, n in enumerate(nodes):
            if isinstance(n, dict):
                out.append((str(n.get("id", n.get("node", i))), n))
        return out
    return []


def usage_line(u: Any) -> str:
    if not isinstance(u, dict):
        return ""
    keys = ("promptTokenCount", "candidatesTokenCount", "thoughtsTokenCount",
            "totalTokenCount", "prompt", "output", "thinking", "total")
    got = {k: u[k] for k in keys if k in u}
    return " ".join(f"{k}={v}" for k, v in got.items())


def print_nodes(rec: dict, run_dir: Path) -> None:
    print("\nnodes:")
    total = 0
    think = 0
    for nid, n in as_items(rec.get("nodes")):
        status = n.get("status", "?")
        ms = n.get("duration_ms", n.get("ms", ""))
        cost = n.get("cost_usd", 0) or 0
        u = n.get("usage") if isinstance(n.get("usage"), dict) else {}
        tt = u.get("totalTokenCount")
        th = u.get("thoughtsTokenCount")
        if isinstance(tt, int):
            total += tt
        if isinstance(th, int):
            think += th
        line = f"   {status:<8} {nid:<18}"
        if ms != "":
            line += f" {ms}ms"
        if cost:
            line += f" ${cost:.4f}"
        ul = usage_line(u)
        if ul:
            line += f"  {ul}"
        print(line)
        err = n.get("error")
        if err:
            print(f"      error: {str(err)[:400]}")
        ef = run_dir / "nodes" / f"{nid}.error.txt"
        if ef.exists():
            print(f"      error file: {ef}")
    if total:
        print(f"   total tokens: {total}   thinking tokens: {think}")


def print_plan(run_dir: Path) -> None:
    plans = sorted(run_dir.rglob("plan-*.json"))
    if not plans:
        print("\nno plan-*.json in this run")
        return
    plan = json.loads(plans[-1].read_text())
    shots = plan.get("shots") or []
    print(f"\nplan: {plans[-1].name}")
    print(f"   beat_id: {plan.get('beat_id', '?')}")
    print(f"   shots: {len(shots)}")
    cd = plan.get("continuity_delta")
    if cd:
        print(f"   continuity_delta: {str(cd)[:300]}")

    total_s = 0.0
    for s in shots:
        if not isinstance(s, dict):
            continue
        dur = s.get("duration_s")
        try:
            total_s += float(dur)
        except (TypeError, ValueError):
            pass
        cam = s.get("camera") or {}
        light = s.get("light") or {}
        look = s.get("look") or {}
        audio = s.get("audio") or {}
        refs = s.get("reference_assets") or s.get("references") or []
        sid = f"{s.get('scene_no', '?')}.{s.get('shot_no', '?')}"
        print(f"\n   [{sid}] {dur}s hero={bool(s.get('hero'))} refs={len(refs)}")
        if cam:
            print(f"      cam: {cam.get('shot_size', '-')} {cam.get('lens_mm', '-')}mm "
                  f"f/{cam.get('aperture', '-')} move={cam.get('movement', '-')}")
        if light:
            print(f"      light: key={light.get('key', '-')} mood={light.get('mood', '-')}")
        if look:
            print(f"      look: {str(look.get('palette', look))[:120]}")
        dlg = audio.get("dialogue") or s.get("dialogue")
        if dlg:
            print(f"      dialogue: {str(dlg)[:200]}")
        for key in ("image_prompt", "video_prompt"):
            if s.get(key):
                print(f"      {key}: {str(s[key])[:300]}")
    if total_s:
        print(f"\n   beat runtime: {total_s:.0f}s")


def main() -> int:
    ap = argparse.ArgumentParser(description="report a canonflow run")
    ap.add_argument("run_id", nargs="?", help="run id under var/runs (default: latest)")
    ap.add_argument("--runs-root", default=str(RUNS_DIR))
    ap.add_argument("--json", action="store_true", help="dump raw run.json")
    a = ap.parse_args()

    root = Path(a.runs_root)
    rj = root / a.run_id / "run.json" if a.run_id else latest_run(root)
    if not rj.exists():
        raise SystemExit(f"not found: {rj}")
    rec = json.loads(rj.read_text())

    if a.json:
        print(json.dumps(rec, indent=2, ensure_ascii=False))
        return 0

    run_dir = rj.parent
    print(f"run: {rec.get('run_id', run_dir.name)}   ({rj})")
    print(f"   workflow : {rec.get('workflow', '?')}")
    print(f"   status   : {rec.get('status', '?')}")
    print(f"   dry_run  : {rec.get('dry_run', '?')}")
    cost = rec.get("cost_usd", rec.get("estimated_cost_usd"))
    if cost is not None:
        print(f"   cost     : ${float(cost):.4f}")
    if rec.get("error"):
        print(f"   error    : {str(rec['error'])[:400]}")
    print_nodes(rec, run_dir)
    print_plan(run_dir)
    return 0 if rec.get("status") in ("ok", "success", "PASS", None) else 1


if __name__ == "__main__":
    raise SystemExit(main())
