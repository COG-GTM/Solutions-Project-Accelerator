"""Summarize licenses from a CycloneDX SBOM and report components still unresolved.

Regenerate the SBOM first (from an env that has the runtime deps installed):

    pip install cyclonedx-bom
    cyclonedx-py environment <path-to-env>\\python.exe --of JSON --sv 1.6 -o sbom.json

Then:

    python build_scripts/license_inventory.py [sbom.json]

Exits non-zero while any dependency is still unresolved. Declared licenses for
packages whose metadata carries no usable SPDX data live in
build_scripts/license_overrides.json.
"""

import json
import os
import re
import sys
from collections import defaultdict

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OVERRIDES_PATH = os.path.join(REPO_ROOT, 'build_scripts', 'license_overrides.json')

COPYLEFT = re.compile(r'\b(A?GPL|LGPL|MPL|EPL|CDDL|OSL)\b', re.IGNORECASE)


def normalize(name):
    return re.sub(r'[-_.]+', '-', name).lower()


def read_requirements(path):
    names = set()
    with open(path, encoding='utf-8') as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith(('#', '-')):
                continue
            names.add(normalize(re.split(r'[=<>!~\[;]', line)[0].strip()))
    return names


def load_overrides():
    if not os.path.exists(OVERRIDES_PATH):
        return {}, {}
    with open(OVERRIDES_PATH, encoding='utf-8') as handle:
        data = json.load(handle)
    overrides = {normalize(k): v for k, v in data.get('overrides', {}).items()}
    annotations = {normalize(k): v for k, v in data.get('annotations', {}).items()}
    return overrides, annotations


def is_copyleft(licence):
    return bool(COPYLEFT.search(licence))


def resolve_license(component):
    """Return an SPDX-ish identifier, or None when the metadata is unusable."""
    for entry in component.get('licenses', []):
        if 'expression' in entry:
            return entry['expression']
        lic = entry.get('license', {})
        if lic.get('id'):
            return lic['id']
        name = lic.get('name')
        # Some projects dump the whole license text into the name field.
        if name and len(name) <= 120 and '\n' not in name:
            return name
    return None


def main():
    sbom_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO_ROOT, 'sbom.json')
    with open(sbom_path, encoding='utf-8') as handle:
        sbom = json.load(handle)

    required = read_requirements(os.path.join(REPO_ROOT, 'requirements.txt'))
    overrides, annotations = load_overrides()

    by_license = defaultdict(list)
    unresolved = []
    overridden = []
    copyleft = []

    for component in sbom.get('components', []):
        name = component.get('name', '')
        key = normalize(name)
        if key not in required:
            continue
        version = component.get('version', '?')
        label = f'{name}=={version}'

        licence = resolve_license(component)
        if licence is None and key in overrides:
            licence = overrides[key].get('license')
            if licence:
                overridden.append((label, licence))
        if licence is None:
            unresolved.append(label)
            continue

        by_license[licence].append(label)
        if is_copyleft(licence):
            copyleft.append((label, licence))

    total = sum(len(v) for v in by_license.values()) + len(unresolved)
    print(f'SBOM: {sbom_path}')
    print(f'Direct requirements resolved from environment metadata: {total}\n')

    print('License breakdown')
    print('-' * 60)
    for licence, pkgs in sorted(by_license.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        print(f'{len(pkgs):4d}  {licence}')
        print('      ' + ', '.join(sorted(pkgs)))

    if overridden:
        print('\nResolved via build_scripts/license_overrides.json')
        print('-' * 60)
        for label, licence in sorted(overridden):
            print(f'  {label:<28} {licence}')

    if copyleft:
        print('\nCopyleft obligations (review before distributing a binary)')
        print('-' * 60)
        for label, licence in sorted(copyleft):
            print(f'  {label:<28} {licence}')

    noted = sorted(k for k in annotations if k in {normalize(c.get('name', '')) for c in sbom.get('components', [])})
    if noted:
        print('\nAnnotations (auto-resolved id is misleading)')
        print('-' * 60)
        for key in noted:
            print(f'  {key}: {annotations[key]}')

    print('\nStill unresolved (NOASSERTION, needs manual review)')
    print('-' * 60)
    if unresolved:
        for label in sorted(unresolved):
            print(f'  {label}')
    else:
        print('  none')

    missing = required - {normalize(c.get('name', '')) for c in sbom.get('components', [])}
    if missing:
        print('\nIn requirements.txt but absent from the SBOM environment')
        print('-' * 60)
        for name in sorted(missing):
            print(f'  {name}')

    return 1 if unresolved else 0


if __name__ == '__main__':
    sys.exit(main())
