# -*- coding: utf-8 -*-
import ast
import io
import os
import codecs
import pickle
import configparser
import shutil
import subprocess
from typing import List
import numpy as np
import win32api
import sys
from PIL import Image
from xml.etree import ElementTree as ET
import re

from bin.gui_config_elements import direction_buttons
from bin.gui_hmi_graphic_view import hmi_graphic_view
from bin.logic_acm_console import ACM_Console
from bin.logic_acm_data_handler import ACM_Data_Handler
from bin.logic_acm_function_handler import acm_parameter_handler
from bin.logic_acm_libraries_retrieval import acm_libraries_retrieval, get_library_file_path
from bin.logic_acm_library_parser import acm_library_parser
from bin.logic_config import Config
from bin.logic_excel_exporter import excel_exporter
from bin.logic_export_approved_annotations import ApprovedAnnotationExporter
from bin.logic_hmi_display import HMI_Display
from bin.logic_internal_database import Database
from bin.logic_linked_graphic_scanner import Template_Flip, Template_Rotate
from bin.logic_pdf_export import pdf_with_data_exporter

from bin.logic_sql_database import db_connector
from bin.logic_svg_render import svg_bytes_to_png
from .logic_logger import logging

str_image = 'Image'
str_name = 'Name'
str_md5 = 'MD5'
str_figures = 'Figures'
str_roi = 'ROI'


def get_version_number():
    if not getattr(sys, 'frozen', False):
        return '0.0.1'

    # Must be the absolute path of the running exe: the app chdir()s into the
    # bundle directory, so a bare "runme.exe" no longer resolves.
    try:
        File_information = win32api.GetFileVersionInfo(os.path.abspath(sys.executable), "\\")
    except Exception:
        logging.warning('Unable to read version info from %s', sys.executable, exc_info=True)
        return '0.0.1'

    ms_file_version = File_information['FileVersionMS']
    ls_file_version = File_information['FileVersionLS']

    version_array =  [str(win32api.HIWORD(ms_file_version)), str(win32api.LOWORD(ms_file_version)),
            str(win32api.HIWORD(ls_file_version)), str(win32api.LOWORD(ls_file_version))]
    return ".".join(version_array)


def extract_lines():
    pass


def acm_safe_display_name(path, pno, taken_names):
    """ Build an ACM compliant display name from a drawing path and 0 based page number.

    :param path: The document path the display belongs to.
    :type path: str
    :param pno: The 0 based page number of the display.
    :type pno: int
    :param taken_names: Case folded names already in use, added to as names are handed out.
    :type taken_names: set
    :return: A unique name matching the ACM naming rules.
    :rtype: str
    """
    stem = os.path.splitext(os.path.basename(path))[0]
    stem = re.sub(r'[^A-Za-z0-9_]', '_', stem)
    stem = re.sub(r'_+', '_', stem).strip('_')

    if not stem:
        stem = 'Display'
    elif not re.match(r'^[a-zA-Z_]', stem):
        # ACM names may not start with a digit.
        stem = 'D_' + stem

    base = f'{stem}_P{pno + 1}'
    name = base
    suffix = 2
    while name.casefold() in taken_names:
        name = f'{base}_{suffix}'
        suffix += 1

    taken_names.add(name.casefold())
    return name


def build_auto_hmi_display(name, path, pno):
    """ Build an HMI display record for a page the user never drew a display on.

    :param name: The ACM compliant display name.
    :type name: str
    :param path: The document path the display belongs to.
    :type path: str
    :param pno: The 0 based page number of the display.
    :type pno: int
    :return: An HMI display record ready to be saved to the internal database.
    :rtype: dict
    """
    # No graphic was drawn for this display, so its linked graphics stay empty.
    return {
        'id': f'{pno}-0-0-0-0-{HMI_Display.PRIMARY_GRAPHIC_TYPE}-{name}',
        'name': name,
        'description': '',
        'change_user': os.getlogin(),
        'path': path,
        'pno': pno,
        'primary_linked_graphic': {},
        'secondary_linked_graphic': {},
        'linked_text': {},
        'page_links': [],
        'unlinked_page_links': [],
        'flow_direction': direction_buttons.NONE,
        'template_flip': []
    }


