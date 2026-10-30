import re
import xml.etree.ElementTree as ET


try:
    from bin.logic_acm_data_handler import ACM_Data_Handler
    from bin.logic_acm_libraries_retrieval import acm_libraries_retrieval, get_library_file_path
    from bin.logic_acm_library_parser import acm_library_parser
    from bin.logic_acm_expression import evaluate_acm_expression, evaluate_conditional_function
except:
    from logic_acm_data_handler import ACM_Data_Handler
    from logic_acm_libraries_retrieval import acm_libraries_retrieval, get_library_file_path
    from logic_acm_library_parser import acm_library_parser
    from logic_acm_expression import evaluate_acm_expression, evaluate_conditional_function

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
    and evaluates the expression with `evaluate_acm_expression`. Variable values are bound as data, never pasted
    into the expression text. Raises `AcmExpressionError` for malformed or disallowed expressions.
    
    Example:
        >>> acm_parameter_handler("{Count} * 2", 1, acm_data_handler, "Project")
        '8'
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

    result = str(evaluate_acm_expression(parameter_text, variables))
    if passed_variables is not None:
        return result, variables
    return result


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
        return str(evaluate_conditional_function(func_elem, variables))

    if function_type == 'Calculation':
        return str(evaluate_acm_expression(func_elem.find("Exp").text, variables))


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
