# Prerequisites


Solutions Project Accelerator (SPA) drives Rockwell Automation engineering tools to create control modules, displays, and graphics. These tools must be installed and licensed on the same workstation before SPA can use them.

**Important:** SPA does not install the products listed in this section. Download the required products from the Rockwell Automation [<u>Product Compatibility and Download Centre</u>](https://compatibility.rockwellautomation.com/) (PCDC) and install them before running SPA.

## Software Requirements at a Glance

| **Software** | **Version used** | **Required for** | **Supplied by** |
|----|:--:|----|----|
| Application Code Manager (ACM) | 5.00 | All SPA functions because SPA stores objects, parameters, and displays in the ACM database | PCDC |
| Microsoft SQL Server | ACM instance | ACM database back end | ACM installation |
| Studio 5000 Logix Designer | v35 | Opening and verifying generated PLC code | PCDC |
| FactoryTalk View SE | 14 | Importing generated HMI displays and graphics | PCDC |
| PlantPAx ACM Library | 5.0 | Building HMI display pages | PCDC |
| SPA ACM libraries | 1.8 / 1.5 / 1.6 | Static graphics, page links, and process lines | SPA installer |
| Studio 5000 Logix Designer SDK | 2.0.2 | Optional PLC bridge for L5X to ACD conversion | Studio 5000 SDK installer |
| FactoryTalk Logix Echo SDK | 4.0.0 | Optional download to an emulated controller | Logix Echo installer |

## Application Code Manager Version 5

ACM is the central requirement. SPA reads and writes the ACM SQL database directly and calls ACMConsole.exe to generate code and displays.

**Default install location:** C:\Program Files\Rockwell Automation\Application Code Manager

**Console used by SPA:** C:\Program Files\Rockwell Automation\Application Code Manager\ACMConsole\ACMConsole.exe

**Database:** Use the Microsoft SQL Server instance configured during the ACM installation. SPA supports Windows or SQL Server authentication. Select the server, authentication mode, and database when you first open a project.

**Version note:** ACM 5.00 is not the same as (RA-LIB) Process 5. ACM 5.00 is the Application Code Manager product version. (RA-LIB) Process 5 is the Rockwell library used inside ACM and is the basis for SPA's default settings.

## Studio 5000 Logix Designer v35

Use Studio 5000 Logix Designer to open, verify, and download the PLC code that ACM generates from the SPA project. Version 35 matches SPA's default PLC firmware revision. If your site uses a different revision, change it under **Tools \> Settings \> PLC Code** so the controller ACM creates matches your Studio 5000 version.

## FactoryTalk View SE 14

Import the generated displays into a FactoryTalk View SE application. SPA can target **Distributed**, **Stand-alone**, and **SE Station** applications.

SPA can optionally push components directly into an SE application using the FactoryTalk View SE Add Component tool, which FactoryTalk View installs at C:\Program Files (x86)\Rockwell Software\RSView Enterprise\SEAddComponent.exe.

Set the path, application type, and target area under **Tools \> Settings \> HMI Displays \> FactoryTalk View SE Add Component Tool**.

**Display template version:** SPA defaults to the FactoryTalk View SE 12.0 Process 5 display template (RA-TPL)\_Process_5_HMI_Display_FTViewSE_12.0\_(1.0).xml. This template ships with the PlantPAx 5.0 library and imports into FactoryTalk View SE 14 without changes. If your library supplies a newer template, select it under **Tools \> Settings \> HMI Displays \> HMI Display Settings**.

## PlantPAx Version 5 ACM Library

The PlantPAx 5.0 ACM Library must be installed in ACM before SPA can build HMI display pages. It provides the process object types, HMI display library, and display templates that SPA uses.

**1.** Open the Rockwell Automation [<u>Product Compatibility and Download Centre</u>](https://compatibility.rockwellautomation.com/).

**2.** Search for **PlantPAx Library of Process Objects**.

**3.** Download the **Application Code Manager libraries** package.

**4.** Run the library's registration script to install it into ACM.

## SPA ACM Libraries

The SPA installer places three SPA-specific ACM libraries under acm_libraries\ApplicationCodeManagerLibraries in the installation folder.

| **Library** | **Version** | **Used for** |
|----|:--:|----|
| (SPA) Solutions Project Accelerator ... Image | 1.8 | Static graphics extracted from P&IDs |
| (SPA) Solutions Project Accelerator ... PageLink | 1.5 | Navigation links between display pages |
| (SPA) Solutions Project Accelerator ... ProcessLine | 1.6 | Pipeline connections drawn between objects |

Register the libraries by running acm_library_register.cmd from the acm_libraries folder. The script copies the HSL4 files to Documents\Libraries\Application Code Manager and registers them through ACMConsole.exe. ACM must already be installed.

## Optional PLC Bridge SDKs

The following SDKs are required only for PLC bridge features such as converting L5X files to ACD files and downloading code to an emulated controller. SPA continues to run without them and provides an installation hint if an SDK is missing.

| **SDK** | **Version** | **Default wheel location** |
|----|:--:|----|
| Studio 5000 Logix Designer SDK | 2.0.2 | C:\Users\Public\Documents\Studio 5000\Logix Designer SDK\python |
| FactoryTalk Logix Echo SDK | 4.0.0 | C:\Users\Public\Documents\FactoryTalk Logix Echo\SDK\Python |

Change either path under **Tools \> Settings \> PLC Code \> Rockwell SDK Locations**.

## Basic Library Settings

SPA's defaults match a standard PlantPAx 5.0 installation. Review them under **Tools \> Settings** before creating your first project. If your site uses different libraries or versions, change the settings first because ACM objects are created against the selected libraries.

HMI Display Settings

| **Setting** | **Default** |
|----|----|
| Library used when creating an HMI Server | (RA-LIB) Process 5 Version 5.10 |
| Display template used when creating HMI displays | (RA-TPL)\_Process_5_HMI_Display_FTViewSE_12.0\_(1.0).xml |
| Display Width Pixels | 1920 |
| Display Height Pixels | 1080 |
| Display Color | E0E0E0 |
| Material Line Width / Color | 2 / AAAAAA |
| Signal Line Width / Color | 1 / 0B84FD with Use dash-dot selected |
| Library used when creating an Alarm Server | (RA-LIB) Process 5 Version 1.1 |

The HMI server list shows ACM libraries of type HMI in the Display category. The alarm server list shows type HMI in the FTAE category. If either list is empty, the PlantPAx library has not been registered in ACM.

PLC Code Settings

| **Setting** | **Default** |
|----|----|
| Library used when creating a Project | (RA-LIB) Process 5 Version 2.0 |
| Library used when creating a Controller | (RA-LIB) Process 5 Process_Controller Version 4.1 |
| Program used when creating Objects | Unscheduled |
| Task used when creating Objects | Unscheduled_Routines |
| PLC firmware revision 20 to 99 | 35 |

Static Graphics Settings

| **Setting**                  | **Default** |
|------------------------------|-------------|
| Default Extract Fill Color   | CCCCCC      |
| Default Extract Stroke Color | AAAAAA      |
| Default Extract Stroke Width | 2           |

## ACM Setup

Before SPA can build display pages, configure an HMI server in ACM.

**1.** Register the SPA libraries with acm_library_register.cmd.

**2.** Install the PlantPAx 5.0 ACM Library.

**3.** In the ACM **System View**, right-click **Displays** and select **Add**.

**4.** Choose **Process 5 HMI** and select **Next**.

**5.** Name the HMI server, select the Process 5 display template, and select **Finish**.

Review the ACM Setup subsection before starting Chapter 3, How to Create a Project.

## Recommended Install Order

**1.** Install Microsoft SQL Server or confirm the instance ACM will use.

**2.** Install Application Code Manager 5.00.

**3.** Install and register the PlantPAx 5.0 ACM Library.

**4.** Install Studio 5000 Logix Designer v35.

**5.** Install FactoryTalk View SE 14.

**6.** Install Solutions Project Accelerator.

**7.** Run acm_library_register.cmd to register the SPA ACM libraries.

**8. Review Tools \> Settings** against the Basic Library Settings in this section.
