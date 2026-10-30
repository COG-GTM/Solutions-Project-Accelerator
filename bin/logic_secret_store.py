# -*- coding: utf-8 -*-
"""
DPAPI-backed secret store for user-supplied credentials.

This module encapsulates persistence of small secrets (a user-supplied OpenAI
API key and the saved ACM SQL Server login password) using the Windows Data
Protection API (DPAPI) via pywin32.

Design constraints:
    * Secrets are encrypted per user + per machine — copying the ciphertext
      file to another Windows account cannot decrypt it.
    * ``pywin32`` is imported lazily inside each function so a missing
      dependency never breaks unrelated modules.
    * All failures on ``load`` degrade to ``None`` and are logged at INFO;
      never raised into UI code.
    * The plaintext key is never written to disk, never logged, and only
      lives in memory for the duration of a save/load call.

Storage location:
    ``<workspace>/temp/openai_key.dat`` and ``<workspace>/temp/sql_password.dat``.
    The paths live alongside ``temp/config.ini`` and are created on first save.

This module intentionally exposes only free functions — there is no state to
share and no reason for a class here.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

DPAPI_DESCRIPTION = "SolutionProjectAccelerator OpenAI API key"
SQL_PASSWORD_DPAPI_DESCRIPTION = "SolutionProjectAccelerator SQL Server password"


def _default_key_path() -> str:
    """Return the default on-disk path for the DPAPI-encrypted OpenAI key blob."""
    return _default_secret_path('openai_key.dat')


def _default_sql_password_path() -> str:
    """Return the default on-disk path for the DPAPI-encrypted SQL password blob."""
    return _default_secret_path('sql_password.dat')


def _default_secret_path(file_name: str) -> str:
    """
    Return ``temp/<file_name>`` under the project root.

    Uses the same ``temp/`` folder that ``logic_config.Config`` targets, so
    the settings-related files sit side by side.
    """
    import __main__
    try:
        base_dir = os.path.dirname(os.path.realpath(__main__.__file__))
    except Exception:
        # __main__ may not have __file__ (e.g., interactive python). Fall
        # back to cwd so callers can still exercise the round-trip.
        base_dir = os.getcwd()
    return os.path.join(base_dir, 'temp', file_name)


def save_openai_key(api_key: str, path: Optional[str] = None) -> None:
    """
    Encrypt ``api_key`` with DPAPI (user + machine scope) and write to ``path``.

    :param api_key: Plaintext API key. Must be a non-empty string.
    :param path: Destination file path. Defaults to ``temp/openai_key.dat``
        under the project root.
    :raises ValueError: If ``api_key`` is empty.
    :raises RuntimeError: If pywin32 / DPAPI is unavailable on this system.
    :raises OSError: If the destination directory cannot be created or the
        file cannot be written.
    """
    if not api_key:
        raise ValueError("api_key must be a non-empty string")
    _save_secret(api_key, path or _default_key_path(), DPAPI_DESCRIPTION,
                 "store API keys")


def load_openai_key(path: Optional[str] = None) -> Optional[str]:
    """
    Decrypt and return the stored OpenAI API key.

    Returns ``None`` if the file is missing, DPAPI decryption fails (e.g.,
    the blob was created by a different user), or pywin32 is not
    installed. Never raises into caller code; failures are logged at INFO.

    :param path: File path to read. Defaults to ``temp/openai_key.dat``.
    :return: The decrypted API key, or ``None`` if unavailable.
    """
    return _load_secret(path or _default_key_path(), "OpenAI key")


def save_sql_password(password: str, path: Optional[str] = None) -> None:
    """
    Encrypt the SQL Server login ``password`` with DPAPI and write to ``path``.

    :param password: Plaintext password. Must be a non-empty string.
    :param path: Destination file path. Defaults to ``temp/sql_password.dat``.
    :raises ValueError: If ``password`` is empty.
    :raises RuntimeError: If pywin32 / DPAPI is unavailable on this system.
    :raises OSError: If the file cannot be written.
    """
    if not password:
        raise ValueError("password must be a non-empty string")
    _save_secret(password, path or _default_sql_password_path(),
                 SQL_PASSWORD_DPAPI_DESCRIPTION, "save SQL Server passwords")


def load_sql_password(path: Optional[str] = None) -> Optional[str]:
    """
    Decrypt and return the saved SQL Server password, or ``None``.

    Never raises into caller code; failures are logged at INFO.
    """
    return _load_secret(path or _default_sql_password_path(), "SQL Server password")


def delete_sql_password(path: Optional[str] = None) -> None:
    """Remove the saved SQL Server password blob, if any."""
    target_path = path or _default_sql_password_path()
    try:
        os.remove(target_path)
    except FileNotFoundError:
        pass
    except OSError as exc:
        logging.warning("Unable to delete stored SQL Server password: %s", exc)


def _save_secret(secret: str, target_path: str, description: str, purpose: str) -> None:
    try:
        import win32crypt  # type: ignore[import]
    except ImportError as exc:  # pragma: no cover — Windows-only guard
        raise RuntimeError(
            "Windows DPAPI unavailable — install pywin32 to %s "
            "securely." % purpose
        ) from exc

    target_dir = os.path.dirname(os.path.abspath(target_path))
    if target_dir and not os.path.isdir(target_dir):
        os.makedirs(target_dir, exist_ok=True)

    plaintext = secret.encode('utf-8')
    # CryptProtectData(DataIn, DataDescr, OptionalEntropy, Reserved,
    #                  PromptStruct, Flags). We pass no entropy so the blob
    # is decryptable by any process running as the same user on this
    # machine; Flags=0 = user scope (default), CRYPTPROTECT_LOCAL_MACHINE
    # is intentionally NOT set so other user accounts cannot decrypt.
    ciphertext = win32crypt.CryptProtectData(
        plaintext,
        description,
        None,
        None,
        None,
        0,
    )

    tmp_path = target_path + '.tmp'
    with open(tmp_path, 'wb') as fh:
        fh.write(ciphertext)
    os.replace(tmp_path, target_path)


def _load_secret(target_path: str, label: str) -> Optional[str]:
    if not os.path.isfile(target_path):
        return None

    try:
        import win32crypt  # type: ignore[import]
    except ImportError:  # pragma: no cover — Windows-only guard
        logging.info(
            "pywin32 not available; cannot load DPAPI-protected %s.", label,
        )
        return None

    try:
        with open(target_path, 'rb') as fh:
            ciphertext = fh.read()
        # CryptUnprotectData returns (description, plaintext_bytes).
        _description, plaintext = win32crypt.CryptUnprotectData(
            ciphertext, None, None, None, 0,
        )
        return plaintext.decode('utf-8')
    except Exception as exc:
        # Wrong user, corrupted file, machine key changed, etc. Never
        # propagate — the app must still boot without the secret.
        logging.info("Unable to decrypt stored %s: %s", label, exc)
        return None


def has_openai_key(path: Optional[str] = None) -> bool:
    """
    Return True iff a decryptable OpenAI key is currently persisted.

    Convenience wrapper around ``load_openai_key`` for UI status labels.
    """
    return load_openai_key(path) is not None
