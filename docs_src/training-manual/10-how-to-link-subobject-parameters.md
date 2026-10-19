# How to Link Subobject Parameters


Linking subobject parameters lets engineers write design-document data to ACM subobject parameters. The SPA project must be connected to an ACM project. Engineers create extraction templates that identify related text in other documents. SPA lists the resulting links under Pending Approvals. Accepting a link writes the data to ACM; discarding it removes the proposed link.

This section explains two ways to link data from design documents:

- Linking data from PDF text documents.

- Linking data from Excel workbooks.

## Linking Data from PDF Text Documents

For this exercise, use the current SPA project connected to ACM.

In Data and Documents, right-click Text and select Import. Browse to the required PDF and open it.

<img src="../training-manual-media/media/image227.png" style="width:5.12186in;height:3.35in" />

This example uses Simple Control Philosophy.pdf.

<img src="../training-manual-media/media/image228.png" style="width:5.12186in;height:3.35in" />

The imported file appears under Text.

<img src="../training-manual-media/media/image229.png" style="width:5.12186in;height:3.35in" />

Double-click the imported file under Text to open it in the center document viewer.

<img src="../training-manual-media/media/image230.png" style="width:5.12186in;height:3.35in" />

This example links data to the UX00101 control module in the PMTR sublist under Control Modules.

Select UX00101 to open the control-module details.

<img src="../training-manual-media/media/image279.png" style="width:5.12163in;height:3.35in" />

Select Subobjects.

<img src="../training-manual-media/media/image280.png" style="width:5.12163in;height:3.35in" />

SPA displays the available subobject types.

In this example, select Interlocks.

<img src="../training-manual-media/media/image281.png" style="width:5.12163in;height:3.35in" />

Select + Add Subobject. This action creates a subobject in ACM.

<img src="../training-manual-media/media/image282.png" style="width:5.12186in;height:3.35in" />

SPA displays the new subobject. Select it to continue.

<img src="../training-manual-media/media/image283.png" style="width:5.12186in;height:3.35in" />

SPA displays the following two link fields:

- Tagname Link: identifies the text that contains the current control module’s tag name. In this example, the tag name is UX00101.

- Subobject Link: identifies text that refers to the current subobject type. This example does not contain a subobject-type reference.

> <img src="../training-manual-media/media/image284.png" style="width:5.12186in;height:3.35in" />
>
> Highlight the full tag-name description.
>
> <img src="../training-manual-media/media/image285.png" style="width:5.12186in;height:3.35in" />
>
> Select Link Text under Tagname Link.
>
> <img src="../training-manual-media/media/image286.png" style="width:5.12186in;height:3.35in" />
>
> SPA displays the selected tag-name reference in the text view below Tagname Link.
>
> <img src="../training-manual-media/media/image287.png" style="width:5.12186in;height:3.35in" />
>
> To help SPA find similar text, you can mark variable portions of the selected text to be ignored.
>
> Highlight the variable text, right-click it, and select Ignore Text.

<img src="../training-manual-media/media/image288.png" style="width:5.12186in;height:3.35in" />

Ignored text appears in red.

<img src="../training-manual-media/media/image289.png" style="width:5.12186in;height:3.35in" />

> Highlight the tag-name reference in the text view and the corresponding value in the tag-name field, then select the link button.

<img src="../training-manual-media/media/image290.png" style="width:5.12186in;height:3.35in" />

<img src="../training-manual-media/media/image291.png" style="width:5.12186in;height:3.35in" alt="A screenshot of a computer Description automatically generated" />

