import copy
import logging
from difflib import SequenceMatcher
import hashlib
import re
import uuid
import xml.etree.ElementTree as ET
import os
from typing import Dict, Optional, Union
from dataclasses import dataclass
from typing import Optional

try: 
    from bin.logic_acm_function_handler import extract_handle_bars, process_acm_variable
    from bin.logic_acm_data_handler import ACM_Data_Handler
    from bin.logic_acm_libraries_retrieval import acm_libraries_retrieval, get_library_file_path
    from bin.logic_acm_library_parser import acm_library_parser
    from bin.logic_gfx_to_svg import gfx_to_svg, parse_handlebars, AnchorDirection
    from bin.logic_safe_expression import UnsafeExpressionError, condition_variable_names, evaluate_include_condition
    from bin.logic_library_anchor_overrides import get_default_store as _get_anchor_override_store
except ImportError as e:
    from logic_acm_function_handler import extract_handle_bars, process_acm_variable
    from logic_acm_data_handler import ACM_Data_Handler
    from logic_acm_libraries_retrieval import acm_libraries_retrieval, get_library_file_path
    from logic_acm_library_parser import acm_library_parser
    from logic_gfx_to_svg import gfx_to_svg, parse_handlebars, AnchorDirection
    from logic_safe_expression import UnsafeExpressionError, condition_variable_names, evaluate_include_condition
    from logic_library_anchor_overrides import get_default_store as _get_anchor_override_store




PROCESS_5_HMI_DISPLAY_FT_VIEW_SE_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<gfx xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="Gfx-SE14.xsd">
    <displaySettings displayType="replace" position="specifyPositionInPixels" positionX="{DisplayLeft}" positionY="{DisplayTop}" securityCode="{DisplaySecurity}" backColor="#{DisplayBackColor}" titleBar="true" titleBarText="{DisplayTitle}" maximumTagUpdateRate="1" focusHighlightColor="lime" disableFocusHighlight="false" size="specifySizeInPixels" width="{DisplayWidth}" height="{DisplayHeight}" allowMultipleRunningCopies="false" cacheAfterDisplaying="false" sizeToMainWindow="false" showLastAcquiredValue="true" TrackScreenForNavigation="true" TrackName="" allowResizing="false" whenResized="scale" beepOnPress="false" highlightWhenCursorPassesOver="true" interactiveHighlightColor="black" displayOnScreenKeyboard="false" allowButtonActionOnError="true" fieldNotSelectedTextColor="black" fieldNotSelectedFillColor="white" fieldSelectedTextColor="black" fieldSelectedFillColor="white" fieldInErrorNotSelectedTextColor="black" fieldInErrorNotSelectedFillColor="red" fieldInErrorSelectedTextColor="white" fieldInErrorSelectedFillColor="red" startupCommand="" shutdownCommand="" useGradientStyle="false" endColor="teal" gradientStop="50" gradientDirection="gradientDirectionHorizontal" gradientShadingStyle="gradientHorizontalFromRight"/>
