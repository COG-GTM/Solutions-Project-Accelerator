"""Minimal ``.env`` loader used at application startup.

Deployment-specific values (support links, optional enterprise LLM gateway
settings) are supplied through the environment so nothing site-specific is
committed. Real environment variables always win over ``.env`` entries.

The process working directory is deliberately NOT searched: the app is the
registered ``.aip`` handler, so Explorer starts it inside whatever folder holds
the double-clicked file, and that folder may have been written by someone else.

No third-party dependency: the format is the common ``KEY=value`` subset
(``#`` comments, optional ``export`` prefix, optional surrounding quotes).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

ENV_FILE_VAR = "SPA_ENV_FILE"


def _candidates() -> list[Path]:
    paths: list[Path] = []
    explicit = os.environ.get(ENV_FILE_VAR)
    if explicit:
        paths.append(Path(explicit))
    if getattr(sys, "frozen", False):
        paths.append(Path(sys.executable).parent / ".env")
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            # Values baked into the build by runme.spec.
            paths.append(Path(meipass) / ".env.prod")
    else:
        repo_root = Path(__file__).resolve().parents[1]
        paths.append(repo_root / ".env")
        paths.append(repo_root / "genai_bridge" / ".env")
    paths.append(Path.home() / ".spa" / "spa.env")
    return paths


def _parse(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower().startswith("export "):
            line = line[7:].lstrip()
        key, sep, value = line.partition("=")
        if not sep:
            continue
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key:
            values[key] = value
    return values


def load_env_file(path=None, override=False):
    """Seed ``os.environ`` from the ``.env`` candidates. Earlier files win.

    Returns the first file that supplied a value, or ``None``.
    """
    first_used = None
    for candidate in ([Path(path)] if path is not None else _candidates()):
        try:
            if not candidate.is_file():
                continue
            parsed = _parse(candidate)
        except OSError:
            continue
        for key, value in parsed.items():
            if override or key not in os.environ:
                os.environ[key] = value
                if first_used is None:
                    first_used = candidate
    return first_used


_WEB_SCHEMES = ("http", "https")


def safe_web_url(url):
    """Return ``url`` stripped if it is an absolute http(s) URL, else ``None``.

    ``webbrowser.open`` is ``os.startfile`` on Windows, so anything else (UNC
    paths, ``file:``, local executables, other URI handlers) must be refused.
    """
    if not isinstance(url, str):
        return None
    url = url.strip()
    if not url or "\\" in url or any(ch.isspace() or ord(ch) < 0x20 or ord(ch) == 0x7F for ch in url):
        return None
    try:
        parts = urlsplit(url)
        host = parts.hostname
    except ValueError:
        return None
    if parts.scheme.lower() not in _WEB_SCHEMES or not host:
        return None
    return url
