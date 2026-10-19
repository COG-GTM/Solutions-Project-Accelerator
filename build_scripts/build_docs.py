"""Build the MkDocs Material site for bundling with the installer.

Usage (from the repository root):

    python build_scripts/build_docs.py            # one-shot build
    python build_scripts/build_docs.py --serve    # live preview on http://127.0.0.1:8000
    python build_scripts/build_docs.py --clean    # delete previous build output
    python build_scripts/build_docs.py --check    # build with --strict for CI

The site is written to ``build/docs_site/`` (see ``mkdocs.yml``).  PyInstaller
picks it up via a conditional entry in ``runme.spec`` and the Help ->
Documentation menu opens ``index.html`` from there when the app is frozen.

Dependencies are pinned in ``docs_requirements.txt``.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
MKDOCS_YAML = REPO_ROOT / "mkdocs.yml"
SITE_DIR = REPO_ROOT / "build" / "docs_site"


def _fail(msg: str) -> int:
    print(f"[build_docs] ERROR: {msg}", file=sys.stderr)
    return 1


def _run_mkdocs(args: list[str]) -> int:
    cmd = [sys.executable, "-m", "mkdocs", *args]
    print(f"[build_docs] $ {' '.join(cmd)}")
    return subprocess.call(cmd, cwd=str(REPO_ROOT))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the SPA docs site.")
    parser.add_argument("--serve", action="store_true", help="Run 'mkdocs serve' instead of building.")
    parser.add_argument("--clean", action="store_true", help="Delete previous build output before building.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Build with --strict so broken links / missing pages fail the build (CI-friendly).",
    )
    args = parser.parse_args(argv)

    if not MKDOCS_YAML.exists():
        return _fail(f"mkdocs.yml not found at {MKDOCS_YAML}")

    if args.clean and SITE_DIR.exists():
        print(f"[build_docs] Cleaning {SITE_DIR}")
        shutil.rmtree(SITE_DIR)

    if args.serve:
        return _run_mkdocs(["serve"])

    build_args = ["build", "--clean" if args.clean else "--dirty"]
    if args.check:
        build_args.append("--strict")
    rc = _run_mkdocs(build_args)
    if rc == 0:
        print(f"[build_docs] Site written to {SITE_DIR}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
