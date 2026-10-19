"""
Ollama LLM Agent for extracting industrial automation object parameters from text.

This module provides functionality to:
1. Identify parameter text spans from large bodies of text
2. Extract tagnames, parameters, and values from identified spans
3. Process multiple parameters sequentially with given hints
"""

import logging
import re
import json
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum
import csv
from io import StringIO

try:
    import ollama
except ImportError:
    logging.warning("Ollama not available. Install with: pip install ollama")
    ollama = None


ParameterExtractorConfig = None
load_config = None


class ParameterType(str, Enum):
    """Types of parameters that can be extracted."""
    ANALOG_INPUT = "analog_input"
    DIGITAL_INPUT = "digital_input"
    ANALOG_OUTPUT = "analog_output"
    DIGITAL_OUTPUT = "digital_output"
    CONTROL_LOOP = "control_loop"
    ALARM = "alarm"
    CONFIGURATION = "configuration"
    GENERAL = "general"


class StructuredTextType(str, Enum):
    """Types of structured text that can contain parameters."""
    PLAIN_TEXT = "plain_text"
    TABLE = "table"
    LIST = "list"
    NESTED_LIST = "nested_list"
    KEY_VALUE_PAIRS = "key_value_pairs"


@dataclass
class ParameterHint:
    """Represents a parameter hint with optional description."""
    name: str
    description: Optional[str] = None
    expected_units: Optional[str] = None
    parameter_type: Optional[ParameterType] = None
    
    def to_prompt_string(self) -> str:
        """Convert to string format for LLM prompts."""
        result = self.name
        if self.description:
            result += f" ({self.description})"
        if self.expected_units:
            result += f" [units: {self.expected_units}]"
        return result
    
    @classmethod
    def from_string(cls, hint_str: str) -> 'ParameterHint':
        """Create ParameterHint from string (for backward compatibility)."""
        return cls(name=hint_str)
    
    @classmethod
    def from_dict(cls, hint_dict: Dict[str, Any]) -> 'ParameterHint':
        """Create ParameterHint from dictionary."""
        return cls(
            name=hint_dict.get('name', ''),
            description=hint_dict.get('description'),
            expected_units=hint_dict.get('expected_units'),
            parameter_type=ParameterType(hint_dict['parameter_type']) if hint_dict.get('parameter_type') else None
        )


@dataclass
class ExtractedParameter:
    """Represents an extracted parameter with its metadata."""
    tagname: str
    parameter_name: str
    parameter_value: str
    parameter_type: Optional[ParameterType] = None
    confidence: float = 0.0
    source_text: str = ""
    text_span: Tuple[int, int] = (0, 0)
    structure_type: StructuredTextType = StructuredTextType.PLAIN_TEXT
    table_position: Optional[Tuple[int, int]] = None  # (row, column) for table data
    list_index: Optional[int] = None  # Position in list
    related_headers: List[str] = None  # Table headers or list context
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return asdict(self)


@dataclass
class ParameterExtractionResult:
    """Results from parameter extraction process."""
    extracted_parameters: List[ExtractedParameter]
    identified_spans: List[Tuple[int, int, str]]
    processing_errors: List[str]
    total_text_length: int
    processing_time: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        result = asdict(self)
        result['extracted_parameters'] = [param.to_dict() for param in self.extracted_parameters]
        return result


