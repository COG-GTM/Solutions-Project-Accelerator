# How to Link Object Parameters


Linking object parameters lets engineers write design-document data to ACM object parameters. The SPA project must be connected to an ACM project. Engineers create extraction templates that identify related text in other documents. SPA lists the resulting links under Pending Approvals. Accepting a link writes the data to ACM; discarding it removes the proposed link.

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

This example links data to the AI00741 control module in the PAI sublist under Control Modules.

Select AI00741 to open the control-module details.

<img src="../training-manual-media/media/image231.png" style="width:5.12186in;height:3.35in" />

Select Parameters.

<img src="../training-manual-media/media/image232.png" style="width:5.12186in;height:3.35in" />

SPA displays the parameter-linking view.

<img src="../training-manual-media/media/image233.png" style="width:5.12186in;height:3.35in" />

Enter the required ACM parameter in Parameter Name.

Select the required parameter from the list of matches.

<img src="../training-manual-media/media/image234.png" style="width:5.12186in;height:3.35in" />

Select Add, then select the source cell.

<img src="../training-manual-media/media/image235.png" style="width:5.12186in;height:3.35in" />

SPA displays the following two link fields:

- Tagname Link: identifies the text that contains the current control module’s tag name. In this example, the tag name is AI00741.

- Parameter Link (Cfg_LoLoLim): identifies the source value for the selected ACM parameter. In this example, the value is 2 in the LoLo column.

> <img src="../training-manual-media/media/image236.png" style="width:5.12186in;height:3.35in" />
>
> Highlight AI00741 in the source table. Because the selection is inside a table, SPA displays the table-linking controls.
>
> <img src="../training-manual-media/media/image237.png" style="width:5.12186in;height:3.35in" />

Highlight the matching tag name under Tagname Link, then select the link button.

<img src="../training-manual-media/media/image238.png" style="width:5.12186in;height:3.35in" />

> Change the value under Parameter Link (Cfg_LoLoLim) to match the source table.
>
> <img src="../training-manual-media/media/image239.png" style="width:5.12186in;height:3.35in" />
>
> Highlight the source value and the matching value under Parameter Link, then select the link button.
>
> <img src="../training-manual-media/media/image240.png" style="width:5.12186in;height:3.35in" />
>
> After linking the tag name and parameter value, select Done. SPA writes the source value, 2, to the Cfg_LoLoLim parameter of AI00741, then searches the current page for similar links.
>
> <img src="../training-manual-media/media/image241.png" style="width:5.12186in;height:3.35in" />
>
> SPA marks the approved source link in green and proposed matches in yellow. Proposed matches appear under Pending Approvals. Point to a yellow highlight to view its summary.
>
> The Pending Approvals button, highlighted below in red, shows the number of proposed links.
>
> <img src="../training-manual-media/media/image242.png" style="width:5.12186in;height:3.35in" />
>
> Select Pending Approvals.
>
> <img src="../training-manual-media/media/image243.png" style="width:5.12186in;height:3.35in" />
>
> SPA displays a list of proposed links. Select the header to expand it.
>
> <img src="../training-manual-media/media/image244.png" style="width:5.12186in;height:3.35in" />
>
> The Pending Approvals list.
>
> <img src="../training-manual-media/media/image245.png" style="width:5.12185in;height:3.35in" />
>
> Select a list item to expand it and highlight its tag-name reference in light blue in the document.
>
> The bottom of the Pending Approvals view contains Discard, Accept, and Accept All:

- Discard: removes the proposed link from the list and document.

- Accept: approves the link, changes its document highlight to green, and writes the value to the ACM object parameter.

- Accept All: approves every proposed link.

> <img src="../training-manual-media/media/image246.png" style="width:5.12186in;height:3.35in" alt="A screenshot of a computer Description automatically generated" />
>
> Select Accept to approve one proposed link.
>
> <img src="../training-manual-media/media/image247.png" style="width:5.12186in;height:3.35in" />
>
> The approved item is removed from the list, its document highlight turns green, and the data is written to ACM. Approved links appear under Subobjects in the selected control module.
>
> <img src="../training-manual-media/media/image248.png" style="width:5.12186in;height:3.35in" />
>
> Select Discard to remove a proposed link and its document highlight.
>
> <img src="../training-manual-media/media/image249.png" style="width:5.12186in;height:3.35in" />
>
> <img src="../training-manual-media/media/image250.png" style="width:5.12227in;height:3.35in" />
>
> Select Accept All to approve every proposed link and clear the list.
>
> <img src="../training-manual-media/media/image251.png" style="width:5.12227in;height:3.35in" />
>
> <img src="../training-manual-media/media/image252.png" style="width:5.12227in;height:3.35in" />

