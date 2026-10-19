# -*- coding: utf-8 -*-
"""
DPAPI-backed secret store for user-supplied credentials.

This module encapsulates persistence of small secrets (e.g., a user-supplied
OpenAI API key) using the Windows Data Protection API (DPAPI) via pywin32.

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
    ``<workspace>/temp/openai_key.dat``. The path lives alongside
    ``temp/config.ini`` and is created on first save.

This module intentionally exposes only free functions — there is no state to
share and no reason for a class here.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

DPAPI_DESCRIPTION = "SolutionProjectAccelerator OpenAI API key"


def _default_key_path() -> str:
    """
    Return the default on-disk path for the DPAPI-encrypted OpenAI key blob.

    Uses the same ``temp/`` folder that ``logic_config.Config`` targets, so
    the two settings-related files sit side by side.
    """
    import __main__
    try:
        base_dir = os.path.dirname(os.path.realpath(__main__.__file__))
    except Exception:
        # __main__ may not have __file__ (e.g., interactive python). Fall
        # back to cwd so callers can still exercise the round-trip.
        base_dir = os.getcwd()
    return os.path.join(base_dir, 'temp', 'openai_key.dat')


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

    try:
        import win32crypt  # type: ignore[import]
    except ImportError as exc:  # pragma: no cover — Windows-only guard
        raise RuntimeError(
            "Windows DPAPI unavailable — install pywin32 to store API keys "
            "securely."
        ) from exc

    target_path = path or _default_key_path()
    target_dir = os.path.dirname(os.path.abspath(target_path))
    if target_dir and not os.path.isdir(target_dir):
        os.makedirs(target_dir, exist_ok=True)

    plaintext = api_key.encode('utf-8')
    # CryptProtectData(DataIn, DataDescr, OptionalEntropy, Reserved,
    #                  PromptStruct, Flags). We pass no entropy so the blob
    # is decryptable by any process running as the same user on this
    # machine; Flags=0 = user scope (default), CRYPTPROTECT_LOCAL_MACHINE
    # is intentionally NOT set so other user accounts cannot decrypt.
    ciphertext = win32crypt.CryptProtectData(
        plaintext,
        DPAPI_DESCRIPTION,
        None,
        None,
        None,
        0,
    )

    tmp_path = target_path + '.tmp'
    with open(tmp_path, 'wb') as fh:
        fh.write(ciphertext)
    os.replace(tmp_path, target_path)


def load_openai_key(path: Optional[str] = None) -> Optional[str]:
    """
    Decrypt and return the stored OpenAI API key.

    Returns ``None`` if the file is missing, DPAPI decryption fails (e.g.,
    the blob was created by a different user), or pywin32 is not
    installed. Never raises into caller code; failures are logged at INFO.

    :param path: File path to read. Defaults to ``temp/openai_key.dat``.
    :return: The decrypted API key, or ``None`` if unavailable.
    """
    target_path = path or _default_key_path()
    if not os.path.isfile(target_path):
        return None

    try:
        import win32crypt  # type: ignore[import]
    except ImportError:  # pragma: no cover — Windows-only guard
        logging.info(
            "pywin32 not available; cannot load DPAPI-protected OpenAI key.",
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
        # propagate — the app must still boot without the key.
        logging.info("Unable to decrypt stored OpenAI key: %s", exc)
        return None


def has_openai_key(path: Optional[str] = None) -> bool:
    """
    Return True iff a decryptable OpenAI key is currently persisted.

    Convenience wrapper around ``load_openai_key`` for UI status labels.
    """
    return load_openai_key(path) is not None
