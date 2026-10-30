"""
PDF Approved Annotations Exporter

This script exports PDFs with all approved text link annotations highlighted in a single color.
It reads approved text links from the database and adds highlight annotations to the PDF.

Usage:
    python export_approved_annotations.py --input <pdf_path> --output <output_path> [options]

Arguments:
    --input, -i         : Path to the input PDF file
    --output, -o        : Path to save the annotated PDF
    --project-db, -d    : Path to project database (default: auto-detect from input path)
    --color, -c         : Highlight color in RGB format (default: 0.55,0.8,0.56 - green)
    --opacity, -a       : Annotation opacity 0.0-1.0 (default: 0.3)
    --all-pages         : Process all pages (default: only pages with approved links)
    
Example:
    python export_approved_annotations.py -i document.pdf -o annotated.pdf
    python export_approved_annotations.py -i document.pdf -o output.pdf -c 1,1,0 -a 0.5
"""

import argparse
import sys
import os
from pathlib import Path

from pypdf import PdfWriter
from pypdf.annotations import Highlight
from pypdf.generic import ArrayObject, FloatObject, NameObject, TextStringObject

# Add bin directory to path for imports
script_dir = Path(__file__).parent
bin_dir = script_dir / 'bin'
sys.path.insert(0, str(bin_dir))

try:
    from bin.logic_internal_database import Database
    from bin.logic_linked_texts import LinkedText, GivenTextLink, TargetTextLink, LinkedTextDecodeError, decode_link_map
    from bin.logic_pdf_text import open_text
except ImportError as e:
    print(f"Error importing required modules: {e}")
    print("Make sure the 'bin' directory contains the required modules.")
    sys.exit(1)


def _rgb_to_hex(colour):
    """Convert a 0.0-1.0 RGB triple into the hex string pypdf expects."""
    return ''.join('{:02x}'.format(max(0, min(255, int(round(c * 255))))) for c in colour[:3])


