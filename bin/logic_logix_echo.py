# -*- coding: utf-8 -*-
"""Bridge between Solutions Project Accelerator and the Rockwell
FactoryTalk Logix Echo Python SDK (``ftecho_sdk``).

The SDK now lives inside the ``rockwell_plc_bridge.exe`` sidecar (see
``plc_bridge/`` and :mod:`bin.logic_plc_bridge`) so its ``numpy>=2``
requirement stays isolated from the main app's numpy<2 pin. This
module is a thin, source-compatible facade over that subprocess call:
existing callers keep the same signatures and exception types.

The workflow the sidecar implements mirrors the SDK's example
``create_controller_from_acd.py`` + ``download.py`` pipeline
(``ServiceApiClientV2.send_file`` -> ``get_controller_info_from_acd``
-> ``create_controller`` -> ``download`` -> poll ``get_download_feedback``).
"""

import glob
import os
import sys

from bin.logic_plc_bridge import (
    BridgeExeNotFoundError,
    bridge_available,
    probe_sdk,
    run_bridge,
)


DEFAULT_LOGIX_ECHO_SDK_WHEEL_DIR = (
    r'C:\Users\Public\Documents\FactoryTalk Logix Echo\SDK\Python'
)


class LogixEchoSdkNotFoundError(RuntimeError):
    """Raised when the FactoryTalk Logix Echo Python SDK is not available.

    Retained for signature stability with the pre-sidecar API. The
    message is user-facing and produced by :func:`sdk_install_hint`.
    """


class LogixEchoControllerExistsError(RuntimeError):
    """Raised when a controller with the same name already exists in
    Logix Echo. Deleting or renaming existing controllers is destructive
    so we surface a clear message rather than doing it silently."""


# Map sidecar-side exception type strings to main-app exception classes.
_ERROR_TYPE_MAP: dict[str, type[BaseException]] = {
    'LogixEchoSdkNotFoundError': LogixEchoSdkNotFoundError,
    'LogixEchoControllerExistsError': LogixEchoControllerExistsError,
    'FileNotFoundError': FileNotFoundError,
    'ValueError': ValueError,
}


def is_sdk_available():
    """Return ``True`` if the sidecar reports ``ftecho_sdk`` as
    importable. Returns ``False`` if the sidecar exe is missing or the
    probe fails for any reason."""
    return probe_sdk('echo')


def sdk_install_hint(wheel_dir=None):
    """Return a human-readable install-guide string.

    Two variants (mirrors :func:`bin.logic_logix_designer.sdk_install_hint`):

    - Sidecar exe missing => "sidecar isn't installed" + build recipe.
    - Sidecar exe present but SDK missing => "rebuild the sidecar
      with the wheel installed".
    """
    frozen = getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')
    if wheel_dir is None:
        wheel_dir = DEFAULT_LOGIX_ECHO_SDK_WHEEL_DIR
    wheels = []
    display_location = wheel_dir
    if wheel_dir and os.path.isfile(wheel_dir) and wheel_dir.lower().endswith('.whl'):
        wheels = [wheel_dir]
        display_location = os.path.dirname(wheel_dir) or wheel_dir
    elif os.path.isdir(wheel_dir):
        wheels = sorted(glob.glob(os.path.join(
            wheel_dir, 'ftecho_sdk-*.whl')))
    wheel_hint = (
        wheels[-1] if wheels else os.path.join(
            display_location, 'ftecho_sdk-<version>-py3-none-any.whl'))

    if not bridge_available():
        lines = [
            'The Rockwell FactoryTalk Logix Echo Python SDK is '
            'unavailable because the rockwell_plc_bridge sidecar exe '
            'was not found next to the application.',
            '',
            'Expected wheel location (for rebuilding the sidecar):',
            '    ' + display_location,
        ]
        if frozen:
            lines += [
                '',
                'This is a packaged (frozen) build. Obtain a '
                'distribution that ships rockwell_plc_bridge.exe '
                'alongside runme.exe under '
                '_internal/rockwell_plc_bridge/.',
            ]
        else:
            lines += [
                '',
                'Build the sidecar with:',
                '    plc_bridge\\.venv\\Scripts\\Activate.ps1',
                '    pip install "' + wheel_hint + '"',
                '    pyinstaller plc_bridge/rockwell_plc_bridge.spec '
                '--distpath plc_bridge/dist',
                '',
                'See plc_bridge/README.md for the full build-env recipe.',
            ]
        return '\n'.join(lines)

    lines = [
        'The Rockwell FactoryTalk Logix Echo Python SDK is not '
        'installed inside the rockwell_plc_bridge sidecar exe.',
        '',
        'Expected wheel location (for rebuilding the sidecar):',
        '    ' + display_location,
        '',
        'Rebuild the sidecar with the wheel installed into the '
        'sidecar venv:',
        '    plc_bridge\\.venv\\Scripts\\Activate.ps1',
        '    pip install "' + wheel_hint + '"',
        '    pyinstaller plc_bridge/rockwell_plc_bridge.spec '
        '--distpath plc_bridge/dist',
        '',
        'See plc_bridge/README.md for details.',
    ]
    return '\n'.join(lines)


