# Joan Stark's ASCII Art Gallery

Website of legendary ASCII-art artist [Joan Stark](https://en.wikipedia.org/wiki/Joan_Stark) (jgs), active 1996–2001.

Original site: http://www.geocities.com/SoHo/7373
[Web Archive](https://web.archive.org/web/20091028013825/http://www.geocities.com/SoHo/7373/) · [GitHub Pages](https://oldcompcz.github.io/jgs/joan_stark/) · [Upstream repo (oldcompcz/jgs)](https://github.com/oldcompcz/jgs)

![Title picture](joan_stark/entry5.jpg)

This is **j-greig's fork** with extracted plain-text files and agent-friendly search tooling layered on top of the original archive. The original HTML pages remain untouched in `joan_stark/`.

---

## Layout

```
joan_stark/        original HTML pages, GIFs, MIDIs (untouched)
extracted/         2700 individual .txt files (one ASCII piece per file)
scripts/           agent tooling: build_index, find, extract
INDEX.json         generated metadata index over extracted/
```

---

## Quickstart for agents

### 1. Build (or refresh) the index

```bash
uv run scripts/build_index.py --examples extracted --output INDEX.json
```

Walks `extracted/`, parses headers, measures dimensions, classifies size + charset, infers category. Idempotent. Run any time after you add or modify pieces.

### 2. Search

```bash
uv run scripts/find.py elephant                          # keyword
uv run scripts/find.py "small bird"                      # multi-keyword (OR-scored)
uv run scripts/find.py --category birds --size tiny      # filter by category + size
uv run scripts/find.py --max-width 30 --max-height 6     # size cap
uv run scripts/find.py --year 1997 --month 10            # halloween-era pieces
uv run scripts/find.py --random --category animals       # random pick
uv run scripts/find.py --stats                           # show index statistics
```

**Output formats:**
| flag | what |
|------|------|
| `--format preview` (default) | title + path + ASCII preview |
| `--format paths` | one absolute path per line (pipe to other tools) |
| `--format names` | just filenames |
| `--format json` | full JSON entries (machine-readable) |

**Filters:** `--category`, `--size` (tiny/small/medium/large/xl), `--charset` (ascii-7bit/unicode-box/etc), `--max-width`, `--max-height`, `--min-width`, `--min-height`, `--year`, `--month`, `--has-signature`, `--random`, `--top N`.

### 3. Use a piece

`extracted/<filename>.txt` contains a 4-line header (Title / Artist / Date / Source) followed by the art. Strip the headers when stamping into compositions.

---

## INDEX.json schema

Each entry:
```json
{
  "filename": "elephant-0000-2.txt",
  "title": "Elephant",
  "artist": "jgs (Joan G. Stark)",
  "date_raw": "11/98",
  "date_iso": "1998-11",
  "source": "https://github.com/oldcompcz/jgs/blob/master/joan_stark/98nov.html",
  "category": "seasonal",
  "tags": ["elephant"],
  "width": 31,
  "height": 20,
  "size_class": "medium",
  "charset": "ascii-7bit",
  "has_jgs_signature": true,
  "preview": "              ____\n           .'`    `';--.___.-.\n..."
}
```

---

## Agent-friendly extensions worth adding

PRs welcome. Ideas:

- **categories.json** — manually-curated category map for the ~780 currently `uncategorised` pieces
- **gallery.py** — render a contact-sheet PNG of all matches (pipe `find.py --format paths` into it)
- **semantic.py** — embedding-based similarity search (only if keyword search is missing too much)
- **preview.py** — single-piece pretty-print with attribution header
- **categories/ symlink tree** — `categories/animals/elephant-0000.txt` → `extracted/...` for raw glob-friendliness
- **llms.txt** — agent intro at repo root following the [llms.txt convention](https://llmstxt.org)

The principle: keep `extracted/` and `joan_stark/` immutable as canonical archives. All search tooling and metadata layers live separately and are regenerable.

---

## Attribution

All ASCII art is by **Joan G. Stark (jgs)**, 1996–2001. Her "jgs" signature is preserved in pieces where it appears. Always credit when using:

```
ASCII art by jgs (Joan G. Stark)
Source: https://github.com/oldcompcz/jgs
```

---

## Re-extraction

If you need to regenerate `extracted/` from the original HTML:

```bash
uv run scripts/extract.py
```
