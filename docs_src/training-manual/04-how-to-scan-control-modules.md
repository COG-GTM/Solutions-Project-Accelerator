# How to Scan Control Modules


To scan control modules, select a representative symbol on the P&ID. SPA creates a linked graphic template from the symbol and its nearby text, then scans the P&IDs for similar graphics and text. The original selection becomes the parent template, and matching graphics become child control modules. SPA pairs parent and child graphics using the shortest distance between them.

This section explains two control-module scanning workflows:

- Scanning without an ACM connection.

- Scanning with an existing ACM project.

## Scanning Control Modules Without an ACM Connection

Scanning without an ACM connection lets an engineer:

- Define a naming convention outside ACM.

- Collect I/O counts.

- Create an ACM project and objects from the scan results.

When SPA is not connected to ACM, it scans control modules without writing data to the ACM database. Proposal teams and engineers can use this workflow to obtain a quick I/O count or create a new ACM project and objects from the scan results.

The Control Modules pane is selected in the figure. Because SPA is not connected to ACM, create a new control-module template.

<img src="../training-manual-media/media/image16.png" style="width:6.5in;height:4.24375in" />

The **Not connected to ACM** message is expected until you link an ACM database.

<img src="../training-manual-media/media/image17.png" style="width:6.5in;height:4.24375in" />

Select a representative P&ID symbol that appears across several control modules. Use the symbol with the most text characters, as shown below.

In this example, **PIC2006** contains the most characters.

<img src="../training-manual-media/media/image18.png" style="width:6.5in;height:4.24653in" />

In the ACM section, **right-click** and select **Add New**. SPA adds an **Unassigned** module named **Untitled 1**, which you will use to create the template.

<img src="../training-manual-media/media/image19.png" style="width:6.5in;height:4.24653in" />

Select the **Unassigned** list header in the ACM section.

<img src="../training-manual-media/media/image20.png" style="width:6.5in;height:4.24653in" />

Select **Untitled 1** to open the control-module details.

<img src="../training-manual-media/media/image21.png" style="width:6.5in;height:4.24653in" />

Open **Linked Graphics** to link the selected graphic to the **Untitled 1** control module.

<img src="../training-manual-media/media/image22.png" style="width:6.5in;height:4.24653in" />

Select **Draw a Rectangle**, then outline the control-module symbol. SPA uses this region as the template for finding similar control modules.

Select **Draw a Rectangle**.

<img src="../training-manual-media/media/image23.png" style="width:6.5in;height:4.24653in" />

**Left-click** and **drag** a rectangle around the control module.

<img src="../training-manual-media/media/image24.png" style="width:6.5in;height:4.24653in" />

<img src="../training-manual-media/media/image25.png" style="width:6.5in;height:4.24653in" />

**Highlight** the region that contains the control-module text.

<img src="../training-manual-media/media/image26.png" style="width:6.5in;height:4.24653in" />

<img src="../training-manual-media/media/image27.png" style="width:6.5in;height:4.24653in" />

Select the highlighted graphic, then select the Linked Symbols icon.

<img src="../training-manual-media/media/image28.png" style="width:6.5in;height:4.24653in" />

The graphic appears under Linked Graphics. Define each text location separately, one line at a time.

Under Linked Graphics, add each highlighted line to Linked Text Locations.

**Select** the top line and link it to **Text Location 0**.

<img src="../training-manual-media/media/image29.png" style="width:6.5in;height:4.24653in" />

<img src="../training-manual-media/media/image30.png" style="width:6.5in;height:4.24653in" />

<img src="../training-manual-media/media/image31.png" style="width:6.5in;height:4.24653in" />

Select the bottom line and link it to Text Location 1.

<img src="../training-manual-media/media/image32.png" style="width:6.5in;height:4.24653in" />

<img src="../training-manual-media/media/image33.png" style="width:6.5in;height:4.24653in" />

<img src="../training-manual-media/media/image34.png" style="width:6.5in;height:4.24653in" />

Under Linked Graphics, the blue and red highlights correspond to the matching indicators under Linked Text Locations. The highlights confirm that the text lines are linked. Next, test the linked graphic.

