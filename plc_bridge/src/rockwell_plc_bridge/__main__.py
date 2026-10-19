"""Entry point for ``python -m rockwell_plc_bridge`` and for the
PyInstaller-frozen ``rockwell_plc_bridge.exe``.
"""
import sys


def _force_utf8_io() -> None:
    """Force stdout/stderr to UTF-8.

    On Windows the default console codepage is cp1252, which crashes
    on non-ASCII characters in progress messages (e.g. the "L5X -> ACD"
    arrow, ``\\u2192``). The shim in the main app reads the pipe as
    UTF-8, so if we make the sidecar write UTF-8 unconditionally the
    two agree regardless of console locale. ``errors='replace'`` is a
    last-ditch fallback for pathological input — the JSON layer above
    should never produce anything unrepresentable in UTF-8.
    """
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None:
            continue
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001 — best-effort; never crash startup
            pass


_force_utf8_io()

from rockwell_plc_bridge.cli import main  # noqa: E402 — after I/O setup


if __name__ == "__main__":
    raise SystemExit(main())
