"""JSON-line event emitter.

The sidecar communicates with the main app via a stream of JSON
objects, one per line, on stdout. Every message is a compact JSON
object with an ``event`` field. Line types:

- ``{"event":"progress","textbox":<str|null>,"label":<str|null>,"percent":<int|null>}``
  Maps 1:1 to the existing ``progress_callback(textbox_entry,
  label_text, percentage)`` signature used by
  ``bin/gui_textbox_progressbar_window.texbox_progressbar_window``.
- ``{"event":"log","level":"info"|"warning"|"error","message":<str>}``
- ``{"event":"result","ok":true,"data":<obj>}`` — always the last line
  on success.
- ``{"event":"error","type":<str>,"message":<str>,"traceback":<str>}``
  — always the last line on failure. Process also exits nonzero.

stdout is flushed after every emit so the parent process can consume
events in real time.
"""

from __future__ import annotations

import json
import sys
import traceback
from typing import Any


def _emit(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, default=str))
    sys.stdout.write("\n")
    sys.stdout.flush()


def progress(textbox: str | None = None,
             label: str | None = None,
             percent: int | None = None) -> None:
    """Emit a ``progress`` event. Any field may be ``None`` — the shim
    forwards ``None`` values verbatim to ``progress_callback`` so the
    Tk progress window keeps its current label/percent."""
    _emit({
        "event": "progress",
        "textbox": textbox,
        "label": label,
        "percent": percent,
    })


def log(message: str, level: str = "info") -> None:
    _emit({"event": "log", "level": level, "message": message})


def result(data: Any = None) -> None:
    """Emit the terminal ``result`` line. Callers should not emit
    anything else afterwards."""
    _emit({"event": "result", "ok": True, "data": data})


def error(exc: BaseException, override_type: str | None = None) -> None:
    """Emit the terminal ``error`` line. ``override_type`` lets the
    caller surface a specific exception class name even when the
    underlying exception is a wrapper (e.g. propagate
    ``LogixDesignerSdkNotFoundError`` on ``ImportError``)."""
    _emit({
        "event": "error",
        "type": override_type or type(exc).__name__,
        "message": str(exc),
        "traceback": "".join(traceback.format_exception(
            type(exc), exc, exc.__traceback__)),
    })