def _report(progress_callback, textbox_entry, label_text, percentage):
    """Emit progress if a callback is provided; ignore return value."""
    if progress_callback is not None:
        progress_callback(textbox_entry, label_text, percentage)


def push_acd_to_logix_echo(acd_path, chassis_name=None,
                           ip1=None, m1=None, ip2=None, m2=None,
                           wheel_dir=None, progress_callback=None):
    """Create a controller in FactoryTalk Logix Echo from ``acd_path``
    and download the ACD to it (via the sidecar exe). Returns the new
    controller GUID.

    ``chassis_name`` selects (or creates) a chassis by name; ``None`` /
    empty uses the default chassis. IP overrides are optional — pass
    address + netmask together or leave both as ``None`` to keep the ACD
    default. ``wheel_dir`` is only used to compose an install-guide
    error message if the sidecar or its embedded SDK is missing.

    :raises LogixEchoSdkNotFoundError: if the sidecar is missing or the
        SDK inside it is not importable.
    :raises FileNotFoundError: if ``acd_path`` does not exist.
    :raises LogixEchoControllerExistsError: if a controller with the
        same name already exists in Logix Echo.
    """
    if not os.path.isfile(acd_path):
        raise FileNotFoundError('ACD file not found: ' + acd_path)

    _report(progress_callback,
            'Starting push of ' + os.path.basename(acd_path) +
            ' to FactoryTalk Logix Echo',
            'Push ACD to Logix Echo', 5)

    argv = ['echo', 'push-acd', '--acd-path', acd_path]
    if chassis_name:
        argv += ['--chassis-name', chassis_name]
    if ip1:
        argv += ['--ip1', ip1]
    if m1:
        argv += ['--m1', m1]
    if ip2:
        argv += ['--ip2', ip2]
    if m2:
        argv += ['--m2', m2]

    try:
        data = run_bridge(
            argv,
            progress_callback=progress_callback,
            error_type_map=_ERROR_TYPE_MAP,
        )
    except BridgeExeNotFoundError as ex:
        raise LogixEchoSdkNotFoundError(sdk_install_hint(wheel_dir)) from ex

    controller_guid = (data or {}).get('controller_guid')
    if not controller_guid:
        raise RuntimeError(
            'Rockwell PLC bridge did not return a controller_guid.')
    return str(controller_guid)


def push_build_output_to_logix_echo(progress_callback, acm_data_handler,
                                    config, internal_db, project_name,
                                    output_path):
    """Build the PLC L5X via ACM, convert it to an ``.ACD`` with the
    Logix Designer SDK (via the sidecar), then push that ACD to
    FactoryTalk Logix Echo (also via the sidecar).

    Signature mirrors :func:`bin.logic_tools.start_build_plc` and
    :func:`bin.logic_logix_designer.push_build_output_to_logix_designer`
    so it can be passed directly to
    :class:`bin.gui_textbox_progressbar_window.texbox_progressbar_window`.
    """
    # Lazy import — Logix Designer SDK failures should be surfaced via
    # its own install hint (thrown by push_build_output_to_logix_designer).
    from bin.logic_logix_designer import push_build_output_to_logix_designer

    # Phase 1+2: build L5X → ACD (same as the "Logix Designer" menu item).
    acd_path = push_build_output_to_logix_designer(
        progress_callback, acm_data_handler, config, internal_db,
        project_name, output_path)

    # Phase 3: push to Logix Echo.
    wheel_dir = None
    getter = getattr(config, 'get_logix_echo_sdk_wheel_dir', None)
    if callable(getter):
        wheel_dir = getter()
    controller_guid = push_acd_to_logix_echo(
        acd_path, wheel_dir=wheel_dir, progress_callback=progress_callback)
    return controller_guid
