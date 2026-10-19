# How to Build HMI Display Pages


The SPA project now contains templates for control modules, static graphics, HMI displays, and page links. Use these templates to build HMI display pages from the demo_plant P&IDs.

## Build Displays from SPA

Build HMI Display automatically generates HMI pages from the project’s scanned P&IDs and configured templates. Open Tools \> Build HMI to use ACM to generate the display graphics and export FactoryTalk View bulk-import files and images.

Before export, each generated display opens in an editable canvas. Drag control modules to reposition them, and resize static graphics with the corner or edge handles. You can lock the original aspect ratio. Adjust the generated layout before exporting the final files to FTView Studio.

To begin, select Tools \> Build HMI \> XML and Images.

<img src="../training-manual-media/media/image165.png" style="width:6.5in;height:4.24236in" />

<img src="../training-manual-media/media/image166.png" style="width:6.5in;height:4.24236in" />

A progress window appears while SPA uses ACM to generate the displays.

<img src="../training-manual-media/media/image167.png" style="width:4.80903in;height:2.82639in" />

The Build HMI Display workspace opens when generation finishes.

<img src="../training-manual-media/media/image168.png" style="width:6.5in;height:4.07569in" />

The first display is blank; select Next to continue.

<img src="../training-manual-media/media/image169.png" style="width:6.5in;height:4.07569in" />

PID0002 appears next, but several static graphics are missing.

<img src="../training-manual-media/media/image170.png" style="width:6.5in;height:4.07847in" />

### Creating a Static Graphic

Create Static Graphic is a quick-add command for selected polygons or rectangles on a P&ID. It converts an existing selection directly into a static graphic without the full scan-and-link workflow.

The command opens Quick Create Static Graphic, extracts the selected region, and displays a preview. Edit the suggested name if needed, then select Save to add the graphic to the project’s Static Graphics list.

Use this command for non-animated background elements, such as structural shapes, piping runs, and labels, that do not need a repeating template. Return to the main SPA workspace to add the missing static graphics.

<img src="../training-manual-media/media/image171.png" style="width:6.5in;height:4.24236in" />

Select Draw a Polygon.

<img src="../training-manual-media/media/image172.png" style="width:6.5in;height:4.24236in" />

Draw a polygon around the required static graphic.

<img src="../training-manual-media/media/image173.png" style="width:6.5in;height:4.24236in" />

Point to the polygon outline.

<img src="../training-manual-media/media/image174.png" style="width:6.5in;height:4.24236in" />

Right-click and select Create Static Graphic.

<img src="../training-manual-media/media/image175.png" style="width:6.5in;height:4.24236in" />

Quick Create Static Graphic opens.

<img src="../training-manual-media/media/image176.png" style="width:5.22639in;height:6.05208in" />

Enter a name for the static graphic.

<img src="../training-manual-media/media/image177.png" style="width:5.22639in;height:6.05208in" />

**Enter Hopper in the Name field.**

<img src="../training-manual-media/media/image178.png" style="width:5.22639in;height:6.05208in" />

**Select Save.**

<img src="../training-manual-media/media/image179.png" style="width:5.22639in;height:6.05208in" />

The new graphic appears automatically in Build HMI Display.

<img src="../training-manual-media/media/image180.png" style="width:6.5in;height:4.07569in" />

Repeat the process for the remaining missing static graphics.

<img src="../training-manual-media/media/image181.png" style="width:6.5in;height:4.07569in" />

### Changing a Symbol

Change Symbol replaces the graphic used by a selected object without deleting or repositioning it. Right-click one library symbol and select Change Symbol. The Symbol Selector displays all symbols in that object’s library and marks the current symbol.

Selecting a new symbol replaces the image and dimensions in place. SPA remaps anchors and connected lines to the replacement symbol. If an exact anchor match is unavailable, SPA uses the nearest valid anchor. You can reverse the change with Undo.

Change Symbol is available only when one object is selected.<img src="../training-manual-media/media/image182.png" style="width:6.5in;height:4.07569in" />

Right-click the control module and select Change Symbol.

<img src="../training-manual-media/media/image183.png" style="width:6.49583in;height:4.07847in" />

The Symbol Selector opens with the available library symbols.

<img src="../training-manual-media/media/image184.png" style="width:6.5in;height:5.11319in" />

**Select the required symbol, then select OK.**

<img src="../training-manual-media/media/image185.png" style="width:6.5in;height:5.11319in" />

The selected symbol appears in Build HMI Display.

<img src="../training-manual-media/media/image186.png" style="width:6.5in;height:4.07569in" />

### Anchors and Auto-Routing

Each library symbol can define anchors: fixed connection points on its top, bottom, left, and right edges. To add anchors manually, right-click the symbol and select Configure Symbol Anchors.

SPA adds anchors automatically to extracted static graphics wherever a pipe or signal line crosses the edge of the selected region. Each anchor is snapped to the nearest boundary.

When SPA scans a P&ID, it detects connecting pipe and signal lines and routes them between the corresponding symbol anchors. The right-angle lines use the following styles:

- **Material lines: solid lines for process piping between equipment.**

- **Signal lines: dashed lines for instrument and control signals.**

If a symbol has no anchors, SPA connects the line to the nearest point on the symbol outline. After anchors are added, SPA updates those fallback connections. Moving, resizing, or replacing a symbol reroutes its connected lines to the current anchors.

To configure anchors, right-click a control-module symbol and select Configure Symbol Anchors.

<img src="../training-manual-media/media/image187.png" style="width:6.49583in;height:4.07847in" />

The Configure Anchors window opens.<img src="../training-manual-media/media/image188.png" style="width:6.5in;height:5.86181in" />

