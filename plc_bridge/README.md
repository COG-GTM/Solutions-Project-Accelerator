# rockwell_plc_bridge — Rockwell PLC SDK sidecar

Standalone console exe that isolates the numpy-2 requirement of the
Rockwell `logix_designer_sdk` and `ftecho_sdk` wheels from the main
Solutions Project Accelerator app (which pins numpy < 2 via
paddleocr 2.7.3, imgaug, numba, etc.).

The main app invokes this exe as a subprocess (see
`bin/logic_plc_bridge.py`) and streams JSON-line events on stdout for
progress reporting.

## Build env (one-time)

The fastest path is the one-shot dev setup script. It creates the
virtualenv, installs the wheels, builds the exe, and smoke-tests it:

```powershell
powershell -ExecutionPolicy Bypass -File build_scripts/setup_plc_bridge_dev.ps1
```

Rerun any time to refresh wheels; add `-Force` to nuke and recreate the
env from scratch. `-SkipBuild` provisions the env only. `-SkipSmokeTest`
skips the final `--version` handshake check.

Manual equivalent, if you prefer step-by-step:

```powershell
py -3.12 -m venv plc_bridge\.venv
.\plc_bridge\.venv\Scripts\Activate.ps1
pip install numpy pyinstaller
pip install "C:\Users\Public\Documents\Studio 5000\Logix Designer SDK\python\logix_designer_sdk-2.0.2-py3-none-any.whl"
pip install "C:\Users\Public\Documents\FactoryTalk Logix Echo\SDK\Python\ftecho_sdk-4.0.0-py3-none-any.whl"
```

## Build

```powershell
.\plc_bridge\.venv\Scripts\Activate.ps1
cd plc_bridge
pyinstaller rockwell_plc_bridge.spec --distpath dist
```

Output: `plc_bridge/dist/rockwell_plc_bridge/rockwell_plc_bridge.exe`.

`runme.spec` picks up that folder automatically and bundles it under
`_internal/rockwell_plc_bridge/` in the main app's COLLECT dir.

## CLI

```
rockwell_plc_bridge.exe --version
rockwell_plc_bridge.exe probe --sdk {designer,echo}
rockwell_plc_bridge.exe designer convert-l5x-to-acd
       --l5x-path <path> --acd-path <path>
rockwell_plc_bridge.exe echo push-acd
       --acd-path <path>
       [--chassis-name <name>]
       [--ip1 <addr> --m1 <mask>]
       [--ip2 <addr> --m2 <mask>]
```

All subcommands emit JSON-line events on stdout. The final line is
`{"event":"result",...}` on success or `{"event":"error",...}` on
failure (and the process exits nonzero).