Select **TEST ON PAGE** below Linked Graphics.

<img src="../training-manual-media/media/image35.png" style="width:6.5in;height:4.24653in" />

SPA tests the template and highlights matching control modules on the page. In this example, it finds every module that matches the template.

<img src="../training-manual-media/media/image36.png" style="width:6.5in;height:4.13958in" />

**Close** the test view to return to the control-module list.\
<img src="../training-manual-media/media/image37.png" style="width:6.5in;height:4.24653in" />

Enter the selected module’s exact tag name in the Name field under Linked Graphics. In this example, enter **PIC2006**. SPA cannot create the link if the name does not match the P&ID.

<img src="../training-manual-media/media/image38.png" style="width:6.5in;height:4.24653in" />

<img src="../training-manual-media/media/image39.png" style="width:6.5in;height:4.24653in" />

**Highlight** the module text on the P&ID and the corresponding text in the **Name** field, then select the link icon. You can select only text inside the region linked earlier. A gray bar above each segment in the **Name** field confirms the links.

<img src="../training-manual-media/media/image40.png" style="width:6.5in;height:4.24653in" />

<img src="../training-manual-media/media/image41.png" style="width:6.5in;height:4.24653in" />

<img src="../training-manual-media/media/image42.png" style="width:6.5in;height:4.24653in" />

<img src="../training-manual-media/media/image43.png" style="width:6.5in;height:4.24653in" />

After linking the graphic and text, scan all P&ID pages for similar control-module symbols.

Click **SCAN ALL PAGES**.

<img src="../training-manual-media/media/image44.png" style="width:6.5in;height:4.24653in" />

Scan progress appears in the lower-right corner.

<img src="../training-manual-media/media/image45.png" style="width:6.5in;height:4.24653in" />

<img src="../training-manual-media/media/image46.png" style="width:6.5in;height:4.24653in" />

Review all eight P&ID pages and confirm that SPA found every control module. The ACM list is not updated until you refresh it.

When the **Refresh** button appears, select it to update the control-module list.

<img src="../training-manual-media/media/image47.png" style="width:6.5in;height:4.24653in" />

The control modules found in the P&IDs now appear in the list. To locate a scanned module, select its tag name in the ACM pane and select **SHOW LINK**.

<img src="../training-manual-media/media/image48.png" style="width:6.5in;height:4.24236in" /><img src="../training-manual-media/media/image49.png" style="width:6.5in;height:4.24236in" />

SHOW LINK opens the matching module on the P&ID. Repeat the template-assignment process for the remaining symbol types. After linking each graphic and its text, you can export the database to Excel for an I/O list or instrument list.

## Creating an ACM Project and Objects from Scan Results

Creating an ACM project and objects from scan results lets an engineer:

- Create rules that automatically create ACM objects.

- Build HMI pages.

- Link data to ACM object parameters.

- Link data to ACM subobject parameters.

When SPA is not connected to an ACM project, it can create a project and objects from control-module naming conventions. After the project is created, engineers can populate parameters, subobjects, and subobject parameters in ACM.

For this exercise, use the unlinked project from the previous section with DEMO_PID.pdf already imported and scanned.

To connect to the ACM database, open the **File** menu and select **Connect Database**.

<img src="../training-manual-media/media/image50.png" style="width:6.5in;height:4.24236in" />

<img src="../training-manual-media/media/image51.png" style="width:6.5in;height:4.24236in" />

<img src="../training-manual-media/media/image52.png" style="width:6.5in;height:4.24236in" />

In the connection window, **select** the **SQL Server instance** and **ACM database**.

<img src="../training-manual-media/media/image53.png" style="width:3.93056in;height:5.26111in" />

<img src="../training-manual-media/media/image54.png" style="width:3.93056in;height:5.26111in" />

<img src="../training-manual-media/media/image55.png" style="width:3.93056in;height:5.26111in" />

<img src="../training-manual-media/media/image56.png" style="width:2.53889in;height:1.57361in" />

<img src="../training-manual-media/media/image57.png" style="width:3.93056in;height:5.26111in" />

