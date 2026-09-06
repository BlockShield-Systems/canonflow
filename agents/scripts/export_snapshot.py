#!/usr/bin/env python3
"""Freeze var/runs into a deployable, read-only snapshot inside the package.

The container image cannot see var/runs (outside the build context), so the
web service serves this snapshot instead.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from canonflow_agent.ui import build, data  # noqa: E402


def write_json(path: pathlib.Path, obj) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    txt = json.dumps(obj, ensure_ascii=False, separators=(",", ":"),
                     default=str)
    path.write_text(txt, encoding="utf-8")
    return len(txt.encode("utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(build.SNAPSHOT))
    ap.add_argument("--clean", action="store_true",
                    help="remove target directory first")
    args = ap.parse_args()

    out = pathlib.Path(args.out)
    if args.clean and out.exists():
        shutil.rmtree(out)

    idx = data.scan()
    if not idx:
        print("ERROR: data.scan() returned nothing - wrong cwd?", file=sys.stderr)
        return 1

    index, details = build.build(idx)
    total = write_json(out / "index.json", index)

    for beat, det in details.items():
        total += write_json(out / "beats" / ("%s.json" % beat), det)

    media = 0
    for beat, det in details.items():
        src_dir = pathlib.Path(idx[beat]["run_dir"]) / "media"
        if not src_dir.is_dir():
            continue
        dst_dir = out / "media" / beat
        dst_dir.mkdir(parents=True, exist_ok=True)
        for f in sorted(src_dir.iterdir()):
            if f.is_file():
                shutil.copy2(f, dst_dir / f.name)
                media += 1
                total += f.stat().st_size

    print("snapshot: %s" % out)
    print("  beats            %d" % index["beat_count"])
    print("  shots            %d" % index["shot_count"])
    print("  total duration   %d s" % index["total_duration_s"])
    print("  verdicts         %s" % index["verdicts"])
    print("  ctx_state errors %s" % (index["ctx_state_errors"] or "none"))
    print("  media files      %d" % media)
    print("  size             %.1f MiB" % (total / 1048576))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