> Under Subparameter Name, enter ReferenceTag. The available subparameters come from the selected ACM subobject.
>
> <img src="../training-manual-media/media/image292.png" style="width:5.12186in;height:3.35in" />
>
> Select Add.
>
> <img src="../training-manual-media/media/image293.png" style="width:5.12186in;height:3.35in" />
>
> SPA initially displays the same source text under Parameter (ReferenceTag) Link.
>
> Because this example uses different source text for the parameter, select Unlink.
>
> <img src="../training-manual-media/media/image294.png" style="width:5.12186in;height:3.35in" />
>
> Highlight the full text that refers to the parameter. SPA uses this selection to find similar text.
>
> <img src="../training-manual-media/media/image295.png" style="width:5.12163in;height:3.35in" />
>
> The selected text appears below Parameter (ReferenceTag) Link.\
> <img src="../training-manual-media/media/image296.png" style="width:5.12163in;height:3.35in" />
>
> To help SPA find similar text, you can mark variable portions of the selected text to be ignored.
>
> Highlight the variable text, right-click it, and select Ignore Text.
>
> <img src="../training-manual-media/media/image297.png" style="width:5.12186in;height:3.35in" />
>
> Enter the required ACM object reference and link it to the relevant text in the text view.
>
> <img src="../training-manual-media/media/image298.png" style="width:5.12186in;height:3.35in" />
>
> <img src="../training-manual-media/media/image299.png" style="width:5.12186in;height:3.35in" />
>
> After linking the tag name and subparameter, select Done. SPA writes HSA00184A.Sts_TgtDisagree to the ReferenceTag parameter of the UX00101 interlock subobject, then searches the current page for similar links.
>
> <img src="../training-manual-media/media/image300.png" style="width:5.12163in;height:3.35in" />
>
> SPA marks the approved source link in green and proposed matches in yellow. Proposed matches appear under Pending Approvals. Point to a yellow highlight to view its summary.
>
> The Pending Approvals button, highlighted below in red, shows the number of proposed links.
>
> <img src="../training-manual-media/media/image301.png" style="width:5.12163in;height:3.35in" />
>
> Select Pending Approvals.
>
> <img src="../training-manual-media/media/image302.png" style="width:5.12163in;height:3.35in" />
>
> SPA displays a list of proposed links. Select the header to expand it.
>
> <img src="../training-manual-media/media/image303.png" style="width:5.12163in;height:3.35in" />
>
> The Pending Approvals list.
>
> <img src="../training-manual-media/media/image304.png" style="width:5.12163in;height:3.35in" />
>
> Select a list item to expand it and highlight its tag-name reference in light blue in the document.
>
> The bottom of the Pending Approvals view contains Discard, Accept, and Accept All:

- Discard: removes the proposed link from the list and document.

- Accept: approves the link, changes its document highlight to green, and writes the value to the ACM subobject parameter.

- Accept All: approves every proposed link.

> <img src="../training-manual-media/media/image305.png" style="width:5.12163in;height:3.35in" />
>
> Select Accept to approve one proposed link.
>
> <img src="../training-manual-media/media/image306.png" style="width:5.12163in;height:3.35in" />
>
> The approved item is removed from the list, its document highlight turns green, and the data is written to ACM. Approved links appear under Subobjects in the selected control module.
>
> <img src="../training-manual-media/media/image307.png" style="width:5.12163in;height:3.35in" />
>
> Select Discard to remove a proposed link and its document highlight.
>
> <img src="../training-manual-media/media/image308.png" style="width:5.12163in;height:3.35in" />
>
> <img src="../training-manual-media/media/image309.png" style="width:5.12163in;height:3.35in" />
>
> Select Accept All to approve every proposed link and clear the list.

## Linking Data from Excel Workbooks

For this exercise, use the current SPA project connected to ACM.

In Data and Documents, right-click Sheets and select Import. Browse to the required Excel workbook and open it.

<img src="../training-manual-media/media/image253.png" style="width:5.12163in;height:3.35in" />

This example uses Cause-and-effect-template-2.xlsx.

<img src="../training-manual-media/media/image310.png" style="width:5.12163in;height:3.35in" />

The imported file appears under Sheets.

<img src="../training-manual-media/media/image311.png" style="width:5.12163in;height:3.35in" />

Double-click the imported file under Sheets to open it in the center document viewer.

<img src="../training-manual-media/media/image312.png" style="width:5.12163in;height:3.35in" />

This example links data to the UX00101 control module in the PMTR sublist under Control Modules.

