# How to Scan HMI Display Pages and Page Links


Scanning HMI display pages and page links lets an engineer capture animated graphics and navigation links from P&IDs. You can scan them with or without an ACM connection.

For this exercise, use the current SPA project without an ACM connection.

This workflow uses the drawing-number block as the page template. It captures each P&ID drawing number in a consistent format, identifies HMI display pages, and supplies the destination data for page links.

Select **HMI Displays** on the right. Open DEMO_P&ID.pdf, then create an HMI display template because the ACM list is empty.

<img src="../training-manual-media/media/image109.png" style="width:6.5in;height:4.24236in" />

In the ACM section, **right-click** and select **Add New**. SPA adds an Unassigned display named Untitled 1, which you will use to create the HMI display template.

<img src="../training-manual-media/media/image110.png" style="width:6.5in;height:4.24236in" />

Select the **Unassigned** list header in the ACM section.

<img src="../training-manual-media/media/image111.png" style="width:6.5in;height:4.24236in" />

Select **Untitled 1**.

<img src="../training-manual-media/media/image112.png" style="width:6.5in;height:4.24236in" />

Open **Linked Graphics** to link the selected region to the **Untitled 1** HMI display page.

<img src="../training-manual-media/media/image113.png" style="width:6.5in;height:4.24236in" />

Click the **Draw a Rectangle** and outline the drawing-number block. SPA uses this region to find similar blocks on other pages.

Select **Draw a Rectangle**.

<img src="../training-manual-media/media/image114.png" style="width:6.5in;height:4.24236in" />

Select the drawing-number block used by page links. Include a larger region around the block as the visual reference so SPA can locate it on other pages.

**Left-click** and **drag** around the entire drawing-number cell.

> <img src="../training-manual-media/media/image115.png" style="width:6.5in;height:4.24236in" />
>
> <img src="../training-manual-media/media/image116.png" style="width:6.5in;height:4.24236in" />
>
> Highlight only the drawing-number text, excluding the title.
>
> <img src="../training-manual-media/media/image117.png" style="width:6.5in;height:4.24236in" />
>
> <img src="../training-manual-media/media/image118.png" style="width:6.5in;height:4.24236in" />
>
> Link the highlighted region to Primary Graphic.
>
> <img src="../training-manual-media/media/image119.png" style="width:6.5in;height:4.24236in" />
>
> The graphic appears under Linked Graphics. Define a text location that includes only the drawing number.
>
> Add the highlighted drawing number under Linked Text Locations.
>
> **Select** the drawing-number text and link it to **Text Location 0.**
>
> <img src="../training-manual-media/media/image120.png" style="width:6.5in;height:4.24236in" />
>
> Confirm the **selected** text.
>
> <img src="../training-manual-media/media/image121.png" style="width:6.5in;height:4.24236in" />
>
> <img src="../training-manual-media/media/image122.png" style="width:6.5in;height:4.24236in" />
>
> <img src="../training-manual-media/media/image123.png" style="width:6.5in;height:4.24236in" />
>
> Select TEST ON PAGE below Linked Graphics.
>
> <img src="../training-manual-media/media/image124.png" style="width:6.5in;height:4.13958in" />

SPA highlights the drawing-number location found on the page. Confirm that only the block at the bottom is selected; otherwise, refine the template.

> **Close** the test view to return to the HMI display list.
>
> <img src="../training-manual-media/media/image125.png" style="width:6.5in;height:4.24236in" />
>
> Enter a name for the HMI display in the Name field. In this example, use **PID0002**. The name must begin with a letter so SPA can generate the display; you can link only the **0002** portion of the drawing number.
>
> <img src="../training-manual-media/media/image126.png" style="width:6.5in;height:4.24236in" />

Enter **PID0002** in the Name field.

