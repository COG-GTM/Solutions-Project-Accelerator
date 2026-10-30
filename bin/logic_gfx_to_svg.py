from enum import Enum
import math
import xml.etree.ElementTree as ET
from typing import Dict, Any
import re
import ast
from svgpathtools import parse_path
from svgpathtools.path import transform

import numpy as np

try:
    from bin.logic_safe_expression import evaluate_arithmetic
except ImportError:
    from logic_safe_expression import evaluate_arithmetic

class AnchorDirection(str, Enum):
    """Enum defining different anchor types"""
    TOP = "top"
    BOTTOM = "bottom"
    LEFT = "left"
    RIGHT = "right"
    ANY = "any"
    INPUT = "input"

def parse_handlebars(text, variables=None, functions=None, replace_unknown_vars=True) -> str:
    """
    Parse and evaluate handlebar-like expressions in a string.
    Only processes expressions that are enclosed in quotes without any #.
    
    Args:
        text (str): String containing expressions like 'left="{Calc(41 + {Fn_PositionX})}"'
        variables (dict): Dictionary of variable names and their values
        functions (dict): Dictionary of function names and their implementations
    
    Returns:
        str: String with expressions replaced by their evaluated values, preserving quotes
        
    Note:
        - Only processes handlebar expressions enclosed in quotes without any #
        - Unknown variables are automatically replaced with 0.
        - Returns result with quotes preserved: left="41"
    """
    
    
    if variables is None:
        variables = {}

    # Default variables and functions
    variables.update({
        'Fn_PositionX': 0,
        'Fn_PositionY': 0,
        'CenterX': 0,
        'CenterY': 0,
        'SymbolWidth': 0,
        'SymbolHeight': 0,
        'LeftIndex': 0,
        'TopIndex': 0
    })

    if functions is None:
        functions = {
            'Calc': lambda x: x,  # Simply returns the calculated value
            'Max': max,
            'Min': min,
            'Abs': abs,
            'Round': round
        }
    
    def evaluate_expression(expr):
        """Safely evaluate a mathematical expression with variables and functions."""
        # Replace function calls
        for func_name, func in functions.items():
            if func_name in expr:
                # Handle function calls with parentheses
                pattern = rf'{func_name}\s*\((.*?)\)'
                matches = re.findall(pattern, expr)
                for match in matches:
                    try:
                        # Recursively evaluate the argument
                        arg_value = evaluate_expression(match)
                        result = func(arg_value)
                        expr = expr.replace(f'{func_name}({match})', str(result))
                    except:
                        pass
        
        # Replace variables (known variables first)
        for var_name, var_value in variables.items():
            expr = expr.replace(var_name, str(var_value))
        
        # Replace any remaining unknown variables with 0
        # Look for patterns that look like variable names (letters, numbers, underscores)
        unknown_vars = re.findall(r'\b[A-Za-z_][A-Za-z0-9_]*\b', expr)
        for var in unknown_vars:
            # Skip if it's a number or already processed
            if replace_unknown_vars and not var.isdigit() and var not in [str(v) for v in variables.values()]:
                expr = expr.replace(var, '0')
        
        # Arithmetic goes through a restricted AST evaluator; never eval().
        try:
            if any(op in expr for op in ['+', '-', '*', '/', '(', ')']):
                return evaluate_arithmetic(expr)
            else:
                return ast.literal_eval(expr)
        except:
            return expr  # Return original if evaluation fails
    


    # Process qualified expressions

    qualified_pattern = r'(\{[^{}#]*(?:\{[^{}#]*\}[^{}#]*)*\})'

    for match in re.finditer(qualified_pattern, text):
        # Find expressions that contain braces within quotes without any #
        
        if not match:
            break
            
        expression_part = match.group(1)  # everything inside the quotes that contains braces
        
        # Process nested braces in this expression part from inside out
        processed_expression = expression_part
        inner_iterations = 0
        while '{' in processed_expression and inner_iterations < 30:
            # Find innermost braces
            inner_pattern = r'\{([^{}]+)\}'
            if re.search(inner_pattern, processed_expression):
                def replace_inner(match):
                    content = match.group(1)
                    result = evaluate_expression(content)
                    if result == content:
                        return match.group(0)
                    return str(result)
                processed_expression = re.sub(inner_pattern, replace_inner, processed_expression)
            else:
                break
            inner_iterations += 1
        
        # Replace the original quoted expression with the processed one (keeping quotes)
        original_full = expression_part
        replacement_full = processed_expression
        text = text.replace(original_full, replacement_full, 1)
   
    return text


