import copy
import json
import logging
import os
import re
import textwrap
import time
import uuid
from typing import List, Tuple

import numpy as np
import pandas as pd
import requests

from bin.logic_acm_data_handler import ACM_Data_Handler
from bin.logic_acm_libraries_retrieval import get_library_file_path
from bin.logic_acm_library_parser import acm_library_parser
from bin.logic_config import Config
from bin.logic_extracted_logic_to_rockwell_code import LogicToRockwellConverter
from bin.logic_internal_database import Database
from bin import logic_safe_regex as safe_regex
from bin.logic_linked_texts import LinkedText, TagnameParameterRelationship, GivenTextLink, TargetTextType
from bin.logic_llm_inference import UnifiedInference
from bin.gui_libary_rules_view import acm_libraries_retrieval


TAGNAME_REGEX = r'\b([A-Z0-9]{2,}[-_][A-Z0-9]{2,}[-_][A-Z0-9]{2,})\b|\b([A-Z0-9]{2,}[-_]\d+)\b'

# PlantPAx libraries whose status references are deliberately narrowed before the
# LLM sees them, keyed by ACM catalog number. Libraries absent from this map keep
# their full reference list.
LIBRARY_STATUS_REFERENCE_ALLOWLIST = {
    'PMTR': ('Sts_Stopped', 'Sts_Running1', 'Sts_Running2', 'Sts_Ready',
             'PCmd_Stop', 'PCmd_Start1', 'PCmd_Start2'),
    'PVSD': ('Sts_Stopped', 'Sts_Running1', 'Sts_Running2', 'Sts_Ready',
             'PCmd_Stop', 'PCmd_Start1', 'PCmd_Start2', 'Sts_AtSpeed'),
    'PVLV': ('Sts_Pos1', 'Sts_Pos2', 'PCmd_Pos1', 'PCmd_Pos2'),
    'PAI': ('Sts_Hi', 'Sts_HiHi', 'Sts_Lo', 'Sts_LoLo',
            'Cfg_HiLim', 'Cfg_HiHiLim', 'Cfg_LoLim', 'Cfg_LoLoLim'),
    'PDI': ('Sts_TgtDisagree',),
}


def allowed_status_references(catalog_number, reference_names) -> list:
    """
    Restrict the status references offered to the LLM for an ACM library.

    :param catalog_number: ACM catalog number of the object's library, e.g. ``PMTR``
    :type catalog_number: str
    :param reference_names: Reference/NIB names available in the library
    :type reference_names: iterable[str]
    :return: The allowed reference names, in their original order
    :rtype: list[str]
    """
    allowlist = LIBRARY_STATUS_REFERENCE_ALLOWLIST.get(str(catalog_number or '').strip().upper())
    if not allowlist:
        return list(reference_names)

    allowed = {name.upper() for name in allowlist}
    return [name for name in reference_names if str(name).upper() in allowed]


def _normalize_annotation_field(value) -> str:
    """
    Normalize a single field (tagname / parameter name / parameter value) for
    use in a text-link annotation dedupe key. Lower-cases, strips surrounding
    whitespace, and treats ``None`` as the empty string so keys stay
    comparable regardless of which LLM pass produced them.
    """
    if value is None:
        return ""
    return str(value).strip().lower()


def annotation_dedupe_key(tagname, parameter_name, parameter_value) -> tuple:
    """
    Canonical dedupe key for a text-link annotation.

    Two annotations that resolve to the same ``(tagname, parameter_name,
    parameter_value)`` triple (case-insensitive, whitespace-stripped) represent
    the same logical annotation and should not be processed twice — regardless
    of which LLM path emitted them.
    """
    return (
        _normalize_annotation_field(tagname),
        _normalize_annotation_field(parameter_name),
        _normalize_annotation_field(parameter_value),
    )


# Documents cross-reference the ACM object tag in brackets beside the equipment tag,
# e.g. "Raw Feed Transfer Pump A P-2010A (UX00201)".
_BRACKETED_TAG_PATTERN = re.compile(r'[(\[]\s*([A-Za-z]{1,4}[-_ ]?\d{2,6}[A-Za-z]?)\s*[)\]]')

# Context dictionaries vary by context_type; these are the keys that carry source text.
_CONTEXT_TEXT_KEYS = ('list_heading', 'full_list', 'full_sentence', 'text_blocks_string', 'full_table')


def _normalize_tag(value) -> str:
    return re.sub(r'[^a-zA-Z0-9]', '', str(value or '')).upper()


def context_source_text(highlighted_text, context) -> str:
    """
    Flatten the text a tagname was extracted from, for use as alias lookup material.
    """
    parts = [str(highlighted_text or '')]
    if isinstance(context, dict):
        parts.extend(str(context.get(key, '') or '') for key in _CONTEXT_TEXT_KEYS)
    return '\n'.join(part for part in parts if part)


def extract_bracketed_tag_aliases(source_text, tagname) -> list:
    """
    Bracketed tags sitting on the same line as ``tagname`` in ``source_text``.

    Only lines mentioning the tagname are searched, so a page listing several objects
    cannot donate a neighbour's tag. An ambiguous line (two different bracketed tags)
    yields nothing rather than a guess.
    """
    normalized_tagname = _normalize_tag(tagname)
    if not source_text or not normalized_tagname:
        return []

    aliases = {}
    for line in str(source_text).splitlines():
        if normalized_tagname not in _normalize_tag(line):
            continue
        for match in _BRACKETED_TAG_PATTERN.finditer(line):
            alias = match.group(1).strip()
            normalized_alias = _normalize_tag(alias)
            if normalized_alias and normalized_alias != normalized_tagname:
                aliases.setdefault(normalized_alias, alias)

    return list(aliases.values()) if len(aliases) == 1 else []


def lookup_acm_object(acm_data_handler, tagname, source_text=None):
    """
    Resolve a document tagname to ACM objects, retrying with a bracketed alias from the
    source text when the tagname itself names nothing in ACM.

    :return: Matching objects, or an empty DataFrame when nothing resolves.
    :rtype: pandas.DataFrame
    """
    if not acm_data_handler or not tagname:
        return pd.DataFrame()

    objects_df = acm_data_handler.get_object_with_tagname_like(tagname)
    if not objects_df.empty:
        return objects_df

    for alias in extract_bracketed_tag_aliases(source_text, tagname):
        objects_df = acm_data_handler.get_object_with_tagname_like(alias)
        if not objects_df.empty:
            logging.info(f"Resolved tagname '{tagname}' to ACM object '{alias}' "
                         f"via the bracketed reference in the source document.")
            return objects_df

    return pd.DataFrame()


def match_substring_indexes(text1: str, text2: str, min_threshold: int = 2) -> tuple[list[list[int]], list[list[int]]] | None:
    """
    Find matching substring between two texts and return the character index ranges.
    
    Args:
        text1: First text string
        text2: Second text string
        min_threshold: Minimum number of characters that must match (default: 2)
    
    Returns:
        Tuple of (ranges_in_text1, ranges_in_text2) if a match is found, None otherwise.
        Each list contains [start, end] pairs representing continuous character ranges (inclusive).
    
    Example:
        >>> match_substring_indexes("TI00143", "55-TI-00143")
        ([[0, 6]], [[3, 4], [6, 10]])
    """
    if not text1 or not text2:
        return None
    
    best_match = None
    best_length = 0
    
    # Try all possible substrings of text1
    for i in range(len(text1)):
        for j in range(i + min_threshold, len(text1) + 1):
            substring = text1[i:j]
            
            # Check if this substring exists in text2
            pos = text2.find(substring)
            if pos != -1:
                match_length = len(substring)
                if match_length > best_length:
                    best_length = match_length
                    best_match = {
                        'text1_start': i,
                        'text1_end': j,
                        'text2_start': pos,
                        'text2_end': pos + match_length
                    }
    
    if best_match is None:
        return None
    
    # Build ranges by finding continuous sequences
    def build_ranges(text1_chars, text2_chars):
        """Convert matched character positions to continuous ranges."""
        ranges_text1 = []
        ranges_text2 = []
        
        i = 0
        while i < len(text1_chars):
            start1 = best_match['text1_start'] + i
            start2 = best_match['text2_start'] + i
            
            # Find continuous sequence in both texts
            j = i
            while j < len(text1_chars) - 1:
                if (best_match['text2_start'] + j + 1) == (best_match['text2_start'] + j) + 1:
                    j += 1
                else:
                    break
            
            end1 = best_match['text1_start'] + j
            end2 = best_match['text2_start'] + j
            
            ranges_text1.append([start1, end1])
            ranges_text2.append([start2, end2])
            i = j + 1
        
        return ranges_text1, ranges_text2
    
    # For text1, it's always continuous
    ranges_text1 = [[best_match['text1_start'], best_match['text1_end'] - 1]]
    
    # For text2, find continuous ranges
    ranges_text2 = []
    substring = text1[best_match['text1_start']:best_match['text1_end']]
    text2_pos = best_match['text2_start']
    
    i = 0
    while i < len(substring):
        # Skip non-matching characters in text2
        while text2_pos < len(text2) and text2[text2_pos] != substring[i]:
            text2_pos += 1
        
        if text2_pos >= len(text2):
            break
        
        # Start of a continuous range
        range_start = text2_pos
        
        # Find continuous matching characters
        while i < len(substring) and text2_pos < len(text2) and text2[text2_pos] == substring[i]:
            i += 1
            text2_pos += 1
        
        ranges_text2.append([range_start, text2_pos - 1])
    
    return (ranges_text1, ranges_text2)


def match_all_substrings(text1: str, text2: str, min_threshold: int = 2) -> list[tuple[list[list[int]], list[list[int]]]]:
    """
    Find all non-overlapping matching substrings between two texts.
    
    Args:
        text1: First text string
        text2: Second text string
        min_threshold: Minimum number of characters that must match (default: 2)
    
    Returns:
        List of tuples, each containing (ranges_in_text1, ranges_in_text2).
        Each list contains [start, end] pairs representing continuous character ranges (inclusive).
    
    Example:
        >>> match_all_substrings("TI00143", "55-TI-00143")
        [([[0, 6]], [[3, 4], [6, 10]])]
    """
    matches = []
    used_text1 = set()
    used_text2 = set()
    
    # Find all possible matches
    all_matches = []
    for i in range(len(text1)):
        for j in range(i + min_threshold, len(text1) + 1):
            substring = text1[i:j]
            
            # Find all occurrences in text2
            pos = 0
            while True:
                pos = text2.find(substring, pos)
                if pos == -1:
                    break
                
                all_matches.append({
                    'length': len(substring),
                    'text1_range': (i, j),
                    'text2_range': (pos, pos + len(substring))
                })
                pos += 1
    
    # Sort by length (longest first) to prioritize longer matches
    all_matches.sort(key=lambda x: x['length'], reverse=True)
    
    # Select non-overlapping matches
    for match in all_matches:
        text1_indexes = set(range(match['text1_range'][0], match['text1_range'][1]))
        text2_indexes = set(range(match['text2_range'][0], match['text2_range'][1]))
        
        # Check if these indexes are already used
        if not (text1_indexes & used_text1) and not (text2_indexes & used_text2):
            used_text1.update(text1_indexes)
            used_text2.update(text2_indexes)
            
            # Build ranges for this match
            substring = text1[match['text1_range'][0]:match['text1_range'][1]]
            ranges_text1 = [match['text1_range'][0], match['text1_range'][1] - 1]
            
            # For text2, find continuous ranges
            ranges_text2 = []
            text2_pos = match['text2_range'][0]
            i = 0
            
            while i < len(substring):
                # Skip non-matching characters in text2
                while text2_pos < len(text2) and text2[text2_pos] != substring[i]:
                    text2_pos += 1
                
                if text2_pos >= len(text2):
                    break
                
                # Start of a continuous range
                range_start = text2_pos
                
                # Find continuous matching characters
                while i < len(substring) and text2_pos < len(text2) and text2[text2_pos] == substring[i]:
                    i += 1
                    text2_pos += 1
                
                ranges_text2.append(range_start)
                ranges_text2.append(text2_pos - 1)
            
            matches.append((substring, ranges_text1, ranges_text2))
    
    return matches


def get_text_within_bbox(bbox, text_in_page=None, get_font=False):
    # ``end`` is exclusive so callers can slice ``text_in_page[start:end]``.
    text = ''
    start = np.inf
    end = 0
    for i in range(len(text_in_page)):
        char = text_in_page[i]
        char_bbox = char['bbox']
        if (char_bbox[0] >= bbox[0] and 
            char_bbox[2] <= bbox[2] and 
            char_bbox[1] >= bbox[1] and 
            char_bbox[3] <= bbox[3]):
            text += char['c']
            if i < start:
                start = i
            if i >= end:
                end = i + 1
        if get_font:
            font = char.get('font', None)
    if text and get_font:
        return [text, [start,end], font]
    elif text:
        return [text, [start,end]]

def is_rectangle_overlap(R1, R2):
    if (int(R1[0])>=int(R2[2])) or (int(R1[2])<=int(R2[0])) or (int(R1[3])<=int(R2[1])) or (int(R1[1])>=int(R2[3])):
        return False
    else:
        return True

def get_table_cell_overlapping_bbox(selected_table, bbox, text_in_page):

    # Find the cell within the selected table that overlaps with the bbox
    for row_index, row in enumerate(selected_table.rows):
        for col_index, cell in enumerate(row.cells):
            if cell and is_rectangle_overlap(bbox, cell):
                selected_cell = [row_index, col_index]
                selected_cell_full_text, selected_cell_full_indexes = get_text_within_bbox(selected_table.rows[row_index].cells[col_index], text_in_page=text_in_page)
                selected_table_shape = [selected_table.col_count,selected_table.row_count]
                return selected_cell, selected_cell_full_text, selected_cell_full_indexes, selected_table_shape, selected_table.bbox

    return None, None, None, None, None

def text_indent_remove(text: str) -> str:
    lines = text.splitlines()
    stripped_lines = [line.lstrip() for line in lines]
    return "\n".join(stripped_lines)

def is_bbox_within_bbox(bbox1, bbox2):
    return bbox1[0] >= bbox2[0] and bbox1[1] >= bbox2[1] and bbox1[2] <= bbox2[2] and bbox1[3] <= bbox2[3]

def which_cell_contains_text(table, text_bbox):
    for r, row in enumerate(table.rows):
        for c, cell in enumerate(row.cells):
            if cell and is_bbox_within_bbox(text_bbox, cell):
                return (r, c)
    return (None, None)

def get_text_in_bbox(table, row, column, text_in_page, bbox=None):
        # ``end_index`` is exclusive so callers can slice ``text_in_page[start:end]``.
        if bbox:
            cell_bbox = bbox
        else:
            rows = getattr(table, 'rows', None) or []
            if row is None or column is None or row < 0 or row >= len(rows):
                return {'text': '', 'indexes': (np.inf, 0)}
            cells = getattr(rows[row], 'cells', None) or []
            if column < 0 or column >= len(cells):
                return {'text': '', 'indexes': (np.inf, 0)}
            cell_bbox = cells[column]

        chars = ''
        start_index = np.inf
        end_index = 0

        if cell_bbox is None:
            return {'text': chars, 'indexes':(start_index,end_index)}
        
        for i, char in enumerate(text_in_page):
            if is_bbox_within_bbox(char['bbox'],cell_bbox):
                chars += char['c']
                if i < start_index:
                    start_index = i
                if i >= end_index:
                    end_index = i + 1

        return {'text': chars, 'indexes':(start_index,end_index)}