def find_pages_needing_hmi_displays(internal_db: Database):
    """ Find the scanned drawing pages that hold content but have no HMI display.

    :param internal_db: The internal database of the project.
    :type internal_db: Database
    :return: The (document path, 0 based page number) pairs a display could be built for.
    :rtype: List[tuple]
    """
    pages = []

    for document in internal_db.get_project_drawings():
        path = document.get('path')
        if not path:
            continue

        page_numbers = set()
        for item in (list(internal_db.get_all_control_module_in_document(path))
                     + list(internal_db.get_all_static_graphic_in_document(path))):
            if item.get('pno') is not None:
                page_numbers.add(item['pno'])

        for pno in sorted(page_numbers):
            if not internal_db.get_all_hmi_displays_on_page(path, pno):
                pages.append((path, pno))

    return pages


def auto_create_hmi_displays_for_scanned_pages(internal_db: Database):
    """ Create one HMI display for every scanned drawing page that holds content but has no display.

    :param internal_db: The internal database of the project.
    :type internal_db: Database
    :return: The names of the displays that were created.
    :rtype: List[str]
    """
    taken_names = {display['name'].casefold()
                   for display in internal_db.get_all_hmi_displays() if display.get('name')}
    created_names = []

    for path, pno in find_pages_needing_hmi_displays(internal_db):
        name = acm_safe_display_name(path, pno, taken_names)
        display = build_auto_hmi_display(name, path, pno)
        internal_db.save_hmi_display(display)
        internal_db.save_hmi_display_graphic_template(display)
        created_names.append(name)

    return created_names


def build_pages(progress_update_and_check_if_should_stop, acm_data_handler: ACM_Data_Handler, config, internal_db: Database, project_name,min_progress = 0, max_progress = 100):
    if not acm_data_handler.get_factory_talk_view_se_id():
        percentage = 0.0
        label = 'Creating HMI Server'
        if progress_update_and_check_if_should_stop('Creating HMI Server',label,percentage):
            return
        acm_console = ACM_Console(project_name, acm_data_handler, internal_db, config)
        acm_console.create_hmi_object()

    displays = internal_db.get_all_hmi_displays()
    for i in range(len(displays)):
        display = displays[i]
        display_object = HMI_Display(display['id'],
                                    display['name'],
                                    display['description'],
                                    display['pno'],
                                    None)
        display_object.setup_data_handler(acm_data_handler)
        display_object.setup_for_build(config, internal_db, display['path'], display['pno'], display['flow_direction'])
        display_object.build_display_to_acm()
        percentage = min_progress + ((i+1)/len(displays))*(max_progress-min_progress)
        label = 'Building Page '+str(i+1)+' of '+str(len(displays))
        if progress_update_and_check_if_should_stop(f'Creating HMI Display {display['name']} in ACM',label,percentage):
            break


def quick_build_hmi_page(path, pno, acm_data_handler: ACM_Data_Handler, config, internal_db: Database, project_name):
        
    display = internal_db.get_hmi_display_in_page(path, pno)
    
    display_object = HMI_Display(display['id'],
                                display['name'],
                                display['description'],
                                display['pno'],
                                None)
    display_object.setup_data_handler(acm_data_handler)
    display_object.setup_for_build(config, internal_db, display['path'], display['pno'], display['flow_direction'])
    display_object.build_display_to_acm()



def create_alarms(progress_update_and_check_if_should_stop, acm_data_handler: ACM_Data_Handler, config: Config
                , internal_db: Database, project_name, min_progress = 0, max_progress = 100):
    if not acm_data_handler.get_factory_talk_view_alarm_id():
        percentage = 0.0
        label = 'Creating Alarm Server'
        if progress_update_and_check_if_should_stop('Creating Alarm Server',label,percentage):
            return
        acm_console = ACM_Console(project_name, acm_data_handler, internal_db, config)
        acm_console.create_alarm_object()
        acm_data_handler.refresh_all_data()

    displays = internal_db.get_all_hmi_displays()
    library_id_to_parameters_to_write = {}
    for i in range(len(displays)):
        alarm_group_id = create_alarm_group(acm_data_handler, project_name, displays[i]['name'])
        control_modules = internal_db.get_all_control_module_on_page(displays[i]['path'],displays[i]['pno'])
        assign_control_modules_alarms_to_group(acm_data_handler, project_name, library_id_to_parameters_to_write, alarm_group_id, control_modules)
        percentage = min_progress + ((i+1)/len(displays))*(max_progress-min_progress)
        label = 'Building Alarms for Page '+str(i+1)+' of '+str(len(displays))
        if progress_update_and_check_if_should_stop(label,label,percentage):
            break



