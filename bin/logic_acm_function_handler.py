import ast
import threading
import astor
import re
import xml.etree.ElementTree as ET


try:
    from bin.logic_acm_data_handler import ACM_Data_Handler
    from bin.logic_acm_libraries_retrieval import acm_libraries_retrieval, get_library_file_path
    from bin.logic_acm_library_parser import acm_library_parser
except:
    from logic_acm_data_handler import ACM_Data_Handler
    from logic_acm_libraries_retrieval import acm_libraries_retrieval, get_library_file_path
    from logic_acm_library_parser import acm_library_parser

def acm_parameter_handler(parameter_text, object_id, acm_data_handler:ACM_Data_Handler, project_name, passed_variables=None):
    """
    Handles ACM parameters by extracting variables, processing them, and executing the resulting expression.
    
    :param parameter_text: The text containing the ACM parameters.
    :type parameter_text: str
    :param object_id: The object ID.
    :type object_id: Any
    :param acm_data_handler: The ACM data handler object.
    :type acm_data_handler: ACM_Data_Handler
    :param project_name: The name of the project.
    :type project_name: str
    :return: The result of executing the expression.
    :rtype: str
    :param variables: Optional dictionary of variables to be used in the expression.
    :type variables: dict, optional
    
    This function extracts variables from the parameter text, processes them using the ACM data handler and the object ID,
    and executes the resulting expression. The variables are replaced in the expression using the `format_map` method.
    The resulting expression is then executed safely using the `execute_code_safely` function.
    
    Example:
        >>> acm_parameter_handler("Hello {name}!", 1, acm_data_handler, "Project")
        'Hello World!'
    """

    variables = extract_handle_bars(parameter_text)

    for key, value in variables.items():
        if passed_variables and key in passed_variables:
            variables[key] = passed_variables[key]
        else:
            variables[key] = ''

    if not variables:
        return parameter_text 

    for variable in variables.keys():
        if passed_variables and variable in passed_variables:
            continue
        value = process_acm_variable(variable, object_id, acm_data_handler, project_name)
        variables[variable] = str(value)

    expression = correct_condition(parameter_text)
    expression = expression.format_map(variables)
    if passed_variables is not None:
        return str(execute_code_safely(expression, False)), variables
    else:   
        return str(execute_code_safely(expression, False))


def process_acm_variable(variable_name, object_id, acm_data_handler:ACM_Data_Handler, project_name, object_library_parser=None,shared_controllers=None):
    """
    Retrieves the value of a variable in the ACM system.

    :param variable_name: The name of the variable to retrieve.
    :type variable_name: str
    :param object_id: The ID of the object containing the variable.
    :type object_id: int
    :param acm_data_handler: The ACM data handler object.
    :type acm_data_handler: ACM_Data_Handler
    :param project_name: The name of the project.
    :type project_name: str
    :param object_library_parser: The ACM library parser object.
    :type object_library_parser: Optional[ACM_Library_Parser]
    :return: The value of the variable.
    :rtype: Any

    This function retrieves the value of a variable in the ACM system. It first checks if the variable is present in the parameters of the specified object. If not, it retrieves the library functions of the object and checks if the variable is present in any of them. If still not found, it retrieves the parent object of the specified object and performs the same checks. If the variable is found, it returns the value of the variable. If the variable is not found, it returns None.
    
    Example:
        >>> process_acm_variable('variable_name', 123, acm_data_handler, 'project_name')
        'variable_value'
    """

    if variable_name == 'ObjectName':
        return acm_data_handler.get_object_name(object_id)
    
    controller_id = acm_data_handler.get_object(object_id=int(float(object_id)))['ParentObjectID'].iloc[0]

    if variable_name == 'ControllerName':
        return acm_data_handler.get_object_name(controller_id)

    parameters_df = acm_data_handler.get_all_parameters_in_object(object_id)
    if variable_name in parameters_df['Name'].values:
        return parameters_df[parameters_df['Name']==variable_name].iloc[0]['Value']
    
    
    funcs = get_library_functions(object_id,project_name,acm_data_handler,[object_library_parser])

    for func in funcs:
        if func.get('Name') == variable_name:
            try:
                return acm_function_Handler(func,object_id,acm_data_handler)
            except Exception as e:
                pass
    
    controller_parameters_df = acm_data_handler.get_all_parameters_in_object(int(controller_id))
    if variable_name in controller_parameters_df['Name'].values:
        return controller_parameters_df[controller_parameters_df['Name']==variable_name].iloc[0]['Value']
    
    if not shared_controllers:
        shared_controllers = {}

    if controller_id not in shared_controllers:
        shared_controllers[controller_id] = {}

    controller_library_parser = shared_controllers[controller_id].get('library_parser', None)
    controller_library_parser_ref = [controller_library_parser]
    funcs = get_library_functions(controller_id,project_name,acm_data_handler, controller_library_parser_ref)
    shared_controllers[controller_id]['library_parser'] = controller_library_parser_ref[0]

    for func in funcs:
        if func.get('Name') == variable_name:
            return acm_function_Handler(func,controller_id,acm_data_handler)
    


