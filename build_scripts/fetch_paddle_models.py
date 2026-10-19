"""Populate ``Paddle-OCR/`` with the inference models the app loads.

No download URL is hardcoded here. They are read from the ``MODEL_URLS``
table of the pip-installed ``paddleocr`` package, so the version pinned in
``requirements.txt`` is the single source of truth for which weights this
app runs against, and the fetch goes through PaddleOCR's own downloader.

Integrity is still enforced locally: every extracted file is checked against
the SHA-256 digests below, computed from the model tree this repo shipped at
commit 1542e59.

Usage (from an environment with ``requirements.txt`` installed):

    python build_scripts/fetch_paddle_models.py [--force]
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TARGET_ROOT = REPO_ROOT / 'Paddle-OCR'

# Local model directory -> key path into paddleocr's MODEL_URLS table.
MODELS: dict[str, tuple[str, ...]] = {
    'cls': ('OCR', 'PP-OCRv3', 'cls', 'ch'),
    'det': ('OCR', 'PP-OCRv3', 'det', 'en'),
    'rec': ('OCR', 'PP-OCRv3', 'rec', 'en'),
    'layout': ('STRUCTURE', 'PP-StructureV2', 'layout', 'en'),
    'table': ('STRUCTURE', 'PP-StructureV2', 'table', 'en'),
}

DIGESTS: dict[str, dict[str, str]] = {
    'cls': {
        'inference.pdmodel': '3c4337ec61722a20b1dca2e5bfaffc313c0592bc89ad6e0d45168224186f6683',
        'inference.pdiparams': 'd1efda1b80e174b4fcb168a035ac96c1af4938892bd86a55f300a6027105d08c',
        'inference.pdiparams.info': 'ee0c2eaa4c09814802bf520c01dfdbc1345dc2879dc9e67424d32c7b0ee88e59',
    },
    'det': {
        # Upstream re-exported this graph on 2026-09-11; the weights
        # (inference.pdiparams) were byte-identical before and after.
        'inference.pdmodel': 'c4bfb1b05d9d1d5a760801eaf6d20180ef7e47bcc675fb17d1f3a89da5fef427',
        'inference.pdiparams': '83676ec730627ab4502f401410a4b6a3ce1c0bb98fa249b71db055b6bddae051',
        'inference.pdiparams.info': '2fe414d9eadf914bf44e3f9ba212988a6f26f364e4f87c6d0af57438ffffc0c4',
    },
    'rec': {
        'inference.pdmodel': 'f0288362f754e815030929477f7b1f96fe2e913e197537288a01bd43f768d0ab',
        'inference.pdiparams': '2cea2de604d8a75fd9151b54ea2dd027659fb8cb777cde377224581110dbff13',
        'inference.pdiparams.info': 'cf79f0b9689b4d6b8094d8bfe2481dc4b4d1699adb622568384695b5f56dc600',
    },
    'layout': {
        'inference.pdmodel': '0517e54867af71996b1ef6df3d07b71957d912c9cddb15c4cbda82d3b918940f',
        'inference.pdiparams': '5865c3f96e25150c65a6e51efc32d932ab4271b14bd14d04f5fd114223b8a307',
        'inference.pdiparams.info': '800268836d6bf0ddf5b55c271e95fb451006ee23132f72427dd376965ad9e34b',
    },
    'table': {
        'inference.pdmodel': '14aa8c554d27322f640d5b966eefc2ce09696f5610ff552643168615f74c6c9d',
        'inference.pdiparams': '41c5587892b65faeafffaf1a0dc08dff154f21454eb254a574073a85c33a9f75',
        'inference.pdiparams.info': 'fbdfa732173af232b0c06092a3a1303710b86b53967fa60ccedbe6317ef174b2',
    },
}


def _import_paddleocr():
    try:
        from paddleocr.paddleocr import MODEL_URLS, maybe_download
    except ImportError as exc:  # pragma: no cover - environment guard
        raise SystemExit(
            'paddleocr is not importable in this interpreter '
            f'({sys.executable}).\nInstall the runtime deps first:\n'
            '    python -m pip install -r requirements.txt --no-build-isolation'
        ) from exc
    return MODEL_URLS, maybe_download


def _resolve_url(model_urls: dict, key_path: tuple[str, ...]) -> str:
    node = model_urls
    for key in key_path:
        node = node[key]
    return node['url']


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _verify(name: str, target: Path) -> None:
    for filename, expected in DIGESTS[name].items():
        path = target / filename
        if not path.is_file():
            raise RuntimeError(f'{path} was not produced by the download.')
        actual = _sha256(path)
        if actual != expected:
            raise RuntimeError(
                f'SHA-256 mismatch for {path}\n'
                f'  expected {expected}\n  actual   {actual}\n'
                'Refusing to keep an artifact that does not match the pinned checksum.'
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--force', action='store_true',
                        help='re-download even if the model is already present')
    args = parser.parse_args()

    model_urls, maybe_download = _import_paddleocr()

    for name, key_path in MODELS.items():
        target = TARGET_ROOT / name
        if args.force:
            shutil.rmtree(target, ignore_errors=True)
        elif (target / 'inference.pdiparams').is_file() and (target / 'inference.pdmodel').is_file():
            _verify(name, target)
            print(f'[skip]    Paddle-OCR/{name} already present')
            continue

        print(f'[install] Paddle-OCR/{name}')
        url = _resolve_url(model_urls, key_path)
        # maybe_download downloads, extracts and normalises names to inference.*
        maybe_download(str(target), url)
        try:
            _verify(name, target)
        except RuntimeError:
            shutil.rmtree(target, ignore_errors=True)
            raise
        print('    checksum ok')

    return 0


if __name__ == '__main__':
    sys.exit(main())
