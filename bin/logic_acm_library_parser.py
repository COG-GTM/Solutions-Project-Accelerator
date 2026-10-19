import os
import xml.etree.ElementTree as ET

class acm_library_parser():
    '''
    A class that parses an ACM library XML file and extracts the library ID, parameters, subobjects, and functions.
    '''

    def __init__(self, xml_path) -> None:
        """
        Initializes the acm_library_parser object.

        Parameters:
        xml_path (str): The path to the XML file.

        Returns:
        None
        """
        self.__xml_path = xml_path 
        self.__parsed_xml = ET.parse(self.__xml_path)


    def get_library_ID(self):
        """
        Retrieves the library ID from the parsed XML.

        Returns:
            str: The library ID.
        """
        id = self.__parsed_xml.find("./DefinitionData").attrib['Id']
        return id.replace('DefinitionData','')       


    def get_parameters(self, ):
        """ Get all the parameters and parameter properties as a dictionaries of dictionaries
         e.g.   {
                    Cfg_StartHornTime: {DVal: "2.0", DType:"Real", etc...},
                    Cfg_FullStallTime: {DVal: "15.0", DType:"Real", etc...},
                    Cfg_TransitStallTime: {DVal: "15.0", DType:"Real", etc...},
                } 
        """
        result = {}
        
        for elm in self.__parsed_xml.findall(".//Obj/"):
        
            elms = elm.attrib.copy()
            result.setdefault(elms['Name'],elms)

        return result
    

    def get_most_likely_parameters(self, list_of_substrings, data_type=None):
        """
        Finds the most likely parameter names based on a list of substrings and an optional data type.

        Parameters:
            list_of_substrings (list): A list of substrings to search for in parameter names.
            data_type (str, optional): The desired data type of the parameter. Defaults to None
        Returns:
            list: A list of parameter names that match the criteria.
        """
        parameters = self.get_parameters()
        matched_parameters = []

        for param_name, param_info in parameters.items():
            if all(substring.lower() in param_name.lower() for substring in list_of_substrings):
                if data_type is None or param_info.get('DType', '').lower() == data_type.lower():
                    matched_parameters.append(param_name)

        return matched_parameters


    def get_all_subobjects(self):
        """ Get all the parameters and parameter properties of a specific subject dictionaries of dictionaries
        
        e.g.   {
                    Index: {DVal: "0", DType:"Int", etc...},
                    ReferencedTag: {DVal: "", DType:"String", etc...},
                    Include_IOFault: {DVal: "1", DType:"Bool", etc...},
                } 
        
        """
        result = {}

        for elm in self.__parsed_xml.findall(".//SObjs/"):
            
            elms = elm.attrib.copy()
            result.setdefault(elms['DispName'],elms)          
            
        return result


    def get_subobject_parameters(self, subobject_display_name):
        """ Get all the parameters and parameter properties of a specific subject dictionaries of dictionaries
        
        e.g.   {
                    Index: {DVal: "0", DType:"Int", etc...},
                    ReferencedTag: {DVal: "", DType:"String", etc...},
                    Include_IOFault: {DVal: "1", DType:"Bool", etc...},
                } 
        """
        result = {}

        for elm in self.__parsed_xml.findall(".//SObj[@DispName='"+subobject_display_name+"']/"):
            
            elms = elm.attrib.copy()
            result.setdefault(elms['Name'],elms)          
            
        return result
    

    def get_functions_xmls(self, ):
        """
        Retrieves the XML elements representing the functions.
        Returns:
            list: A list of XML elements representing the functions.
        """

        return self.__parsed_xml.findall(".//Funcs/")



    def extract_object_NIBS(self, destination):
        """
        Extracts the NIBS object from the parsed XML and writes it to a file.

        Parameters:
        - destination (str): The destination directory where the file will be saved.

        Returns:
        - None
        """
        nibs = self.__parsed_xml.find(".//NIBS")
        nibs_string = ET.tostring(nibs,encoding='unicode')
        filename = os.path.basename(self.__xml_path)
        filename, _ = os.path.splitext(filename)
        with open(destination +'/'+ filename +".object_nibs", "w") as text_file:
            text_file.write(nibs_string)



    def extract_subobjects(self, destination):
        """
        Extracts subobjects from the parsed XML and writes them to a file.

        Parameters:
        - destination (str): The destination directory where the subobjects file will be saved.

        Returns:
        - None
        """
        subobjects = self.__parsed_xml.find(".//SObjs")
        subobjects_string = ET.tostring(subobjects,encoding='unicode')
        filename = os.path.basename(self.__xml_path)
        filename, _ = os.path.splitext(filename)
        with open(destination +'/'+ filename +".subobjects", "w") as text_file:
            text_file.write(subobjects_string)


    def extract_all_controller_programs(self):
        """
        Extracts all controller programs names from the parsed XML and returns them as a list.

     
        Returns:
        - list: A list of controller programs names.
        """
        controller_programs = self.__parsed_xml.find(".//Programs")
        controller_programs_list = []

        if controller_programs is None:
            return controller_programs_list

        for controller_program in controller_programs:
            controller_programs_list.append(controller_program.attrib['Name'])

        return controller_programs_list
    

    def extract_all_controller_tasks(self):
        """
        Extracts all controller tasks names from the parsed XML and returns them as a list.


        Returns:
        - list: A list of controller tasks names.
        """
        controller_tasks = self.__parsed_xml.find(".//Tasks")
        controller_tasks_list = []

        if controller_tasks is None:
            return controller_tasks_list

        for controller_task in controller_tasks:
            controller_tasks_list.append(controller_task.attrib['Name'])

        return controller_tasks_list
    

    def extract_all_display_templates(self):
        """
        Extracts all display templates names from the parsed XML and returns them as a list.

        Returns:
        - list: A list of display templates names.
        """
        display_templates_list = []
        display_template = self.__parsed_xml.find(".//Par[@Name='DisplayTemplate']")
        
        if display_template is not None and 'CVals' in display_template.attrib:
            # Get CVals and split by comma
            display_templates_list = display_template.attrib['CVals'].split(',')
            return display_templates_list
        
        else:
            return display_templates_list
        

    def extract_all_ft_view_se_symbols(self):
        """
        Extracts all FT View SE symbols from the parsed XML and returns them as a list.

        Found in 
        <FTView Id="FTViewEE8F50C4-5BB7-4A3F-A766-1F2885F85B6C">
            <Collections>
                <Collection Name="Substitutions">
                    <Items />
                        </Collection>
                            <Collection Name="SE Symbols">
                                <Items>
                                    <Item Name="Symbol1" />
                                    <Item Name="Symbol2" />
                                    <Item Name="Symbol3" />
                                </Items>
                            </Collection>

        Items look like this:
        <Item Name="GO_PVLV_SO" IncludeCondition="{SymbolStyle} = 0 AND {SymbolOrientation} = 0">
            <Attributes>
              <Attribute Name="Icons">
                <Value>String</Value>
              </Attribute>
            </Attributes>
        </Item>

        Returns:
        - list: A list of FT View SE symbols.
        """
        if hasattr(self, 'ft_view_se_symbols_list'):
            return self.ft_view_se_symbols_list
        
        ft_view_se_symbols = self.__parsed_xml.find(".//FTView/Collections/Collection[@Name='SE Symbols']/Items")
        self.ft_view_se_symbols_list = []

        if ft_view_se_symbols is not None:
            # Get CVals and split by comma
            for item in ft_view_se_symbols:
                if 'Name' in item.attrib:

                    value = item.find('Attributes/Attribute/Value').text if item.find('Attributes/Attribute/Value') is not None else ''
                    width, height = get_width_and_height(ET.fromstring(value))
                    data = {'Name': item.attrib['Name'],
                            'IncludeCondition': item.attrib.get('IncludeCondition', ''),
                            'Value': value,
                            'Width': width,
                            'Height': height}

                    self.ft_view_se_symbols_list.append(data)

            return self.ft_view_se_symbols_list
        else:
            return self.ft_view_se_symbols_list
        