def gfx_to_svg(xml_string: str, passed_svg_elements=None) -> str:
    xml_string = parse_handlebars(xml_string)
    root = ET.fromstring(xml_string)
    is_root = False
    if passed_svg_elements is None:
        passed_svg_elements = []
        is_root = True
    svg_elements = passed_svg_elements

    left_anchors = []
    right_anchors = []
    top_anchors = []
    bottom_anchors = []
    
    for element in root.findall('./*'):
        if element.tag == 'group':
            # Handle groups recursively
            svg_elements = gfx_to_svg(ET.tostring(element, encoding='unicode'), svg_elements)[0]
        elif element.tag == 'ellipse' and '_Anchor_' in element.attrib.get('name',''):
            x = int(element.attrib.get('left', 0)) + int(element.attrib.get('width', 0)) // 2
            y = int(element.attrib.get('top', 0)) + int(element.attrib.get('height', 0)) // 2
            anchor_direction = determine_anchor_direction(element)
            if anchor_direction == AnchorDirection.LEFT:
                left_anchors.append((x, y))
            elif anchor_direction == AnchorDirection.RIGHT:
                right_anchors.append((x, y))
            elif anchor_direction == AnchorDirection.TOP:
                top_anchors.append((x, y))
            elif anchor_direction == AnchorDirection.BOTTOM:
                bottom_anchors.append((x, y))
        else:
            svg_element = convert_element_to_svg(element)
            if svg_element:
                svg_elements.append(svg_element)

    anchors = {
        AnchorDirection.LEFT: left_anchors,
        AnchorDirection.RIGHT: right_anchors,
        AnchorDirection.TOP: top_anchors,
        AnchorDirection.BOTTOM: bottom_anchors,
        AnchorDirection.ANY: []
    }
    
    if not is_root:
        return svg_elements, None, anchors, None
    
    list_of_elements = root.findall('.//*')

    if len(list_of_elements) == 0:
        return svg_elements, None, anchors, None
    
    # If list of elements does not contain any elements with 'left' or 'top' attributes, return empty SVG
    if not any('left' in e.attrib or 'top' in e.attrib for e in list_of_elements):
        return svg_elements, None, anchors, None

    
    # Determine SVG dimensions but dont include multistateIndicator
    left = min(int(e.attrib['left']) 
                for e in list_of_elements 
                if 'left' in e.attrib)
    
    top = min(int(e.attrib['top']) 
                for e in list_of_elements 
                if 'top' in e.attrib)
    
    width = max(int(e.attrib['left']) + int(e.attrib['width']) 
                for e in list_of_elements 
                if 'left' in e.attrib and 'width' in e.attrib) - left
    
    height = max(int(e.attrib['top']) + int(e.attrib['height']) 
                for e in list_of_elements 
                if 'top' in e.attrib and 'height' in e.attrib) - top

    border_left = min(int(e.attrib['left']) 
                        for e in list_of_elements 
                        if 'left' in e.attrib and e.tag != 'multistateIndicator' and e.tag != 'stringDisplay')
    
    # Calculate border dimensions excluding multistateIndicator and stringDisplay for border anchors
    border_top = min(int(e.attrib['top']) 
                        for e in list_of_elements 
                        if 'top' in e.attrib and e.tag != 'multistateIndicator' and e.tag != 'stringDisplay')
    
    border_width = max(int(e.attrib['left']) + int(e.attrib['width']) 
                        for e in list_of_elements 
                        if 'left' in e.attrib and 'width' in e.attrib and 
                        e.tag != 'multistateIndicator' and e.tag != 'stringDisplay') - border_left
    
    border_height = max(int(e.attrib['top']) + int(e.attrib['height']) 
                        for e in list_of_elements 
                        if 'top' in e.attrib and 'height' in e.attrib 
                        and e.tag != 'multistateIndicator' and e.tag != 'stringDisplay') - border_top

    

    # Readjust the x, y of the anchor points
    for direction, points in anchors.items():
        for i, (x, y) in enumerate(points):
            if direction == AnchorDirection.LEFT:
                anchors[direction][i] = (x - left, y - top)
            elif direction == AnchorDirection.RIGHT:
                anchors[direction][i] = (x - left, y - top)
            elif direction == AnchorDirection.TOP:
                anchors[direction][i] = (x - left, y - top)
            elif direction == AnchorDirection.BOTTOM:
                anchors[direction][i] = (x - left, y - top)

    # Add some padding
    padding = 4
    svg_width = width + padding
    svg_height = height + padding

    # Add SVG header and footer
    svg_elements.insert(0, '<svg xmlns="http://www.w3.org/2000/svg" version="1.1"'
                        +' width="{}" height="{}" viewBox="{} {} {} {}">'.format(svg_width, svg_height, left, top, width, height))
    # Close SVG tag
    svg_elements.append('</svg>')

    border_to_left = border_left - left
    border_to_top = border_top - top

    return '\n'.join(svg_elements), (left, top, width, height), anchors, (border_to_left, border_to_top, border_width, border_height)

