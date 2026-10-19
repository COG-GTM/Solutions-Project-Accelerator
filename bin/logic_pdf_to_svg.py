"""Render a PDF page to SVG using Poppler's ``pdftocairo``.

``pdftocairo`` is a GPL-2.0 *program* invoked as a separate process and never
linked, the same arrangement this project already uses for ``potrace.exe``.
See THIRD-PARTY-NOTICES.md for the corresponding-source offer.
"""

import glob
import os
import subprocess
import sys
import tempfile

_EXE_PARTS = ('Poppler', 'poppler-*', 'Library', 'bin', 'pdftocairo.exe')
# Keeps the console window from flashing up in the windowed build.
_NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


def _candidate_bases():
    bases = []
    meipass = getattr(sys, '_MEIPASS', None)
    if meipass:
        bases.append(meipass)
    if getattr(sys, 'frozen', False):
        bases.append(os.path.dirname(sys.executable))
    bases.append(os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)))
    return bases


def find_pdftocairo():
    """Locate the vendored pdftocairo.exe, or return None when it is absent."""
    for base in _candidate_bases():
        for prefix in ((), ('_internal',)):
            matches = sorted(glob.glob(os.path.join(base, *prefix, *_EXE_PARTS)))
            if matches:
                return matches[-1]
    return None


def page_to_svg(pdf_path, pno, timeout=300):
    """Return page ``pno`` (0 based) of ``pdf_path`` as an SVG string.

    :raises FileNotFoundError: when the vendored Poppler build is missing.
    :raises RuntimeError: when pdftocairo fails or emits nothing.
    """
    exe = find_pdftocairo()
    if exe is None:
        raise FileNotFoundError(
            'pdftocairo.exe not found. Run build_scripts/setup_vendor_deps.ps1 '
            'to fetch the vendored Poppler build.'
        )

    with tempfile.TemporaryDirectory(prefix='spa_svg_') as tmp:
        out_path = os.path.join(tmp, 'page.svg')
        # List argv with no shell: pdf_path comes from the user.
        result = subprocess.run(
            [exe, '-svg', '-f', str(pno + 1), '-l', str(pno + 1), pdf_path, out_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=_NO_WINDOW,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f'pdftocairo failed on page {pno} of {pdf_path} '
                f'(exit {result.returncode}): {result.stderr.strip()}'
            )
        if not os.path.isfile(out_path):
            raise RuntimeError(f'pdftocairo produced no SVG for page {pno} of {pdf_path}')
        with open(out_path, encoding='utf-8') as handle:
            return handle.read()
