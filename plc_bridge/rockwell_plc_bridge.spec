# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Rockwell PLC SDK sidecar.

Onedir console exe. Built inside the ``plc_bridge/.venv`` virtualenv
(python 3.12 + numpy 2 + logix_designer_sdk + ftecho_sdk + pyinstaller).
See plc_bridge/README.md for the env recipe.

The main app's ``runme.spec`` picks up ``plc_bridge/dist/rockwell_plc_bridge``
automatically and bundles it under ``_internal/rockwell_plc_bridge/`` in
the frozen distribution.
"""
import os
import sys

from PyInstaller.utils.hooks import collect_all

# Make ``rockwell_plc_bridge`` importable when Analysis resolves it.
_here = os.path.dirname(os.path.abspath(SPEC))  # noqa: F821 — provided by PyInstaller
_src = os.path.join(_here, 'src')
if _src not in sys.path:
    sys.path.insert(0, _src)

# --- Preflight: fail loudly if the wheels aren't importable in the ---
# current interpreter. Without this check ``collect_all`` silently
# returns empty tuples when a package is missing, PyInstaller emits a
# tiny warning buried in its log, and you end up with a built exe that
# only fails at runtime with "SDK not installed". That situation is
# always operator error: the build was launched from the wrong
# virtualenv (usually the main app's ``.venv``) instead of
# ``plc_bridge/.venv``.
import importlib.util as _importlib_util
_missing = [name for name in ('logix_designer_sdk', 'ftecho_sdk')
            if _importlib_util.find_spec(name) is None]
if _missing:
    raise SystemExit(
        "\n[rockwell_plc_bridge.spec] ABORTING. The following Rockwell "
        "SDK packages are not importable in the current interpreter:\n"
        "    " + ", ".join(_missing) + "\n\n"
        "Interpreter: " + sys.executable + "\n\n"
        "Build the sidecar in the ``plc_bridge/.venv`` virtualenv, "
        "not the main app env. Either run\n"
        "    powershell -File build_scripts/setup_plc_bridge_dev.ps1\n"
        "or activate the env manually:\n"
        "    plc_bridge\\.venv\\Scripts\\Activate.ps1\n"
        "    pyinstaller plc_bridge/rockwell_plc_bridge.spec "
        "--distpath plc_bridge/dist\n"
        "See plc_bridge/README.md for the env recipe.\n"
    )

datas, binaries, hiddenimports = [], [], []

# Bundle both SDKs and their transitive .NET / native dependencies.
# collect_all pulls in datas (config files), binaries (.dll / .pyd), and
# hidden imports (submodules the static analyzer misses because the SDKs
# load them via clr_loader / pythonnet at runtime).
for _sdk in ('logix_designer_sdk', 'ftecho_sdk'):
    _d, _b, _h = collect_all(_sdk)
    datas += _d
    binaries += _b
    hiddenimports += _h

# clr_loader / pythonnet + interfaces submodule (Echo). The Echo module
# does ``from ftecho_sdk.interfaces import ...`` which PyInstaller
# usually catches, but adding it explicitly is cheap insurance.
hiddenimports += [
    'clr_loader',
    'pythonnet',
    'ftecho_sdk.interfaces',
]


a = Analysis(
    [os.path.join(_src, 'rockwell_plc_bridge', '__main__.py')],
    pathex=[_src],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Main-app deps that must not accidentally land in the sidecar.
        'paddle', 'paddleocr', 'imgaug', 'cv2', 'torch', 'tensorflow',
        'sklearn', 'scipy', 'matplotlib', 'pandas', 'PIL', 'tkinter',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='rockwell_plc_bridge',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # JSON-lines on stdout — must stay console=True.
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='rockwell_plc_bridge',
)
