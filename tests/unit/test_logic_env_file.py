"""``.env`` lookup order and Help-menu URL validation."""

import os
import sys
from pathlib import Path

import pytest

from bin import logic_env_file
from bin.logic_env_file import ENV_FILE_VAR, _candidates, load_env_file, safe_web_url

KEYS = ("SPA_GET_HELP_URL", "GENAI_BASE_URL", "SPA_TEST_INSTALLED")


@pytest.fixture
def clean_env(monkeypatch, tmp_path):
    for key in KEYS + (ENV_FILE_VAR,):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))
    return monkeypatch


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_cwd_env_is_not_a_candidate(clean_env, tmp_path):
    launch = tmp_path / "attacker_folder"
    launch.mkdir()
    clean_env.chdir(launch)
    assert launch / ".env" not in _candidates()


def test_cwd_env_is_ignored_in_frozen_build(clean_env, tmp_path):
    install = tmp_path / "install"
    meipass = install / "_internal"
    _write(install / ".env", "SPA_TEST_INSTALLED=exe\n")
    _write(meipass / ".env.prod", "GENAI_BASE_URL=https://gateway.example.com\n")
    launch = tmp_path / "attacker_folder"
    _write(launch / ".env", "SPA_GET_HELP_URL=\\\\127.0.0.1\\share\\x.exe\nGENAI_BASE_URL=https://evil.example\n")
    clean_env.chdir(launch)
    clean_env.setattr(sys, "frozen", True, raising=False)
    clean_env.setattr(sys, "executable", str(install / "runme.exe"))
    clean_env.setattr(sys, "_MEIPASS", str(meipass), raising=False)

    assert _candidates() == [
        install / ".env",
        meipass / ".env.prod",
        tmp_path / "home" / ".spa" / "spa.env",
    ]
    assert load_env_file() == install / ".env"
    assert "SPA_GET_HELP_URL" not in os.environ
    assert os.environ["GENAI_BASE_URL"] == "https://gateway.example.com"
    assert os.environ["SPA_TEST_INSTALLED"] == "exe"


def test_explicit_env_file_still_wins(clean_env, tmp_path):
    explicit = _write(tmp_path / "chosen.env", "SPA_GET_HELP_URL=https://help.example.com\n")
    _write(tmp_path / "home" / ".spa" / "spa.env", "SPA_GET_HELP_URL=https://other.example.com\n")
    clean_env.setenv(ENV_FILE_VAR, str(explicit))
    clean_env.setattr(logic_env_file, "__file__", str(tmp_path / "repo" / "bin" / "logic_env_file.py"))
    assert _candidates()[0] == explicit
    load_env_file()
    assert os.environ["SPA_GET_HELP_URL"] == "https://help.example.com"


@pytest.mark.parametrize("url", [
    "https://support.example.com/help",
    "http://intranet.example/wiki?a=1#b",
    "  HTTPS://Example.com  ",
])
def test_safe_web_url_accepts_http_and_https(url):
    assert safe_web_url(url) == url.strip()


@pytest.mark.parametrize("url", [
    "",
    None,
    "\\\\127.0.0.1\\share\\x.exe",
    "//127.0.0.1/share/x.exe",
    "file:///C:/Windows/System32/calc.exe",
    "file://127.0.0.1/share/x.exe",
    "C:\\Windows\\System32\\calc.exe",
    "calc.exe",
    "ms-msdt:/id PCWDiagnostic",
    "search-ms:query=x&crumb=location:\\\\evil\\share",
    "javascript:alert(1)",
    "https:\\\\evil.example\\x",
    "https://",
    "https:///path",
    "https://exa mple.com",
    "https://example.com/\nfile:///x",
    "https://[::1",
])
def test_safe_web_url_rejects_everything_else(url):
    assert safe_web_url(url) is None


def test_relative_env_file_var_is_ignored(clean_env, tmp_path):
    launch = tmp_path / "attacker_folder"
    _write(launch / "spa.env", "SPA_GET_HELP_URL=\\\\127.0.0.1\\share\\x.exe\n")
    clean_env.chdir(launch)
    clean_env.setenv(ENV_FILE_VAR, "spa.env")
    clean_env.setattr(logic_env_file, "__file__", str(tmp_path / "repo" / "bin" / "logic_env_file.py"))
    assert all(p.is_absolute() for p in _candidates())
    assert load_env_file() is None
    assert "SPA_GET_HELP_URL" not in os.environ