After connecting to the database, the ACM section indicates that you must create or link an ACM project.

<img src="../training-manual-media/media/image58.png" style="width:6.5in;height:4.24236in" />

Open a scanned control module and select **ASSIGN OBJECT**.

<img src="../training-manual-media/media/image59.png" style="width:6.5in;height:4.24236in" />

<img src="../training-manual-media/media/image60.png" style="width:6.5in;height:4.24236in" />

<img src="../training-manual-media/media/image61.png" style="width:6.5in;height:4.24236in" />

The Assign Object view displays the object’s tag name and a Library Selection field.

Use Library Selection to choose an ACM library registered in ACM.

Enter **PPID** to filter the list for this specific example of FIC0000.

<img src="../training-manual-media/media/image62.png" style="width:6.5in;height:4.24236in" />

Scroll down and select **PPID 2.0.**

<img src="../training-manual-media/media/image63.png" style="width:6.5in;height:4.24236in" />

The text view lets you ignore characters and choose the text SPA uses to find objects with similar naming conventions.

Ignored text is excluded when SPA searches for similar objects.

Highlight **0000** in the text view.

<img src="../training-manual-media/media/image64.png" style="width:6.5in;height:4.24236in" />

<img src="../training-manual-media/media/image65.png" style="width:6.5in;height:4.24236in" />

**Right-click** the selection and select **Ignore Text**.

<img src="../training-manual-media/media/image66.png" style="width:6.5in;height:4.24236in" />

Ignored text appears in red. In this example, also ignore **F** so the rule can match PPID control modules that contain **IC** in the name.

<img src="../training-manual-media/media/image67.png" style="width:6.5in;height:4.24236in" />

<img src="../training-manual-media/media/image68.png" style="width:6.5in;height:4.24236in" />

Select **Apply**.

<img src="../training-manual-media/media/image69.png" style="width:6.5in;height:4.24236in" />

Click the **back arrow** to return to the main page.

<img src="../training-manual-media/media/image70.png" style="width:6.5in;height:4.24236in" />

**Refresh** the list.

<img src="../training-manual-media/media/image71.png" style="width:6.5in;height:4.24236in" />

<img src="../training-manual-media/media/image72.png" style="width:6.5in;height:4.24236in" />

Objects that match the naming rule appear under the assigned object type in blue.

<img src="../training-manual-media/media/image73.png" style="width:6.5in;height:4.24236in" />

Define additional naming rules for the remaining object types.

After defining the object types, select **Tools** \> **Create ACM Project**.

<img src="../training-manual-media/media/image74.png" style="width:6.5in;height:4.24236in" />

<img src="../training-manual-media/media/image75.png" style="width:6.5in;height:4.24236in" />

SPA creates an ACM project named SPA Project.

<img src="../training-manual-media/media/image76.png" style="width:4.80903in;height:2.82639in" />

When the process finishes, select Close.

<img src="../training-manual-media/media/image77.png" style="width:4.80903in;height:2.82639in" />

SPA is now linked to the new ACM project.

<img src="../training-manual-media/media/image78.png" style="width:6.5in;height:4.24236in" />

The new project appears in ACM.

<img src="../training-manual-media/media/image79.png" style="width:5.67192in;height:3.07956in" />

Select **Tools** \> **Create Assigned ACM Objects**. SPA creates the assigned control modules in the new ACM project.

<img src="../training-manual-media/media/image80.png" style="width:6.5in;height:4.24236in" />

<img src="../training-manual-media/media/image81.png" style="width:4.80903in;height:2.82639in" />

When the process finishes, select Close.

<img src="../training-manual-media/media/image82.png" style="width:4.80903in;height:2.82639in" />

Open the ACM project again and confirm that SPA created the assigned control modules.

<img src="../training-manual-media/media/image83.png" style="width:5.62403in;height:3.05416in" alt="A screenshot of a computer AI-generated content may be incorrect." />

<img src="../training-manual-media/media/image84.png" style="width:6.5in;height:4.24236in" />

<img src="../training-manual-media/media/image85.png" style="width:6.5in;height:4.24236in" />
