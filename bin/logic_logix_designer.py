# -*- coding: utf-8 -*-
"""Bridge between Solutions Project Accelerator and the Rockwell Logix
Designer Python SDK.

The SDK now lives inside the ``rockwell_plc_bridge.exe`` sidecar (see
``plc_bridge/`` and :mod:`bin.logic_plc_bridge`) so its ``numpy>=2``
requirement stays isolated from the main app's numpy<2 pin. This
module is a thin, source-compatible facade over that subprocess call:
existing callers keep the same signatures and exception types.
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


DEFAULT_LOGIX_SDK_WHEEL_DIR = (
    r'C:\Users\Public\Documents\Studio 5000\Logix Designer SDK\python'
)


class LogixDesignerSdkNotFoundError(RuntimeError):
    """Raised when the Logix Designer Python SDK is not available.

    Retained for signature stability with the pre-sidecar API. The
    message is user-facing and produced by :func:`sdk_install_hint`.
    """


class LogixDesignerServiceUnavailableError(RuntimeError):
    """Raised when the Logix Designer SDK is installed but the
    underlying ``LdSdkService`` cannot be reached.

    This usually means Studio 5000 / its SDK service is not running,
    not installed correctly, or is blocked by policy/AV.
    """


# Map sidecar-side exception type strings (see plc_bridge.designer /
# plc_bridge.echo) to main-app exception classes. Anything not listed
# falls through to RuntimeError inside run_bridge.
_ERROR_TYPE_MAP: dict[str, type[BaseException]] = {
    'LogixDesignerSdkNotFoundError': LogixDesignerSdkNotFoundError,
    'OperationNotPerformedError': LogixDesignerServiceUnavailableError,
    'FileNotFoundError': FileNotFoundError,
    'ValueError': ValueError,
}


def _service_unreachable_hint(raw_message, l5x_path):
    """Return a user-facing message for ``LdSdkService`` connectivity
    failures.

    The SDK throws ``OperationNotPerformedError`` for multiple backend
    failures, but the most common field issue is:
    "Could not reach LdSdkService (<path>)".
    """
    lines = [
        'Rockwell Logix Designer SDK is installed, but its backend '
        'service (LdSdkService) is not reachable.',
        '',
        'L5X file:',
        '    ' + str(l5x_path),
        '',
        'SDK message:',
        '    ' + str(raw_message),
        '',
        'Try these steps:',
        '1) Start Studio 5000 Logix Designer (same Windows user/session).',
        '2) Verify the Logix Designer SDK components are installed '
        '(Studio 5000 installer).',
        '3) Restart the "Rockwell Logix Designer SDK Service" '
        '(LdSdkService) or reboot.',
        '4) Ensure endpoint security is not blocking the SDK service '
        'or local IPC.',
    ]
    return '\n'.join(lines)


def is_sdk_available():
    """Return ``True`` if the sidecar reports ``logix_designer_sdk``
    as importable. Returns ``False`` if the sidecar exe is missing or
    the probe fails for any reason (matches the pre-sidecar behavior
    of "any error => SDK unavailable")."""
    return probe_sdk('designer')


def sdk_install_hint(wheel_dir=None):
    """Return a human-readable install-guide string for the SDK.

    ``wheel_dir`` may be a path to a specific ``*.whl`` file or a
    directory containing one; it defaults to
    :data:`DEFAULT_LOGIX_SDK_WHEEL_DIR`. It's only used to name the
    wheel in the "rebuild the sidecar" instructions.

    Two variants:

    - Sidecar exe missing => "the sidecar isn't installed next to
      runme.exe" plus build recipe (unfrozen) or "obtain a rebuilt
      distribution" (frozen).
    - Sidecar exe present but SDK missing inside it => "rebuild the
      sidecar with the wheel installed".
    """
    frozen = getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')
    if wheel_dir is None:
        wheel_dir = DEFAULT_LOGIX_SDK_WHEEL_DIR
    wheels = []
    display_location = wheel_dir
    if wheel_dir and os.path.isfile(wheel_dir) and wheel_dir.lower().endswith('.whl'):
        wheels = [wheel_dir]
        display_location = os.path.dirname(wheel_dir) or wheel_dir
    elif os.path.isdir(wheel_dir):
        wheels = sorted(glob.glob(os.path.join(
            wheel_dir, 'logix_designer_sdk-*.whl')))
    wheel_hint = (
        wheels[-1] if wheels else os.path.join(
            display_location,
            'logix_designer_sdk-<version>-py3-none-any.whl'))

    if not bridge_available():
        lines = [
            'The Rockwell Logix Designer Python SDK is unavailable '
            'because the rockwell_plc_bridge sidecar exe was not '
            'found next to the application.',
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
        'The Rockwell Logix Designer Python SDK is not installed '
        'inside the rockwell_plc_bridge sidecar exe.',
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


def convert_l5x_to_acd(l5x_path, acd_path, wheel_dir=None,
                       progress_callback=None):
    """Open ``l5x_path`` with the Logix Designer SDK (via the sidecar
    exe) and save it as an ``.ACD`` at ``acd_path``.

    ``wheel_dir`` is only used to compose an install-guide error
    message if the sidecar or its embedded SDK is missing.

    :raises LogixDesignerSdkNotFoundError: if the sidecar is missing
        or the SDK inside it is not importable.
    :raises FileNotFoundError: if ``l5x_path`` does not exist.
    """
    if not os.path.isfile(l5x_path):
        raise FileNotFoundError('L5X file not found: ' + l5x_path)

    _report(progress_callback,
            'Starting L5X \u2192 ACD conversion via Logix Designer SDK',
            'Converting L5X to ACD',
            10)
    try:
        run_bridge(
            (
                'designer', 'convert-l5x-to-acd',
                '--l5x-path', l5x_path,
                '--acd-path', acd_path,
            ),
            progress_callback=progress_callback,
            error_type_map=_ERROR_TYPE_MAP,
        )
    except BridgeExeNotFoundError as ex:
        raise LogixDesignerSdkNotFoundError(
            sdk_install_hint(wheel_dir)) from ex
    except LogixDesignerServiceUnavailableError as ex:
        raise LogixDesignerServiceUnavailableError(
            _service_unreachable_hint(ex, l5x_path)) from ex
    _report(progress_callback,
            'ACD written: ' + acd_path,
            'Done',
            100)
    return acd_path


def push_build_output_to_logix_designer(progress_callback, acm_data_handler,
                                        config, internal_db, project_name,
                                        output_path):
    """Build the PLC L5X via ACM and convert it to an ``.ACD`` in the
    same folder using the Logix Designer SDK.

    Signature mirrors :func:`bin.logic_tools.start_build_plc` so it can
    be passed directly to
    :class:`bin.gui_textbox_progressbar_window.texbox_progressbar_window`
    as::

        texbox_progressbar_window(
            push_build_output_to_logix_designer,
            'Build PLC \u2192 Logix Designer',
            acm_data_handler, config, db, project_name, output_path)
    """
    # Import lazily so gui_main.py stays importable even if this module
    # ever grows a dependency that isn't required for the L5X path.
    from bin.logic_acm_console import ACM_Console

    # Phase 1: run the same ACM build the "ACD" target runs.
    acm_console = ACM_Console(project_name, acm_data_handler, internal_db, config)
    acm_console.build_plc_acd(output_path, progress_callback=progress_callback)

    # Phase 2: locate the produced L5X. ACM_Console.build_plc_acd writes to
    # ``<output_path>\<controller_name>.ACD`` (see
    # bin/logic_acm_console.py::ACM_Console.build_plc_acd).
    controller_name = acm_data_handler.get_controller_name()
    if not controller_name:
        raise ValueError(
            'No controller name available from ACM data handler. '
            'Go to Tools > Create ACM Project first.')
    acd_path = os.path.join(output_path, controller_name + '.ACD')

    return acd_path