def determine_anchor_direction(element):

    color = element.attrib.get('backColor', '').lower()

    if color == 'red':
        return AnchorDirection.LEFT
    elif color == 'green':
        return AnchorDirection.RIGHT
    elif color == 'blue':
        return AnchorDirection.TOP
    elif color == 'yellow':
        return AnchorDirection.BOTTOM
    elif color == 'black':
        return AnchorDirection.ANY
    
    return None

def convert_element_to_svg(element: ET.Element) -> str:
    tag = element.tag
    attrs = element.attrib
    
    svg_converters = {
        'arc': convert_arc,
        'ellipse': convert_ellipse,
        'freehand': convert_freehand,
        'line': convert_line,
        'polygon': convert_polygon,
        'polyline': convert_polyline,
        'rectangle': convert_rectangle,
        'roundedRectangle': convert_rounded_rectangle,
        'wedge': convert_wedge,
        'text': convert_text,
        'image': convert_image,
        'stringDisplay': convert_string_display,
        'numericDisplay': convert_numeric_display
    }

    converter = svg_converters.get(tag)
    if converter:
        svg = converter(attrs)

        # If the element has a transform child, apply the transformation
        svg = apply_transform_to_element(svg, element, attrs)

        return svg
    return ''


def apply_transform_to_element(element_svg: str, element: ET.Element, element_attrs: Dict[str, Any]) -> str:
    """
    Apply transform to an existing SVG element string.
    
    Args:
        element_svg: The SVG element string (e.g., from convert_rectangle, convert_wedge)
        transform_attrs: Transform attributes dictionary
        element_attrs: Attributes of the SVG element (to determine original width/height if needed)
    
    Returns:
        SVG element string with transform applied
    """
    
    transform_matric = convert_transform(element, element_attrs)

    if element.tag == 'arc' or element.tag == 'wedge':
        # Invert the y-axis for arcs and wedges
        inverse_y_matric = np.array([[1, 0, 0], [0, -1, 0], [0, 0, 1]])
        transform_matric = transform_matric @ inverse_y_matric

    # If the transform matrix is identity, no need to apply any transformation
    if np.array_equal(transform_matric, np.eye(3)):
        return element_svg

    # Fit the path to the bounding box of the element
    adjusted_matrix = fit_path_to_bbox(element_svg, transform_matric, element_attrs, maintain_aspect_ratio=False, center=True)

    transform_str = (f"matrix({adjusted_matrix[0, 0]}, {adjusted_matrix[1, 0]}, "
                                f"{adjusted_matrix[0, 1]}, {adjusted_matrix[1, 1]}, "
                                f"{adjusted_matrix[0, 2]}, {adjusted_matrix[1, 2]})")
    transform_str = transform_str.replace('\n', ' ')
    
    
    # Insert transform attribute before the closing />
    if element_svg.endswith('/>'):
        return element_svg[:-2] + f' transform="{transform_str}"/>'
    elif element_svg.endswith('>'):
        return element_svg[:-1] + f' transform="{transform_str}">'
    else:
        return element_svg
    


def convert_transform(element: ET.Element, element_attrs: Dict[str, Any]) -> str:
    """
    Convert FactoryTalk View transform attributes to SVG transform string.
    
    Args:
        element: The original element from the XML tree
        element_attrs: Attributes of the SVG element (to determine original width/height if needed)

    Returns:
        SVG transform attribute string
    """

    transform_element = element.find('transform')

    if transform_element is None:
        return np.eye(3)  # Identity matrix if no transform is present

    transform_attrs = {k: v for k, v in transform_element.attrib.items() if k in ['scaleWidth', 'scaleHeight'
                                                                                  , 'shearWidth', 'shearHeight'
                                                                                  , 'offsetWidth', 'offsetHeight']}

    # Handle scaling and flipping
    width = float(element_attrs.get("width"))
    height = float(element_attrs.get("height"))
    scale_x  = float(transform_attrs.get("scaleWidth", 1))
    scale_y = float(transform_attrs.get("scaleHeight", 1))
    shear_x = float(transform_attrs.get('shearWidth', 0))
    shear_y = float(transform_attrs.get('shearHeight', 0))

    norm_scale_x = scale_x / width * 2
    norm_scale_y = scale_y / height * 2
    norm_shear_x = shear_x / width * 2
    norm_shear_y = shear_y / height * 2


    # Construct 3x3 transformation matrix
    # FactoryTalk appears to use: [scaleX, shearX; shearY, scaleY]
    # SVG matrix(a, b, c, d, e, f) = [a c e; b d f; 0 0 1]
    # So: a=scaleX, b=shearY, c=shearX, d=scaleY, e=offsetX, f=offsetY
    
    a = norm_scale_x
    b = norm_shear_y  
    c = norm_shear_x
    d = norm_scale_y
    e = 0
    f = 0

    numpy_matrix = np.array([[a, c, e], [b, d, f], [0, 0, 1]])

    return numpy_matrix


