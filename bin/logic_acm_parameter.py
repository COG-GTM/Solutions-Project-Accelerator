from bin.logic_acm_data_handler import ACM_Data_Handler
from bin.logic_acm_libraries_retrieval import get_library_file_path
from bin.logic_acm_library_parser import get_object_NIBS


class acm_paramter():
    """ 
    A class that handles getting ACM parameters options 
    and writing ACM parameters values while handling the reference types.

    Reference types are:
    - object
    - objectNIB
    - subobject
    - subobjectNIB
    - immediate

    Reference type values are based on the ACM database constants and are as follows:
    - 1: immediate
    - 2: object
    - 5: objectNIB
    - 3: subobject
    - 9: subobjectNIB
    """


    REF_OBJECT_FLAG = 'object'
    REF_OBJECT_NIB_FLAG = 'objectNIB'
    REF_SUBOBJECT_FLAG = 'subobject'
    REF_SUBOBJECT_NIB_FLAG = 'subobjectNIB'
    REF_IMMEDIATE_FLAG = 'immediate'

    REF_IMMEDIATE_TYPE = 1
    REF_OBJECT_TYPE = 2
    REF_OBJECT_NIB_TYPE = 5
    REF_SUBOBJECT_TYPE = 3
    REF_SUBOBJECT_NIB_TYPE = 9


    def __init__(self, object_id, acm_data_handler: ACM_Data_Handler, parameter_data, project_name) -> None:
        """
        Initializes the Logic_ACM_Parameter object.

        :param object_id: The object ID.
        :type object_id: Any
        :param acm_data_handler: The ACM data handler.
        :type acm_data_handler: ACM_Data_Handler
        :param parameter_data: The parameter data.
        :type parameter_data: Any
        :param project_name: The project name.
        :type project_name: str

        :return: None
        :rtype: None

        Initializes the Logic_ACM_Parameter object with the given object ID, ACM data handler, parameter data, and project name.
        """             
        self.__object_id = object_id 
        self.__acm_data_handler = acm_data_handler 
        self.__project_name = project_name
        self.__parameter_data = parameter_data


    def write_parameter_value(self, value, parameter):
        """
        Writes the value of a parameter.

        :param value: The value to be written.
        :type value: Any
        :param parameter: The parameter to write the value to.
        :type parameter: str

        :return: None
        :rtype: None

        This function writes the given value to the specified ACM parameter.

        Example:
            >>> write_parameter_value(10, 'param1')
            None
        """
        self.__acm_data_handler.write_parameter_value(value,self.__object_id,parameter)


    def write_subparameter_value(self, value, parameter):
        """
        Writes the value of a ACM subparameter.

        :param value: The value to be written.
        :type value: Any
        :param parameter: The parameter to which the value belongs.
        :type parameter: str

        :return: None
        :rtype: None

        This function writes the given value to the specified ACM subparameter of the subobject.

        Example:
            >>> write_subparameter_value(10, 'subparam')
        """
        self.__acm_data_handler.write_subparameter_value(value,self.__object_id,parameter)


    def get_value(self):
        """
        Retrieves the value of a ACM parameter for a given object.

        :return: The value of the parameter.
        :rtype: Any

        Example:
            >>> get_value()
            'Result'
        """
        return self.__acm_data_handler.get_parameter_in_object(self.__object_id,self.__parameter_data['Name'])


    def write_unknown_referenced_values(self,parameter, value, subobject_id=None):
        """
        Writes unknown referenced values to the specified parameter.

        :param parameter: The parameter to write the values to.
        :type parameter: str
        :param value: The value to write.
        :type value: str
        :param subobject_id: The ID of the subobject (optional).
        :type subobject_id: int, optional
        :return: None
        :rtype: None
        
        This function writes unknown referenced values to the specified parameter. It first 
        retrieves all reference options for the given value. Then, it determines the 
        reference type based on the options. Finally, it calls the write_referenced_values 
        function to write the values to the parameter.
        
        Example:
            >>> write_unknown_referenced_values('param', 'value', 123)
        """

        if parameter == ACM_Data_Handler.SUBOBJECT_DESCRIPTION:
            self.__acm_data_handler.set_subobject_description(subobject_id,value)
            return 'immediate'


        options = self.get_all_reference_options(value)

        flag_to_type = {
            'immediate': 1,
            'object': 2,
            'objectNIB': 5,
            'subobject': 3,
            'subobjectNIB': 9,
        }

        ref_type = 1
        selected_option = None
        for option in options:
            if option[0].lower() == value.lower():
                ref_type = flag_to_type[option[1]]
                selected_option = option

        
        


        
        self.write_referenced_values(ref_type,parameter, value, subobject_id)

        if selected_option:
            return selected_option[1]
        else:
            return 'immediate'


    def write_referenced_values(self, ref_type, parameter, value, subobject_id=None):
        """
        Writes referenced values based on the given reference type.
        :param ref_type: The type of reference.
        :type ref_type: str
        :param parameter: The parameter to write the referenced values for.
        :type parameter: str
        :param value: The value to write.
        :type value: Any
        :param subobject_id: The ID of the subobject (optional).
        :type subobject_id: int, optional
        :return: The result of writing the referenced values.
        :rtype: Any

        Writes referenced values based on the given reference type. The function 
        uses a dictionary to map the reference type to the appropriate function that writes the referenced values.
        
        Example:
            >>> write_referenced_values('object', 'parameter', 'value', 123)
            None
        """
        referenced_type = {
            self.REF_OBJECT_TYPE: self.__write_ref_type_object,
            self.REF_OBJECT_NIB_TYPE: self.__write_ref_type_object_nib,
            self.REF_SUBOBJECT_TYPE: self.__write_ref_type_subobject,
            self.REF_SUBOBJECT_NIB_TYPE: self.__write_ref_type_subobject_nib,
            '_': self.__write_ref_type_default
        }
        
        return referenced_type.get(ref_type, referenced_type['_'])(value
                                                                   , parameter
                                                                   , subobject_id)
    

    
    def __write_ref_type_default(self, value, parameter, subobject_id):
        """
        Writes the default value for a reference type parameter.

        :param value: The value to be written.
        :type value: Any
        :param parameter: The parameter name.
        :type parameter: str
        :param subobject_id: The subobject ID (optional).
        :type subobject_id: int or None
        
        :return: None
        :rtype: None

        This function writes the default value for a reference type parameter. If a subobject ID is provided, the value is written as a subparameter value using the REF_IMMEDIATE_TYPE. Otherwise, the value is written as a parameter value using the REF_IMMEDIATE_TYPE.

        Example:
            >>> __write_ref_type_default(10, 'param1', 5)
            None
        """
        if subobject_id:
            self.__acm_data_handler.write_subparameter_value(value,subobject_id,parameter,self.REF_IMMEDIATE_TYPE)
        else:
            self.__acm_data_handler.write_parameter_value(value,self.__object_id,parameter,self.REF_IMMEDIATE_TYPE)


    def __write_ref_type_object(self, value, parameter, subobject_id):
        """
        Writes a reference type object to the ACM data handler.

        :param value: The value of the reference type object.
        :type value: str
        :param parameter: The parameter to write the value to.
        :type parameter: str
        :param subobject_id: The subobject ID to write the value to. If None, the value is written to the main object.
        :type subobject_id: str or None
        :return: None
        :rtype: None
        
        This function writes a reference type object to the ACM data handler. It splits the value by '.' to get the object name,
        retrieves the object ID using the object name, and then writes the value to the specified parameter in the object or subobject.
        
        Example:
            >>> __write_ref_type_object('object1.parameter1', 'parameter1', 'subobject1')
            None
        """
        reference_text = value.split('.')
        object_name = reference_text[0]

        object_id = self.__acm_data_handler.get_object_id(object_name,case=False)
        if subobject_id:
            self.__acm_data_handler.write_subparameter_value(object_id,subobject_id,parameter,self.REF_OBJECT_TYPE)
        else:
            self.__acm_data_handler.write_parameter_value(object_id,self.__object_id,parameter,self.REF_OBJECT_TYPE)


    def __write_ref_type_object_nib(self, value, parameter, subobject_id):
        """
        Writes a reference type object NIB value to the ACM data handler.
        
        :param value: The value of the reference type object NIB.
        :type value: str
        :param parameter: The parameter to write the value to.
        :type parameter: str
        :param subobject_id: The subobject ID (optional).
        :type subobject_id: int or None
        :return: None
        :rtype: None
        
        This function writes the value of a reference type object NIB to the ACM data handler. If a subobject ID is provided, the value is written as a subparameter value. Otherwise, the value is written as a parameter value.
        
        Example:
            >>> __write_ref_type_object_nib('object_name.ref_value', 'parameter', 123)
            None
        """
        reference_text = value.split('.')
        object_name = reference_text[0]
        ref_value = reference_text[1]

        object_id = self.__acm_data_handler.get_object_id(object_name,case=False)
        if subobject_id:
            self.__acm_data_handler.write_subparameter_value(object_id,subobject_id,parameter,self.REF_OBJECT_NIB_TYPE,ref_value)
        else:
            self.__acm_data_handler.write_parameter_value(object_id,self.__object_id,parameter,self.REF_OBJECT_NIB_TYPE,ref_value)


    def __write_ref_type_subobject(self, value, parameter, subobject_id):
        """
        Write the reference type subobject value to the ACM data handler.

        :param value: The value of the reference type subobject.
        :type value: str
        :param parameter: The parameter to write the value to.
        :type parameter: str
        :param subobject_id: The ID of the subobject.
        :type subobject_id: int
        :return: None
        :rtype: None

        This function writes the value of the reference type subobject to the ACM data handler. It first extracts the object name and subobject name from the given value. Then, it retrieves the object ID and subobject ID using the ACM data handler's methods. Finally, it writes the value to the appropriate subparameter or parameter based on the availability of the subobject ID.
        
        Example:
            >>> __write_ref_type_subobject('object_name.subobject_name', 'parameter', 123)
            None
        """
        reference_text = value.split('.')
        object_name = reference_text[0]
        subobject_name = reference_text[2]

        value_object_id = self.__acm_data_handler.get_object_id(object_name,case=False)
        value_subobject_id = self.__acm_data_handler.get_subobject_id(subobject_name,value_object_id)

        if subobject_id:
            self.__acm_data_handler.write_subparameter_value(value_subobject_id,subobject_id,parameter,self.REF_SUBOBJECT_TYPE)
        else:
            self.__acm_data_handler.write_parameter_value(value_subobject_id,self.__object_id,parameter,self.REF_SUBOBJECT_TYPE)


    def __write_ref_type_subobject_nib(self, value, parameter, subobject_id):
        """
        Writes a reference type subobject nib to the ACM data handler.

        :param value: The value of the reference type subobject nib.
        :type value: str
        :param parameter: The parameter to write the value to.
        :type parameter: str
        :param subobject_id: The ID of the subobject.
        :type subobject_id: int
        :return: None
        :rtype: None

        This function writes the value of a reference type subobject nib to the ACM data handler. It first extracts the object name, subobject name, and reference value from the given value. Then, it retrieves the object ID and subobject ID using the ACM data handler. Finally, it writes the parameter value to the subobject ID if it exists, otherwise it writes it to the object ID.
        
        Example:
            >>> __write_ref_type_subobject_nib('object_name.subobject_type.subobject_name.nib_name', 'parameter', 123)
            None
        """
        reference_text = value.split('.')
        object_name = reference_text[0]
        subobject_name = reference_text[2]
        ref_value = reference_text[3]

        object_id = self.__acm_data_handler.get_object_id(object_name,case=False)
        subobject_id = self.__acm_data_handler.get_subobject_id(subobject_name,object_id)

        object_id = self.__acm_data_handler.get_object_id(object_name,case=False)

        if subobject_id:
            self.__acm_data_handler.write_parameter_value(subobject_id,self.__object_id,parameter,self.REF_SUBOBJECT_TYPE,ref_value)
        else:
            self.__acm_data_handler.write_parameter_value(subobject_id,self.__object_id,parameter,self.REF_SUBOBJECT_TYPE,ref_value)



    def get_referenced_options(self, ref_type, value,  ref_value, ):
        """
        Retrieves referenced options based on the given reference type, value, and reference value.
        
        :param ref_type: The type of reference.
        :type ref_type: str
        :param value: The value to be used for reference.
        :type value: Any
        :param ref_value: The reference value.
        :type ref_value: Any
        :return: The referenced options.
        :rtype: Any
        
        Retrieves referenced options based on the given reference type, value, and reference value. The function 
        uses a dictionary to map the reference type to the appropriate function that retrieves the referenced options.
        """
        referenced_type = {
            self.REF_OBJECT_TYPE: self.__get_ref_type_object,
            self.REF_OBJECT_NIB_TYPE: self.__get_ref_type_object_nib,
            self.REF_SUBOBJECT_TYPE: self.__get_ref_type_subobject,
            self.REF_SUBOBJECT_NIB_TYPE: self.__get_ref_type_subobject_nib,
            '_': self.__get_ref_type_default
        }
        
        return referenced_type.get(ref_type, referenced_type['_'])(value, ref_value)



    def __get_ref_type_default(self, value, _):
        """
        Returns the default reference type.

        :param value: The value to be returned.
        :type value: Any
        :param _: Placeholder parameter.
        :type _: Any
        
        :return: The value.
        :rtype: Any

        This function returns the given value.
        
        Example:
            >>> __get_ref_type_default('value', None)
            'value'
        """
        return value


    def __get_ref_type_object(self, object_id, _):
        """
        Returns the reference type object.

        :param object_id: The ID of the object.
        :type object_id: int
        :param _: Placeholder parameter.
        :type _: Any

        :return: The reference type object.
        :rtype: str

        This function retrieves the object with the given ID and returns a string representation of the object's name.

        Example:
            >>> __get_ref_type_object(123, None)
            'Result'
        """
        return self.__acm_data_handler.get_object_name(int(object_id))


    def __get_ref_type_object_nib(self, object_id, ref_value):
        """
        Returns the reference type object nib.

        :param object_id: The ID of the object.
        :type object_id: int
        :param ref_value: The reference value.
        :type ref_value: str
        
        :return: The concatenated string of the object name and the reference value.
        :rtype: str

        More detailed description of the function (if needed).

        Example:
            >>> example_function(1, 'test')
            'Result'
        """
        return self.__acm_data_handler.get_object_name(int(object_id)) +'.'+ref_value


    def __get_ref_type_subobject(self, subobject_id, _ ):
        """
        Returns the reference type subobject.

        :param subobject_id: The ID of the subobject.
        :type subobject_id: int
        :param _: Placeholder parameter.
        :type _: Any

        :return: The reference type subobject.
        :rtype: str

        This function retrieves the subobject with the given ID and returns a string representation of the subobject's parent object name, type, and name.

        Example:
            >>> __get_ref_type_subobject(123, None)
            'ParentObjectName.Type.Name'
        """
        subobject = self.__acm_data_handler.get_subobject(subobject_id).iloc[0].to_dict()
        object_name = self.__acm_data_handler.get_object_name(subobject['ParentObjectID'])
        return object_name +'.'+subobject['Type']+'.'+subobject['Name']
    

    def __get_ref_type_subobject_nib(self, subobject_id, ref_value ):
        """
        Returns a string representing the reference type subobject nib.

        :param subobject_id: The ID of the subobject.
        :type subobject_id: int
        :param ref_value: The reference value.
        :type ref_value: str
        
        :return: The reference type subobject nib.
        :rtype: str

        This function takes a subobject ID and a reference value and returns a string representing the reference type subobject nib. The reference type subobject nib is constructed by concatenating the object name, subobject type, subobject name, and reference value.

        Example:
            >>> __get_ref_type_subobject_nib(123, 'test')
            'object_name.subobject_type.subobject_name.test'
        """
        subobject = self.__acm_data_handler.get_subobject(subobject_id).iloc[0].to_dict()
        object_name = self.__acm_data_handler.get_object_name(subobject['ParentObjectID'])
        return object_name +'.'+subobject['Type']+'.'+subobject['Name']+'.'+ref_value
    

    def get_all_reference_options(self, text='', ref_type=None):
        """
        Retrieves all reference options based on the given text.

        :param text: The text used for filtering the reference options. (default: '')
        :type text: str
        :return: A list of reference options.
        :rtype: list

        Retrieves all reference options based on the given text. The function first checks if there is a 'Filter' and 'SubObject' in the parameter data. If so, it calls the __get_all_subobjects_with_acm_filter method to get the options. Otherwise, it calls the __get_all_objects_with_acm_filter method. 
        The function then splits the text by '.' and extracts the object name. If the object name is empty or not found in the project, it returns the options as is.
        Next, the function updates the autocomplete with object nib options. It retrieves the library ID and object ID based on the object name. It then gets the case-corrected object name and the library file path. Using the library file path, it retrieves the object NIBs. It creates options for each NIB with the format 'object_name.nib_name' and adds them to the options list.
        The function also updates the autocomplete with subobject options. It retrieves all subobjects in the object and creates options for each subobject with the format 'object_name.subobject_display_name.subobject_name'. These options are added to the options list.
        If the text does not contain any subobject options, it returns the options as is.
        Finally, the function updates the autocomplete with subobject nibs options. It extracts the subobject type and subobject name from the text. It creates options for each NIB with the format 'object_name.subobject_type.subobject_name.nib_name' and adds them to the options list.
        The updated options list is then returned.
        """

        if self.__parameter_data and 'Filter' in self.__parameter_data and 'SubObject' in self.__parameter_data['Filter']:
            options = self.__get_all_subobjects_with_acm_filter()
        else:
            options = self.__get_all_objects_with_acm_filter()

        reference_text = text.split('.')
        object_name = reference_text[0]

        if object_name =='' or not self.__acm_data_handler.is_object_in_project(object_name):
            
            return options

        
        # Update autocomplete with object nib options
        library_id = self.__acm_data_handler.get_object_library_id(object_name,case=False)
        object_id = self.__acm_data_handler.get_object_id(object_name,case=False)

        # Get case corrected object name
        object_name = self.__acm_data_handler.get_object_name(object_id)
        library_file_path = get_library_file_path(library_id,self.__project_name)
        nibs = get_object_NIBS(library_file_path)
        object_nibs_options = [(object_name+'.'+nib['Name']
                                    ,self.REF_OBJECT_NIB_FLAG
                                    ,object_name
                                    ,object_id
                                    ,nib) for _, nib in nibs.items() if nib['Scope']=='Object']
        options = object_nibs_options + options
        


        # Update autocomplete with subobject options
        subobjects_df = self.__acm_data_handler.get_all_subobjects_in_object(self.__acm_data_handler.get_object_id(object_name,case=False))
        subobject_options = [(object_name+'.'+data['DisplayName']+'.'+data['Name']
                                ,self.REF_SUBOBJECT_FLAG
                                ,object_name
                                ,object_id
                                ,subobject_id) for subobject_id, data in subobjects_df.iterrows()]
        options = subobject_options + options

        if not any(option[0].lower() in text.lower() for option in subobject_options):
            
            return options


        # Update autocomplete with subobject nibs options
        subobject_type = reference_text[1]
        subobject_name = reference_text[2]
        subobject_nibs_options = [(object_name+'.'+subobject_type+'.'+subobject_name+'.'+nib['Name']
                                        ,self.REF_SUBOBJECT_NIB_FLAG
                                        ,object_name
                                        ,object_id
                                        ,subobject_type
                                        ,subobject_name
                                        ,nib) for _, nib in nibs.items() if nib['Scope']=='Object']
        options = subobject_nibs_options + options

        
        return options


    def write_reference_option(self,option, parameter, subobject_id=None):
        """
        Writes a reference option to a file.

        :param option: The reference option.
        :type option: tuple
        :param parameter: The parameter.
        :type parameter: str
        :param subobject_id: The subobject ID (optional).
        :type subobject_id: int, None
        :return: None
        :rtype: None
        
        Writes the reference option to a file based on the given parameters.
        
        Example:
            >>> write_reference_option(('REF_OBJECT_FLAG', 'value'), 'parameter', subobject_id=1)
        """

        ref_flag = option[1]

        ref_type_saving = {
            self.REF_OBJECT_FLAG: self.__ref_type_object,
            self.REF_OBJECT_NIB_FLAG: self.__ref_type_object_nib,
            self.REF_SUBOBJECT_FLAG: self.__ref_type_subobject,
            self.REF_SUBOBJECT_NIB_FLAG: self.__ref_type_subobject_nib
        }

        ref_type,value,ref_value = ref_type_saving[ref_flag](option)
        self.__write_ref_type_option(ref_type, value,parameter,ref_value,subobject_id)


    def __write_ref_type_option(self, ref_type, value, parameter,ref_value, subobject_id):
        """
        Writes the reference type option to the ACM data handler.

        :param ref_type: The reference type.
        :type ref_type: str
        :param value: The value to be written.
        :type value: Any
        :param parameter: The parameter to write the value to.
        :type parameter: str
        :param ref_value: The reference value.
        :type ref_value: Any
        :param subobject_id: The subobject ID (optional).
        :type subobject_id: int or None
        
        :return: None
        :rtype: None
        
        Writes the given value to the ACM data handler based on the reference type and reference value.
        If a subobject ID is provided, the value is written as a subparameter value.
        Otherwise, the value is written as a parameter value for the object ID.
        
        Example:
            >>> __write_ref_type_option('type', 'value', 'param', 'ref_value', 123)
            None
        """
        if subobject_id is not None:
            self.__acm_data_handler.write_subparameter_value(value,subobject_id,parameter,ref_type,ref_value)
        else:
            self.__acm_data_handler.write_parameter_value(value,self.__object_id,parameter,ref_type,ref_value)


    def __ref_type_object(self,option):
        """
        Returns the reference type, object ID, and an empty string in the place of ref_value.

        :param option: The option list.
        :type option: list

        :return: A tuple containing the reference type, object ID, and an empty string.
        :rtype: tuple

        This function takes an option list and extracts the object ID from it. It then 
        returns a tuple containing the reference type, object ID, and an empty string in the place of ref_value.

        Example:
            >>> __ref_type_object(option)
            ('ref_type', 'object_id', '')
        """
        object_id = option[2]
        ref_type = self.REF_OBJECT_TYPE # From ACM
        return ref_type, object_id, ''


    def __ref_type_object_nib(self,option):
        """
        Returns the reference type, object ID, and reference value.

        :param option: The option list.
        :type option: list

        :return: A tuple containing the reference type, object ID, and reference value.
        :rtype: tuple

        This function takes an option list and extracts the object ID and reference value 
        from it. It then returns a tuple containing the reference type, object ID, and reference value.

        Example:
            >>> __ref_type_object_nib(option)
            ('REF_OBJECT_NIB_TYPE', object_id, ref_value)
        """
        object_id = option[3]
        ref_value = option[4]['Name']
        ref_type = self.REF_OBJECT_NIB_TYPE # From ACM
        return ref_type,object_id,ref_value


    def __ref_type_subobject(self,option):
        """
        Returns the reference type, subobject ID, and an empty string.

        :param option: The option parameter.
        :type option: The type of the option parameter.

        :return: A tuple containing the reference type, subobject ID, and an empty string.
        :rtype: tuple

        This function retrieves the subobject ID based on the given option parameter and returns a tuple containing the reference type, subobject ID, and an empty string.

        Example:
            >>> __ref_type_subobject('example')
            ('REF_SUBOBJECT_TYPE', 'subobject_id', '')
        """
        subobject_id = self.__get_subobject_id(option)
        ref_type = self.REF_SUBOBJECT_TYPE # From ACM
        return ref_type, subobject_id,''


    def __ref_type_subobject_nib(self,option):
        """
        Returns the reference type, subobject ID, and reference value for a given option.

        :param option: The option to retrieve the reference information from.
        :type option: dict

        :return: A tuple containing the reference type, subobject ID, and reference value.
        :rtype: tuple

        This function retrieves the subobject ID and reference value from the given option dictionary and returns them along with the reference type.

        Example:
            >>> __ref_type_subobject_nib(option)
            ('REF_SUBOBJECT_NIB_TYPE', subobject_id, ref_value)
        """
        subobject_id = self.__get_subobject_id(option)
        ref_value = option[6]['Name']
        ref_type = self.REF_SUBOBJECT_NIB_TYPE # From ACM
        return ref_type,subobject_id,ref_value


    def __get_subobject_id(self, option):
        """
        Retrieves the subobject ID based on the given option.

        :param option: The option containing the necessary information.
        :type option: list
        :return: The subobject ID.
        :rtype: int
        
        Retrieves the subobject ID by iterating through the DataFrame of all subobjects in the object.
        It matches the 'Name' column with the option name and returns the corresponding subobject ID.
        
        Example:
            >>> __get_subobject_id(option)
            12345
        """
        object_id = option[3]
        subobject_id = None

        df = self.__acm_data_handler.get_all_subobjects_in_object(object_id)
        for index, row in df.iterrows():
            if row['Name'].lower() == option[4]:
                subobject_id = index
                break

        return subobject_id


    def get_subobject_reference_options(self, object_id):
        """
        Returns the options for subobject references.
        :param object_id: The ID of the object.
        :type object_id: int
        :return: The options for subobject references.
        :rtype: list
        This function retrieves all subobjects in the specified object and returns a list of options.
        Each option is a tuple containing the subobject name, the reference flag, and the index.
        Example:
            >>> get_subobject_reference_options(1)
            [('Subobject1', 'REF_SUBOBJECT_FLAG', 0), ('Subobject2', 'REF_SUBOBJECT_FLAG', 1)]
        """
        df = self.__acm_data_handler.get_all_subobjects_in_object(object_id)

        options = []
        for index, row in df.iterrows():
            
            options.append((row['Name'],self.REF_SUBOBJECT_FLAG,index))

        return options


    def __get_all_objects_with_acm_filter(self):
        """
        Retrieves all objects as options for text linking with an ACM filter.

        :return: List of options
        :rtype: list

        This function retrieves all objects with ACM filter and returns a list of options.
        Each option is a tuple containing the object's name, REF_OBJECT_FLAG, and index.
        
        Example:
            >>> __get_all_objects_with_acm_filter()
            [('Object1', REF_OBJECT_FLAG, 0), ('Object2', REF_OBJECT_FLAG, 1), ...]
        """
        acm_filter = ''
        if self.__parameter_data and 'Filter' in self.__parameter_data:
            acm_filter: str = self.__parameter_data['Filter']

            # Change to ACM acm_data_handler table name
            acm_filter = acm_filter.replace('Library.','RegisteredLibraries.')

            # Change to ACM acm_data_handler column name
            acm_filter = acm_filter.replace('RegisteredLibraries.SolutionType','RegisteredLibraries.CoreType')
        
        df = self.__acm_data_handler.get_all_objects_with_acm_filter(acm_filter)

        options = []
        for index, row in df.iterrows():
            options.append((row['Name'],self.REF_OBJECT_FLAG,index))

        return options



    def __get_all_subobjects_with_acm_filter(self):
        """
        Retrieves all subobjects as options for text linking based on the ACM filter.

        :return: A list of options containing subobject information.
        :rtype: list
        
        This function retrieves all subobjects based on the ACM filter and returns a list of options containing subobject information.

        Example: 
            >>> get_all_subobjects_with_acm_filter()
            [('SubObject1', 'subobject', '1'), ('SubObject2', 'subobject', '2')]
        """
        acm_filter: str = self.__parameter_data['Filter']

        # Change to ACM acm_data_handler table name
        acm_filter = acm_filter.replace('Library.','RegisteredLibraries.')

        # Change to ACM acm_data_handler table name
        acm_filter = acm_filter.replace('SubObject.','SubObjects.')  

        # Change to ACM acm_data_handler column name
        acm_filter = acm_filter.replace('RegisteredLibraries.SolutionType','RegisteredLibraries.CoreType')
        
        df = self.__acm_data_handler.get_all_subobjects_with_acm_filter(acm_filter)
        
        options = []
        for index, row in df.iterrows():
            options.append((row['ObjectName']+'.'+row['DisplayName']+'.'+row['Name']
                                ,self.REF_SUBOBJECT_FLAG
                                ,row['ObjectName']
                                ,row['ObjectID']
                                ,index))

        return options
    

if __name__ == '__main__':
    acm_db = ACM_Data_Handler(r'DRIVER={ODBC Driver 18 for SQL Server};SERVER=1TV0VV3\SQLACM;DATABASE=ACM;Trusted_Connection=yes;TrustServerCertificate=yes;')
    acm_db.set_project_id("9")
    acm_paramter()



   


        

        