def get_library_functions(object_id, project_name, acm_data_handler:ACM_Data_Handler, library_parser=None):
    
    if library_parser and library_parser[0]:
        return library_parser[0].get_functions_xmls()
    
    
    library_id = acm_data_handler.get_object_library_id(None, int(float(object_id)))
    library_file_path = get_library_file_path(library_id,project_name)
    if not library_file_path:
        projects_df = acm_data_handler.get_all_projects()
        acm_project_name = projects_df.loc[int(float(acm_data_handler.get_project_id()))]['Name']
        acm_libraries_retrieval(project_name, acm_project_name, threaded=False)
        library_file_path = get_library_file_path(library_id,project_name)
    library_parser[0] = acm_library_parser(library_file_path)
    return library_parser[0].get_functions_xmls()
    

def acm_function_Handler(func_elem:ET.Element, object_id, acm_data_handler:ACM_Data_Handler):
    
    if isinstance(func_elem,str):
        func_elem = ET.fromstring(func_elem)

    function_type = func_elem.get("FType")
    
    variables = extract_all_varibles(ET.tostring(func_elem,encoding='unicode'), acm_data_handler, object_id)


    if function_type == 'Conditional':
        data = {}
        condition_func = handle_conditional_function(func_elem, variables)
        data = execute_code_safely(condition_func,True,data)
        return str(data['condition_output'])



    if function_type == 'Calculation':
        expression = correct_condition(func_elem.find("Exp").text)
        expression = remove_braces_with_parentheses(expression)
        expression = expression.format_map(variables)
        return str(execute_code_safely(expression, False))


def handle_conditional_function(xml_element,variables):
    
    indent="    "
    output='def func():\n'
    for child in xml_element:
        output = process_element(child, indent,output)

    output = output.format_map(variables)

    output +='\ncondition_output = func()'

    return output


def remove_braces_with_parentheses(text):
    """
    Remove curly braces {} if there are parentheses () between them.
    
    Args:
        text (str): Input string to process
        
    Returns:
        str: String with curly braces removed if parentheses are between them
    """
    # Pattern to match { followed by content containing (), then }
    pattern = r'\{([^{}]*\([^)]*\)[^{}]*)\}'
    
    # Replace the matched pattern with just the content (without the braces)
    result = re.sub(pattern, r'\1', text)
    
    return result

# Alternative implementation using a more explicit approach
def remove_braces_with_parentheses_explicit(text):
    """
    Alternative implementation that's more explicit about the logic.
    """
    result = []
    i = 0
    
    while i < len(text):
        if text[i] == '{':
            # Find the matching closing brace
            brace_count = 1
            j = i + 1
            content = ""
            
            while j < len(text) and brace_count > 0:
                if text[j] == '{':
                    brace_count += 1
                elif text[j] == '}':
                    brace_count -= 1
                
                if brace_count > 0:
                    content += text[j]
                j += 1
            
            # Check if content contains parentheses
            if '(' in content and ')' in content:
                # Remove the braces, keep the content
                result.append(content)
            else:
                # Keep the braces
                result.append(text[i:j])
            
            i = j
        else:
            result.append(text[i])
            i += 1
    
    return ''.join(result)




def extract_all_varibles(text, acm_data_handler, object_id):
    
    variables = extract_handle_bars(text)


    parameter_df = acm_data_handler.get_all_parameters_in_object(object_id)
    

    for key, _ in variables.items():
        if key in parameter_df['Name'].values:
            row = parameter_df.loc[parameter_df['Name']==key].iloc[0]
            value = row['Value']
            variables[key] = str(value)

    return variables

def extract_handle_bars(text):
    pattern = r"\{([^{}]+)\}"
    variables = {}

    matches = re.findall(pattern, text)
    for match in matches:
        variables[match.strip().strip('{').strip('}')] = ""
    return variables

        


def correct_condition(condition):
    logic_statements = [
                        [' and ', ' and '],
                        [' or ', ' or '],
                        [' not ', ' not '],
                        [r'(?<=[^a-zA-Z0-9_])int\(', ' int('],
                        [r'(?<=[^a-zA-Z0-9_])abs\(', ' abs('],
                        [r'(?<=[^a-zA-Z0-9_])round\(', ' round('],
                        [r'(?<=[^a-zA-Z0-9_])length\(', ' len('],
                        ]

    for statement in logic_statements:
        pattern = re.compile(statement[0], re.IGNORECASE)
        condition= pattern.sub(statement[1], condition)


    condition = condition.replace('=','==')
    condition = condition.replace('round(','int')
    condition = condition.replace('length(','len')
    condition = condition.replace('<>','!=')
    condition = condition.replace('&',' + ')

    return condition