</gfx>
"""

# FTView SE's Gfx-SE14.xsd caps every graphic object's "name" attribute at 64
# characters; anything longer aborts the display import.
_MAX_ELEMENT_NAME_LENGTH = 64


def _ensure_xml_name_start(candidate: str) -> str:
    """
    FTView SE parses a graphic object's ``name`` as the XML ID datatype, which
    may not start with a digit ("A name was started with an invalid
    character."). Trimming a leading token such as ``Sep`` off
    ``Sep_22_morning_demo_controller...`` exposes one, so restore a legal start
    character.
    """
    if candidate[:1].isalpha() or candidate[:1] == '_':
        return candidate
    return '_' + candidate[:_MAX_ELEMENT_NAME_LENGTH - 1]


def _shorten_element_name(name: str, used: set) -> str:
    """
    Build a <= 64 character replacement for ``name`` that is not already in
    ``used``.

    Leading underscore-separated tokens are dropped one at a time, so the
    project/controller prefix is shed first and the readable tail - the object
    tag and the symbol member, e.g. ``LIC2001_msd_CmdSrcExceptions`` - survives.
    """
    tokens = name.split('_')
    candidate = name
    for index in range(1, len(tokens)):
        candidate = '_'.join(tokens[index:])
        if len(candidate) <= _MAX_ELEMENT_NAME_LENGTH:
            break

    if len(candidate) > _MAX_ELEMENT_NAME_LENGTH:
        candidate = candidate[-_MAX_ELEMENT_NAME_LENGTH:]

    candidate = _ensure_xml_name_start(candidate)

    attempt = 0
    unique = candidate
    while unique in used:
        attempt += 1
        digest = hashlib.blake2s(f"{name}#{attempt}".encode('utf-8'), digest_size=2).hexdigest()
        suffix = f"_{digest}"
        unique = candidate[:_MAX_ELEMENT_NAME_LENGTH - len(suffix)] + suffix

    return unique


PROCESS_LINE_TEMPLATE = """<line name="{name}" height="{height}" width="{width}" left="{left}" top="{top}" visible="true" wallpaper="false" toolTipText="" exposeToVba="notExposed" isReferenceObject="false" line="{line}" backStyle="solid" lineStyle="{lineStyle}" lineWidth="{lineWidth}" backColor="#{backColor}" foreColor="#{foreColor}" />"""

# Attributes for a stand-alone Static Graphic <image>. The geometric values stay
# as ACM-style handlebars so change_element_size / change_element_position (and,
# as a backstop, _scrub_unresolved_placeholders) resolve them the same way they do
# for library-sourced image symbols.
PROCESS_HMI_IMAGE_ATTRIBUTES = {
    "height": "{HeightFinal}",
    "width": "{WidthFinal}",
    "left": "{LeftFinal}",
    "top": "{TopFinal}",
    "visible": "true",
    "wallpaper": "false",
    "toolTipText": "",
    "exposeToVba": "notExposed",
    "isReferenceObject": "false",
    "imageBackStyle": "transparent",
    "imageBackColor": "white",
    "imageColor": "black",
    "imageBlink": "false",
    "description": "",
}


PROCESS_LINE_BREAK_TEMPLATE = """<rectangle name="{name}" height="{height}" width="{width}" left="{left}" top="{top}" visible="true" wallpaper="false" toolTipText="" exposeToVba="notExposed" isReferenceObject="false" backStyle="solid" backColor="teal" foreColor="black" lineStyle="solid" lineWidth="1" patternStyle="none" patternColor="black" endColor="white" gradientStop="50" gradientDirection="gradientDirectionHorizontal" gradientShadingStyle="gradientHorizontalFromRight">
        <animations>
            <animateColor expression="1" blinkRate="2">
                <color value="0" foreBehavior="solid" foreColor1="black" foreColor2="black" backBehavior="solid" backColor1="red" backColor2="red" fillColorMode="2" endColor="white" gradientStop="50" gradientDirection="gradientDirectionHorizontal" gradientShadingStyle="gradientHorizontalFromRight" fillEndColor="white" fillGradientStop="50" fillGradientDirection="gradientDirectionHorizontal" fillGradientShadingStyle="gradientHorizontalFromRight"/>
                <color value="1" foreBehavior="solid" foreColor1="#{color}" foreColor2="#{color}" backBehavior="solid" backColor1="#{color}" backColor2="#{color}" fillColorMode="2" endColor="white" gradientStop="50" gradientDirection="gradientDirectionHorizontal" gradientShadingStyle="gradientHorizontalFromRight" fillEndColor="white" fillGradientStop="50" fillGradientDirection="gradientDirectionHorizontal" fillGradientShadingStyle="gradientHorizontalFromRight"/>
            </animateColor>
        </animations>
    </rectangle>"""


@dataclass
class ElementMapItem:
    """Data class representing a mapping between a GFX element and ACM object."""
    catalog_number: str
    object_id: int
    controller_id: int
    xml_element: ET.Element  # ElementTree element
    library_id: str
    Cfg_PositionX: float
    Cfg_PositionY: float
    isPositioned: bool
    spa_id: Optional[str] = None  # Optional as it's only set when names differ
    hmi_symbol: Optional[str] = None  # Will be populated in extract_svg_images
    image_width: Optional[float] = None  # Width of the image if applicable
    image_height: Optional[float] = None  # Height of the image if applicable
    original_image_name: Optional[str] = None  # Original name of the image if applicable


class GfxFileEditor:
    """
    Class for opening and modifying FTView gfx files using ElementTree.
    Provides functionality to modify element positions and create lines.
    """
    
    def __init__(self,factory_talk_view_se_id:str, display_name:str, file_path: str
                 , acm_data_handler:ACM_Data_Handler, project_name: str, config=None
                 , library_parsers: Dict[str, acm_library_parser]=None
                 , use_express: bool = False):
        """
        Initialize the GfxFileEditor with a gfx file path.
        
        Args:
            factory_talk_view_se_id: ID of the FactoryTalk View SE instance
            display_name: Name of the display (for logging or identification)
            file_path: Path to the FTView gfx file
            export_path: Path to save the modified gfx file
            acm_handler: Instance of ACM_Data_Handler connected to the ACM database
            project_name: Name of the project (for library retrieval)
        """
        self.factory_talk_view_se_id = factory_talk_view_se_id
        self.display_name = display_name.replace('.xml', '')
        self.file_path = file_path
        self.acm_data_handler: ACM_Data_Handler = acm_data_handler
        self.project_name = project_name
        self.config = config 
        self.library_parsers: Dict[str, acm_library_parser] = library_parsers
        self.library_svg_images = {}
        self.use_express = use_express

        if not self.use_express:
            # Check if file exists
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")
            
            # Parse the XML file
            self.tree = ET.parse(file_path)
            self.root = self.tree.getroot()
            
            # Cache all elements for faster lookup
            self.all_elements = self._cache_elements()

        # Initialize library parsers and map elements to ACM objects
        self.element_map: Dict[str, ElementMapItem] = self.map_element_to_acm_object(acm_data_handler, factory_talk_view_se_id)

        # Extract SVG images from GFX library elements
        library_hmi_symbols = self.extract_svg_images()

        if not self.use_express:
            # Filter out children elements
            self.filter_child_elements(library_hmi_symbols)

        # Match GFX elements to library symbols
        self.match_elements_to_library_symbols(library_hmi_symbols)


    def get_library_parsers(self) -> Dict[str, acm_library_parser]:
        """
        Returns the dictionary of library parsers.
        
        Returns:
            Dictionary mapping library IDs to their respective acm_library_parser instances.
        """
        return self.library_parsers
    
    
    def extract_svg_images(self) -> Optional[ET.Element]:
        """
        Extracts SVG images from GFX library elements and maps them to the element map.
        This method populates the `library_svg_images` dictionary with SVG images for each GFX element.
        It also matches GFX elements to the element map based on their names.


        """
        library_hmi_symbols = {}
        library_parsers = copy.deepcopy(self.library_parsers)
        override_store = _get_anchor_override_store()
        for library_id, parser in library_parsers.items():
            list_of_hmi_symbols = parser.extract_all_ft_view_se_symbols()
            library_hmi_symbols[library_id] = list_of_hmi_symbols
            for hmi_symbol in list_of_hmi_symbols:
                svg_image, viewbox, anchors, border = gfx_to_svg(hmi_symbol['Value'])
                if viewbox:
                    _,_,width, height = viewbox
                else:
                    width = 0
                    height = 0

                # Apply user-defined anchor overrides (if any) on top of the
                # parser-derived anchors. Overrides fully replace the four
                # direction buckets - useful for PlantPAx libraries whose
                # symbols ship without `_Anchor_*` marker ellipses.
                override = override_store.get(library_id, hmi_symbol['Name'])
                if override is not None:
                    anchors = {
                        AnchorDirection.TOP:    [tuple(pt) for pt in override.get('top', [])],
                        AnchorDirection.BOTTOM: [tuple(pt) for pt in override.get('bottom', [])],
                        AnchorDirection.LEFT:   [tuple(pt) for pt in override.get('left', [])],
                        AnchorDirection.RIGHT:  [tuple(pt) for pt in override.get('right', [])],
                        AnchorDirection.ANY:    [],
                    }

                if library_id not in self.library_svg_images:
                    self.library_svg_images[library_id] = {}

                self.library_svg_images[library_id][hmi_symbol['Name']] = [svg_image,[width, height], anchors, border, hmi_symbol['Value']]

        return library_hmi_symbols


    def get_symbol_xml(self, library_id: str, symbol_name: str) -> Optional[str]:
        """
        Returns the raw FTView SE symbol XML string for a library symbol.

        Args:
            library_id: ID of the library the symbol belongs to
            symbol_name: Name of the HMI symbol
        Returns:
            The symbol XML string, or None if the symbol is unknown.
        """
        entry = self.library_svg_images.get(library_id, {}).get(symbol_name)
        if entry and len(entry) >= 5:
            return entry[4]
        return None


    def filter_child_elements(self, library_hmi_symbols):
        # Filter out children elements by checking if number 
        # of lines equals any of the library elements
        elements_to_remove = []
        for element_name, element in self.element_map.items():
            
            remove_element = True
            for hmi_symbol in library_hmi_symbols[element.library_id]:
                if 'Lines' not in hmi_symbol:
                    hmi_symbol['Lines'] = len(hmi_symbol['Value'].splitlines())
                if element.xml_element and hmi_symbol['Lines'] == self.get_element_text_lines(element.xml_element):
                    remove_element = False
                    break

            if remove_element and element.catalog_number not in ['Image', 'PageLink']:
                elements_to_remove.append(element_name)
                

        # Remove elements that are children of other elements
        for element_name in elements_to_remove:
            del self.element_map[element_name]


    def match_elements_to_library_symbols(self, library_hmi_symbols):
        # Match the list of gfx elements to the element map

        elements_to_remove = []
        shared_controllers = {}
        for element_name, element in self.element_map.items():
            variables = {}
            for hmi_symbol in library_hmi_symbols[element.library_id]:
                # If there is a IncludeCondition then use the IncludeCondition in the GFX element to match with the library elements
                # Conditional look like this: "{SymbolStyle} = 0 AND {SymbolOrientation} = 0 AND ({SymbolType} = 0 OR {SymbolType} = 1)"
                # Then use the acm_data_handler to get the values of these variables
                if 'IncludeCondition' in hmi_symbol and hmi_symbol['IncludeCondition']:
                    include_condition = hmi_symbol['IncludeCondition']
                    for var in condition_variable_names(include_condition):
                        if var not in variables:
                            variables[var] = self.acm_data_handler.get_parameter_in_object(element.object_id, var)

                    try:
                        include_symbol = evaluate_include_condition(include_condition, variables)
                    except UnsafeExpressionError as e:
                        logging.warning("Rejected IncludeCondition %r of HMI symbol %r for element %r: %s",
                                        include_condition, hmi_symbol.get('Name'), element_name, e)
                        include_symbol = False
                    if not include_symbol:
                        continue
                

                # If the IncludeCondition matches or IncludeCondition does not exist, check if the number of lines matches
                if not self.use_express and element.xml_element and hmi_symbol['Lines'] != self.get_element_text_lines(element.xml_element):
                    elements_to_remove.append(element_name)
                    break
                elif self.use_express:
                    # For express mode, we don't check the number of lines
                    self.get_object_xml_symbol(element_name, hmi_symbol['Value'], shared_controllers)
                    
                    element.hmi_symbol = hmi_symbol['Name']
                    break

                element.hmi_symbol = hmi_symbol['Name']
                break

        # Remove elements that are children of other elements
        for element_name in elements_to_remove:
            del self.element_map[element_name]


    def create_image_element(self, element_name, element) -> None:
        """
        Build the ``<image>`` XML for a Static Graphic that has no FTView SE
        symbol in its ACM library.

        Static Graphics are inserted into ACM by SPA under the "HMI Image"
        design-pattern library, which ships no graphic symbol, so
        :meth:`match_elements_to_library_symbols` finds nothing to attach. The
        element must still be emitted as a real ``<image>`` tag: ``<gfx>`` only
        accepts graphic tags, and anything else makes FTView SE reject the whole
        display on import.
        """
        try:
            image_name = self.acm_data_handler.get_parameter_in_object(element.object_id, 'ImageName')
        except IndexError:
            image_name = None

        element.original_image_name = image_name or element_name
        element.xml_element = ET.Element(
            'image',
            {'name': element_name, **PROCESS_HMI_IMAGE_ATTRIBUTES, 'imageName': element.original_image_name},
        )


    def get_object_xml_symbol(self, object_name: str, new_symbol_xml_string:str, shared_controller=None) -> str:

        """
        Changes the symbol XML string of an object in the GFX file.
        
        Args:
            object_name: Name of the object to change
            new_symbol_xml_string: New symbol XML string to set
        Returns:
            str: The updated XML string of the object
        """
        variables = extract_handle_bars(new_symbol_xml_string)

        element = self.element_map.get(object_name)

        processed_variables = {}
        for variable in variables:
            if any(special_char in variable for special_char in ['#', '.', '@']):
                continue

            if variable == 'ObjectName':
                processed_variables[variable] = object_name
                continue

            if variable == 'ControllerName' and shared_controller and element.controller_id in shared_controller:
                processed_variables[variable] = shared_controller[element.controller_id]['name']
                continue

            object_library_parser = self.library_parsers.get(element.library_id, None)
            
            
            value = process_acm_variable(variable, element.object_id, self.acm_data_handler, self.project_name
                                         , object_library_parser, shared_controller)
            if value:
                processed_variables[variable] = str(value)
                if variable == 'ControllerName' and shared_controller is not None:
                    if element.controller_id not in shared_controller:
                        shared_controller[element.controller_id] = {}
                    shared_controller[element.controller_id]['name'] = value

        
        xml_string = parse_handlebars(new_symbol_xml_string, variables=processed_variables, replace_unknown_vars=False)

        # Update the element's XML string
        element.xml_element = ET.fromstring(xml_string)

        if element.catalog_number == 'PageLink' and 'NavToDisplayName' not in processed_variables:
            self._make_page_link_inert(element.xml_element)

        if element.xml_element.tag == 'image':
            element.original_image_name = element.xml_element.get('imageName', '')


    def _make_page_link_inert(self, xml_element) -> None:
        """
        Strip the touch animation from a page link that has no navigation target.

        An empty ACM parameter is falsy, so it never reaches ``processed_variables`` and
        ``parse_handlebars(replace_unknown_vars=False)`` leaves the literal
        ``{NavToDisplayName}`` behind in ``Display "{NavToDisplayName}"``. Such a page link
        was never matched to a display, so the button must do nothing.

        The whole ``<animateTouch>`` node is removed rather than blanked: FTView SE rejects a
        touch animation with no press/repeat/release action and reports "An error occured
        while applying the 'animateTouch' animation ... This animation will be ignored" on
        import. An ``<animations>`` container left empty is removed too.
        """
        for parent in list(xml_element.iter()):
            touch_nodes = [child for child in parent if child.tag == 'animateTouch']
            for node in touch_nodes:
                parent.remove(node)

        for parent in list(xml_element.iter()):
            for child in list(parent):
                if child.tag == 'animations' and len(child) == 0:
                    parent.remove(child)


    def map_element_to_acm_object(self, acm_handler, factory_talk_view_se_id):
        """
        Maps GFX elements to ACM database objects by retrieving objects associated with the display.
        
        Args:
            acm_handler: Instance of ACM_Data_Handler connected to the ACM database
            factory_talk_view_se_id: ID of the FactoryTalk View SE instance
            
        Returns:
            Dictionary mapping element names to their catalog numbers and object IDs
        """
        element_map = {}
        

        # Get all objects from the ACM database for this display
        display_objects_df = acm_handler.get_display_objects(self.display_name, factory_talk_view_se_id)
        
        if display_objects_df.empty:
            print(f"No objects found for display: {self.display_name}")
            return element_map
        
        # Create a mapping of element names to their catalog numbers and object IDs
        for index, object_row in display_objects_df.iterrows():
            self.add_acm_element(element_map, index, object_row)
                    
   
        
        return element_map

    def add_acm_element(self, element_map, acm_id, object_row):
        object_id = acm_id
        object_name = object_row['Name']
        catalog_number = object_row['CatalogNumber']
        library_id = object_row['LibraryID']
        controller_id = object_row['ControllerID']

        xml_element = None

            # Check if this object name exists in our GFX elements
        if not self.use_express and object_name in self.all_elements:
            xml_element = self.all_elements[object_name]
            
            
            # If not found, try to find a similar element by name
        if not self.use_express and xml_element is None:
            for element_name, element in self.all_elements.items():
                if object_name in element_name:
                    xml_element = element
                    break

        x = (object_row['Cfg_PositionX'] if object_row['Cfg_PositionX']
                  else object_row['CenterX'] if object_row['CenterX'] 
                  else object_row['X1'] if object_row['X1'] else 0)
        y = (object_row['Cfg_PositionY'] if object_row['Cfg_PositionY']
                  else object_row['CenterY'] if object_row['CenterY']
                  else object_row['Y1'] if object_row['Y1'] else 0)
            
            

        element_map[object_name] = ElementMapItem(
                catalog_number=catalog_number,
                object_id=object_id,
                controller_id=controller_id,
                xml_element=xml_element,
                library_id=library_id,
                Cfg_PositionX=int(x),
                Cfg_PositionY=int(y),
                isPositioned=object_row['isPositioned'],
                spa_id=object_row.get('SolutionsProjectAcceleratorID', None)  # Optional, may not exist in all rows
            )

        if  object_row['X2'] and  object_row['Y2']:
            width = int(object_row['X2']) - int(x)
            height = int(object_row['Y2']) - int(y)
            element_map[object_name].image_width = width
            element_map[object_name].image_height = height

        if library_id not in self.library_parsers:
                # Initialize a parser for this library if not already done
            self.add_library_parser(library_id)

        if self.use_express and xml_element is None and catalog_number == 'Image':
            self.create_image_element(object_name, element_map[object_name])

        return element_map[object_name]


    def create_image_element(self, element_name, element) -> None:
        """
        Build the ``<image>`` XML for a Static Graphic that has no FTView SE
        symbol in its ACM library.

        Static Graphics are inserted into ACM by SPA under the "HMI Image"
        design-pattern library, which ships no graphic symbol, so
        :meth:`match_elements_to_library_symbols` finds nothing to attach. The
        element must still be emitted as a real ``<image>`` tag: ``<gfx>`` only
        accepts graphic tags, and anything else makes FTView SE reject the whole
        display on import.
        """
        try:
            image_name = self.acm_data_handler.get_parameter_in_object(element.object_id, 'ImageName')
        except IndexError:
            image_name = None

        element.original_image_name = image_name or element_name
        element.xml_element = ET.Element(
            'image',
            {'name': element_name, **PROCESS_HMI_IMAGE_ATTRIBUTES, 'imageName': element.original_image_name},
        )


    def get_element_text_lines(self, element):
        """
        Count the number of lines when the element is serialized to XML string.
        This includes the element and all its descendants.
        """
        # Convert element to string
        xml_string = ET.tostring(element, encoding='unicode')
        return len(xml_string.splitlines())
    

    
    def add_library_parser(self, library_id):
        """
        Adds a library parser for a specific library ID.
        
        Args:
            library_id: ID of the library to add
            acm_data_handler: Instance of ACM_Data_Handler connected to the ACM database
            
        Returns:
            None
        """
        library_file_path = get_library_file_path(library_id,self.project_name)
        if not library_file_path:
            projects_df = self.acm_data_handler.get_all_projects()
            acm_project_name = projects_df.loc[int(float(self.acm_data_handler.get_project_id()))]['Name']
            acm_libraries_retrieval(self.project_name, acm_project_name, threaded=False)
            library_file_path = get_library_file_path(library_id,self.project_name)
        self.library_parsers[library_id] = acm_library_parser(library_file_path)


    
    def _cache_elements(self) -> dict:
        """
        Cache all elements in the gfx file for faster lookup by name.
        
        Returns:
            Dictionary mapping element names to element objects
        """
        elements_by_name = {}
        
        # Find all elements that have a 'name' attribute and tag = 'group'
        for element in self.root.findall(".//*[@name]"):
            name = element.get("name")
            if name and element.tag == "group":
                elements_by_name[name] = element
        
        return elements_by_name
    
    def find_element_by_name(self, name: str) -> Optional[ET.Element]:
        """
        Find an element by its name attribute.
        
        Args:
            name: The name attribute to search for
            
        Returns:
            Element if found, None otherwise
        """
        return self.all_elements.get(name)
    
    
    def change_element_position(self, gfx_reference: str, left: Union[int, str], top: Union[int, str]) -> bool:
        """
        Change the position of an element or group by its name.
        
        Args:
            gfx_reference: Name of the element or group
            left: New left position
            top: New top position
            
        Returns:
            True if position was changed, False otherwise
        """
        if not self.use_express:
            element = self.find_element_by_name(gfx_reference)
        else:
            # In express mode, we use the element map directly
            element = self.element_map.get(gfx_reference)
        if element is None or element.xml_element is None:
            return False
        
        if element.xml_element.tag == 'image':
            xml = ET.tostring(element.xml_element, encoding='unicode')
            new_xml = xml.replace("{LeftFinal}", '0').replace("{TopFinal}", '0')
            element.xml_element = ET.fromstring(new_xml)

        
        # Get the smallest left and top in the xml
        min_left = float('inf')
        min_top = float('inf')
        
        # First, check the element itself
        if element.xml_element.get("left") is not None and element.xml_element.get("top") is not None:
            min_left = int(element.xml_element.get("left"))
            min_top = int(element.xml_element.get("top"))
        
        # Then check all children with left and top attributes
        for child in element.xml_element.findall(".//*[@left][@top]"):
            child_left = int(child.get("left", "0"))
            child_top = int(child.get("top", "0"))
            min_left = min(min_left, child_left)
            min_top = min(min_top, child_top)
        

        
        

        # Check if this is a group
        is_group = element.xml_element.tag.lower() == "group" 
        
        if is_group:
            # For groups, we need to calculate the offset and move all children
            old_left = int(element.xml_element.get("left", "0"))
            old_top = int(element.xml_element.get("top", "0"))

            # Convert position values to strings if they're not already
            left_str = str(int(left - min_left))
            top_str = str(int(top - min_top))
            
            # Calculate the offset
            offset_left = int(left_str) - old_left
            offset_top = int(top_str) - old_top
            
            # Update the group position
            #element.xml_element.set("left", left_str)
            #element.xml_element.set("top", top_str)
            
            # Update positions of all children
            for child in element.xml_element.findall(".//*[@left][@top]"):
                if child.tag.lower() == "group":
                    continue
                child_left = int(child.get("left", "0"))
                child_top = int(child.get("top", "0"))
                
                child.set("left", str(child_left + offset_left))
                child.set("top", str(child_top + offset_top))

            for child in element.xml_element.findall(".//*[@offsetWidth][@offsetHeight]"):
                if child.tag.lower() == "group":
                    continue
                child_offset_width = float(child.get("offsetWidth", "0"))
                child_offset_height = float(child.get("offsetHeight", "0"))

                child.set("offsetWidth", str(child_offset_width + offset_left))
                child.set("offsetHeight", str(child_offset_height + offset_top))

        else:
            # For simple elements, just update the position attributes
            element.xml_element.set("left", str(int(left)))
            element.xml_element.set("top", str(int(top)))
        
        return 
    
    
    
    def change_element_size(self, gfx_reference: str, width: Union[int, str], height: Union[int, str], filename_suffix: str = "") -> Optional[str]:
        """
        Change the size of a Static Graphic by simply replacing {HeightFinal} and {WidthFinal} in the XML.
        """

        if not self.use_express:
            element = self.find_element_by_name(gfx_reference)
        else:
            # In express mode, we use the element map directly
            element = self.element_map.get(gfx_reference)

        if element is None or element.xml_element is None:
            return 
        
        if element.xml_element.tag != 'image':
            return

        # Convert width and height to strings
        width_str = str(int(float(width)))
        height_str = str(int(float(height)))

        # Update the imageName 
        new_image_name = f"{element.original_image_name} {filename_suffix}"
        element.xml_element.attrib['imageName'] = new_image_name
        xml = ET.tostring(element.xml_element, encoding='unicode')
        
        new_xml = xml.replace("{HeightFinal}", height_str).replace("{WidthFinal}", width_str)

        element.xml_element = ET.fromstring(new_xml)
        return new_image_name
    

    def create_line(self, 
                    name: str,
                    x0: Union[int, str], 
                    y0: Union[int, str], 
                    x1: Union[int, str], 
                    y1: Union[int, str], 
                    line_width: Union[int, str] = 1, 
                    back_color: str = "#C6C6C6", 
                    fore_color: str = "#AAAAAA",
                    dash_dot: bool = False) -> ET.Element:
        """
        Create a line element in the gfx file.
        
        Args:
            x0: Starting x coordinate
            y0: Starting y coordinate
            x1: Ending x coordinate
            y1: Ending y coordinate
            line_width: Line width
            back_color: Line background color (as a string representing the color value)
            fore_color: Line foreground color (as a string representing the color value)
            dash_dot: Whether the line is dashed or dotted

        Returns:
            The created line element
        """
       
        line_width = int(float(line_width))

        # Convert all values to strings
        line = "{} {} {} {} ".format(str(int(x0)), str(int(y0)), str(int(x1)), str(int(y1)))
        width = str(abs(int(x1) - int(x0)) + line_width)
        height = str(abs(int(y1) - int(y0)) + line_width)
        top = str(min(int(y0 - line_width/2) , int(y1 - line_width/2)))
        left = str(min(int(x0 - line_width/2), int(x1 - line_width/2)))
        line_width = str(line_width)
        

        if dash_dot:
            lineStyle = "dashDot"
        else:
            lineStyle = "solid"

        # Create the line element
        line_element = ET.fromstring(PROCESS_LINE_TEMPLATE.format(
            name=name,
            height=height,
            width=width,
            left=left,
            top=top,
            line=line,
            lineWidth=line_width,
            backColor=back_color,
            foreColor=fore_color,
            lineStyle=lineStyle
        ))

        return line_element
    

    def create_line_break(self,
                            name: str,
                            x: Union[int, str],
                            y: Union[int, str],
                            width: Union[int, str] = 13,
                            height: Union[int, str] = 13,
                            color: str = "#E0E0E0") -> ET.Element:
        """        
        Create a line break element in the gfx file.
        
        Args:
            name: Name of the line break element
            x: X coordinate of the line break
            y: Y coordinate of the line break
            width: Width of the line break
            height: Height of the line break
            color: Color of the line break
        Returns:
            The created line break element
        """
        # Convert all values to strings
        x_str = str(int(float(x)))
        y_str = str(int(float(y)))
        width_str = str(int(float(width)))
        height_str = str(int(float(height)))
        # Create the line break element
        line_break_element = ET.fromstring(PROCESS_LINE_BREAK_TEMPLATE.format(
            name=name,
            height=height_str,
            width=width_str,
            left=x_str,
            top=y_str,
            color=color
        ))

        return line_break_element
    

    def save(self, output_path: Optional[str] = None) -> None:
        """
        Save the modified gfx file.
        
        Args:
            output_path: Path to save the file. If None, overwrites the original file.
        """
        save_path = output_path if output_path else self.file_path
        ET.indent(self.tree, space="\t", level=0)
        self.tree.write(save_path, encoding="utf-8", xml_declaration=True, pretty_print=True)
    
    def get_all_element_names(self) -> list:
        """
        Get a list of all element names in the gfx file.
        
        Returns:
            List of element names
        """
        return list(self.all_elements.keys())
    
    def get_element_attributes(self, name: str) -> dict:
        """
        Get all attributes of an element by name.
        
        Args:
            name: Name of the element
            
        Returns:
            Dictionary of element attributes or empty dict if element not found
        """
        element = self.find_element_by_name(name)
        if element is not None:
            return dict(element.attrib)
        return {}
    
    def export_display(self, material_lines, signal_lines, line_breaks, export_path):
        """
        Export the display to a gfx file.
        """
        
        if self.use_express:
            _, _, displayColor, _, _ = self.config.get_hmi_display_settings()
            display_df = self.acm_data_handler.get_display(self.display_name, self.factory_talk_view_se_id)
            # Get the variables for the display
            display_variables = {
                "DisplayLeft": display_df['DisplayLeft'].iloc[0],
                "DisplayTop": display_df['DisplayTop'].iloc[0],
                "DisplaySecurity": display_df['DisplaySecurity'].iloc[0],
                "DisplayBackColor": displayColor,
                "DisplayTitle": display_df['DisplayTitle'].iloc[0],
                "DisplayWidth": display_df['DisplayWidth'].iloc[0],
                "DisplayHeight": display_df['DisplayHeight'].iloc[0]
            }
            # Replace the variables in the template
            template = PROCESS_5_HMI_DISPLAY_FT_VIEW_SE_TEMPLATE.format(**display_variables)
            display = ET.fromstring(template.strip())


            self._create_lines(material_lines, signal_lines, line_breaks, display)

            for element_name, element in self.element_map.items():
                if element.xml_element is not None:
                    # Defensive: substitute any residual ACM template placeholders
                    # (e.g. {WidthFinal}, {HeightFinal}, {LeftFinal}, {TopFinal})
                    # so we never write invalid XML that FTView SE would reject on
                    # import. See _scrub_unresolved_placeholders for details.
                    self._scrub_unresolved_placeholders(element_name, element)
                    # Add the element to the root
                    display.append(element.xml_element)
                else:
                    # The FTView SE <gfx> content model only permits graphic
                    # tags (group/text/image/panel/...), so an unresolved
                    # element must be omitted rather than stubbed out.
                    print(
                        f"Skipping element '{element_name}' in display "
                        f"'{self.display_name}': no XML element was generated."
                    )

            self._enforce_name_length_limit(display)

            filename = f"{self.display_name}.xml"
            file_path = os.path.join(export_path, f"{self.display_name}.xml")
            # Save the modified display
            tree = ET.ElementTree(display)
            tree.write(file_path, encoding="utf-8", xml_declaration=True)
            return filename


    def _enforce_name_length_limit(self, display) -> None:
        """
        Shorten any ``name`` attribute longer than the 64 characters allowed by
        FTView SE's ``Gfx-SE14.xsd``.

        ACM builds object names by concatenating the project name, the
        controller name and the object name (plus the library symbol's own
        suffix), so a verbose project/controller name pushes nested symbol
        parts past the limit and FTView SE rejects the whole display on import
        with ``violates maxLength constraint of '64'``.

        The head of the name is trimmed a token at a time so the readable tail
        (object tag + symbol member, e.g. ``LIC2001_msd_CmdSrcExceptions``) is
        preserved. Names are only referenced from VBA, and SPA exports objects
        as ``exposeToVba="notExposed"``, so renaming is safe.
        """
        nodes = [node for node in display.iter() if node.get('name')]
        used = {node.get('name') for node in nodes
                if len(node.get('name')) <= _MAX_ELEMENT_NAME_LENGTH}

        renamed = 0
        for node in nodes:
            original = node.get('name')
            if len(original) <= _MAX_ELEMENT_NAME_LENGTH:
                continue
            shortened = _shorten_element_name(original, used)
            used.add(shortened)
            node.set('name', shortened)
            renamed += 1

        if renamed:
            print(
                f"WARNING [export_display] display '{self.display_name}': "
                f"{renamed} object name(s) exceeded the FTView SE "
                f"{_MAX_ELEMENT_NAME_LENGTH}-character limit and were shortened "
                f"before export. Consider using a shorter project or controller "
                f"name to keep the generated names readable."
            )


    # Attributes we scrub for residual ACM template placeholders. Attributes
    # are grouped by fallback source on the ElementMapItem so we can pull a
    # sensible value (or the last-resort default) without duplicating logic.
    _PLACEHOLDER_ATTR_FALLBACKS = (
        # (attribute name, ElementMapItem field, last-resort default)
        ("width",  "image_width",   "1"),
        ("height", "image_height",  "1"),
        ("left",   "Cfg_PositionX", "0"),
        ("top",    "Cfg_PositionY", "0"),
    )

    _PLACEHOLDER_PATTERN = re.compile(r"\{[A-Za-z_][A-Za-z0-9_]*\}")

    def _scrub_unresolved_placeholders(self, element_name, element):
        """
        Walk ``element.xml_element`` and any descendants, replacing any
        remaining ACM library template placeholders (e.g. ``{WidthFinal}``,
        ``{HeightFinal}``, ``{LeftFinal}``, ``{TopFinal}``) in the geometric
        attributes of ``<image>`` and ``<line>`` tags.

        These placeholders normally get substituted by
        :meth:`change_element_size` / :meth:`change_element_position` while
        the display canvas is being generated. If the corresponding canvas
        element was skipped (for example because the Static Graphic's SPA
        record or SVG file was missing), the placeholders survive into the
        exported XML and FTView SE rejects the display with an error like
        ``Error parsing '{WidthFinal}' as short datatype``.

        Fallback values come from the ``ElementMapItem`` when available
        (``image_width`` / ``image_height`` / ``Cfg_PositionX`` /
        ``Cfg_PositionY``); otherwise a safe default is used (``1`` for
        width/height, ``0`` for left/top).
        """
        xml_element = element.xml_element
        if xml_element is None:
            return

        # <image> and <line> are the two library-template tags that use
        # {LeftFinal}/{TopFinal}/{WidthFinal}/{HeightFinal} placeholders.
        target_tags = ("image", "line")
        nodes = []
        if xml_element.tag in target_tags:
            nodes.append(xml_element)
        for tag in target_tags:
            nodes.extend(xml_element.findall(f".//{tag}"))

        scrubbed = []
        for node in nodes:
            for attr, field, default in self._PLACEHOLDER_ATTR_FALLBACKS:
                value = node.get(attr)
                if value is None or not self._PLACEHOLDER_PATTERN.search(value):
                    continue
                fallback = getattr(element, field, None)
                if fallback is None:
                    resolved = default
                else:
                    try:
                        resolved = str(int(float(fallback)))
                    except (TypeError, ValueError):
                        resolved = default
                node.set(attr, resolved)
                scrubbed.append((node.tag, attr, value, resolved))

        if scrubbed:
            details = ", ".join(
                f"{tag}.{attr}={old!r}->{new!r}" for tag, attr, old, new in scrubbed
            )
            print(
                f"WARNING [export_display] '{element_name}' had unresolved "
                f"template placeholders that were substituted before export: "
                f"{details}. This usually means the source Static Graphic could "
                f"not be built (missing SPA record or SVG file)."
            )

    def _create_lines(self, material_lines, signal_lines, line_breaks, display):
        """
        Create line elements for material line, line breaks and signal lines 
        and add them to the display.

        Args:
            material_lines: List of material lines to create
            signal_lines: List of signal lines to create
            line_breaks: List of line breaks to create
            display: The display element to which the lines will be added
        """

        # Split horizontal lines and vertical lines
        material_horizontal_lines = [line for line in material_lines if line['y0'] == line['y1']]
        material_vertical_lines = [line for line in material_lines if line['x0'] == line['x1']]

        signal_horizontal_lines = [line for line in signal_lines if line['y0'] == line['y1']]
        signal_vertical_lines = [line for line in signal_lines if line['x0'] == line['x1']]

        _, _, displayColor, _,_ = self.config.get_hmi_display_settings()
        materialLineWidth, materialForeColor, _ = self.config.get_hmi_material_line_properties()
        signalLineWidth, signalLineColor, hasDot = self.config.get_hmi_signal_line_properties()

        for i, line in enumerate(material_vertical_lines):
                # Create a line element for each signal line
            line_element = self.create_line(
                    name="VerticalMaterialLine_" + str(i),
                    x0=line['x0'],
                    y0=line['y0'],
                    x1=line['x1'],
                    y1=line['y1'],
                    line_width=materialLineWidth,
                    back_color=displayColor,
                    fore_color=materialForeColor,
                    dash_dot=False
                )
            display.append(line_element)

        for i, line in enumerate(signal_vertical_lines):
                # Create a line element for each signal line
            line_element = self.create_line(
                    name="VerticalSignalLine_" + str(i),
                    x0=line['x0'],
                    y0=line['y0'],
                    x1=line['x1'],
                    y1=line['y1'],
                    line_width=signalLineWidth,
                    back_color=displayColor,
                    fore_color=signalLineColor,
                    dash_dot=hasDot
                )
            display.append(line_element)

        for i, line in enumerate(line_breaks):
                # Create a line break element for each line break
            line_break_element = self.create_line_break(
                    name="LineBreak_" + str(i),
                    x=line['x'] - int(materialLineWidth) * 3,
                    y=line['y'] - int(materialLineWidth) * 3,
                    width=int(materialLineWidth) * 6 + 1 ,
                    height=int(materialLineWidth) * 6 + 1,
                    color=displayColor
                )
            display.append(line_break_element)

        for i, line in enumerate(material_horizontal_lines):
                # Create a line element for each signal line
            line_element = self.create_line(
                    name="HorizontalMaterialLine_" + str(i),
                    x0=line['x0'],
                    y0=line['y0'],
                    x1=line['x1'],
                    y1=line['y1'],
                    line_width=materialLineWidth,
                    back_color=displayColor,
                    fore_color=materialForeColor,
                    dash_dot=False
                )
            display.append(line_element)

        for i, line in enumerate(signal_horizontal_lines):
                # Create a line element for each signal line
            line_element = self.create_line(
                    name="HorizontalSignalLine_" + str(i),
                    x0=line['x0'],
                    y0=line['y0'],
                    x1=line['x1'],
                    y1=line['y1'],
                    line_width=signalLineWidth,
                    back_color=displayColor,
                    fore_color=signalLineColor,
                    dash_dot=hasDot
                )
            display.append(line_element)

# Example usage
if __name__ == "__main__":
    # Replace with your actual gfx file path
    file_path = "example.gfx"
    export_path = "exported"

    try:
        # Initialize the editor
        editor = GfxFileEditor(file_path, "DisplayName", export_path)
        
        # Example: Change position of an element
        editor.change_element_position("ElementName", 100, 200)
        
        # Example: Create a line
        editor.create_line(10, 20, 30, 40, 2, "255", False)
        
        # Save the modified file
        editor.save("modified_example.gfx")
        
        print("File modified successfully!")
        
    except Exception as e:
        print(f"Error: {e}")