class OllamaParameterExtractor:
    """
    Ollama-based LLM agent for extracting industrial automation parameters from text.
    
    This class provides a two-stage approach:
    1. Text Classification: Identify spans that likely contain parameter information
    2. Parameter Extraction: Extract specific tagnames, parameters, and values
    """
    
    def __init__(self, 
                 model_name: str = "qwen3:4b",
                 ollama_host: str = "http://localhost:11434",
                 temperature: float = 0.1,
                 timeout: int = 60,
                 config_path: Optional[str] = None):
        """
        Initialize the parameter extractor.
        
        Args:
            model_name: Name of the Ollama model to use
            ollama_host: Ollama server host URL
            temperature: Sampling temperature (lower = more deterministic)
            timeout: Request timeout in seconds
            config_path: Path to configuration file (optional)
        """
        # Load configuration
        if ParameterExtractorConfig and load_config:
            self.config = load_config(config_path)
            # Override with provided parameters
            if model_name != "llama3.1:8b":
                self.config.model.name = model_name
            if ollama_host != "http://localhost:11434":
                self.config.model.host = ollama_host
            if temperature != 0.1:
                self.config.model.temperature = temperature
            if timeout != 60:
                self.config.model.timeout = timeout
        else:
            # Fallback to manual configuration if config module not available
            self.config = None
            
        self.model_name = model_name if not self.config else self.config.model.name
        self.ollama_host = ollama_host if not self.config else self.config.model.host
        self.temperature = temperature if not self.config else self.config.model.temperature
        self.timeout = timeout if not self.config else self.config.model.timeout
        self.logger = logging.getLogger(__name__)
        
        # Industrial automation parameter patterns
        if self.config:
            self.parameter_patterns = self.config.parameter_patterns
            self.tagname_patterns = self.config.tagname_patterns
            self.units_patterns = self.config.units_patterns
        else:
            # Fallback patterns if no config
            self.parameter_patterns = {
                'limits': ['limit', 'hi', 'lo', 'high', 'low', 'max', 'min', 'range'],
                'alarms': ['alarm', 'alert', 'warning', 'trip', 'fault'],
                'configuration': ['config', 'cfg', 'setting', 'setup', 'mode'],
                'scaling': ['scale', 'span', 'zero', 'full', 'engineering'],
                'timing': ['time', 'delay', 'duration', 'interval', 'period'],
                'control': ['setpoint', 'sp', 'output', 'bias', 'gain', 'integral', 'derivative']
            }
            
            # Common tagname patterns for industrial automation
            self.tagname_patterns = [
                r'\b[A-Z]{2,4}\d{3,5}\b',  # e.g., LIT1005, FIT2001, TIC3004
                r'\b[A-Z]+_[A-Z0-9_]+\b',  # e.g., TANK_LEVEL_01
                r'\b[A-Z]{1,3}-\d{2,4}[A-Z]?\b',  # e.g., P-101A, T-201
            ]
            
            self.units_patterns = [
                r'%', r'°[CF]|deg[CF]?|degrees?', r'PSI|psi|bar|Pa|kPa|MPa',
                r'GPM|gpm|LPM|lpm|m³/h|L/s', r'ft|in|mm|cm|m',
                r'V|mV|A|mA', r'Hz|RPM|rpm', r's|sec|min|hr|hours?'
            ]
        
        self._validate_setup()
    
    def _validate_setup(self) -> None:
        """Validate that Ollama is available and configured."""
        if ollama is None:
            raise ImportError("Ollama library not available. Install with: pip install ollama")
        
        try:
            # Test connection to Ollama
            ollama.list()
            self.logger.info(f"Successfully connected to Ollama at {self.ollama_host}")
        except Exception as e:
            self.logger.warning(f"Could not connect to Ollama: {e}")
    
    def identify_parameter_spans(self, text: str) -> List[Tuple[int, int, str]]:
        """
        Identify text spans that likely contain parameter information.
        Handles plain text, tables, and lists.
        
        Args:
            text: Input text to analyze
            
        Returns:
            List of tuples (start_index, end_index, span_text)
        """
        spans = []
        
        # First, identify structured content (tables and lists)
        table_spans = self._identify_table_spans(text)
        list_spans = self._identify_list_spans(text)
        
        # Add structured spans
        spans.extend(table_spans)
        spans.extend(list_spans)
        
        # Process remaining text as sentences, avoiding already identified structured content
        structured_ranges = [(start, end) for start, end, _ in spans]
        
        sentences = re.split(r'[.!?]\s+', text)
        current_pos = 0
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
                
            # Find sentence position in original text
            start_idx = text.find(sentence, current_pos)
            end_idx = start_idx + len(sentence)
            
            # Skip if this sentence is already covered by structured content
            if any(self._ranges_overlap((start_idx, end_idx), struct_range) 
                   for struct_range in structured_ranges):
                current_pos = end_idx
                continue
            
            # Check if sentence contains parameter-like content
            if self._is_parameter_sentence(sentence):
                spans.append((start_idx, end_idx, sentence))
            
            current_pos = end_idx
        
        # Sort spans by start position
        spans.sort(key=lambda x: x[0])
        return spans
    
    def _is_parameter_sentence(self, sentence: str) -> bool:
        """
        Determine if a sentence likely contains parameter information using LLM.
        
        Args:
            sentence: Sentence to analyze
            
        Returns:
            True if sentence likely contains parameters
        """
        # Quick rule-based filter for obvious non-parameter content
        if len(sentence.strip()) < 10 or not any(c.isdigit() for c in sentence):
            return False
        
        
        try:
            prompt = f"""
You are an expert in industrial automation and control systems.
Analyze the following sentence and determine if it contains industrial parameter information.

Sentence: "{sentence}"

Look for:
- Instrument tagnames (like LIT1005, TIC3004, FIT2001)
- Parameter names (like setpoint, alarm, limit, configuration values)
- Numeric values with units (percentages, temperatures, pressures, etc.)
- Control system terminology

Respond with only "YES" if the sentence contains parameter information, or "NO" if it doesn't.

Examples:
- "The high high limit of Water Tank Level (LIT1005) should be 90%" → YES
- "Temperature controller TIC3004 setpoint is 150°C" → YES
- "This section describes the general plant operations" → NO
- "Safety procedures must be followed at all times" → NO

Response:"""
            
            response = ollama.chat(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                options={
                    "temperature": 0.1,
                    "timeout": 10  # Short timeout for classification
                },
                think=False
            )
            
            result = response['message']['content'].strip().upper()
            return result.startswith('YES')
            
        except Exception as e:
            self.logger.warning(f"LLM classification failed, falling back to rules: {e}")
        
    
    
    
    def _identify_table_spans(self, text: str) -> List[Tuple[int, int, str]]:
        """
        Identify table-like structures in text.
        
        Args:
            text: Input text to analyze
            
        Returns:
            List of table spans
        """
        table_spans = []
        
        # Pattern 1: Pipe-separated tables (|column1|column2|column3|)
        pipe_table_pattern = r'(?:^|\n)((?:\s*\|[^\n]*\|\s*\n?){2,})'
        pipe_matches = re.finditer(pipe_table_pattern, text, re.MULTILINE)
        
        for match in pipe_matches:
            table_text = match.group(1).strip()
            if self._is_parameter_table(table_text):
                start_idx = match.start(1)
                end_idx = match.end(1)
                table_spans.append((start_idx, end_idx, table_text))
        
        # Pattern 2: Tab-separated or multiple-space separated tables
        # Look for multiple lines with consistent column structure
        lines = text.split('\n')
        potential_table_start = None
        potential_table_lines = []
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                if potential_table_lines and len(potential_table_lines) >= 2:
                    # End of potential table
                    table_text = '\n'.join(potential_table_lines)
                    if self._is_parameter_table(table_text):
                        # Calculate position in original text
                        table_start = text.find(potential_table_lines[0])
                        table_end = table_start + len(table_text)
                        table_spans.append((table_start, table_end, table_text))
                
                potential_table_start = None
                potential_table_lines = []
                continue
            
            # Check if line looks like a table row
            if self._is_table_row(line):
                if potential_table_start is None:
                    potential_table_start = i
                potential_table_lines.append(line)
            else:
                if potential_table_lines and len(potential_table_lines) >= 2:
                    # End of potential table
                    table_text = '\n'.join(potential_table_lines)
                    if self._is_parameter_table(table_text):
                        table_start = text.find(potential_table_lines[0])
                        table_end = table_start + len(table_text)
                        table_spans.append((table_start, table_end, table_text))
                
                potential_table_start = None
                potential_table_lines = []
        
        return table_spans
    
    def _identify_table_headers(self, table_text: str) -> Tuple[List[int], List[str]]:
        """
        Use LLM to identify which lines in a table are headers and extract header text.
        
        Args:
            table_text: Table text to analyze
            
        Returns:
            Tuple of (header_line_indices, header_texts)
        """
        try:
            prompt = f"""
            You are an expert in industrial automation and control systems.
            Analyze the following TABLE and identify which lines contain column headers.

            Table:
            {table_text}

            Look for:
            - Lines that contain column names like "Tagname", "Parameter", "Value", "Units", "Description"
            - Lines that describe what each column contains
            - Lines that are typically at the top or after separator lines
            - Industrial automation terminology in header positions

            Respond in JSON format with this structure:
            {{
                "header_lines": [0, 1],
                "headers": ["Tagname", "Parameter", "Value", "Units"]
            }}

            Where:
            - header_lines: Array of line numbers (0-based) that contain headers
            - headers: Array of actual header text extracted from those lines

            If no clear headers are found, return {{"header_lines": [], "headers": []}}.

            Response:"""
            
            response = ollama.chat(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                options={
                    "temperature": 0.1,
                    "timeout": 20  # Longer timeout for table header analysis
                },
                think=False
            )
            
            # Parse JSON response
            result_text = response['message']['content'].strip()
            if result_text.startswith('{'):
                data = json.loads(result_text)
            else:
                # Try to extract JSON from response
                json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())
                else:
                    raise ValueError("No valid JSON found")
            
            header_lines = data.get('header_lines', [])
            headers = data.get('headers', [])
            
            return header_lines, headers
            
        except Exception as e:
            self.logger.warning(f"LLM header identification failed, falling back to rules: {e}")
    
    

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
    
    def _is_parameter_table(self, table_text: str) -> bool:
        """
        Determine if table contains parameter information using LLM.
        
        Args:
            table_text: Table text to analyze
            
        Returns:
            True if table likely contains parameters
        """
        # Quick rule-based filter for obviously empty or malformed tables
        if len(table_text.strip()) < 20 or table_text.count('|') < 2:
            return False
        
        # Use LLM for intelligent table classification
        if ollama:
            try:
                prompt = f"""
You are an expert in industrial automation and control systems.
Analyze the following TABLE and determine if it contains industrial parameter information.

Table:
{table_text}

Look for:
- Instrument tagnames (like LIT1005, TIC3004, FIT2001) in columns or rows
- Parameter names in headers or cells (like CfgHi, CfgLo, Setpoint, Alarm)
- Configuration values with units (percentages, temperatures, pressures)
- Control system parameter data organized in tabular format

Respond with only "YES" if the table contains parameter information, or "NO" if it doesn't.

Examples:
- A table with columns like "Tagname | Parameter | Value | Units" → YES
- A table listing alarm limits for different instruments → YES
- A table with general project information or schedules → NO
- A table with personnel names and contact information → NO

Response:"""
                
                response = ollama.chat(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    options={
                        "temperature": 0.1,
                        "timeout": 15  # Slightly longer for table analysis
                    },think=False
                )
                
                result = response['message']['content'].strip().upper()
                return result.startswith('YES')
                
            except Exception as e:
                self.logger.warning(f"LLM table classification failed, falling back to rules: {e}")
        
        # Fallback to rule-based method if LLM fails
        return self._fallback_is_parameter_table(table_text)
    
    def _fallback_is_parameter_table(self, table_text: str) -> bool:
        """
        Fallback rule-based parameter table detection.
        
        Args:
            table_text: Table text to analyze
            
        Returns:
            True if table likely contains parameters
        """
        # Check for tagname patterns
        has_tagnames = any(re.search(pattern, table_text) 
                          for pattern in self.tagname_patterns)
        
        # Check for parameter keywords
        table_lower = table_text.lower()
        has_param_keywords = any(
            keyword in table_lower
            for category in self.parameter_patterns.values()
            for keyword in category
        )
        
        # Check for values with units
        units_pattern = '|'.join(self.units_patterns) if hasattr(self, 'units_patterns') else r'%|\w+'
        has_values = bool(re.search(rf'\d+(?:\.\d+)?\s*(?:{units_pattern})', table_text))
        
        return (has_tagnames and has_values) or (has_param_keywords and has_values)
    
    def _is_table_row(self, line: str) -> bool:
        """
        Determine if a line looks like a table row.
        
        Args:
            line: Line to analyze
            
        Returns:
            True if line looks like table data
        """
        # Check for multiple columns separated by tabs, multiple spaces, or pipes
        separators = [r'\t', r'\s{2,}', r'\|']
        
        for sep_pattern in separators:
            parts = re.split(sep_pattern, line.strip())
            if len(parts) >= 2:  # At least 2 columns
                return True
        
        return False
    
    def _is_parameter_list(self, list_text: str) -> bool:
        """
        Determine if list contains parameter information using LLM.
        
        Args:
            list_text: List text to analyze
            
        Returns:
            True if list likely contains parameters
        """
        # Quick rule-based filter for obviously empty or short lists
        if len(list_text.strip()) < 15 or list_text.count('\n') < 1:
            return False
        
        # Use LLM for intelligent list classification

        try:
            prompt = f"""
You are an expert in industrial automation and control systems.
Analyze the following LIST and determine if it contains industrial parameter information.

List:
{list_text}

Look for:
- Instrument tagnames (like LIT1005, TIC3004, FIT2001) in list items
- Parameter names (like CfgHi, CfgLo, Setpoint, Alarm, Configuration)
- Values with units (percentages, temperatures, pressures) associated with parameters
- Control system configuration items or alarm settings
- Key-value pairs with industrial automation data

Respond with only "YES" if the list contains parameter information, or "NO" if it doesn't.

Examples:
- "- LIT1005 High Alarm: 85%" → YES
- "- Temperature setpoint: 150°C" → YES
- "- CfgHiHi: 95%" → YES
- "- Review safety procedures" → NO
- "- Contact maintenance team" → NO
- "- Schedule next meeting" → NO

Response:"""
            
            response = ollama.chat(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                options={
                    "temperature": 0.1,
                    "timeout": 12  # Medium timeout for list analysis
                }, think=False
            )
            
            result = response['message']['content'].strip().upper()
            return result.startswith('YES')
            
        except Exception as e:
            self.logger.warning(f"LLM list classification failed, falling back to rules: {e}")

            return False
        

    
    def _ranges_overlap(self, range1: Tuple[int, int], range2: Tuple[int, int]) -> bool:
        """
        Check if two ranges overlap.
        
        Args:
            range1: First range (start, end)
            range2: Second range (start, end)
            
        Returns:
            True if ranges overlap
        """
        return range1[0] < range2[1] and range2[0] < range1[1]
    
    def extract_parameters_from_span(self, 
                                   text_span: str,
                                   parameter_hints: List[str],
                                   span_indices: Tuple[int, int] = (0, 0)) -> List[ExtractedParameter]:
        """
        Extract parameters from a single text span using LLM, processing each line individually.
        
        Args:
            text_span: Text span to process
            parameter_hints: List of expected parameter names
            span_indices: Start and end indices of span in original text
            
        Returns:
            List of extracted parameters
        """
        if not ollama:
            self.logger.error("Ollama not available")
            return []
        
        try:
            # Determine structure type
            structure_type = self._determine_structure_type(text_span)
            
            # Process line by line based on structure type
            if structure_type == StructuredTextType.TABLE:
                return self._extract_from_table_line_by_line(text_span, parameter_hints, span_indices)
            elif structure_type in [StructuredTextType.LIST, StructuredTextType.NESTED_LIST, StructuredTextType.KEY_VALUE_PAIRS]:
                return self._extract_from_list_line_by_line(text_span, parameter_hints, span_indices)
            else:
                return self._extract_from_text_line_by_line(text_span, parameter_hints, span_indices)
            
        except Exception as e:
            self.logger.error(f"Error extracting parameters: {e}")
            return []
        
    
    def _extract_from_table_line_by_line(self, table_text: str, parameter_hints: List[str], span_indices: Tuple[int, int]) -> List[ExtractedParameter]:
        """
        Extract parameters from table by processing each data row individually with header context.
        
        Args:
            table_text: Table text to process
            parameter_hints: Expected parameter names
            span_indices: Span location
            
        Returns:
            List of extracted parameters
        """
        extracted_params = []
        
        try:
            # Identify headers first
            header_lines, headers = self._identify_table_headers(table_text)
            
            # Parse table structure
            rows = [row.strip() for row in table_text.split('\n') if row.strip()]

            # Create header context for this row
            header_context = '\n'.join(rows[header_lines[0]:header_lines[-1]+1]) if header_lines else rows[0]
                
            # Process each data row (non-header rows)
            for row_idx, row_text in enumerate(rows):
                if row_idx in header_lines:
                    continue  # Skip header rows
                
                # Create focused prompt for this single row
                prompt = self._create_single_row_prompt(header_context, row_text, parameter_hints)
                
                # Extract from this single row
                try:
                    response = ollama.chat(
                        model=self.model_name,
                        messages=[{"role": "user", "content": prompt}],
                        options={
                            "temperature": self.temperature,
                            "timeout": 15  # Shorter timeout for single row
                        },
                        think=False
                    )

                    print(response['message']['content'])
                    
                    # Parse response for this row
                    row_params = self._parse_single_line_response(
                        response['message']['content'],
                        row_text,
                        span_indices,
                        StructuredTextType.TABLE,
                        row_idx,
                        headers
                    )
                    extracted_params.extend(row_params)
                    
                except Exception as e:
                    self.logger.warning(f"Error processing table row {row_idx}: {e}")
                    continue
        
        except Exception as e:
            self.logger.error(f"Error in line-by-line table extraction: {e}")
        
        return extracted_params
    
    def _extract_from_list_line_by_line(self, list_text: str, parameter_hints: List[str], span_indices: Tuple[int, int]) -> List[ExtractedParameter]:
        """
        Extract parameters from list by processing each item individually.
        
        Args:
            list_text: List text to process
            parameter_hints: Expected parameter names
            span_indices: Span location
            
        Returns:
            List of extracted parameters
        """
        extracted_params = []
        
        try:
            # Split into individual list items
            lines = [line.strip() for line in list_text.split('\n') if line.strip()]
            
            # Identify list context/headers if any
            list_context = self._identify_list_context(list_text)
            
            for item_idx, line in enumerate(lines):
                # Clean up list markers
                clean_line = re.sub(r'^\s*[-*•]\s+', '', line)
                clean_line = re.sub(r'^\s*(?:\d+\.|\w\))\s+', '', clean_line)
                
                if not clean_line.strip():
                    continue
                
                # Create focused prompt for this single list item
                prompt = self._create_single_list_item_prompt(list_context, clean_line, parameter_hints)
                
                # Extract from this single item
                try:
                    response = ollama.chat(
                        model=self.model_name,
                        messages=[{"role": "user", "content": prompt}],
                        options={
                            "temperature": self.temperature,
                            "timeout": 12  # Shorter timeout for single item
                        },
                        think=False
                    )
                    
                    # Parse response for this item
                    item_params = self._parse_single_line_response(
                        response['message']['content'],
                        clean_line,
                        span_indices,
                        StructuredTextType.LIST,
                        item_idx,
                        list_context
                    )
                    extracted_params.extend(item_params)
                    
                except Exception as e:
                    self.logger.warning(f"Error processing list item {item_idx}: {e}")
                    continue
        
        except Exception as e:
            self.logger.error(f"Error in line-by-line list extraction: {e}")
        
        return extracted_params
    
    def _extract_from_text_line_by_line(self, text: str, parameter_hints: List[str], span_indices: Tuple[int, int]) -> List[ExtractedParameter]:
        """
        Extract parameters from plain text by processing each sentence individually.
        
        Args:
            text: Text to process
            parameter_hints: Expected parameter names
            span_indices: Span location
            
        Returns:
            List of extracted parameters
        """
        extracted_params = []
        
        try:
            # Split into sentences
            sentences = re.split(r'[.!?]\s+', text)
            
            for sent_idx, sentence in enumerate(sentences):
                sentence = sentence.strip()
                if not sentence or len(sentence) < 10:
                    continue
                
                # Create focused prompt for this single sentence
                prompt = self._create_single_sentence_prompt(sentence, parameter_hints)
                
                # Extract from this single sentence
                try:
                    response = ollama.chat(
                        model=self.model_name,
                        messages=[{"role": "user", "content": prompt}],
                        options={
                            "temperature": self.temperature,
                            "timeout": 10  # Short timeout for single sentence
                        },
                        think=False
                    )
                    
                    # Parse response for this sentence
                    sent_params = self._parse_single_line_response(
                        response['message']['content'],
                        sentence,
                        span_indices,
                        StructuredTextType.PLAIN_TEXT,
                        sent_idx,
                        []
                    )
                    extracted_params.extend(sent_params)
                    
                except Exception as e:
                    self.logger.warning(f"Error processing sentence {sent_idx}: {e}")
                    continue
        
        except Exception as e:
            self.logger.error(f"Error in line-by-line text extraction: {e}")
        
        return extracted_params
    
    def _determine_structure_type(self, text_span: str) -> StructuredTextType:
        """
        Determine the structure type of the text span.
        
        Args:
            text_span: Text to analyze
            
        Returns:
            Structure type
        """
        # Check for table patterns
        if '|' in text_span and text_span.count('|') >= 4:
            return StructuredTextType.TABLE
        
        # Check for consistent column structure
        lines = text_span.split('\n')
        if len(lines) >= 2:
            tab_separated = all('\t' in line for line in lines if line.strip())
            multi_space_separated = all(re.search(r'\s{2,}', line) for line in lines if line.strip())
            
            if tab_separated or multi_space_separated:
                return StructuredTextType.TABLE
        
        # Check for list patterns
        if re.search(r'^\s*[-*•]\s+', text_span, re.MULTILINE):
            return StructuredTextType.LIST
        
        if re.search(r'^\s*(?:\d+\.|[a-z]\)|[A-Z]\))\s+', text_span, re.MULTILINE):
            return StructuredTextType.LIST
        
        # Check for key-value pairs
        kv_lines = [line for line in lines if ':' in line and line.strip()]
        if len(kv_lines) >= 2 and len(kv_lines) / len([l for l in lines if l.strip()]) > 0.5:
            return StructuredTextType.KEY_VALUE_PAIRS
        
        return StructuredTextType.PLAIN_TEXT
    
    def _create_header_context(self, headers: List[str], row_data: List[str]) -> str:
        """
        Create header context string for table row processing.
        
        Args:
            headers: List of column headers
            row_data: Data values for this row
            
        Returns:
            Formatted header context string
        """
        if not headers:
            return "No headers identified"
        
        context_pairs = []
        for i, header in enumerate(headers):
            if i < len(row_data):
                context_pairs.append(f"{header}: {row_data[i]}")
            else:
                context_pairs.append(f"{header}: [empty]")
        
        return " | ".join(context_pairs)
    
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
    
    def _create_single_row_prompt(self, header_context: str, row_text: str, parameter_hints: List[str]) -> str:
        """
        Create focused prompt for single table row extraction.
        
        Args:
            header_context: Header context for this row
            row_text: Single row text
            parameter_hints: Expected parameter names
            
        Returns:
            Formatted prompt string
        """
        parameter_hints_text = ""
        parameter_hints_example = ""
        for parameter_hint, description in parameter_hints.items():
            parameter_hints_text = parameter_hints_text + f" - {parameter_hint}: ({description[0]}) {description[1]} e.g. {description[2]}\n"
            parameter_hints_example = f" (e.g. {description[2]})"
        hints_str = parameter_hints_text if parameter_hints_text else "any relevant parameters"
        
        prompt = f"""
You are an expert in industrial automation. Extract parameter information from this SINGLE TABLE ROW with the table header.

{header_context}
{row_text}

The Parameters to extract:
{hints_str}

Extract:
1. Tagname (instrument identifier like LIT1005, TIC3004)
2. Parameter name (from hints or context)
3. Parameter value{parameter_hints_example}
4. Column heading (from table header)

Respond in JSON format:
{{
    "extractions": [
        {{
            "tagname": "extracted_tagname",
            "parameter_name": "parameter_name",
            "parameter_value": "value",
            "column_heading": "column_heading"
        }}
    ]
}}

If no parameters found, return {{"extractions": []}}.
Response:"""
        return prompt
    
    def _create_single_list_item_prompt(self, list_context: List[str], item_text: str, parameter_hints: List[str]) -> str:
        """
        Create focused prompt for single list item extraction.
        
        Args:
            list_context: Context about the list structure
            item_text: Single list item text
            parameter_hints: Expected parameter names
            
        Returns:
            Formatted prompt string
        """
        hints_str = ", ".join(parameter_hints) if parameter_hints else "any relevant parameters"
        context_str = ", ".join(list_context)
        
        prompt = f"""
You are an expert in industrial automation. Extract parameter information from this SINGLE LIST ITEM.

List Context: {context_str}
Item: {item_text}

Parameter hints: {hints_str}

Extract:
1. Tagname (instrument identifier like LIT1005, TIC3004)
2. Parameter name (from hints or context)
3. Parameter value

Respond in JSON format:
{{
    "extractions": [
        {{
            "tagname": "extracted_tagname",
            "parameter_name": "parameter_name",
            "parameter_value": "value",
            "confidence": 0.95
        }}
    ]
}}

If no parameters found, return {{"extractions": []}}.
Response:"""
        return prompt
    
    def _create_single_sentence_prompt(self, sentence: str, parameter_hints: List[str]) -> str:
        """
        Create focused prompt for single sentence extraction.
        
        Args:
            sentence: Single sentence text
            parameter_hints: Expected parameter names
            
        Returns:
            Formatted prompt string
        """
        hints_str = ", ".join(parameter_hints) if parameter_hints else "any relevant parameters"
        
        prompt = f"""
You are an expert in industrial automation. Extract parameter information from this SINGLE SENTENCE.

Sentence: {sentence}

Parameter hints: {hints_str}

Extract:
1. Tagname (instrument identifier like LIT1005, TIC3004)
2. Parameter name (from hints or sentence context)
3. Parameter value 

Respond in JSON format:
{{
    "extractions": [
        {{
            "tagname": "extracted_tagname",
            "parameter_name": "parameter_name",
            "parameter_value": "value",
            "confidence": 0.95
        }}
    ]
}}

If no parameters found, return {{"extractions": []}}.
Response:"""
        return prompt
    
    def _parse_single_line_response(self, 
                                  response: str, 
                                  source_text: str,
                                  span_indices: Tuple[int, int],
                                  structure_type: StructuredTextType,
                                  line_index: int,
                                  headers: List[str]) -> List[ExtractedParameter]:
        """
        Parse LLM response for single line extraction.
        
        Args:
            response: Raw LLM response
            source_text: Original source text
            span_indices: Span location
            structure_type: Type of structure
            line_index: Index of this line/row/item
            headers: Headers or context information
            
        Returns:
            List of extracted parameters
        """
        extracted_params = []
        
        try:
            # Try to parse JSON response
            if response.strip().startswith('{'):
                data = self._llm_safe_json_parse(response)
            else:
                # Try to extract JSON from response
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())
                else:
                    return []  # No valid JSON found
            
            # Extract parameters from JSON
            extractions = data.get('extractions', [])
            
            for extraction in extractions:
                param = ExtractedParameter(
                    tagname=extraction.get('tagname', '').strip(),
                    parameter_name=extraction.get('parameter_name', '').strip(),
                    parameter_value=extraction.get('parameter_value', '').strip(),
                    confidence=float(extraction.get('confidence', 0.9)),  # Higher default for focused extraction
                    source_text=source_text,
                    text_span=span_indices,
                    structure_type=structure_type,
                    table_position=(line_index, 0) if structure_type == StructuredTextType.TABLE else None,
                    list_index=line_index if structure_type == StructuredTextType.LIST else None,
                    related_headers=headers if headers else None
                )
                
                # Validate extraction
                if param.tagname and param.parameter_name and param.parameter_value:
                    extracted_params.append(param)
                    
        except json.JSONDecodeError as e:
            self.logger.warning(f"JSON parsing error for line {line_index}: {e}")
        except Exception as e:
            self.logger.error(f"Error parsing single line response: {e}")
        
        return extracted_params
    
    def _llm_safe_json_parse(self, response: str) -> dict:
        """
        Safely parse JSON from LLM response, handling common formatting issues.
        
        Args:
            response: Raw LLM response

        Returns:
            Parsed JSON dictionary
        """
        try:
            if response.strip().startswith('{'):
                return json.loads(response)
            else:
                # Try to extract JSON from response
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
                else:
                    raise ValueError("No valid JSON found in response")
        except json.JSONDecodeError as e:
            prompt = f"""Please correct the following JSON so it can be parsed. Output only the corrected JSON.
            
            Original response:
            {response}
            """
            response = ollama.chat(
                        model=self.model_name,
                        messages=[{"role": "user", "content": prompt}],
                        options={
                            "temperature": self.temperature,
                            "timeout": 12  # Shorter timeout for single item
                        },
                        think=False
                    )
            try:
                return json.loads(response['message']['content'])
            except json.JSONDecodeError as e:
                self.logger.error(f"Error parsing JSON: {e}")
                raise
        except Exception as e:
            self.logger.error(f"Error parsing JSON: {e}")
            raise
    
    def _create_extraction_prompt(self, text_span: str, parameter_hints: List[str]) -> str:
        """
        Create a prompt for parameter extraction.
        
        Args:
            text_span: Text to analyze
            parameter_hints: Expected parameter names
            
        Returns:
            Formatted prompt string
        """
        hints_str = ", ".join(parameter_hints) if parameter_hints else "any relevant parameters"
        
        prompt = f"""
You are an expert in industrial automation and control systems. 
Extract parameter information from the following text.

Text to analyze: "{text_span}"

Parameter hints (look for these specific parameters): {hints_str}

Please extract:
1. Tagname (instrument/object identifier like LIT1005, FIT2001, etc.)
2. Parameter name (from hints or similar)
3. Parameter value (number with or without units)

Respond in JSON format with this structure:
{{
    "extractions": [
        {{
            "tagname": "extracted_tagname",
            "parameter_name": "parameter_from_hints",
            "parameter_value": "extracted_value",
            "confidence": 0.95
        }}
    ]
}}

If no clear parameters are found, return {{"extractions": []}}.
Only extract information that is clearly stated in the text.
"""
        return prompt
    
    def _create_table_extraction_prompt(self, table_text: str, parameter_hints: List[str]) -> str:
        """
        Create a prompt for extracting parameters from table data with header awareness.
        
        Args:
            table_text: Table text to analyze
            parameter_hints: Expected parameter names
            
        Returns:
            Formatted prompt string
        """
        hints_str = ", ".join(parameter_hints) if parameter_hints else "any relevant parameters"
        
        # First identify headers using LLM
        header_lines, headers = self._identify_table_headers(table_text)
        header_info = f"Identified headers: {headers}" if headers else "No clear headers identified"
        
        prompt = f"""
You are an expert in industrial automation and control systems.
Extract parameter information from the following TABLE data.

Table to analyze:
{table_text}

{header_info}

Parameter hints (look for these specific parameters): {hints_str}

For TABLE data, please extract:
1. Tagname (instrument/object identifier like LIT1005, FIT2001, etc.)
2. Parameter name (from hints, column headers, or similar)
3. Parameter value (number with or without units)
4. Table position (row and column numbers, starting from 0 for data rows only)
5. Related headers (column headers or row labels)

Important:
- Ignore header rows when counting row positions
- Focus on data rows that contain actual parameter values
- Use the identified headers to understand column meanings

Respond in JSON format with this structure:
{{
    "extractions": [
        {{
            "tagname": "extracted_tagname",
            "parameter_name": "parameter_from_hints_or_headers",
            "parameter_value": "extracted_value",
            "confidence": 0.95,
            "table_position": {{"row": 1, "column": 2}},
            "related_headers": ["column_header", "row_label"]
        }}
    ]
}}

If no clear parameters are found, return {{"extractions": []}}.
Only extract information that is clearly stated in the table data rows.
"""
        return prompt
    
    def _create_list_extraction_prompt(self, list_text: str, parameter_hints: List[str]) -> str:
        """
        Create a prompt for extracting parameters from list data.
        
        Args:
            list_text: List text to analyze
            parameter_hints: Expected parameter names
            
        Returns:
            Formatted prompt string
        """
        hints_str = ", ".join(parameter_hints) if parameter_hints else "any relevant parameters"
        
        prompt = f"""
You are an expert in industrial automation and control systems.
Extract parameter information from the following LIST data.

List to analyze:
{list_text}

Parameter hints (look for these specific parameters): {hints_str}

For LIST data, please extract:
1. Tagname (instrument/object identifier like LIT1005, FIT2001, etc.)
2. Parameter name (from hints or list context)
3. Parameter value (number with or without units)
4. List position (item number, starting from 0)
5. Context (surrounding list items or headers)

Respond in JSON format with this structure:
{{
    "extractions": [
        {{
            "tagname": "extracted_tagname",
            "parameter_name": "parameter_from_hints",
            "parameter_value": "extracted_value",
            "confidence": 0.95,
            "list_index": 2,
            "related_headers": ["list_context", "section_header"]
        }}
    ]
}}

If no clear parameters are found, return {{"extractions": []}}.
Only extract information that is clearly stated in the list.
"""
        return prompt
    
    def _parse_extraction_response(self, 
                                 response: str, 
                                 source_text: str,
                                 span_indices: Tuple[int, int],
                                 structure_type: StructuredTextType = StructuredTextType.PLAIN_TEXT) -> List[ExtractedParameter]:
        """
        Parse LLM response into ExtractedParameter objects.
        
        Args:
            response: Raw LLM response
            source_text: Original source text
            span_indices: Span location in original text
            
        Returns:
            List of extracted parameters
        """
        extracted_params = []
        
        try:
            # Try to parse JSON response
            if response.strip().startswith('{'):
                data = json.loads(response)
            else:
                # Try to extract JSON from response
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())
                else:
                    self.logger.warning(f"Could not parse JSON from response: {response}")
                    return []
            
            # Extract parameters from JSON
            extractions = data.get('extractions', [])
            
            for extraction in extractions:
                # Extract table/list specific information
                table_pos = extraction.get('table_position')
                table_position = None
                if table_pos and isinstance(table_pos, dict):
                    table_position = (table_pos.get('row', 0), table_pos.get('column', 0))
                
                list_index = extraction.get('list_index')
                related_headers = extraction.get('related_headers', [])
                
                param = ExtractedParameter(
                    tagname=extraction.get('tagname', '').strip(),
                    parameter_name=extraction.get('parameter_name', '').strip(),
                    parameter_value=extraction.get('parameter_value', '').strip(),
                    confidence=float(extraction.get('confidence', 0.0)),
                    source_text=source_text,
                    text_span=span_indices,
                    structure_type=structure_type,
                    table_position=table_position,
                    list_index=list_index,
                    related_headers=related_headers if related_headers else None
                )
                
                # Validate extraction
                if param.tagname and param.parameter_name and param.parameter_value:
                    extracted_params.append(param)
                    
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON parsing error: {e}")
        except Exception as e:
            self.logger.error(f"Error parsing extraction response: {e}")
        
        return extracted_params


 
    
    def process_text(self, 
                    text: str, 
                    parameter_hints: Union[List[str], List[ParameterHint], List[Dict[str, Any]]] = None) -> ParameterExtractionResult:
        """
        Process a large body of text to extract all parameters.
        
        Args:
            text: Input text to process
            parameter_hints: List of expected parameter names, ParameterHint objects, or dictionaries
            
        Returns:
            Complete extraction results
        """
        import time
        start_time = time.time()
        
        if parameter_hints is None:
            parameter_hints = {}
        
        
        # Step 1: Identify parameter spans
        self.logger.info("Identifying parameter spans...")
        identified_spans = self.identify_parameter_spans(text)
        self.logger.info(f"Found {len(identified_spans)} potential parameter spans")
        
        # Step 2: Extract parameters from each span
        all_extracted_parameters = []
        processing_errors = []
        
        for i, (start_idx, end_idx, span_text) in enumerate(identified_spans):
            self.logger.info(f"Processing span {i+1}/{len(identified_spans)} (line-by-line extraction)")
            
            try:
                extracted_params = self.extract_parameters_from_span(
                    span_text, 
                    parameter_hints,
                    (start_idx, end_idx)
                )
                all_extracted_parameters.extend(extracted_params)
                self.logger.info(f"Extracted {len(extracted_params)} parameters from span {i+1}")
                
            except Exception as e:
                error_msg = f"Error processing span {i+1}: {e}"
                self.logger.error(error_msg)
                processing_errors.append(error_msg)
        
        processing_time = time.time() - start_time
        
        # Create result object
        result = ParameterExtractionResult(
            extracted_parameters=all_extracted_parameters,
            identified_spans=identified_spans,
            processing_errors=processing_errors,
            total_text_length=len(text),
            processing_time=processing_time
        )
        
        self.logger.info(f"Extraction complete. Found {len(all_extracted_parameters)} parameters in {processing_time:.2f}s")
        
        return result
    
    
    def get_supported_models(self) -> List[str]:
        """
        Get list of available Ollama models.
        
        Returns:
            List of model names
        """
        if not ollama:
            return []
        
        try:
            models = ollama.list()
            return [model['name'] for model in models.get('models', [])]
        except Exception as e:
            self.logger.error(f"Error getting models: {e}")
            return []
    
    def get_parameter_suggestions(self, category: Optional[str] = None) -> List[str]:
        """
        Get parameter suggestions based on configuration.
        
        Args:
            category: Specific category to get suggestions for
            
        Returns:
            List of parameter suggestions
        """
        suggestions = []
        
        if self.config and hasattr(self.config, 'standard_parameters'):
            suggestions.extend(self.config.standard_parameters.keys())
        
        if category and self.parameter_patterns and category in self.parameter_patterns:
            suggestions.extend(self.parameter_patterns[category])
        elif not category and self.parameter_patterns:
            for category_params in self.parameter_patterns.values():
                suggestions.extend(category_params)
        
        return list(set(suggestions))  # Remove duplicates
    
    def get_parameter_description(self, parameter_name: str) -> Optional[str]:
        """
        Get description for a parameter name.
        
        Args:
            parameter_name: Name of the parameter
            
        Returns:
            Description string or None
        """
        if (self.config and 
            hasattr(self.config, 'standard_parameters') and 
            parameter_name in self.config.standard_parameters):
            return self.config.standard_parameters[parameter_name]
        return None
    
    def set_model(self, model_name: str) -> bool:
        """
        Change the active model.
        
        Args:
            model_name: Name of model to use
            
        Returns:
            True if model was set successfully
        """
        try:
            # Test the model
            test_response = ollama.chat(
                model=model_name,
                messages=[{"role": "user", "content": "test"}],
                options={"timeout": 10},
                think=False
            )
            
            self.model_name = model_name
            self.logger.info(f"Successfully set model to {model_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error setting model {model_name}: {e}")
            return False