def process_element(element, indent, output):
    if element.tag == "ifcond":
        # Extract the condition value
        condition = element.text.strip()
        if condition:
            # If condition is not empty, evaluate the children
            corrected_condition = correct_condition(condition)
            output +=  f"{indent}if {corrected_condition}:\n"
            indent += "    "
            for child in element:
                output = process_element(child, indent, output)
            if 'Value' in element.attrib:
                output +=f"{indent}return {element.get("Value")}\n"
            indent = indent[:-4]  # Remove indentation
        else:
            # If condition is empty, evaluate the else block if it exists
            for child in element:
                if child.tag == "else":
                    output = process_element(child, indent, output)
    elif element.tag == "else":
        # Evaluate the else block
        output +=f"{indent}else:\n"
        indent += "    "
        for child in element:
            output = process_element(child, indent, output)
        if 'Value' in element.attrib:
            output +=f"{indent}return {element.get("Value")}\n"
        indent = indent[:-4]  # Remove indentation
    else:
        # Evaluate other elements (e.g., <ifcond Value="True">)
        value = element.get("Value")
        output +=f"{indent}return {value}"

    return output


class CodeSanitizer:
   def remove_imports(self, code: str) -> str:
       """Remove all import statements from the code to prevent malicious code execution"""
       tree = ast.parse(code)
       new_body = [
           node
           for node in tree.body
           if not isinstance(node, (ast.Import, ast.ImportFrom))
       ]
       new_tree = ast.Module(body=new_body)
       return astor.to_source(new_tree).strip()
   
def watchdog():
    raise TimeoutError("Function timed out")

def execute_code_safely(code: str, is_exec=False, data=None):
    sanitizer = CodeSanitizer()
    sanitized_code = sanitizer.remove_imports(code)
    # Define a restricted namespace
    safe_globals = {
        "__builtins__": {
            "len": len,
            "int": int,
            "min": min,
            "max": max,
            "abs": abs,
        }
    }
    if data is not None:
        safe_locals = {}
    else:
        safe_locals = data
    
    # Set a time limit for execution
    # Register the timeout handler
    # Create a Timer that will call the watchdog function after the specified delay
    alarm = threading.Timer(2, watchdog)
    alarm.start()
    try:
        if is_exec:
            exec(sanitized_code, safe_globals, safe_locals)
            return safe_locals
        else:
            return eval(sanitized_code, safe_globals, safe_locals)
    except TimeoutError as e:
        return str(e)
    except Exception as e:
        return f"Error during execution: {e}"
    finally:
        # Cancel the timer if the function returned before the timeout
        alarm.cancel()
    


    

if __name__ == "__main__": 

    # Example XML string
    test_0 = """<Func Name="fn_EvtLimit" Scope="Object" CLXDep="true" AADDep="false" FType="Conditional" ResType="Numeric">
            <ifcond Value="32767"><![CDATA['{EventLogging_Style}' = 'EdgeGateway']]></ifcond>
            <else Value="15" />
        </Func>"""



    test_1 = '''<Func Name="fn_Redundant" Scope="Object" CLXDep="true" AADDep="false" FType="Conditional" ResType="Bool">
            <ifcond Value="1"><![CDATA[{Has_Redundant} AND {Cfg_HasSecNotRdyAlm}]]></ifcond>
            <else Value="0" />
        </Func>'''

    test_2 = '''<Func Name="fn_Redundant" Scope="Object" CLXDep="true" AADDep="false" FType="Conditional" ResType="Bool">
            <ifcond><![CDATA[True]]><ifcond Value="True"><![CDATA[True]]></ifcond><ifcond Value="True"><![CDATA[False]]></ifcond><else Value="True" /></ifcond>
            <else Value="False" />
        </Func>'''

    test_3 = '''<Func Name="fn_Connection_IO" Scope="Object" CLXDep="true" AADDep="false" FType="Calculation" ResType="Bool">
            <Exp><![CDATA[{IO_Map_Strategy}=5]]></Exp>
        </Func>'''

    acm_db = ACM_Data_Handler(r'DRIVER={ODBC Driver 18 for SQL Server};SERVER=1TV0VV3\SQLACM;DATABASE=ACM;Trusted_Connection=yes;TrustServerCertificate=yes;')
    acm_db.set_project_id("9")
    print(process_acm_variable('fn_EvtLimit','6545',acm_db,'dfsdfvs'))
    print(acm_function_Handler(test_0, '4998', acm_db))
    print(acm_function_Handler(test_3, '4998', acm_db))

            


