"""
Global JSON store for per-library-symbol anchor overrides.

PlantPAx ACM libraries ship without ``_Anchor_*`` marker ellipses, so
``logic_gfx_to_svg.gfx_to_svg`` returns empty anchor lists for their
symbols. This module lets the HMI Builder persist user-defined anchor
overrides in a global JSON file so they survive across projects and are
layered on top of the parser output at load time.

Schema (v1)::

    {
        "version": 1,
        "overrides": {
            "<library_id>::<symbol_name>": {
                "top":    [[x, y], ...],
                "bottom": [[x, y], ...],
                "left":   [[x, y], ...],
                "right":  [[x, y], ...]
            },
            ...
        }
    }

Coordinates are stored in the SVG viewBox coordinate space returned by
``gfx_to_svg`` (i.e. already anchor-normalised so ``(0, 0)`` maps to the
top-left of the SVG's viewBox after ``left/top`` translation).
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from threading import RLock
from typing import Dict, List, Optional, Tuple

_STORE_VERSION = 1
_DIRECTIONS = ("top", "bottom", "left", "right")

_this_dir = os.path.dirname(os.path.realpath(__file__))
DEFAULT_STORE_PATH = os.path.join(_this_dir, "data", "library_symbol_anchor_overrides.json")

AnchorList = List[Tuple[float, float]]
AnchorDict = Dict[str, AnchorList]


def _make_key(library_id: str, symbol_name: str) -> str:
    return f"{library_id}::{symbol_name}"


def _normalise_points(points) -> AnchorList:
    """Coerce a list of iterables/dicts to a list of ``(x, y)`` tuples."""
    result: AnchorList = []
    if not points:
        return result
    for pt in points:
        try:
            if isinstance(pt, dict):
                x, y = pt.get("x"), pt.get("y")
            else:
                x, y = pt[0], pt[1]
            result.append((float(x), float(y)))
        except (TypeError, ValueError, IndexError, KeyError):
            continue
    return result


class LibraryAnchorOverridesStore:
    """Load/save global library-symbol anchor overrides.

    Instances are cheap; a module-level singleton is provided via
    :func:`get_default_store` for callers that want the shared instance.
    """

    def __init__(self, path: str = DEFAULT_STORE_PATH):
        self._path = path
        self._lock = RLock()
        self._overrides: Dict[str, AnchorDict] = {}
        self.load()

    @property
    def path(self) -> str:
        return self._path

    def load(self) -> None:
        """Load overrides from disk. Missing/corrupt files reset to empty."""
        with self._lock:
            self._overrides = {}
            if not os.path.isfile(self._path):
                return
            try:
                with open(self._path, "r", encoding="utf-8") as fh:
                    payload = json.load(fh)
            except (OSError, json.JSONDecodeError) as exc:
                logging.warning(
                    "LibraryAnchorOverridesStore: could not load '%s': %s. "
                    "Continuing with empty override set.",
                    self._path, exc,
                )
                return

            raw = payload.get("overrides") if isinstance(payload, dict) else None
            if not isinstance(raw, dict):
                return

            for key, value in raw.items():
                if not isinstance(key, str) or not isinstance(value, dict):
                    continue
                cleaned: AnchorDict = {d: _normalise_points(value.get(d)) for d in _DIRECTIONS}
                self._overrides[key] = cleaned

    def save(self) -> bool:
        """Atomically persist overrides to disk. Returns ``True`` on success."""
        with self._lock:
            payload = {
                "version": _STORE_VERSION,
                "overrides": {
                    key: {d: [list(pt) for pt in anchors.get(d, [])] for d in _DIRECTIONS}
                    for key, anchors in self._overrides.items()
                },
            }
            try:
                os.makedirs(os.path.dirname(self._path), exist_ok=True)
                fd, tmp_path = tempfile.mkstemp(
                    prefix=".library_anchors_", suffix=".json",
                    dir=os.path.dirname(self._path),
                )
                try:
                    with os.fdopen(fd, "w", encoding="utf-8") as fh:
                        json.dump(payload, fh, indent=2)
                    os.replace(tmp_path, self._path)
                except Exception:
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass
                    raise
            except OSError as exc:
                logging.warning(
                    "LibraryAnchorOverridesStore: failed to save '%s': %s",
                    self._path, exc,
                )
                return False
            return True

    def get(self, library_id: str, symbol_name: str) -> Optional[AnchorDict]:
        """Return the override for the given key, or ``None`` if absent."""
        if not library_id or not symbol_name:
            return None
        with self._lock:
            anchors = self._overrides.get(_make_key(library_id, symbol_name))
            if anchors is None:
                return None
            # Return a defensive copy so callers can't mutate the store.
            return {d: list(anchors.get(d, [])) for d in _DIRECTIONS}

    def set(self, library_id: str, symbol_name: str, anchors: AnchorDict) -> None:
        """Replace the override for the given key. Does not auto-save."""
        if not library_id or not symbol_name:
            return
        cleaned: AnchorDict = {d: _normalise_points(anchors.get(d)) for d in _DIRECTIONS}
        with self._lock:
            self._overrides[_make_key(library_id, symbol_name)] = cleaned

    def clear(self, library_id: str, symbol_name: str) -> None:
        """Remove any override for the given key. Does not auto-save."""
        if not library_id or not symbol_name:
            return
        with self._lock:
            self._overrides.pop(_make_key(library_id, symbol_name), None)

    def has(self, library_id: str, symbol_name: str) -> bool:
        if not library_id or not symbol_name:
            return False
        with self._lock:
            return _make_key(library_id, symbol_name) in self._overrides


_default_store: Optional[LibraryAnchorOverridesStore] = None
_default_store_lock = RLock()


def get_default_store() -> LibraryAnchorOverridesStore:
    """Return the process-wide default store instance."""
    global _default_store
    with _default_store_lock:
        if _default_store is None:
            _default_store = LibraryAnchorOverridesStore()
        return _default_store


def reload_default_store() -> LibraryAnchorOverridesStore:
    """Force a reload of the default store from disk."""
    store = get_default_store()
    store.load()
    return store