def assign_control_modules_alarms_to_group(acm_data_handler, project_name, library_id_to_parameters_to_write, alarm_group_id, control_modules):
    for control_module in control_modules:
        objects_df = acm_data_handler.get_all_objects_in_project()
        row = objects_df.loc[objects_df['Name'] == control_module['name']]
        if row.size == 0:
            continue
            # Get the LibraryID of the object
        control_module_id= str(row.index[0])
        library_id = row['LibraryID'].values[0]
        if library_id not in library_id_to_parameters_to_write:
                # Use the library parser to get the parameters of the object
            library_parser = parse_library_file(None,project_name,acm_data_handler,library_id)
            parameters = library_parser.get_parameters()
                # Get parameters that have the 'AlarmGroup' text within the Filter property 
            alarm_parameters = [k for k,v in parameters.items() if 'Filter' in v and 'AlarmGroup' in v['Filter']]
            library_id_to_parameters_to_write[library_id] = alarm_parameters
            
        for alarm_parameter in library_id_to_parameters_to_write[library_id]:
            acm_data_handler.write_parameter_value(alarm_group_id,control_module_id,alarm_parameter,acm_data_handler.REF_SUBOBJECT_TYPE)


def create_alarm_group( acm_data_handler: ACM_Data_Handler, project_name, page_name):

    ftv_alarm_object_id = acm_data_handler.get_factory_talk_view_alarm_id()
    library_parser = parse_library_file(ftv_alarm_object_id,project_name,acm_data_handler)
    subobjects = library_parser.get_all_subobjects()
    # Get the first subobject 
    subobject = list(subobjects.keys())[0]
    subobject_parameters = library_parser.get_subobject_parameters(subobject)
    
    # Use Name property of the subobject to create a new subobject
    # by check which parameters are string and of refence type immediate 
    parameters_used = extract_handle_bars(subobjects[subobject]['Name'])

    for parameter in parameters_used:
        if subobject_parameters[parameter]['DType'] == 'String' and subobject_parameters[parameter]['RType'] == 'Immediate':
            subobject_parameters[parameter]['DVal'] = page_name


    subobject_name = acm_data_handler.create_subobject(ftv_alarm_object_id,subobjects[subobject], subobject_parameters)
    return acm_data_handler.get_subobject_id(subobject_name,ftv_alarm_object_id)

def extract_handle_bars(text):
    pattern = r'{([^{}:]+)(?::[^{}]+)?}'
    variables = []

    matches = re.findall(pattern, text)
    for match in matches:
        variables.append(match.strip().strip('{').strip('}'))
    return variables


def parse_library_file(object_id, project_name,acm_data_handler:ACM_Data_Handler, library_id=None) -> acm_library_parser:
    if not library_id:
        library_id = acm_data_handler.get_object_library_id(object_id=object_id)
    library_file_path = get_library_file_path(library_id,project_name)
    if not library_file_path:
        projects_df = acm_data_handler.get_all_projects()
        acm_project_name = projects_df.loc[int(acm_data_handler.get_project_id())]['Name']
        acm_libraries_retrieval(project_name, acm_project_name,threaded=False)
        library_file_path = get_library_file_path(library_id,project_name)
    return acm_library_parser(library_file_path)


def start_build_hmi(progress_update_and_check_if_should_stop, acm_data_handler: ACM_Data_Handler, config: Config, internal_db
              , project_name, output_path):
    acm_console = ACM_Console(project_name, acm_data_handler, internal_db, config)
    if not acm_data_handler.get_factory_talk_view_se_id():
        percentage = 0.0
        label = 'Creating HMI Server'
        if progress_update_and_check_if_should_stop('Creating HMI Server',label,percentage):
            return
        
        acm_console.create_hmi_object()
        acm_data_handler.refresh_all_data()

    factory_talk_view_se_id = acm_data_handler.get_factory_talk_view_se_id()
    #factory_talk_view_se_name = acm_data_handler.get_object_name(factory_talk_view_se_id)
    hmi_display_template = config.get_hmi_display_template()
    acm_data_handler.write_parameter_value(hmi_display_template, factory_talk_view_se_id,'DisplayTemplate')

    if not internal_db.get_all_hmi_displays():
        created_names = auto_create_hmi_displays_for_scanned_pages(internal_db)
        if not created_names:
            progress_update_and_check_if_should_stop(
                'No HMI Displays are defined and no scanned page has content to build one from.'
                ,'No displays to build',100.0)
            return
        for i, created_name in enumerate(created_names):
            percentage = 5.0 + ((i+1)/len(created_names))*5.0
            if progress_update_and_check_if_should_stop(f'Created HMI Display {created_name}'
                                                       ,'Creating missing HMI Displays',percentage):
                return

    build_pages(progress_update_and_check_if_should_stop, acm_data_handler, config, internal_db, project_name, 10, 100)
    #acm_console.build_hmi(output_path,factory_talk_view_se_name,progress_update_and_check_if_should_stop,70)
    #export_images(progress_update_and_check_if_should_stop, internal_db, output_path + '/images', 80, 100)