def fit_path_to_bbox(transformed_path, transform_matrix, element_attrs, 
                     maintain_aspect_ratio=False, center=True):
    """
    Adjusts the transformation matrix of an SVG path to fit within a specified bounding box.
    
    Parameters:
    -----------
    path : svgpathtools.Path or str
        The SVG path object or path string to be fitted
    transform_matrix : numpy.ndarray or list
        Current 2D transformation matrix (3x3 or 2x3 format)
    target_left : float
        Left coordinate of target bounding box
    target_top : float
        Top coordinate of target bounding box  
    target_width : float
        Width of target bounding box
    target_height : float
        Height of target bounding box
    maintain_aspect_ratio : bool, default=True
        Whether to maintain the original aspect ratio of the path
    center : bool, default=True
        Whether to center the path within the bounding box
        
    Returns:
    --------
    numpy.ndarray
        New 3x3 transformation matrix that fits the path to the target bbox
    """

    target_width = float(element_attrs.get("width"))
    target_height = float(element_attrs.get("height"))
    target_left = float(element_attrs.get("left", 0))  # Default left to 0 if not provided
    target_top = float(element_attrs.get("top", 0))
    
    # Parse path string if needed
    if isinstance(transformed_path, str):
        # Get path substring from the SVG element
        transformed_path = transformed_path.strip().split('d="')[1].split('"')[0]
        # Remove any /n or \r characters
        transformed_path = transformed_path.replace('\n', '').replace('\r', '')
        transformed_path = parse_path(transformed_path)
        
    
    # Convert transform matrix to numpy array and ensure it's 3x3
    if isinstance(transform_matrix, list):
        transform_matrix = np.array(transform_matrix)

    transformed_path = transform(transformed_path, transform_matrix)
    
    if transform_matrix.shape == (2, 3):
        # Convert 2x3 to 3x3 affine matrix
        full_matrix = np.array([
            [transform_matrix[0, 0], transform_matrix[0, 1], transform_matrix[0, 2]],
            [transform_matrix[1, 0], transform_matrix[1, 1], transform_matrix[1, 2]],
            [0, 0, 1]
        ])
    elif transform_matrix.shape == (3, 3):
        full_matrix = transform_matrix.copy()
    else:
        raise ValueError("Transform matrix must be 2x3 or 3x3")
    
    
    # Get bounding box of the transformed path
    xmin, xmax, ymin, ymax = transformed_path.bbox()
    current_width = xmax - xmin
    current_height = ymax - ymin
    
    # Calculate scale factors
    scale_x = target_width / current_width if current_width > 0 else 1
    scale_y = target_height / current_height if current_height > 0 else 1
    
    # Maintain aspect ratio if requested
    if maintain_aspect_ratio:
        scale = min(scale_x, scale_y)
        scale_x = scale_y = scale
    
    # Calculate the scaled dimensions
    scaled_width = current_width * scale_x
    scaled_height = current_height * scale_y
    
    # Calculate translation to position the path
    if center:
        # Center within the target bounding box
        translate_x = target_left + (target_width - scaled_width) / 2 - (xmin * scale_x)
        translate_y = target_top + (target_height - scaled_height) / 2 - (ymin * scale_y)
    else:
        # Align to top-left of target bounding box
        translate_x = target_left - (xmin * scale_x)
        translate_y = target_top - (ymin * scale_y)
    
    # Create the adjustment transformation matrix
    adjustment_matrix = np.array([
        [scale_x, 0, translate_x],
        [0, scale_y, translate_y],
        [0, 0, 1]
    ])
    
    # Combine with the original transformation
    final_matrix = adjustment_matrix @ full_matrix
    
    return final_matrix