Select UX00101 to open the control-module details.<img src="../training-manual-media/media/image313.png" style="width:5.12163in;height:3.35in" />

Select Subobjects.

<img src="../training-manual-media/media/image314.png" style="width:5.12163in;height:3.35in" />

SPA displays the available subobject types.

In this example, select Interlocks.

<img src="../training-manual-media/media/image315.png" style="width:5.12163in;height:3.35in" />

Select + Add Subobject. This action creates a subobject in ACM.

<img src="../training-manual-media/media/image316.png" style="width:5.12163in;height:3.35in" />

SPA displays the new subobject. Select it to continue.

<img src="../training-manual-media/media/image317.png" style="width:5.12163in;height:3.35in" />

SPA displays the following two link fields:

- Tagname Link: identifies the text that contains the current control module’s tag name. In this example, the tag name is UX00101.

- Subobject Link: identifies text that refers to the current subobject type. This example does not contain a subobject-type reference.

> <img src="../training-manual-media/media/image318.png" style="width:5.12163in;height:3.35in" />
>
> Select the source cell or highlight the tag-name reference in the document viewer. Highlight the matching value in the tag-name field, then select the link button.

<img src="../training-manual-media/media/image319.png" style="width:5.12163in;height:3.35in" />

<img src="../training-manual-media/media/image320.png" style="width:5.12163in;height:3.35in" />

> Under Subparameter Name, enter ReferenceTag. The available subparameters come from the selected ACM subobject.
>
> <img src="../training-manual-media/media/image321.png" style="width:5.12163in;height:3.35in" />
>
> Select Add.
>
> <img src="../training-manual-media/media/image322.png" style="width:5.12163in;height:3.35in" />
>
> Enter the required ACM object reference and link it to the relevant text in the text view.
>
> <img src="../training-manual-media/media/image323.png" style="width:5.12163in;height:3.35in" />
>
> <img src="../training-manual-media/media/image324.png" style="width:5.12163in;height:3.35in" />
>
> After linking the tag name and subparameter, select Done. SPA writes FI00726.Sts_HiHi to the ReferenceTag parameter of the UX00101 interlock subobject, then searches the current page for similar links.
>
> <img src="../training-manual-media/media/image325.png" style="width:5.12163in;height:3.35in" />
>
> The Pending Approvals button, highlighted below in red, shows the number of proposed links.
>
> <img src="../training-manual-media/media/image326.png" style="width:5.12163in;height:3.35in" />
>
> Select Pending Approvals.
>
> <img src="../training-manual-media/media/image327.png" style="width:5.12163in;height:3.35in" />
>
> SPA displays a list of proposed links. Select the header to expand it.
>
> <img src="../training-manual-media/media/image328.png" style="width:5.12163in;height:3.35in" />
>
> The Pending Approvals list.
>
> <img src="../training-manual-media/media/image329.png" style="width:5.12163in;height:3.35in" />
>
> Select a list item to expand it and highlight its tag-name reference in light blue in the document.
>
> The bottom of the Pending Approvals view contains Discard, Accept, and Accept All:

- Discard: removes the proposed link from the list and document.

- Accept: approves the link, changes its document highlight to green, and writes the value to the ACM subobject parameter.

- Accept All: approves every proposed link.

> <img src="../training-manual-media/media/image330.png" style="width:5.12163in;height:3.35in" />
>
> Select Accept to approve one proposed link.
>
> <img src="../training-manual-media/media/image330.png" style="width:5.12163in;height:3.35in" />
>
> The approved item is removed from the list, and the data is written to ACM. Approved links appear under Subobjects in the selected control module.
>
> <img src="../training-manual-media/media/image307.png" style="width:5.12163in;height:3.35in" />
>
> Select Discard to remove a proposed link.
>
> <img src="../training-manual-media/media/image331.png" style="width:5.12163in;height:3.35in" />
>
> <img src="../training-manual-media/media/image309.png" style="width:5.12163in;height:3.35in" />
>
> Select Accept All to approve every proposed link and clear the list.

**\**