def export_images(progress_update_and_check_if_should_stop, db:Database, output_path, min_progress=0, max_progress=100):
        static_graphics = db.get_all_static_graphic_templates()
        for i in range(len(static_graphics)):
            graphic = static_graphics[i]
            method = graphic['hmi_graphic']['method']

            path = ''
            if hmi_graphic_view.EXTRACT_GRAPHIC == method:
                path = graphic['hmi_graphic']['extract_graphic']['svg_image_path']
                if path == '': continue
            elif hmi_graphic_view.CUSTOM_GRAPHIC == method:
                path = graphic['hmi_graphic']['custom_graphic']['path']
            else:
                textbox_entry = 'Error Exproting '+graphic['name']
                label_text = ''
                percentage = min_progress + (len(static_graphics)/(i+1))*(max_progress-min_progress)
                if (i + 1) < len(static_graphics):
                    label_text = 'Error Exproting '+static_graphics[i+1]['name']
                    
                if progress_update_and_check_if_should_stop(textbox_entry, label_text, percentage):
                    break

                continue
            
            _, extension = os.path.splitext(path)
            # If the output path does not exist, create it
            if not os.path.exists(output_path):
                os.makedirs(output_path)
            shutil.copy(path, output_path+'/'+graphic['name']+extension)
            textbox_entry = 'Exported '+graphic['name']+extension
            label_text = ''
            percentage = (len(static_graphics)/(i+1))*100.0
            if (i + 1) < len(static_graphics):
                label_text = 'Exporting '+static_graphics[i+1]['name']+extension
                
            if progress_update_and_check_if_should_stop(textbox_entry, label_text, percentage):
                break


def export_reduced_images(progress_update_and_check_if_should_stop, db: Database, config: Config, output_path, min_progress=0, max_progress=100):
    """
    Export reduced images from the database.

    :param progress_update_and_check_if_should_stop: Function to update progress and check if the process should stop
    :type progress_update_and_check_if_should_stop: Callable
    :param db: Database instance
    :type db: Database
    :param config: Configuration instance
    :type config: Config
    :param output_path: Path to save the exported images
    :type output_path: str
    :param min_progress: Minimum progress percentage
    :type min_progress: int
    :param max_progress: Maximum progress percentage
    :type max_progress: int
    :return: None
    :rtype: None

    Export reduced images from the database and save them to the specified output path.
    """
    static_graphics = db.get_all_static_graphic_templates()
    display_width, display_height, _, __ = config.get_hmi_display_settings()

    def update_progress(textbox_entry, label_text, i):
        percentage = min_progress + (i / len(static_graphics)) * (max_progress - min_progress)
        return progress_update_and_check_if_should_stop(textbox_entry, label_text, percentage)

    for i in range(len(static_graphics)):
        graphic = static_graphics[i]
        method = graphic['hmi_graphic']['method']
        path = ''

        if hmi_graphic_view.EXTRACT_GRAPHIC == method:
            path = graphic['hmi_graphic']['extract_graphic']['svg_image_path']
        elif hmi_graphic_view.CUSTOM_GRAPHIC == method:
            if update_progress(f'Cannot export custom graphic {graphic["name"]}', f'Exporting {static_graphics[i+1]["name"]}' if (i + 1) < len(static_graphics) else '', i + 1):
                break
            continue
        else:
            if update_progress(f'Error Exporting {graphic["name"]}', f'Exporting {static_graphics[i+1]["name"]}' if (i + 1) < len(static_graphics) else '', i + 1):
                break
            continue

        try:
            reduce_svg_image(path, graphic, display_width, display_height)
        except ValueError as e:
            if update_progress(f'Error reducing image: {str(e)}', f'Exporting {static_graphics[i+1]["name"]}' if (i + 1) < len(static_graphics) else '', i + 1):
                break
            continue

        extension = '.svg'
        shutil.copy('out.svg', f'{output_path}/{graphic["name"]}{extension}')
        os.remove('in.bmp')
        os.remove('out.svg')

        if update_progress(f'Exported {graphic["name"]}{extension}', f'Exporting {static_graphics[i+1]["name"]}{extension}' if (i + 1) < len(static_graphics) else '', i + 1):
            break

            