class TextDocumentLLMPreprocessor:
    """
    Classifier and Extractor for industrial automation text elements using UnifiedInference LLM
    
    Classifies highlighted text as:
    - Parameter: Industrial automation object parameter definition
    - Interlock: Condition based on another industrial automation object  
    - Sequence Step: Part of a sequence involving multiple industrial automation objects
    """
    
    # Classification categories
    PARAMETER = "parameter"
    INTERLOCK = "interlock" 
    SEQUENCE_STEP = "sequence_step"
    UNKNOWN = "unknown"
    
    def __init__(self, llm, project_name, acm_data_handler:ACM_Data_Handler=None,config=None):
        """
        Initialize the classifier with a UnifiedInference LLM client
        
        :param llm_provider: LLM provider to use ("ollama" or "openai")
        :type llm_provider: str
        :param llm_kwargs: Additional arguments for the LLM client
        """
        self.llm = llm
        self.project_name = project_name
        self.acm_data_handler = acm_data_handler
        self.config = config
        
        
        # System prompt template for classification
        self.system_prompt = text_indent_remove("""\
            You are an expert in industrial automation and control systems. Your task is to classify highlighted text from industrial automation documentation.

            The highlighted text may be:
            - A single cell from a table (with table header and row context provided)
            - A single item from a list (with list heading context provided)
            - Any other text fragment from industrial automation documentation

            Classification Categories:
            1. PARAMETER: An industrial automation object parameter definition (e.g., setpoints, ranges, units, alarm limits, control parameters, configuration values)
            2. INTERLOCK: A condition or logic based on another industrial automation object (e.g., safety conditions, permissive logic, equipment status checks, dependencies)
            3. SEQUENCE_STEP: Part of a sequence of steps involving multiple industrial automation objects (e.g., batch operations, startup procedures, control sequences, procedural steps)
            4. UNKNOWN: Text that doesn't clearly fit the above categories

            Examples:

            Table Context Examples:
            - Header: "|Tag|Setpoint|Unit|" Row: "|TIC-101|85|°C|" Highlighted: "85" → PARAMETER
            - Header: "|Step|Action|Condition|" Row: "|1|Start pump|Tank level > 50%|" Highlighted: "Tank level > 50%" → INTERLOCK
            - Header: "|Step|Description|Duration|" Row: "|3|Heat to temperature|30 min|" Highlighted: "Heat to temperature" → SEQUENCE_STEP

            List Context Examples:
            - Heading: "Alarm Limits" Item: "High: 100°C" → PARAMETER
            - Heading: "Safety Interlocks" Item: "Motor stopped and valve closed" → INTERLOCK  
            - Heading: "Startup Sequence" Item: "Open inlet valve" → SEQUENCE_STEP

            General Examples:
            - "Temperature setpoint: 85°C" → PARAMETER
            - "Pump P-101 running and valve V-205 open" → INTERLOCK  
            - "Step 3: Open valve V-101, wait 30 seconds, then start pump P-102" → SEQUENCE_STEP
            - "The weather is sunny today" → UNKNOWN

            Respond with only the classification category in uppercase.""")

    
    
    def identify_table_headers(self, table_text: str) -> Tuple[List[int], List[str]]:
        """
        Use LLM to identify which lines in a table are headers and extract header text.
        
        Args:
            table_text: Table text to analyze
            
        Returns:
            Tuple of (header_line_indices, header_texts)
        """
        try:
            prompt = text_indent_remove(f"""\
                You are an expert in industrial automation and control systems.
                Analyze the following TABLE and identify which rows contain column headers.

                Table:
                {table_text}

                Extract:
                1. headers: Array of actual header text extracted from those rows
                2. header_rows: Array of rows numbers (0-based) that contain headers
                

                Respond in JSON format with this structure:
                {{
                    "headers": "extracted_headers",
                    "header_rows": "header_rows"
                    
                }}

                If no clear headers are found, return {{"headers": [] ,"header_rows": []}}.

                Response:""")
            
            
            messages=[{"role": "user", "content": prompt}]

            response = self.llm.chat(
                messages=messages,
                temperature=0.1,
                max_tokens=10000,
                think=False
            )
            
            # Parse JSON response
            if response.startswith('{'):
                data = json.loads(response)
            else:
                # Try to extract JSON from response
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())
                else:
                    raise ValueError("No valid JSON found")
            
            header_rows = data.get('header_rows', [])
            headers = data.get('headers', [])
            
            return header_rows, headers
        
        except requests.exceptions.ConnectionError as e:
            raise
        except Exception as e:
            logging.error(f"LLM header identification failed {e}")
            



    def _identify_list_spans(self, text: str) -> List[Tuple[int, int, str]]:
        """
        Identify list structures in text.
        
        Args:
            text: Input text to analyze
            
        Returns:
            List of list spans
        """
        list_spans = []
        
        # Pattern 1: Bulleted lists (-, *, •)
        bullet_pattern = r'(?:^|\n)((?:\s*[-*•]\s+[^\n]+\n?){2,})'
        bullet_matches = re.finditer(bullet_pattern, text, re.MULTILINE)
        
        for match in bullet_matches:
            list_text = match.group(1).strip()
            if self._is_parameter_list(list_text):
                start_idx = match.start(1)
                end_idx = match.end(1)
                list_spans.append((start_idx, end_idx, list_text))
        
        # Pattern 2: Numbered lists (1., 2., a), b), etc.)
        numbered_pattern = r'(?:^|\n)((?:\s*(?:\d+\.|[a-z]\)|[A-Z]\))\s+[^\n]+\n?){2,})'
        numbered_matches = re.finditer(numbered_pattern, text, re.MULTILINE)
        
        for match in numbered_matches:
            list_text = match.group(1).strip()
            if self._is_parameter_list(list_text):
                start_idx = match.start(1)
                end_idx = match.end(1)
                list_spans.append((start_idx, end_idx, list_text))
        
        # Pattern 3: Key-value pair lists
        kv_pattern = r'(?:^|\n)((?:\s*[^\n:]+:\s*[^\n]+\n?){2,})'
        kv_matches = re.finditer(kv_pattern, text, re.MULTILINE)
        
        for match in kv_matches:
            list_text = match.group(1).strip()
            if self._is_parameter_list(list_text):
                start_idx = match.start(1)
                end_idx = match.end(1)
                list_spans.append((start_idx, end_idx, list_text))
        
        return list_spans
    

    def _identify_list_context(self, list_text: str) -> List[str]:
        """
        Identify context or headers for list processing.
        
        Args:
            list_text: List text to analyze
            
        Returns:
            List of context elements
        """
        # Look for patterns that might indicate list structure
        context = []
        
        # Check for key-value patterns
        if ':' in list_text:
            context.append("Key-value pairs")
        
        # Check for common industrial automation terms
        list_lower = list_text.lower()
        if any(term in list_lower for term in ['alarm', 'limit', 'setpoint', 'config']):
            context.append("Industrial parameters")
        
        # Check for tagname patterns
        tagname_patterns = [
                r'\b[A-Z]{2,4}\d{3,5}\b',  # e.g., LIT1005, FIT2001, TIC3004
                r'\b[A-Z]+_[A-Z0-9_]+\b',  # e.g., TANK_LEVEL_01
                r'\b[A-Z]{1,3}-\d{2,4}[A-Z]?\b',  # e.g., P-101A, T-201
            ]
        
        if any(re.search(pattern, list_text) for pattern in tagname_patterns):
            context.append("Contains tagnames")
        
        return context if context else ["General list"]


    def classify_text(self, highlighted_text, context=None, context_type="general", temperature=0.1, max_tokens=1000):
        """
        Classify highlighted text in industrial automation context
        
        :param highlighted_text: The highlighted text to classify
        :type highlighted_text: str
        :param context_text: Additional context around the highlighted text
        :type context_text: str
        :param context_type: Type of context ("table", "list", or "general")
        :type context_type: str
        :param temperature: LLM temperature for classification consistency
        :type temperature: float
        :param max_tokens: Maximum tokens for response
        :type max_tokens: int
        :return: Classification result with category and confidence
        :rtype: dict
        """
        try:
            

            # Prepare the classification prompt based on context type
            if context_type == "table" and context:
                
                selected_row, selected_column = context['row_and_column']

                user_prompt = text_indent_remove(f"""\
                    Classify the following highlighted text from a table cell in industrial automation documentation:

                    TABLE CONTEXT: 
                    {context['full_table']}

                    HIGHLIGHTED CELL CONTENT: "{highlighted_text}"
                    HIGHLIGHTED CELL COLUMN: "{selected_column}"
                    HIGHLIGHTED CELL ROW: "{selected_row}"


                    The table context shows the table header and the full row containing the highlighted cell.
                    Consider the column meaning and row data when classifying the highlighted text.

                    Classification:""")
            
            elif context_type == "list" and context:
                # For list items, provide list heading context
                user_prompt = text_indent_remove(f"""\
                    Classify the following highlighted text from a list item in industrial automation documentation:

                    LIST HEADING: {context['list_heading']}
                    HIGHLIGHTED LIST ITEM: "{highlighted_text}"

                    The list heading provides context about what type of information the list contains.
                    Consider the list purpose when classifying the highlighted item.

                    Classification:""")
            
            else:
                # General context
                user_prompt = text_indent_remove(f"""\
                    Classify the following highlighted text from industrial automation documentation:

                    CONTEXT: "{context['text_blocks_string']}"


                    HIGHLIGHTED TEXT: "{highlighted_text}"

                    Classification:""")

            # Create messages for chat completion
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_prompt}
            ]

            start_time = time.time()
            
            # Get classification from LLM
            response = self.llm.chat(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )

            print(f"LLM classification took {time.time() - start_time:.2f} seconds")
            
            # Parse response and normalize
            classification = response.strip().upper()
            
            # Map to standard categories
            category_mapping = {
                "PARAMETER": self.PARAMETER,
                "INTERLOCK": self.INTERLOCK,
                "SEQUENCE_STEP": self.SEQUENCE_STEP,
                "SEQUENCE": self.SEQUENCE_STEP,
                "STEP": self.SEQUENCE_STEP,
                "UNKNOWN": self.UNKNOWN
            }
            
            # Find best match
            final_category = self.UNKNOWN
            for key, value in category_mapping.items():
                if key in classification:
                    final_category = value
                    break
            
            # Calculate confidence based on response clarity
            confidence = self._calculate_confidence(response, final_category)

            return {
                "category": final_category,
                "confidence": confidence,
                "raw_response": response.strip(),
                "highlighted_text": highlighted_text,
                "context": context,
                "context_type": context_type
            }
        
        except requests.exceptions.ConnectionError as e:
            raise
        except Exception as e:
            return {
                "category": self.UNKNOWN,
                "confidence": 0.0,
                "error": str(e),
                "highlighted_text": highlighted_text,
                "context": context,
                "context_type": context_type
            }
    
    def classify_batch(self, text_items, temperature=0.1, max_tokens=1000):
        """
        Classify multiple text items in batch
        
        :param text_items: List of dicts with 'text' and optional 'context' keys
        :type text_items: list
        :param temperature: LLM temperature for classification
        :type temperature: float
        :param max_tokens: Maximum tokens per response
        :type max_tokens: int
        :return: List of classification results
        :rtype: list
        """
        results = []
        
        for item in text_items:
            if isinstance(item, str):
                text = item
                context = ""
            elif isinstance(item, dict):
                text = item.get('text', '')
                context = item.get('context', '')
            else:
                results.append({
                    "category": self.UNKNOWN,
                    "confidence": 0.0,
                    "error": "Invalid input format",
                    "highlighted_text": str(item),
                    "context": ""
                })
                continue
            
            result = self.classify_text(text, context, temperature, max_tokens)
            results.append(result)
        
        return results
    
    def get_classification_summary(self, results):
        """
        Generate summary statistics from classification results
        
        :param results: List of classification results
        :type results: list
        :return: Summary statistics
        :rtype: dict
        """
        if not results:
            return {"total": 0, "categories": {}, "average_confidence": 0.0}
        
        category_counts = {
            self.PARAMETER: 0,
            self.INTERLOCK: 0,
            self.SEQUENCE_STEP: 0,
            self.UNKNOWN: 0
        }
        
        total_confidence = 0.0
        error_count = 0
        
        for result in results:
            category = result.get("category", self.UNKNOWN)
            confidence = result.get("confidence", 0.0)
            
            if "error" in result:
                error_count += 1
            
            category_counts[category] = category_counts.get(category, 0) + 1
            total_confidence += confidence
        
        average_confidence = total_confidence / len(results) if results else 0.0
        
        return {
            "total": len(results),
            "categories": category_counts,
            "average_confidence": round(average_confidence, 3),
            "error_count": error_count,
            "success_rate": round((len(results) - error_count) / len(results) * 100, 1) if results else 0.0
        }
    
    def _calculate_confidence(self, response, category):
        """
        Calculate confidence score based on response clarity
        
        :param response: Raw LLM response
        :type response: str
        :param category: Determined category
        :type category: str
        :return: Confidence score between 0.0 and 1.0
        :rtype: float
        """
        response_upper = response.upper()
        
        # High confidence if exact category match
        if category.upper() in response_upper:
            if len(response.strip()) <= 20:  # Concise response
                return 0.95
            else:
                return 0.85
        
        # Medium confidence for partial matches
        category_keywords = {
            self.PARAMETER: ["PARAM", "SET", "LIMIT", "VALUE", "RANGE"],
            self.INTERLOCK: ["CONDITION", "LOGIC", "SAFETY", "PERMISSIVE"],
            self.SEQUENCE_STEP: ["STEP", "SEQUENCE", "PROCEDURE", "OPERATION"],
            self.UNKNOWN: ["UNKNOWN", "UNCLEAR", "NOT"]
        }
        
        keywords = category_keywords.get(category, [])
        for keyword in keywords:
            if keyword in response_upper:
                return 0.70
        
        # Default low confidence
        return 0.50
    

    
    def extract_tagname(self, highlighted_text, context=None, context_type="general", temperature=0.1, max_tokens=1000):
        """
        Extract tagname/instrument identifier from highlighted text
        
        :param highlighted_text: The highlighted text to extract tagname from
        :type highlighted_text: str
        :param context: Context dictionary with appropriate keys for context type
        :type context: dict
        :param context_type: Type of context ("table", "list", or "general")
        :type context_type: str
        :param temperature: LLM temperature for extraction consistency
        :type temperature: float
        :param max_tokens: Maximum tokens for response
        :type max_tokens: int
        :return: Extraction result with tagname and confidence
        :rtype: dict
        """
        try:
            extraction_prompt = text_indent_remove(f"""\
                You are an expert in industrial automation tag naming conventions. Extract the tagname (instrument identifier) from the highlighted text.

                Common tagname patterns:
                - Temperature Indicators: TIT-101, TIC-205, TE-301, 200-TI-0025
                - Pressure Indicators: PIT-101, PIC-205, PE-301, 300-PI-0115  
                - Flow Indicators: FIT-101, FIC-205, FE-301, 250-FT-0088
                - Level Indicators: LIT-101, LIC-205, LE-301, 400-LI-0200
                - Valve Tags: HV-101, CV-205, XV-301, 100-HV-0112
                - Motor/Equipment Tags: M-101, P-205, FAN-301, 200-PP-0017
                - Generic formats: [Type][Function]-[Number], [Type][Number], [Area]-[Type]-[Number]

                Examples:
                - "Temperature setpoint TIC-101: 85°C" → TIC-101
                - "Pump P-205 motor current" → P-205
                - "Table row: |TIC-301|85|°C|" → TIC-301
                - "Valve XV-105 position feedback" → XV-105
                - "Pump 200-PP-0017 discharge pressure" → 200-PP-0017
                - "Temperature indicator 300-TI-0025 reading" → 300-TI-0025
                - "Flow transmitter 250-FT-0088 calibration" → 250-FT-0088
                - "Level transmitter (230-LT-0094) calibration" → 230-LT-0094

                If no clear tagname is found, respond with "NONE".
                Respond with only the tagname or "NONE".""")

            # Prepare context-specific prompt
            if context_type.lower() == "table" and context:
                

                selected_row, selected_column = context['row_and_column']

                user_prompt = text_indent_remove(f"""\
                    Extract the tagname from this table context:

                    TABLE CONTEXT: 
                    {context['full_table']}

                    HIGHLIGHTED CELL CONTENT: "{highlighted_text}"
                    HIGHLIGHTED CELL COLUMN: "{selected_column}"
                    HIGHLIGHTED CELL ROW: "{selected_row}"

                    Tagname:""")
            elif context_type.lower() == "list" and context:
                user_prompt = text_indent_remove(f"""\
                    Extract the tagname from this list item:

                    LIST HEADING: {context.get('list_heading', '')}
                    HIGHLIGHTED ITEM: "{highlighted_text}"

                    Tagname:""")
            else:
                context_text = context.get('full_sentence', '') if context else ''
                user_prompt = text_indent_remove(f"""\
                    Extract the tagname from this text:

                    HIGHLIGHTED TEXT: "{highlighted_text}"
                    CONTEXT: "{context_text}"

                    Tagname:""")

            messages = [
                {"role": "system", "content": extraction_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            response = self.llm.chat(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            # Parse response
            tagname = response.strip()
            objects_dict = {}
            if tagname.upper() == "NONE" or not tagname:
                tagname = None
                confidence = 0.0
            else:
                acm_object_df = self.check_acm_for_tagname(tagname, context_source_text(highlighted_text, context))
                for object_id, row in acm_object_df.iterrows():
                    objects_dict[object_id] = {}
                    objects_dict[object_id]['name'] = row['Name']
                    objects_dict[object_id]['library_id'] = row['LibraryID']
                    objects_dict[object_id]['parameters'] = self.get_most_likely_parameter(highlighted_text, row['LibraryID'], context, context_type)

                # Calculate confidence based on tagname pattern matching
                confidence = self._calculate_tagname_confidence(tagname)
            
            return {
                "objects": objects_dict if tagname else None,
                "confidence": confidence,
                "raw_tagname": response.strip(),
                "highlighted_text": highlighted_text,
                "context": context,
                "context_type": context_type
            }
        except requests.exceptions.ConnectionError as e:
            raise
        except Exception as e:
            return {
                "objects": None,
                "confidence": 0.0,
                "error": str(e),
                "highlighted_text": highlighted_text,
                "context": context,
                "context_type": context_type
            }
        

    def get_most_likely_parameter(self, highlighted_text, library_id, context=None, context_type="general", temperature=0.1, max_tokens=1000):
        """
        Get the most likely parameter from highlighted text by generating possible parameter names and data types,
        then checking against the ACM library for matches.
        
        :param highlighted_text: The highlighted text to extract parameter from
        :type highlighted_text: str
        :param library_id: The library ID to check against
        :type library_id: str
        :param context: Context dictionary with appropriate keys for context type
        :type context: dict
        :param context_type: Type of context ("table", "list", or "general")
        :type context_type: str
        :param temperature: LLM temperature for extraction consistency
        :type temperature: float
        :param max_tokens: Maximum tokens for response
        :type max_tokens: int
        :return: Extraction result with parameter and confidence
        :rtype: dict
        """
        try:
            parameter_prompt = text_indent_remove(f"""\
                You are an expert in industrial automation control systems and parameter naming conventions.
                Analyze the highlighted text and generate possible parameter names and data types that could match.
                The parameter names should not include the tagname itself.

                Common Parameter Patterns in Industrial Automation:
                
                Configuration Parameters:
                - General config: Cfg_[Feature], Cfg_[Option] (Bool, String, Int, Real)
                - Device types: ACM_Type, ACM_UsedIn (String)
                - Capabilities: Cfg_Has[Feature] (Bool)
                - Requirements: Cfg_[Action]Reqd, Cfg_[Action]Required (Bool)
                
                Input/Output Parameters:
                - Process inputs: Inp_PV, Inp_PVA, Inp_PVB (String references)
                - Input aliases: Inp_[Signal]_Alias (String)
                - Input connections: Inp_[Signal]_Connection (String) 
                - Input addresses: Inp_[Signal]_Address (String)
                - IO status: Inp_[Signal]_ModuleOk, Inp_[Signal]_ChannelFault (String)
                
                Alarm Parameters:
                - Alarm limits: Cfg_[Level]Lim (Real) - HiHi, Hi, Lo, LoLo
                - Alarm config: Cfg_[Level]AckReqd, Cfg_[Level]ResetReqd (Bool)
                - Alarm severity: Cfg_[Level]Severity (Int)
                - Alarm enable: Cfg_Has[Level]Alm (Bool)
                
                Control Parameters:
                - Setpoints: [Type]Setpoint, Cfg_[Type]SP (Real)
                - Limits: Cfg_Min[Property], Cfg_Max[Property] (Real, Int)
                - Scaling: Cfg_[Signal][RawEU][MinMax] (Real)
                - Display: Cfg_[Property]DecPlcs (Int)
                
                Reference Parameters:
                - Object references: [Type]_RefTag (String)
                - Library references: Filter="Library..." parameters
                
                Example Mappings:
                - "Process Variable" → ["Inp_PV", "PV", "Cfg_PV"] (String)
                - "High-High Alarm" → ["Cfg_HiHiLim", "Cfg_HasHiHiAlm", "Cfg_HiHiAckReqd"] (Real, Bool, Bool)
                - "PV input" → ["Inp_PV", "Inp_PVA", "Inp_PVB"] (String)
                - "Alarm acknowledge" → ["Cfg_HiHiAckReqd", "Cfg_HiAckReqd", "Cfg_LoAckReqd"] (Bool)
                - "Module fault" → ["Inp_PV_ModuleOk", "Inp_[Signal]_ModuleOk"] (String)
                - "Channel A" → ["Inp_PVA", "PAIA_RefTag", "Inp_PVA_Alias"] (String)
                - "Severity level" → ["Cfg_HiHiSeverity", "Cfg_HiSeverity", "Cfg_LoSeverity"] (Int)
                - "Reset required" → ["Cfg_HiHiResetReqd", "Cfg_HiResetReqd"] (Bool)
                - "Uncertain status" → ["Inp_PV_Uncertain", "Inp_[Signal]_Uncertain"] (String)
                - "Dual channel" → ["ACM_Type", "Cfg_HasPVA", "Cfg_HasPVB"] (String, Bool, Bool)

                Data Type Guidelines:
                - Bool: Enable/disable, has/allow, required/not required, true/false options
                - String: References, addresses, connections, text values, object names
                - Real: Setpoints, limits, scaling values, measurements, alarm thresholds
                - Int: Counts, decimal places, enumeration values, severity levels

                Generate 3-7 most likely parameter name variations and their probable data types.
                Consider context clues like alarm levels, input types, configuration options.
                
                Respond in JSON format:
                {{
                    "possible_parameters": [
                        {{"name": "parameter_name", "data_type": "Bool|String|Real|Int"}},
                        ...
                    ]
                }}""")

            # Prepare context-specific prompt
            if context_type.lower() == "table" and context:
                selected_row, selected_column = context['row_and_column']
                user_prompt = text_indent_remove(f"""\
                    Extract possible parameter names from this table context:

                    TABLE CONTEXT: 
                    {context['full_table']}

                    HIGHLIGHTED CELL CONTENT: "{highlighted_text}"
                    HIGHLIGHTED CELL COLUMN: "{selected_column}"
                    HIGHLIGHTED CELL ROW: "{selected_row}"

                    Consider the column header and row context when determining parameter names.
                    Do not create parameter names that seem to be somewhere else in the table.
                    
                    Parameter Analysis:""")
            elif context_type.lower() == "list" and context:
                user_prompt = text_indent_remove(f"""\
                    Extract possible parameter names from this list item:

                    LIST HEADING: {context.get('list_heading', '')}
                    HIGHLIGHTED ITEM: "{highlighted_text}"

                    Consider the list heading context when determining parameter names.
                    
                    Parameter Analysis:""")
            else:
                context_text = context.get('full_sentence', '') if context else ''
                user_prompt = text_indent_remove(f"""\
                    Extract possible parameter names from this text:

                    HIGHLIGHTED TEXT: "{highlighted_text}"
                    CONTEXT: "{context_text}"

                    Parameter Analysis:""")

            messages = [
                {"role": "system", "content": parameter_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            response = self.llm.chat(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            # Parse JSON response
            if response.startswith('{'):
                data = json.loads(response)
            else:
                # Try to extract JSON from response
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())
                else:
                    raise ValueError("No valid JSON found")
            
            possible_parameters = data.get('possible_parameters', [])
            
            # Get library parser to check against actual parameters
            library_parser = self.__parse_library_file(library_id)
            library_parameters = library_parser.get_parameters()
            
            # Match possible parameters against library parameters
            matched_parameters = []
            for param_suggestion in possible_parameters:
                param_name = param_suggestion.get('name', '')
                suggested_type = param_suggestion.get('data_type', '')
                
                # Check for exact match
                if param_name in library_parameters:
                    actual_param = library_parameters[param_name]
                    type_match = actual_param.get('DType', '').lower() == suggested_type.lower()
                    
                    matched_parameters.append({
                        'parameter_name': param_name,
                        'parameter_details': actual_param,
                        'match_type': 'exact',
                        'suggested_type': suggested_type,
                        'actual_type': actual_param.get('DType', '')
                    })
                else:
                    # Check for partial matches
                    partial_matches = [p for p in library_parameters.keys() 
                                    if param_name.lower() in p.lower() or p.lower() in param_name.lower()]
                    
                    for partial_match in partial_matches[:3]:  # Limit to top 3 partial matches
                        actual_param = library_parameters[partial_match]
                        type_match = actual_param.get('DType', '').lower() == suggested_type.lower()
                        
                        matched_parameters.append({
                            'parameter_name': partial_match,
                            'parameter_details': actual_param,
                            'match_type': 'partial',
                            'suggested_name': param_name,
                            'suggested_type': suggested_type,
                            'actual_type': actual_param.get('DType', '')
                        })
            
            
            return {
                "matched_parameters": matched_parameters[:1],  # Top 1 match
                "total_suggestions": len(possible_parameters),
                "total_matches": len(matched_parameters),
                "highlighted_text": highlighted_text,
                "context": context,
                "context_type": context_type,
                "raw_response": response.strip()
            }
        
        except requests.exceptions.ConnectionError as e:
            raise
        except Exception as e:
            return {
                "matched_parameters": [],
                "total_suggestions": 0,
                "total_matches": 0,
                "error": str(e),
                "highlighted_text": highlighted_text,
                "context": context,
                "context_type": context_type
            }
        
    
    def extract_interlock_objects(self, highlighted_text, context=None, context_type="general", temperature=0.1, max_tokens=10000):
        """
        Extract objects being interlocked from interlock condition text
        
        :param highlighted_text: The highlighted interlock text
        :type highlighted_text: str
        :param context: Context dictionary with appropriate keys for context type
        :type context: dict
        :param context_type: Type of context ("table", "list", or "general")
        :type context_type: str
        :param temperature: LLM temperature for extraction consistency
        :type temperature: float
        :param max_tokens: Maximum tokens for response
        :type max_tokens: int
        :return: Extraction result with interlock objects and confidence
        :rtype: dict
        """
        try:
            interlock_prompt = text_indent_remove(f"""\
                You are an expert in industrial automation interlock systems. Extract the objects/equipment being interlocked from the text.

                Interlocked objects are typically:
                - Equipment that is being controlled/protected (pumps, valves, motors, reactors, etc.)
                - The equipment whose operation depends on the interlock condition
                - Equipment that will be started, stopped, opened, closed, or otherwise controlled

                Examples:
                - "Pump P-101 running and valve V-205 open" → Object being interlocked: (not specified, this is the condition)
                - "Start pump P-101 when tank level > 50%" → P-101
                - "Close valve XV-205 if pressure > 100 PSI" → XV-205  
                - "Stop all motors when emergency stop activated" → all motors
                - "Reactor R-101 heating interlock: temperature < 200°C" → R-101

                Extract the main object/equipment being controlled by this interlock.
                If multiple objects, list them separated by commas.
                If no clear object being interlocked, respond with "NONE".
                Respond with only the object identifier(s) or "NONE".""")

            # Prepare context-specific prompt
            if context_type.lower() == "table" and context:


                selected_row, selected_column = context['row_and_column']

                user_prompt = text_indent_remove(f"""\
                    Extract the object being interlocked from this table context using the highlighted cell as reference on which row to focus on:

                    TABLE CONTEXT: 
                    {context['full_table']}

                    HIGHLIGHTED CELL CONTENT: "{highlighted_text}"
                    HIGHLIGHTED CELL COLUMN: "{selected_column}"
                    HIGHLIGHTED CELL ROW: "{selected_row}"

                    Interlocked Object:""")
            elif context_type.lower() == "list" and context:
                user_prompt = text_indent_remove(f"""\
                    Extract the object being interlocked from this text:

                    LIST HEADING: {context.get('list_heading', '')}
                    FULL LIST CONTEXT: {context.get('full_list', '')}

                    HIGHLIGHTED ITEM: "{highlighted_text}"

                    Interlocked Object:""")
            else:
                user_prompt = text_indent_remove(f"""\
                    Extract the object being interlocked from this text:
                                                 
                    CONTEXT: "{context.get('text_blocks_string', '')}"

                    HIGHLIGHTED TEXT: "{highlighted_text}"
                    
                    Interlocked Object:""")

            messages = [
                {"role": "system", "content": interlock_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            response = self.llm.chat(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            # Parse response
            objects = response.strip()
            object_dict = {}
            if objects.upper() == "NONE" or not objects:
                objects = None
                confidence = 0.0
            else:
                # Split multiple objects if comma-separated
                object_list = [obj.strip() for obj in objects.split(',')]
                source_text = context_source_text(highlighted_text, context)
                library_parsers = {}
                for obj in object_list:
                    # Check ACM data handler for details if available
                    acm_object_df = self.check_acm_for_tagname(obj, source_text)
                    for object_id, row in acm_object_df.iterrows():
                        object_dict[object_id] = {}
                        object_dict[object_id]['name'] = row['Name']
                        object_dict[object_id]['library_id'] = row['LibraryID']
                        library_id = row['LibraryID']

                        if library_id not in library_parsers:
                            library_parsers[library_id] = self.__parse_library_file(library_id)
                        library_parser = library_parsers[library_id]
                        subobjects = library_parser.get_all_subobjects()
                        if subobjects:
                            object_dict[object_id]['subobjects'] = list(subobjects.keys())

                confidence = self._calculate_interlock_confidence(objects)
            
            return {
                "interlock_objects": object_dict if objects else None,
                "interlock_objects_raw": objects,
                "confidence": confidence,
                "raw_response": response.strip(),
                "highlighted_text": highlighted_text,
                "context": context,
                "context_type": context_type
            }
            
        except requests.exceptions.ConnectionError as e:
            raise
        except Exception as e:
            return {
                "interlock_objects": None,
                "interlock_objects_raw": None,
                "confidence": 0.0,
                "error": str(e),
                "highlighted_text": highlighted_text,
                "context": context,
                "context_type": context_type
            }
        

    def __parse_library_file(self,library_id):
        library_file_path = get_library_file_path(library_id,self.project_name)
        if not library_file_path:
            projects_df = self.acm_data_handler.get_all_projects()
            acm_project_name = projects_df.loc[int(self.acm_data_handler.get_project_id())]['Name']
            acm_libraries_retrieval(self.project_name, acm_project_name,threaded=False)
            library_file_path = get_library_file_path(library_id,self.project_name)
            if not library_file_path:
                raise Exception(f"Unable to access parameters of {self.__name}.")
        return acm_library_parser(library_file_path)

    
    def classify_and_extract(self, highlighted_text, context=None, context_type="general", temperature=0.1):
        """
        Combined method that classifies text and extracts relevant information
        
        :param highlighted_text: The highlighted text to analyze
        :type highlighted_text: str
        :param context_text: Additional context around the highlighted text
        :type context_text: str
        :param context_type: Type of context ("table", "list", or "general")
        :type context_type: str
        :param temperature: LLM temperature for consistency
        :type temperature: float
        :return: Combined classification and extraction results
        :rtype: dict
        """
        # First classify the text
        classification_result = self.classify_text(highlighted_text, context, context_type, temperature)
        
        # Initialize extraction results
        tagname_result = None
        interlock_result = None
        
        
        # Extract interlock objects only for interlock category
        if classification_result.get("category") == self.INTERLOCK:
            interlock_result = self.extract_interlock_objects(highlighted_text, context, context_type, temperature)
            tagname_result = None
        else:
            tagname_result = self.extract_tagname(highlighted_text, context, context_type, temperature)
            interlock_result = None

        # The individual stages degrade gracefully by returning an ``error``
        # entry; for interactive use the caller needs to know the LLM failed.
        for stage_result in (classification_result, tagname_result, interlock_result):
            if stage_result and stage_result.get('error'):
                raise RuntimeError(stage_result['error'])

        # Combine results
        combined_result = {
            "classification": classification_result,
            "tagname_extraction": tagname_result,
            "interlock_extraction": interlock_result,
            "highlighted_text": highlighted_text
        }
        
        return combined_result
    
    def _calculate_tagname_confidence(self, tagname):
        """
        Calculate confidence score for extracted tagname based on pattern matching
        
        :param tagname: Extracted tagname
        :type tagname: str
        :return: Confidence score between 0.0 and 1.0
        :rtype: float
        """
        import re
        
        if not tagname or tagname.upper() == "NONE":
            return 0.0
        
        # Common industrial tagname patterns
        patterns = [
            r'^[A-Z]{2,3}-\d{3,4}$',      # TIC-101, FIT-205, etc.
            r'^[A-Z]{1,2}\d{3,4}$',       # P101, T205, etc.
            r'^[A-Z]+-\d{3,4}$',          # P-101, M-205, etc.
            r'^[A-Z]{2,4}-[A-Z]?\d{3,4}$', # More complex patterns
            r'^\d{3}-[A-Z]{2,4}-\d{4}$',  # 200-PP-0017, 300-TI-0025, etc.
            r'^\d{2,3}-[A-Z]{1,4}-\d{3,5}$' # Flexible area-type-number format
        ]
        
        for pattern in patterns:
            if re.match(pattern, tagname.upper()):
                return 0.90
        
        # Partial matches
        if re.search(r'[A-Z]{2,3}.*\d{2,4}', tagname.upper()):
            return 0.70
        
        return 0.50
    
    def _calculate_interlock_confidence(self, objects):
        """
        Calculate confidence score for extracted interlock objects
        
        :param objects: Extracted interlock objects string
        :type objects: str
        :return: Confidence score between 0.0 and 1.0
        :rtype: float
        """
        import re
        
        if not objects or objects.upper() == "NONE":
            return 0.0
        
        # Check for tagname patterns in the objects
        if re.search(r'[A-Z]{1,3}-?\d{2,4}', objects.upper()):
            return 0.85
        
        # Check for equipment keywords
        equipment_keywords = ['pump', 'valve', 'motor', 'fan', 'reactor', 'tank', 'heater']
        objects_lower = objects.lower()
        for keyword in equipment_keywords:
            if keyword in objects_lower:
                return 0.75
        
        return 0.60
    

    def check_acm_for_tagname(self, tagname, source_text=None):
        """
        Check ACM data handler for tagname details if available
        
        :param tagname: Tagname to look up
        :type tagname: str
        :param source_text: Document text the tagname was extracted from, used to resolve a
            bracketed ACM object reference when the tagname itself names no object
        :type source_text: str or None
        :return: ACM data details or empty DataFrame
        :rtype: DataFrame
        """
        return lookup_acm_object(self.acm_data_handler, tagname, source_text)


class TextDocumentLLMPostProcessor:
    def __init__(self, llm, project_name, acm_data_handler:ACM_Data_Handler=None, internal_db:Database=None, config:Config=None):
        """
        Post-process classification and extraction results to enhance accuracy
        :param llm: LLM inference instance
        :param project_name: Name of the project for context
        :param acm_data_handler: Optional ACM data handler for tagname lookups
        :type llm: UnifiedInference
        :type project_name: str
        :type acm_data_handler: ACM_Data_Handler or None
        """
        self.llm = llm
        self.project_name = project_name
        self.acm_data_handler = acm_data_handler
        self.internal_db = internal_db
        self.config = config
        self.__library_parsers = {} 

    def _collect_existing_annotation_keys(self, path, pno) -> set:
        """
        Build the set of ``annotation_dedupe_key`` tuples already persisted on
        the given ``(path, pno)`` — unioning approved, unapproved, and
        rejected text-link records — so we can skip re-emitting an annotation
        the user (or a previous LLM pass) has already seen.

        Returns an empty set on any error or when ``self.internal_db`` is
        unset. Missing/rejected accessors are tolerated so callers do not
        need to introspect DB capabilities.

        :param path: Document path.
        :type path: str
        :param pno: 0-based page number.
        :type pno: int
        :return: Set of ``(tagname, parameter_name, parameter_value)`` keys.
        :rtype: set[tuple[str, str, str]]
        """
        existing_keys = set()
        if not self.internal_db or path is None or pno is None:
            return existing_keys

        records = []
        for accessor in (
            'get_all_approved_text_links_by_page_no',
            'get_all_unapproved_text_links_by_page_no',
            'get_all_rejected_text_links_by_page_no',
        ):
            fn = getattr(self.internal_db, accessor, None)
            if fn is None:
                continue
            try:
                result = fn(path, pno)
            except Exception as exc:
                logging.debug(
                    "Skipping %s during annotation-dedupe lookup: %s",
                    accessor, exc,
                )
                continue
            if isinstance(result, dict):
                records.extend(result.values())
            elif isinstance(result, list):
                records.extend(result)

        for record in records:
            if not isinstance(record, dict):
                continue
            tagname_entry = record.get('tagname')
            tagname_text = (
                tagname_entry.get('text') if isinstance(tagname_entry, dict) else None
            )
            parameters = record.get('parameters') or {}
            if not isinstance(parameters, dict) or not parameters:
                continue
            for parameter_name, parameter_entry in parameters.items():
                parameter_value = (
                    parameter_entry.get('text')
                    if isinstance(parameter_entry, dict)
                    else None
                )
                existing_keys.add(
                    annotation_dedupe_key(tagname_text, parameter_name, parameter_value)
                )

        return existing_keys

    def post_process_dependency_extraction(self,subobject, results, context, highlighted_text, selected_table, page, text_on_page, callback):
        """
        Post-process the results from the LLM to enhance accuracy and context
        :param results: Raw results from the LLM
        :type results: dict
        :return: Processed results
        :rtype: dict
        """
        dependent_text_bboxes = []
        raw_dependent = results['interlock_extraction']['interlock_objects_raw']
        raw_dependent = raw_dependent.strip()
        dependent_text_rects = page.search_for(raw_dependent)


        for rect in dependent_text_rects:
            text_bbox = [rect.x0, rect.y0, rect.x1, rect.y1]

            if context['type'] == 'table' and self.__is_within_bbox(text_bbox, selected_table.bbox):
                row, column = which_cell_contains_text(selected_table, text_bbox)
                full_text = get_text_in_bbox(selected_table, row, column, text_on_page)
                dependent_text_bboxes.append((row, column,text_bbox, full_text, raw_dependent))
                break

            elif (context['type'] == 'list' and 
                ((context['header_bbox'] and self.__is_within_bbox(text_bbox, context['header_bbox']) or 
                  (context['list_bbox'] and self.__is_within_bbox(text_bbox, context['list_bbox']))))):
                full_text = get_text_in_bbox(None, None, None, text_on_page, text_bbox)
                dependent_text_bboxes.append((None, None,text_bbox, full_text, raw_dependent))
                break


            elif context['type'] == 'text' and self.__is_within_bbox(text_bbox, context['text_blocks_bbox']):
                full_text = get_text_in_bbox(None, None, None, text_on_page, text_bbox)
                dependent_text_bboxes.append((None, None,text_bbox, full_text, raw_dependent))
                break
        

        
        dependencies_result = self.__extract_dependencies(results, context, highlighted_text, page, text_on_page, selected_table, raw_dependent)
        callback(dependencies_result, 'Extracting dependencies from text...')
        dependencies_result = self.__associate_dependents_to_dependencies(context, dependencies_result, dependent_text_bboxes, dependent_text_rects)
        callback(dependencies_result, 'Associating dependents to dependencies...')
        dependencies_result = self.__extract_dependency_groups(dependencies_result)
        callback(dependencies_result, 'Extracting dependency groups...')
        dependencies_result = self.__map_dependencies_to_object_status(dependencies_result)
        callback(dependencies_result, 'Mapping dependencies to object status...')
        dependencies_result = self.__identify_text_to_ignore(dependencies_result)
        callback(dependencies_result, 'Identifying text to ignore...')
        results['dependencies_extraction'] = dependencies_result

        results = self.process_dependency_extraction(results, context, page)

        callback(results, '')
        

    def process_dependency_extraction(self, results, context, page):
        """
        Process the dependency extraction results
        :param dependencies_result: Raw dependency extraction results
        :type dependencies_result: dict
        :return: Processed dependency extraction results
        :rtype: dict
        """

        processed_results = []

        # Track annotations already emitted in this call so two dependency
        # groups that resolve to the same source location + Rockwell
        # ``subparameter_text`` do not both produce an annotation. Key layout:
        # ``(path, pno, given_start_idx, given_end_idx, subparameter_text_norm)``.
        seen_annotation_keys = set()

        
        dependencies_result = results.get('dependencies_extraction', {})
        acm_tagname_dependent = list(results['interlock_extraction']['interlock_objects'].values())[0].get('name', '')
        given_text_dependent = results['interlock_extraction']['interlock_objects_raw']
        associated_dependents = {}
    
        
        for group_info in dependencies_result.get('dependency_groups', {}):
            processed_result = {}
            tagnames = group_info.get('tagnames', [])

            if len(tagnames) == 1:
                reference_type = 'object'
            elif len(tagnames) > 1:
                reference_type = 'string'
            else:
                continue

            processed_result['reference_type'] = reference_type

            tagname_linked_text_data = []

            acm_tagnames = {}
            acm_nibs = {}
            given_linked_text = None
            subparameter_text = ''
            text_to_ignore = []
            for tagname in tagnames:

                dependency_info = dependencies_result['dependencies'].get(tagname, {})
                if not dependency_info:
                    continue

                if not dependency_info['acm_objects'].values():
                    continue

                
                acm_tagname = list(dependency_info['acm_objects'].values())[0].get('name', tagname)
                acm_tagnames[tagname] = {'acm_tagname': acm_tagname}
                acm_nibs[tagname] = {
                                        'nib_name':dependency_info.get('nib_name', ''),
                                        'nib_data_type':dependency_info.get('nib_data_type', '')
                                    }
                text_to_ignore = text_to_ignore + dependency_info.get('text_to_ignore', [])

                if not given_linked_text:
                    if context['type'] == 'table':
                        row = dependency_info.get('row', None)
                        column = dependency_info.get('column', None)
                        given_linked_text = self.table_given_linked_text(context, cell_row=row, cell_column=column )
                    elif context['type'] == 'list':
                        text = dependency_info.get('full_text', None)
                        given_linked_text = self.list_given_linked_text(context, text, page)
                    else:
                        text = dependency_info.get('full_text_alternative',dependency_info.get('full_text', None))
                        given_linked_text = self.text_given_linked_text(context, text, page)
                cell_text = given_linked_text[0][1]

                acm_tagnames[tagname]['acm_to_given'] = match_all_substrings(acm_tagname, tagname)
                
                associated_dependent = dependency_info.get('associated_dependents', [])

                if associated_dependents:
                    first_associated_dependent = list(associated_dependents.values())[0]
                    if (first_associated_dependent['row'] == associated_dependent[0]['row']
                            and first_associated_dependent['column'] == associated_dependent[0]['column']):
                        continue

                if associated_dependent:
                    associated_dependents[tagname] = associated_dependent[0]
            
            
            # Every tagname in the group can be skipped above (missing dependency
            # info, no ACM object, or duplicate dependent cell), leaving nothing to
            # build an annotation from.
            if not acm_tagnames or not acm_nibs or not given_linked_text:
                continue

            if reference_type == 'object':
                first_tagname = next(iter(acm_tagnames))
                subparameter_text = acm_tagnames[first_tagname]['acm_tagname'] + '.' + acm_nibs[first_tagname]['nib_name']
            elif reference_type == 'string':

                logic_expression = dependencies_result.get('logic_expression', '')
                subparameter_text = LogicToRockwellConverter().convert_logic_expression_to_rockwell_code(logic_expression, acm_nibs)

                for given_tagname, acm_tagname in acm_tagnames.items():
                    subparameter_text = subparameter_text.replace(given_tagname, acm_tagname['acm_tagname'])


            if not subparameter_text:
                continue

            # Duplicate-annotation guard: skip if a previous group in this call
            # already emitted an annotation for the same source location with
            # the same resolved ``subparameter_text``.
            annotation_key = (
                given_linked_text[5] if given_linked_text and len(given_linked_text) > 5 else None,
                given_linked_text[4] if given_linked_text and len(given_linked_text) > 4 else None,
                given_linked_text[1] if given_linked_text and len(given_linked_text) > 1 else None,
                given_linked_text[2] if given_linked_text and len(given_linked_text) > 2 else None,
                _normalize_annotation_field(subparameter_text),
            )
            if annotation_key in seen_annotation_keys:
                logging.debug(
                    "Skipping duplicate dependency-extraction annotation: %s",
                    annotation_key,
                )
                continue
            seen_annotation_keys.add(annotation_key)

            key_linked_texts = []


            cell_text = given_linked_text[0][1]
            
            ignore_linked_texts = []

            
            for tagname, data in acm_tagnames.items():
                given_text_positions = [i for i in range(len(cell_text)) if cell_text.startswith(tagname, i)]
                target_text_positions = [i for i in range(len(subparameter_text)) if subparameter_text.startswith(data['acm_tagname'], i)]
                print(cell_text,subparameter_text)
                for key_text, target_indexes, given_indexes in acm_tagnames[tagname]['acm_to_given']:
                    try:
                        print(key_text, target_indexes, given_indexes)
                        print(given_text_positions, target_text_positions)
                        given_indexes = [given_text_positions[0] + idx for idx in given_indexes]
                        given_indexes[1] = given_indexes[1] + 1
                        target_indexes = [target_text_positions[0] + idx for idx in target_indexes]
                        key_linked_text = [[key_text, cell_text, given_indexes], target_indexes]
                        key_linked_texts.append(key_linked_text)
                    except Exception as e:
                        logging.error(f"Error processing linked texts: {e}")


                

            # Process text_to_ignore to find consecutive words and merge them
            ignore_linked_texts = self.merge_consecutive_ignore_texts(text_to_ignore, cell_text)

            # Mark tagnames not part of the key text as ignore texts
            ignore_linked_texts = self.mark_non_key_tagnames_as_ignore_texts(ignore_linked_texts, key_linked_texts, cell_text)
        
        
            
            parameter_result = {
                'reference_type': reference_type,
                'subparameter_text': subparameter_text,
                'given_text': given_linked_text,
                'key_texts': key_linked_texts,
                'ignore_texts': ignore_linked_texts,
            }

                
            key_linked_texts = []

            if tagname_linked_text_data:
                continue
            
            associated_dependent = dependency_info.get('associated_dependents', [])

            if not associated_dependent:
                continue

            if context['type'] == 'table':
                given_linked_text = self.table_given_linked_text(context, associated_dependent[0]['bbox'])
            elif context['type'] == 'list':
                given_linked_text = self.list_given_linked_text(context, text_item_bbox=associated_dependent[0]['bbox'])
            else:
                given_linked_text = self.text_given_linked_text(context, text_item_bbox=associated_dependent[0]['bbox'])

            acm_to_given = match_all_substrings(acm_tagname_dependent, given_text_dependent)

            cell_text = given_linked_text[0][1]

            given_text_positions = [i for i in range(len(cell_text)) if cell_text.startswith(given_text_dependent, i)]
            target_text_positions = [0]

            
            print(cell_text)
            for key_text, target_indexes, given_indexes in acm_to_given:
                print(key_text, target_indexes, given_indexes)
                print(given_text_positions, target_text_positions)
                given_indexes = [given_text_positions[0] + idx for idx in given_indexes]
                given_indexes[1] = given_indexes[1] + 1
                target_indexes = [target_text_positions[0] + idx for idx in target_indexes]
                key_linked_text = [[key_text, cell_text, given_indexes], target_indexes]
                key_linked_texts.append(key_linked_text)

         
            # Process text_to_ignore to find consecutive words and merge them
            ignore_linked_texts = self.merge_consecutive_ignore_texts(text_to_ignore, cell_text)

            # Mark tagnames not part of the key text as ignore texts
            ignore_linked_texts = self.mark_non_key_tagnames_as_ignore_texts(ignore_linked_texts, key_linked_texts, cell_text)
            

            dependent_result = {
                'given_text': given_linked_text,
                'key_texts': key_linked_texts,
                'ignore_texts': ignore_linked_texts,
            }

            processed_results.append({
                'parameter_reference': parameter_result,
                'dependent_reference': dependent_result
            })

        results['processed_dependencies'] = processed_results
        # For debugging save time and results to file (append to existing)
        #with open("debug_results.json", "a", encoding="utf-8") as f:
        #    json.dump(results, f, indent=4)
        return results

    def merge_consecutive_ignore_texts(self, text_to_ignore, cell_text):
        if not text_to_ignore or not cell_text:
            return []
            
        # Sort text_to_ignore by their position in cell_text
        texts_with_positions = []
        for item in text_to_ignore:
            text = item.get('text', '')
            reason = item.get('reason', '')
            if text:
                # Find the position of this text in cell_text
                pos = cell_text.find(text)
                if pos != -1:
                    texts_with_positions.append({
                            'text': text,
                            'reason': reason,
                            'start_pos': pos,
                            'end_pos': pos + len(text)
                        })
            
        # Sort by start position
        texts_with_positions.sort(key=lambda x: x['start_pos'])
            
        # Merge consecutive or adjacent texts
        merged_texts = []
        i = 0
        while i < len(texts_with_positions):
            current = texts_with_positions[i]
            start_pos = current['start_pos']
            end_pos = current['end_pos']
            reason = current['reason']
                
            # Check if next items are consecutive (with only whitespace between)
            j = i + 1
            while j < len(texts_with_positions):
                next_item = texts_with_positions[j]
                # Check if there's only whitespace between current end and next start
                between_text = cell_text[end_pos:next_item['start_pos']]
                if between_text.strip() == '':  # Only whitespace between
                    end_pos = next_item['end_pos']
                    j += 1
                else:
                    break
                
            # Extract the merged text including any whitespace
            merged_text = cell_text[start_pos:end_pos]
            merged_texts.append({
                    'text': merged_text,
                    'reason': reason,
                    'indexes': (start_pos, end_pos)
                })
                
            i = j
            
        ignore_linked_texts = merged_texts
        return ignore_linked_texts
    
    def mark_non_key_tagnames_as_ignore_texts(self, ignore_linked_texts, key_linked_texts, cell_text):
        """
        Mark tagnames that are not part of the key text as ignore texts.
        Uses TAGNAME_REGEX to identify tagnames in the cell text.
        Excludes hyphens and underscores from the ignore ranges.
        """
        if not cell_text:
            return ignore_linked_texts
        
        # Extract the key text indexes from key_linked_texts
        # key_linked_texts format: [[key_text, cell_text, given_indexes], target_indexes]
        key_text_ranges = []
        for key_linked_text in key_linked_texts:
            if key_linked_text and len(key_linked_text) > 0:
                given_indexes = key_linked_text[0][2]  # [start, end]
                key_text_ranges.append((given_indexes[0], given_indexes[1]))
        
        # Find all tagnames in cell_text using TAGNAME_REGEX
        tagname_matches = re.finditer(TAGNAME_REGEX, cell_text)
        
        for match in tagname_matches:
            tagname = match.group(0)
            start_pos = match.start()
            
            # Split the tagname by hyphens and underscores to get alphanumeric segments
            current_pos = start_pos
            for char in tagname:
                if char in ['-', '_']:
                    # Skip hyphens and underscores
                    current_pos += 1
                else:
                    # Find the end of this alphanumeric segment
                    segment_start = current_pos
                    segment_end = segment_start
                    
                    # Continue until we hit a hyphen, underscore, or end of tagname
                    while segment_end < start_pos + len(tagname):
                        idx = segment_end - start_pos
                        if idx >= len(tagname) or tagname[idx] in ['-', '_']:
                            break
                        segment_end += 1
                    
                    if segment_end > segment_start:
                        segment_text = cell_text[segment_start:segment_end]
                        
                        # Check if this segment is already in ignore_linked_texts
                        already_ignored = False
                        for ignore_item in ignore_linked_texts:
                            ignore_start, ignore_end = ignore_item['indexes']
                            if segment_start >= ignore_start and segment_end <= ignore_end:
                                already_ignored = True
                                break
                            
                        # Check if this tagname overlaps with any key text range
                        is_key_text = False
                        for key_start, key_end in key_text_ranges:
                            # Check for overlap
                            if segment_start >= key_start and segment_end <= key_end:
                                is_key_text = True
                                break
                        
                        if not already_ignored and not is_key_text:
                            ignore_linked_texts.append({
                                'text': segment_text,
                                'reason': 'Non-key tagname segment',
                                'indexes': (segment_start, segment_end)
                            })
                    
                    current_pos = segment_end
        
        # Sort by start position to maintain order
        ignore_linked_texts.sort(key=lambda x: x['indexes'][0])
        
        return ignore_linked_texts
    
    def list_given_linked_text(self, context, item_text=None, page=None, text_item_bbox=None):

        text_on_page = context['text_on_page']
        pno = context['pno']
        path = context['path']

        if text_item_bbox is None:
            text_block_bbox = context['list_bbox'] if context.get('list_bbox') else context.get('text_blocks_bbox')
            
            list_item_rects = page.search_for(item_text)
            if not list_item_rects:
                return
            
            text_item_bbox = []
            for list_item_rect in list_item_rects:
                bbox = [list_item_rect.x0, list_item_rect.y0, list_item_rect.x1, list_item_rect.y1]
                if self.__is_within_bbox(bbox, text_block_bbox):
                    text_item_bbox.append(bbox)
                    

        if not text_item_bbox:
            return

        list_item = None
        if isinstance(text_item_bbox[0], list):
            for item in text_item_bbox:
                item = get_text_within_bbox(item,text_on_page,True)
                if not item:
                    continue
                if not list_item:
                    list_item = item
                else:
                    list_item = [list_item[0] + item[0],
                                 (min(list_item[1][0], item[1][0]), max(list_item[1][1], item[1][1])),
                                 list_item[2]]
        else:
            list_item = get_text_within_bbox(text_item_bbox,text_on_page,True)
        if not list_item:
            return
        item_full_text = list_item[0]
        item_full_indexes = list_item[1]
        font = list_item[2]
        given_linked_text = [[None, item_full_text]
                            ,item_full_indexes[0]
                            ,item_full_indexes[1]
                            ,(None, None, True, font, None, None)
                            ,pno
                            ,path
                            ,Database.TEXT]
        
        return given_linked_text
    

    def text_given_linked_text(self, context, item_text=None, page=None, text_item_bbox=None):

        text_on_page = context['text_on_page']
        pno = context['pno']
        path = context['path']

        if text_item_bbox is None:
            text_block_bbox = context['list_bbox'] if context.get('list_bbox') else context.get('text_blocks_bbox')
            
            unhyphened_linebreaks_text = self.__remove_hyphened_linebreaks(item_text, context['text_blocks_string'])
            list_item_rects = page.search_for(unhyphened_linebreaks_text)
            if not list_item_rects:
                return
            
            text_item_bbox = []
            for list_item_rect in list_item_rects:
                bbox = [list_item_rect.x0, list_item_rect.y0, list_item_rect.x1, list_item_rect.y1]
                if self.__is_within_bbox(bbox, text_block_bbox):
                    text_item_bbox.append(bbox)
                    

        if not text_item_bbox:
            return

        list_item = None
        if isinstance(text_item_bbox[0], list):
            for item in text_item_bbox:
                item = get_text_within_bbox(item,text_on_page,True)
                if not item:
                    continue
                if not list_item:
                    list_item = item
                else:
                    list_item = [list_item[0] + item[0],
                                 (min(list_item[1][0], item[1][0]), max(list_item[1][1], item[1][1])),
                                 list_item[2]]
            list_item[0] = item_text
        else:
            list_item = get_text_within_bbox(text_item_bbox,text_on_page,True)
        if not list_item:
            return
        item_full_text = list_item[0]
        item_full_indexes = list_item[1]
        font = list_item[2]
        given_linked_text = [[None, item_full_text]
                            ,item_full_indexes[0]
                            ,item_full_indexes[1]
                            ,(None, None, True, font, None, None)
                            ,pno
                            ,path
                            ,Database.TEXT]
        
        return given_linked_text


    def __remove_hyphened_linebreaks(self, text, original_text):
        '''Search for text in the orginal text and if found with hyphened linebreaks'''
        list_of_indexes_of_new_lines = []
        for match in re.finditer(r'\n', original_text):
            list_of_indexes_of_new_lines.append(match.start())

        _original_text = original_text.replace('\n', '')
        if text in _original_text:
            _text = copy.deepcopy(text)
            index = _original_text.index(text)
            for i, new_line_index in enumerate(list_of_indexes_of_new_lines):
                idx = new_line_index - index
                if idx > 0 and idx < len(_text):
                    _text = _text[:idx-i] + '\n' + _text[idx-i:]

        return _text.replace('-\n', '').replace('\n', '')


    def table_given_linked_text(self, context, cell_bbox=None, cell_row=None, cell_column=None): 
        pno = context['pno']
        path = context['path']
        table = context['table_object']
        text_on_page = context['text_on_page']
        if cell_row and cell_column:
            cell_bbox = table.rows[cell_row].cells[cell_column]
        table_cell = get_table_cell_overlapping_bbox(table,cell_bbox,text_on_page)
        if not table_cell:
            return
        cell = table_cell[0]
        cell_full_text = table_cell[1]
        cell_full_indexes = table_cell[2]
        table_shape = table_cell[3]
        table_bbox = table_cell[4]
        text_data = get_text_within_bbox(cell_bbox,text_on_page,True)
        if not text_data: 
            return 
        indexes = text_data[1]
        font = text_data[2]
        given_linked_text = [[cell_full_text, text_data[0]]
                            ,indexes[0]
                            ,indexes[1]
                            ,(cell, table_shape, False, font, table_bbox, cell_full_indexes)
                            ,pno
                            ,path
                            ,Database.TEXT]
        
        return given_linked_text



    def __associate_dependents_to_dependencies(self, context, dependencies_result, dependent_text_bboxes, dependent_text_rects):
        
        if context['type'] == 'table':
            if len(dependent_text_rects) == 1 and dependent_text_bboxes[0][4] == dependent_text_bboxes[0][3]['text'].strip():
                # Single occurrence, no further disambiguation needed
                for _, dependency_info in dependencies_result.get('dependencies', {}).items():
                    dependency_info['associated_dependents'] = [{
                        'row': dependent_text_bboxes[0][0],
                        'column': dependent_text_bboxes[0][1],
                        'bbox': dependent_text_bboxes[0][2],
                        'full_text': dependent_text_bboxes[0][3]
                    }]
                
            else:
                # Multiple occurrences, attempt to associate based on row matching
                for _, dependency_info in dependencies_result.get('dependencies', {}).items():
                    dependency_info['associated_dependents'] = []
                    for row, column, bbox, full_text, raw_dependent in dependent_text_bboxes:
                        # If the dependent is on the same row as the dependency and there is only one dependent, associate it
                        if row == dependency_info.get('row'):
                            dependency_info['associated_dependents'].append({
                                'row': row,
                                'column': column,
                                'bbox': bbox,
                                'full_text': full_text
                            })
        
        else:
            if len(dependent_text_rects) == 1 and dependent_text_bboxes[0][4] == dependent_text_bboxes[0][3]['text'].strip():
                # Single occurrence, no further disambiguation needed
                for _, dependency_info in dependencies_result.get('dependencies', {}).items():
                    dependency_info['associated_dependents'] = [{
                        'row': dependent_text_bboxes[0][0],
                        'column': dependent_text_bboxes[0][1],
                        'bbox': dependent_text_bboxes[0][2],
                        'full_text': dependent_text_bboxes[0][3]
                    }]
            
            else:
                # Multiple occurrences, associate all dependents
                for _, dependency_info in dependencies_result.get('dependencies', {}).items():
                    dependency_info['associated_dependents'] = []
                    for row, column, bbox, full_text, raw_dependent in dependent_text_bboxes:
                        dependency_info['associated_dependents'].append({
                            'row': row,
                            'column': column,
                            'bbox': bbox,
                            'full_text': full_text
                        })

        return dependencies_result
                    

        


    
    def __extract_dependency_groups(self, dependencies_result):
        if not dependencies_result.get('success'):
            return dependencies_result
        
        logic_expression = dependencies_result.get('logic_expression', '')
        dependencies = dependencies_result.get('dependencies', {})
        
        if not logic_expression:
            dependencies_result['dependency_groups'] = [{
                'group_id': 0,
                'tagnames': list(dependencies.keys()),
                'logic_operator': 'NONE'
            }]
            dependencies_result['total_groups'] = 1
            return dependencies_result
        
        groups = self._parse_logic_groups(logic_expression, dependencies)
        dependencies_result['dependency_groups'] = groups
        dependencies_result['total_groups'] = len(groups)
        
        return dependencies_result
    
    def _parse_logic_groups(self, logic_expression, dependencies):
        import re
        groups = []
        
        # Split by first-level AND operators
        and_segments = self._split_by_operator(logic_expression, 'AND')
        
        for group_id, segment in enumerate(and_segments):
            segment = segment.strip()
            
            # Remove outer parentheses from segment
            while segment.startswith('(') and segment.endswith(')'):
                # Check if these are matching outer parens
                depth = 0
                matching = True
                for i, char in enumerate(segment):
                    if char == '(':
                        depth += 1
                    elif char == ')':
                        depth -= 1
                    if depth == 0 and i < len(segment) - 1:
                        matching = False
                        break
                if matching:
                    segment = segment[1:-1].strip()
                else:
                    break
            
            # Check if this segment contains OR operators at the first level
            or_check = self._contains_first_level_operator(segment, 'OR')
            
            if or_check:
                # Split by OR to get individual conditions in this group
                or_conditions = self._split_by_operator(segment, 'OR')
                tagnames_in_group = []
                
                for condition in or_conditions:
                    condition = condition.strip()
                    # Remove outer parentheses from condition
                    while condition.startswith('(') and condition.endswith(')'):
                        depth = 0
                        matching = True
                        for i, char in enumerate(condition):
                            if char == '(':
                                depth += 1
                            elif char == ')':
                                depth -= 1
                            if depth == 0 and i < len(condition) - 1:
                                matching = False
                                break
                        if matching:
                            condition = condition[1:-1].strip()
                        else:
                            break
                    
                    tagname = self._extract_tagname_from_condition(condition, dependencies)
                    if tagname:
                        tagnames_in_group.append(tagname)
                
                groups.append({
                    'group_id': group_id,
                    'tagnames': tagnames_in_group,
                    'logic_operator': 'OR',
                    'expression': segment
                })
            else:
                # Single condition in this AND group
                tagname = self._extract_tagname_from_condition(segment, dependencies)
                if tagname:
                    groups.append({
                        'group_id': group_id,
                        'tagnames': [tagname],
                        'logic_operator': 'AND',
                        'expression': segment
                    })
        
        return groups
    
    def _contains_first_level_operator(self, expression, operator):
        """Check if expression contains operator at first level (not nested in parens)"""
        depth = 0
        i = 0
        while i < len(expression):
            if expression[i] == '(':
                depth += 1
            elif expression[i] == ')':
                depth -= 1
            elif depth == 0:
                # Check for operator at this position
                if expression[i:i+len(operator)] == operator:
                    # Verify it's a whole word (surrounded by spaces or parens)
                    before_ok = (i == 0 or expression[i-1] in ' (')
                    after_ok = (i+len(operator) >= len(expression) or 
                                expression[i+len(operator)] in ' )')
                    if before_ok and after_ok:
                        return True
            i += 1
        return False
    
    def _split_by_operator(self, expression, operator):
        """Split expression by operator while respecting parentheses."""
        segments = []
        current_segment = []
        depth = 0
        i = 0
        
        while i < len(expression):
            char = expression[i]
            
            if char == '(':
                depth += 1
                current_segment.append(char)
            elif char == ')':
                depth -= 1
                current_segment.append(char)
            elif depth == 0 and expression[i:i+len(operator)] == operator:
                # Check if it's a whole word
                before_ok = (i == 0 or expression[i-1] in ' (')
                after_ok = (i+len(operator) >= len(expression) or 
                            expression[i+len(operator)] in ' )')
                
                if before_ok and after_ok:
                    # Found operator at depth 0
                    if current_segment:
                        segments.append(''.join(current_segment).strip())
                        current_segment = []
                    i += len(operator)
                    continue
                else:
                    current_segment.append(char)
            else:
                current_segment.append(char)
            
            i += 1
        
        # Add final segment
        if current_segment:
            segments.append(''.join(current_segment).strip())
        
        return segments
    
    def _extract_tagname_from_condition(self, condition, dependencies):
        import re
        condition = condition.strip()
        
        # Check each known tagname
        for tagname in dependencies.keys():
            if tagname in condition:
                return tagname
        
        # Try to extract tagname pattern if not found
        # Look for common patterns like TAG.property or TAG[status]
        match = re.match(r'([A-Z0-9\-_]+)[\.\[]', condition)
        if match:
            return match.group(1)
        
        return None


    def __map_dependencies_to_object_status(self, dependencies):
        """
        Map extracted dependencies to their ACM object status if available
        
        :param dependencies: Dependencies extraction result
        :type dependencies: dict
        :return: Updated dependencies with ACM object status
        :rtype: dict
        """
        # Group dependencies by (library_id, core_type, catalog_number, condition) to avoid duplicate requests
        dependency_groups = {}
        
        for tagname, dep_info in dependencies.get('dependencies', {}).items():
            # Get the ACM library ID for this tagname
            acm_objects = dep_info['acm_objects'].values()
            if not acm_objects:
                continue
            acm_object = list(acm_objects)[0]
            
            if acm_object and 'library_id' in acm_object:
                library_id = acm_object['library_id']
                catalog_number = acm_object.get('catalog_number', '')
                core_type = acm_object.get('core_type', '')
                dependency_logic = dep_info.get('condition', '')
                
                # Create a unique key for this combination
                group_key = (library_id, core_type, catalog_number, dependency_logic)
                
                if group_key not in dependency_groups:
                    dependency_groups[group_key] = []
                dependency_groups[group_key].append((tagname, dep_info))
        
        # Process each unique group once
        for group_key, tagname_list in dependency_groups.items():
            library_id, core_type, catalog_number, dependency_logic = group_key
            
            # Use the first tagname in the group for the request
            first_tagname = tagname_list[0][0]
            
            # Try user prompts first
            nib_result = self.__get_most_likely_status_for_dependency_from_user_prompts(
                first_tagname, library_id, core_type, catalog_number, dependency_logic
            )

            # If user prompts didn't work, try NIB file
            if not nib_result:
                nib_result = self.__get_most_likely_status_for_dependency_from_nib_file(
                    first_tagname, library_id, dependency_logic, catalog_number
                )
            
            # Apply the result to all dependencies in this group
            if nib_result:
                for tagname, dep_info in tagname_list:
                    dep_info['nib_name'] = nib_result.get('nib_name')
                    dep_info['nib_description'] = nib_result.get('nib_description')
                    dep_info['nib_data_type'] = nib_result.get('nib_data_type')
                    dep_info['confidence'] = nib_result.get('confidence')
            
        return dependencies

    def __get_most_likely_status_for_dependency_from_user_prompts(self, tagname, library_id, core_type, catalog_number, dependency_logic, max_retries=3):
        """
        Use LLM to intelligently guess NIB status indicators for a dependency based on user library prompts.
        
        :param tagname: The tagname to find status for
        :type tagname: str
        :param library_id: The ACM library ID
        :type library_id: str
        :param core_type: The core type of the ACM object
        :type core_type: str
        :param catalog_number: The catalog number of the ACM object
        :type catalog_number: str
        :param dependency_logic: The logic describing the dependency condition
        :type dependency_logic: str
        :param max_retries: Maximum number of attempts (default: 3)
        :type max_retries: int
        :return: Dictionary with NIB information or None
        :rtype: dict or None
        """
        try:
            library_prompts = self.internal_db.get_llm_library_prompts(library_id, core_type, catalog_number)

            if not library_prompts or 'References' not in library_prompts:
                return None
            
            references = library_prompts['References']
            references = {name: references[name]
                          for name in allowed_status_references(catalog_number, references)}
            if not references:
                return None
            
            # Build list of available NIBs from references
            available_nibs = []
            for nib_name, nib_data in references.items():
                properties = nib_data.get('properties', {})
                value_description = nib_data.get('value', '')
                
                available_nibs.append({
                    'name': nib_name,
                    'description': properties.get('Description', ''),
                    'data_type': properties.get('DType', ''),
                    'usage': value_description
                })
            
            if not available_nibs:
                return None
            
            # A single allowed reference leaves the LLM no choice to make.
            if len(available_nibs) == 1:
                only_nib = available_nibs[0]
                return {
                    'nib_name': only_nib['name'],
                    'nib_description': only_nib['description'],
                    'nib_data_type': only_nib['data_type'],
                    'nib_usage': only_nib['usage'],
                    'confidence': 1.0,
                    'attempts': 0,
                    'source': 'user_prompts'
                }
            
            # System prompt for NIB selection using user-provided library information
            system_prompt = text_indent_remove("""\
                You are an expert in industrial automation and PlantPAx ACM libraries.
                Your task is to identify the most appropriate NIB (Named Interface Binding) status indicator
                for a dependency condition in interlock logic.
                
                NIBs are standardized status indicators that objects use to expose their state to other objects.
                You will be provided with:
                - The tagname of the object being monitored
                - The dependency logic/condition
                - Available NIBs with their descriptions and usage information
                
                The available NIBs differ per object type and may be deliberately restricted, so the provided
                list is the only source of valid answers. Never suggest a name that is absent from it, however
                common that name is in PlantPAx.
                
                Consider the dependency logic carefully to select the NIB that best represents the condition being monitored.
                
                If none of the available NIBs appropriately match the dependency logic, respond with "NONE".
                Otherwise, respond with ONLY a valid NIB name from the provided list.""")
            
            feedback = ""
            
            for attempt in range(max_retries):
                # Build the user prompt with NIB details
                nibs_list = []
                for nib in available_nibs:
                    nib_entry = f"- {nib['name']}: {nib['description']} ({nib['data_type']})"
                    if nib['usage']:
                        nib_entry += f"\n  Usage: {nib['usage']}"
                    nibs_list.append(nib_entry)
                
                nibs_formatted = "\n".join(nibs_list)
                
                user_prompt = text_indent_remove(f"""\
                    Tagname: {tagname}
                    Dependency Logic: {dependency_logic}

                    Available NIBs for this object type:
                    {nibs_formatted}

                    {feedback}

                    Select the most appropriate NIB name for this dependency condition.""")

                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            
                response = self.llm.chat(
                    messages=messages,
                    temperature=0.1,
                    max_tokens=100
                )
                
                # Extract NIB name from response
                suggested_nib = response.strip().strip('"\'')
                
                # Check if LLM determined no NIB fits
                if suggested_nib.upper() == "NONE":
                    return None
                
                # Validate the suggested NIB exists in references
                if suggested_nib in references:
                    nib_properties = references[suggested_nib].get('properties', {})
                    nib_usage = references[suggested_nib].get('value', '')
                    
                    return {
                        'nib_name': suggested_nib,
                        'nib_description': nib_properties.get('Description', ''),
                        'nib_data_type': nib_properties.get('DType', ''),
                        'nib_usage': nib_usage,
                        'confidence': 1.0 - (attempt * 0.2),  # Decrease confidence with retries
                        'attempts': attempt + 1,
                        'source': 'user_prompts'
                    }
                
                # NIB not found, provide feedback for next attempt
                if attempt < max_retries - 1:
                    valid_nibs = ', '.join(references.keys())
                    feedback = f"The NIB '{suggested_nib}' does not exist in this library. Please choose from these exact NIB names: {valid_nibs}"
            
            # Failed to find valid NIB after all retries
            return None
        except requests.exceptions.ConnectionError as e:
            raise
        except Exception as e:
            print(f"Error in __get_most_likely_status_for_dependency_from_user_prompts: {str(e)}")
            return None

        

    def __get_most_likely_status_for_dependency_from_nib_file(self, tagname, library_id, dependency_logic, catalog_number='', max_retries=3):
        """
        Use LLM to intelligently guess and validate NIB status indicators for a dependency.
        Will attempt up to max_retries times to find a valid NIB from the ACM library.
        
        :param tagname: The tagname to find status for
        :type tagname: str
        :param library_id: The ACM library ID
        :type library_id: str
        :param dependency_logic: The logic describing the dependency condition
        :type dependency_logic: str
        :param catalog_number: ACM catalog number, used to narrow the offered NIBs
        :type catalog_number: str
        :param max_retries: Maximum number of attempts (default: 3)
        :type max_retries: int
        :return: Dictionary with NIB information or None
        :rtype: dict or None
        """
        try:
            # Get the library parser and available NIBs
            if library_id not in self.__library_parsers:
                self.__library_parsers[library_id] = self.__parse_library_file(library_id)
            
            if not self.__library_parsers[library_id]:
                return None
            
            # Get library file path
            library_file_path = get_library_file_path(library_id, self.project_name)
            if not library_file_path:
                return None
                
            # First extract NIBS if not already done
            temp_dir = os.path.join(os.path.dirname(library_file_path), 'temp_nibs')
            os.makedirs(temp_dir, exist_ok=True)
            self.__library_parsers[library_id].extract_object_NIBS(temp_dir)
            
            # Import and get NIBs
            from bin.logic_acm_library_parser import get_object_NIBS
            nibs_dict = get_object_NIBS(library_file_path)
            if not nibs_dict:
                return None
            
            nibs_dict = {name: nibs_dict[name]
                         for name in allowed_status_references(catalog_number, nibs_dict)}
            if not nibs_dict:
                return None
            
            # Build list of available NIBs for the prompt
            available_nibs = []
            for nib_name, nib_info in nibs_dict.items():
                available_nibs.append({
                    'name': nib_name,
                    'description': nib_info.get('Description', ''),
                    'data_type': nib_info.get('DType', '')
                })
            
            # A single allowed reference leaves the LLM no choice to make.
            if len(available_nibs) == 1:
                only_nib = available_nibs[0]
                return {
                    'nib_name': only_nib['name'],
                    'nib_description': only_nib['description'],
                    'nib_data_type': only_nib['data_type'],
                    'confidence': 1.0,
                    'attempts': 0
                }
            
            # System prompt for NIB selection
            system_prompt = text_indent_remove("""\
                You are an expert in industrial automation and PlantPAx ACM libraries.
                Your task is to identify the most appropriate NIB (Named Interface Binding) status indicator
                for a dependency condition in interlock logic.
                
                NIBs are standardized status indicators that objects use to expose their state to other objects.
                The available NIBs differ per object type and may be deliberately restricted, so the provided
                list is the only source of valid answers. Never suggest a name that is absent from it, however
                common that name is in PlantPAx.
                
                If none of the available NIBs appropriately match the dependency logic, respond with "NONE".
                Otherwise, respond with ONLY a valid NIB name from the provided list.""")
            
            feedback = ""
            
            for attempt in range(max_retries):
                # Build the user prompt
                nibs_list = "\n".join([f"- {nib['name']}: {nib['description']} ({nib['data_type']})" 
                                      for nib in available_nibs])
                
                user_prompt = text_indent_remove(f"""\
                    Tagname: {tagname}
                    Dependency Logic: {dependency_logic}

                    Available NIBs:
                    {nibs_list}

                    {feedback}

                    Select the most appropriate NIB name for this dependency condition.""")

                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            
                response = self.llm.chat(
                    messages=messages,
                    temperature=0.1,
                    max_tokens=100
                )
                
                # Extract NIB name from response
                suggested_nib = response.strip().strip('"\'')
                
                # Check if LLM determined no NIB fits
                if suggested_nib.upper() == "NONE":
                    return None
                
                # Validate the suggested NIB exists
                if suggested_nib in nibs_dict:
                    nib_info = nibs_dict[suggested_nib]
                    return {
                        'nib_name': suggested_nib,
                        'nib_description': nib_info.get('Description', ''),
                        'nib_data_type': nib_info.get('DType', ''),
                        'confidence': 1.0 - (attempt * 0.2),  # Decrease confidence with retries
                        'attempts': attempt + 1
                    }
                
                # NIB not found, provide feedback for next attempt
                if attempt < max_retries - 1:
                    feedback = f"The NIB '{suggested_nib}' does not exist in this library. Please choose from the exact NIB names listed above."
            
            # Failed to find valid NIB after all retries
            return None
        except requests.exceptions.ConnectionError as e:
            raise
        except Exception as e:
            print(f"Error in __get_most_likely_status_for_dependency: {str(e)}")
            return None
        

    def __extract_dependencies(self, results, context, highlighted_text, page, text_on_page, selected_table, raw_dependent):
        """
        Extract dependency tagnames and their logic from interlock text using LLM
        
        :param results: Raw results from the LLM containing dependency extraction
        :type results: dict
        :param context: Context dictionary with table/row information
        :type context: dict
        :param highlighted_text: The highlighted text being processed
        :type highlighted_text: str
        :param page: PDF page object for text search
        :param selected_table: Table object containing the highlighted text
        :return: Dependencies extraction result with tagnames and logic
        :rtype: dict
        """
        try:
            # Build prompt for dependency extraction
            dependency_prompt = text_indent_remove(f"""\
                You are an expert in industrial automation interlock systems. Extract the dependency tagnames and their logic from the interlock condition text.

                Dependencies are equipment/instruments that provide the conditions for the interlock:
                - Process variables (temperature, pressure, flow, level indicators)  
                - Equipment status (pump running, valve position, motor state)
                - Safety devices (emergency stops, alarms, protective systems)
                - Any tagnames that are being monitored or checked as part of the condition

                Logic Types:
                - AND: All conditions must be true (e.g., "Pump running AND valve open")
                - OR: Any condition can be true (e.g., "High pressure OR low flow")
                - MIXED: Combination of AND/OR (e.g., "(Pump1 OR Pump2) AND Valve open")

                Examples:
                - "Pump P-101 running and valve V-205 open" → Dependencies: P-101 (status=running), V-205 (status=open), Logic: (P-101.running) AND (V-205.open), Type: AND
                - "Start pump P-102 when tank level TIT-301 > 50% or manual override enabled" → Dependencies: TIT-301 (value>50%), Manual_Override (status=enabled), Logic: (TIT-301.value > 50) OR (Manual_Override.enabled), Type: OR
                - "Close valve XV-205 if pressure PIT-101 > 100 PSI or emergency stop activated" → Dependencies: PIT-101 (value>100), Emergency_Stop (status=activated), Logic: (PIT-101.value > 100) OR (Emergency_Stop.activated), Type: OR
                - "Reactor heating enabled when (temperature TIC-401 < 200°C and flow FIT-205 > 10 GPM) or manual override" → Dependencies: TIC-401 (value<200), FIT-205 (value>10), Manual_Override (status=enabled), Logic: ((TIC-401.value < 200) AND (FIT-205.value > 10)) OR (Manual_Override.enabled), Type: MIXED
                - "Start pump when (Level_High OR Level_VeryHigh) AND Valve_Open" → Dependencies: Level_High (status=true), Level_VeryHigh (status=true), Valve_Open (status=true), Logic: ((Level_High.status) OR (Level_VeryHigh.status)) AND (Valve_Open.status), Type: MIXED

                Extract:
                1. All tagnames/identifiers mentioned as conditions
                2. The logic condition for each dependency
                3. The logic type: "AND", "OR", or "MIXED"
                4. The overall logic expression combining all dependencies with proper parentheses for precedence""")

            # Prepare context-specific prompt
            if context and context.get('row_and_column'):
                selected_row, selected_column = context['row_and_column']
                user_prompt = text_indent_remove(f"""\
                    5. Identify row and columns that contain the tagname/object name
                    
                    Respond in JSON format:
                    {{
                        "dependencies": [
                            {{
                                "tagname": "TIC-401",
                                "condition": "value < 200",
                                "operator": "<",
                                "value": "200",
                                "row": 1,
                                "column": 2
                            }},
                            {{
                                "tagname": "FIT-205", 
                                "condition": "value > High-High",
                                "operator": ">",
                                "value": "High-High",
                                "row": 2,
                                "column": 2
                            }},
                            {{
                                "tagname": "Manual_Override",
                                "condition": "status = enabled",
                                "operator": "=",
                                "value": "enabled",
                                "row": 3,
                                "column": 2
                            }},
                            {{
                                "tagname": "PUM-105",
                                "condition": "status = running",
                                "operator": "=",
                                "value": "running",
                                "row": 3,
                                "column": 2
                            }}
                        ],
                        "logic_type": "MIXED",
                        "logic_expression": "((TIC-401.value < 200) AND (FIT-205.value > High-High)) OR (Manual_Override.status = enabled) OR (PUM-105.status = running)"
                    }}
                                              
                
                    Extract dependency tagnames and logic from this table context:

                    TABLE CONTEXT: 
                    {context['full_table']}

                    EQUIPMENT BEING CONTROLLED: {raw_dependent}

                    Focus on the equipment being controlled to identify dependency conditions.

                    For row and column reference use this cell:
                    CELL TEXT: "{highlighted_text}"
                    ROW: {selected_row}
                    COLUMN: {selected_column}

                    Dependencies and Logic:""")
                
            elif context and context.get('type')== 'list':
                context_text = context.get('full_list', '') if context else ''
                user_prompt = text_indent_remove(f"""\
                    5. Identify list items that contain the tagname/object name
                    6. Also give the full list item text for context
                    7. If the text is from multiple segments in the text, list the segments
                                                
                    Respond in JSON format:
                    {{
                        "dependencies": [
                            {{
                                "tagname": "TIC-401",
                                "condition": "value < 200",
                                "operator": "<",
                                "value": "200",
                                "list_index": 0,
                                "full_text": "TIC-401 reading below 200",
                                "full_text_segments": ["TIC-401 reading", "below 200"]
                            }},
                            {{
                                "tagname": "FIT-205",
                                "condition": "value > High-High",
                                "operator": ">",
                                "value": "High-High",
                                "list_index": 1,
                                "full_text": "FIT-205 above High-High limit",
                                "full_text_segments": ["FIT-205 above High-High limit"]
                            }},
                            {{
                                "tagname": "Manual_Override",
                                "condition": "status = enabled",
                                "operator": "=",
                                "value": "enabled",
                                "list_index": 1,
                                "full_text": "Manual_Override enabled",
                                "full_text_segments": ["Manual_Override enabled"]
                            }},
                            {{
                                "tagname": "PUM-105",
                                "condition": "status = running",
                                "operator": "=",
                                "value": "running",
                                "list_index": 2,
                                "full_text": "PUM-105 is currently running",
                                "full_text_segments": ["PUM-105", "is currently running"]
                            }}
                        ],
                        "logic_type": "MIXED",
                        "logic_expression": "(TIC-401.value < 200) AND (FIT-205.value > High-High) OR (Manual_Override.status = enabled) AND (PUM-105.status = running)"
                    }}

                    Extract dependency tagnames and logic from this list context:

                    FULL LIST: 
                    {context_text}
                    
                    EQUIPMENT BEING CONTROLLED: {raw_dependent}

                    Focus on the equipment being controlled to identify dependency conditions.

                    Dependencies and Logic:""")
            else:
                context_text = context.get('text_blocks_string', '') if context else ''
                user_prompt = text_indent_remove(f"""\
                    5. Also give the exact full statement/text for context
                    6. If the text is from multiple segments in the text, list the segments
                                                
                    Respond in JSON format:
                    {{
                        "dependencies": [
                            {{
                                "tagname": "TIC-401",
                                "condition": "value < 200",
                                "operator": "<",
                                "value": "200",
                                "full_text": "TIC-401 reading below 200",
                                "full_text_segments": ["TIC-401 reading", "below 200"]
                            }},
                            {{
                                "tagname": "FIT-205",
                                "condition": "value > High-High",
                                "operator": ">",
                                "value": "High-High",
                                "full_text": "FIT-205 above High-High limit",
                                "full_text_segments": ["FIT-205 above High-High limit"]
                            }},
                            {{
                                "tagname": "Manual_Override",
                                "condition": "status = enabled",
                                "operator": "=",
                                "value": "enabled",
                                "full_text": "Manual_Override enabled",
                                "full_text_segments": ["Manual_Override enabled"]
                            }},
                            {{
                                "tagname": "PUM-105",
                                "condition": "status = running",
                                "operator": "=",
                                "value": "running",
                                "full_text": "PUM-105 is currently running",
                                "full_text_segments": ["PUM-105", "is currently running"]
                            }}
                        ],
                        "logic_type": "MIXED",
                        "logic_expression": "(TIC-401.value < 200) AND (FIT-205.value > High-High) OR (Manual_Override.status = enabled) AND (PUM-105.status = running)"
                    }}
                                                 
                    Extract dependency tagnames and logic from this text:
                                                 
                    CONTEXT: "{context_text}"

                    HIGHLIGHTED TEXT: "{highlighted_text}"
                    

                    Dependencies and Logic:""")

            messages = [
                {"role": "system", "content": dependency_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            response = self.llm.chat(
                messages=messages,
                temperature=0.1,
                max_tokens=5000
            )
            
            # Parse JSON response
            if response.startswith('{'):
                data = json.loads(response)
            else:
                # Try to extract JSON from response
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())
                else:
                    raise ValueError("No valid JSON found")
            
            # Process extracted dependencies
            dependencies = data.get('dependencies', [])
            dependencies_dict = {}
            
            for dep in dependencies:
                tagname = dep.get('tagname', '')
                if tagname:
                    # Check ACM for tagname details
                    source_text = '\n'.join(filter(None, [dep.get('full_text', ''),
                                                          context_source_text(highlighted_text, context)]))
                    acm_object_df = self.check_acm_for_tagname(tagname, source_text)
                    
                    dependencies_dict[tagname] = {
                        'condition': dep.get('condition', ''),
                        'operator': dep.get('operator', ''),
                        'value': dep.get('value', ''),
                        'row': dep.get('row', ''),
                        'column': dep.get('column', ''),
                        'list_index': dep.get('list_index', ''),
                        'full_text': dep.get('full_text', ''),
                        'full_text_segments': dep.get('full_text_segments', []),
                        'acm_objects': {}
                    }
                    
                    # Add ACM object details if found
                    for object_id, row in acm_object_df.iterrows():

                        library_df = self.acm_data_handler.get_registered_library(row['LibraryID'])
                        core_type = library_df.loc[row['LibraryID']]['CoreType'] if not library_df.empty else ''

                        dependencies_dict[tagname]['acm_objects'][object_id] = {
                            'name': row['Name'],
                            'library_id': row['LibraryID'],
                            'catalog_number': row.get('CatalogNumber', ''),
                            'core_type': core_type,
                        }
            
            # Find bounding boxes for dependency tagnames in the table
            dependency_bboxes = {}
            dependency_text = {}
            
            if context['type'] == 'table':
                self.__extract_table_dependency(page, text_on_page, selected_table, dependencies_dict, dependency_bboxes, dependency_text)
            elif context['type'] == 'list':
                self.__extract_list_dependency(page, text_on_page, context, dependencies_dict, dependency_bboxes, dependency_text)
            else:
                self.__extract_text_dependency(page, text_on_page, context, dependencies_dict, dependency_bboxes, dependency_text)

            return {
                "success": True,
                "dependencies": dependencies_dict,
                "logic_expression": data.get('logic_expression', ''),
                "logic_type": data.get('logic_type', ''),
                "dependency_bboxes": dependency_bboxes,
                "dependency_text": dependency_text,
                "total_dependencies": len(dependencies_dict),
                "raw_response": response.strip(),
                "highlighted_text": highlighted_text,
                "context": context
            }
        except requests.exceptions.ConnectionError as e:
            raise
        except Exception as e:
            return {
                "success": False,
                "dependencies": {},
                "logic_expression": "",
                "logic_type": "",
                "dependency_bboxes": {},
                "dependency_text": {},
                "total_dependencies": 0,
                "error": str(e),
                "highlighted_text": highlighted_text,
                "context": context
            }
        

    def __extract_text_dependency(self, page, text_on_page, context, dependencies_dict, dependency_bboxes,  dependency_text):
        for tagname, tagname_data in dependencies_dict.items():
            tagname_rects = page.search_for(tagname)
            if 'full_text_segments' in tagname_data and len(tagname_data['full_text_segments']) > 1:
                full_text_rects = []
                is_from_segment = True
                for segment in tagname_data['full_text_segments']:
                    segment_rects = page.search_for(segment)
                    full_text_rects.extend([[segment, rect] for rect in segment_rects])
            else:
                full_text = tagname_data['full_text']
                full_text_rects =  [[full_text,rect] for rect in page.search_for(full_text)]
                is_from_segment = False

            for rect in tagname_rects:
                tagname_bbox = [rect.x0, rect.y0, rect.x1, rect.y1]
                    
                for full_text, full_text_rect in full_text_rects:
                    
                    full_text_bbox = [full_text_rect.x0, full_text_rect.y0, full_text_rect.x1, full_text_rect.y1]
                    if not self.__is_within_bbox(full_text_bbox, context['text_blocks_bbox']):
                        continue

                    list_text = get_text_in_bbox(None, None, None,text_on_page, bbox=full_text_bbox)

                    if list_text['text'] !=  '':
                        indexes = list_text['indexes']
                    else:
                        indexes = (None, None)
                        
                    if self.__is_within_bbox(tagname_bbox, full_text_bbox):
                        dependency_bboxes[tagname] = [tagname_bbox]
                        dependency_text[tagname] = {
                            'text': full_text,
                            'indexes': indexes  # Indexes not tracked in list context
                        }
                        if is_from_segment:
                            tagname_data['full_text_alternative'] = full_text
                        break

        
    def __extract_list_dependency(self, page, text_on_page, context, dependencies_dict, dependency_bboxes,  dependency_text):
        for tagname, tagname_data in dependencies_dict.items():
            tagname_rects = page.search_for(tagname)
            '''if 'full_text_segments' in tagname_data and len(tagname_data['full_text_segments']) > 1:
                list_item_text_rects = []
                is_from_segment = True
                for segment in tagname_data['full_text_segments']:
                    segment_rects = page.search_for(segment)
                    list_item_text_rects.extend([[segment, rect] for rect in segment_rects])
            else:'''
            is_from_segment = False
            list_item_text = tagname_data['full_text']
            list_item_text_rects = [[list_item_text,rect] for rect in page.search_for(list_item_text)]

            for rect in tagname_rects:
                tagname_bbox = [rect.x0, rect.y0, rect.x1, rect.y1]
                    
                for list_item_text, list_item_text_rect in list_item_text_rects:
                    
                    list_text_item_bbox = [list_item_text_rect.x0, list_item_text_rect.y0, list_item_text_rect.x1, list_item_text_rect.y1]
                    if not self.__is_within_bbox(list_text_item_bbox, context['list_bbox']):
                        continue

                    list_text = get_text_in_bbox(None, None, None,text_on_page, bbox=list_text_item_bbox)

                    if list_text['text'] !=  '':
                        indexes = list_text['indexes']
                    else:
                        indexes = (None, None)
                        
                    if self.__is_within_bbox(tagname_bbox, list_text_item_bbox):
                        dependency_bboxes[tagname] = [tagname_bbox]
                        dependency_text[tagname] = {
                            'text': list_item_text,
                            'indexes': indexes  # Indexes not tracked in list context
                        }
                        if is_from_segment:
                            tagname_data['full_text_alternative'] = list_item_text
                        break





    def __extract_table_dependency(self, page, text_on_page, selected_table, dependencies_dict, dependency_bboxes, dependency_text):
        for tagname, tagname_data in dependencies_dict.items():
            text_rects = page.search_for(tagname)
            row = tagname_data['row']
            column = tagname_data['column']

            text_in_cell = get_text_in_bbox(selected_table, row, column, text_on_page)

            if tagname not in text_in_cell['text']:
                continue
                
                # For simple cases where the hyphenated tagname is not split across lines
            for rect in text_rects:
                text_bbox = [rect.x0, rect.y0, rect.x1, rect.y1]
                    
                if self.__is_within_bbox(text_bbox, selected_table.rows[row].cells[column]):
                    dependency_bboxes[tagname] = [text_bbox]
                    dependency_text[tagname] = text_in_cell
                    break
                
                # Handle hyphenated tagnames that may be split across lines
            if '-' in tagname and not text_rects:
                cell_start_index, _ = text_in_cell['indexes']
                cell_text = text_in_cell['text']

                text_pos = cell_text.find(tagname)

                if text_pos == -1:
                    continue

                absolute_start_index = cell_start_index + text_pos
                absolute_end_index = absolute_start_index + len(tagname) - 1

                bboxes_in_range = [text_on_page[i]['bbox'] for i in range(absolute_start_index, absolute_end_index + 1)]
                    

                if bboxes_in_range:
                    dependency_bboxes[tagname] = bboxes_in_range
                    dependency_text[tagname] = text_in_cell



    def check_acm_for_tagname(self, tagname, source_text=None):
        """
        Check ACM data handler for tagname details if available
        
        :param tagname: Tagname to look up
        :type tagname: str
        :param source_text: Document text the tagname was extracted from, used to resolve a
            bracketed ACM object reference when the tagname itself names no object
        :type source_text: str or None
        :return: ACM data details or empty DataFrame
        :rtype: DataFrame
        """
        return lookup_acm_object(self.acm_data_handler, tagname, source_text)

    def post_process_paramter_extraction(self, results, context, highlighted_text, parameter_properties, selected_table, page ):
        """
        Post-process the results from the LLM to enhance accuracy and context
        :param results: Raw results from the LLM
        :type results: dict
        :return: Processed results
        :rtype: dict
        """
        tagname_text_bbox = None
        parameter_text_bbox = None
        raw_tagname = results['tagname_extraction']['raw_tagname']
        raw_tagname = raw_tagname.strip()
        text_rects = page.search_for(raw_tagname)

        selected_row, _ = context['row_and_column']
        for rect in text_rects:
            text_bbox = [rect.x0, rect.y0, rect.x1, rect.y1]
            if self.__is_within_bbox(text_bbox, selected_table.rows[selected_row].bbox):
                tagname_text_bbox = text_bbox
                break
        
        
        parameter_name = parameter_properties['Name']
        parameter_data_type = parameter_properties['DType']


        data_entry_types = {
            'String': self.__is_string,
            'Real': self.__is_real,
            'Int': self.__is_int, 
        }

        if data_entry_types[parameter_data_type](highlighted_text, parameter_properties):
            # Remove Trailing and Leading spaces
            highlighted_text = highlighted_text.strip()
            text_rects = page.search_for(highlighted_text)
            for rect in text_rects:
                text_bbox = [rect.x0, rect.y0, rect.x1, rect.y1]
                if self.__is_within_bbox(text_bbox, selected_table.rows[selected_row].bbox):
                    parameter_text_bbox = text_bbox
                    break

            # Duplicate-annotation guard: if a persisted text link on this
            # page already covers ``(tagname, parameter_name,
            # parameter_value)`` we return ``None`` so the caller does not
            # save a duplicate. ``page.parent.name`` / ``page.number`` are
            # used to derive path + pno since this method does not receive
            # them directly.
            path = getattr(getattr(page, 'parent', None), 'name', None)
            pno = getattr(page, 'number', None)
            candidate_key = annotation_dedupe_key(
                raw_tagname, parameter_name, highlighted_text
            )
            if candidate_key in self._collect_existing_annotation_keys(path, pno):
                logging.debug(
                    "Skipping duplicate manual parameter annotation: %s",
                    candidate_key,
                )
                return None

            return {
                "tagname": {'raw_text': raw_tagname, 'bbox': tagname_text_bbox},
                "parameter": {'raw_text': highlighted_text, 'bbox': parameter_text_bbox, 'parameter_name': parameter_name}
            }

    def __is_string(self, text, _):
        if isinstance(text, str):
            return True
        return False

    def __is_int(self, text, _):
        if str.isdigit(text) or text == "":
            return True
        return False
    

    def __is_real(self, text, parameter):
        min = float(parameter['Min'])
        max = float(parameter['Max'])
        regex = re.compile(r"[+-]?(\d+([.]\d*)?([eE][+-]?\d+)?|[.]\d+([eE][+-]?\d+)?)")
        try:
            result = regex.match(text)
            return (text == ""
                    or (text.count('+') <= 1
                        and text.count('-') <= 1
                        and text.count('.') <= 1
                        and result is not None
                        and result.group(0) != ""
                        and float(text) >= min
                        and float(text) <= max))
        except ValueError:
            return False

    def __is_within_bbox(self, bbox, cell_bbox):
        cell_x1, cell_y1, cell_x2, cell_y2 = cell_bbox
        return (bbox[0] >= cell_x1 and 
                bbox[2] <= cell_x2 and 
                bbox[1] >= cell_y1 and 
                bbox[3] <= cell_y2)
    

    def __identify_text_to_ignore(self, dependencies_result):
        """
        Identify text segments that are descriptive/specific to the instance vs. generic property text.
        Uses LLM to distinguish between:
        - Descriptive text: Specific identifiers, locations, physical descriptions (should be ignored)
        - Generic text: Property names, conditions, states that apply to any similar object (should NOT be ignored)
        
        :param dependencies_result: Result dictionary containing dependency information
        :type dependencies_result: dict
        :return: Updated dependencies_result with text_to_ignore field added
        :rtype: dict
        """
        if not dependencies_result.get('success'):
            return dependencies_result
        
        try:
            # System prompt for text classification
            system_prompt = text_indent_remove("""\
                You are an expert in industrial automation control systems and technical documentation.
                Your task is to identify which parts of text are DESCRIPTIVE (instance-specific) vs. GENERIC (property/condition).
                
                CRITICAL: Always KEEP tagnames and identifiers - they should NOT be ignored.
                
                DESCRIPTIVE text (should be IGNORED):
                - Physical location descriptions (discharge, inlet, outlet, upstream, downstream)
                - Equipment type specifications (manual, pneumatic, electric) - BUT NOT control equipment types
                - Any text that specifies a unique instance of equipment
                - Specific measurements or calibration values unique to this instance - BUT NOT generic measurement types
                - Manufacturer names, model numbers
                - Specific channel/address identifiers (that are NOT tagnames)
                
                GENERIC text (should NOT be ignored):
                - Tagnames, identifiers, serial numbers (HSA-00104A, TIT-305, 45-PIT-201, E-STOP-01, 85-TI-501, etc.)
                - State/condition words: open, closed, running, stopped, healthy, faulted, alarm, normal
                - Property types: limit switch, sensor, transmitter, indicator, controller
                - Control equipment types: pump, motor, valve, analog input, digital output, digital input, actuator, drive, VFD
                - Generic functional descriptions: switch, relay, contactor
                - Status qualifiers: high, low, enabled, disabled, ready, not ready, hihi, hi, lo, lolo, running
                - Measurement types: pressure, temperature, flow, level
                
                Examples:
                1. "Discharge manual valve open limit switch HSA-00104A healthy"
                   - IGNORE: "Discharge", "manual"
                   - KEEP: "HSA-00104A", "valve", "open", "limit switch", "healthy"
                
                2. "Inlet temperature high alarm TIT-305"
                   - IGNORE: "Inlet"
                   - KEEP: "TIT-305", "temperature", "high", "alarm"
                
                3. "Pneumatic actuator position sensor ready"
                   - IGNORE: "Pneumatic"
                   - KEEP: "actuator", "position", "sensor", "ready"
                
                4. "Emergency stop button pressed E-STOP-01"
                   - IGNORE: (nothing)
                   - KEEP: "E-STOP-01", "Emergency stop", "button", "pressed"
                   
                5. "Pump discharge pressure transmitter PIT-201 value high"
                   - IGNORE: "discharge"
                   - KEEP: "PIT-201", "Pump", "pressure", "transmitter", "value", "high"
                
                6. "Motor starter digital input ready M-101"
                   - IGNORE: (nothing)
                   - KEEP: "M-101", "Motor", "starter", "digital input", "ready"
                
                Respond in JSON format with text segments to ignore.""")
            
            dependencies = dependencies_result.get('dependencies', {})
            context_type = dependencies_result.get('context', {}).get('type', 'text')
            dependency_text = copy.deepcopy(dependencies_result.get('dependency_text', {}))
            
            # Process each dependency's text using multi-threading
            import concurrent.futures
            
            def process_dependency_text(tagname, text_info, context_type):
                """Process a single dependency's text to identify ignore/keep segments."""
                if not text_info or 'text' not in text_info:
                    return tagname, None
                
                full_text = text_info['text']
                if not full_text or not full_text.strip():
                    return tagname, {}

                if 'full_text_alternative' in text_info and context_type == 'text':
                    return tagname, {
                        'text_to_ignore': [],
                        'text_to_keep': [],
                        'full_text': full_text
                    }
                
                # Build user prompt
                user_prompt = text_indent_remove(f"""\
                    Analyze this text and identify which parts should be IGNORED (descriptive/instance-specific):
                    
                    TEXT: "{full_text}"
                    TAGNAME IDENTIFIED: "{tagname}"
                    
                    IMPORTANT: Keep all tagnames and identifiers. DO NOT mark tagnames as text to ignore.
                    
                    Respond in JSON format:
                    {{
                        "text_to_ignore": [
                            {{"text": "Discharge", "reason": "location descriptor"}},
                            {{"text": "manual", "reason": "equipment type modifier"}}
                        ],
                        "text_to_keep": [
                            {{"text": "HSA-00104A", "reason": "tagname/identifier"}},
                            {{"text": "valve", "reason": "generic equipment type"}},
                            {{"text": "open", "reason": "state/condition"}},
                            {{"text": "limit switch", "reason": "generic property type"}},
                            {{"text": "healthy", "reason": "status qualifier"}}
                        ]
                    }}""")
                
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
                
                try:
                    response = self.llm.chat(
                        messages=messages,
                        temperature=0.1,
                        max_tokens=2000
                    )
                    
                    # Parse JSON response
                    if response.startswith('{'):
                        data = json.loads(response)
                        print(data)
                    else:
                        # Try to extract JSON from response
                        json_match = re.search(r'\{.*\}', response, re.DOTALL)
                        if json_match:
                            data = json.loads(json_match.group())
                            print(data)
                        else:
                            return tagname, None
                    
                    return tagname, {
                        'text_to_ignore': data.get('text_to_ignore', []),
                        'text_to_keep': data.get('text_to_keep', []),
                        'full_text': full_text
                    }
                    
                except Exception as e:
                    logging.error(f"Error processing dependency {tagname}: {e}")
                    return tagname, {
                        'text_to_ignore': [],
                        'text_to_keep': [],
                        'full_text': full_text
                    }
            
            # Use ThreadPoolExecutor for concurrent processing
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                # Submit all tasks
                future_to_tagname = {
                    executor.submit(process_dependency_text, tagname, text_info, context_type): tagname
                    for tagname, text_info in dependency_text.items()
                }
                
                # Collect results as they complete
                for future in concurrent.futures.as_completed(future_to_tagname):
                    tagname, result = future.result()
                    
                    # Add the ignore/keep information to the dependency
                    if result and tagname in dependencies:
                        dependencies[tagname]['text_to_ignore'] = result['text_to_ignore']
                        dependencies[tagname]['text_to_keep'] = result['text_to_keep']
                        dependencies[tagname]['full_text'] = result['full_text']
            return dependencies_result
        
        except requests.exceptions.ConnectionError as e:
            raise
        except Exception as e:
            # If there's an error, return the original result without modifications
            print(f"Error in __identify_text_to_ignore: {str(e)}")
            return dependencies_result

    def __parse_library_file(self, library_id):
        """
        Parse ACM library file to get parameter information.
        
        :param library_id: Library ID to parse
        :type library_id: str
        :return: Library parser instance
        :rtype: acm_library_parser
        """
        library_file_path = get_library_file_path(library_id, self.project_name)
        if not library_file_path:
            projects_df = self.acm_data_handler.get_all_projects()
            acm_project_name = projects_df.loc[int(self.acm_data_handler.get_project_id())]['Name']
            acm_libraries_retrieval(self.project_name, acm_project_name, threaded=False)
            library_file_path = get_library_file_path(library_id, self.project_name)
            if not library_file_path:
                raise Exception(f"Unable to access parameters for library {library_id}.")
        return acm_library_parser(library_file_path)

class TextDocumentLLMProcessor:
    def __init__(self, llm: UnifiedInference, project_name: str, acm_data_handler: ACM_Data_Handler = None, internal_db: Database = None, config: Config = None):
        """
        Main processor that uses example from how previous linked Text extraction have been done to comeup with new extractions

        :param llm: LLM inference instance
        :param project_name: Name of the project for context
        :param acm_data_handler: Optional ACM data handler for tagname lookups
        :type llm: UnifiedInference
        :type project_name: str
        :type acm_data_handler: ACM_Data_Handler or None
        """
        self.llm = llm
        self.project_name = project_name
        self.acm_data_handler = acm_data_handler
        self.internal_db = internal_db
        self.linked_texts: List[LinkedText] = []
        self.table_examples: List[LinkedText] = []
        self.list_examples: List[LinkedText] = []
        self.general_examples: List[LinkedText] = []
        self.__library_parsers = {}
        self.table_examples_count = 0
        self.list_examples_count = 0
        self.general_examples_count = 0
        self.config = config

    def _collect_existing_annotation_keys(self, path, pno) -> set:
        """
        Mirror of
        ``TextDocumentLLMPostProcessor._collect_existing_annotation_keys`` —
        returns the set of ``annotation_dedupe_key`` tuples already persisted
        for ``(path, pno)`` across approved, unapproved, and rejected
        text-link tables so ``process_parameter_tables_with_examples`` can
        drop rebuilt LinkedTexts that duplicate a prior run.
        """
        existing_keys = set()
        if not self.internal_db or path is None or pno is None:
            return existing_keys

        records = []
        for accessor in (
            'get_all_approved_text_links_by_page_no',
            'get_all_unapproved_text_links_by_page_no',
            'get_all_rejected_text_links_by_page_no',
        ):
            fn = getattr(self.internal_db, accessor, None)
            if fn is None:
                continue
            try:
                result = fn(path, pno)
            except Exception as exc:
                logging.debug(
                    "Skipping %s during annotation-dedupe lookup: %s",
                    accessor, exc,
                )
                continue
            if isinstance(result, dict):
                records.extend(result.values())
            elif isinstance(result, list):
                records.extend(result)

        for record in records:
            if not isinstance(record, dict):
                continue
            tagname_entry = record.get('tagname')
            tagname_text = (
                tagname_entry.get('text') if isinstance(tagname_entry, dict) else None
            )
            parameters = record.get('parameters') or {}
            if not isinstance(parameters, dict) or not parameters:
                continue
            for parameter_name, parameter_entry in parameters.items():
                parameter_value = (
                    parameter_entry.get('text')
                    if isinstance(parameter_entry, dict)
                    else None
                )
                existing_keys.add(
                    annotation_dedupe_key(tagname_text, parameter_name, parameter_value)
                )

        return existing_keys

    @staticmethod
    def _rebuilt_linked_text_annotation_keys(rebuilt_linked_text) -> list:
        """
        Extract the annotation keys represented by a rebuilt LinkedText entry
        (as produced by ``_rebuild_linked_texts_from_validated_results``).
        Each parameter within the entry produces one key; a rebuilt entry is
        considered a duplicate only if *every* key is already persisted.
        """
        if not isinstance(rebuilt_linked_text, dict):
            return []
        tagname_lt = rebuilt_linked_text.get('tagname')
        tagname_text = getattr(tagname_lt, 'text', None)
        parameters = rebuilt_linked_text.get('parameters') or {}
        if not isinstance(parameters, dict):
            return []
        keys = []
        for parameter_name, parameter_lt in parameters.items():
            parameter_value = getattr(parameter_lt, 'text', None)
            keys.append(
                annotation_dedupe_key(tagname_text, parameter_name, parameter_value)
            )
        return keys



    def set_example_linked_texts(self, linked_texts: list[dict[str,LinkedText]]):
        """
        Set previously linked texts to provide context for processing

        Example of the extraction will be generated for the try types of text based data 
        1. Table based text
        2. List based text
        3. General text

        :param linked_texts: List of previously linked text entries
        :type linked_texts: list of dict
        """
        # Filter only new user inputed linked texts
        linked_texts = self.filter_new_user_inputed_linked_texts(linked_texts)

        # Sort by timestamp descending to get most recent examples first
        linked_texts.sort(key=lambda x: x.get('timestamp', 0), reverse=True)

    
        self.linked_texts = linked_texts

        

        self.table_examples = []
        self.list_examples = []
        self.general_examples = []

        for linked_text in linked_texts:
            if linked_text['text_relationship'] == TagnameParameterRelationship.IN_TABLE:
                self.table_examples.append(linked_text)
            elif linked_text['text_relationship'] == TagnameParameterRelationship.LIST_HEADER:
                self.list_examples.append(linked_text)
            else:
                self.general_examples.append(linked_text)


        


    def filter_new_user_inputed_linked_texts(self, linked_texts: list[dict[str,LinkedText]]):
        """
        Check if the provided linked texts are new user inputs compared to existing ones

        :param linked_texts: List of linked text entries to check
        :type linked_texts: list of dict
        :return: True if new user inputs, False otherwise
        :rtype: bool
        """
        new_list = []

        for new_lt in linked_texts:
            if new_lt.get('is_llm_generated', False) == False:
                new_list.append(new_lt)
        return new_list
    



        
    def process_parameter_tables_with_examples(self, table_context, examples=None, max_retries=3):
        """
        Process a table to extract parameters based on provided examples.
        Uses iterative LLM calls with feedback when parameters don't exist.
        
        :param table_context: Table structure and content
        :type table_context: dict
        :param examples: List of example extractions to guide the process
        :type examples: list[dict]
        :param max_retries: Maximum number of retry attempts
        :type max_retries: int
        :return: Extracted parameters with validation results
        :rtype: dict
        """

        if self.__has_table_already_been_processed(table_context):
            return {
                "success": False,
                "error": "Table has already been processed."
            }
        


        if not examples and not self.table_examples:
            return {
                "success": False,
                "error": "No example linked texts available for table parameter extraction."
            }
        
        if self.table_examples_count == len(self.table_examples):
            return {
                "success": False,
                "error": "All available table examples have been used for extraction."
            }
        self.table_examples_count = len(self.table_examples)

        # Use examples to build the extraction prompt
        example_prompt = self._build_examples_prompt(examples or self.table_examples[:3])
        
        # Initial extraction attempt
        extraction_result = self._extract_parameters_from_table(table_context, example_prompt)
        
        # Validate and retry if needed
        validated_result = self._validate_and_retry_extraction(
            extraction_result, table_context, example_prompt, max_retries
        )

        # Rebuild new linked text based on validated results
        rebuilt_linked_texts = self._rebuild_linked_texts_from_validated_results(
            validated_result, table_context
        )

        # Cross-run dedupe: drop rebuilt LinkedTexts whose annotation key
        # already exists on this page in any persisted state (approved,
        # unapproved, or rejected). Intra-call dedupe is already handled in
        # ``_validate_and_retry_extraction`` and
        # ``_rebuild_linked_texts_from_validated_results``; this guard
        # prevents repeated LLM runs from re-emitting the same annotation
        # into ``__save_new_text_links``.
        existing_keys = self._collect_existing_annotation_keys(
            table_context.get('path'), table_context.get('pno')
        )
        if existing_keys:
            filtered_rebuilt = []
            for entry in rebuilt_linked_texts:
                entry_keys = self._rebuilt_linked_text_annotation_keys(entry)
                if entry_keys and all(k in existing_keys for k in entry_keys):
                    logging.debug(
                        "Skipping rebuilt LinkedText already persisted on page: %s",
                        entry_keys,
                    )
                    continue
                filtered_rebuilt.append(entry)
            rebuilt_linked_texts = filtered_rebuilt

        # Add rebuilt linked texts to the result
        validated_result['rebuilt_linked_texts'] = rebuilt_linked_texts

        self.internal_db.save_table_already_processed_by_llm(
            table_context.get('path'),
            table_context.get('pno'),
            table_context.get('table_bbox'),
            self.llm.get_model_name(),
        )

        return validated_result
    

    def __has_table_already_been_processed(self, table_context):
        """
        Check if the table has already been processed by comparing with internal database records.
        
        :param table_context: Table structure and content
        :type table_context: dict
        :return: True if already processed, False otherwise
        :rtype: bool
        """
        bbox = table_context.get('table_bbox')
        pno = table_context.get('pno')
        path = table_context.get('path')
        table_data = self.internal_db.get_table_already_processed_by_llm(path, pno, bbox)

        if table_data is None:
            return False
        
        # Get latest table example timestamp
        latest_example_timestamp = self.table_examples[0]['timestamp'] if self.table_examples else 0

        if latest_example_timestamp > table_data['timestamp']:
            return False
        return True
    

    def _build_examples_prompt(self, examples:list[dict[str,LinkedText]]):
        """
        Build a comprehensive prompt using examples of successful parameter extractions.
        
        :param examples: List of example LinkedText objects
        :type examples: list[dict]
        :return: Formatted examples prompt
        :rtype: str
        """
        if not examples:
            return "No examples available. Use general industrial automation parameter patterns."
        
        examples_text = []
        for i, example in enumerate(examples[:3], 1):
            tagname_linked_text:LinkedText = example['tagname']
            tagname_linked_text_given_text:LinkedText = list(tagname_linked_text.given_text.values())[0]
            parameter_linked_text:LinkedText = list(example['parameters'].values())[0]
            parameter_linked_text_given_text:LinkedText = list(parameter_linked_text.given_text.values())[0]
            
            example_text = text_indent_remove(f"""
            EXAMPLE {i}:
            
            Extracted Results:
            - Tagname: {tagname_linked_text.text}
            - Tagname Row {tagname_linked_text_given_text.roi[0]}
            - Tagname Column {tagname_linked_text_given_text.roi[1]}
            - Parameter: {list(example['parameters'].keys())[0]}
            - Parameter Row {parameter_linked_text_given_text.roi[0]} 
            - Parameter Column {parameter_linked_text_given_text.roi[1]}
            - Parameter Type: {parameter_linked_text.text_type}
            - Value: {parameter_linked_text.text}
            
            """)
            examples_text.append(example_text)
        
        return "\n".join(examples_text)

    def _extract_parameters_from_table(self, table_context, examples_prompt):
        """
        Extract parameters from table using examples as guidance.
        
        :param table_context: Table structure and content
        :type table_context: dict
        :param examples_prompt: Formatted examples prompt
        :type examples_prompt: str
        :return: Initial extraction results
        :rtype: dict
        """
        extraction_prompt = text_indent_remove(f"""
        You are an expert in industrial automation parameter extraction. Using the provided examples,
        analyze this table and extract all possible parameter-value pairs.
                                            
        TABLE CONTEXT:
        {table_context.get('full_table', '')}

        EXAMPLES OF SUCCESSFUL EXTRACTIONS FROM THE TABLE:
        {examples_prompt}

        EXTRACTION INSTRUCTIONS:
        1. Identify row and columns that contain tagname/object name
        2. Identify row and columns that contain parameter values
        3. Identify for only one tagname/object
        4. Match the extraction patterns from the examples
        5. Consider table headers and column relationships

        EXPECTED OUTPUT FORMAT:
        For each extractable parameter, provide:
        - Tagname Row index (0-based including header rows)
        - Tagname Column index (0-based including header columns)
        - Tagname/Object identifier
        - Parameter Row index (0-based including header rows)
        - Parameter Column index (0-based including header columns)
        - Parameter name (based on column header or inferred from examples)
        - Parameter value
        - Confidence score (0.0-1.0)

        Respond in JSON format:
        {{
            "extracted_parameters": [
                {{
                    "tagname": "TIC-101",
                    "tagname_row_index": 1,
                    "tagname_column_index": 0,
                    "parameter_name": "Cfg_HiHiLim",
                    "parameter_row_index": 1,
                    "parameter_column_index": 2,
                    "parameter_value": "85.5",
                    "confidence": 0.95,
                    "extraction_reasoning": "Column header indicates high-high limit values"
                }}
            ]
        }}
        """)
        
        messages = [
            {"role": "user", "content": extraction_prompt}
        ]
        
        response = self.llm.chat(
            messages=messages,
            temperature=0.1,
            max_tokens=5000
        )

        logging.info("LLM table extraction raw response:\n%s", response)

        # Parse JSON response
        try:
            if response.startswith('{'):
                data = json.loads(response)
            else:
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())
                else:
                    raise ValueError("No valid JSON found")
            
            return {
                "success": True,
                "extracted_parameters": data.get("extracted_parameters", []),
                "raw_response": response
            }
            
        except requests.exceptions.ConnectionError as e:
            raise
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to parse LLM response: {e}",
                "raw_response": response,
                "extracted_parameters": []
            }

    @staticmethod
    def _parameter_dedupe_key(param):
        """
        Build a canonical key for deduping extracted parameters within one
        table-extraction call. Uses ``(tagname, parameter_name,
        parameter_value)`` — case-insensitive and whitespace-stripped — because
        the LLM sometimes shifts row/column indices between retries for the
        *same* logical parameter, and we want to collapse those into a single
        annotation while still allowing genuinely different values for the
        same tagname/parameter to be kept.

        :param param: Extracted parameter dict from the LLM.
        :type param: dict
        :return: Tuple key suitable for use in a set.
        :rtype: tuple[str, str, str]
        """
        return annotation_dedupe_key(
            param.get("tagname"),
            param.get("parameter_name"),
            param.get("parameter_value"),
        )

    @classmethod
    def _dedupe_failed_parameters(cls, failed_parameters):
        """
        Dedupe the failed-parameters set by ``_parameter_dedupe_key`` before it
        is sent back to the LLM. The most recent occurrence wins so retry
        feedback always reflects the latest failure reason.

        :param failed_parameters: List of failed parameter dicts.
        :type failed_parameters: list[dict]
        :return: Deduped list preserving the last occurrence of each key.
        :rtype: list[dict]
        """
        deduped_by_key = {}
        for param in failed_parameters:
            deduped_by_key[cls._parameter_dedupe_key(param)] = param
        return list(deduped_by_key.values())

    def _validate_and_retry_extraction(self, extraction_result, table_context, examples_prompt, max_retries):
        """
        Validate extracted parameters against ACM library and retry with feedback if needed.
        
        :param extraction_result: Initial extraction results
        :type extraction_result: dict
        :param table_context: Original table context
        :type table_context: dict
        :param examples_prompt: Examples prompt for retry attempts
        :type examples_prompt: str
        :param max_retries: Maximum retry attempts
        :type max_retries: int
        :return: Validated and refined extraction results
        :rtype: dict
        """
        if not extraction_result.get("success"):
            return extraction_result
        
        validated_parameters = []
        failed_parameters = []
        retry_count = 0

        # Track (tagname, parameter_name) keys of already-validated parameters so
        # subsequent retry passes cannot re-add the same logical parameter as a
        # duplicate annotation. The LLM's retry response frequently re-emits the
        # entire parameter set (both successful and failed items); without this
        # guard each retry would append the successful ones again.
        seen_validated_keys = set()

        # Initial validation
        for param in extraction_result["extracted_parameters"]:
            validation_result = self._validate_single_parameter(param)

            if validation_result["valid"]:
                key = self._parameter_dedupe_key(param)
                if key in seen_validated_keys:
                    logging.debug(
                        "Skipping duplicate validated parameter on initial pass: %s", key,
                    )
                    continue
                seen_validated_keys.add(key)
                validated_parameters.append({
                    **param,
                    "validation_result": validation_result
                })
            else:
                failed_parameters.append({
                    **param,
                    "validation_result": validation_result
                })

        # Dedupe the failed set by (tagname, parameter_name) so we don't feed
        # the same failure back to the LLM multiple times. Keep the last
        # occurrence (most recent extraction attempt).
        failed_parameters = self._dedupe_failed_parameters(failed_parameters)

        # Retry failed parameters with feedback
        while failed_parameters and retry_count < max_retries:
            retry_count += 1

            retry_result = self._retry_failed_parameters(
                failed_parameters,
                table_context,
                examples_prompt,
                retry_count,
                already_validated=validated_parameters,
            )

            if not retry_result.get("success"):
                logging.warning(
                    "Retry #%s failed with error: %s. Keeping previous failures for next attempt.",
                    retry_count, retry_result.get("error"),
                )
                # Preserve failed_parameters so the next iteration retries again.
                continue

            refined = retry_result.get("refined_parameters") or []
            if not refined:
                logging.warning(
                    "Retry #%s produced no usable refined parameters (schema drift or empty response). "
                    "Retrying with the same failed set.",
                    retry_count,
                )
                # Do NOT clear failed_parameters; loop again with the same set.
                continue

            new_failed = []

            for param in refined:
                key = self._parameter_dedupe_key(param)
                if key in seen_validated_keys:
                    # Retry re-emitted a parameter that has already been
                    # validated in a previous pass. Skip it to prevent
                    # duplicate annotations on the same cell/parameter.
                    logging.info(
                        "Retry #%s re-emitted already-validated parameter %s; skipping duplicate.",
                        retry_count, key,
                    )
                    continue

                validation_result = self._validate_single_parameter(param)

                if validation_result["valid"]:
                    seen_validated_keys.add(key)
                    validated_parameters.append({
                        **param,
                        "validation_result": validation_result,
                        "retry_attempt": retry_count
                    })
                else:
                    new_failed.append({
                        **param,
                        "validation_result": validation_result
                    })

            failed_parameters = self._dedupe_failed_parameters(new_failed)
        
        return {
            "success": True,
            "validated_parameters": validated_parameters,
            "failed_parameters": failed_parameters,
            "total_validation_attempts": retry_count + 1,
            "validation_summary": {
                "total_extracted": len(extraction_result["extracted_parameters"]),
                "successfully_validated": len(validated_parameters),
                "failed_validation": len(failed_parameters),
                "retry_attempts": retry_count
            }
        }

    def _validate_single_parameter(self, param):
        """
        Validate a single parameter against ACM library data.
        
        :param param: Parameter extraction result to validate
        :type param: dict
        :return: Validation result with details
        :rtype: dict
        """
        try:
            tagname = param.get("tagname")
            parameter_name = param.get("parameter_name")
            parameter_value = param.get("parameter_value")
            
            if not tagname or not parameter_name:
                return {
                    "valid": False,
                    "reason": "Missing tagname or parameter name",
                    "tagname_found": False,
                    "parameter_found": False
                }
            
            # Check if tagname exists in ACM
            acm_objects = self.check_acm_for_tagname(tagname)
            if acm_objects.empty:
                return {
                    "valid": False,
                    "reason": f"Tagname '{tagname}' not found in ACM database",
                    "tagname_found": False,
                    "parameter_found": False
                }
            
            # Check parameter exists in object's library
            object_row = acm_objects.iloc[0]
            library_id = object_row['LibraryID']
            
            try:
                
                if library_id not in self.__library_parsers:
                    self.__library_parsers[library_id] = self.__parse_library_file(library_id)
                library_parser = self.__library_parsers[library_id]
                library_parameters = library_parser.get_parameters()
                
                # Check for exact parameter match
                if parameter_name in library_parameters:
                    param_details = library_parameters[parameter_name]
                    
                    # Validate parameter value type and range
                    value_validation = self._validate_parameter_value(
                        parameter_value, param_details
                    )
                    
                    return {
                        "valid": value_validation["valid"],
                        "reason": value_validation.get("reason", "Parameter validated successfully"),
                        "tagname_found": True,
                        "parameter_found": True,
                        "parameter_details": param_details,
                        "value_validation": value_validation
                    }
                else:
                    # Check for similar parameter names
                    similar_params = [p for p in library_parameters.keys() 
                                    if parameter_name.lower() in p.lower() or p.lower() in parameter_name.lower()]
                    
                    return {
                        "valid": False,
                        "reason": f"Parameter '{parameter_name}' not found in library",
                        "tagname_found": True,
                        "parameter_found": False,
                        "suggested_parameters": similar_params[:3]
                    }
                    
            except Exception as e:
                return {
                    "valid": False,
                    "reason": f"Failed to access library for {library_id}: {e}",
                    "tagname_found": True,
                    "parameter_found": False
                }
                
        except Exception as e:
            return {
                "valid": False,
                "reason": f"Validation error: {e}",
                "tagname_found": False,
                "parameter_found": False
            }

    def _validate_parameter_value(self, value, param_details):
        """
        Validate parameter value against its data type and constraints.
        
        :param value: Parameter value to validate
        :type value: str
        :param param_details: Parameter details from library
        :type param_details: dict
        :return: Validation result
        :rtype: dict
        """
        try:
            data_type = param_details.get('DType', '').lower()
            
            if data_type == 'string':
                return {"valid": True, "reason": "String value accepted"}
            
            elif data_type == 'bool':
                bool_values = ['true', 'false', '1', '0', 'yes', 'no', 'on', 'off']
                if value.lower() in bool_values:
                    return {"valid": True, "reason": "Valid boolean value"}
                else:
                    return {"valid": False, "reason": f"Invalid boolean value: {value}"}
            
            elif data_type == 'int':
                try:
                    int_val = int(value)
                    min_val = int(param_details.get('Min', float('-inf')))
                    max_val = int(param_details.get('Max', float('inf')))
                    
                    if min_val <= int_val <= max_val:
                        return {"valid": True, "reason": "Valid integer value within range"}
                    else:
                        return {"valid": False, "reason": f"Integer value {int_val} outside range [{min_val}, {max_val}]"}
                except ValueError:
                    return {"valid": False, "reason": f"Cannot convert '{value}' to integer"}
            
            elif data_type == 'real':
                try:
                    real_val = float(value)
                    min_val = float(param_details.get('Min', float('-inf')))
                    max_val = float(param_details.get('Max', float('inf')))
                    
                    if min_val <= real_val <= max_val:
                        return {"valid": True, "reason": "Valid real value within range"}
                    else:
                        return {"valid": False, "reason": f"Real value {real_val} outside range [{min_val}, {max_val}]"}
                except ValueError:
                    return {"valid": False, "reason": f"Cannot convert '{value}' to real number"}
            
            else:
                return {"valid": True, "reason": f"Unknown data type '{data_type}', accepting value"}
                
        except Exception as e:
            return {"valid": False, "reason": f"Value validation error: {e}"}

    def _retry_failed_parameters(self, failed_parameters, table_context, examples_prompt, attempt_number,
                                 already_validated=None):
        """
        Retry parameter extraction with feedback about previous failures.

        :param failed_parameters: List of parameters that failed validation
        :type failed_parameters: list[dict]
        :param table_context: Original table context
        :type table_context: dict
        :param examples_prompt: Examples prompt
        :type examples_prompt: str
        :param attempt_number: Current retry attempt number
        :type attempt_number: int
        :param already_validated: Parameters already validated in previous passes;
            included in the prompt as a do-not-re-emit list so the model focuses
            purely on the failed items.
        :type already_validated: list[dict] or None
        :return: Refined extraction results
        :rtype: dict
        """
        # Build failure feedback
        failure_feedback = self._build_failure_feedback(failed_parameters)
        already_validated_feedback = self._build_already_validated_feedback(already_validated)

        retry_prompt = text_indent_remove(f"""
        RETRY ATTEMPT #{attempt_number}

        The previous parameter extraction attempt had the following issues:
        {failure_feedback}

        ALREADY VALIDATED (do NOT re-emit these — they are already accepted):
        {already_validated_feedback}

        ORIGINAL EXAMPLES (for reference):
        {examples_prompt}

        CURRENT TABLE TO RE-ANALYZE:
        {table_context.get('full_table', '')}

        RETRY INSTRUCTIONS:
        1. Return ONLY refined entries for the failed parameters listed above.
           Do NOT re-emit any parameter listed under "ALREADY VALIDATED".
           Do NOT invent additional parameter columns beyond the failed set.
        2. Address the specific issues mentioned in the failure feedback.
        3. Re-examine the table structure and column meanings for those failures only.
        4. Use alternative parameter names if exact matches failed.
        5. Consider different interpretation of column headers for the failed cells.
        6. Keep the same single-tagname focus as the initial pass — do not
           introduce a new tagname.

        For failed tagname lookups: Try alternative tagname formats or look for partial matches
        For failed parameter matches: Use synonyms or related parameter names from the library
        For value validation errors: Check data type compatibility and value ranges

        Respond ONLY with JSON in EXACTLY this schema (no prose, no extra keys, DO NOT
        rename fields, DO NOT wrap in additional objects):
        {{
            "extracted_parameters": [
                {{
                    "tagname": "<tagname>",
                    "tagname_row_index": <int>,
                    "tagname_column_index": <int>,
                    "parameter_name": "<parameter name>",
                    "parameter_row_index": <int>,
                    "parameter_column_index": <int>,
                    "parameter_value": "<value from target cell>",
                    "confidence": <float 0.0-1.0>,
                    "extraction_reasoning": "<short reason>"
                }}
            ],
            "retry_reasoning": "<short summary of what changed vs previous attempt>"
        }}
        """)
        
        messages = [
            {"role": "user", "content": retry_prompt}
        ]
        
        try:
            response = self.llm.chat(
                messages=messages,
                temperature=0.2,  # Slightly higher temperature for creative retry
                max_tokens=5000
            )

            logging.info(
                "LLM table extraction retry #%s raw response:\n%s",
                attempt_number, response,
            )

            # Parse JSON response
            if response.startswith('{'):
                data = json.loads(response)
            else:
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())
                else:
                    raise ValueError("No valid JSON found")
            
            return {
                "success": True,
                "refined_parameters": data.get("extracted_parameters", []),
                "retry_reasoning": data.get("retry_reasoning", ""),
                "raw_response": response
            }
        except requests.exceptions.ConnectionError as e:
            raise
        except Exception as e:
            return {
                "success": False,
                "error": f"Retry attempt {attempt_number} failed: {e}",
                "raw_response": response if 'response' in locals() else ""
            }

    def _build_failure_feedback(self, failed_parameters):
        """
        Build detailed feedback about why parameters failed validation.
        
        :param failed_parameters: List of failed parameter extractions
        :type failed_parameters: list[dict]
        :return: Formatted failure feedback
        :rtype: str
        """
        feedback_lines = []
        
        for i, param in enumerate(failed_parameters, 1):
            validation = param.get("validation_result", {})
            
            feedback_lines.append(f"""
            FAILURE {i}:
            - Tagname Location: Row {param.get('tagname_row_index')}, Column {param.get('tagname_column_index')}
            - Attempted Tagname: {param.get('tagname')}
            - Parameter Location: Row {param.get('parameter_row_index')}, Column {param.get('parameter_column_index')}
            - Attempted Parameter: {param.get('parameter_name')}
            - Attempted Value: {param.get('parameter_value')}
            - Failure Reason: {validation.get('reason', 'Unknown')}
            - Tagname Found: {validation.get('tagname_found', False)}
            - Parameter Found: {validation.get('parameter_found', False)}
            """)
            
            if validation.get('suggested_parameters'):
                feedback_lines.append(f"  - Suggested Parameters: {', '.join(validation['suggested_parameters'])}")
        
        return "\n".join(feedback_lines)

    def _build_already_validated_feedback(self, already_validated):
        """
        Build a short "do-not-re-emit" list of parameters that have already
        been successfully validated on previous passes. Included in the retry
        prompt so the LLM stops re-emitting successful parameters (which
        otherwise get re-validated and added as duplicate annotations).

        :param already_validated: List of already-validated parameter dicts.
        :type already_validated: list[dict] or None
        :return: Formatted, indented list of tagname/parameter pairs.
        :rtype: str
        """
        if not already_validated:
            return "  (none — this is the first retry)"

        lines = []
        for param in already_validated:
            lines.append(
                f"  - Tagname: {param.get('tagname')} | Parameter: {param.get('parameter_name')} "
                f"| Value: {param.get('parameter_value')}"
            )
        return "\n".join(lines)

    def _rebuild_linked_texts_from_validated_results(self, validated_result, table_context):
        """
        Rebuild LinkedText objects based on validated extraction results.
        Uses existing examples as a baseline and updates necessary fields.
        
        :param validated_result: Results from validation and retry process
        :type validated_result: dict
        :param table_context: Original table context
        :type table_context: dict
        :return: List of rebuilt LinkedText structures
        :rtype: list[dict[str, LinkedText]]
        """
        rebuilt_linked_texts = []
        
        if not validated_result.get('validated_parameters'):
            return rebuilt_linked_texts
            
        # Use the first example as a baseline template if available
        baseline_example = None
        if self.table_examples:
            baseline_example = self.table_examples[0]

        # Safety-net dedupe. `_validate_and_retry_extraction` already prevents
        # duplicate (tagname, parameter_name) keys from entering
        # ``validated_parameters``, but we defensively dedupe again here (keeping
        # the highest-confidence occurrence) so that a future regression cannot
        # produce duplicate LinkedText annotations for the same cell.
        deduped_params = {}
        for param_data in validated_result['validated_parameters']:
            key = self._parameter_dedupe_key(param_data)
            existing = deduped_params.get(key)
            if existing is None:
                deduped_params[key] = param_data
                continue
            existing_conf = existing.get('confidence') or 0.0
            new_conf = param_data.get('confidence') or 0.0
            if new_conf > existing_conf:
                logging.warning(
                    "Duplicate validated parameter %s reached rebuild; "
                    "replacing lower-confidence entry (%.2f -> %.2f).",
                    key, existing_conf, new_conf,
                )
                deduped_params[key] = param_data
            else:
                logging.warning(
                    "Duplicate validated parameter %s reached rebuild; "
                    "dropping lower-confidence duplicate (%.2f <= %.2f).",
                    key, new_conf, existing_conf,
                )

        for param_data in deduped_params.values():
            # Extract information from validated parameter
            tagname = param_data.get('tagname')
            tagname_row_index = param_data.get('tagname_row_index')
            tagname_column_index = param_data.get('tagname_column_index')
            parameter_name = param_data.get('parameter_name') 
            parameter_value = param_data.get('parameter_value')
            parameter_row_index = param_data.get('parameter_row_index')
            parameter_column_index = param_data.get('parameter_column_index')
            confidence = param_data.get('confidence', 0.8)
            
            # Get parameter details from validation result
            validation_result = param_data.get('validation_result', {})
            parameter_details = validation_result.get('parameter_details', {})
            parameter_data_type = parameter_details.get('DType', 'String')
            
            # Create new linked text structure based on baseline
            new_linked_text = self._create_linked_text_from_baseline(
                baseline_example, 
                tagname, 
                tagname_row_index,
                tagname_column_index,
                parameter_name, 
                parameter_value,
                parameter_data_type,
                parameter_row_index,
                parameter_column_index,
                table_context,
                confidence
            )
            
            if new_linked_text is not None:
                rebuilt_linked_texts.append(new_linked_text)
            
        
        return rebuilt_linked_texts

    def _reconcile_cell_location(self, table_context, row_index, column_index, parameter_value):
        """Return ``(row, col)`` whose cell text matches ``parameter_value``.

        The LLM frequently reports the correct ``parameter_value`` string but an
        off-by-one column (or occasionally an off-by-one row). Trust the value
        string over the reported coordinates: probe the reported cell, then
        scan the same row, then adjacent rows, and return the first cell whose
        stripped text matches. Returns ``None`` when no cell in the vicinity
        matches so callers can drop the annotation instead of pointing at the
        wrong cell.
        """
        def _norm(s):
            return (s or '').strip()

        target = _norm(parameter_value)
        if target == '':
            # Nothing to reconcile against; trust the reported location.
            return row_index, column_index

        if row_index is None or column_index is None:
            return None

        # Fast path: reported cell already matches.
        current = _norm(self._get_text_from_table_context(
            table_context, row_index, column_index))
        if current == target:
            return row_index, column_index

        # Probe the same row across a reasonable column span, then nearby rows.
        MAX_COL_SCAN = 64
        candidate_rows = [row_index]
        for delta in (-1, 1, -2, 2):
            r = row_index + delta
            if r >= 0:
                candidate_rows.append(r)

        for r in candidate_rows:
            trailing_empty = 0
            for c in range(MAX_COL_SCAN):
                text = _norm(self._get_text_from_table_context(table_context, r, c))
                if text == target:
                    return r, c
                if text == '':
                    trailing_empty += 1
                    # Bail once we're clearly past the end of the row.
                    if trailing_empty > 4 and c > column_index:
                        break
                else:
                    trailing_empty = 0

        return None

    @staticmethod
    def _apply_document_locator(linked_text: LinkedText, path, pno, doc_type):
        """Re-point every given_text of a baseline-derived link at the scanned document."""
        if linked_text is None or not linked_text.given_text:
            return
        for given_text in linked_text.given_text.values():
            given_text.path = path
            given_text.pno = pno
            if doc_type is not None:
                given_text.doc_type = doc_type

    def _create_linked_text_from_baseline(self, baseline_example, tagname, tagname_row_index, 
                                        tagname_column_index, parameter_name, parameter_value, 
                                        parameter_data_type, parameter_row_index, parameter_column_index, 
                                        table_context, confidence):
        """
        Create a new LinkedText structure using a baseline example as template.
        
        :param baseline_example: Example LinkedText to use as baseline
        :type baseline_example: dict[str, LinkedText] or None
        :param tagname: Extracted tagname
        :type tagname: str
        :param parameter_name: Parameter name
        :type parameter_name: str
        :param parameter_value: Parameter value
        :type parameter_value: str
        :param parameter_data_type: Parameter data type from ACM library
        :type parameter_data_type: str
        :param row_index: Row position in table
        :type row_index: int
        :param column_index: Column position in table
        :type column_index: int
        :param table_context: Table context information
        :type table_context: dict
        :param confidence: Confidence score
        :type confidence: float
        :return: New LinkedText structure
        :rtype: dict[str, LinkedText]
        """

        # Baselines are project-wide templates, so their locator may point at a
        # different document/page than the one being scanned.
        current_path = table_context.get('path')
        current_pno = table_context.get('pno')
        current_doc_type = table_context.get('doc_type')
        if current_path is None or current_pno is None:
            logging.warning(
                "Rebuilt link skipped: table context has no document locator (path=%s, pno=%s).",
                current_path, current_pno,
            )
            return None

        # Create new LinkedText structure
        new_linked_text = {
            'tagname': LinkedText(),
            'parameters': {parameter_name: LinkedText()},
            'text_relationship': TagnameParameterRelationship.IN_TABLE,
            'is_llm_generated': True,
        }
        
        # Configure tagname LinkedText
        tagname_linked_text: LinkedText = new_linked_text['tagname']
        tagname_linked_text.text_type = TargetTextType.OBJECT

        acm_lookup = self.check_acm_for_tagname(tagname)
        catalog_values = acm_lookup['CatalogNumber'].values if (
            acm_lookup is not None and not acm_lookup.empty and 'CatalogNumber' in acm_lookup.columns
        ) else []
        if len(catalog_values) == 0:
            logging.warning(
                "ACM lookup returned no CatalogNumber for tagname '%s'; skipping rebuilt linked text.",
                tagname,
            )
            return None

        # The document spells the tag differently to ACM (TI-2007 vs TI2007) and every downstream
        # consumer matches on the ACM object name, so carry that rather than the raw document text.
        name_values = acm_lookup['Name'].values if 'Name' in acm_lookup.columns else []
        acm_tagname = str(name_values[0]) if len(name_values) else tagname
        tagname_linked_text.text = acm_tagname
        tagname_linked_text.linked = True
        tagname_linked_text.object_type = catalog_values[0]

        
        # Copy additional fields from baseline
        baseline_tagname = baseline_example['tagname']
        baseline_tagname_given_values = list(baseline_tagname.given_text.values()) if baseline_tagname.given_text else []
        if not baseline_tagname_given_values:
            logging.warning(
                "Baseline tagname '%s' has no given_text entries; skipping rebuilt linked text.",
                getattr(baseline_tagname, 'text', ''),
            )
            return None
        baseline_given_text = baseline_tagname_given_values[0]

        # Same LLM off-by-one column drift affects the tagname coordinates;
        # reconcile against the tagname string so the tagname highlight lands
        # on the real Tag cell (fixes the "Baseline tagname does not match /
        # To be implemented" fallback silently producing indexless highlights).
        tagname_reconciled = self._reconcile_cell_location(
            table_context, tagname_row_index, tagname_column_index, tagname,
        )
        if tagname_reconciled is None:
            logging.warning(
                "Rebuilt link skipped: tagname '%s' not found near row=%s col=%s.",
                tagname, tagname_row_index, tagname_column_index,
            )
            return None
        if (tagname_reconciled[0], tagname_reconciled[1]) != (tagname_row_index, tagname_column_index):
            logging.info(
                "Reconciled tagname '%s' from row=%s col=%s to row=%s col=%s.",
                tagname,
                tagname_row_index, tagname_column_index,
                tagname_reconciled[0], tagname_reconciled[1],
            )
        tagname_row_index, tagname_column_index = tagname_reconciled

        if baseline_tagname.text == acm_tagname and baseline_given_text.roi == [tagname_row_index, tagname_column_index]:

            tagname_linked_text.given_text = copy.deepcopy(baseline_tagname.given_text)
            tagname_linked_text.links = copy.deepcopy(baseline_tagname.links)
            self._apply_document_locator(tagname_linked_text, current_path, current_pno, current_doc_type)

        else:
            tagname_cell_text = self._get_text_from_table_context(
                table_context, tagname_row_index, tagname_column_index,
            )
            tagname_cell_indexes = self._get_indexes_from_table_context(
                table_context, tagname_row_index, tagname_column_index,
            )
            if not tagname_cell_text or tagname_cell_indexes is None:
                logging.warning(
                    "Rebuilt link skipped: tagname '%s' has no resolvable cell at row=%s col=%s.",
                    tagname, tagname_row_index, tagname_column_index,
                )
                return None

            tagname_given_text = GivenTextLink()
            tagname_given_text.linked = True
            tagname_given_text.text = tagname_cell_text
            tagname_given_text.roi = [tagname_row_index, tagname_column_index]
            tagname_given_text.in_table = True
            tagname_given_text.table_shape = table_context.get('table_shape', (0, 0))
            tagname_given_text.table_bbox = table_context.get('table_bbox', [0, 0, 0, 0])
            tagname_given_text.indexes = tagname_cell_indexes
            tagname_given_text.path = current_path
            tagname_given_text.pno = current_pno
            tagname_given_text.doc_type = current_doc_type if current_doc_type is not None else baseline_given_text.doc_type
            tagname_given_text.axis = baseline_given_text.axis
            tagname_given_text.text_format = baseline_given_text.text_format

            tagname_linked_text.given_text = {str(uuid.uuid4()): tagname_given_text}

     
        baseline_param_values = list(baseline_example['parameters'].values()) if baseline_example.get('parameters') else []
        if not baseline_param_values:
            logging.warning(
                "Baseline example has no parameters; skipping rebuilt linked text for tagname '%s'.",
                tagname,
            )
            return None
        baseline_param = baseline_param_values[0]

        # Trust the LLM's parameter_value string over its reported row/column;
        # scan the table for the cell whose text actually matches so the
        # annotation lands on the correct cell (fixes wrong-column previews).
        reconciled = self._reconcile_cell_location(
            table_context, parameter_row_index, parameter_column_index, parameter_value,
        )
        if reconciled is None:
            logging.warning(
                "Rebuilt link skipped: parameter '%s'='%s' for tagname '%s' does not match "
                "any cell near row=%s col=%s.",
                parameter_name, parameter_value, tagname,
                parameter_row_index, parameter_column_index,
            )
            return None
        if (reconciled[0], reconciled[1]) != (parameter_row_index, parameter_column_index):
            logging.info(
                "Reconciled parameter '%s'='%s' from row=%s col=%s to row=%s col=%s.",
                parameter_name, parameter_value,
                parameter_row_index, parameter_column_index,
                reconciled[0], reconciled[1],
            )
        parameter_row_index, parameter_column_index = reconciled

        # Copy additional fields from baseline parameter
        if self._map_acm_type_to_target_type(parameter_data_type) == baseline_param.text_type:
            

            link_data = {
                'text': self._get_text_from_table_context(table_context, parameter_row_index, parameter_column_index),
                'indexes': self._get_indexes_from_table_context(table_context, parameter_row_index, parameter_column_index)

            }
            new_linked_text['parameters'][parameter_name] = self.__build_new_table_link(baseline_param
                                                                                        , link_data
                                                                                        , [parameter_row_index, parameter_column_index]
                                                                                        , parameter_name)
            self._apply_document_locator(new_linked_text['parameters'][parameter_name],
                                         current_path, current_pno, current_doc_type)
            if (new_linked_text['parameters'][parameter_name] is not None
                    and new_linked_text['parameters'][parameter_name].text == parameter_value):
                return new_linked_text
            # If the table-link build failed or didn't match, fall through and rebuild manually
            if new_linked_text['parameters'][parameter_name] is None:
                new_linked_text['parameters'][parameter_name] = LinkedText()



        # Configure parameter LinkedText
        parameter_linked_text = new_linked_text['parameters'][parameter_name]
        parameter_linked_text.text = parameter_value
        parameter_linked_text.text_type = self._map_acm_type_to_target_type(parameter_data_type)
        parameter_linked_text.linked = True
        parameter_linked_text.object_type = tagname_linked_text.object_type

        cell_text = self._get_text_from_table_context(
            table_context, parameter_row_index, parameter_column_index
        )
        cell_indexes = self._get_indexes_from_table_context(
            table_context, parameter_row_index, parameter_column_index
        )
        if not cell_text or cell_indexes is None:
            logging.warning(
                "Rebuilt link skipped: parameter '%s' for tagname '%s' has no resolvable cell at row=%s col=%s.",
                parameter_name, tagname, parameter_row_index, parameter_column_index,
            )
            return None

        # Create GivenTextLink for parameter value
        parameter_given_text = GivenTextLink()
        parameter_given_text.linked = True
        parameter_given_text.text = cell_text
        parameter_given_text.roi = [parameter_row_index, parameter_column_index]
        parameter_given_text.in_table = True
        parameter_given_text.table_shape = table_context.get('table_shape', (0, 0))
        parameter_given_text.table_bbox = table_context.get('table_bbox', [0, 0, 0, 0])

        baseline_param_given_values = list(baseline_param.given_text.values()) if baseline_param.given_text else []
        if not baseline_param_given_values:
            logging.warning(
                "Baseline parameter has no given_text entries; skipping rebuilt linked text for parameter '%s'.",
                parameter_name,
            )
            return None
        baseline_param_given_text = baseline_param_given_values[0]
        parameter_given_text.path = current_path
        parameter_given_text.pno = current_pno
        parameter_given_text.doc_type = current_doc_type if current_doc_type is not None else baseline_param_given_text.doc_type
        parameter_given_text.axis = baseline_param_given_text.axis
        parameter_given_text.text_format = baseline_param_given_text.text_format
        parameter_given_text.indexes = cell_indexes
    
        parameter_linked_text.given_text = {str(uuid.uuid4()): parameter_given_text}
        
        return new_linked_text
    

    def __build_new_table_link(self, linked_text:LinkedText, found_cell_text, roi,  parameter=None):


        character_differences = []

        try:
            new_linked_text = self.__build_linked_table_text_string(found_cell_text
                                                            , linked_text
                                                            , roi
                                                            , character_differences)
        except Exception as error:
            logging.debug("Error rebuilding linked text: %s", error)
            return None
        #if parameter:
        #    new_linked_text = self.__subobject_reftype_parameter_value_correction(new_linked_text,parameter)


        new_linked_text = self.__correct_link_text_indexes(
                                                        character_differences, 
                                                        new_linked_text
                                                        )

        return new_linked_text
    

    def __correct_link_text_indexes(self, character_differences, linked_text:LinkedText):
        corrected_indexes_links = {}
        if linked_text.links is None:
            return linked_text
        
        for indexes_id, link in linked_text.links.items():
    
            indexes = list(link.target_text_indexes)
            for character_difference in character_differences:
                if indexes[1] >= character_difference['index']:
                    indexes[0] = indexes[0] + character_difference['difference']
                    if indexes[0] <= 0:
                        indexes[0] = 0
                    indexes[1] = indexes[1] + character_difference['difference']

            key = "{start}-{end}".format(start=indexes[0],end=indexes[1])
            link.target_text_indexes = (indexes[0],indexes[1])
            corrected_indexes_links[indexes_id] = key

        for indexes_id, key in corrected_indexes_links.items():
            linked_text.links[key] = linked_text.links.pop(indexes_id)

        return linked_text
    

    def __build_linked_table_text_string(self, found_cell_texts, linked_text:LinkedText,roi , character_differences):

        new_linked_text = copy.deepcopy(linked_text)
        
        for indexes_id, link in new_linked_text.links.items():
                
            given_text = linked_text.given_text[link.given_text_id]
            group = self.__get_regex_group(given_text.text,given_text.regex_string, link.given_text_indexes)
            if group is None:
                raise ValueError('Group not found in regex string')
            
            match = safe_regex.search(given_text.regex_string,found_cell_texts['text'])
            if match is None:
                raise ValueError('Group not found in regex string')
            sub_string = str(match.group(group))
            new_linked_text.given_text[link.given_text_id].key_and_ignore_indexes.remove(link.given_text_indexes)
            match_start = match.span(group)[0] - match.span(0)[0]
            new_linked_text.links[indexes_id].given_text_indexes = [match_start,match_start+len(sub_string)]
            new_linked_text.given_text[link.given_text_id].key_and_ignore_indexes.append(link.given_text_indexes)



            try:
                target_text_indexes = linked_text.links[indexes_id].target_text_indexes
                new_linked_text.text = self.__replacer(new_linked_text.text
                                            ,sub_string
                                            ,list(target_text_indexes)
                                            ,character_differences=character_differences)

                data = {
                    'index':target_text_indexes[1],
                    'difference':len(sub_string)-(target_text_indexes[1] - target_text_indexes[0])
                }
                character_differences.append(data)

                new_linked_text.given_text[link.given_text_id].text = found_cell_texts['text']
                new_linked_text.given_text[link.given_text_id].indexes = found_cell_texts['indexes']
                new_linked_text.given_text[link.given_text_id].roi = roi
               
                
            except Exception as error:
                continue


        return new_linked_text
    

    def __replacer(self, s, newstring, indexes, nofail=False, character_differences=None):

        for character_difference in character_differences:
            if indexes[1] >= character_difference['index']:
                indexes[0] = indexes[0] + character_difference['difference']
                indexes[1] = indexes[1] + character_difference['difference']

        # raise an error if index is outside of the string
        if not nofail and indexes[0] not in range(len(s)):
            raise ValueError("index outside given string")
        
        # if not erroring, but the index is still not in the correct range..
        if indexes[0] < 0:  # add it to the beginning
            return newstring + s
        if indexes[0] > len(s):  # add it to the end
            return s + newstring
        if len(s[:indexes[0]]) + len(newstring) >= len(s):
            return s[:indexes[0]] + newstring

        # insert the new string between "slices" of the original
        return s[:indexes[0]] + newstring + s[indexes[1]:]
    
    
    def __get_regex_group(self, original_string, regex_pattern, char_indexes):
        match = safe_regex.search(regex_pattern, original_string)
        
        if not match:
            return None
        
        if char_indexes[0] < 0 or char_indexes[0] >= len(original_string):
            return None
        
        # Check each group (including group 0, which is the entire match)
        for group_num in range(1, len(match.groups()) + 1):
            if char_indexes[0] in range(match.start(group_num), match.end(group_num)):
                return group_num
        
        return None
    

    def _find_tagname_column_index(self, table_context, tagname, row_index):
        """
        Find the column index where the tagname appears in the table.
        
        :param table_context: Table context information
        :type table_context: dict
        :param tagname: Tagname to find
        :type tagname: str
        :param row_index: Row where tagname should be found
        :type row_index: int
        :return: Column index or 0 if not found
        :rtype: int
        """
        # Simple search in table context - this could be enhanced with actual table parsing
        full_table = table_context.get('full_table', '')
        table_lines = full_table.split('\n')
        
        if row_index < len(table_lines):
            row_text = table_lines[row_index]
            # Look for tagname in row and estimate column index
            if tagname in row_text:
                # Simple estimation based on character position
                char_position = row_text.find(tagname)
                # Estimate column based on typical cell width
                estimated_column = char_position // 15  # Rough estimate
                return max(0, estimated_column)
        
        return 0  # Default to first column

    def _infer_object_type_from_tagname(self, tagname):
        """
        Infer object type from tagname using common industrial automation patterns.
        
        :param tagname: Tagname to analyze
        :type tagname: str
        :return: Inferred object type
        :rtype: str
        """
        tagname_upper = tagname.upper()
        
        # Common patterns for industrial automation
        if re.match(r'[A-Z]*T[I|C].*', tagname_upper):
            return 'Temperature Controller'
        elif re.match(r'[A-Z]*P[I|C].*', tagname_upper):
            return 'Pressure Controller'  
        elif re.match(r'[A-Z]*F[I|C].*', tagname_upper):
            return 'Flow Controller'
        elif re.match(r'[A-Z]*L[I|C].*', tagname_upper):
            return 'Level Controller'
        elif re.match(r'[A-Z]*[X|H]V.*', tagname_upper):
            return 'Valve'
        elif re.match(r'[A-Z]*[M|P].*', tagname_upper):
            return 'Motor/Pump'
        else:
            return 'Generic Object'

    def _map_acm_type_to_target_type(self, acm_data_type):
        """
        Map ACM library data type to TargetTextType.
        
        :param acm_data_type: ACM data type string
        :type acm_data_type: str
        :return: Mapped TargetTextType
        :rtype: TargetTextType
        """
        acm_type_lower = acm_data_type.lower()
        
        if acm_type_lower == 'real':
            return TargetTextType.REAL
        elif acm_type_lower == 'int' or acm_type_lower == 'integer':
            return TargetTextType.INT
        elif acm_type_lower == 'string':
            return TargetTextType.STRING
        else:
            return TargetTextType.STRING  # Default fallback

    def check_acm_for_tagname(self, tagname, source_text=None):
        """
        Check ACM data handler for tagname details if available
        
        :param tagname: Tagname to look up
        :type tagname: str
        :param source_text: Document text the tagname was extracted from, used to resolve a
            bracketed ACM object reference when the tagname itself names no object
        :type source_text: str or None
        :return: ACM data details or empty DataFrame
        :rtype: DataFrame
        """
        return lookup_acm_object(self.acm_data_handler, tagname, source_text)

    def __parse_library_file(self, library_id):
        """
        Parse ACM library file to get parameter information.
        
        :param library_id: Library ID to parse
        :type library_id: str
        :return: Library parser instance
        :rtype: acm_library_parser
        """
        library_file_path = get_library_file_path(library_id, self.project_name)
        if not library_file_path:
            projects_df = self.acm_data_handler.get_all_projects()
            acm_project_name = projects_df.loc[int(self.acm_data_handler.get_project_id())]['Name']
            acm_libraries_retrieval(self.project_name, acm_project_name, threaded=False)
            library_file_path = get_library_file_path(library_id, self.project_name)
            if not library_file_path:
                raise Exception(f"Unable to access parameters for library {library_id}.")
        return acm_library_parser(library_file_path)

    def _get_text_from_table_context(self, table_context, row_index, column_index):
        """
        Extract text from a specific cell in the table context.
        
        :param table_context: Table context containing the full_table string
        :type table_context: dict
        :param row_index: Row index (0-based)
        :type row_index: int
        :param column_index: Column index (0-based)  
        :type column_index: int
        :return: Text content of the specified cell
        :rtype: str
        """
        row_index = row_index + 1 # Compensate for row and column indexing
        column_index = column_index + 1 # Compensate for row and column indexing
        try:
            full_table = table_context.get('full_table', '')
            if not full_table:
                return ""
            
            # Split table into lines
            table_lines = full_table.split('\n')
            
            # Check if row_index is valid
            if row_index >= len(table_lines):
                return ""
            
            # Get the row and split by pipe delimiter
            row_text = table_lines[row_index]
            cells = [cell.strip() for cell in row_text.split('|')]
            
            # Remove empty cells from start/end (pipe-delimited tables often have empty first/last)
            while cells and cells[0] == '':
                cells.pop(0)
            while cells and cells[-1] == '':
                cells.pop()
            
            # Check if column_index is valid
            if column_index >= len(cells):
                return ""
                
            return cells[column_index]
            
        except Exception as e:
            return ""

    def _get_indexes_from_table_context(self, table_context, row_index, column_index):
        """
        Get text character indexes for a specific cell in the table context.
        
        :param table_context: Table context containing the full_table string
        :type table_context: dict
        :param row_index: Row index (0-based)
        :type row_index: int
        :param column_index: Column index (0-based)
        :type column_index: int
        :return: start and end character indexes of the cell text
        :rtype: dict
        """
        table = table_context.get('table_object', None)
        text_on_page = table_context.get('text_on_page', [])


        if table is None:            
            return None

        # Validate indices against the actual table shape so an out-of-range
        # LLM prediction does not raise IndexError.
        rows = getattr(table, 'rows', None) or []
        if row_index is None or column_index is None or row_index < 0 or row_index >= len(rows):
            return None
        cells = getattr(rows[row_index], 'cells', None) or []
        if column_index < 0 or column_index >= len(cells):
            return None

        cell_text_info = get_text_in_bbox(table, row_index, column_index, text_on_page)

        indexes = cell_text_info['indexes']
        # get_text_in_bbox seeds start=inf, end=0; if nothing landed inside
        # the cell those sentinels remain, meaning no text was found.
        if indexes[0] == np.inf or indexes[1] <= indexes[0]:
            return None

        return indexes
    

    
    




def demo_classifier():
    """
    Demonstrate the IndustrialAutomationClassifier capabilities
    """
    print("\n" + "=" * 60)
    print("Industrial Automation Text Classifier Demo")
    print("=" * 60)

    from bin.logic_llm_inference import UnifiedInference

    try:
        llm = UnifiedInference(provider="openai", model_name="gpt-4.1-mini")
        # Initialize classifier with OpenAI (you can also use "ollama")
        classifier = TextDocumentLLMPreprocessor(llm)
        
        # Test examples including table and list contexts with extraction examples
        test_cases = [
            # General context examples
            {
                "highlighted_text": "Temperature setpoint TIC-101: 85.5°C, Range: 70-100°C",
                "context": {
                    "full_sentence": "Reactor R-101 control parameters: Temperature setpoint TIC-101: 85.5°C, Range: 70-100°C"
                },
                "context_type": "general"
            },
            {
                "highlighted_text": "Start pump P-101 when valve V-205 is fully open",
                "context": {
                    "full_sentence": "Safety interlock conditions for reactor startup: Start pump P-101 when valve V-205 is fully open"
                },
                "context_type": "general"
            },
            {
                "highlighted_text": "Step 3: Open valve XV-101, wait 30 seconds, then start pump P-102",
                "context": {
                    "full_sentence": "Batch reactor startup procedure: Step 3: Open valve XV-101, wait 30 seconds, then start pump P-102"
                },
                "context_type": "general"
            },
            
            # Table context examples with tagnames
            {
                "highlighted_text": "85",
                "context": {
                    "full_table": "|Tag|Setpoint|Unit|Range|\n|TIC-101|85|°C|70-100|",
                    "row": "1"
                },
                "context_type": "table"
            },
            {
                "highlighted_text": "Stop motor M-205 if pressure > 100 PSI",
                "context": {
                    "full_table": "|Equipment|Interlock|Action|\n|Motor-M205|Stop motor M-205 if pressure > 100 PSI|Emergency stop|",
                    "full_row": "1"
                },
                "context_type": "table"
            },
            {
                "highlighted_text": "Heat mixture",
                "context": {
                    "full_table": "|Step|Action|Duration|\n|3|Heat mixture|30 min|",
                    "full_row": "1"
                },
                "context_type": "table"
            },
            
            # List context examples
            {
                "highlighted_text": "TIC-301 High: 95°C, Low: 65°C",
                "context": {
                    "list_heading": "Alarm Limits Configuration"
                },
                "context_type": "list"
            },
            {
                "highlighted_text": "Close valve XV-205 when emergency stop activated",
                "context": {
                    "list_heading": "Safety Interlocks"
                },
                "context_type": "list"
            },
            {
                "highlighted_text": "Open inlet valve HV-101",
                "context": {
                    "list_heading": "Startup Sequence Steps"
                },
                "context_type": "list"
            },
            
            # Unknown example
            {
                "highlighted_text": "The weather forecast shows rain tomorrow",
                "context": {
                    "full_sentence": "Daily operations meeting notes: The weather forecast shows rain tomorrow"
                },
                "context_type": "general"
            }
        ]
        
        print(f"\nClassifying {len(test_cases)} test cases...\n")
        
        # Classify individual items with extraction
        results = []
        for i, case in enumerate(test_cases, 1):
            print(f"Test Case {i} ({case['context_type'].upper()}):")
            print(f"  Text: '{case['highlighted_text']}'")
            print(f"  Context: {case['context']}")
            
            # Use the combined classify_and_extract method
            combined_result = classifier.classify_and_extract(
                case["highlighted_text"], 
                case["context"], 
                case["context_type"]
            )
            results.append(combined_result["classification"])
            
            # Display classification results
            classification = combined_result["classification"]
            print(f"  Classification: {classification['category'].upper()}")
            print(f"  Classification Confidence: {classification['confidence']:.2f}")
            
            # Display tagname extraction results
            tagname_extraction = combined_result["tagname_extraction"]
            if tagname_extraction and tagname_extraction["objects"]:
                print(f"  Extracted Tagname: {tagname_extraction['objects']} (confidence: {tagname_extraction['confidence']:.2f})")
            else:
                print(f"  Extracted Tagname: None")
            
            # Display interlock extraction results (only for interlocks)
            if classification['category'] == classifier.INTERLOCK:
                interlock_extraction = combined_result["interlock_extraction"]
                if interlock_extraction and interlock_extraction["interlock_objects"]:
                    print(f"  Interlock Objects: {interlock_extraction['interlock_objects']} (confidence: {interlock_extraction['confidence']:.2f})")
                else:
                    print(f"  Interlock Objects: None identified")
            
            if "error" in classification:
                print(f"  Error: {classification['error']}")
            
            print()
        
        # Demonstrate individual extraction methods
        print("\n" + "-" * 60)
        print("EXTRACTION DEMOS")
        print("-" * 60)
        
        print("\n1. Tagname Extraction Demo:")
        print("-" * 30)
        
        tagname_examples = [
            "Temperature controller TIC-101 setpoint: 85°C",
            "Pump P-205 motor status",
            "Valve XV-301 position feedback",
            "Flow indicator FIT-105 reading"
        ]
        
        for text in tagname_examples:
            result = classifier.extract_tagname(text)
            print(f"Text: '{text}'")
            print(f"  → Tagname: {result['objects']} (confidence: {result['confidence']:.2f})")
        
        print("\n2. Interlock Object Extraction Demo:")
        print("-" * 30)
        
        interlock_examples = [
            "Start pump P-101 when tank level > 50%",
            "Close valve XV-205 if pressure exceeds 100 PSI", 
            "Stop reactor R-301 heating if temperature > 200°C",
            "Emergency shutdown: stop all motors and close all valves"
        ]
        
        for text in interlock_examples:
            result = classifier.extract_interlock_objects(text)
            print(f"Text: '{text}'")
            if result['interlock_objects']:
                objects = ", ".join(result['interlock_objects'])
                print(f"  → Objects: {objects} (confidence: {result['confidence']:.2f})")
            else:
                print(f"  → Objects: None identified")
        
        # Show batch classification
        print("\n" + "-" * 40)
        print("Batch Classification Demo:")
        print("-" * 40)
        
        batch_items = [
            {"text": "PID_Output range: 0-100%", "context": "Controller configuration"},
            {"text": "IF Emergency_Stop THEN Stop_All_Motors", "context": "Safety system"},
            {"text": "Phase 2: Heat to 150°C while stirring", "context": "Batch recipe"}
        ]
        
        batch_results = classifier.classify_batch(batch_items)
        
        for i, result in enumerate(batch_results, 1):
            print(f"Batch Item {i}: {result['category'].upper()} (confidence: {result['confidence']:.2f})")
        
        # Generate summary
        print("\n" + "-" * 40)
        print("Classification Summary:")
        print("-" * 40)
        
        all_results = results + batch_results
        summary = classifier.get_classification_summary(all_results)
        
        print(f"Total items classified: {summary['total']}")
        print(f"Success rate: {summary['success_rate']}%")
        print(f"Average confidence: {summary['average_confidence']:.3f}")
        print("\nCategory breakdown:")
        for category, count in summary['categories'].items():
            percentage = (count / summary['total'] * 100) if summary['total'] > 0 else 0
            print(f"  {category.replace('_', ' ').title()}: {count} ({percentage:.1f}%)")
        
        if summary['error_count'] > 0:
            print(f"\nErrors encountered: {summary['error_count']}")
            
    except Exception as e:
        print(f"Demo error: {e}")


if __name__ == "__main__":
    demo_classifier()
