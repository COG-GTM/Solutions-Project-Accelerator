"""Shared pytest fixtures and global safety guards.

Two guards are autouse because the app is a desktop GUI:
  * network access is blocked, so no test can reach Ollama/Azure/HTTP endpoints;
  * tkinter message boxes are stubbed, because many logic functions are wrapped in
    ``@handle_exception_with_messagebox()`` which would otherwise open a modal
    dialog and hang a headless run.
"""

import socket
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture(autouse=True)
def _block_network(monkeypatch):
    def _blocked(*args, **kwargs):
        raise RuntimeError("Network access is disabled in the test suite")

    monkeypatch.setattr(socket.socket, "connect", _blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)


@pytest.fixture(autouse=True)
def captured_dialogs(monkeypatch):
    """Swallow Tk dialogs and record them so tests can assert on error paths."""
    from tkinter import messagebox

    recorded = {"error": [], "info": [], "warning": [], "ask": []}

    monkeypatch.setattr(messagebox, "showerror", lambda *a, **k: recorded["error"].append((a, k)))
    monkeypatch.setattr(messagebox, "showinfo", lambda *a, **k: recorded["info"].append((a, k)))
    monkeypatch.setattr(messagebox, "showwarning", lambda *a, **k: recorded["warning"].append((a, k)))
    monkeypatch.setattr(messagebox, "askyesno", lambda *a, **k: (recorded["ask"].append((a, k)), False)[1])
    return recorded


@pytest.fixture(autouse=True)
def _block_subprocess_by_default(monkeypatch, request):
    """Ollama and the PLC sidecar are invoked via subprocess; keep tests offline."""
    if request.node.get_closest_marker("allow_subprocess"):
        return
    import subprocess

    def _blocked(*args, **kwargs):
        raise RuntimeError(f"subprocess call blocked in tests: {args[:1]}")

    monkeypatch.setattr(subprocess, "run", _blocked)
    monkeypatch.setattr(subprocess, "Popen", _blocked)
    monkeypatch.setattr(subprocess, "check_output", _blocked)


@pytest.fixture
def tmp_project_root(tmp_path, monkeypatch):
    """Project_File_Manager and Database build every path from './projects/' relative to CWD."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "projects").mkdir(exist_ok=True)
    return tmp_path


@pytest.fixture
def tmp_config_home(tmp_path, monkeypatch):
    """Config() resolves config.ini from the directory of __main__.__file__."""
    import __main__

    entry_point = tmp_path / "runme.py"
    entry_point.write_text("")
    monkeypatch.setattr(__main__, "__file__", str(entry_point), raising=False)
    (tmp_path / "temp").mkdir(exist_ok=True)
    return tmp_path
