# Getting started

## Install

The Solutions Project Accelerator ships as a Windows installer
(`solutions_project_accelerator_setup.exe`). Run the installer with
administrator privileges and follow the wizard.

The app drives Application Code Manager, Studio 5000 and FactoryTalk View SE,
which are installed separately — see [Prerequisites](prerequisites.md).

## Launch

From the Start menu, choose **Solutions Project Accelerator**, or double-click
the desktop shortcut if you elected to create one during installation.

## Open your first project

1. On first launch, choose **File → New project**.
2. Point the picker at the folder where you want the project stored.
3. Import your P&ID PDFs, control philosophy documents, and equipment lists via
   **File → Import project** or by dragging them onto the main window.

## Demo files

The release package ships a synthetic sample set so you can follow the whole
training manual without using your own drawings. After installation it lives in
the `demo` folder alongside the application.

| File | Used by |
| --- | --- |
| `DEMO_P&ID.pdf` | Chapters 2–7 — creating a project, scanning control modules, static graphics, display pages and page links, and building HMI displays |
| `DEMO_P&ID.xlsx` | Chapter 6 — exporting project data |
| `Simple Control Philosophy.pdf` | Chapters 8–9 — linking object and subobject parameters |
| `H0001.xml`, `DisplaysImport.txt`, the FactoryTalk View import XMLs | Chapter 7 — importing the generated displays into FactoryTalk View |

None of these contain customer or plant data.

## Before you build HMI displays

Building HMI display pages needs the **PlantPAx 5.0 ACM Library** installed in
Application Code Manager, and the SPA ACM libraries registered with
`acm_library_register.cmd`. See [Prerequisites](prerequisites.md) for the
downloads, the ACM-side setup, and the library settings SPA defaults to.

## Getting help

- **Help → Documentation** opens this local documentation site.
- **Help → Get Help** opens the internal Teams support channel (requires
  network access).
- **Help → About** shows the installed version.
