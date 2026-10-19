import tkinter.font
from typing import Dict
import xlsxwriter
from xlsxwriter import worksheet
from xlsxwriter.worksheet import Worksheet

class excel_exporter:
    """
    The excel_exporter class is used to export data to an Excel workbook.
    """

    MIN_COLUMN_WIDTH = 10

    def __init__(self, filename) -> None:
        """
        Initializes the LogicExcelExporter class.

        :param filename: The filename of the Excel workbook.
        :type filename: str

        :return: None
        :rtype: None
        """
        self.__workbook = xlsxwriter.Workbook(filename)
        self.__worksheet_previous_row = {}
        self.__worksheet_column_width :Dict[str:[int]] = {}
        self.__font = tkinter.font.Font(family='Calibri', size=11)

    
    def add_control_module_worksheet(self, worksheet_name):
        """
        Adds a new worksheet to the workbook.

        :param worksheet_name: The name of the worksheet to be added.
        :type worksheet_name: str
        :return: None
        
        This function adds a new worksheet to the workbook with the specified name. If a worksheet with the same name already exists, the function does nothing.
        
        Example:
            >>> add_control_module_worksheet('Sheet1')
        """

        if self.__workbook.get_worksheet_by_name(worksheet_name):
            return

        worksheet = self.__workbook.add_worksheet(worksheet_name)
        cell_format = self.__workbook.add_format()
        cell_format.set_border()
        cell_format.set_bold()
        cell_format.set_bg_color('yellow')
        cell_format.set_rotation(90)
        worksheet.write(0,0,'Tagname',cell_format)
        worksheet.write(0,1,'Description',cell_format)
        worksheet.write(0,2,'Type',cell_format)
        worksheet.write(0,3,'Document',cell_format)
        worksheet.write(0,4,'Page',cell_format)
        worksheet.write(0,5,'Display Name',cell_format)
        worksheet.write(0,6,'Rel X Position',cell_format)
        worksheet.write(0,7,'Rel Y Position',cell_format)
        worksheet.write(0,8,'Secondary Linked Graphic Found',cell_format)
        worksheet.write(0,9,'Secondary Rotation',cell_format)
        self.__worksheet_previous_row[worksheet_name] = 0
        self.__worksheet_column_width[worksheet_name] = []


    def add_static_graphic_worksheet(self, worksheet_name):
        """
        Adds a new worksheet for static graphics to the workbook.

        :param worksheet_name: The name of the worksheet to be added.
        :type worksheet_name: str
        :return: None
        
        This function adds a new worksheet for static graphics to the workbook with the specified name. If a worksheet with the same name already exists, the function does nothing.
        """
        
        if self.__workbook.get_worksheet_by_name(worksheet_name):
            return
        
        worksheet = self.__workbook.add_worksheet(worksheet_name)
        cell_format = self.__workbook.add_format()
        cell_format.set_border()
        cell_format.set_bold()
        cell_format.set_bg_color('yellow')
        cell_format.set_rotation(90)
        worksheet.write(0,0,'Tagname',cell_format)
        worksheet.write(0,1,'Description',cell_format)
        worksheet.write(0,2,'Document',cell_format)
        worksheet.write(0,3,'Page',cell_format)
        self.__worksheet_previous_row[worksheet_name] = 0
        self.__worksheet_column_width[worksheet_name] = []

    
    def add_hmi_display_worksheet(self, worksheet_name):
        """
        Adds a new worksheet for HMI displays to the workbook.

        :param worksheet_name: The name of the worksheet to be added.
        :type worksheet_name: str
        :return: None
        
        This function adds a new worksheet for HMI displays to the workbook with the specified name. If a worksheet with the same name already exists, the function does nothing.
        """
        
        if self.__workbook.get_worksheet_by_name(worksheet_name):
            return
        
        worksheet = self.__workbook.add_worksheet(worksheet_name)
        cell_format = self.__workbook.add_format()
        cell_format.set_border()
        cell_format.set_bold()
        cell_format.set_bg_color('yellow')
        cell_format.set_rotation(90)
        worksheet.write(0,0,'Tagname',cell_format)
        worksheet.write(0,1,'Description',cell_format)
        worksheet.write(0,2,'Page',cell_format)
        self.__worksheet_previous_row[worksheet_name] = 0
        self.__worksheet_column_width[worksheet_name] = []


    def add_worksheet_with_headers(self, worksheet_name, headers):
        """
        Adds a new worksheet with an arbitrary header row to the workbook.

        :param worksheet_name: The name of the worksheet to be added.
        :type worksheet_name: str
        :param headers: The column headings to write into the first row.
        :type headers: list
        :return: None

        This function adds a new worksheet to the workbook with the specified name and header row.
        If a worksheet with the same name already exists, the function does nothing.

        Example:
            >>> add_worksheet_with_headers('Approved Links', ['Tagname','Parameter'])
        """

        if self.__workbook.get_worksheet_by_name(worksheet_name):
            return

        worksheet = self.__workbook.add_worksheet(worksheet_name)
        cell_format = self.__workbook.add_format()
        cell_format.set_border()
        cell_format.set_bold()
        cell_format.set_bg_color('yellow')
        cell_format.set_rotation(90)
        for column, header in enumerate(headers):
            worksheet.write(0,column,header,cell_format)
        self.__worksheet_previous_row[worksheet_name] = 0
        self.__worksheet_column_width[worksheet_name] = []


    def get_next_row(self, worksheet_name):
        """
        Returns the next row number for the specified worksheet.

        :param worksheet_name: The name of the worksheet.
        :type worksheet_name: str

        :return: The next row number.
        :rtype: int

        This function calculates the next row number by adding 1 to the previous row number for the specified worksheet.

        Example:
            >>> get_next_row('Sheet1')
            2
        """
        return self.__worksheet_previous_row[worksheet_name] + 1


    def write_to_cell(self,worksheet_name,row,column,value,percentage=False):
        """
        Writes a value to a specific cell in a worksheet.

        :param worksheet_name: The name of the worksheet.
        :type worksheet_name: str
        :param row: The row number of the cell.
        :type row: int
        :param column: The column number of the cell.
        :type column: int
        :param value: The value to be written to the cell.
        :type value: Any
        :param percentage: Indicates whether the value should be formatted as a percentage. Default is False.
        :type percentage: bool
        :return: None
        :rtype: None

        This function writes the specified value to the cell at the given row and column in the specified worksheet.
        If the percentage flag is set to True, the value will be formatted as a percentage before writing to the cell.

        Example:
            >>> write_to_cell('Sheet1', 1, 1, 0.75, percentage=True)
        """
        worksheet: Worksheet = self.__workbook.get_worksheet_by_name(worksheet_name)
        
        if percentage:
            cell_format = self.__workbook.add_format({'num_format':'0.00%'})
        else:
            cell_format = self.__workbook.add_format()
        
        cell_format.set_border()
        
        worksheet.write(row,column,value,cell_format)
        
        self.__auto_fit_column(worksheet_name, column, value, worksheet)
        self.__worksheet_previous_row[worksheet_name] = row


    def __auto_fit_column(self, worksheet_name, column, value, worksheet):
        """
        Auto fits the width of a column in the worksheet based on the value.

        :param worksheet_name: The name of the worksheet.
        :type worksheet_name: str
        :param column: The index of the column.
        :type column: int
        :param value: The value used to calculate the width of the column.
        :type value: Any
        :param worksheet: The worksheet object.
        :type worksheet: Worksheet
        :return: None
        :rtype: None

        This function calculates the width of a column based on the value and adjusts the column width accordingly in the worksheet.
        
        Example:
            >>> excel_exporter = excel_exporter('test.xlsx')
            >>> excel_exporter.add_control_module_worksheet('Sheet1')
            >>> worksheet = excel_exporter.get_worksheet('Sheet1')
            >>> excel_exporter.auto_fit_column('Sheet1', 0, 'Test', worksheet)
        """
        width = self.__font.measure(str(value) + ' ')/self.__font.measure('0')

        column_widths = self.__worksheet_column_width[worksheet_name]

        if len(column_widths)<(column+1):
            column_widths.append(self.MIN_COLUMN_WIDTH)
        if column_widths[column] < width:
            column_widths[column] = width
            worksheet.set_column(column,column,width)


    def close(self):
        """
        Closes the workbook.

        :return: None
        :rtype: None
        """
        self.__workbook.close()