# -*- mode: python ; coding: utf-8 -*-
import os
import sysconfig
from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.utils.hooks import collect_all

# Resolve site-packages from the interpreter running PyInstaller, not a fixed env path.
SITE_PACKAGES = sysconfig.get_paths()['purelib']

datas = [('./bin/logo.ico', './bin'), ('./cairosvg/VERSION', './cairosvg'), ('./Paddle-OCR', './Paddle-OCR'), ('./SAM2.1', './SAM2.1'), ('./Potrace', './Potrace'), ('./Poppler', './Poppler'), ('./AnyMD', './AnyMD'), ('TaskbarLib.tlb', '.')]

datas += [
    (os.path.join(SITE_PACKAGES, 'Cython', 'Utility', 'StringTools.c'), './Cython/Utility'),
    (os.path.join(SITE_PACKAGES, 'Shapely.libs'), './Shapely.libs'),
    (os.path.join(SITE_PACKAGES, 'cairocffi'), './cairocffi'),
]

# PyTaskbar >= 0.1.1 loads TaskbarLib.tlb from its own package directory.
datas += collect_data_files('PyTaskbar', includes=['*.tlb'])

# --- Bundled documentation (built by build_scripts/build_docs.py) -----------
# The MkDocs Material site is written to ./build/docs_site.  If it exists,
# ship it under _internal/docs/site so Help -> Documentation can open it
# offline via file://.  Build is optional so devs without the docs toolchain
# still get a working PyInstaller build.
_docs_site = os.path.join(os.getcwd(), 'build', 'docs_site')
if os.path.isdir(_docs_site) and os.path.isfile(os.path.join(_docs_site, 'index.html')):
    datas += [(_docs_site, './docs/site')]
    print(f"[runme.spec] Bundling docs site from {_docs_site}")
else:
    print(f"[runme.spec] WARNING: docs site not found at {_docs_site}; "
          "run 'python build_scripts/build_docs.py' before packaging to include the offline docs.")
binaries = []
hiddenimports = ['imghdr', 'cython', 'imgaug', 'pyclipper', 'sqlalchemy.sql.default_comparator', 'cairosvg']

# --- Optional enterprise LLM gateway plugin --------------------------------
# ``genai_bridge`` lives in its own repository (and is git-ignored here), so
# it is only bundled when the source tree is present next to this one. Its
# production credentials come from ``genai_bridge/.env.prod``, which lands at
# ``_internal/.env.prod`` and is picked up by ``bin/logic_env_file.py``.
# See bin/logic_llm_inference.py::load_enterprise_inference_class.
_genai_src = os.path.join(os.getcwd(), 'genai_bridge', 'src')
_genai_pathex = []
if os.path.isdir(os.path.join(_genai_src, 'genai_bridge')):
    _genai_pathex.append(_genai_src)
    hiddenimports += [
        'genai_bridge',
        'genai_bridge.config',
        'genai_bridge.inference',
        'genai_bridge.msal_login',
        'genai_bridge.api_protector',
    ]
    _genai_prod_env = os.path.join(os.getcwd(), 'genai_bridge', '.env.prod')
    if os.path.isfile(_genai_prod_env):
        datas += [(_genai_prod_env, '.')]
        print(f"[runme.spec] Bundling genai_bridge + {_genai_prod_env}")
    else:
        print("[runme.spec] WARNING: genai_bridge bundled without .env.prod; "
              "the frozen exe will fall back to Ollama / public OpenAI.")
else:
    print("[runme.spec] WARNING: genai_bridge source not found; the frozen "
          "exe will fall back to Ollama / public OpenAI.")

datas += collect_data_files('paddle')
datas += collect_data_files('scipy')
tmp_ret = collect_all('paddleocr')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('lmdb')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

# NOTE: The Rockwell ``logix_designer_sdk`` and ``ftecho_sdk`` wheels
# are NOT bundled directly into this frozen exe. They transitively
# require ``numpy>=2.4``, which conflicts with the numpy<2 pins that
# the main ``.venv``'s ``paddleocr 2.7.3``, ``numba``,
# ``opencv-python`` (4.6), ``imgaug`` etc. depend on.
#
# The workaround is a separate ``rockwell_plc_bridge.exe`` sidecar
# built out-of-band from the ``plc_bridge/.venv`` env (numpy 2 +
# the two Rockwell wheels + pyinstaller). The block below copies that
# sidecar's COLLECT dir under ``_internal/rockwell_plc_bridge/`` in
# this build so ``bin/logic_plc_bridge.py::resolve_bridge_exe`` can
# find it at runtime. See ``plc_bridge/README.md`` and
# ``build_scripts/build_all.ps1``.
_plc_bridge_dist = os.path.join(os.getcwd(),
                                'plc_bridge', 'dist',
                                'rockwell_plc_bridge')
if os.path.isdir(_plc_bridge_dist):
    datas += [(_plc_bridge_dist, './rockwell_plc_bridge')]
    print(f"[runme.spec] Bundling PLC sidecar from {_plc_bridge_dist}")
else:
    print(f"[runme.spec] WARNING: PLC sidecar not built at "
          f"{_plc_bridge_dist}; the frozen exe will not include it and "
          "Tools > Build PLC menu items will show an install hint. "
          "Build via plc_bridge/rockwell_plc_bridge.spec first — see "
          "plc_bridge/README.md.")


a = Analysis(
    ['runme.py'],
    pathex=_genai_pathex,
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=['./build_scripts', '. hook_paddle.py', '. hook_paddleocr.py'],
    hooksconfig={},
    runtime_hooks=[],
    # Copyleft transitives of paddleocr that this app never imports. Bundling them
    # would make the distributed exe subject to GPL-3.0 / LGPL / AGPL-3.0 terms.
    # fitz/pymupdf are listed so a stale dev environment cannot smuggle AGPL code
    # back into the artifact after the port to pypdfium2/pikepdf/pypdf/pdfplumber.
    # brotli/brotlicffi are optional urllib3 content-decoders this app never uses;
    # a half-collected brotlicffi imports but lacks `error`, which crashed
    # urllib3.response at import time. Excluding them makes urllib3 set brotli=None.
    excludes=['pdf2docx', 'premailer', 'cssutils', 'tkcalendar',
              'fitz', 'pymupdf', 'pymupdf4llm',
              'brotli', 'brotlicffi', '_brotli'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='runme',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='file_version_info.txt',
    icon=['bin\\logo.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='runme',
)