def reduce_svg_image(svg_path, static_graphic, display_width, display_height):
    page_width = static_graphic['primary_linked_graphic']['page_width']
    page_height = static_graphic['primary_linked_graphic']['page_height']

    image_width = abs(static_graphic['primary_linked_graphic']['maxX'] - static_graphic['primary_linked_graphic']['minX'])
    image_height = abs(static_graphic['primary_linked_graphic']['maxY'] - static_graphic['primary_linked_graphic']['minY'])

    aspect_ratio = image_width/image_height

    # Scaling factor to increase the image size for potrace, larger resolution gives better results
    scaling = 8

    hmi_image_minX = static_graphic['primary_linked_graphic']['minX'] * display_width / page_width
    hmi_image_maxX = (static_graphic['primary_linked_graphic']['minX'] + (image_width * scaling)) * display_width / page_width
    hmi_image_width = abs(hmi_image_maxX - hmi_image_minX)
    hmi_image_maxY = static_graphic['primary_linked_graphic']['minY'] * display_height / page_height + (hmi_image_width / aspect_ratio)
    hmi_image_minY = static_graphic['primary_linked_graphic']['minY'] * display_height / page_height
    hmi_image_height = abs(hmi_image_maxY - hmi_image_minY)

    strokes_svg_string, fill_svg_string, stroke_color, fill_color = separate_svg_paths(svg_path)

    strokes_svg_string = apply_svg_simplification(strokes_svg_string, hmi_image_width, hmi_image_height)
    fill_svg_string = apply_svg_simplification(fill_svg_string, hmi_image_width, hmi_image_height)

    # Restore the original stroke color by add the property to all paths
    fill_svg_string = fill_svg_string.replace('<path', f'<path fill="{fill_color}"')
    
    # combine the two by taking the paths from the fill_svg_string and adding them to the strokes_svg_string
    stroke_paths = re.findall(r'<path[^>]+d="([^"]+)"[^>]*>', strokes_svg_string)
    for path in stroke_paths:
        fill_svg_string = fill_svg_string.replace('</g>', f'<path fill="{stroke_color}" d="{path}"/></g>')



    # Save svg to file
    with open('out.svg', 'w') as f:
        f.write(fill_svg_string)




def apply_svg_simplification(svg_string, hmi_image_width, hmi_image_height):
    image_data = svg_bytes_to_png(svg_string, output_width=hmi_image_width, output_height=hmi_image_height)
    image = Image.open(io.BytesIO(image_data))
    image.save('in.bmp')

    command = '''{} {} -b svg -o {}'''.format(r'Potrace\potrace-1.16.win64\potrace.exe','in.bmp', 'out.svg')

    try:
        subprocess.run(command, shell=True, check=True, capture_output=True, text=True) 
        # Return the svg string 
        return open('out.svg').read()  
         
    except subprocess.CalledProcessError as e:
        # If the command fails, print the error message
        raise ValueError('Error reducing image: '+str(e))
    
    

