# -*- coding: utf-8 -*-
"""Subprocess bridge to ``rockwell_plc_bridge.exe`` — the sidecar exe
that hosts the Rockwell ``logix_designer_sdk`` and ``ftecho_sdk`` in a
numpy-2 environment isolated from the main app.

The main app cannot import those SDKs directly because their numpy
requirement (``numpy>=2.4``) conflicts with the numpy pin (``<2``)
transitively imposed by ``paddleocr 2.7.3``, ``imgaug``, and friends.

This module resolves the sidecar exe location, spawns it with the
requested subcommand, parses its JSON-line event stream, and forwards
``progress`` / ``log`` events to the caller's ``progress_callback`` in
the same shape the existing GUI progress dialog already consumes
(``progress_callback(textbox_entry, label_text, percentage)``).

See ``plc_bridge/README.md`` for the sidecar CLI protocol.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from typing import Any, Callable, Iterable


class BridgeExeNotFoundError(RuntimeError):
    """Raised when :func:`resolve_bridge_exe` cannot find the sidecar
    exe in any of its well-known locations. The message includes every
    location that was checked so the developer knows where to drop the
    exe (or where to run ``pyinstaller`` to build it)."""


class BridgeProtocolError(RuntimeError):
    """Raised when the sidecar exits without emitting a terminal
    ``result`` or ``error`` event, or emits malformed JSON. This is
    always a bug in the sidecar (or a crash before any output was
    produced)."""


# Progress callback shape used by
# bin/gui_textbox_progressbar_window.texbox_progressbar_window and the
# existing PLC-code helpers. ``None`` values mean "keep the current
# textbox / label / percent unchanged".
ProgressCallback = Callable[[str | None, str | None, int | None], None]


# ────────────────────────────────────────────────────────────────────
# Resolver
# ────────────────────────────────────────────────────────────────────
_BRIDGE_EXE_NAME = "rockwell_plc_bridge.exe"
_BRIDGE_COLLECT_DIR = "rockwell_plc_bridge"


def _candidate_bridge_paths() -> list[str]:
    """Return the list of paths that :func:`resolve_bridge_exe` probes,
    in priority order. Exposed as its own function so
    :class:`BridgeExeNotFoundError` can name every location it checked.
    """
    bases: list[str] = []

    # 1. Frozen main app (PyInstaller onedir) — data files under _MEIPASS.
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        bases.append(meipass)

    # 2. Frozen main app — the COLLECT dir sits next to runme.exe under
    #    ``_internal/rockwell_plc_bridge/``. _MEIPASS should equal that
    #    _internal path in onedir mode, but keep this as a belt-and-
    #    braces fallback for other freeze layouts.
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        bases.append(os.path.join(exe_dir, "_internal"))
        bases.append(exe_dir)

    # 3. Running from source — repo root (two levels up from this file).
    #    Sidecar output lives at plc_bridge/dist/rockwell_plc_bridge/.
    repo_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), os.pardir))
    bases.append(os.path.join(repo_root, "plc_bridge", "dist"))

    candidates: list[str] = []
    for base in bases:
        candidates.append(os.path.join(
            base, _BRIDGE_COLLECT_DIR, _BRIDGE_EXE_NAME))
    return candidates


def resolve_bridge_exe() -> str:
    """Return the absolute path to ``rockwell_plc_bridge.exe``.

    :raises BridgeExeNotFoundError: if the sidecar is not present in
        any of the well-known locations.
    """
    checked: list[str] = []
    for path in _candidate_bridge_paths():
        checked.append(path)
        if os.path.isfile(path):
            return path

    raise BridgeExeNotFoundError(
        "The Rockwell PLC SDK sidecar (" + _BRIDGE_EXE_NAME + ") was not "
        "found. Build it with:\n"
        "    plc_bridge\\.venv\\Scripts\\Activate.ps1\n"
        "    pyinstaller plc_bridge/rockwell_plc_bridge.spec "
        "--distpath plc_bridge/dist\n"
        "See plc_bridge/README.md for the build-env recipe.\n\n"
        "Checked locations:\n" + "\n".join("    " + p for p in checked)
    )


def bridge_available() -> bool:
    """Return ``True`` if the sidecar exe can be found on disk. Does not
    execute it."""
    try:
        resolve_bridge_exe()
        return True
    except BridgeExeNotFoundError:
        return False


# ────────────────────────────────────────────────────────────────────
# Subprocess runner
# ────────────────────────────────────────────────────────────────────
def _popen_kwargs() -> dict[str, Any]:
    # stderr is merged into stdout so a full stderr pipe (64 KB on
    # Windows) can never block the sidecar. Non-JSON lines that leak
    # through are captured for post-mortem in BridgeProtocolError.
    #
    # PYTHONIOENCODING=utf-8 forces the sidecar's stdio to UTF-8
    # regardless of the Windows console codepage. The sidecar also
    # calls ``sys.stdout.reconfigure`` at startup for defense in depth,
    # but env-var is the belt.
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    kw: dict[str, Any] = dict(
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,  # line-buffered
        env=env,
    )
    # Don't flash a console window when the main app is a windowed
    # PyInstaller build.
    if sys.platform == "win32":
        kw["creationflags"] = getattr(
            subprocess, "CREATE_NO_WINDOW", 0x08000000)
    return kw


def run_bridge(
    argv: Iterable[str],
    progress_callback: ProgressCallback | None = None,
    error_type_map: dict[str, type[BaseException]] | None = None,
) -> Any:
    """Run ``rockwell_plc_bridge.exe`` with ``argv`` and return the
    ``data`` field of the final ``result`` event.

    ``progress_callback`` receives ``(textbox, label, percent)`` for
    every ``progress`` event; ``log`` events are logged at the
    matching level. Any other event type is silently ignored so the
    sidecar can grow new event types without breaking older shims.

    ``error_type_map`` maps sidecar exception class names to main-app
    exception classes. On an ``error`` event the shim raises the
    mapped exception (or :class:`RuntimeError` if the name is
    unmapped) with ``message`` from the JSON. A nonzero exit without
    a terminal event raises :class:`BridgeProtocolError`.
    """
    exe = resolve_bridge_exe()
    cmd = [exe, *argv]
    logging.info("plc_bridge: launching %s", cmd)

    error_type_map = error_type_map or {}
    terminal_event: dict[str, Any] | None = None
    # Non-JSON stdout / stderr lines are kept for post-mortem in case
    # the sidecar crashes before emitting a terminal event. Bounded so
    # a runaway sidecar can't blow up main-app memory.
    stray_output: list[str] = []
    _STRAY_LIMIT = 200

    proc = subprocess.Popen(cmd, **_popen_kwargs())
    try:
        assert proc.stdout is not None  # for type checkers
        for raw_line in proc.stdout:
            line = raw_line.rstrip("\r\n")
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                # Non-JSON stdout is treated as a plain log line rather
                # than a fatal error — the sidecar may emit stray output
                # from third-party libraries we can't silence. Keep the
                # last few lines for the crash message below.
                logging.debug("plc_bridge: non-JSON stdout: %s", line)
                if len(stray_output) < _STRAY_LIMIT:
                    stray_output.append(line)
                continue

            kind = event.get("event")
            if kind == "progress":
                if progress_callback is not None:
                    try:
                        progress_callback(
                            event.get("textbox"),
                            event.get("label"),
                            event.get("percent"),
                        )
                    except Exception:  # noqa: BLE001 — never let GUI errors kill the pump
                        logging.exception(
                            "plc_bridge: progress_callback raised")
            elif kind == "log":
                level = str(event.get("level", "info")).lower()
                msg = str(event.get("message", ""))
                log_fn = getattr(logging, level, logging.info)
                log_fn("plc_bridge: %s", msg)
            elif kind in ("result", "error"):
                terminal_event = event
                # Keep pumping in case the sidecar emits stray output
                # after the terminal event — we only care about the
                # first terminal event.
            else:
                logging.debug("plc_bridge: unknown event: %s", event)

        exit_code = proc.wait()
    finally:
        # Ensure we don't leak the process on unexpected exceptions.
        if proc.poll() is None:
            proc.kill()
            proc.wait()

    if terminal_event is None:
        raise BridgeProtocolError(
            "Rockwell PLC bridge exited with code " + str(exit_code) +
            " without emitting a terminal event.\n"
            "Command: " + " ".join(cmd) + "\n"
            "Stray output:\n" +
            ("\n".join(stray_output) if stray_output else "<empty>")
        )

    if terminal_event.get("event") == "result":
        return terminal_event.get("data")

    # ``error`` event — translate to a main-app exception.
    err_type = str(terminal_event.get("type", "BridgeError"))
    err_msg = str(terminal_event.get("message",
                                     "Rockwell PLC bridge failed."))
    exc_cls = error_type_map.get(err_type, RuntimeError)
    raise exc_cls(err_msg)


# ────────────────────────────────────────────────────────────────────
# Higher-level helpers
# ────────────────────────────────────────────────────────────────────
def probe_sdk(sdk: str) -> bool:
    """Return ``True`` if the sidecar reports the given SDK
    (``"designer"`` or ``"echo"``) as importable. Returns ``False`` if
    the sidecar exe is missing or the probe raises any error — this
    matches the behavior of the legacy in-process ``is_sdk_available``
    functions so menu-time guards keep working unchanged.
    """
    try:
        run_bridge(("probe", "--sdk", sdk))
        return True
    except Exception:  # noqa: BLE001 — probe is best-effort
        return False


def bridge_version() -> dict[str, Any] | None:
    """Return the sidecar's ``--version`` JSON payload, or ``None`` if
    the sidecar cannot be located / run."""
    try:
        return run_bridge(("--version",))
    except Exception:  # noqa: BLE001 — version check is best-effort
        return None
