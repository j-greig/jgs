#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""
find.py — agent-friendly search over the JGS archive.

Loads INDEX.json and filters/scores entries.

Examples:
    uv run scripts/find.py elephant
    uv run scripts/find.py "small bird"
    uv run scripts/find.py --category animals --size tiny
    uv run scripts/find.py --max-width 30 --max-height 8
    uv run scripts/find.py halloween --month 10
    uv run scripts/find.py --random --category birds
    uv run scripts/find.py elephant --format json --top 5
    uv run scripts/find.py elephant --format paths      # just file paths
    uv run scripts/find.py elephant --format preview    # default: previews

Output formats:
    preview  list with title + path + small ASCII preview (default)
    paths    one absolute path per line
    json     full JSON entries, ready to pipe
    names    just filenames
"""
from __future__ import annotations
import argparse
import json
import random
import re
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INDEX = SKILL_ROOT / "INDEX.json"
EXAMPLES = SKILL_ROOT / "examples"


def score(entry: dict, terms: list[str]) -> int:
    """Simple keyword score: matches in title, tags, category, filename."""
    if not terms:
        return 1
    haystacks = {
        "title": (entry.get("title") or "").lower(),
        "tags": " ".join(entry.get("tags") or []),
        "category": entry.get("category") or "",
        "filename": entry.get("filename") or "",
    }
    s = 0
    for term in terms:
        t = term.lower()
        if t in haystacks["title"]:
            s += 5
        if t in haystacks["tags"]:
            s += 3
        if t in haystacks["category"]:
            s += 2
        if t in haystacks["filename"]:
            s += 1
    return s


def filter_entry(entry: dict, args) -> bool:
    if args.category and entry.get("category") != args.category:
        return False
    if args.size and entry.get("size_class") != args.size:
        return False
    if args.charset and entry.get("charset") != args.charset:
        return False
    if args.max_width is not None and (entry.get("width") or 0) > args.max_width:
        return False
    if args.max_height is not None and (entry.get("height") or 0) > args.max_height:
        return False
    if args.min_width is not None and (entry.get("width") or 0) < args.min_width:
        return False
    if args.min_height is not None and (entry.get("height") or 0) < args.min_height:
        return False
    iso = entry.get("date_iso") or ""
    if args.year and not iso.startswith(f"{args.year:04d}"):
        return False
    if args.month and not iso.endswith(f"-{args.month:02d}"):
        return False
    if args.has_signature is not None:
        if bool(entry.get("has_jgs_signature")) != args.has_signature:
            return False
    return True


def render_preview(entry: dict, examples_dir: Path) -> str:
    p = examples_dir / entry["filename"]
    if not p.exists():
        return entry.get("preview", "(no preview)")
    text = p.read_text(encoding="utf-8", errors="replace")
    # Strip header lines
    lines = []
    in_header = True
    for line in text.splitlines():
        if in_header and (line.startswith("#") or not line.strip()):
            continue
        in_header = False
        lines.append(line)
    return "\n".join(lines).rstrip()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("terms", nargs="*", help="search keywords")
    ap.add_argument("--index", default=str(DEFAULT_INDEX))
    ap.add_argument("--examples", default=str(EXAMPLES))
    ap.add_argument("--category", help="filter by category (animals, birds, holidays, ...)")
    ap.add_argument("--size", choices=["tiny", "small", "medium", "large", "xl"])
    ap.add_argument("--charset", choices=["ascii-7bit", "extended-ascii", "unicode-box", "unicode-other", "unicode-mixed"])
    ap.add_argument("--max-width", type=int)
    ap.add_argument("--max-height", type=int)
    ap.add_argument("--min-width", type=int)
    ap.add_argument("--min-height", type=int)
    ap.add_argument("--year", type=int)
    ap.add_argument("--month", type=int)
    ap.add_argument("--has-signature", type=lambda v: v.lower() in ("1", "true", "yes"))
    ap.add_argument("--random", action="store_true", help="pick a random match")
    ap.add_argument("--top", type=int, default=10, help="show top N (default 10)")
    ap.add_argument("--format", choices=["preview", "paths", "json", "names"], default="preview")
    ap.add_argument("--stats", action="store_true", help="just print index stats and exit")
    args = ap.parse_args()

    index_path = Path(args.index)
    if not index_path.exists():
        print(f"error: {index_path} not found. run build_index.py first.", file=sys.stderr)
        return 1
    data = json.loads(index_path.read_text())
    # Honour examples_dir from the index unless user overrode --examples
    if "examples_dir" in data and args.examples == str(EXAMPLES):
        args.examples = data["examples_dir"]

    if args.stats:
        print(json.dumps(data["stats"], indent=2))
        return 0

    entries = data["entries"]
    matches = [e for e in entries if filter_entry(e, args)]

    if args.terms:
        scored = [(score(e, args.terms), e) for e in matches]
        scored = [(s, e) for s, e in scored if s > 0]
        scored.sort(key=lambda x: (-x[0], x[1].get("date_iso") or ""))
        matches = [e for _, e in scored]

    if args.random and matches:
        matches = [random.choice(matches)]
    else:
        matches = matches[: args.top]

    if not matches:
        print("(no matches)", file=sys.stderr)
        return 2

    examples_dir = Path(args.examples)

    if args.format == "json":
        print(json.dumps(matches, indent=2, ensure_ascii=False))
    elif args.format == "paths":
        for e in matches:
            print(examples_dir / e["filename"])
    elif args.format == "names":
        for e in matches:
            print(e["filename"])
    else:  # preview
        for i, e in enumerate(matches):
            print(f"─── {i+1}/{len(matches)} ─── {e['title']}  [{e['size_class']} {e['width']}×{e['height']}]")
            print(f"    file: {e['filename']}")
            print(f"    cat:  {e['category']}    date: {e.get('date_iso') or '?'}    charset: {e['charset']}")
            print()
            art = render_preview(e, examples_dir)
            # Indent two spaces for readability
            for line in art.splitlines():
                print(f"  {line}")
            print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
