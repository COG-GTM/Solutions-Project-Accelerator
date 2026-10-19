""" Discovery of FactoryTalk View SE applications installed on the local
    machine.

    Populates the picker dialog used by "Build HMI → View Designer" so the
    user can select the target application for SEAddComponent.exe instead
    of having it silently derived from the SPA project name.

    Three sources are consulted and merged (dedup by application name,
    case-insensitive):

      1. **Local / Standalone** projects on disk
         ``C:\\Users\\Public\\Documents\\RSView Enterprise\\SE\\HMI Projects\\<App>\\<App>.sed``

      2. **Network Distributed** projects served by this node
         ``C:\\ProgramData\\Rockwell\\RNAServer\\Global\\RnaStore\\<App>\\``

      3. **FactoryTalk View Studio MRU** (Recent Applications registry key)
         which distinguishes ``Global`` (Distributed), ``Local``
         (Stand-alone) and ``SEStation`` sub-lists per Studio version GUID.

    Cross-platform-safe: on non-Windows the module still imports and
    ``discover_ftview_applications()`` returns ``[]``.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import List, Dict


# Public constants — reused by the picker and the settings dialog so the
# labels stay consistent across the UI.
APP_TYPE_DISTRIBUTED = 'Distributed'
APP_TYPE_STAND_ALONE = 'Stand-alone'
APP_TYPE_SE_STATION = 'SE Station'


# Filesystem roots for SE applications. These paths are the Rockwell
# defaults verified against a real FTView SE 13 install; they are the
# only locations SEAddComponent.exe can target directly.
_SE_LOCAL_PROJECTS_ROOT = r"C:\Users\Public\Documents\RSView Enterprise\SE\HMI Projects"
_SE_RNA_STORE_ROOT = r"C:\ProgramData\Rockwell\RNAServer\Global\RnaStore"

# Registry sub-key names (under FactoryTalk View Studio → Recent
# Applications → <GUID>) → SEAddComponent application-type label.
_MRU_SUBKEYS = {
    'Global': APP_TYPE_DISTRIBUTED,
    'Local': APP_TYPE_STAND_ALONE,
    'SEStation': APP_TYPE_SE_STATION,
}

# HKCU parent path for the MRU.
_MRU_HKCU_PATH = r"Software\Rockwell Software\FactoryTalk View Studio\Recent Applications"


def _is_windows() -> bool:
    return sys.platform.startswith('win')


def _scan_local_projects() -> List[Dict[str, str]]:
    """ Return standalone SE applications that have a ``<App>.sed`` file in
        the standard Public Documents HMI Projects folder. """
    apps: List[Dict[str, str]] = []
    if not os.path.isdir(_SE_LOCAL_PROJECTS_ROOT):
        return apps
    try:
        entries = os.listdir(_SE_LOCAL_PROJECTS_ROOT)
    except OSError as exc:
        logging.debug(f"FTView discovery: cannot list local projects root: {exc}")
        return apps
    for name in entries:
        folder = os.path.join(_SE_LOCAL_PROJECTS_ROOT, name)
        sed_file = os.path.join(folder, f"{name}.sed")
        if os.path.isdir(folder) and os.path.isfile(sed_file):
            apps.append({
                'name': name,
                'app_type': APP_TYPE_STAND_ALONE,
                'source': f'{_SE_LOCAL_PROJECTS_ROOT}\\{name}',
            })
    return apps


def _scan_rna_store() -> List[Dict[str, str]]:
    """ Return network-distributed SE applications served by this node's
        RNA store. Skips FT Directory system folders (``$System`` etc.). """
    apps: List[Dict[str, str]] = []
    if not os.path.isdir(_SE_RNA_STORE_ROOT):
        return apps
    try:
        entries = os.listdir(_SE_RNA_STORE_ROOT)
    except OSError as exc:
        logging.debug(f"FTView discovery: cannot list RnaStore: {exc}")
        return apps
    for name in entries:
        if name.startswith('$'):
            continue
        folder = os.path.join(_SE_RNA_STORE_ROOT, name)
        if not os.path.isdir(folder):
            continue
        apps.append({
            'name': name,
            'app_type': APP_TYPE_DISTRIBUTED,
            'source': f'{_SE_RNA_STORE_ROOT}\\{name}',
        })
    return apps


def _scan_mru_registry() -> List[Dict[str, str]]:
    """ Return applications listed in HKCU ``Recent Applications`` for
        FactoryTalk View Studio, spanning all installed Studio version
        GUIDs. Silently returns ``[]`` when the key is absent (Studio not
        installed, or the user has never opened an app). """
    if not _is_windows():
        return []
    try:
        import winreg
    except ImportError:
        return []
    apps: List[Dict[str, str]] = []
    try:
        parent = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _MRU_HKCU_PATH)
    except OSError:
        return apps
    try:
        guid_index = 0
        while True:
            try:
                guid = winreg.EnumKey(parent, guid_index)
            except OSError:
                break
            guid_index += 1
            for sub_name, app_type in _MRU_SUBKEYS.items():
                try:
                    sub_key = winreg.OpenKey(parent, f"{guid}\\{sub_name}")
                except OSError:
                    continue
                try:
                    value_index = 0
                    while True:
                        try:
                            _, value, _ = winreg.EnumValue(sub_key, value_index)
                        except OSError:
                            break
                        value_index += 1
                        if isinstance(value, str) and value.strip():
                            apps.append({
                                'name': value.strip(),
                                'app_type': app_type,
                                'source': f'MRU: {sub_name}',
                            })
                finally:
                    sub_key.Close()
    finally:
        parent.Close()
    return apps


def discover_ftview_applications() -> List[Dict[str, str]]:
    """ Return all discoverable FactoryTalk View SE applications on this
        machine as a sorted list of ``{'name', 'app_type', 'source'}``
        dicts. The first observation wins on collisions — filesystem
        entries take precedence over registry MRU entries so the reported
        source is the concrete on-disk path when available.

        Never raises: on any environmental failure returns whatever was
        collected up to that point (possibly ``[]``). """
    if not _is_windows():
        return []

    seen_lower: Dict[str, Dict[str, str]] = {}

    def _merge(records: List[Dict[str, str]]) -> None:
        for rec in records:
            key = rec['name'].lower()
            if key not in seen_lower:
                seen_lower[key] = rec

    # Order matters: on-disk scans first so their source paths beat MRU.
    try:
        _merge(_scan_local_projects())
    except Exception as exc:
        logging.exception(f"FTView discovery: local scan failed: {exc}")
    try:
        _merge(_scan_rna_store())
    except Exception as exc:
        logging.exception(f"FTView discovery: RnaStore scan failed: {exc}")
    try:
        _merge(_scan_mru_registry())
    except Exception as exc:
        logging.exception(f"FTView discovery: MRU scan failed: {exc}")

    return sorted(seen_lower.values(), key=lambda r: r['name'].lower())


if __name__ == '__main__':  # pragma: no cover - manual smoke test
    logging.basicConfig(level=logging.INFO)
    for row in discover_ftview_applications():
        print(f"  {row['name']:<40} {row['app_type']:<14} {row['source']}")
