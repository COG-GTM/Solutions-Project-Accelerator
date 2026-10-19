# Prerequisites

Solutions Project Accelerator (SPA) does not work on its own. It drives
Rockwell Automation engineering tools to create the control modules, displays
and graphics it generates, so those tools must already be installed and
licensed on the same workstation.

!!! warning "SPA does not install any of these"
    None of the products below ship inside the SPA installer. Download them
    from the Rockwell Automation
    [Product Compatibility and Download Centre](https://compatibility.rockwellautomation.com/)
    (PCDC) and install them before running SPA.

## At a glance

| Software | Minimum version | Required for | Supplied by |
| --- | --- | --- | --- |
| Application Code Manager (ACM) | 5.00+ | Everything: SPA stores all objects, parameters and displays in the ACM database | PCDC |
| Microsoft SQL Server | The instance your ACM installation uses | ACM's database back end | Your ACM installation |
| Studio 5000 Logix Designer | v35+ | Opening and verifying the generated PLC code | PCDC |
| FactoryTalk View SE | 14+ | Importing the generated HMI displays and graphics | PCDC |
| PlantPAx 5.0 ACM Library (Library of Process Objects) | 5.0+ | Building HMI display pages | PCDC |
| SPA ACM libraries (Image, PageLink, ProcessLine) | 1.8 / 1.5 / 1.6 | Static graphics, page links and process lines | Ships with SPA |
| Studio 5000 Logix Designer SDK | 2.0.2 | *Optional*: the PLC bridge (L5X to ACD conversion) | Studio 5000 SDK installer |
| FactoryTalk Logix Echo SDK | 4.0.0 | *Optional*: downloading the generated code to an emulated controller | Logix Echo installer |

## Application Code Manager 5.00

ACM is the central requirement: SPA reads and writes the ACM SQL database
directly and calls `ACMConsole.exe` to generate code and displays.

- Default install location:
  `C:\Program Files\Rockwell Automation\Application Code Manager`
- Console used by SPA:
  `C:\Program Files\Rockwell Automation\Application Code Manager\ACMConsole\ACMConsole.exe`
- Database: the Microsoft SQL Server instance configured during the ACM
  install. SPA connects with either Windows or SQL Server authentication — you
  pick the server, authentication mode and database the first time you open a
  project.

!!! note "ACM 5.00 is not the same as `(RA-LIB) Process 5`"
    `5.00` is the Application Code Manager product version. `(RA-LIB) Process 5`
    is the name of the Rockwell *library* that ships for use inside ACM, and it
    is what all of SPA's default settings point at. Seeing both numbers is
    expected.

## Studio 5000 Logix Designer v35

Needed to open, verify and download the PLC code that ACM generates from the
SPA project. v35 matches SPA's default **PLC firmware revision** (see
[Basic library settings](#basic-library-settings)); if you standardise on a
different revision, change it in **Settings → PLC Code** so the controller ACM
creates matches your Studio 5000 version.

## FactoryTalk View SE 14

The generated displays are imported into a FactoryTalk View SE application.
SPA can target **Distributed**, **Stand-alone** and **SE Station**
applications.

SPA can optionally push components straight into an SE application using the
FactoryTalk View SE Add Component tool, installed with FactoryTalk View at:

```text
C:\Program Files (x86)\Rockwell Software\RSView Enterprise\SEAddComponent.exe
```

The path, application type and target area are set in **Settings → HMI
Displays → FactoryTalk View SE Add Component Tool**.

!!! info "Display template version"
    The Process 5 display template SPA defaults to is the FactoryTalk View SE
    **12.0** template
    (`(RA-TPL)_Process_5_HMI_Display_FTViewSE_12.0_(1.0).xml`), which is the
    template shipped with the PlantPAx 5.0 library. It imports into FactoryTalk
    View SE 14 without change. If your library supplies a newer template,
    select it in **Settings → HMI Displays → HMI Display Settings**.

## PlantPAx 5.0 ACM Library

Building HMI display pages needs the **PlantPAx 5.0 ACM Library** installed in
ACM. It provides the process object types, HMI display library and display
templates SPA builds against.

1. Go to the
   [Product Compatibility and Download Centre](https://compatibility.rockwellautomation.com/).
2. Search for **PlantPAx Library of Process Objects**.
3. Take the **Application Code Manager libraries** download.
4. Run the library's own registration script to install it into ACM.

## SPA ACM libraries

Three SPA-specific ACM libraries are installed with the application, under
`acm_libraries\ApplicationCodeManagerLibraries` in the installation folder:

| Library | Version | Used for |
| --- | --- | --- |
| `(SPA) Solutions Project Accelerator … Image` | 1.8 | Static graphics extracted from P&IDs |
| `(SPA) Solutions Project Accelerator … PageLink` | 1.5 | Navigation links between display pages |
| `(SPA) Solutions Project Accelerator … ProcessLine` | 1.6 | Pipeline connections drawn between objects |

Register them by running `acm_library_register.cmd` from the `acm_libraries`
folder. The script copies the `.HSL4` files to
`…\Documents\Libraries\Application Code Manager\` and registers them through
`ACMConsole.exe`, so ACM must already be installed when you run it.

## Optional: PLC bridge SDKs

These are only needed for the PLC bridge features (converting L5X to ACD and
downloading to an emulated controller). SPA runs without them; the features
report an install hint if the SDK is missing.

| SDK | Version | Default wheel location |
| --- | --- | --- |
| Studio 5000 Logix Designer SDK | 2.0.2 | `C:\Users\Public\Documents\Studio 5000\Logix Designer SDK\python\` |
| FactoryTalk Logix Echo SDK | 4.0.0 | `C:\Users\Public\Documents\FactoryTalk Logix Echo\SDK\Python\` |

Both paths can be changed in **Settings → PLC Code → Rockwell SDK Locations**.

## Basic library settings

SPA ships with defaults that match a standard PlantPAx 5.0 installation. Check
them in **Tools → Settings** before you create your first project — if your
site uses different libraries or versions, change them here first, because ACM
objects are created against whatever is selected.

### Settings → HMI Displays

| Setting | Default |
| --- | --- |
| Library used when creating a HMI Server | `(RA-LIB) Process 5 Version 5.10` |
| Display template used when creating HMI displays | `(RA-TPL)_Process_5_HMI_Display_FTViewSE_12.0_(1.0).xml` |
| Display Width Pixels | 1920 |
| Display Height Pixels | 1080 |
| Display Color | `E0E0E0` |
| Material Line Width / Color | 2 / `AAAAAA` |
| Signal Line Width / Color | 1 / `0B84FD`, **Use dash-dot** ticked |
| Library used when creating a Alarm Server | `(RA-LIB) Process 5 Version 1.1` |

The HMI server list shows ACM libraries of type `HMI` in the `Display`
category; the alarm server list shows type `HMI` in the `FTAE` category. If
either dropdown is empty, the PlantPAx library has not been registered in ACM.

### Settings → PLC Code

| Setting | Default |
| --- | --- |
| Library used when creating a Project | `(RA-LIB) Process 5 Version 2.0` |
| Library used when creating a Controller | `(RA-LIB) Process 5 Process_Controller Version 4.1` |
| Program used when creating Objects | `Unscheduled` |
| Task used when creating Objects | `Unscheduled_Routines` |
| PLC firmware revision (20–99) | 35 |

### Settings → Static Graphics

| Setting | Default |
| --- | --- |
| Default Extract Fill Color | `CCCCCC` |
| Default Extract Stroke Color | `AAAAAA` |
| Default Extract Stroke Width | 2 |

## ACM-side setup

Before SPA can build display pages, ACM itself needs an HMI server configured:

1. Register the SPA libraries with `acm_library_register.cmd`.
2. Install the PlantPAx 5.0 ACM Library.
3. In the ACM **System View**, right-click **Displays** and select **Add**.
4. Choose **Process 5 HMI** and click **Next**.
5. Name the HMI server and select the Process 5 display template from the
   drop-down, then click **Finish**.

The full walkthrough, with screenshots, is in
[How to build HMI display pages](training-manual/08-how-to-build-hmi-display-pages.md).

## Recommended install order

1. Microsoft SQL Server (or confirm the instance ACM will use).
2. Application Code Manager 5.00.
3. PlantPAx 5.0 ACM Library, registered into ACM.
4. Studio 5000 Logix Designer v35.
5. FactoryTalk View SE 14.
6. Solutions Project Accelerator.
7. `acm_library_register.cmd` to register the SPA ACM libraries.
8. Review **Tools → Settings** against
   [Basic library settings](#basic-library-settings).