def separate_svg_paths(svg_path):
    """
    Separates SVG paths into two SVGs based on stroke definitions.
    One SVG will contain paths with strokes, the other will contain paths with stroke="none" and fills.
    
    Args:
        input_svg (str): Input SVG file content as string
    
    Returns:
        tuple: (stroked_svg, filled_svg) - Two SVG strings containing separated paths
    """
    # Parse the input SVG path
    root = ET.parse(svg_path).getroot()

    fill_color = ""
    stroke_color = ""
    
    # Get the SVG namespace if it exists
    ns = re.match(r'{.*}', root.tag).group(0)[1:-1] if '}' in root.tag else ''
    ns_prefix = f'{{{ns}}}' if ns else ''
    
    # Create new SVG roots with the same attributes as the original
    stroked_root = ET.Element(f'{ns_prefix}svg', root.attrib)
    filled_root = ET.Element(f'{ns_prefix}svg', root.attrib)


    # Add a white background to the SVG by add the attributes at the same viewBox as the root
    viewBox = root.get('viewBox').split(' ')
    background = ET.Element(f'{ns_prefix}rect', {'x': str(float(viewBox[0])-5)
                                                 , 'y': str(float(viewBox[1])-5)
                                                 , 'width': str(float(viewBox[2])+10)
                                                 , 'height': str(float(viewBox[3])+10)
                                                 , 'fill': 'white'})
    stroked_root.append(background)
    filled_root.append(background)

    
    # Copy non-path elements to both SVGs
    for child in root:
        if 'path' not in child.tag:
            stroked_root.append(ET.fromstring(ET.tostring(child)))
            filled_root.append(ET.fromstring(ET.tostring(child)))
    
    # Process paths and separate them
    for path in root.findall(f'.//{ns_prefix}path'):
        stroke = path.get('stroke', '')
        stroke_width = path.get('stroke-width', '')
        
        # Create a copy of the path
        path_copy = ET.fromstring(ET.tostring(path))
        
        # If stroke is explicitly "none" or not defined but has fill, add to filled SVG
        if stroke.lower() == 'none' or (not stroke and not stroke_width and path.get('fill')):
            fill_color = path_copy.get('fill', '')
            path_copy.set('fill','black')
            filled_root.append(path_copy)

        # If stroke is defined or implied, add to stroked SVG
        else:
            stroke_color = path_copy.get('stroke', '')
            path_copy.set('stroke','black')
            stroked_root.append(path_copy)
    
    # Convert back to string
    def svg_to_string(root):
        return ET.tostring(root, encoding='unicode')
    
    return svg_to_string(stroked_root), svg_to_string(filled_root),stroke_color, fill_color


def start_build_plc(progress_update_and_check_if_should_stop, acm_data_handler: ACM_Data_Handler, config: Config, internal_db
              , project_name, output_path ):
    acm_console = ACM_Console(project_name, acm_data_handler, internal_db, config)
    acm_console.build_plc(output_path,progress_callback=progress_update_and_check_if_should_stop)


def export_excel_with_data(progress_update_and_check_if_should_stop, path, filename, internal_db: Database, acm_data_handler:ACM_Data_Handler):

    exporter = excel_exporter(filename)

    static_graphics = internal_db.get_all_static_graphic_in_document(path)
    hmi_displays = internal_db.get_all_hmi_displays_in_document(path)

    acm_object = acm_data_handler.get_all_objects_in_project()
    control_modules = internal_db.get_all_control_module_in_document(path)

    control_module_types = set()
    control_module_types.add('Unassigned')

    for control_module in control_modules:
        row = None
        try:
            row = acm_object.loc[acm_object['Name'] == control_module['name']]
        except Exception as e:
            logging.warning('Error getting control module type for '+control_module['name']+': '+str(e))
                          
        if row is None or row.size == 0:
            control_module['type'] = 'Unassigned'
        else:
            control_module['type'] = row['CatalogNumber'].values[0]
            control_module_types.add(control_module['type'])

            

    number_of_control_modules = len(control_modules)

    types_to_export:List[str] = []

    for control_module_type in control_module_types:
        exporter.add_control_module_worksheet(control_module_type)
        if control_module_type not in types_to_export:
            types_to_export.append(control_module_type)

    if len(static_graphics) > 0 or len(hmi_displays) > 0:
        final_percentage = 80.0
    else:
        final_percentage = 100.0
        
    for control_modules_type in types_to_export:   
        control_modules_of_type = [cm for cm in control_modules if cm['type'] == control_modules_type]
        for i in range(len(control_modules_of_type)):
            control_module = control_modules_of_type[i]
            row = exporter.get_next_row(control_modules_type)
            exporter.write_to_cell(control_modules_type,row,0,control_module['name'])
            exporter.write_to_cell(control_modules_type,row,1,control_module['description'])
            exporter.write_to_cell(control_modules_type,row,2,control_modules_type)
            exporter.write_to_cell(control_modules_type,row,3,os.path.split(control_module['path'])[1])
            exporter.write_to_cell(control_modules_type,row,4,control_module['pno'] + 1)
            displays = internal_db.get_all_hmi_displays_on_page(path,control_module['pno'])
            if displays:
                exporter.write_to_cell(control_modules_type,row,5,displays[0]['name'])
            else:
                exporter.write_to_cell(control_modules_type,row,5,'Not defined') 
            
            if control_module['secondary_linked_graphic']:
                has_secondary_linked_graphic = 'True'
                linked_graphic = control_module['secondary_linked_graphic']
                rotation = get_final_template_rotation_angle(control_module['flow_direction'], linked_graphic['rotation'])
            else:
                has_secondary_linked_graphic = 'False'
                linked_graphic = control_module['primary_linked_graphic']
                rotation = 'Secondary Not Defined'

            exporter.write_to_cell(control_modules_type,row,6,linked_graphic['minX']/linked_graphic['page_width'],True)
            exporter.write_to_cell(control_modules_type,row,7,linked_graphic['minY']/linked_graphic['page_height'],True)
            exporter.write_to_cell(control_modules_type,row,8,has_secondary_linked_graphic)
            exporter.write_to_cell(control_modules_type,row,9,rotation)

            textbox_entry = control_module['name']
            label_text = 'Writing '+ control_modules_type

            percentage = ((i+1)/number_of_control_modules)*final_percentage

            if progress_update_and_check_if_should_stop(textbox_entry,label_text,percentage):
                break

    if len(hmi_displays) > 0:
        final_percentage = 90.0
    else:
        final_percentage = 100.0

    if len(static_graphics) > 0:
        exporter.add_static_graphic_worksheet('Static Graphics')
        for i in range(len(static_graphics)):
            static_graphic = static_graphics[i]
            row = exporter.get_next_row('Static Graphics')
            exporter.write_to_cell('Static Graphics',row,0,static_graphic['name'])
            exporter.write_to_cell('Static Graphics',row,1,static_graphic['description'])
            exporter.write_to_cell('Static Graphics',row,2,os.path.split(static_graphic['path'])[1])
            exporter.write_to_cell('Static Graphics',row,3,static_graphic['pno'] + 1)
            
            textbox_entry = static_graphic['name']
            label_text = 'Writing Static Graphics'
            
            percentage = ((i+1)/len(static_graphics))*final_percentage

            if progress_update_and_check_if_should_stop(textbox_entry,label_text,percentage):
                break

    if len(hmi_displays) > 0:
        exporter.add_hmi_display_worksheet('HMI Displays')
        for i in range(len(hmi_displays)):
            hmi_display = hmi_displays[i]
            row = exporter.get_next_row('HMI Displays')
            exporter.write_to_cell('HMI Displays',row,0,hmi_display['name'])
            exporter.write_to_cell('HMI Displays',row,1,hmi_display['description'])
            exporter.write_to_cell('HMI Displays',row,2,hmi_display['pno'] + 1)
            
            textbox_entry = hmi_display['name']
            label_text = 'Writing HMI Displays'
            
            percentage = ((i+1)/len(hmi_displays))*100.0

            if progress_update_and_check_if_should_stop(textbox_entry,label_text,percentage):
                break

    exporter.close()


