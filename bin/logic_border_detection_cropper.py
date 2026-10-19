"""
Border Detection and Cropping Module for Engineering Drawings

This module provides functionality to detect drawing borders using flood fill
and crop pages to the inner boundary. It also calculates optimal zoom levels
to fit target dimensions.
"""

import os
import shutil
import cv2
import pikepdf
import numpy as np
from PIL import Image
import logging

try:
    from bin.logic_pdf_render import page_count, page_size, render_page
except Exception:
    from logic_pdf_render import page_count, page_size, render_page

logger = logging.getLogger(__name__)


def detect_border_contour(image, debug=False):
    """
    Detect the outermost border contour in an engineering drawing.
    
    :param image: Input image (PIL Image or numpy array)
    :type image: PIL.Image or numpy.ndarray
    :param debug: Enable debug visualization
    :type debug: bool
    
    :returns: The largest closed contour representing the border, or None if not found
    :rtype: numpy.ndarray or None
    """
    # Convert PIL Image to numpy array if needed
    if isinstance(image, Image.Image):
        img_array = np.array(image)
    else:
        img_array = image.copy()
    
    # Convert to grayscale if needed
    if len(img_array.shape) == 3:
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
    else:
        gray = img_array.copy()
    
    h, w = gray.shape[:2]
    
    # Create a copy for flood fill (needs to be larger by 2 pixels)
    flood_fill_img = gray.copy()
    
    # Create mask for flood fill (must be 2 pixels larger than image)
    mask = np.zeros((h + 2, w + 2), np.uint8)
    
    # Apply binary threshold to get clear separation
    _, binary = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY)
    
    # Flood fill from all four corners to mark the outer margin area
    # This assumes the border doesn't touch the edges
    fill_value = 128  # Gray value to mark filled areas
    
    # Fill from corners and edges
    points_to_fill = [
        (0, 0),           # Top-left corner
        (w-1, 0),         # Top-right corner
        (0, h-1),         # Bottom-left corner
        (w-1, h-1),       # Bottom-right corner
    ]
    
    # Also fill from multiple points along edges
    edge_samples = 20
    for i in range(1, edge_samples):
        x = int(i * w / edge_samples)
        y = int(i * h / edge_samples)
        points_to_fill.extend([
            (x, 0),       # Top edge
            (x, h-1),     # Bottom edge
            (0, y),       # Left edge
            (w-1, y),     # Right edge
        ])
    
    # Perform flood fill from all points
    for point in points_to_fill:
        if 0 <= point[0] < w and 0 <= point[1] < h:
            if binary[point[1], point[0]] == 255:  # Only fill white areas
                cv2.floodFill(binary, mask, point, fill_value)
    
    # Now the remaining white areas are inside the border
    # The gray areas (128) are outside the border
    # Create a mask where only the inner area is white
    inner_mask = (binary != fill_value).astype(np.uint8) * 255

    
    # Find contours directly from the inner mask (areas NOT filled by flood fill)
    # This gives us the drawing area within the border
    contours, _ = cv2.findContours(inner_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        logger.warning("No border contours found")
        return None
    
    # Get the largest contour (the main drawing area)
    largest_contour = max(contours, key=cv2.contourArea)
    
    # Filter out contours that are too small (less than 10% of image area)
    min_area = (h * w) * 0.1
    if cv2.contourArea(largest_contour) < min_area:
        logger.warning("Detected border contour is too small")
        return None
    
    if debug:
        # Visualize the detection process
        debug_img = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        cv2.drawContours(debug_img, [largest_contour], -1, (0, 255, 0), 3)
        cv2.imshow("Border Detection Debug", cv2.resize(debug_img, (1200, int(1200 * h / w))))
        cv2.waitKey(0)
    
    return largest_contour


def get_border_bounding_box(contour):
    """
    Get the bounding box of a border contour.
    
    :param contour: The border contour
    :type contour: numpy.ndarray
    
    :returns: Bounding box as (x, y, width, height)
    :rtype: tuple
    """
    return cv2.boundingRect(contour)


def calculate_zoom_for_target_dimensions(page_rect, border_bbox, target_dimensions, detection_zoom):
    """
    Calculate the zoom level needed to fit the cropped area into target dimensions.
    
    :param page_rect: Original page rectangle as (x0, y0, x1, y1)
    :type page_rect: tuple
    :param border_bbox: Border bounding box (x, y, w, h) in pixel coordinates at detection zoom
    :type border_bbox: tuple
    :param target_dimensions: Target (width, height) in pixels
    :type target_dimensions: tuple
    :param detection_zoom: The zoom level used when detecting the border
    :type detection_zoom: float
    
    :returns: Optimal zoom level
    :rtype: float
    """
    if target_dimensions is None:
        return 2.0  # Default zoom
    
    target_width, target_height = target_dimensions
    border_x, border_y, border_w, border_h = border_bbox
    
    # Convert pixel dimensions back to PDF coordinate dimensions
    # The border_bbox is in pixels at detection_zoom, so we need to scale back to PDF coordinates
    pdf_width = border_w / detection_zoom
    pdf_height = border_h / detection_zoom
    
    # Calculate zoom factors for width and height based on PDF coordinates
    zoom_width = target_width / pdf_width
    zoom_height = target_height / pdf_height
    
    # Use the smaller zoom to ensure the entire content fits
    optimal_zoom = min(zoom_width, zoom_height)
    
    # Ensure zoom is reasonable (between 0.5 and 10)
    optimal_zoom = max(0.5, min(10.0, optimal_zoom))
    
    logger.info(f"Calculated optimal zoom: {optimal_zoom:.2f} for target dimensions {target_dimensions} "
                f"(PDF size: {pdf_width:.1f}x{pdf_height:.1f}, detection zoom: {detection_zoom})")
    
    return optimal_zoom


def detect_and_crop_border(image, debug=False):
    """
    Detect border and return the cropped image and bounding box.
    
    :param image: Input image (PIL Image or numpy array)
    :type image: PIL.Image or numpy.ndarray
    :param debug: Enable debug visualization
    :type debug: bool
    
    :returns: Tuple of (cropped_image, bounding_box) or (original_image, None) if no border found
    :rtype: tuple
    """
    # Detect the border contour
    contour = detect_border_contour(image, debug=debug)
    
    if contour is None:
        logger.info("No border detected, returning original image")
        return image, None
    
    # Get bounding box
    x, y, w, h = get_border_bounding_box(contour)
    
    # Convert to numpy array if needed for cropping
    if isinstance(image, Image.Image):
        img_array = np.array(image)
        # Crop the image
        cropped_array = img_array[y:y+h, x:x+w]
        # Convert back to PIL Image
        cropped_image = Image.fromarray(cropped_array)
    else:
        cropped_image = image[y:y+h, x:x+w]
    
    logger.info(f"Cropped image from ({x}, {y}) with size ({w}, {h})")
    
    return cropped_image, (x, y, w, h)


def check_pdf_border_consistency(input_pdf_path, tolerance=10):
    """
    Check if a PDF has consistent borders across all pages or different borders.
    
    :param input_pdf_path: Path to the input PDF file
    :type input_pdf_path: str
    :param tolerance: Maximum allowed difference in pixels for borders to be considered consistent
    :type tolerance: int
    :return: Dictionary with analysis results
    :rtype: dict
    """
    print(f"\n{'='*80}")
    print(f"Analyzing border consistency: {input_pdf_path}")
    print(f"{'='*80}\n")
    
    detection_zoom = 2.0
    
    borders = []
    page_info = []
    
    # Detect borders for all pages
    for page_num in range(page_count(input_pdf_path)):
        # Render page for border detection
        img_detect = render_page(input_pdf_path, page_num, zoom=detection_zoom)
        
        _, border_bbox = detect_and_crop_border(img_detect, debug=False)
        
        width, height = page_size(input_pdf_path, page_num)
        clip_rect = clip_rect_for_border(width, height, border_bbox, detection_zoom)
        
        borders.append(border_bbox)
        page_info.append({
            'page': page_num + 1,
            'border': border_bbox,
            'clip_rect': clip_rect,
            'width': clip_rect[2] - clip_rect[0],
            'height': clip_rect[3] - clip_rect[1],
            'has_border': border_bbox is not None
        })
    
    # Analyze consistency
    pages_with_borders = [info for info in page_info if info['has_border']]
    pages_without_borders = [info for info in page_info if not info['has_border']]
    
    consistent = True
    different_borders = []
    
    if len(pages_with_borders) > 1:
        # Compare all borders against the first one
        reference = pages_with_borders[0]['border']
        
        for info in pages_with_borders[1:]:
            border = info['border']
            # Check if borders differ by more than tolerance
            if (abs(border[0] - reference[0]) > tolerance or
                abs(border[1] - reference[1]) > tolerance or
                abs(border[2] - reference[2]) > tolerance or
                abs(border[3] - reference[3]) > tolerance):
                consistent = False
                different_borders.append(info['page'])
    
    # Print summary
    print(f"Total pages: {len(page_info)}")
    print(f"Pages with borders detected: {len(pages_with_borders)}")
    print(f"Pages without borders: {len(pages_without_borders)}")
    
    if pages_without_borders:
        print(f"\nPages without borders: {[p['page'] for p in pages_without_borders]}")
    
    if consistent:
        print(f"\n✓ All borders are CONSISTENT (within {tolerance}px tolerance)")
        if pages_with_borders:
            ref = pages_with_borders[0]
            print(f"  Reference border: x={ref['border'][0]}, y={ref['border'][1]}, "
                  f"w={ref['border'][2]}, h={ref['border'][3]}")
            print(f"  Cropped dimensions: {ref['width']:.1f} x {ref['height']:.1f} pts")
    else:
        print(f"\n✗ Borders are DIFFERENT across pages")
        print(f"  Pages with different borders: {different_borders}")
        print(f"\n  Border details:")
        for info in pages_with_borders:
            if info['page'] == pages_with_borders[0]['page'] or info['page'] in different_borders:
                print(f"    Page {info['page']}: x={info['border'][0]}, y={info['border'][1]}, "
                      f"w={info['border'][2]}, h={info['border'][3]} "
                      f"({info['width']:.1f} x {info['height']:.1f} pts)")
    
    print(f"{'='*80}\n")
    
    return {
        'consistent': consistent,
        'total_pages': len(page_info),
        'pages_with_borders': len(pages_with_borders),
        'pages_without_borders': len(pages_without_borders),
        'different_border_pages': different_borders,
        'page_info': page_info,
        'tolerance': tolerance
    }


def create_pdf_from_cropped_pages(input_pdf_path, output_pdf_path, target_dimensions):
    """
    Create a new PDF with all pages cropped to borders using native PDF cropping.
    Preserves vector quality by using PDF cropbox instead of rasterization.
    
    :param input_pdf_path: Path to the input PDF file
    :type input_pdf_path: str
    :param output_pdf_path: Path to save the output PDF
    :type output_pdf_path: str
    :param target_dimensions: Target (width, height) in points (not pixels)
    :type target_dimensions: tuple
    """
    print(f"\n{'='*80}")
    print(f"Creating cropped PDF: {output_pdf_path}")
    print(f"Target dimensions: {target_dimensions} points")
    print(f"{'='*80}\n")

    # change the input pdf filename to a temp file to avoid overwriting while reading
    source_path = input_pdf_path + ".tmp"
    os.rename(input_pdf_path, source_path)

    detection_zoom = 2.0
    target_width, target_height = target_dimensions

    with pikepdf.open(source_path) as src_doc, pikepdf.Pdf.new() as out_doc:
        for page_num, src_page in enumerate(src_doc.pages):
            print(f"Processing page {page_num + 1}/{len(src_doc.pages)}...")

            # Step 1: Detect border at detection zoom
            img_detect = render_page(source_path, page_num, zoom=detection_zoom)

            _, border_bbox = detect_and_crop_border(img_detect, debug=False)

            # Step 2: Get crop rectangle in PDF coordinates, top left origin
            width, height = page_size(source_path, page_num)
            clip_rect = clip_rect_for_border(width, height, border_bbox, detection_zoom)
            if border_bbox:
                print(f"  - Border detected, crop rect: {clip_rect}")
            else:
                print(f"  - No border detected, using full page")

            cropped_width = clip_rect[2] - clip_rect[0]
            cropped_height = clip_rect[3] - clip_rect[1]

            # Determine final page size
            if target_width and target_height:
                page_width = target_width
                page_height = target_height

                # Scale to fit the cropped content into the target size, keeping aspect
                scale = min(target_width / cropped_width, target_height / cropped_height)
            else:
                page_width = cropped_width
                page_height = cropped_height
                scale = 1.0

            # Step 3: Draw the source page onto a new page whose mediabox is the crop.
            # handle_transformations bakes /Rotate in, so the form draws upright from
            # (0, 0) to (width, height) and no remove_rotation is needed.
            form = out_doc.copy_foreign(src_page.as_form_xobject(handle_transformations=True))
            new_page = pikepdf.Page(out_doc.add_blank_page(page_size=(page_width, page_height)))
            name = new_page.add_resource(form, pikepdf.Name.XObject)

            # Translate so the crop's top left corner lands on the new page's top left
            tx = -scale * clip_rect[0]
            ty = page_height - scale * (height - clip_rect[1])
            new_page.contents_add(
                'q {} 0 0 {} {} {} cm {} Do Q\n'.format(scale, scale, tx, ty, name).encode())

            if target_width and target_height:
                print(f"  - Page cropped and scaled: {cropped_width:.1f}x{cropped_height:.1f} -> {page_width}x{page_height} pts (scale: {scale:.2f})")
            else:
                print(f"  - Page cropped: {cropped_width:.1f}x{cropped_height:.1f} pts")

        page_count_out = len(out_doc.pages)
        out_doc.save(output_pdf_path)

    print(f"\n{'='*80}")
    print(f"PDF created successfully: {output_pdf_path}")
    print(f"Total pages: {page_count_out}")
    print(f"{'='*80}\n")


def clip_rect_for_border(page_width, page_height, border_bbox, zoom_level):
    """
    Convert a pixel space border bounding box into a PDF point clip rectangle.
    
    :param page_width: Page width in PDF points
    :type page_width: float
    :param page_height: Page height in PDF points
    :type page_height: float
    :param border_bbox: Border bounding box (x, y, w, h) in pixel coordinates at ``zoom_level``
    :type border_bbox: tuple or None
    :param zoom_level: The zoom level used when detecting the border
    :type zoom_level: float
    
    :returns: Clip rectangle as (x0, y0, x1, y1) in PDF points, top left origin
    :rtype: tuple
    """
    if border_bbox is None:
        return (0.0, 0.0, page_width, page_height)
    
    x, y, w, h = border_bbox
    return (x / zoom_level, y / zoom_level, (x + w) / zoom_level, (y + h) / zoom_level)