def convert_arc(attrs: Dict[str, Any]) -> str:
    """
    Convert FactoryTalk View arc to SVG path.
    """
    start_angle = float(attrs['startAngle'])
    end_angle = float(attrs['endAngle'])
    
    # Handle special case: full circle (start == end and both are 0)
    if start_angle == end_angle and start_angle == 0:
        cx = float(attrs['left'] + attrs['width'] / 2)
        cy = float(attrs['top'] + attrs['height'] / 2)
        rx = float(attrs['width'] / 2)
        ry = float(attrs['height'] / 2)
        return create_svg_ellipse(attrs, cx, cy, rx, ry)
    
    # Calculate the actual ellipse dimensions and center to fit the arc in the bounding box
    ellipse_params = calculate_ellipse_from_arc_bounds(
        float(attrs['left']), float(attrs['top']), float(attrs['width']), float(attrs['height']),
        start_angle, end_angle
    )
    
    # Convert angles and create path
    path_data = create_arc_path(
        ellipse_params['cx'], ellipse_params['cy'], 
        ellipse_params['rx'], ellipse_params['ry'], 
        start_angle, end_angle
    )

    if attrs['backStyle'] == 'transparent':
        attrs['backColor'] = 'none'
    
    return f'<path d="{path_data}" fill="{attrs["backColor"]}" stroke="{attrs["foreColor"]}" stroke-width="{attrs["lineWidth"]}" stroke-linecap="round" paint-order="stroke"/>'


def calculate_ellipse_from_arc_bounds(left: float, top: float, width: float, height: float, 
                                    start_angle: float, end_angle: float) -> Dict:
    """
    Calculate ellipse parameters where the arc segment fits within the given bounds.
    
    FactoryTalk View appears to define width/height as the bounding box of the 
    actual arc segment, not the full ellipse.
    """
    # Calculate the angular extents of the arc
    angles = [start_angle, end_angle]
    
    # Handle boundary crossing case (when end_angle < start_angle)
    actual_end_angle = end_angle
    if end_angle < start_angle:
        actual_end_angle = end_angle + 2 * math.pi
    
    # Add quadrant boundaries that fall within the arc range
    quadrant_angles = [0, math.pi/2, math.pi, 3*math.pi/2, 2*math.pi]
    for qa in quadrant_angles:
        # Check if this quadrant angle falls within our arc range
        if start_angle <= qa <= actual_end_angle:
            angles.append(qa)
    
    # Calculate the extent of the arc in unit circle coordinates
    x_coords = [math.cos(a) for a in angles]
    y_coords = [math.sin(a) for a in angles]
    
    arc_x_min, arc_x_max = min(x_coords), max(x_coords)
    arc_y_min, arc_y_max = min(y_coords), max(y_coords)
    
    arc_x_range = arc_x_max - arc_x_min
    arc_y_range = arc_y_max - arc_y_min
    
    # Calculate required ellipse radii to fit the arc in the bounding box
    if arc_x_range > 0.001:
        rx = width / arc_x_range
    else:
        rx = width / 2
        
    if arc_y_range > 0.001:
        ry = height / arc_y_range
    else:
        ry = height / 2
    
    # Calculate the center position
    # The arc's bounding box center should align with the given left/top + width/2, height/2
    arc_center_x = (arc_x_min + arc_x_max) / 2
    arc_center_y = (arc_y_min + arc_y_max) / 2
    
    # Position the ellipse center so the arc segment appears at left/top
    cx = left + width/2 - arc_center_x * rx
    cy = top + height/2 - arc_center_y * ry
    
    return {
        'cx': cx,
        'cy': cy,
        'rx': rx,
        'ry': ry
    }

def create_svg_ellipse(params: Dict, cx: float, cy: float, rx: float, ry: float) -> str:
    """Create a full ellipse SVG element."""

    if params['backStyle'] == 'transparent':
        params['backColor'] = 'none'

    fill = params['backColor'] if params['backColor'] else 'none'
    stroke = params['foreColor']
    stroke_width = params['lineWidth']
    
    return f'''<ellipse id="{params['name']}" 
         cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" 
         fill="{fill}" 
         stroke="{stroke}" 
         stroke-width="{stroke_width}"/>'''


