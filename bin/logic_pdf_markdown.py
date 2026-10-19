"""Convert a PDF page to Markdown using the vendored ``anymd`` binary.

anymd is MIT and is invoked as a separate process, the same arrangement already
used for ``potrace.exe`` and ``pdftocairo.exe``. See THIRD-PARTY-NOTICES.md.
"""

import os
import re
import subprocess
import sys

_EXE_PARTS = ('AnyMD', 'anymd.exe')
# Keeps the console window from flashing up in the windowed build.
_NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
# anymd prefixes every page with a citation anchor; the callers scan the markdown
# line by line and expect no such line.
_PAGE_MARKER = re.compile(r'^\s*<!--\s*page\s+\d+\s*-->\s*$', re.IGNORECASE)


def _candidate_bases():
    bases = []
    meipass = getattr(sys, '_MEIPASS', None)
    if meipass:
        bases.append(meipass)
    if getattr(sys, 'frozen', False):
        bases.append(os.path.dirname(sys.executable))
    bases.append(os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)))
    return bases


def find_anymd():
    """Locate the vendored anymd.exe, or return None when it is absent."""
    for base in _candidate_bases():
        for prefix in ((), ('_internal',)):
            candidate = os.path.join(base, *prefix, *_EXE_PARTS)
            if os.path.isfile(candidate):
                return candidate
    return None


def page_to_markdown(pdf_path, pno, timeout=300):
    """Return page ``pno`` (0 based) of ``pdf_path`` as a Markdown string.

    :raises FileNotFoundError: when the vendored anymd build is missing.
    :raises RuntimeError: when anymd fails.
    """
    exe = find_anymd()
    if exe is None:
        raise FileNotFoundError(
            'anymd.exe not found. Run build_scripts/setup_vendor_deps.ps1 '
            'to fetch the vendored anymd build.'
        )

    # List argv with no shell: pdf_path comes from the user. --images none keeps
    # anymd from writing extracted figures to its cache; --no-ocr keeps it from
    # shelling out to tesseract, since the app does its own OCR with PaddleOCR.
    result = subprocess.run(
        [exe, pdf_path, '--pages', str(pno + 1), '--images', 'none', '--no-ocr'],
        capture_output=True,
        timeout=timeout,
        creationflags=_NO_WINDOW,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f'anymd failed on page {pno} of {pdf_path} '
            f'(exit {result.returncode}): {result.stderr.decode("utf-8", "replace").strip()}'
        )

    markdown = result.stdout.decode('utf-8', 'replace')
    return '\n'.join(l for l in markdown.splitlines() if not _PAGE_MARKER.match(l))
