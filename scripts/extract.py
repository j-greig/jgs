#!/usr/bin/env python3
"""
Joan Stark ASCII Art Extractor

Extracts ASCII art from the JGS GitHub repository:
https://github.com/oldcompcz/jgs/tree/master/joan_stark

Usage:
    uv run python extract.py

Or with custom output:
    uv run python extract.py --output /path/to/examples
"""

import re
import html
import json
import time
import argparse
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError


GITHUB_API_URL = "https://api.github.com/repos/oldcompcz/jgs/contents/joan_stark"
GITHUB_RAW_BASE = "https://raw.githubusercontent.com/oldcompcz/jgs/master/joan_stark"
GITHUB_BLOB_BASE = "https://github.com/oldcompcz/jgs/blob/master/joan_stark"

# User agent to avoid GitHub rate limiting
HEADERS = {"User-Agent": "joan-stark-ascii-extractor/1.0"}


def fetch_url(url: str, encoding: str = "latin-1") -> str:
    """Fetch URL content with proper headers."""
    request = Request(url, headers=HEADERS)
    try:
        with urlopen(request, timeout=30) as response:
            return response.read().decode(encoding)
    except (HTTPError, URLError) as e:
        print(f"  Error fetching {url}: {e}")
        return ""


def fetch_json(url: str) -> list | dict:
    """Fetch JSON from URL."""
    content = fetch_url(url, encoding="utf-8")
    if content:
        return json.loads(content)
    return []


def clean_html_art(block: str) -> str:
    """
    Convert HTML-encoded ASCII art to plain text.

    Handles:
    - &nbsp; -> space
    - <FONT ...>...</FONT> -> just content (strip color tags)
    - <B>, <TT>, <A NAME...> -> strip
    - HTML entities (&gt; &lt; &amp;)
    - Preserve exact whitespace/newlines
    """
    text = block

    # Strip HTML tags but preserve content
    text = re.sub(r'<FONT[^>]*>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'</FONT>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'</?B>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'</?I>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'</?TT>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'</?STRONG>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'<A[^>]*>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'</A>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'<BR\s*/?>', '\n', text, flags=re.IGNORECASE)

    # Convert HTML entities
    text = text.replace('&nbsp;', ' ')
    text = html.unescape(text)

    # Normalise line endings
    text = text.replace('\r\n', '\n').replace('\r', '\n')

    # Remove leading/trailing blank lines but preserve internal structure
    lines = text.split('\n')
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()

    return '\n'.join(lines)


def extract_title_and_date(block: str) -> tuple[str | None, str]:
    """
    Extract title and date from ASCII art block.

    Looks for patterns like:
    - -=[ cardinal ]=- 7/97
    - ~~ penguin ~~ 12/96
    - ** owl ** 9/97

    Returns: (title, date) or (None, "unknown")
    """
    # Pattern 1: -=[ title ]=- MM/YY
    match = re.search(r'-=\[\s*([^\]]+?)\s*\]=-\s*(\d{1,2}/\d{2})?', block)
    if match:
        return match.group(1).strip(), match.group(2) or "unknown"

    # Pattern 2: ~ title ~ or ~~ title ~~ with optional date
    match = re.search(r'~+\s*([^~]+?)\s*~+\s*(\d{1,2}/\d{2})?', block)
    if match and len(match.group(1)) < 50:  # Avoid matching decorative lines
        return match.group(1).strip(), match.group(2) or "unknown"

    # Pattern 3: ** title ** with optional date
    match = re.search(r'\*\*+\s*([^*]+?)\s*\*\*+\s*(\d{1,2}/\d{2})?', block)
    if match and len(match.group(1)) < 50:
        return match.group(1).strip(), match.group(2) or "unknown"

    return None, "unknown"


def remove_title_line(art: str, title: str) -> str:
    """Remove the title line from the art content."""
    if not title:
        return art

    lines = art.split('\n')
    cleaned_lines = []
    title_removed = False

    for line in lines:
        # Check if this line contains the title pattern
        if not title_removed:
            if f'-=[ {title}' in line.lower() or f'-=[{title}' in line.lower():
                title_removed = True
                continue
            if f'~~ {title}' in line.lower() or f'~~{title}' in line.lower():
                title_removed = True
                continue
            if f'** {title}' in line.lower() or f'**{title}' in line.lower():
                title_removed = True
                continue
        cleaned_lines.append(line)

    return '\n'.join(cleaned_lines)


def is_valid_art(art: str) -> bool:
    """Check if extracted content is valid ASCII art."""
    if not art or len(art.strip()) < 20:
        return False

    # Skip if it's just decorative separators
    if re.match(r'^[\s.:*~\-=<>]+$', art.replace('\n', '')):
        return False

    # Skip if it's mostly HTML or links
    if art.count('<') > 5 or 'href=' in art.lower():
        return False

    # Must have some visual content (non-whitespace, non-alphanumeric)
    visual_chars = re.findall(r'[^\s\w]', art)
    if len(visual_chars) < 5:
        return False

    return True


