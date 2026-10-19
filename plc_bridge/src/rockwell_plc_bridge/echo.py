"""FactoryTalk Logix Echo SDK calls.

Copied verbatim (modulo progress-emission plumbing) from
``bin/logic_logix_echo.py``. Isolated inside the sidecar so the
numpy>=2 requirement of ``ftecho_sdk`` doesn't conflict with the
main app's numpy<2 pin.
"""

from __future__ import annotations

import asyncio
import os

from rockwell_plc_bridge import events


class LogixEchoSdkNotFoundError(RuntimeError):
    """Raised when ``import ftecho_sdk`` fails inside the sidecar."""


class LogixEchoControllerExistsError(RuntimeError):
    """Raised when a controller with the same name already exists in
    Logix Echo. Deleting or renaming existing controllers is destructive
    so we surface a clear message rather than doing it silently."""


def _require_sdk():
    try:
        from ftecho_sdk import ServiceApiClientV2, FTEchoSdkError
        from ftecho_sdk.interfaces import OperationState, ChassisUpdate
    except ImportError as ex:
        raise LogixEchoSdkNotFoundError(
            "The FactoryTalk Logix Echo Python SDK (ftecho_sdk) is not "
            "installed in the sidecar exe. Rebuild plc_bridge with the "
            "wheel installed into the plc_bridge/.venv virtualenv. See "
            "plc_bridge/README.md."
        ) from ex
    return ServiceApiClientV2, OperationState, ChassisUpdate, FTEchoSdkError


async def _find_or_create_chassis(service_client, ChassisUpdate, chassis_name):
    """Return the GUID of a chassis called ``chassis_name``, creating it
    if it does not yet exist. An empty / ``None`` name selects the Logix
    Echo default chassis (empty-string GUID)."""
    if not chassis_name:
        return ""

    chassis_list = await service_client.list_chassis()
    for chassis in chassis_list:
        if chassis.name == chassis_name:
            return chassis.chassis_guid

    chassis_data = await service_client.create_chassis(
        ChassisUpdate(name=chassis_name, description="Created by SPA"))
    return chassis_data.chassis_guid


async def _wait_for_download(service_client, OperationState, controller_guid):
    """Poll ``get_download_feedback`` until the operation leaves
    ``IN_PROGRESS``. Streams status messages / progress into the
    progress-window textbox via ``events.progress``."""
    seen_messages = 0
    last_progress = -1
    while True:
        feedback = await service_client.get_download_feedback(controller_guid)

        if feedback.messages and len(feedback.messages) > seen_messages:
            for msg in feedback.messages[seen_messages:]:
                events.progress(
                    textbox="Echo: " + str(msg),
                    label="Download to Logix Echo",
                    percent=None,
                )
            seen_messages = len(feedback.messages)

        progress = getattr(feedback, "progress", 0) or 0
        if progress != last_progress and progress > 0:
            events.progress(
                textbox=None,
                label="Download to Logix Echo",
                percent=min(99, 50 + progress // 2),
            )
            last_progress = progress

        if feedback.state != OperationState.IN_PROGRESS:
            return feedback.state

        await asyncio.sleep(1)


async def _push_acd_to_echo_async(acd_path, chassis_name, ip1, m1, ip2, m2):
    (ServiceApiClientV2, OperationState, ChassisUpdate,
     _FTEchoSdkError) = _require_sdk()

    events.progress(
        textbox="Connecting to FactoryTalk Logix Echo service",
        label="Uploading ACD to Logix Echo",
        percent=15,
    )
    service_client = ServiceApiClientV2()

    async with await service_client.send_file(acd_path) as file_handle:
        events.progress(
            textbox="Uploaded: " + os.path.basename(acd_path),
            label="Uploading ACD to Logix Echo",
            percent=30,
        )

        controller_info = await service_client.get_controller_info_from_acd(
            file_handle)

        controller_name = getattr(controller_info, "controller_name", None)
        if not controller_name:
            # Fallback: derive from filename (matches ACM output naming).
            controller_name = os.path.splitext(os.path.basename(acd_path))[0]
            controller_info.controller_name = controller_name

        # Abort early on name clash — deleting existing controllers is a
        # destructive action we don't perform silently.
        existing = await service_client.list_controllers()
        for ctrl in existing:
            if getattr(ctrl, "controller_name", None) == controller_name:
                raise LogixEchoControllerExistsError(
                    'A controller called "' + controller_name +
                    '" already exists in Logix Echo. Delete it (or '
                    "rename it) in the FactoryTalk Logix Echo Manager "
                    "and retry."
                )

        # Optional IP overrides (both address + netmask required together).
        if ip1 and m1 and controller_info.ip_configuration_data:
            controller_info.ip_configuration_data.address = ip1
            controller_info.ip_configuration_data.netmask = m1
        if ip2 and m2 and getattr(
                controller_info, "ip_configuration_data_secondary", None):
            controller_info.ip_configuration_data_secondary.address = ip2
            controller_info.ip_configuration_data_secondary.netmask = m2

        controller_info.chassis_guid = await _find_or_create_chassis(
            service_client, ChassisUpdate, chassis_name)

        events.progress(
            textbox="Creating controller: " + controller_name,
            label="Creating Logix Echo controller",
            percent=45,
        )
        controller_data = await service_client.create_controller(controller_info)

        events.progress(
            textbox="Controller GUID: " + str(controller_data.controller_guid),
            label="Downloading to Logix Echo controller",
            percent=50,
        )
        await service_client.download(controller_data.controller_guid,
                                      file_handle)

        final_state = await _wait_for_download(
            service_client, OperationState, controller_data.controller_guid)

    if final_state == OperationState.DONE:
        events.progress(
            textbox="Download complete: " + controller_name,
            label="Done",
            percent=100,
        )
        return str(controller_data.controller_guid)

    raise RuntimeError(
        "Logix Echo download finished in unexpected state: " + str(final_state))


def push_acd_to_logix_echo(acd_path: str,
                           chassis_name: str | None = None,
                           ip1: str | None = None,
                           m1: str | None = None,
                           ip2: str | None = None,
                           m2: str | None = None) -> str:
    """Create a controller in FactoryTalk Logix Echo from ``acd_path``
    and download the ACD to it. Returns the new controller GUID.

    :raises LogixEchoSdkNotFoundError: if the SDK is not installed
        in the sidecar.
    :raises FileNotFoundError: if ``acd_path`` does not exist.
    :raises LogixEchoControllerExistsError: if a controller with the
        same name already exists in Logix Echo.
    """
    if not os.path.isfile(acd_path):
        raise FileNotFoundError("ACD file not found: " + acd_path)

    events.progress(
        textbox="Starting push of " + os.path.basename(acd_path) +
                " to FactoryTalk Logix Echo",
        label="Push ACD to Logix Echo",
        percent=5,
    )
    return asyncio.run(_push_acd_to_echo_async(
        acd_path, chassis_name, ip1, m1, ip2, m2))