## Linking Data from Excel Workbooks

For this exercise, use the current SPA project connected to ACM.

In Data and Documents, right-click Sheets and select Import. Browse to the required Excel workbook and open it.

<img src="../training-manual-media/media/image253.png" style="width:5.12163in;height:3.35in" />

This example uses IO-List-Ranges.xlsx.

<img src="../training-manual-media/media/image254.png" style="width:5.12163in;height:3.35in" />

The imported file appears under Sheets.

<img src="../training-manual-media/media/image255.png" style="width:5.12163in;height:3.35in" />

Double-click the imported file under Sheets to open it in the center document viewer.

<img src="../training-manual-media/media/image256.png" style="width:5.12163in;height:3.35in" />

This example links data to the AI00741 control module in the PAI sublist under Control Modules.

Select AI00741 to open the control-module details.

<img src="../training-manual-media/media/image257.png" style="width:5.12163in;height:3.35in" />

Select Parameters.

<img src="../training-manual-media/media/image258.png" style="width:5.12163in;height:3.35in" />

SPA displays the parameter-linking view.

<img src="../training-manual-media/media/image259.png" style="width:5.12163in;height:3.35in" />

Enter the required ACM parameter in Parameter Name.

Select the required parameter from the list of matches.

<img src="../training-manual-media/media/image260.png" style="width:5.12163in;height:3.35in" />

Select Add, then select the source cell.

<img src="../training-manual-media/media/image261.png" style="width:5.12163in;height:3.35in" />

SPA displays the following two link fields:

- Tagname Link: identifies the text that contains the current control module’s tag name. In this example, the tag name is AI00741.

- Parameter Link (Cfg_HiHiLim): identifies the source value for the selected ACM parameter. In this example, the value is 60 in the HiHi column.

> <img src="../training-manual-media/media/image262.png" style="width:5.12163in;height:3.35in" />
>
> Highlight AI00741 in the spreadsheet.
>
> <img src="../training-manual-media/media/image263.png" style="width:5.12163in;height:3.35in" />

Highlight the matching tag name under Tagname Link, then select the link button.

<img src="../training-manual-media/media/image264.png" style="width:5.12163in;height:3.35in" />

> Change the value under Parameter Link (Cfg_HiHiLim) to match the source table.
>
> <img src="../training-manual-media/media/image265.png" style="width:5.12163in;height:3.35in" />

Highlight the source value and the matching value under Parameter Link, then select the link button.

> <img src="../training-manual-media/media/image266.png" style="width:5.12163in;height:3.35in" />
>
> After linking the tag name and parameter value, select Done. SPA writes the source value, 60, to the Cfg_HiHiLim parameter of AI00741, then searches the current page for similar links.
>
> <img src="../training-manual-media/media/image267.png" style="width:5.12163in;height:3.35in" />
>
> The Pending Approvals button, highlighted below in red, shows the number of proposed links.
>
> <img src="../training-manual-media/media/image268.png" style="width:5.12163in;height:3.35in" />
>
> Select Pending Approvals.
>
> <img src="../training-manual-media/media/image269.png" style="width:5.12163in;height:3.35in" />
>
> SPA displays a list of proposed links. Select the header to expand it.
>
> <img src="../training-manual-media/media/image270.png" style="width:5.12163in;height:3.35in" />
>
> The Pending Approvals list.
>
> <img src="../training-manual-media/media/image271.png" style="width:5.12163in;height:3.35in" />
>
> The bottom of the Pending Approvals view contains Discard, Accept, and Accept All:

- Discard: removes the proposed link from the list.

- Accept: approves the link and writes the value to the ACM object parameter.

- Accept All: approves every proposed link.

> <img src="../training-manual-media/media/image272.png" style="width:5.12163in;height:3.35in" />
>
> Select Accept to approve one proposed link.
>
> <img src="../training-manual-media/media/image273.png" style="width:5.12163in;height:3.35in" />
>
> The approved item is removed from the list, and the data is written to ACM. Approved links appear under Subobjects in the selected control module.
>
> <img src="../training-manual-media/media/image274.png" style="width:5.12163in;height:3.35in" />
>
> Select Discard to remove a proposed link and its document highlight.
>
> <img src="../training-manual-media/media/image275.png" style="width:5.12163in;height:3.35in" />
>
> Select Accept All to approve every proposed link and clear the list.
>
> <img src="../training-manual-media/media/image276.png" style="width:5.12163in;height:3.35in" />
>
> <img src="../training-manual-media/media/image277.png" style="width:5.12153in;height:3.35in" />
>
> Accepted links appear under Parameters for their respective control modules.
>
> <img src="../training-manual-media/media/image278.png" style="width:6.5in;height:4.25in" />