def get_final_template_rotation_angle(template_rotation, linked_graphic_rotation:Template_Rotate):
    final_rotation = get_final_template_rotation(template_rotation, linked_graphic_rotation)

    final_rotation_angle = 90 * final_rotation

    return final_rotation_angle


def get_final_template_rotation(template_rotation, linked_graphic_rotation):
    if template_rotation == 4:
        final_rotation = 0
    else:
        final_rotation = template_rotation

    if linked_graphic_rotation != Template_Rotate.NONE.value:
        final_rotation = final_rotation + 1 + linked_graphic_rotation

    if final_rotation > 3:
            final_rotation = final_rotation - 4
            
    return final_rotation


def export_pdf_with_data(progress_update_and_check_if_should_stop, path,new_path, internal_db: Database):
    
    exporter = pdf_with_data_exporter(path)

    for i in range(exporter.get_number_of_pages()):

        build_page_pdf_with_control_module_data(path, internal_db, exporter, i)
        build_page_pdf_with_page_link_data(path, internal_db, exporter, i)
        
        textbox_entry = 'Built Page '+str(i + 1)
        label_text = 'Building Page '+str(i + 1)
        percentage = ((i+1)/exporter.get_number_of_pages())*100.0

        if progress_update_and_check_if_should_stop(textbox_entry,label_text,percentage):
            break
        
    exporter.export_pdf(new_path)


        

def build_page_pdf_with_control_module_data(path, internal_db, exporter:pdf_with_data_exporter, i):
    modules = internal_db.get_all_control_module_on_page(path,i)

    for module in modules:
        if not module['secondary_linked_graphic']:
            linked_graphic = module['primary_linked_graphic']
        else:
            linked_graphic = module['secondary_linked_graphic']

        point = [
                        linked_graphic['minX']/linked_graphic['page_width'],
                        linked_graphic['minY']/linked_graphic['page_height']
                    ]

        exporter.create_annotation(i,point,module['name'],module['description'])

    
