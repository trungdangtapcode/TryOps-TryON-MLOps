#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path

CHECKBOX_RE = re.compile(r"^- \[(?P<mark>[ xX~])\] (?P<item>[A-Z]\d{3}) (?P<title>.*)$")


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize TryOps roadmap checkbox status.")
    parser.add_argument("roadmap", type=Path)
    args = parser.parse_args()

    completed: list[str] = []
    partial: list[str] = []
    remaining: list[str] = []
    for line in args.roadmap.read_text(encoding="utf-8").splitlines():
        match = CHECKBOX_RE.match(line)
        if not match:
            continue
        item = f"{match.group('item')} {match.group('title')}"
        if match.group("mark").lower() == "x":
            completed.append(item)
        elif match.group("mark") == "~":
            partial.append(item)
        else:
            remaining.append(item)

    total = len(completed) + len(partial) + len(remaining)
    percent = (len(completed) / total * 100.0) if total else 0.0
    print(f"roadmap_total={total}")
    print(f"roadmap_completed={len(completed)}")
    print(f"roadmap_partial={len(partial)}")
    print(f"roadmap_not_started={len(remaining)}")
    print(f"roadmap_remaining={len(partial) + len(remaining)}")
    print(f"roadmap_completion_percent={percent:.1f}")
    print()
    print("next_partial_items:")
    for item in partial[:10]:
        print(f"- {item}")
    print()
    print("next_remaining_items:")
    for item in remaining[:10]:
        print(f"- {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