def create_arc_path(cx: float, cy: float, rx: float, ry: float, 
                   start_angle: float, end_angle: float) -> str:
    """
    Create SVG path data for an elliptical arc.
    
    FactoryTalk View angles appear to be in radians with 0 at 3 o'clock position.
    """
    # Calculate start and end points
    start_x = cx + rx * math.cos(start_angle)
    start_y = cy + ry * math.sin(start_angle)
    end_x = cx + rx * math.cos(end_angle)
    end_y = cy + ry * math.sin(end_angle)
    
    # Calculate angle difference, handling boundary crossing
    angle_diff = end_angle - start_angle
    if angle_diff < 0:
        angle_diff += 2 * math.pi
    
    # Determine if we need the large arc flag
    large_arc_flag = 1 if angle_diff > math.pi else 0
    
    # SVG arcs are always drawn clockwise with sweep-flag=1
    sweep_flag = 1
    
    # Special case: nearly full circle
    if abs(angle_diff - 2 * math.pi) < 0.001:
        # Draw as two semicircles to avoid SVG arc limitations
        mid_x = cx - rx * math.cos(start_angle)
        mid_y = cy - ry * math.sin(start_angle)
        
        return f'''M {start_x},{start_y} 
                  A {rx},{ry} 0 0,1 {mid_x},{mid_y}
                  A {rx},{ry} 0 0,1 {start_x},{start_y}'''
    
    # Standard arc
    return f'M {start_x:.2f},{start_y:.2f} A {rx:.2f},{ry:.2f} 0 {large_arc_flag},{sweep_flag} {end_x:.2f},{end_y:.2f}'

def convert_string_display(attrs: Dict[str, Any]) -> str:
    """
    Convert FactoryTalk View stringDisplay to SVG text element.
    
    Args:
        attrs: Dictionary of attributes from the stringDisplay element.
        
    Returns:
        str: SVG text element as a string.
    """
    font_weight = "bold" if attrs.get("bold") == "true" else "normal"
    
    # calculate the number of "X" characters that fit in the width
    fontSize = int(attrs.get('fontSize', attrs.get('charHeight', 10)))
    num_x_chars = int(attrs['width']) // int(fontSize)
    # create a caption with "X" repeated to fill the width
    text = 'S ' * num_x_chars
    return f'<text x="{attrs["left"]}" y="{int(attrs["top"]) + int(int(attrs["height"])/5*4)}" fill="{attrs["foreColor"]}" font-family="{attrs["fontFamily"]}" font-weight="{font_weight}" font-size="{int(fontSize*1.2)}">{text}</text>'

def convert_numeric_display(attrs: Dict[str, Any]) -> str:
    """
    Convert FactoryTalk View numericDisplay to SVG text element.
    
    Args:
        attrs: Dictionary of attributes from the numericDisplay element.
        
    Returns:
        str: SVG text element as a string.
    """
    font_weight = "bold" if attrs.get("bold") == "true" else "normal"
    
    # calculate the number of "0" characters that fit in the width
    fontSize = int(attrs.get('fontSize', attrs.get('charHeight', 10)))
    num_0_chars = int(attrs['width']) // int(fontSize)
    # create a caption with "0" repeated to fill the width
    text = '# ' * num_0_chars
    return f'<text x="{attrs["left"]}" y="{int(attrs["top"]) + int(int(attrs["height"])/5*4)}" fill="{attrs["foreColor"]}" font-family="{attrs["fontFamily"]}" font-weight="{font_weight}" font-size="{int(fontSize*1.2)}">{text}</text>'


def convert_ellipse(attrs: Dict[str, Any]) -> str:
    cx = int(attrs['left']) + int(attrs['width']) // 2
    cy = int(attrs['top']) + int(attrs['height']) // 2
    rx = int(attrs['width']) // 2
    ry = int(attrs['height']) // 2
    if attrs['backStyle'] == 'transparent':
        attrs['backColor'] = 'none'
    return f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="{attrs["backColor"]}" stroke="{attrs["foreColor"]}" stroke-width="{attrs["lineWidth"]}"/>'

def convert_freehand(attrs: Dict[str, Any]) -> str:
    path = attrs['path'].strip().replace(' ', 'L').replace('L', ' L')
    return f'<path d="M {path}" fill="none" stroke="{attrs["foreColor"]}" stroke-width="{attrs["lineWidth"]}"/>'

def convert_line(attrs: Dict[str, Any]) -> str:
    x1, y1, x2, y2 = attrs['line'].split()
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{attrs["foreColor"]}" stroke-width="{attrs["lineWidth"]}" stroke-linecap="round"/>'

def convert_polygon(attrs: Dict[str, Any]) -> str:
    points = attrs['path'].strip().replace(' ', ',')
    min_x = min([int(points.split(",")[i]) for i in range(0, len(points.split(',')), 2)])
    min_y = min([int(points.split(",")[i+1]) for i in range(0, len(points.split(',')), 2)])
    new_points = []
    for i in range(0, len(points.split(',')), 2):
        new_x = int(points.split(",")[i]) - min_x + int(attrs['left'])
        new_y = int(points.split(",")[i+1]) - min_y + int(attrs['top'])
        new_points.append(f"{new_x},{new_y}")
    
    if attrs['backStyle'] == 'transparent':
        attrs['backColor'] = 'none'

    return f'<polygon points="{",".join(new_points)}" fill="{attrs["backColor"]}" stroke="{attrs["foreColor"]}" stroke-width="{attrs["lineWidth"]}" stroke-linejoin="round"/>'

