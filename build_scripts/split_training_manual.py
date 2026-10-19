"""One-off: split the converted training manual into per-chapter pages.

The pypandoc conversion produced a single ``training-manual.md`` that
contains (a) the docx preamble (logo + revision-history table),
(b) a stale docx-generated Contents section, and (c) the actual chapters
starting at ``# Introduction``.

This script:
1. Drops everything before the first ``# Introduction`` heading.
2. Splits the remainder on H1 boundaries into one file per chapter under
   ``docs_src/training-manual/``.
3. Rewrites image references so relative links still work from the new
   subfolder (``training-manual-media/`` -> ``../training-manual-media/``).
4. Prints a ready-to-paste ``mkdocs.yml`` nav snippet.

Rerun-safe: the output folder is wiped before writing.
"""
from __future__ import annotations

import re
import shutil
import unicodedata
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_MD = REPO_ROOT / "docs_src" / "training-manual.md"
OUT_DIR = REPO_ROOT / "docs_src" / "training-manual"

# --- helpers ---------------------------------------------------------------

_SLUG_STRIP_RE = re.compile(r"[^a-z0-9]+")


def slugify(title: str) -> str:
    """Return a filesystem-safe slug for a chapter title."""
    text = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = _SLUG_STRIP_RE.sub("-", text).strip("-")
    return text or "chapter"


def clean_title(raw: str) -> str:
    """Strip leading chapter numbering (e.g. ``1. `` or ``3.1.1---``)."""
    return re.sub(r"^\s*\d+(\.\d+)*[.\-\s]+", "", raw).strip()


# --- main ------------------------------------------------------------------


def main() -> int:
    if not SRC_MD.exists():
        print(f"[split] ERROR: {SRC_MD} not found.")
        return 1

    text = SRC_MD.read_text(encoding="utf-8")

    # 1) Drop preamble: keep everything from the first "# Introduction" onward.
    m = re.search(r"(?m)^# Introduction\b", text)
    if not m:
        print("[split] ERROR: '# Introduction' heading not found in source.")
        return 2
    text = text[m.start():]

    # 2) Rewrite image paths to work from the new subfolder.
    text = text.replace("training-manual-media/", "../training-manual-media/")

    # 3) Split on H1 boundaries.
    # Match at line starts only, and capture the heading title.
    parts = re.split(r"(?m)^# (.+)$", text)
    # After split: [pre-first-header, title1, body1, title2, body2, ...]
    # pre-first-header is empty because text starts with a heading.
    if len(parts) < 3:
        print("[split] ERROR: no H1 chapters detected.")
        return 3

    chapters: list[tuple[str, str]] = []  # (title, body-with-heading)
    for i in range(1, len(parts), 2):
        title = parts[i].strip()
        body = parts[i + 1]
        chapters.append((title, f"# {title}\n{body}".rstrip() + "\n"))

    # 4) Wipe output dir and write files with numeric prefixes for stable order.
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)

    nav_lines: list[str] = []
    for idx, (title, body) in enumerate(chapters, start=1):
        slug = slugify(clean_title(title))
        filename = f"{idx:02d}-{slug}.md"
        (OUT_DIR / filename).write_text(body, encoding="utf-8")
        display = clean_title(title)
        nav_lines.append(f"      - {display}: training-manual/{filename}")
        print(f"  wrote {filename}  <-  {title!r}")

    print()
    print("=" * 72)
    print("Paste the following under the 'Training manual (2025)' entry in mkdocs.yml:")
    print("=" * 72)
    print("      - Training manual (2025):")
    for line in nav_lines:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
