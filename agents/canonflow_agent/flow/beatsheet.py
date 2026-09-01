"""Extract a beat block from the active beat sheet.

Canonical beat ids look like P10G-BEAT-001. Accepted --beat forms:
  1  01  001  B01  beat-1  P10G-BEAT-001

Usage:
  uv run python -m canonflow_agent.flow.beatsheet --list
  uv run python -m canonflow_agent.flow.beatsheet --beat 1 --out /tmp/beat01.txt
  uv run python -m canonflow_agent.flow.beatsheet --beat 1 --print-id
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
DEFAULT_SHEET = (REPO_ROOT / "docs/evidence/p10g-canon-beat-sheet/"
                 "38-canon-beat-sheet-third-revised-draft.md")

HEADING = re.compile(r"^#{1,4}[^\n]*$", re.MULTILINE)
BEAT_ID = re.compile(r"\b([A-Z0-9]+[-_])*BEAT[-_\s]*(\d+)\b", re.IGNORECASE)


class Beat:
    __slots__ = ("id", "number", "title", "start", "end")

    def __init__(self, bid: str, number: int, title: str, start: int):
        self.id, self.number, self.title, self.start = bid, number, title, start
        self.end = -1


def parse(text: str) -> list[Beat]:
    heads = [(m.start(), m.group(0).strip()) for m in HEADING.finditer(text)]
    beats: list[Beat] = []
    for i, (pos, head) in enumerate(heads):
        m = BEAT_ID.search(head)
        if not m:
            continue
        raw = m.group(0).strip()
        title = head.lstrip("#").strip()
        b = Beat(raw.upper(), int(m.group(2)), title, pos)
        b.end = heads[i + 1][0] if i + 1 < len(heads) else len(text)
        beats.append(b)
    return beats


def select(beats: list[Beat], token: str) -> Beat:
    m = BEAT_ID.search(token)
    if m:
        num = int(m.group(2))
    else:
        digits = re.sub(r"\D", "", token)
        if not digits:
            raise SystemExit(f"cannot read a beat number from '{token}'")
        num = int(digits)
    hits = [b for b in beats if b.number == num]
    if not hits:
        raise SystemExit(f"beat number {num} not found; run --list")
    if len(hits) > 1:
        raise SystemExit(f"beat number {num} is ambiguous: "
                         + ", ".join(b.id for b in hits))
    return hits[0]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="canonflow-beatsheet")
    ap.add_argument("--sheet", default=str(DEFAULT_SHEET))
    ap.add_argument("--beat", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--list", action="store_true", dest="do_list")
    ap.add_argument("--print-id", action="store_true", dest="print_id",
                    help="print only the canonical beat id, for shell capture")
    a = ap.parse_args(argv)

    src = pathlib.Path(a.sheet)
    if not src.exists():
        raise SystemExit(f"beat sheet not found: {src}")
    text = src.read_text(encoding="utf-8")
    beats = parse(text)

    if a.do_list or not a.beat:
        print(f"{src}\nbeats: {len(beats)}")
        for b in beats:
            print(f"  {b.id:16s} {len(text[b.start:b.end]):6d} chars  {b.title[:70]}")
        nums = [b.number for b in beats]
        gaps = [n for n in range(1, max(nums) + 1) if n not in nums] if nums else []
        if gaps:
            print(f"missing numbers: {gaps}")
        return 0

    b = select(beats, a.beat)
    block = text[b.start:b.end].strip()

    if a.print_id:
        print(b.id)
        if a.out:
            pathlib.Path(a.out).write_text(block, encoding="utf-8")
        return 0

    print(f"id    : {b.id}\ntitle : {b.title}\nchars : {len(block)}")
    if a.out:
        pathlib.Path(a.out).write_text(block, encoding="utf-8")
        print("written:", a.out)
    else:
        print("---")
        print(block[:600])
    return 0


if __name__ == "__main__":
    sys.exit(main())