class ApprovedAnnotationExporter:
    """Export PDFs with approved text link annotations"""
    
    # Default green color matching APPROVED_STROKE from gui_text_selector_tools.py
    DEFAULT_COLOR = (0.5529, 0.8, 0.5608)
    
    def __init__(self, pdf_path, db:Database=None, highlight_color=None, opacity=0.3):
        """
        Initialize the exporter
        
        :param pdf_path: Path to the PDF file
        :param db_path: Path to the database file (optional, will auto-detect)
        :param highlight_color: RGB tuple for highlight color (0.0-1.0 range)
        :param opacity: Opacity for annotations (0.0-1.0)
        """
        self.pdf_path = pdf_path
        self.highlight_color = highlight_color or self.DEFAULT_COLOR
        self.opacity = opacity
        
        # Open PDF and database
        self.doc = PdfWriter(clone_from=pdf_path)
        self.text_doc = open_text(pdf_path)
        self.db:Database = db 
        
        # Statistics
        self.stats = {
            'pages_processed': 0,
            'annotations_added': 0,
            'approved_links_found': 0
        }
        
   
    
    def _extract_linked_text(self, data):
        """
        Extract LinkedText object from database record
        
        :param data: Database record dictionary
        :return: LinkedText object
        """
        linked_text = LinkedText(**{
            k: v for k, v in data.items() 
            if k in ['text', 'text_type', 'object_type', 'linked', 'reftype', 'link_type', 'axis']
        })
        
        if data.get('links'):
            linked_text.links = decode_link_map(data['links'], TargetTextLink)
        
        if data.get('given_text'):
            linked_text.given_text = decode_link_map(data['given_text'], GivenTextLink)
        
        return linked_text
    
    def _extract_approved_link_data(self, approved_link):
        """
        Extract structured data from approved link record
        
        :param approved_link: Database record for approved link
        :return: Dictionary with tagname, parameters, and metadata
        """
        result = {
            'id': approved_link['id'],
            'tagname': self._extract_linked_text(approved_link['tagname']),
            'parameters': {
                k: self._extract_linked_text(v) 
                for k, v in approved_link['parameters'].items()
            },
            'template_id': approved_link.get('template_id'),
            'is_llm_generated': approved_link.get('is_llm_generated', False)
        }
        
        if 'subobject' in approved_link:
            result['subobject'] = self._extract_linked_text(approved_link['subobject'])
        
        return result
    
    def _get_text_on_page(self, page_number):
        """
        Extract text characters with bounding boxes from page
        
        :param page_number: Page number to extract
        :return: List of character dictionaries
        """
        chars = []
        char_index = 0
        
        blocks = self.text_doc[page_number].blocks()
        blocks.sort(key=lambda b: b['bbox'][1])  # Sort by y-coordinate
        
        for block in blocks:
            for char_data in block['chars']:
                chars.append({
                    'c': char_data['c'],
                    'bbox': char_data['bbox'],
                    'index': char_index
                })
                char_index += 1
        
        return chars
    
    def _is_bbox_within_row_column(self, char_bbox, table_bbox, row, column):
        """
        Check if character bbox is within specified table cell
        
        :param char_bbox: Character bounding box
        :param table_bbox: Table bounding box
        :param row: Row index
        :param column: Column index
        :return: True if within cell
        """
        # If no table info, return True (not in table)
        if table_bbox is None:
            return True
        
        # For simplicity, if we have table info but no specific row/col, check table bounds
        if row is None or column is None:
            return (char_bbox[0] >= table_bbox[0] and 
                    char_bbox[1] >= table_bbox[1] and
                    char_bbox[2] <= table_bbox[2] and 
                    char_bbox[3] <= table_bbox[3])
        
        # TODO: Implement proper table cell checking if needed
        return True
    
    def _build_highlight_rects(self, chars_to_highlight):
        """
        Build rectangles for highlighting from character list
        
        :param chars_to_highlight: List of characters to highlight
        :return: List of (x0, y0, x1, y1) tuples in unrotated top-left page space
        """
        if not chars_to_highlight:
            return []
        
        # Group characters into lines based on y-coordinate proximity
        lines = {}
        
        for char in chars_to_highlight:
            bbox = char['bbox']
            # Round y-coordinate to group into lines (tolerance of 2 points)
            line_key = round(bbox[1] * 2) / 2
            
            if line_key not in lines:
                lines[line_key] = []
            lines[line_key].append(bbox)
        
        # Create rectangles for each line
        rects = []
        for line_bboxes in lines.values():
            if not line_bboxes:
                continue
            
            # Get bounding box for entire line
            x0 = min(b[0] for b in line_bboxes)
            y0 = min(b[1] for b in line_bboxes)
            x1 = max(b[2] for b in line_bboxes)
            y1 = max(b[3] for b in line_bboxes)
            
            rects.append((x0, y0, x1, y1))
        
        return rects
    
    def _to_pdf_rect(self, page, rect):
        """Flip a top-left-origin rect in unrotated page space into PDF user space."""
        mediabox = page.mediabox
        left, top = float(mediabox.left), float(mediabox.top)
        x0, y0, x1, y1 = rect
        return (left + x0, top - y1, left + x1, top - y0)
    
    def _build_annotation(self, rect, info_text):
        """Build the highlight annotation for one rect."""
        x0, y0, x1, y1 = rect
        quad_points = ArrayObject(
            [FloatObject(v) for v in (x0, y1, x1, y1, x0, y0, x1, y0)])
        annotation = Highlight(rect=(x0, y0, x1, y1),
                               quad_points=quad_points,
                               highlight_color=_rgb_to_hex(self.highlight_color),
                               printing=True)
        annotation[NameObject('/CA')] = FloatObject(self.opacity)
        annotation[NameObject('/Contents')] = TextStringObject(info_text)
        return annotation
    
    def process_page(self, page_number):
        """
        Process a single page and add annotations
        
        :param page_number: Page number to process
        :return: Number of annotations added
        """
        page = self.doc.pages[page_number]
        annotations_added = 0
        
        # Get approved links for this page
        approved_links = self.db.get_all_approved_text_links_by_page_no(
            self.pdf_path, 
            page_number
        )
        
        if not approved_links:
            return 0
        
        self.stats['approved_links_found'] += len(approved_links)
        
        # Get text on page
        text_on_page = self._get_text_on_page(page_number)
        
        # Process each approved link
        for approved_link in approved_links:
            try:
                link_data = self._extract_approved_link_data(approved_link)
            except LinkedTextDecodeError as error:
                print(f"Skipping invalid approved link {approved_link.get('id')!r}: {error}")
                continue
            
            # Collect all characters to highlight for this link
            chars_to_highlight = []
            
            # Add characters from all parameters
            for parameter_name, parameter_data in link_data['parameters'].items():
                if not parameter_data.given_text:
                    continue
                
                for given_text_id, given_text in parameter_data.given_text.items():
                    if not given_text.indexes:
                        continue
                    
                    # Get characters in this range
                    start_idx, end_idx = given_text.indexes
                    chars = text_on_page[start_idx:end_idx]
                    
                    # Filter by table/ROI if specified
                    for char in chars:
                        if self._is_bbox_within_row_column(
                            char['bbox'],
                            given_text.table_bbox,
                            given_text.roi[0] if given_text.roi else None,
                            given_text.roi[1] if given_text.roi else None
                        ):
                            chars_to_highlight.append(char)
            
            # Build highlight rectangles
            rects = self._build_highlight_rects(chars_to_highlight)
            
            # Add highlights to page
            for rect in rects:
                info_text = f"Approved: {link_data['tagname'].text}"
                if 'subobject' in link_data:
                    info_text += f" - {link_data['subobject'].text}"

                self.doc.add_annotation(
                    page_number=page_number,
                    annotation=self._build_annotation(self._to_pdf_rect(page, rect), info_text))
                annotations_added += 1
        
        return annotations_added
    
    def get_number_of_pages(self):
        """
        :return: Number of pages in the PDF being annotated
        :rtype: int
        """
        return len(self.doc.pages)
    
    def save(self, output_path):
        """
        Save the annotated document to a new path, leaving the source PDF untouched.
        
        :param output_path: Path to save annotated PDF
        """
        self.doc.compress_identical_objects()
        self.doc.write(output_path)
    
    def export(self, output_path, process_all_pages=False):
        """
        Export PDF with annotations
        
        :param output_path: Path to save annotated PDF
        :param process_all_pages: If True, process all pages; if False, only pages with approved links
        """
        print(f"Exporting PDF with approved annotations...")
        print(f"Input: {self.pdf_path}")
        print(f"Output: {output_path}")
        print(f"Color: RGB{self.highlight_color}, Opacity: {self.opacity}")
        print()
        
        if process_all_pages:
            pages_to_process = range(len(self.doc.pages))
        else:
            # Get unique page numbers with approved links
            pages_to_process = set()
            for page_num in range(len(self.doc.pages)):
                approved_links = self.db.get_all_approved_text_links_by_page_no(
                    self.pdf_path, 
                    page_num
                )
                if approved_links:
                    pages_to_process.add(page_num)
            pages_to_process = sorted(pages_to_process)
        
        print(f"Processing {len(pages_to_process)} pages...")
        
        # Process each page
        for page_num in pages_to_process:
            print(f"  Page {page_num + 1}...", end=' ')
            annotations = self.process_page(page_num)
            self.stats['annotations_added'] += annotations
            self.stats['pages_processed'] += 1
            print(f"{annotations} annotations added")
        
        # Save the annotated PDF
        self.save(output_path)
        print()
        print("Export complete!")
        print(f"  Pages processed: {self.stats['pages_processed']}")
        print(f"  Approved links found: {self.stats['approved_links_found']}")
        print(f"  Annotations added: {self.stats['annotations_added']}")
    
    def close(self):
        """Close PDF and database"""
        if self.doc:
            self.doc.close()
        if self.text_doc:
            self.text_doc.close()
        # Database closes automatically