> <img src="../training-manual-media/media/image127.png" style="width:6.5in;height:4.24236in" />
>
> Drag from the first zero to highlight **0002**.
>
> <img src="../training-manual-media/media/image128.png" style="width:6.5in;height:4.24236in" />
>
> Highlight **0002** in both the P&ID and the **Name** field.
>
> <img src="../training-manual-media/media/image129.png" style="width:6.5in;height:4.24236in" />
>
> Select the **Link** **Text** icon.
>
> <img src="../training-manual-media/media/image130.png" style="width:6.5in;height:4.24236in" />
>
> Page links on other P&IDs point to this drawing. Go to page 3 of DEMO_P&ID.pdf to find the link to **NPS-PID-0002**.
>
> <img src="../training-manual-media/media/image131.png" style="width:6.5in;height:4.24236in" />
>
> Using the rectangle selection tool, select the page-link graphic and its two text fields. Make the text region large enough to include links that point in either direction.
>
> <img src="../training-manual-media/media/image132.png" style="width:6.5in;height:4.24236in" />
>
> <img src="../training-manual-media/media/image133.png" style="width:6.5in;height:4.24236in" />
>
> <img src="../training-manual-media/media/image134.png" style="width:6.5in;height:4.24236in" />
>
> <img src="../training-manual-media/media/image134.png" style="width:6.5in;height:4.24236in" />
>
> Link the page-link graphic to Secondary Graphic and link both text locations.
>
> <img src="../training-manual-media/media/image135.png" style="width:6.5in;height:4.24236in" />
>
> <img src="../training-manual-media/media/image136.png" style="width:6.5in;height:4.24236in" />
>
> <img src="../training-manual-media/media/image137.png" style="width:6.5in;height:4.24236in" />
>
> <img src="../training-manual-media/media/image138.png" style="width:6.5in;height:4.24236in" />
>
> <img src="../training-manual-media/media/image139.png" style="width:6.5in;height:4.24236in" />
>
> <img src="../training-manual-media/media/image140.png" style="width:6.5in;height:4.24236in" />
>
> <img src="../training-manual-media/media/image141.png" style="width:6.5in;height:4.24236in" />
>
> <img src="../training-manual-media/media/image142.png" style="width:6.5in;height:4.24236in" />
>
> Select **Test on Page** and confirm that the scan finds every page link.
>
> <img src="../training-manual-media/media/image143.png" style="width:6.5in;height:4.24236in" />
>
> SPA highlights the page links found by the scan.
>
> <img src="../training-manual-media/media/image144.png" style="width:6.5in;height:4.13958in" />
>
> Click the **back arrow** to return to the HMI Displays list.
>
> <img src="../training-manual-media/media/image145.png" style="width:6.5in;height:4.24236in" />
>
> Repeat the name-linking process using the text from the page link.
>
> <img src="../training-manual-media/media/image146.png" style="width:6.5in;height:4.24236in" />
>
> <img src="../training-manual-media/media/image147.png" style="width:6.5in;height:4.24236in" />
>
> <img src="../training-manual-media/media/image148.png" style="width:6.5in;height:4.24236in" />
>
> Gray bars below the name confirm that Secondary Graphic is linked.
>
> Click **Run Scan**.
>
> <img src="../training-manual-media/media/image149.png" style="width:6.5in;height:4.24236in" />

When the **Refresh** button appears, select it to update the HMI display list.

> <img src="../training-manual-media/media/image150.png" style="width:6.5in;height:4.24236in" />
>
> After the scan completes, the list shows the number of pages created. Open PID0002, review its page links, and select the page used to create the template.
>
> <img src="../training-manual-media/media/image151.png" style="width:6.5in;height:4.24236in" />
>
> <img src="../training-manual-media/media/image152.png" style="width:6.5in;height:4.24236in" />
>
> Open **Page Links**.
>
> <img src="../training-manual-media/media/image153.png" style="width:6.5in;height:4.24236in" />
>
> The captured page links appear in the list.
>
> <img src="../training-manual-media/media/image154.png" style="width:6.5in;height:4.24236in" />

The page numbers in the ACM section identify the P&ID pages linked to PID0002.

<img src="../training-manual-media/media/image155.png" style="width:6.5in;height:4.24236in" />

<span id="_Toc182477877" class="anchor"></span>
