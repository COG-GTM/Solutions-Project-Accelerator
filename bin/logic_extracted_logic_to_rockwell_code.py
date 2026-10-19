"""
Module for converting logic expressions to Rockwell Automation ladder logic code.

This module provides functionality to parse logical expressions (with AND/OR operators
and comparison operators) and convert them to Rockwell Automation instruction format
using Named Interface Bindings (NIBs).
"""


class LogicToRockwellConverter:
    """
    Converts logic expressions to Rockwell Automation ladder logic code.
    
    Supports:
    - Boolean logic: AND (sequential), OR (bracketed)
    - Comparison operators: <, >, <=, >=, =, != (for non-boolean types)
    - Rockwell instructions: XIC (for booleans), GRT, LES, GEQ, LEQ, EQU, NEQ
    
    For boolean NIBs (nib_data_type == 'Bool'), always generates XIC instruction
    regardless of the operator used in the logic expression, assuming "true" value.
    """
    
    def __init__(self):
        """Initialize the converter."""
        pass
    
    def convert_logic_expression_to_rockwell_code(self, logic_expression, nib_info):
        """
        Convert a logic expression to Rockwell Automation ladder logic code.
        
        :param logic_expression: The logic expression to convert
        :type logic_expression: str
        :param nib_info: Dictionary mapping tagnames to their NIB information
        :type nib_info: dict
        :return: Rockwell Automation ladder logic code
        :rtype: str
        
        Example:
            Input:
                logic_expression: "((TIC-401.value < 200) AND (FIT-205.value > 10)) OR (FIT-205 < HiHi)"
                nib_info: {
                    "TIC-401": {"nib_name": "Val", "nib_data_type": "Real"},
                    "FIT-205": {"nib_name": "Val", "nib_data_type": "Real"}
                }
            Output:
                "[LES(TIC-401.Val,200)GRT(FIT-205.Val,10)]XIC(FIT-205.sts_HiHi)"
        """
        try:
            # Parse the logic expression into tokens
            tokens = self._tokenize_logic_expression(logic_expression)
            
            # Convert tokens to Rockwell code
            rockwell_code = self._convert_tokens_to_rockwell(tokens, nib_info)
            
            return rockwell_code
            
        except Exception as e:
            print(f"Error converting logic expression to Rockwell code: {str(e)}")
            return ""
    
    def _tokenize_logic_expression(self, expression):
        """
        Tokenize a logic expression into components.
        
        :param expression: Logic expression string
        :type expression: str
        :return: List of tokens
        :rtype: list
        """
        tokens = []
        current_token = ""
        i = 0
        
        while i < len(expression):
            char = expression[i]
            
            if char == '(':
                if current_token.strip() and current_token.strip() not in ['AND', 'OR']:
                    tokens.append({'type': 'paren', 'value': '('})
                elif not current_token.strip():
                    tokens.append({'type': 'paren', 'value': '('})
                else:
                    current_token += char
                current_token = ""
            elif char == ')':
                if current_token.strip():
                    self._add_condition_token(current_token.strip(), tokens)
                    current_token = ""
                tokens.append({'type': 'paren', 'value': ')'})
            elif char == ' ':
                if current_token.strip():
                    # Check if this is AND or OR
                    if current_token.strip() == 'AND':
                        tokens.append({'type': 'operator', 'value': 'AND'})
                        current_token = ""
                    elif current_token.strip() == 'OR':
                        tokens.append({'type': 'operator', 'value': 'OR'})
                        current_token = ""
                    else:
                        current_token += char
            else:
                current_token += char
            
            i += 1
        
        if current_token.strip():
            self._add_condition_token(current_token.strip(), tokens)
        
        return tokens
    
    def _add_condition_token(self, condition_str, tokens):
        """
        Parse a condition string and add it as a token.
        
        :param condition_str: Condition string to parse
        :type condition_str: str
        :param tokens: List of tokens to append to
        :type tokens: list
        """
        # Parse comparison operators (check longer operators first)
        operators = ['<=', '>=', '!=', '<', '>', '=']
        
        for op in operators:
            if op in condition_str:
                parts = condition_str.split(op, 1)  # Split only on first occurrence
                if len(parts) == 2:
                    left = parts[0].strip()
                    right = parts[1].strip()
                    
                    # Extract tagname and property
                    if '.' in left:
                        tagname, prop = left.rsplit('.', 1)
                    else:
                        tagname = left
                        prop = None
                    
                    tokens.append({
                        'type': 'condition',
                        'tagname': tagname,
                        'property': prop,
                        'operator': op,
                        'value': right
                    })
                    return
        
        # If no operator found, treat as boolean check
        if '.' in condition_str:
            tagname, prop = condition_str.rsplit('.', 1)
        else:
            tagname = condition_str
            prop = None
        
        tokens.append({
            'type': 'condition',
            'tagname': tagname,
            'property': prop,
            'operator': None,
            'value': None
        })
    
    def _convert_tokens_to_rockwell(self, tokens, nib_info):
        """
        Convert tokens to Rockwell Automation code.
        
        :param tokens: List of parsed tokens
        :type tokens: list
        :param nib_info: NIB information for tagnames
        :type nib_info: dict
        :return: Rockwell code string
        :rtype: str
        """
        # First check if the entire expression contains OR at the top level
        has_top_level_or = self._has_top_level_or(tokens)
        
        result = []
        i = 0
        or_bracket_opened = False
        
        # If the entire expression has OR at top level, open bracket at start
        if has_top_level_or:
            result.append('[')
            or_bracket_opened = True
        
        while i < len(tokens):
            token = tokens[i]
            
            if token['type'] == 'paren':
                if token['value'] == '(':
                    # Look ahead to determine if this is an OR group
                    is_or_group = self._is_or_group(tokens, i)
                    if is_or_group and not or_bracket_opened:
                        result.append('[')
                        or_bracket_opened = True
                else:  # ')'
                    # Check if we need to close an OR group
                    # Close if we're at the matching paren for an OR group
                    if or_bracket_opened and self._is_closing_or_group(tokens, i):
                        result.append(']')
                        or_bracket_opened = False
            
            elif token['type'] == 'operator':
                # Operators are implicit in Rockwell code structure
                # AND = sequential instructions
                # OR = bracketed instructions
                pass
            
            elif token['type'] == 'condition':
                rockwell_instruction = self._convert_condition_to_rockwell(token, nib_info)
                result.append(rockwell_instruction)
            
            i += 1
        
        # Close bracket if still open at the end
        if or_bracket_opened:
            result.append(']')
        
        return ''.join(result)
    
    def _has_top_level_or(self, tokens):
        """
        Check if tokens contain OR operator at the top level (depth 0).
        
        :param tokens: List of tokens
        :type tokens: list
        :return: True if there's a top-level OR
        :rtype: bool
        """
        depth = 0
        for token in tokens:
            if token['type'] == 'paren':
                if token['value'] == '(':
                    depth += 1
                else:
                    depth -= 1
            elif token['type'] == 'operator' and token['value'] == 'OR' and depth == 0:
                return True
        return False
    
    def _is_closing_or_group(self, tokens, close_paren_index):
        """
        Check if this closing paren closes an OR group.
        
        :param tokens: List of tokens
        :type tokens: list
        :param close_paren_index: Index of the closing paren
        :type close_paren_index: int
        :return: True if this closes an OR group
        :rtype: bool
        """
        # Find the matching opening paren
        depth = 1
        i = close_paren_index - 1
        
        while i >= 0 and depth > 0:
            if tokens[i]['type'] == 'paren':
                if tokens[i]['value'] == ')':
                    depth += 1
                elif tokens[i]['value'] == '(':
                    depth -= 1
                    if depth == 0:
                        # Found matching opening paren
                        # Check if it starts an OR group
                        return self._is_or_group(tokens, i)
            i -= 1
        
        return False
    
    def _is_or_group(self, tokens, start_index):
        """
        Check if a parenthesis starts an OR group.
        
        :param tokens: List of tokens
        :type tokens: list
        :param start_index: Index of opening paren
        :type start_index: int
        :return: True if this is an OR group
        :rtype: bool
        """
        depth = 1
        i = start_index + 1
        
        while i < len(tokens) and depth > 0:
            if tokens[i]['type'] == 'paren':
                if tokens[i]['value'] == '(':
                    depth += 1
                else:
                    depth -= 1
            elif tokens[i]['type'] == 'operator' and tokens[i]['value'] == 'OR' and depth == 1:
                return True
            i += 1
        
        return False
    
    def _convert_condition_to_rockwell(self, condition, nib_info):
        """
        Convert a single condition to Rockwell instruction.
        
        For boolean NIBs, always uses XIC instruction regardless of operator,
        assuming the value is "true".
        
        :param condition: Condition token
        :type condition: dict
        :param nib_info: NIB information
        :type nib_info: dict
        :return: Rockwell instruction string
        :rtype: str
        """
        tagname = condition['tagname']
        operator = condition['operator']
        value = condition['value']
        
        # Get NIB name for this tagname
        if tagname in nib_info:
            nib_name = nib_info[tagname].get('nib_name', '')
            nib_data_type = nib_info[tagname].get('nib_data_type', '')
        else:
            # Fallback: default to 'Val' for unknown tags
            nib_name = 'Val'
            nib_data_type = 'Real'
        
        tag_with_nib = f"{tagname}.{nib_name}"
        
        # For boolean types, always use XIC (assuming "true" value)
        if nib_data_type == 'Bool':
            return f"XIC({tag_with_nib})"
        
        # Convert based on operator for non-boolean types
        if operator == '<':
            return f"LES({tag_with_nib},{value})"
        elif operator == '>':
            return f"GRT({tag_with_nib},{value})"
        elif operator == '<=':
            return f"LEQ({tag_with_nib},{value})"
        elif operator == '>=':
            return f"GEQ({tag_with_nib},{value})"
        elif operator == '=':
            return f"EQU({tag_with_nib},{value})"
        elif operator == '!=':
            return f"NEQ({tag_with_nib},{value})"
        else:
            # No operator - boolean check (XIC)
            return f"XIC({tag_with_nib})"
        
        