def parse_color(color_str):
    """
    Parse color string to RGB tuple
    
    :param color_str: Color as "R,G,B" where each is 0.0-1.0
    :return: Tuple of (R, G, B)
    """
    try:
        parts = [float(x.strip()) for x in color_str.split(',')]
        if len(parts) != 3:
            raise ValueError("Color must have 3 components (R,G,B)")
        
        for val in parts:
            if not 0.0 <= val <= 1.0:
                raise ValueError("Color components must be between 0.0 and 1.0")
        
        return tuple(parts)
    except Exception as e:
        raise argparse.ArgumentTypeError(f"Invalid color format: {e}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Export PDF with approved text link annotations highlighted',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic export with default green highlighting
  python export_approved_annotations.py -i document.pdf -o annotated.pdf
  
  # Export with yellow highlighting and higher opacity
  python export_approved_annotations.py -i doc.pdf -o out.pdf -c 1,1,0 -a 0.5
  
  # Process all pages (not just those with approved links)
  python export_approved_annotations.py -i doc.pdf -o out.pdf --all-pages
  
  # Specify custom database location
  python export_approved_annotations.py -i doc.pdf -o out.pdf -d /path/to/db.json
        """
    )
    
    parser.add_argument(
        '-i', '--input',
        required=True,
        help='Path to input PDF file'
    )
    
    parser.add_argument(
        '-o', '--output',
        required=True,
        help='Path to save annotated PDF'
    )
    
    parser.add_argument(
        '-d', '--project-db',
        help='Path to project database (auto-detects if not specified)'
    )
    
    parser.add_argument(
        '-c', '--color',
        type=parse_color,
        default=None,
        help='Highlight color as "R,G,B" (e.g., "1,1,0" for yellow). Default: green'
    )
    
    parser.add_argument(
        '-a', '--opacity',
        type=float,
        default=0.3,
        help='Annotation opacity from 0.0 to 1.0 (default: 0.3)'
    )
    
    parser.add_argument(
        '--all-pages',
        action='store_true',
        help='Process all pages (default: only pages with approved links)'
    )
    
    args = parser.parse_args()
    
    # Validate inputs
    if not os.path.exists(args.input):
        print(f"Error: Input file not found: {args.input}")
        sys.exit(1)
    
    if not 0.0 <= args.opacity <= 1.0:
        print(f"Error: Opacity must be between 0.0 and 1.0")
        sys.exit(1)
    
    # Create exporter and process
    try:
        exporter = ApprovedAnnotationExporter(
            pdf_path=args.input,
            db_path=args.project_db,
            highlight_color=args.color,
            opacity=args.opacity
        )
        
        exporter.export(args.output, process_all_pages=args.all_pages)
        exporter.close()
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