Select Place Right Anchor.

<img src="../training-manual-media/media/image189.png" style="width:6.5in;height:5.86181in" />

Place the anchor at the point shown below.

<img src="../training-manual-media/media/image190.png" style="width:6.5in;height:5.86181in" />

A green circle confirms the right-side anchor.

<img src="../training-manual-media/media/image191.png" style="width:6.5in;height:5.86181in" />

Repeat the process for the left anchor.

<img src="../training-manual-media/media/image192.png" style="width:6.5in;height:5.86181in" />

<img src="../training-manual-media/media/image193.png" style="width:6.5in;height:5.86181in" />

Save the changes. SPA applies them to other instances of the same symbol.

<img src="../training-manual-media/media/image194.png" style="width:6.5in;height:5.86181in" />

Use the anchor points in Build HMI Display to connect symbols.

Drag from the first anchor point.

<img src="../training-manual-media/media/image195.png" style="width:6.5in;height:4.07569in" />

<img src="../training-manual-media/media/image196.png" style="width:6.5in;height:4.07569in" />

Drop the connection on the page-link anchor.

<img src="../training-manual-media/media/image197.png" style="width:6.5in;height:4.07569in" />

When you release the mouse button, SPA links the anchors and draws the connecting line.

<img src="../training-manual-media/media/image198.png" style="width:6.5in;height:4.07569in" />

Connect the remaining anchor points.

<img src="../training-manual-media/media/image199.png" style="width:6.5in;height:4.07569in" />

### Editing a Static Graphic

Edit Static Graphic changes a static graphic already placed on an HMI display. Right-click the graphic and select Edit Static Graphic to open the SVG editor. You can adjust its lines, curves, points, colors, stroke width, and fill. Apply the changes only to the selected graphic or to matching graphics across open and saved displays.

Right-click the static graphic and select Edit Static Graphic.

<img src="../training-manual-media/media/image200.png" style="width:6.5in;height:4.17639in" />

In this example, right-click each extra rectangle and select Delete Path.

<img src="../training-manual-media/media/image201.png" style="width:6.5in;height:5.11319in" />

<img src="../training-manual-media/media/image202.png" style="width:6.5in;height:5.11319in" />

Delete the second rectangle in the same way.

<img src="../training-manual-media/media/image203.png" style="width:6.5in;height:5.11319in" />

Select Save.

<img src="../training-manual-media/media/image204.png" style="width:6.5in;height:5.11319in" />

The updated graphic appears automatically in Build HMI Display.

<img src="../training-manual-media/media/image205.png" style="width:6.5in;height:4.07569in" />

When the display is complete, select Export Display.

<img src="../training-manual-media/media/image206.png" style="width:6.5in;height:4.07569in" />

Select Select Folder.

<img src="../training-manual-media/media/image207.png" style="width:6.5in;height:4.49722in" />

Select OK to close the confirmation.

<img src="../training-manual-media/media/image208.png" style="width:3.67847in;height:1.57361in" />

The export folder contains bulk-import files, graphic XML files, and an Images folder for FTView.

<img src="../training-manual-media/media/image209.png" style="width:6.5in;height:4.34167in" />

## Importing to FTView Studio

Open FTView Studio and select the target application. This example uses Project_Example_Plant.

Import the exported images into FTView.

<img src="../training-manual-media/media/image210.png" style="width:6.5in;height:4.16944in" />

Confirm that the images appear in FTView.

<img src="../training-manual-media/media/image211.png" style="width:6.5in;height:4.17292in" />

<img src="../training-manual-media/media/image212.png" style="width:6.5in;height:4.99375in" />

<img src="../training-manual-media/media/image213.png" style="width:5.50903in;height:2.93056in" alt="Graphical user interface Description automatically generated" />Open the Displays section of the FTView project.

**Right-click Displays and select Import and Export.**

<img src="../training-manual-media/media/image214.png" style="width:6.5in;height:4.17292in" />

<img src="../training-manual-media/media/image215.png" style="width:6.5in;height:4.17292in" />

Select Import graphic information into displays, then select Next.

<img src="../training-manual-media/media/image216.png" style="width:4.70417in;height:3.51319in" />

Select No Backup, then select Next.

<img src="../training-manual-media/media/image217.png" style="width:4.70417in;height:3.51319in" />

Select Multiple displays batch import file, then select Next.

<img src="../training-manual-media/media/image218.png" style="width:4.70417in;height:3.51319in" />

Locate the multiple-display batch-import file.

<img src="../training-manual-media/media/image219.png" style="width:4.70417in;height:3.51319in" />

In the HMI export directory, select the batch-import file.

<img src="../training-manual-media/media/image220.png" style="width:6.5in;height:4.99375in" />

<img src="../training-manual-media/media/image221.png" style="width:6.5in;height:4.99375in" />

<img src="../training-manual-media/media/image222.png" style="width:4.70417in;height:3.51319in" />

FTView Studio imports the files into the project. Compare the generated displays with the source P&IDs. Only objects with templates in SPA are included; in this example, the display contains the configured valves, pumps, and page connectors.

<img src="../training-manual-media/media/image223.png" style="width:4.63472in;height:1.69583in" />

Open each object to confirm that the data entered in SPA is present. Confirm that every page connector points to the correct HMI display.

<img src="../training-manual-media/media/image224.png" style="width:6.5in;height:4.17292in" />

The page-connector animation displays the name of its destination.

<img src="../training-manual-media/media/image225.png" style="width:6.5in;height:4.17292in" />

<img src="../training-manual-media/media/image226.png" style="width:6.5in;height:4.17292in" />

Confirm that each static graphic appears on the correct HMI display and in the same relative position as on the P&ID.
