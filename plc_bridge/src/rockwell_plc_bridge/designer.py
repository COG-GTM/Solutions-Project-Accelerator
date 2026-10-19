"""Rockwell Logix Designer SDK calls.

Copied verbatim (modulo progress-emission plumbing) from
``bin/logic_logix_designer.py`` so the sidecar owns exactly the same
runtime behavior. The main app now calls this via subprocess instead
of importing ``logix_designer_sdk`` directly, so the numpy>=2
requirement stays isolated inside the sidecar exe.
"""

from __future__ import annotations

import asyncio
import os

from rockwell_plc_bridge import events


class LogixDesignerSdkNotFoundError(RuntimeError):
    """Raised when ``import logix_designer_sdk`` fails inside the
    sidecar. The shim in the main app re-raises the same-named
    exception (defined in ``bin/logic_logix_designer.py``) when it
    parses this out of the ``error`` event."""


def _require_sdk():
    try:
        from logix_designer_sdk import LogixProject
    except ImportError as ex:
        raise LogixDesignerSdkNotFoundError(
            "The Logix Designer Python SDK (logix_designer_sdk) is not "
            "installed in the sidecar exe. Rebuild plc_bridge with the "
            "wheel installed into the plc_bridge/.venv virtualenv. See "
            "plc_bridge/README.md."
        ) from ex
    return LogixProject


async def _convert_l5x_to_acd_async(l5x_path: str, acd_path: str) -> None:
    LogixProject = _require_sdk()

    events.progress(
        textbox="Opening L5X: " + l5x_path,
        label="Opening L5X in Logix Designer SDK",
        percent=30,
    )
    project = await LogixProject.open_logix_project(l5x_path)
    try:
        # ``save_as`` does not overwrite unless ``force=True``. Remove
        # any stale ACD first so a failed save leaves no half-written
        # file behind.
        if os.path.isfile(acd_path):
            os.remove(acd_path)
        events.progress(
            textbox="Saving as ACD: " + acd_path,
            label="Saving ACD",
            percent=70,
        )
        await project.save_as(acd_path, True)
    finally:
        try:
            await project.close()
        except Exception:  # noqa: BLE001 - best-effort cleanup
            pass


def convert_l5x_to_acd(l5x_path: str, acd_path: str) -> str:
    """Open ``l5x_path`` with the Logix Designer SDK and save it as an
    ``.ACD`` at ``acd_path``. Returns the ACD path on success.

    :raises LogixDesignerSdkNotFoundError: if the SDK is not installed
        in the sidecar.
    :raises FileNotFoundError: if ``l5x_path`` does not exist.
    """
    if not os.path.isfile(l5x_path):
        raise FileNotFoundError("L5X file not found: " + l5x_path)

    events.progress(
        textbox="Starting L5X \u2192 ACD conversion via Logix Designer SDK",
        label="Converting L5X to ACD",
        percent=10,
    )
    asyncio.run(_convert_l5x_to_acd_async(l5x_path, acd_path))
    events.progress(
        textbox="ACD written: " + acd_path,
        label="Done",
        percent=100,
    )
    return acd_path
