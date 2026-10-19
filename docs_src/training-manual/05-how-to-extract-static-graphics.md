# How to Extract Static Graphics


Extracting static graphics lets an engineer capture non-animated graphics from a P&ID. You can scan static graphics with or without an ACM connection.

For this exercise, use the current SPA project connected to ACM.

This example uses the cooler graphic on page 7.

Select **Static Graphics** on the right. Because the list is empty, open DEMO_PID.pdf and select the graphic to add.

<img src="../training-manual-media/media/image86.png" style="width:6.5in;height:4.24236in" />

Click the **Draw a Polygon** tool.

<img src="../training-manual-media/media/image87.png" style="width:6.5in;height:4.24236in" />

Use the polygon tool to place points around the graphic. Keep the selection close to the graphic so it does not include unrelated lines or objects. When SPA processes a native PDF, it can convert the selected region to an SVG file.

<img src="../training-manual-media/media/image88.png" style="width:6.5in;height:4.24236in" />

**Close** the polygon to complete the selection.

<img src="../training-manual-media/media/image89.png" style="width:6.5in;height:4.24236in" />

In the ACM section, **right-click** and select **Add New**. SPA adds an Unassigned graphic named Untitled 1, which you will use to create the static-graphic template.

<img src="../training-manual-media/media/image90.png" style="width:6.5in;height:4.24236in" />

Select the **Unassigned** list header in the ACM section.

<img src="../training-manual-media/media/image91.png" style="width:6.5in;height:4.24236in" />

Select **Untitled 1**.

<img src="../training-manual-media/media/image92.png" style="width:6.5in;height:4.24236in" />

Name the template Cooler.

Select the **Name** field.

<img src="../training-manual-media/media/image93.png" style="width:6.5in;height:4.24236in" />

Enter **Cooler**.

<img src="../training-manual-media/media/image94.png" style="width:6.5in;height:4.24236in" />

As in the previous section, open **Linked Graphics** to link the polygon to the static-graphic object.

<img src="../training-manual-media/media/image95.png" style="width:6.5in;height:4.24236in" />

**Select** the static-graphic **polygon.**

<img src="../training-manual-media/media/image96.png" style="width:6.5in;height:4.24236in" />

Select the **Link** icon. The graphic appears in the **Primary Graphic** area.

<img src="../training-manual-media/media/image97.png" style="width:6.5in;height:4.24236in" />

Click the **back arrow** to return to the Static Graphics list.

<img src="../training-manual-media/media/image98.png" style="width:6.5in;height:4.24236in" />

Open HMI Graphic for the static-graphic template.

Select **HMI Graphic**.

<img src="../training-manual-media/media/image99.png" style="width:6.5in;height:4.24236in" />

The HMI Graphic section provides three options:

- **Extract Graphic:** creates an HMI graphic from the linked selection.

- **Custom Graphic:** imports an SVG or PNG file.

- **Similar Graphics:** links the template to a similar graphic in the repository.

For this example, select Extract Graphic.

<img src="../training-manual-media/media/image100.png" style="width:6.5in;height:4.24236in" />

Select Extract and wait for the graphic to appear in the template.

<img src="../training-manual-media/media/image101.png" style="width:6.5in;height:4.24236in" />

<img src="../training-manual-media/media/image102.png" style="width:6.5in;height:4.24236in" />

The extracted graphic retains line and fill colors. To change the fill, select the Fill color swatch and choose a color from the palette.

<img src="../training-manual-media/media/image103.png" style="width:6.5in;height:4.24236in" />

Select the required color.

<img src="../training-manual-media/media/image104.png" style="width:4.67847in;height:3.43472in" />

Click the **back arrow** to return to the Static Graphics list.

<img src="../training-manual-media/media/image105.png" style="width:6.5in;height:4.24236in" />

Select Export Graphic to save the graphic as an SVG or PNG file.

<img src="../training-manual-media/media/image106.png" style="width:6.5in;height:4.24236in" />

Enter a file name and select Save.

<img src="../training-manual-media/media/image107.png" style="width:6.5in;height:4.49722in" />

<img src="../training-manual-media/media/image108.png" style="width:6.5in;height:4.49722in" />

After configuring the extracted graphic, select Run Scan to search the P&IDs for similar graphics. This example P&ID contains no matching static graphics, so the scan returns no matches.