def get_width_and_height(gfx_element):
    """
    Extracts the height and width from a given XML element. Also works for group elements.
    The height and width are expected to be attributes of the element.

    Args:
        gfx_element (xml.etree.ElementTree.Element): The XML element containing the height and width attributes.

    Returns:
        tuple: A tuple containing the height and width as integers.
    """
    height_str = gfx_element.attrib.get('height', "0")
    width_str = gfx_element.attrib.get('width', "0")
    height = int(height_str) if height_str.isdigit() else 0
    width = int(width_str) if width_str.isdigit() else 0

    # Check if the element is a group and has children
    if gfx_element.tag.lower() == 'group':
        for child in gfx_element:
            child_height, child_width = get_width_and_height(child)
            height = max(height, child_height)
            width = max(width, child_width)

    return width, height


def get_object_NIBS(xml_path):
    """
    Parses an XML file containing object NIBs and returns a dictionary of NIBs.
    Args:
        xml_path (str): The path to the XML file.
    Returns:
        dict: A dictionary of NIBs, where the key is the NIB name and the value is a dictionary of NIB attributes.
    """
    filename, _ = os.path.splitext(xml_path)

    result = {}

    nibs_tree = ET.parse(filename + ".object_nibs")
    nibs_root = nibs_tree.getroot()

    for elm in nibs_root:
        elms = elm.attrib.copy()
        result.setdefault(elms['Name'],elms)          
        
    return result


def get_subobjects(xml_path):
    """
    Parses an XML file containing subobjects and returns a dictionary of subobjects.
    Args:
        xml_path (str): The path to the XML file.
    Returns:
        dict: A dictionary of subobjects, where the key is the subobject name and the value is a dictionary of attributes.
    """
    filename, _ = os.path.splitext(xml_path)

    result = {}

    nibs_tree = ET.parse(filename + ".subobjects")
    nibs_root = nibs_tree.getroot()

    for elm in nibs_root:
        elms = elm.attrib.copy()
        result.setdefault(elms['Name'],elms)          
        
    return result