def extract_from_html(html_content: str, source_file: str) -> list[dict]:
    """
    Extract ASCII art pieces from HTML content.

    Returns list of dicts with: title, date, art, source
    """
    pieces = []

    # Find all <PRE>...</PRE> blocks
    pre_blocks = re.findall(r'<PRE[^>]*>(.*?)</PRE>', html_content, re.DOTALL | re.IGNORECASE)

    for block in pre_blocks:
        # Extract title and date
        title, date = extract_title_and_date(block)

        if not title:
            # Try to extract title from preceding content
            continue

        # Clean the art
        art = clean_html_art(block)

        # Remove the title line from the art itself
        art = remove_title_line(art, title)

        # Strip leading/trailing whitespace lines again after title removal
        lines = art.split('\n')
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        art = '\n'.join(lines)

        if is_valid_art(art):
            pieces.append({
                'title': title,
                'date': date,
                'art': art,
                'source': f"{GITHUB_BLOB_BASE}/{source_file}"
            })

    return pieces


def generate_filename(title: str, date: str, seen: dict) -> str:
    """
    Generate unique, slug-style filename.

    Examples:
    - "cardinal" + "7/97" -> "cardinal-0797.txt"
    - "birds on a wire" + "1/97" -> "birds-on-a-wire-0197.txt"
    - "bird" (duplicate) -> "bird-0297-2.txt"
    """
    # Slugify title
    slug = re.sub(r'[^a-z0-9]+', '-', title.lower())
    slug = re.sub(r'-+', '-', slug).strip('-')
    slug = slug[:40]  # Truncate long names

    if not slug:
        slug = "untitled"

    # Format date: MM/YY -> MMYY (zero-padded)
    if date and date != "unknown":
        parts = date.split('/')
        if len(parts) == 2:
            month = parts[0].zfill(2)
            year = parts[1]
            date_slug = f"{month}{year}"
        else:
            date_slug = "0000"
    else:
        date_slug = "0000"

    base = f"{slug}-{date_slug}"

    # Handle duplicates
    if base in seen:
        seen[base] += 1
        return f"{base}-{seen[base]}.txt"
    else:
        seen[base] = 1
        return f"{base}.txt"


def save_art_file(piece: dict, filename: str, output_dir: Path) -> None:
    """Save ASCII art to file with metadata header."""
    filepath = output_dir / filename

    # Format title nicely
    title_formatted = piece['title'].title()

    header = f"""# Title: {title_formatted}
# Artist: jgs (Joan G. Stark)
# Date: {piece['date']}
# Source: {piece['source']}

"""

    filepath.write_text(header + piece['art'], encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description="Extract Joan Stark ASCII art from JGS repo")
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=Path.home() / ".claude/skills/joan-stark-ascii-art/examples",
        help="Output directory for extracted art files"
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=0,
        help="Limit number of HTML files to process (0 = all)"
    )
    args = parser.parse_args()

    output_dir = args.output
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Output directory: {output_dir}")
    print(f"Fetching file list from GitHub API...")

    # Fetch file list
    files = fetch_json(GITHUB_API_URL)
    if not files:
        print("Failed to fetch file list!")
        return

    # Filter to HTML files only
    html_files = [f for f in files if f.get('name', '').endswith('.html')]
    print(f"Found {len(html_files)} HTML files")

    if args.limit > 0:
        html_files = html_files[:args.limit]
        print(f"Limited to {args.limit} files")

    seen_filenames = {}
    total_extracted = 0
    failed_files = []

    for i, file_info in enumerate(html_files):
        filename = file_info['name']
        print(f"[{i+1}/{len(html_files)}] Processing {filename}...", end=" ")

        # Fetch HTML content
        raw_url = f"{GITHUB_RAW_BASE}/{filename}"
        html_content = fetch_url(raw_url)

        if not html_content:
            failed_files.append(filename)
            print("FAILED")
            continue

        # Extract art pieces
        pieces = extract_from_html(html_content, filename)

        for piece in pieces:
            out_filename = generate_filename(piece['title'], piece['date'], seen_filenames)
            save_art_file(piece, out_filename, output_dir)
            total_extracted += 1

        print(f"{len(pieces)} pieces")

        # Rate limit: small delay between requests
        time.sleep(0.1)

    print(f"\n{'='*50}")
    print(f"Extraction complete!")
    print(f"Total pieces extracted: {total_extracted}")
    print(f"Output directory: {output_dir}")

    if failed_files:
        print(f"Failed files: {', '.join(failed_files)}")


if __name__ == "__main__":
    main()
