# Third-party notices

This product is distributed under the MIT License (see `LICENSE`). It also
redistributes the independent third-party programs listed below.

## Programs invoked as separate processes

These are complete, unmodified upstream programs. They are executed as separate
processes via `subprocess` and are never linked into this application. They keep
their own licences, which do not extend to this project's source code.

### anymd 8.5.1

- Licence: MIT
- Copyright: Sylphx
- Upstream: <https://github.com/SylphxAI/anymd>
- Used by: `bin/logic_pdf_markdown.py` to convert PDF pages to Markdown

### Potrace 1.16

- Licence: GNU General Public License, version 2 or later
- Copyright: Peter Selinger
- Upstream: <https://potrace.sourceforge.net/>
- Source archive: <https://potrace.sourceforge.net/download/1.16/potrace-1.16.tar.gz>
- Used by: `bin/logic_tools.py` for raster-to-SVG vectorisation

### Poppler 26.09.0 (`pdftocairo`)

- Licence: GNU General Public License, version 2 or later
- Copyright: The Poppler Developers; Glyph & Cog, LLC
- Upstream: <https://poppler.freedesktop.org/>
- Windows build redistributed: <https://github.com/oschwartz10612/poppler-windows>
- Source archive: <https://poppler.freedesktop.org/poppler-26.09.0.tar.xz>
- Used by: `bin/logic_pdf_to_svg.py` to render PDF pages to SVG

### Written offer for corresponding source

For a period of three years from the date you received this software, we will
provide, on request, a complete machine-readable copy of the corresponding
source code for the GPL-licensed programs above (Potrace and Poppler), on a
medium customarily used for software interchange, for no more than the cost of
performing the distribution. Direct requests to the contact address in
`SECURITY.md`.

The exact upstream artifacts and their pinned SHA-256 checksums are recorded in
`build_scripts/setup_vendor_deps.ps1`.

## Libraries under weak copyleft

### CairoSVG

- Licence: GNU Lesser General Public License, version 3 or later
- Upstream: <https://cairosvg.org/>

CairoSVG is installed as a separate, unmodified pip package. Recipients may
replace it with a modified version by installing a different build of the
`cairosvg` package, as required by LGPL section 4.

### certifi, pikepdf, tqdm

- Licence: Mozilla Public License 2.0 (file-level copyleft)

All are redistributed unmodified.

## Build-time only

### PyInstaller

- Licence: GNU General Public License, version 2 or later, **with an exception**
  permitting the use of PyInstaller to build and distribute non-free programs
- Upstream: <https://pyinstaller.org/>

PyInstaller is a build tool. Its bootloader exception expressly allows the
resulting executable to be distributed under this project's own licence.

## Full dependency inventory

A machine-generated licence inventory for every Python dependency is produced by
`build_scripts/license_inventory.py` from a CycloneDX SBOM. Declared licences for
packages whose published metadata is not SPDX-resolvable, together with the
evidence each was derived from, are recorded in
`build_scripts/license_overrides.json`.