def convert_polyline(attrs: Dict[str, Any]) -> str:
    points = attrs['path'].strip().replace(' ', ',')
    min_x = min([int(points.split(",")[i]) for i in range(0, len(points.split(',')), 2)])
    min_y = min([int(points.split(",")[i+1]) for i in range(0, len(points.split(',')), 2)])
    new_points = []
    for i in range(0, len(points.split(',')), 2):
        new_x = int(points.split(",")[i]) - min_x + int(attrs['left'])
        new_y = int(points.split(",")[i+1]) - min_y + int(attrs['top'])
        new_points.append(f"{new_x},{new_y}")
    return f'<polyline points="{",".join(new_points)}" fill="none" stroke="{attrs["foreColor"]}" stroke-width="{attrs["lineWidth"]}"/>'

def convert_rectangle(attrs: Dict[str, Any]) -> str:

    if attrs['backStyle'] == 'transparent':
        attrs['backColor'] = 'none'

    return f'<rect x="{attrs["left"]}" y="{attrs["top"]}" width="{attrs["width"]}" height="{attrs["height"]}" fill="{attrs["backColor"]}" stroke="{attrs["foreColor"]}" stroke-width="{attrs["lineWidth"]}" stroke-linejoin="round"/>'

def convert_rounded_rectangle(attrs: Dict[str, Any]) -> str:
    
    if attrs['backStyle'] == 'transparent':
        attrs['backColor'] = 'none'

    return f'<rect x="{attrs["left"]}" y="{attrs["top"]}" width="{attrs["width"]}" height="{attrs["height"]}" rx="{attrs["roundingWidth"]}" ry="{attrs["roundingHeight"]}" fill="{attrs["backColor"]}" stroke="{attrs["foreColor"]}" stroke-width="{attrs["lineWidth"]}"/>'

def convert_wedge(attrs: Dict[str, Any]) -> str:

    start_angle = float(attrs['startAngle'])
    end_angle = float(attrs['endAngle'])
    
    # Handle special case: full circle (start == end and both are 0)
    if start_angle == end_angle and start_angle == 0:
        cx = float(attrs['left']) + float(attrs['width'] / 2)
        cy = float(attrs['top']) + float(attrs['height'] / 2)
        rx = float(attrs['width']) / 2
        ry = float(attrs['height']) / 2
        return create_svg_ellipse(attrs, cx, cy, rx, ry)
    
    # For wedges, use wedge-specific bounding calculation
    ellipse_params = calculate_ellipse_from_wedge_bounds(
        float(attrs['left']), float(attrs['top']), float(attrs['width']), float(attrs['height']),
        start_angle, end_angle
    )

    path_data = create_wedge_path(
        ellipse_params['cx'], ellipse_params['cy'], 
        ellipse_params['rx'], ellipse_params['ry'], 
        start_angle, end_angle
    )

    if attrs['backStyle'] == 'transparent':
        attrs['backColor'] = 'none'
    
    return f'<path d="{path_data}" fill="{attrs["backColor"]}" stroke="{attrs["foreColor"]}" stroke-width="{attrs["lineWidth"]}" stroke-linejoin="round" paint-order="stroke"/>'

def create_wedge_path(cx: float, cy: float, rx: float, ry: float, 
                     start_angle: float, end_angle: float) -> str:
    """
    Create SVG path data for a wedge (filled sector).
    
    A wedge is like a pie slice - it includes the center point and the arc.
    """
    # Handle angle wrapping - if end < start, add 2π to end
    normalized_end_angle = end_angle
    if end_angle < start_angle:
        normalized_end_angle = end_angle + 2 * math.pi
    
    # Calculate start and end points on the ellipse
    start_x = cx + rx * math.cos(start_angle)
    start_y = cy + ry * math.sin(start_angle)
    end_x = cx + rx * math.cos(normalized_end_angle)
    end_y = cy + ry * math.sin(normalized_end_angle)
    
    # Calculate angle difference
    angle_diff = normalized_end_angle - start_angle
    
    # Determine if we need the large arc flag
    large_arc_flag = 1 if angle_diff > math.pi else 0
    
    # SVG arcs are drawn clockwise with sweep-flag=1
    sweep_flag = 1
    
    # Special case: nearly full circle
    if abs(angle_diff - 2 * math.pi) < 0.001:
        # For a full wedge, create a path that goes almost all the way around
        return f'''M {cx},{cy} 
                  L {start_x},{start_y} 
                  A {rx},{ry} 0 1,1 {start_x + 0.001},{start_y}
                  Z'''
    
    # Standard wedge: Move to center, line to start, arc to end, close path
    return f'''M {cx},{cy} 
              L {start_x},{start_y} 
              A {rx},{ry} 0 {large_arc_flag},{sweep_flag} {end_x},{end_y}
              Z'''