def build_page_pdf_with_page_link_data(path, internal_db:Database, exporter:pdf_with_data_exporter, i):

    displays = internal_db.get_all_hmi_displays_on_page(path, i)

    for display in displays:
        if 'page_links' not in display:
            continue
        for page_link in display['page_links']:
            rect = (
                        page_link['minX']/page_link['page_width'],
                        page_link['minY']/page_link['page_height'],
                        page_link['maxX']/page_link['page_width'],
                        page_link['maxY']/page_link['page_height']
                    )
            exporter.create_page_link(page_link['pno'],rect,i)


def export_text_pdf_with_data(progress_update_and_check_if_should_stop, path, new_path, internal_db: Database):

    exporter = ApprovedAnnotationExporter(path, internal_db)

    try:
        number_of_pages = exporter.get_number_of_pages()

        for i in range(number_of_pages):

            exporter.process_page(i)

            textbox_entry = 'Built Page '+str(i + 1)
            label_text = 'Building Page '+str(i + 1)
            percentage = ((i+1)/number_of_pages)*100.0

            if progress_update_and_check_if_should_stop(textbox_entry,label_text,percentage):
                break

        exporter.save(new_path)
    finally:
        exporter.close()


TEXT_LINK_HEADERS = ['Tagname','Subobject','Parameter','Value','Document','Page','LLM Generated']


def export_text_excel_with_data(progress_update_and_check_if_should_stop, path, filename, internal_db: Database):

    exporter = excel_exporter(filename)

    worksheets = [
        ('Approved Links', internal_db.get_all_approved_text_links_by_document(path)),
        ('Unapproved Links', internal_db.get_all_unapproved_text_links_by_document(path)),
        ('Rejected Links', internal_db.get_all_rejected_text_links_by_document(path)),
    ]

    number_of_links = sum(len(text_links) for _, text_links in worksheets)

    written = 0
    stopped = False

    for worksheet_name, text_links in worksheets:
        exporter.add_worksheet_with_headers(worksheet_name, TEXT_LINK_HEADERS)

        if stopped:
            continue

        for text_link in text_links:
            tagname = write_text_link_rows(exporter, worksheet_name, text_link, path)

            written = written + 1
            label_text = 'Writing '+ worksheet_name
            percentage = (written/number_of_links)*100.0

            if progress_update_and_check_if_should_stop(tagname,label_text,percentage):
                stopped = True
                break

    if number_of_links == 0:
        progress_update_and_check_if_should_stop('No text links found','Writing Text Links',100.0)

    exporter.close()


def write_text_link_rows(exporter:excel_exporter, worksheet_name, text_link, path):
    """Writes one row per linked parameter, or a single row when the link has no parameters."""

    tagname = (text_link.get('tagname') or {}).get('text','')
    subobject = text_link.get('subobject_name','')
    document = os.path.split(path)[1]
    pno = text_link.get('pno')
    page = pno + 1 if isinstance(pno, int) else ''
    is_llm_generated = 'True' if text_link.get('is_llm_generated') else 'False'

    parameters = text_link.get('parameters') or {'': None}

    for parameter_name, parameter in parameters.items():
        row = exporter.get_next_row(worksheet_name)
        exporter.write_to_cell(worksheet_name,row,0,tagname)
        exporter.write_to_cell(worksheet_name,row,1,subobject)
        exporter.write_to_cell(worksheet_name,row,2,parameter_name)
        exporter.write_to_cell(worksheet_name,row,3,(parameter or {}).get('text',''))
        exporter.write_to_cell(worksheet_name,row,4,document)
        exporter.write_to_cell(worksheet_name,row,5,page)
        exporter.write_to_cell(worksheet_name,row,6,is_llm_generated)

    return tagname



def open_figures(imframe, path):
    """ Open ROI figures and show them on the canvas """
    parser = configparser.ConfigParser()  # create config parser
    parser.optionxform = lambda option: option  # preserve case for letters
    parser.read(path)  # read file with ROI figures
    """
    if parser[str_image][str_md5] != imframe.md5:  # check md5 sum
        raise Exception('Wrong polygons. MD5 sum of image and from selected file should be equal.')
    """
    roi = parser[str_figures][str_roi]  # get roi info
    roi = pickle.loads(codecs.decode(roi.encode(), 'base64'))  # unwrap roi info
    logging.info('Open ROI figures from: {}'.format(path))
    imframe.reset(roi)  # clear old and draw new polygons
