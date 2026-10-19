"""Packaging regression guard for the PyInstaller output in dist/runme.

Packaging omissions (a vendored engine or model folder silently dropped from
runme.spec) are the most common way a release breaks while the source tree is
fine, and nothing else in the suite catches them.

Every test here is skipped unless a build already exists, so the default
``pytest -m "not slow"`` run stays fast. Build first with:
    powershell -ExecutionPolicy Bypass -File build_scripts/build_all.ps1
"""

import subprocess
from pathlib import Path

import pytest

pytestmark = [pytest.mark.slow, pytest.mark.packaging]

REPO_ROOT = Path(__file__).resolve().parents[2]
DIST = REPO_ROOT / "dist" / "runme"
INTERNAL = DIST / "_internal"

requires_build = pytest.mark.skipif(
    not (DIST / "runme.exe").is_file(),
    reason="no frozen build in dist/runme — run build_scripts/build_all.ps1 first",
)


@requires_build
def test_main_executable_exists():
    assert (DIST / "runme.exe").is_file()


@requires_build
def test_main_executable_is_not_a_stub():
    # A truncated/failed PyInstaller run can still leave a small exe behind.
    assert (DIST / "runme.exe").stat().st_size > 1_000_000


@requires_build
@pytest.mark.parametrize("folder", [
    "Paddle-OCR",
    "SAM2.1",
    "Potrace",
    "cairosvg",
])
def test_vendored_engine_folders_are_bundled(folder):
    """These are listed in runme.spec `datas` and are loaded at runtime by path."""
    assert (INTERNAL / folder).is_dir(), f"{folder} missing from the frozen build"


@requires_build
@pytest.mark.parametrize("relative_path", [
    "bin/logo.ico",
    "cairosvg/VERSION",
    "TaskbarLib.tlb",
])
def test_individual_data_files_are_bundled(relative_path):
    assert (INTERNAL / relative_path).is_file(), f"{relative_path} missing from the frozen build"


class TestPlcBridgeSidecar:
    SIDECAR = INTERNAL / "rockwell_plc_bridge" / "rockwell_plc_bridge.exe"

    requires_sidecar = pytest.mark.skipif(
        not SIDECAR.is_file(),
        reason="plc_bridge sidecar not present in dist/runme/_internal",
    )

    @requires_build
    @requires_sidecar
    def test_sidecar_executable_is_embedded(self):
        assert self.SIDECAR.is_file()

    @requires_build
    @requires_sidecar
    @pytest.mark.allow_subprocess
    def test_sidecar_reports_its_version(self):
        # Mirrors the smoke check in build_scripts/setup_plc_bridge_dev.ps1.
        result = subprocess.run(
            [str(self.SIDECAR), "--version"],
            capture_output=True, text=True, timeout=120,
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip()


@requires_build
def test_spec_declared_top_level_datas_all_landed():
    """Cross-check the literal `datas` entries in runme.spec against dist/.

    Only the repo-relative entries are checked; site-packages and
    collect_all()-generated entries are PyInstaller's responsibility.
    """
    spec_text = (REPO_ROOT / "runme.spec").read_text(encoding="utf-8")

    import ast
    import re

    match = re.search(r"^datas = (\[.*?\])$", spec_text, re.MULTILINE | re.DOTALL)
    assert match, "could not locate the literal `datas` list in runme.spec"

    entries = ast.literal_eval(match.group(1))
    missing = []
    for source, target in entries:
        if source.startswith(("./", "..")) or not Path(source).is_absolute():
            expected = INTERNAL / target.lstrip("./") / Path(source).name
            folder = INTERNAL / target.lstrip("./")
            if not expected.exists() and not folder.exists():
                missing.append(f"{source} -> {target}")

    assert not missing, f"declared in runme.spec but absent from dist/: {missing}"
