"""
Data models for regions of interest, linked graphics, and text structures.

This module provides type-safe dataclass models to replace dictionary-based structures,
improving code maintainability and reducing errors from typos/missing keys.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any
from enum import Enum


class DocumentType(str, Enum):
    """Document type enumeration."""
    DRAWING = 'Drawing'
    IMAGE = 'Image'
    TEXT = 'Text'
    TABLE = 'Table'


class TemplateFlip(Enum):
    """Template flip transformation."""
    NONE = 0
    HORIZONTAL = 1
    VERTICAL = 2
    BOTH = 3


class TemplateRotate(Enum):
    """Template rotation transformation."""
    NONE = 0
    CW_90 = 90
    CW_180 = 180
    CW_270 = 270



@dataclass
class Document:
    """
    Complete document metadata and processing state.
    
    Represents a PDF, collection of images, or Excel document imported into a project.
    Tracks file location, type, dimensions, processing state, and page information.
    Documents are referenced throughout the codebase via path + pno (page number).
    """
    name: str  # Filename only (e.g., "diagram.pdf")
    path: str  # Full relative path (e.g., "projects/MyProject/drawings/diagram.pdf")
    document_type: str  # DocumentType enum value (DRAWING, IMAGE, TEXT, TABLE)
    timestamp: int  # Import timestamp in milliseconds
    
    def __post_init__(self):
        """Validate document data structure."""
        if not self.name.strip():
            raise ValueError("Document name cannot be empty")
        if not self.path.strip():
            raise ValueError("Document path cannot be empty")
        if self.page_count < 1:
            raise ValueError(f"Page count must be >= 1, got: {self.page_count}")
        
    @property
    def filename(self) -> str:
        """Extract filename from path (handles both forward and backslashes)."""
        return self.path.replace('\\', '/').split('/')[-1]
    
    @property
    def extension(self) -> str:
        """Get file extension (lowercase, with dot)."""
        import os
        return os.path.splitext(self.name)[1].lower()
    
    @property
    def is_pdf(self) -> bool:
        """Check if document is a PDF."""
        return self.extension == '.pdf'
    
    @property
    def is_image(self) -> bool:
        """Check if document is an image."""
        return self.extension in ['.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.tif']
    
    @property
    def is_excel(self) -> bool:
        """Check if document is an Excel file."""
        return self.extension in ['.xlsx', '.xlsm', '.xls']
    
    
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            'name': self.name,
            'path': self.path,
            'type': self.document_type,
            'timestamp': self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Document':
        """Create Document from dictionary."""
        
        # Determine default zoom scale based on document type
        doc_type = data.get('type', DocumentType.DRAWING.value)
        return cls(
            name=data['name'],
            path=data['path'],
            document_type=doc_type,
            timestamp=data['timestamp']
        )


@dataclass(frozen=True)
class CharacterData:
    """
    Immutable representation of a single character from OCR/PDF extraction.
    
    Each character has precise spatial coordinates for accurate text positioning
    and bounding box information for visual rendering.
    """
    uuid: str  # Unique identifier
    c: str  # Single character
    origin: Tuple[float, float]  # (x, y) baseline origin point
    bbox: Tuple[float, float, float, float]  # (x0, y0, x1, y1) bounding box
    
    def __post_init__(self):
        """Validate character data structure."""
        if len(self.c) != 1:
            raise ValueError(f"Character must be single char, got: '{self.c}'")
        if len(self.origin) != 2:
            raise ValueError(f"Origin must be (x,y), got: {self.origin}")
        if len(self.bbox) != 4:
            raise ValueError(f"Bbox must be (x0,y0,x1,y1), got: {self.bbox}")
    
    @property
    def width(self) -> float:
        """Calculate character width from bounding box."""
        return self.bbox[2] - self.bbox[0]
    
    @property
    def height(self) -> float:
        """Calculate character height from bounding box."""
        return self.bbox[3] - self.bbox[1]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for backward compatibility."""
        return {
            'uuid': self.uuid,
            'c': self.c,
            'origin': self.origin,
            'bbox': self.bbox
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CharacterData':
        """Create CharacterData from dictionary."""
        return cls(
            uuid=data['uuid'],
            c=data['c'],
            origin=tuple(data['origin']),
            bbox=tuple(data['bbox'])
        )


@dataclass
class TextLocation:
    """
    Represents a text region with character-level data and spatial information.
    
    Contains the OCR-extracted text as a list of CharacterData objects,
    along with the text region's bounding polygon and metadata.
    """
    uuid: str  # Unique identifier
    roi_uuid: str  # ROI identifier (e.g., '830-680-842-689')
    text_dict: List[CharacterData]  # Character-level data
    mask_shape: List[List[int]]  # Mask polygon coordinates
    pno: int  # Page number
    path: str  # Document file path
    color: str = '#0000FF'  # Display color code
    vertical_direction: Optional[int] = None  # For vertical text (CJK)
    
    def get_text_string(self) -> str:
        """Extract full text string from character list."""
        return ''.join(char.c for char in self.text_dict)
    
    def get_substring(self, start: int, end: Optional[int] = None) -> str:
        """Extract substring from character indices."""
        if end is None:
            return ''.join(char.c for char in self.text_dict[start:])
        return ''.join(char.c for char in self.text_dict[start:end])
    
    def get_text_without_whitespace(self) -> str:
        """Get text with all whitespace removed."""
        return ''.join(char.c for char in self.text_dict if not char.c.isspace())
    
    def get_character_at_index(self, index: int) -> Optional[CharacterData]:
        """Get character at specific index, or None if out of bounds."""
        if 0 <= index < len(self.text_dict):
            return self.text_dict[index]
        return None
    
    def find_substring_indices(self, substring: str) -> List[Tuple[int, int]]:
        """Find all occurrences of substring and return (start, end) indices."""
        text = self.get_text_string()
        indices = []
        start = 0
        while True:
            pos = text.find(substring, start)
            if pos == -1:
                break
            indices.append((pos, pos + len(substring)))
            start = pos + 1
        return indices
    
    def trim_leading_whitespace(self) -> None:
        """Remove leading whitespace characters (mutates text_dict)."""
        while self.text_dict and self.text_dict[0].c.isspace():
            self.text_dict.pop(0)
    
    def trim_trailing_whitespace(self) -> None:
        """Remove trailing whitespace characters (mutates text_dict)."""
        while self.text_dict and self.text_dict[-1].c.isspace():
            self.text_dict.pop()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            'uuid': self.uuid,
            'roi_uuid': self.roi_uuid,
            'text_dict': [char.to_dict() for char in self.text_dict],
            'mask_shape': self.mask_shape,
            'pno': self.pno,
            'path': self.path,
            'color': self.color,
            'vertical_direction': self.vertical_direction
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TextLocation':
        """Create TextLocation from dictionary."""
        return cls(
            uuid=data['uuid'],
            roi_uuid=data['roi_uuid'],
            text_dict=[CharacterData.from_dict(char) for char in data['text_dict']],
            mask_shape=data['mask_shape'],
            pno=data['pno'],
            path=data['path'],
            color=data.get('color', '#0000FF'),
            vertical_direction=data.get('vertical_direction')
        )


@dataclass
class RegionOfInterest:
    """
    Representation of a polygon region on a document page.
    
    ROI represents a spatial location on a document page..
    """
    points: Tuple[Tuple[int, int], ...]  # Corner points of the ROI polygon
    points_of_interests: Tuple[Tuple[int, int], ...]  # Point where the might be a line for P&ID
    pno: int  # Page number
    path: str  # Document path
    document_type: str = DocumentType.DRAWING.value  # Document type
    
    def __post_init__(self):
        """Validate ROI data structure."""
        if self.pno < 0:
            raise ValueError(f"Page number must be >= 0, got: {self.pno}")
        if not self.path.strip():
            raise ValueError("Path cannot be empty")
        for i, point in enumerate(self.points):
            if len(point) != 2:
                raise ValueError(f"Point {i} must be (x, y) tuple, got: {point}")
    
    @property
    def min_x(self) -> int:
        """Minimum X coordinate of bounding box."""
        return min(p[0] for p in self.points)
    
    @property
    def min_y(self) -> int:
        """Minimum Y coordinate of bounding box."""
        return min(p[1] for p in self.points)
    
    @property
    def max_x(self) -> int:
        """Maximum X coordinate of bounding box."""
        return max(p[0] for p in self.points)
    
    @property
    def max_y(self) -> int:
        """Maximum Y coordinate of bounding box."""
        return max(p[1] for p in self.points)
    
    @property
    def center(self) -> Tuple[int, int]:
        """Calculate center point of ROI."""
        return (
            int((self.min_x + self.max_x) / 2),
            int((self.min_y + self.max_y) / 2)
        )
    
    @property
    def width(self) -> int:
        """Calculate width of bounding box."""
        return self.max_x - self.min_x
    
    @property
    def height(self) -> int:
        """Calculate height of bounding box."""
        return self.max_y - self.min_y
    
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            'uuid': self.uuid,
            'points': [list(p) for p in self.points],
            'points_of_interests': self.points_of_interests,
            'pno': self.pno,
            'path': self.path,
            'document_type': self.document_type
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RegionOfInterest':
        """Create RegionOfInterest from dictionary."""
        return cls(
            uuid=data['uuid'],
            points=tuple(tuple(p) for p in data['points']),
            points_of_interests=tuple(tuple(p) for p in data.get('points_of_interests', [])),
            pno=data['pno'],
            path=data['path'],
            document_type=data.get('document_type', DocumentType.DRAWING.value)
        )
    
    @classmethod
    def from_roi_list_format(cls, uuid: str, points: List[Tuple[int, int]], points_of_interests: List[Tuple[int, int]], 
                            pno: int, path: str, document_type: str = DocumentType.DRAWING.value) -> 'RegionOfInterest':
        """
        Create RegionOfInterest from roi_list format (list of 4 tuples).
        
        Args:
            uuid: Unique identifier
            points: List of 4 (x, y) tuples representing corners
            pno: Page number
            path: Document path
            document_type: Document type
            
        Returns:
            RegionOfInterest instance
        """
        return cls(
            uuid=uuid,
            points=tuple(tuple(p) for p in points),
            points_of_interests=tuple(tuple(p) for p in points_of_interests),
            pno=pno,
            path=path,
            document_type=document_type
        )


@dataclass
class LinkedGraphic:
    """
    Complete graphic data with ROI reference, text locations, and transformations.
    
    Mutable container that aggregates ROI, text locations, image paths, and metadata
    for a linked graphic (primary or secondary).
    """
    uuid: str  # Unique identifier
    roi_uuid: str  # Unique ROI identifier
    path: str  # Document path
    pno: int  # Page number
    text_locations: Dict[str, TextLocation]  # Text locations by ID (dict format for flexibility)
    text_location_name_to_roi_name_map: Dict[str, str]  # Name mappings
    page_width: int  # Page dimensions
    page_height: int  # Page dimensions
    is_primary: bool = False  # primary is graphic with unique identifier
    
    # Image data (file paths)
    display_image: Optional[str] = None  # Path to display image
    template_image: Optional[str] = None  # Path to template image
    template_mask: Optional[str] = None  # Path to template mask
    template_and_text_mask: Optional[str] = None  # Path to combined mask
    
    # Image dimensions
    template_image_width: int = 0
    template_image_height: int = 0

    # Template rotation metadata
    template_rotation: List[int] = field(default_factory=list)  # Allowed rotation values
    
    # Processing metadata
    ocr_used: bool = False  # Whether OCR was used
    pdf_zoom_scale: float = 1.0  # Zoom scale used
    
    # Transformation (for secondary graphics)
    flip: Optional[int] = None  # Template flip (use TemplateFlip enum values)
    rotation: Optional[int] = None  # Rotation angle (use TemplateRotate enum values)
    
    # Document type
    document_type: str = DocumentType.DRAWING.value  # Document type
    
    # Template matching
    template_to_match_ratio: float = 0.0  # Template matching score
    
    def __post_init__(self):
        """Validate linked graphic data."""
        if self.page_width <= 0 or self.page_height <= 0:
            raise ValueError(f"Page dimensions must be > 0, got: {self.page_width}x{self.page_height}")
        if self.rotation is not None and self.rotation not in [0, 90, 180, 270]:
            raise ValueError(f"Invalid rotation: {self.rotation}. Must be 0, 90, 180, or 270")
        if len(self.roi) != 4:
            raise ValueError(f"ROI must have exactly 4 corner points, got: {len(self.roi)}")
    
    
    @property
    def center(self) -> Tuple[int, int]:
        """Calculate center point of ROI."""
        return (
            int((self.minX + self.maxX) / 2),
            int((self.minY + self.maxY) / 2)
        )
    
    def add_text_location(self, roi_name: str, text_location: TextLocation) -> None:
        """Add text location to dict (mutates text_location_dict)."""
        self.text_locations[roi_name] = text_location
    
    def get_text_location(self, roi_name: str) -> Optional[TextLocation]:
        """Get text location by ROI name."""
        return self.text_locations.get(roi_name)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            'uuid': self.uuid,
            'roi_uuid': self.roi_uuid,
            'path': self.path,
            'pno': self.pno,
            'text_locations': self.text_locations,
            'text_location_name_to_roi_name_map': self.text_location_name_to_roi_name_map,
            'display_image': self.display_image,
            'template_image': self.template_image,
            'template_mask': self.template_mask,
            'template_and_text_mask': self.template_and_text_mask,
            'template_image_width': self.template_image_width,
            'template_image_height': self.template_image_height,
            'ocr_used': self.ocr_used,
            'page_width': self.page_width,
            'page_height': self.page_height,
            'pdf_zoom_scale': self.pdf_zoom_scale,
            'flip': self.flip,
            'rotation': self.rotation,
            'document_type': self.document_type,
            'template_to_match_ratio': self.template_to_match_ratio,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LinkedGraphic':
        """Create LinkedGraphic from dictionary."""
        return cls(
            uuid=data['uuid'],
            roi_uuid=data['roi_uuid'],
            path=data['path'],
            pno=data['pno'],
            text_locations=data.get('text_locations', {}),
            text_location_name_to_roi_name_map=data.get('text_location_name_to_roi_name_map', {}),
            page_width=data['page_width'],
            page_height=data['page_height'],
            is_primary=data.get('is_primary', False),
            display_image=data.get('display_image'),
            template_image=data.get('template_image'),
            template_mask=data.get('template_mask'),
            template_and_text_mask=data.get('template_and_text_mask'),
            template_image_width=data.get('template_image_width', 0),
            template_image_height=data.get('template_image_height', 0),
            ocr_used=data.get('ocr_used', False),
            points_of_interests=data.get('points_of_interests', []),
            pdf_zoom_scale=data.get('pdf_zoom_scale', 1.0),
            flip=data.get('flip'),
            rotation=data.get('rotation'),
            document_type=data.get('document_type', DocumentType.DRAWING.value),
            template_to_match_ratio=data.get('template_to_match_ratio', 0.0)
        )


@dataclass
class ControlModule:
    """
    Complete control module data structure.
    
    Represents an object in Application Code Manager (ACM) used to control a process.
    Contains an array of linked graphics (primary and secondary) and linked text.
    """
    uuid: str  # Unique identifier
    name: str  # Module name
    description: str  # Module description
    type: str  # Object type / Group ID
    linked_graphics: List[str]  # Array of linked graphic data (primary and secondary)
    linked_texts: list[str]  # Linked text mappings
    
    def get_primary_graphic(self) -> Optional[LinkedGraphic]:
        """Get the primary linked graphic (first graphic with is_primary=True)."""
        for graphic in self.linked_graphics:
            if graphic.get('is_primary', False):
                return graphic
        return None
    
    def get_secondary_graphics(self) -> List[LinkedGraphic]:
        """Get all secondary linked graphics (graphics with is_primary=False)."""
        return [g for g in self.linked_graphics if not g.get('is_primary', False)]
    
    def add_linked_graphic(self, graphic: LinkedGraphic) -> None:
        """Add a linked graphic to the array."""
        self.linked_graphics.append(graphic)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            'uuid': self.uuid,
            'name': self.name,
            'description': self.description,
            'type': self.type,
            'linked_graphics': self.linked_graphics,
            'linked_text': self.linked_text,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ControlModule':
        """Create ControlModule from dictionary."""
        
        return cls(
            uuid=data.get('uuid', data.get('id', '')),  # Support legacy 'id' field
            name=data['name'],
            description=data['description'],
            type=data['type'],
            path=data['path'],
            pno=data['pno'],
            linked_graphics=data.get('linked_text', {}),
            linked_text=data.get('linked_text', {}),
        )


# Migration utility functions

def migrate_control_module_dict(control_module: Dict[str, Any]) -> Dict[str, Any]:
    """
    Migrates old control module dicts to use new dataclasses.
    
    Args:
        control_module: Control module dictionary
        
    Returns:
        Updated dict with dataclass instances where applicable
    """
    # For now, return as-is since we're maintaining dict format in database
    # In future phases, can convert nested structures to dataclasses
    return control_module


def migrate_document_dict(document: Dict[str, Any]) -> Dict[str, Any]:
    """
    Migrates old document dicts to standardized format.
    
    Ensures compatibility between database storage format and Document dataclass.
    Normalizes field names and sets defaults for missing fields.
    
    Args:
        document: Document dictionary
        
    Returns:
        Updated dict with standardized fields
    """
    # Normalize 'type' field (handle legacy naming)
    if 'document_type' in document and 'type' not in document:
        document['type'] = document['document_type']
    
    # Set default zoom scale based on document type
    if 'pdf_zoom_scale' not in document:
        doc_type = document.get('type', DocumentType.DRAWING.value)
        document['pdf_zoom_scale'] = 2.0 if doc_type in [DocumentType.DRAWING.value, DocumentType.TEXT.value] else 1.0
    
    # Set default page count
    if 'page_count' not in document:
        document['page_count'] = 1
    
    # Set default processing flags
    document.setdefault('ocr_used', False)
    document.setdefault('border_check_completed', False)
    
    return document


def validate_roi_structure(roi_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validates ROI data integrity before conversion.
    
    Args:
        roi_data: ROI dictionary data
        
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    
    if 'points' not in roi_data:
        errors.append("Missing 'points' field")
    elif len(roi_data['points']) != 4:
        errors.append(f"ROI must have 4 points, got {len(roi_data['points'])}")
    
    if 'pno' not in roi_data:
        errors.append("Missing 'pno' field")
    elif not isinstance(roi_data['pno'], int) or roi_data['pno'] < 0:
        errors.append(f"Invalid page number: {roi_data.get('pno')}")
    
    if 'path' not in roi_data:
        errors.append("Missing 'path' field")
    elif not roi_data['path'].strip():
        errors.append("Path cannot be empty")
    
    return (len(errors) == 0, errors)


def validate_document_structure(document_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validates document data integrity before conversion.
    
    Args:
        document_data: Document dictionary data
        
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    
    # Required fields
    if 'name' not in document_data:
        errors.append("Missing 'name' field")
    elif not document_data['name'].strip():
        errors.append("Document name cannot be empty")
    
    if 'path' not in document_data:
        errors.append("Missing 'path' field")
    elif not document_data['path'].strip():
        errors.append("Document path cannot be empty")
    
    if 'timestamp' not in document_data:
        errors.append("Missing 'timestamp' field")
    elif not isinstance(document_data['timestamp'], (int, float)):
        errors.append(f"Invalid timestamp type: {type(document_data['timestamp'])}")
    
    # Type validation (support both 'type' and 'document_type' keys)
    doc_type = document_data.get('type') or document_data.get('document_type')
    if not doc_type:
        errors.append("Missing document type field")
    elif doc_type not in [DocumentType.DRAWING.value, DocumentType.IMAGE.value, 
                          DocumentType.TEXT.value, DocumentType.TABLE.value]:
        errors.append(f"Invalid document type: {doc_type}")
    
    # Page count validation
    if 'page_count' in document_data:
        if not isinstance(document_data['page_count'], int) or document_data['page_count'] < 1:
            errors.append(f"Invalid page count: {document_data.get('page_count')}")
    
    # Zoom scale validation
    if 'pdf_zoom_scale' in document_data:
        if not isinstance(document_data['pdf_zoom_scale'], (int, float)) or document_data['pdf_zoom_scale'] <= 0:
            errors.append(f"Invalid pdf_zoom_scale: {document_data.get('pdf_zoom_scale')}")
    
    return (len(errors) == 0, errors)