def calculate_ellipse_from_wedge_bounds(left: float, top: float, width: float, height: float, 
                                      start_angle: float, end_angle: float) -> Dict:
    """
    Calculate ellipse parameters for a wedge where the filled sector fits within the given bounds.
    
    Unlike arcs, wedges include the center point and filled area, so the bounding calculation
    must account for the entire sector area, not just the arc.
    """
    # Handle angle normalization and wrapping - if end < start, add 2π to end
    normalized_end_angle = end_angle
    if end_angle < start_angle:
        normalized_end_angle = end_angle + 2 * math.pi
    
    # Collect all critical points for the wedge boundary  
    critical_angles = [start_angle, normalized_end_angle]
    
    # Add quadrant boundaries (0, π/2, π, 3π/2) that fall within the sector
    quadrants = [0, math.pi/2, math.pi, 3*math.pi/2, 2*math.pi]
    for qa in quadrants:
        # Check if this quadrant angle falls within our sector
        test_angle = qa
        while test_angle < start_angle:
            test_angle += 2 * math.pi
        if test_angle <= normalized_end_angle:
            critical_angles.append(test_angle)
    
    # Calculate all boundary points
    boundary_points = []
    
    # Always include the center point for wedges
    boundary_points.append((0, 0))
    
    # Add points on the arc
    for angle in critical_angles:
        x = math.cos(angle)
        y = math.sin(angle)
        boundary_points.append((x, y))
    
    # Find the bounding box of all boundary points
    x_coords = [p[0] for p in boundary_points]
    y_coords = [p[1] for p in boundary_points]
    
    wedge_x_min, wedge_x_max = min(x_coords), max(x_coords)
    wedge_y_min, wedge_y_max = min(y_coords), max(y_coords)
    
    wedge_x_range = wedge_x_max - wedge_x_min
    wedge_y_range = wedge_y_max - wedge_y_min
    
    # Calculate required ellipse dimensions
    if wedge_x_range > 0.001:
        rx = width / wedge_x_range
    else:
        rx = width / 2
        
    if wedge_y_range > 0.001:
        ry = height / wedge_y_range
    else:
        ry = height / 2
    
    # Calculate center position to fit the wedge in the bounding box
    wedge_center_x = (wedge_x_min + wedge_x_max) / 2
    wedge_center_y = (wedge_y_min + wedge_y_max) / 2
    
    cx = left + width/2 - wedge_center_x * rx
    cy = top + height/2 - wedge_center_y * ry
    
    return {
        'cx': cx,
        'cy': cy,
        'rx': rx,
        'ry': ry
    }


def convert_text(attrs: Dict[str, Any]) -> str:
    font_weight="bold" if attrs.get("bold") == "true" else "normal"
    return f'<text x="{attrs["left"]}" y="{int(attrs["top"]) + int(int(attrs["height"])/5*4)}" fill="{attrs["foreColor"]}" font-family="{attrs["fontFamily"]}" font-weight="{font_weight}" font-size="{int(int(attrs["fontSize"])*1.2)}">{attrs["caption"]}</text>'

def convert_image(attrs: Dict[str, Any]) -> str:
    x = attrs["left"]
    y = attrs["top"]
    width = attrs["width"]
    height = attrs["height"]
    return f'''
    <g>
        <rect x="{x}" y="{y}" width="{width}" height="{height}" fill="lightgray" stroke="gray" stroke-width="1"/>
        <line x1="{x}" y1="{y}" x2="{int(x)+int(width)}" y2="{int(y)+int(height)}" stroke="gray" stroke-width="1"/>
        <line x1="{x}" y1="{int(y)+int(height)}" x2="{int(x)+int(width)}" y2="{y}" stroke="gray" stroke-width="1"/>
    </g>
    '''

if __name__ == "__main__":
    # Example XML string (replace with actual XML data)
    xml_string = ''' '''
    
    svg_output = gfx_to_svg(xml_string)
    print(svg_output)
    # Save the SVG output to a file
    with open('outputr.svg', 'w') as svg_file:
        svg_file.write(svg_output)