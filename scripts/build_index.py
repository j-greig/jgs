#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""
Build INDEX.json — agent-friendly searchable metadata for the JGS archive.

Walks examples/*.txt, parses # Title / # Date / # Source headers, measures
art body, classifies size + charset, infers category from source URL.

Output: INDEX.json at the skill root (alongside existing INDEX.txt).

Idempotent. Safe to re-run any time.

Usage:
    uv run scripts/build_index.py
    uv run scripts/build_index.py --output custom-index.json
"""
from __future__ import annotations
import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = SKILL_ROOT / "examples"


def parse_headers(text: str) -> tuple[dict, str]:
    """Return ({title, artist, date, source}, body_with_headers_stripped)."""
    meta = {"title": None, "artist": None, "date": None, "source": None}
    body_lines = []
    in_header = True
    for line in text.splitlines():
        if in_header and line.startswith("#"):
            m = re.match(r"#\s*(\w+)\s*:\s*(.+)", line)
            if m:
                key = m.group(1).strip().lower()
                if key in meta:
                    meta[key] = m.group(2).strip()
            continue
        if in_header and not line.strip():
            in_header = False
            continue
        in_header = False
        body_lines.append(line)
    # Drop trailing empty lines from body
    while body_lines and not body_lines[-1].strip():
        body_lines.pop()
    return meta, "\n".join(body_lines)


def measure(body: str) -> tuple[int, int]:
    """Return (max_width, height) in characters."""
    lines = body.splitlines()
    if not lines:
        return 0, 0
    return max(len(l) for l in lines), len(lines)


def classify_size(width: int, height: int) -> str:
    """tiny / small / medium / large / xl by total cell area + height heuristic."""
    if height <= 6 and width <= 30:
        return "tiny"
    if height <= 15:
        return "small"
    if height <= 30:
        return "medium"
    if height <= 50:
        return "large"
    return "xl"


def classify_charset(body: str) -> str:
    """ascii-7bit | extended-ascii | unicode-box | unicode-mixed."""
    has_high = False
    has_box = False
    has_other_unicode = False
    for ch in body:
        o = ord(ch)
        if o < 128:
            continue
        has_high = True
        # Box drawing block: U+2500–U+257F. Block elements: U+2580–U+259F.
        if 0x2500 <= o <= 0x259F:
            has_box = True
        else:
            has_other_unicode = True
    if not has_high:
        return "ascii-7bit"
    if has_box and not has_other_unicode:
        return "unicode-box"
    if has_other_unicode and not has_box:
        return "unicode-other"
    return "unicode-mixed"


# Source HTML page → category mapping (manual + heuristic)
PAGE_CATEGORY = {
    "birds": "birds",
    "animals": "animals",
    "cats": "animals",
    "dogs": "animals",
    "bugs": "animals",
    "fish": "animals",
    "horses": "animals",
    "fantasy": "fantasy",
    "halloween": "holidays",
    "xmas": "holidays",
    "christmas": "holidays",
    "easter": "holidays",
    "valentine": "holidays",
    "stpat": "holidays",
    "thanksgiving": "holidays",
    "food": "food",
    "people": "people",
    "transport": "transport",
    "vehicles": "transport",
    "borders": "borders",
    "logos": "logos",
    "flowers": "nature",
    "trees": "nature",
    "nature": "nature",
    "music": "music",
    "tv": "cartoons",
    "cartoons": "cartoons",
    "computers": "tech",
    "tech": "tech",
}


def infer_category(source: str | None, filename: str) -> str:
    """Best-effort category from source URL or filename."""
    if source:
        m = re.search(r"/([^/]+)\.html?", source)
        if m:
            page = m.group(1).lower()
            for key, cat in PAGE_CATEGORY.items():
                if key in page:
                    return cat
            # Date-based pages like 97april.html → seasonal
            if re.match(r"\d{2}[a-z]+", page):
                return "seasonal"
    # Fallback: keyword in filename
    fname = filename.lower()
    for key, cat in PAGE_CATEGORY.items():
        if key in fname:
            return cat
    return "uncategorised"


def parse_date(date_str: str | None) -> str | None:
    """Convert various date formats to ISO YYYY-MM (best effort)."""
    if not date_str:
        return None
    # "7/97", "12/96", "10/1997"
    m = re.match(r"(\d{1,2})/(\d{2,4})", date_str)
    if m:
        month = int(m.group(1))
        year = int(m.group(2))
        if year < 50:
            year += 2000
        elif year < 100:
            year += 1900
        return f"{year:04d}-{month:02d}"
    # "Aug 97"
    m = re.match(r"([A-Za-z]+)\s+(\d{2,4})", date_str)
    if m:
        try:
            from datetime import datetime
            dt = datetime.strptime(f"{m.group(1)[:3]} {m.group(2)}", "%b %y")
            return dt.strftime("%Y-%m")
        except ValueError:
            pass
    return None


def keywords_from(filename: str, title: str | None) -> list[str]:
    """Filename slug + title words → flat keyword list."""
    base = Path(filename).stem
    # Strip trailing date suffixes like -0797 or -0000-2
    base = re.sub(r"-\d{4}(-\d+)?$", "", base)
    parts = re.split(r"[-_\s]+", base)
    if title:
        parts.extend(re.split(r"[\s/]+", title.lower()))
    return sorted(set(p for p in parts if p and len(p) > 1 and not p.isdigit()))


def build_entry(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    meta, body = parse_headers(text)
    width, height = measure(body)
    preview = "\n".join(body.splitlines()[:3])
    return {
        "filename": path.name,
        "title": meta["title"] or path.stem.replace("-", " ").title(),
        "artist": meta["artist"] or "jgs (Joan G. Stark)",
        "date_raw": meta["date"],
        "date_iso": parse_date(meta["date"]),
        "source": meta["source"],
        "category": infer_category(meta["source"], path.name),
        "tags": keywords_from(path.name, meta["title"]),
        "width": width,
        "height": height,
        "size_class": classify_size(width, height),
        "charset": classify_charset(body),
        "has_jgs_signature": "jgs" in body.lower(),
        "preview": preview,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default=str(SKILL_ROOT / "INDEX.json"))
    ap.add_argument("--examples", default=str(EXAMPLES))
    args = ap.parse_args()

    examples_dir = Path(args.examples)
    if not examples_dir.is_dir():
        print(f"error: {examples_dir} not found", file=sys.stderr)
        return 1

    files = sorted(examples_dir.glob("*.txt"))
    print(f"indexing {len(files)} files from {examples_dir}", file=sys.stderr)

    entries = [build_entry(p) for p in files]

    # Summary stats
    by_category: dict[str, int] = {}
    by_size: dict[str, int] = {}
    by_charset: dict[str, int] = {}
    for e in entries:
        by_category[e["category"]] = by_category.get(e["category"], 0) + 1
        by_size[e["size_class"]] = by_size.get(e["size_class"], 0) + 1
        by_charset[e["charset"]] = by_charset.get(e["charset"], 0) + 1

    out = {
        "version": 1,
        "skill": "joan-stark-ascii-art",
        "fork": "https://github.com/j-greig/jgs",
        "upstream": "https://github.com/oldcompcz/jgs",
        "examples_dir": str(examples_dir),
        "count": len(entries),
        "stats": {
            "by_category": dict(sorted(by_category.items(), key=lambda x: -x[1])),
            "by_size": dict(sorted(by_size.items(), key=lambda x: -x[1])),
            "by_charset": dict(sorted(by_charset.items(), key=lambda x: -x[1])),
        },
        "entries": entries,
    }

    Path(args.output).write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"wrote {args.output}", file=sys.stderr)
    print(f"  {len(entries)} entries", file=sys.stderr)
    print(f"  categories: {by_category}", file=sys.stderr)
    print(f"  sizes:      {by_size}", file=sys.stderr)
    print(f"  charsets:   {by_charset}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
