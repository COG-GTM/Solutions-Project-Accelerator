"""Every SVG rasterisation must go through bin.logic_svg_render (offline url_fetcher)."""

import re
from pathlib import Path


def test_cairosvg_is_only_called_through_logic_svg_render():
    bin_dir = Path(__file__).resolve().parents[2] / "bin"
    offenders = [
        f"{path.name}:{lineno}"
        for path in sorted(bin_dir.glob("*.py"))
        if path.name != "logic_svg_render.py"
        for lineno, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1)
        if re.search(r"^\s*(import cairosvg|from cairosvg\b)|cairosvg\.\w+\(", line)
    ]
    assert offenders == [], f"render SVGs via bin.logic_svg_render instead: {offenders}"
