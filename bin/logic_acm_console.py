import logging
import os
import re
import subprocess
import tempfile
import uuid
import time

import pandas as pd

from bin.logic_internal_database import Database
from bin.logic_acm_data_handler import ACM_Data_Handler


class LogFileMonitor:
    """
    Simple log file monitor that can return lines from a log file.
    Useful for monitoring ACM console operations in real-time.
    """
    
    def __init__(self, log_file_path):
        """
        Initialize the log file monitor
        
        :param log_file_path: Path to the log file to monitor
        :type log_file_path: str
        """
        self.log_file_path = log_file_path
        self.last_position = 0
        self.file_size = 0
        
    def get_new_lines(self):
        """
        Get new lines from the log file since last read
        
        :return: List of new lines from the log file
        :rtype: list
        """
        if not os.path.exists(self.log_file_path):
            return []
            
        try:
            current_size = os.path.getsize(self.log_file_path)
            
            # If file was truncated or recreated, reset position
            if current_size < self.file_size:
                self.last_position = 0
                
            self.file_size = current_size
            
            # If no new content, return empty list
            if current_size <= self.last_position:
                return []
                
            with open(self.log_file_path, 'r', encoding='utf-8', errors='ignore') as file:
                file.seek(self.last_position)
                new_content = file.read()
                self.last_position = file.tell()
                
            # Split into lines and filter out empty lines
            lines = [line.strip() for line in new_content.split('\n') if line.strip()]
            return lines
            
        except (IOError, OSError) as e:
            logging.warning(f"Error reading log file {self.log_file_path}: {str(e)}")
            return []
    
    def get_all_lines(self):
        """
        Get all lines from the log file
        
        :return: List of all lines from the log file
        :rtype: list
        """
        if not os.path.exists(self.log_file_path):
            return []
            
        try:
            with open(self.log_file_path, 'r', encoding='utf-8', errors='ignore') as file:
                lines = [line.strip() for line in file.readlines() if line.strip()]
                self.last_position = file.tell()
                self.file_size = os.path.getsize(self.log_file_path)
                return lines
        except (IOError, OSError) as e:
            logging.warning(f"Error reading log file {self.log_file_path}: {str(e)}")
            return []
    
    def reset_position(self):
        """
        Reset the file position to beginning for next read
        """
        self.last_position = 0
        
    def wait_for_new_lines(self, timeout=30, poll_interval=0.5):
        """
        Wait for new lines in the log file with timeout
        
        :param timeout: Maximum time to wait in seconds
        :type timeout: float
        :param poll_interval: Time between checks in seconds
        :type poll_interval: float
        :return: List of new lines found, or empty list if timeout
        :rtype: list
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            new_lines = self.get_new_lines()
            if new_lines:
                return new_lines
            time.sleep(poll_interval)
            
        return []


build_plc_acm_command = '''
GENERATECONTROLLER "{project_name}" "{controller_name}" "{output_path}" "AllACMProjectData" 
'''

build_hmi_acm_command = '''
GENERATEDISPLAYS "{project_name}" "{ft_view_display_object}" "" "{output_path}"
'''

build_alarms_acm_command = '''
GENERATEALARMS "{project_name}" "{controller_name}" "{alarm_object}" "{output_path}"
'''

create_project_acm_command = '''
BEGINCREATE
	CREATEPROJECT "{project_name}" "{extended_script_path}"
ENDCREATE
'''

create_project_acm_xml = '''
<InstanceData>
  <IObjs>
    <IObj Name="@Project" Task="" Program="" Description="{description}" Sol="{solution}" CatalogNumber="{catalog_number}" Maj="{major_revision}" Min="{minor_revision}">
      <IPars />
      <ISObjs />
      <ILLibs />
      <IILinks />
    </IObj>
	</IObjs>
  <ICOObjs />
</InstanceData>
'''


create_controller_acm_command = '''
BEGINCREATE
	CREATECONTROLLER "{project_name}" "{controller_name}" "{extended_script_path}"
ENDCREATE
'''
create_controller_acm_xml = '''
<InstanceData>
  <IObjs>
    <IObj Name="@Controller" Task="" Program="" Description="{description}" Sol="{solution}" CatalogNumber="{catalog_number}" Maj="{major_revision}" Min="{minor_revision}">
      <IPars />
      <ISObjs />
      <ILLibs />
      <IILinks />
    </IObj>
	</IObjs>
  <ICOObjs />
</InstanceData>
'''

create_objects_acm_command = '''
BEGINCREATE
	CREATEOBJECTS "{project_name}" "{controller_name}" "{extended_script_path}"
ENDCREATE
'''

# Combined batch command for running multiple CREATE operations under single BEGINCREATE/ENDCREATE
create_batch_acm_command = '''
BEGINCREATE
{batch_commands}
ENDCREATE
'''

# Individual command templates for batch mode (without BEGINCREATE/ENDCREATE)
create_project_batch_command = '''	CREATEPROJECT "{project_name}" "{extended_script_path}"'''
create_controller_batch_command = '''	CREATECONTROLLER "{project_name}" "{controller_name}" "{extended_script_path}"'''
create_objects_batch_command = '''	CREATEOBJECTS "{project_name}" "{controller_name}" "{extended_script_path}"'''


create_object_acm_xml = '''
    <IObj Name="{name}" ParObj="@Controller" Task="{task}" Program="{program}" Description="{description}" Sol="{solution}" CatalogNumber="{catalog_number}" Maj="{major_revision}" Min="{minor_revision}"/>
'''

create_ft_view_acm_xml = '''
    <IObj Name="FT_View_sever" Sol="(RA-LIB) Process 5" CatalogNumber="FTViewSE" Maj="5" Min="21"/>
'''


create_objects_acm_xml = '''
<InstanceData>
  <IObjs>
    {objects_xml}
	</IObjs>
  <ICOObjs />
</InstanceData>
'''




class ACM_Console:
    """
    This class creates ACM Objects 
    
    Configuration Options:
    - get_acm_batch_create_enabled(): Should return True to enable batch mode where all CREATE 
      commands (CREATEPROJECT, CREATECONTROLLER, CREATEOBJECTS) are wrapped in a single 
      BEGINCREATE/ENDCREATE block, or False for individual mode (default behavior).
    """

    GET_LIBRARY_CMD = 'ACMConsole.exe'
    DEFAULT_ACM_LOCATION = r"C:\Program Files\Rockwell Automation\Application Code Manager\ACMConsole"
    DEFAULT_CONROLLER_NAME = '{project_name}_controller'


    def __init__(self,project_name:str, acm_data_handler:ACM_Data_Handler, db:Database, config) -> None:
        self.__project_name = project_name
        self.__acm_location = self.DEFAULT_ACM_LOCATION
        self.__acm_data_handler = acm_data_handler
        self.__config = config
        self.__db = db
        

    def _is_batch_create_enabled(self):
        """
        Check if batch create mode is enabled from config
        
        :return: True if batch create is enabled, False otherwise
        :rtype: bool
        """
        try:
            return self.__config.get_acm_batch_create_enabled()
        except (AttributeError, TypeError):
            # If config method doesn't exist or returns None, default to False (individual mode)
            return True

    def _get_acm_project_name(self):
        """
        Resolve the project name to use in ACM console commands.

        When the SPA project is linked to an existing ACM project the ACM project name
        can differ from the SPA project name, so the linked name must be used. Falls back
        to the SPA project name when no ACM project is linked (e.g. while creating one).

        :return: The ACM project name to reference in ACM commands
        :rtype: str
        """
        if self.__acm_data_handler is None:
            return self.__project_name

        try:
            acm_project_name = self.__acm_data_handler.get_project_name()
        except Exception as e:
            logging.warning(f"Could not resolve linked ACM project name: {e}")
            return self.__project_name

        return acm_project_name if acm_project_name else self.__project_name

    def _write_controller_software_revision(self):
        """
        Writes the PLC firmware / software revision configured in Settings to the
        `SoftwareRevision` parameter of the newly-created controller object in the
        ACM database.

        Silently no-ops (with a log warning) if the config value is missing, if the
        controller cannot be located, or if the underlying write fails, so that a
        parameter-write hiccup never aborts the outer create flow.
        """
        try:
            software_revision = self.__config.get_acm_controller_software_revision()
        except AttributeError:
            return

        if software_revision is None or str(software_revision).strip() == '':
            return

        if self.__acm_data_handler is None:
            return

        try:
            controller_object_id = self.__acm_data_handler.get_controller_object_id()
        except Exception as e:
            logging.warning(f"Could not locate controller to write SoftwareRevision: {e}")
            return

        if controller_object_id is None:
            logging.warning("No controller found in project when writing SoftwareRevision")
            return

        try:
            self.__acm_data_handler.write_parameter_value(
                str(software_revision), controller_object_id, 'SoftwareRevision'
            )
        except Exception as e:
            logging.warning(f"Failed to write SoftwareRevision to controller: {e}")

    def create_log_monitor(self, log_file_path):
        """
        Create a LogFileMonitor for the given log file
        
        :param log_file_path: Path to the log file to monitor
        :type log_file_path: str
        :return: LogFileMonitor instance
        :rtype: LogFileMonitor
        """
        return LogFileMonitor(log_file_path)

    @staticmethod
    def extract_error_from_log_file(file_path):
        try:
            # Read the file
            with open(file_path, 'r') as file:
                log_text = file.read()
            
            # Regular expression to match error lines
            error_pattern = r'Error.*\[.*\]:\s*(.*)'
            
            # Find all error lines in the log text
            error_lines = re.findall(error_pattern, log_text, re.MULTILINE)
            
            if error_lines:
                # Return the first error found (you can modify this to return all errors if needed)
                return error_lines[0].strip()
            else:
                return "No error found in the log file."
        
        except FileNotFoundError:
            return f"Error: The file {file_path} was not found."
        except IOError:
            return f"Error: There was an issue reading the file {file_path}."
        except Exception as e:
            return f"An unexpected error occurred: {str(e)}"
        


    def execute(self, script, log):
        """
        This function executes the ACM command and logs any errors to the log file
        
        :param script: The script file path
        :type script: str
        :param log: The log file path
        :type log: str
        
        :return: None
        :rtype: None
        
        :raises ValueError: If an error occurs during the execution of the ACM command
        
        """
        try:
            subprocess.check_call([self.__acm_location +'\\'+self.GET_LIBRARY_CMD
                                    , '-p'      # script file mode
                                    , script    # script file path
                                    , '-l'      # log file mode
                                    , log       # log file path
                                    , '-s'])    # silent mode
        except subprocess.CalledProcessError as e:
            error = self.extract_error_from_log_file(log)

            # Ignore all Validation Failure errors
            if "Validation Failure" in error:
                return
            
            logging.error(f"Error: {error}")
            raise ValueError(f"ACM Error {error}")
        except Exception as e:
            logging.error(f"An unexpected error occurred: {str(e)}")
            raise ValueError(f"An unexpected error occurred: {str(e)}")
        

    def execute_with_log_monitoring(self, script, log, progress_callback=None):
        """
        Execute ACM command with real-time log monitoring
        
        :param script: The script file path
        :type script: str
        :param log: The log file path
        :type log: str
        :param progress_callback: Optional progress callback function
        :param log_callback: Optional callback function that receives new log lines
        :return: None
        :rtype: None
        :raises ValueError: If an error occurs during the execution of the ACM command
        :raises ProcessCancelled: If the user cancels the operation via ``progress_callback``.
        """

        # Local import to avoid a hard dependency on the GUI module at import time.
        from bin.gui_textbox_progressbar_window import ProcessCancelled

        def _check_cancel(proc):
            """Poll ``progress_callback`` for a cancel request; kill ACM if requested."""
            if progress_callback is None:
                return False
            try:
                should_stop = progress_callback(None, None)
            except TypeError:
                # Callback doesn't support (None, None) poll form; skip polling.
                return False
            if should_stop:
                try:
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                except Exception as kill_error:
                    logging.warning(f"Failed to terminate ACM subprocess on cancel: {kill_error}")
                return True
            return False

        # Create log monitor
        log_monitor = LogFileMonitor(log)
        
        try:
            # Start the ACM process
            process = subprocess.Popen([self.__acm_location +'\\'+self.GET_LIBRARY_CMD
                                       , '-p'      # script file mode
                                       , script    # script file path
                                       , '-l'      # log file mode
                                       , log       # log file path
                                       , '-s'])    # silent mode
            
            # Monitor the process and log file
            while process.poll() is None:
                # Poll for cancellation even when no new log lines are produced.
                if _check_cancel(process):
                    raise ProcessCancelled()

                # Get new log lines
                new_lines = log_monitor.get_new_lines()
                
                # Call log callback with new lines if provided
                if progress_callback and new_lines:
                    for line in new_lines:
                        # Extract just the message part after the bracket section
                        # Pattern: Info	2025-09-03T15:42:59.5066775+02:00	[ExportXLS_Objects]:	Exporting Objects
                        # We want to keep only: Exporting Objects
                        if ']\t' in line or ']:\t' in line:
                            # Find the last occurrence of ]:\t or ]\t and take everything after it
                            if ']:\t' in line:
                                textbox_entry = line.split(']:\t', 1)[-1].strip()
                            else:
                                textbox_entry = line.split(']\t', 1)[-1].strip()
                        else:
                            textbox_entry = line
                        label_text = 'ACM Processing'

                        if progress_callback(textbox_entry, label_text):
                            try:
                                process.terminate()
                                try:
                                    process.wait(timeout=5)
                                except subprocess.TimeoutExpired:
                                    process.kill()
                            except Exception as kill_error:
                                logging.warning(f"Failed to terminate ACM subprocess on cancel: {kill_error}")
                            raise ProcessCancelled()
                
                # Small delay to avoid excessive CPU usage
                time.sleep(0.1)
            
            # Get any remaining log lines after process completes
            final_lines = log_monitor.get_new_lines()
            if progress_callback and final_lines:
                for line in final_lines:
                    # Extract just the message part after the bracket section
                    # Pattern: Info	2025-09-03T15:42:59.5066775+02:00	[ExportXLS_Objects]:	Exporting Objects
                    # We want to keep only: Exporting Objects
                    if ']\t' in line or ']:\t' in line:
                        # Find the last occurrence of ]:\t or ]\t and take everything after it
                        if ']:\t' in line:
                            textbox_entry = line.split(']:\t', 1)[-1].strip()
                        else:
                            textbox_entry = line.split(']\t', 1)[-1].strip()
                    else:
                        textbox_entry = line
                    label_text = 'ACM Processing'

                    if progress_callback:
                        progress_callback(textbox_entry,label_text)
            
            # Check the return code
            return_code = process.returncode
            if return_code != 0:
                error = self.extract_error_from_log_file(log)
                
                # Ignore all Validation Failure errors
                if "Validation Failure" in error:
                    return
                
                logging.error(f"Error: {error}")
                raise ValueError(f"ACM Error {error}")

        except ProcessCancelled:
            # Let the cancellation propagate to the top-level worker.
            raise
        except subprocess.SubprocessError as e:
            error = self.extract_error_from_log_file(log)
            
            # Ignore all Validation Failure errors
            if "Validation Failure" in error:
                return
            
            logging.error(f"Error: {error}")
            raise ValueError(f"ACM Error {error}")
        except Exception as e:
            logging.error(f"An unexpected error occurred: {str(e)}")
            raise ValueError(f"An unexpected error occurred: {str(e)}")


    def create_acm_project(self,progress_callback, solution:str='', catalog_number:str='', major_revision:str='', minor_revision:str=''
                           ,link_project_function=None):
        """
        This function creates a new ACM project
        
        :param solution: The solution of the ACM object
        :type solution: str
        :param catalog_number: The catalog number of the ACM object
        :type catalog_number: str
        :param major_revision: The major revision of the ACM object
        :type major_revision: str
        :param minor_revision: The minor revision of the ACM object
        :type minor_revision: str

        :return: None
        :rtype: None
        """

        # Check if batch create mode is enabled
        if self._is_batch_create_enabled():
            return self.create_acm_project_batch(progress_callback, solution, catalog_number, major_revision, minor_revision, link_project_function)

        # Original individual create mode
        # Create a temporary file to store the extended script
        fd, extended_script = tempfile.mkstemp(suffix = '.xml')
        os.close(fd)
        with open(extended_script, "w") as text_file:
            text_file.write(create_project_acm_xml.format(
                description = self.__project_name,
                solution = solution,
                catalog_number = catalog_number,
                major_revision = major_revision,
                minor_revision = minor_revision
            ))

        # Create a temporary file to store the command
        fd, script = tempfile.mkstemp(suffix = '.tp')
        os.close(fd)
        with open(script, "w") as text_file:
            text_file.write(create_project_acm_command.format(
                project_name = self.__project_name,
                extended_script_path = extended_script
                ))
            

        # Create a temporary file to store the log
        fd, log = tempfile.mkstemp(suffix = '.log')
        os.close(fd)
        
        textbox_entry = 'Creating Project'
        label_text = 'Creating Project'
        percentage = 0

        if progress_callback and progress_callback(textbox_entry,label_text,percentage):
            return
        
        # Execute the command
        self.execute_with_log_monitoring(script, log, progress_callback)
        
        textbox_entry = 'Done creating Project'
        label_text = 'Creating Project'
        percentage = 0


        if progress_callback:
            progress_callback(textbox_entry,label_text,percentage)

        controller_library_array = self.__config.get_acm_controller()

        if controller_library_array is None:
            raise ValueError('Controller Library not set in Settings. Please go Tools > Setting to set the controller library.')

        self.create_acm_controller(progress_callback, controller_library_array[0]
                                   , controller_library_array[1]
                                   , controller_library_array[2]
                                   , controller_library_array[3])
        

        if link_project_function is None:
            return

        projects_df = self.__acm_data_handler.get_all_projects()

        # Get the project id description using the project name
        project_id = projects_df[projects_df['Name'] == self.__project_name].index[0]
        project_description = projects_df.loc[project_id]['Description']

        
        link_project_function(self.__project_name, [project_description, str(project_id)])



        

    def create_acm_project_batch(self, progress_callback, solution:str='', catalog_number:str='', major_revision:str='', minor_revision:str='',
                                 link_project_function=None):
        """
        This function creates a new ACM project using batch mode (single BEGINCREATE/ENDCREATE)
        
        :param solution: The solution of the ACM object
        :type solution: str
        :param catalog_number: The catalog number of the ACM object
        :type catalog_number: str
        :param major_revision: The major revision of the ACM object
        :type major_revision: str
        :param minor_revision: The minor revision of the ACM object
        :type minor_revision: str

        :return: None
        :rtype: None
        """

        controller_library_array = self.__config.get_acm_controller()
        if controller_library_array is None:
            raise ValueError('Controller Library not set in Settings. Please go Tools > Setting to set the controller library.')

        program_name = self.__config.get_acm_controller_program()
        task_name = self.__config.get_acm_controller_task()

        if program_name == '':
            raise ValueError('Controller Program not set in Settings. Please go Tools > Setting to set the controller program.')
        
        if task_name == '':
            raise ValueError('Controller Task not set in Settings. Please go Tools > Setting to set the controller task.')

        # Create temporary files for project XML
        fd_project, project_extended_script = tempfile.mkstemp(suffix = '.xml')
        os.close(fd_project)
        with open(project_extended_script, "w") as text_file:
            text_file.write(create_project_acm_xml.format(
                description = self.__project_name,
                solution = solution,
                catalog_number = catalog_number,
                major_revision = major_revision,
                minor_revision = minor_revision
            ))

        # Create temporary files for controller XML
        fd_controller, controller_extended_script = tempfile.mkstemp(suffix = '.xml')
        os.close(fd_controller)
        with open(controller_extended_script, "w") as text_file:
            text_file.write(create_controller_acm_xml.format(
                description = self.__project_name,
                solution = controller_library_array[0],
                catalog_number = controller_library_array[1],
                major_revision = controller_library_array[2],
                minor_revision = controller_library_array[3]
            ))

        controller_name = self.DEFAULT_CONROLLER_NAME.format(project_name = self.__project_name)

        # Build batch commands
        batch_commands = []
        
        batch_commands.append(create_project_batch_command.format(
            project_name = self.__project_name,
            extended_script_path = project_extended_script
        ))
        
        batch_commands.append(create_controller_batch_command.format(
            project_name = self.__project_name,
            controller_name = controller_name,
            extended_script_path = controller_extended_script
        ))

        

        # Create the batch script
        fd, script = tempfile.mkstemp(suffix = '.tp')
        os.close(fd)
        with open(script, "w") as text_file:
            text_file.write(create_batch_acm_command.format(
                batch_commands = '\n'.join(batch_commands)
            ))

        # Create a temporary file to store the log
        fd, log = tempfile.mkstemp(suffix = '.log')
        os.close(fd)
        
        textbox_entry = 'Creating Project and Controllerin batch mode'
        label_text = 'Batch Creating Project'
        percentage = 0

        if progress_callback and progress_callback(textbox_entry,label_text,percentage):
            return
        
        # Execute the batch command
        self.execute_with_log_monitoring(script, log, progress_callback)
        
        textbox_entry = 'Done creating Project and Controller'
        label_text = 'Batch Creating Project'
        percentage = 100

        if progress_callback:
            progress_callback(textbox_entry,label_text,percentage)

        # Write PLC firmware / software revision from Settings to the new controller
        self._write_controller_software_revision()

        if link_project_function is None:
            return

        projects_df = self.__acm_data_handler.get_all_projects()
        project_id = projects_df[projects_df['Name'] == self.__project_name].index[0]
        project_description = projects_df.loc[project_id]['Description']
        
        link_project_function(self.__project_name, [project_description, str(project_id)])


    def create_acm_controller(self,progress_callback, solution:str='', catalog_number:str='', major_revision:str='', minor_revision:str=''):
        """
        This function creates a new ACM controller
        
        :param solution: The solution of the ACM object
        :type solution: str
        :param catalog_number: The catalog number of the ACM object
        :type catalog_number: str
        :param major_revision: The major revision of the ACM object
        :type major_revision: str
        :param minor_revision: The minor revision of the ACM object
        :type minor_revision: str

        :return: None
        :rtype: None
        """

        # Check if batch create mode is enabled
        if self._is_batch_create_enabled():
            return self.create_acm_controller_batch(progress_callback, solution, catalog_number, major_revision, minor_revision)

        # Original individual create mode
        fd, extended_script = tempfile.mkstemp(suffix = '.xml')
        os.close(fd)
        with open(extended_script, "w") as text_file:
            text_file.write(create_controller_acm_xml.format(
                description = self.__project_name,
                solution = solution,
                catalog_number = catalog_number,
                major_revision = major_revision,
                minor_revision = minor_revision
            ))
        fd, script = tempfile.mkstemp(suffix = '.tp')
        os.close(fd)
        with open(script, "w") as text_file:
            text_file.write(create_controller_acm_command.format(
                project_name = self._get_acm_project_name(),
                controller_name = self.DEFAULT_CONROLLER_NAME.format(project_name = self.__project_name),
                extended_script_path = extended_script
                ))
        
        
        # Create a temporary file to store the log
        fd, log = tempfile.mkstemp(suffix = '.log')
        os.close(fd)
        
        
        textbox_entry = 'Creating Controller'
        label_text = 'Creating Controller'
        percentage = 0

        if progress_callback and progress_callback(textbox_entry,label_text,percentage):
            return
        
        # Execute the command
        self.execute_with_log_monitoring(script, log, progress_callback)
        
        textbox_entry = 'Done creating Controller'
        label_text = 'Creating Controller'
        percentage = 0

        progress_callback(textbox_entry,label_text,percentage)

        # Write PLC firmware / software revision from Settings to the new controller
        self._write_controller_software_revision()

        self.create_assigned_acm_objects(progress_callback)


    def create_acm_controller_batch(self, progress_callback, solution:str='', catalog_number:str='', major_revision:str='', minor_revision:str=''):
        """
        This function creates a new ACM controller using batch mode (single BEGINCREATE/ENDCREATE)
        
        :param solution: The solution of the ACM object
        :type solution: str
        :param catalog_number: The catalog number of the ACM object
        :type catalog_number: str
        :param major_revision: The major revision of the ACM object
        :type major_revision: str
        :param minor_revision: The minor revision of the ACM object
        :type minor_revision: str

        :return: None
        :rtype: None
        """

        program_name = self.__config.get_acm_controller_program()
        task_name = self.__config.get_acm_controller_task()

        if program_name == '':
            raise ValueError('Controller Program not set in Settings. Please go Tools > Setting to set the controller program.')
        
        if task_name == '':
            raise ValueError('Controller Task not set in Settings. Please go Tools > Setting to set the controller task.')

        # Create temporary files for controller XML
        fd_controller, controller_extended_script = tempfile.mkstemp(suffix = '.xml')
        os.close(fd_controller)
        with open(controller_extended_script, "w") as text_file:
            text_file.write(create_controller_acm_xml.format(
                description = self.__project_name,
                solution = solution,
                catalog_number = catalog_number,
                major_revision = major_revision,
                minor_revision = minor_revision
            ))

        controller_name = self.DEFAULT_CONROLLER_NAME.format(project_name = self.__project_name)
        acm_project_name = self._get_acm_project_name()

        # Build batch commands
        batch_commands = []
        
        batch_commands.append(create_controller_batch_command.format(
            project_name = acm_project_name,
            controller_name = controller_name,
            extended_script_path = controller_extended_script
        ))

        # Add objects creation if there are objects to create
        acm_db_df = self.__get_acm_objects()
        internal_db_df = self.__get_internal_db_objects()

        if not internal_db_df.empty:
            if not acm_db_df.empty:
                internal_db_only_df = internal_db_df.loc[~internal_db_df['Name'].isin(acm_db_df['Name'])].copy()
            else:
                internal_db_only_df = internal_db_df
            
            regexs = self.__db.get_all_object_assignment_regexs()

            def remove_brackets(text):
                result = ""
                inside_brackets = False
                
                for char in text:
                    if char == '(':
                        inside_brackets = True
                    elif char == ')':
                        inside_brackets = False
                    elif not inside_brackets:
                        result += char
                        
                return result

            sorted_regexs = sorted(regexs, key=lambda x: len(remove_brackets(x['regex'])), reverse=True)
            processed_objects = {}
            
            for regex in sorted_regexs:
                matching_objects = self.search_objects(regex['regex'], internal_db_only_df)
                matching_objects = matching_objects.loc[~matching_objects['Name'].isin(processed_objects.keys())].copy()
                new_objects = self.__matching_objects_object_assignment(matching_objects, program_name, task_name)
                
                data = {
                    'solution': regex['library'][1],
                    'catalog_number': regex['library'][2],
                    'major_revision': regex['library'][3],
                    'minor_revision': regex['library'][4],
                    'objects': new_objects
                }
                
                if regex['library'][0] not in processed_objects:
                    processed_objects[regex['library'][0]] = data
                else:
                    processed_objects[regex['library'][0]]['objects'].update(new_objects)

            # Create objects batch commands and XML files for each library type
            for _, data in processed_objects.items():
                if len(data['objects']) == 0:
                    continue

                # Create objects XML for this library type
                fd_objects, objects_extended_script = tempfile.mkstemp(suffix = '.xml')
                os.close(fd_objects)
                with open(objects_extended_script, "w") as text_file:
                    objects_xml = ''
                    for object_name, obj in data['objects'].items():
                        objects_xml += create_object_acm_xml.format(
                            name = object_name,
                            description = obj['description'],
                            task = obj['task'],
                            program = obj['program'],
                            solution = data['solution'],
                            catalog_number = data['catalog_number'],
                            major_revision = data['major_revision'],
                            minor_revision = data['minor_revision']
                        )
                    text_file.write(create_objects_acm_xml.format(
                        objects_xml = objects_xml
                    ))

                batch_commands.append(create_objects_batch_command.format(
                    project_name = acm_project_name,
                    controller_name = controller_name,
                    extended_script_path = objects_extended_script
                ))

        # Create the batch script
        fd, script = tempfile.mkstemp(suffix = '.tp')
        os.close(fd)
        with open(script, "w") as text_file:
            text_file.write(create_batch_acm_command.format(
                batch_commands = '\n'.join(batch_commands)
            ))

        # Create a temporary file to store the log
        fd, log = tempfile.mkstemp(suffix = '.log')
        os.close(fd)
        
        textbox_entry = 'Creating Controller and Objects in batch mode'
        label_text = 'Batch Creating Controller'
        percentage = 0

        if progress_callback and progress_callback(textbox_entry,label_text,percentage):
            return
        
        # Execute the batch command
        self.execute_with_log_monitoring(script, log, progress_callback)
        
        textbox_entry = 'Done creating Controller and Objects'
        label_text = 'Batch Creating Controller'
        percentage = 100

        if progress_callback:
            progress_callback(textbox_entry,label_text,percentage)

        # Write PLC firmware / software revision from Settings to the new controller
        self._write_controller_software_revision()


    def create_assigned_acm_objects(self, progress_callback):
        # Check if batch create mode is enabled
        if self._is_batch_create_enabled():
            return self.create_assigned_acm_objects_batch(progress_callback)

        # Original individual create mode
        acm_db_df = self.__get_acm_objects()
        internal_db_df = self.__get_internal_db_objects()

        program_name = self.__config.get_acm_controller_program()
        task_name = self.__config.get_acm_controller_task()

        if program_name == '':
            raise ValueError('Controller Program not set in Settings. Please go Tools > Setting to set the controller program.')
        
        if task_name == '':
            raise ValueError('Controller Task not set in Settings. Please go Tools > Setting to set the controller task.')

        if internal_db_df.empty:
            return
        
        if not acm_db_df.empty:
            internal_db_only_df = internal_db_df.loc[~internal_db_df['Name'].isin(acm_db_df['Name'])].copy()
        else:
            internal_db_only_df = internal_db_df
        
        regexs = self.__db.get_all_object_assignment_regexs()

        def remove_brackets(text):
            # Initialize result string
            result = ""
            # Flag to track if we're inside brackets
            inside_brackets = False
            
            for char in text:
                if char == '(':
                    inside_brackets = True
                elif char == ')':
                    inside_brackets = False
                elif not inside_brackets:
                    result += char
                    
            return result

        sorted_regexs = sorted(regexs, key=lambda x: len(remove_brackets(x['regex'])), reverse=True)

        
        controller_name = self.__acm_data_handler.get_controller_name()
        if controller_name == '':
            controller_name = self.DEFAULT_CONROLLER_NAME.format(project_name = self.__project_name)

        # Uses the processed_objects list to keep track of which objects have already been assigned a type
        processed_objects = {}
        total_objects = 0
        for regex in sorted_regexs:
            matching_objects = self.search_objects(regex['regex'], internal_db_only_df)
            matching_objects = matching_objects.loc[~matching_objects['Name'].isin(processed_objects.keys())].copy()
            new_objects = self.__matching_objects_object_assignment(matching_objects
                                                                    , program_name
                                                                    , task_name)
            
            # '(RA-LIB) Process 5', 'PAI', '2', '0'
            data = {
                'solution': regex['library'][1],
                'catalog_number': regex['library'][2],
                'major_revision': regex['library'][3],
                'minor_revision': regex['library'][4],
                'objects': new_objects
            }
            if regex['library'][0] not in processed_objects:
                processed_objects[regex['library'][0]] = data
            else:
                processed_objects[regex['library'][0]]['objects'].update(new_objects)

            total_objects = total_objects + len(new_objects)

        number_objects_processed = 0
        for _, data in processed_objects.items():
            
            if len(data['objects']) == 0:
                continue

            number_objects_processed, stop =self.create_acm_objects(controller_name
                                            , data['objects']
                                            , data['solution']
                                            , data['catalog_number']
                                            , data['major_revision']
                                            , data['minor_revision']
                                            , progress_callback
                                            , total_objects
                                            , number_objects_processed)
            
            if stop:
                break


    def create_assigned_acm_objects_batch(self, progress_callback):
        """
        This function creates assigned ACM objects using batch mode (single BEGINCREATE/ENDCREATE)
        
        :param progress_callback: Progress callback function
        :return: None
        :rtype: None
        """
        
        acm_db_df = self.__get_acm_objects()
        internal_db_df = self.__get_internal_db_objects()

        program_name = self.__config.get_acm_controller_program()
        task_name = self.__config.get_acm_controller_task()

        if program_name == '':
            raise ValueError('Controller Program not set in Settings. Please go Tools > Setting to set the controller program.')
        
        if task_name == '':
            raise ValueError('Controller Task not set in Settings. Please go Tools > Setting to set the controller task.')

        if internal_db_df.empty:
            return
        
        if not acm_db_df.empty:
            internal_db_only_df = internal_db_df.loc[~internal_db_df['Name'].isin(acm_db_df['Name'])].copy()
        else:
            internal_db_only_df = internal_db_df
        
        regexs = self.__db.get_all_object_assignment_regexs()

        def remove_brackets(text):
            result = ""
            inside_brackets = False
            
            for char in text:
                if char == '(':
                    inside_brackets = True
                elif char == ')':
                    inside_brackets = False
                elif not inside_brackets:
                    result += char
                    
            return result

        sorted_regexs = sorted(regexs, key=lambda x: len(remove_brackets(x['regex'])), reverse=True)

        controller_name = self.__acm_data_handler.get_controller_name()
        if controller_name == '':
            controller_name = self.DEFAULT_CONROLLER_NAME.format(project_name = self.__project_name)

        # Uses the processed_objects list to keep track of which objects have already been assigned a type
        processed_objects = {}
        
        for regex in sorted_regexs:
            matching_objects = self.search_objects(regex['regex'], internal_db_only_df)
            matching_objects = matching_objects.loc[~matching_objects['Name'].isin(processed_objects.keys())].copy()
            new_objects = self.__matching_objects_object_assignment(matching_objects, program_name, task_name)
            
            data = {
                'solution': regex['library'][1],
                'catalog_number': regex['library'][2],
                'major_revision': regex['library'][3],
                'minor_revision': regex['library'][4],
                'objects': new_objects
            }
            
            if regex['library'][0] not in processed_objects:
                processed_objects[regex['library'][0]] = data
            else:
                processed_objects[regex['library'][0]]['objects'].update(new_objects)

        if not processed_objects:
            return

        # Build batch commands
        batch_commands = []

        all_processed_objects_names = []

        # Create objects batch commands and XML files for each library type
        for _, data in processed_objects.items():
            if len(data['objects']) == 0:
                continue

            # Create objects XML for this library type
            fd_objects, objects_extended_script = tempfile.mkstemp(suffix = '.xml')
            os.close(fd_objects)
            with open(objects_extended_script, "w") as text_file:
                objects_xml = ''
                for object_name, obj in data['objects'].items():
                    if object_name in all_processed_objects_names:
                        continue
                    objects_xml += create_object_acm_xml.format(
                        name = object_name,
                        description = obj['description'],
                        task = obj['task'],
                        program = obj['program'],
                        solution = data['solution'],
                        catalog_number = data['catalog_number'],
                        major_revision = data['major_revision'],
                        minor_revision = data['minor_revision']
                    )
                    all_processed_objects_names.append(object_name)
                text_file.write(create_objects_acm_xml.format(
                    objects_xml = objects_xml
                ))

            batch_commands.append(create_objects_batch_command.format(
                project_name = self._get_acm_project_name(),
                controller_name = controller_name,
                extended_script_path = objects_extended_script
            ))

        if not batch_commands:
            return

        # Create the batch script
        fd, script = tempfile.mkstemp(suffix = '.tp')
        os.close(fd)
        with open(script, "w") as text_file:
            text_file.write(create_batch_acm_command.format(
                batch_commands = '\n'.join(batch_commands)
            ))

        # Create a temporary file to store the log
        fd, log = tempfile.mkstemp(suffix = '.log')
        os.close(fd)
        
        textbox_entry = 'Creating Objects in batch mode'
        label_text = 'Batch Creating Objects'
        percentage = 0

        if progress_callback and progress_callback(textbox_entry,label_text,percentage):
            return
        
        # Execute the batch command
        self.execute_with_log_monitoring(script, log, progress_callback)
        
        textbox_entry = 'Done creating Objects'
        label_text = 'Batch Creating Objects'
        percentage = 100

        if progress_callback:
            progress_callback(textbox_entry,label_text,percentage)


    def search_objects(self, regex_string, internal_db_only_df):
        return internal_db_only_df[internal_db_only_df['Name'].str.match(regex_string)]


    
    def __matching_objects_object_assignment(self, matching_objects, program_name, task_name):
        objects = {}
        # 'TIT001': {'task':'Fast', 'program':'FastProgram' ,'description':'Process 5 Title Object'},
        for _, row in matching_objects.iterrows():
            objects[row['Name']] = {
                                    'task':task_name
                                    , 'program':program_name 
                                    ,'description':' SPA Generated Object'
                                    }
            
        return objects
            
            
        

    def __get_acm_objects(self):
    
        if self.__acm_data_handler is None:
            return
        
        all_object = self.__acm_data_handler.get_all_objects_in_project()

        if all_object.empty:
            # Return empty dataframe if no objects
            return pd.DataFrame() 
        
        frame = {
                    'id':all_object.index,
                    'Name':all_object['Name'],
                    'Type':all_object['CatalogNumber']
        }
        return pd.DataFrame(frame)
        


    def __get_internal_db_objects(self):
        if self.__db is None:
            return 
        
        self.__control_modules = self.__db.get_all_control_modules()

        list = []
        for control_module in self.__control_modules:
            if 'id' not in  control_module:
                control_module['id'] = str(uuid.uuid4())
            d = {
                'id':control_module['id'],
                'Name':control_module['name'],
                'Type':control_module['type'],
            }
            list.append(d)

        internal_db_df = pd.DataFrame(list)
        return internal_db_df
    
        


    def create_acm_objects(self,controller_name, objects:dict, solution:str='', catalog_number:str='', major_revision:str='', minor_revision:str=''
                           , progress_callback=None, total_number_objects=1, number_objects_processed=0):
        """
        This function creates a new ACM objects in batches of BATCH_SIZE
        
        :param objects: The dict of objects to be created with the object name as the key and a list of task, program and description as the value
        :type objects: dict
        :param solution: The solution of the ACM object
        :type solution: str
        :param catalog_number: The catalog number of the ACM object
        :type catalog_number: str
        :param major_revision: The major revision of the ACM object
        :type major_revision: str
        :param minor_revision: The minor revision of the ACM object
        :type minor_revision: str

        :return: None
        :rtype: None
        """
        textbox_entry = 'Creating '+ catalog_number + ' ' + solution
        label_text = 'Creating '+ catalog_number + ' ' + solution
        percentage = (number_objects_processed/total_number_objects)*100.0

        if progress_callback and progress_callback(textbox_entry,label_text,percentage):
            return number_objects_processed, True

        BATCH_SIZE = 5

        #split the objects into batches of BATCH_SIZE
        for i in range(0, len(objects), BATCH_SIZE):
            objects_created = ''
            batch = dict(list(objects.items())[i:i+BATCH_SIZE])
            fd, extended_script = tempfile.mkstemp(suffix = '.xml')
            os.close(fd)
            with open(extended_script, "w") as text_file:
                objects_xml = ''
                for object_name, obj in batch.items():
                    objects_created = objects_created +'\n'+ object_name + ','
                    objects_xml += create_object_acm_xml.format(
                        name = object_name,
                        description = obj['description'],
                        task = obj['task'],
                        program = obj['program'],
                        solution = solution,
                        catalog_number = catalog_number,
                        major_revision = major_revision,
                        minor_revision = minor_revision
                    )
                text_file.write(create_objects_acm_xml.format(
                    objects_xml = objects_xml
                ))
            fd, script = tempfile.mkstemp(suffix = '.tp')
            os.close(fd)
            with open(script, "w") as text_file:
                text_file.write(create_objects_acm_command.format(
                    project_name = self._get_acm_project_name(),
                    controller_name = controller_name,
                    extended_script_path = extended_script
                    ))
                
            # Create a temporary file to store the log
            fd, log = tempfile.mkstemp(suffix = '.log')
            os.close(fd)
            
            # Execute the command
            self.execute_with_log_monitoring(script, log, progress_callback)
            
            if progress_callback:
                # Remove the first newline 
                objects_created = objects_created[1:]

                if i+BATCH_SIZE > len(objects):
                    total = number_objects_processed + len(objects)
                    percentage = total/total_number_objects*100
                    progress_callback(objects_created,label_text,percentage)
                else:
                    total = number_objects_processed + (i+BATCH_SIZE)
                    percentage = total/total_number_objects*100
                    if progress_callback(objects_created,label_text,percentage):
                        return total, True


        return number_objects_processed + len(objects), False


    def create_acm_objects_batch(self, controller_name, objects_by_library:dict, progress_callback=None, total_number_objects=1, number_objects_processed=0):
        """
        This function creates ACM objects in batch mode (single BEGINCREATE/ENDCREATE for all library types)
        
        :param controller_name: The controller name
        :type controller_name: str
        :param objects_by_library: Dictionary with library info as keys and objects dict as values
        :type objects_by_library: dict
        :param progress_callback: Progress callback function
        :param total_number_objects: Total number of objects to process
        :param number_objects_processed: Number of objects already processed
        
        :return: Tuple of (number_objects_processed, stop_flag)
        :rtype: tuple
        """
        
        if not objects_by_library:
            return number_objects_processed, False
            
        textbox_entry = 'Creating Objects in batch mode'
        label_text = 'Batch Creating Objects'
        percentage = (number_objects_processed/total_number_objects)*100.0

        if progress_callback and progress_callback(textbox_entry, label_text, percentage):
            return number_objects_processed, True

        batch_commands = []
        
        # Create XML files and batch commands for each library type
        for library_key, data in objects_by_library.items():
            if len(data['objects']) == 0:
                continue
                
            # Create objects XML for this library type
            fd_objects, objects_extended_script = tempfile.mkstemp(suffix = '.xml')
            os.close(fd_objects)
            with open(objects_extended_script, "w") as text_file:
                objects_xml = ''
                for object_name, obj in data['objects'].items():
                    objects_xml += create_object_acm_xml.format(
                        name = object_name,
                        description = obj['description'],
                        task = obj['task'],
                        program = obj['program'],
                        solution = data['solution'],
                        catalog_number = data['catalog_number'],
                        major_revision = data['major_revision'],
                        minor_revision = data['minor_revision']
                    )
                text_file.write(create_objects_acm_xml.format(
                    objects_xml = objects_xml
                ))

            batch_commands.append(create_objects_batch_command.format(
                project_name = self._get_acm_project_name(),
                controller_name = controller_name,
                extended_script_path = objects_extended_script
            ))

        if not batch_commands:
            return number_objects_processed, False

        # Create the batch script
        fd, script = tempfile.mkstemp(suffix = '.tp')
        os.close(fd)
        with open(script, "w") as text_file:
            text_file.write(create_batch_acm_command.format(
                batch_commands = '\n'.join(batch_commands)
            ))

        # Create a temporary file to store the log
        fd, log = tempfile.mkstemp(suffix = '.log')
        os.close(fd)
        
        # Execute the batch command
        self.execute_with_log_monitoring(script, log, progress_callback)
        
        # Count total objects
        total_objects = sum(len(data['objects']) for data in objects_by_library.values())
        
        if progress_callback:
            objects_created = []
            for data in objects_by_library.items():
                objects_created.extend(data[1]['objects'].keys())
            
            objects_created_str = '\n'.join(objects_created)
            percentage = ((number_objects_processed + total_objects)/total_number_objects)*100
            progress_callback(objects_created_str, label_text, percentage)

        return number_objects_processed + total_objects, False
    


    def build_plc(self, output_path, controller_name=None, progress_callback=None):
        """
        This function builds the PLC project
        
        :return: None

        :rtype: None

        :raises ValueError: If an error occurs during the execution of the ACM command

        """

        if controller_name is None:
            controller_name = self.__acm_data_handler.get_controller_name()

        if not controller_name:
            raise ValueError('No Controller. Please go Tools > Create ACM Project or maunally create a controller in ACM.')


        textbox_entry = 'Building '+ controller_name + ' PLC'
        label_text = 'Building '+ controller_name + ' PLC'
        percentage = 0

        if progress_callback:
            progress_callback(textbox_entry,label_text,percentage)

        # Create a temporary file to store the command
        fd, script = tempfile.mkstemp(suffix = '.tp')
        os.close(fd)
        with open(script, "w") as text_file:
            text_file.write(build_plc_acm_command.format(
                project_name = self._get_acm_project_name(),
                controller_name = controller_name,
                output_path = output_path + '\\' + controller_name + '.L5X'
                ))
        
        # Create a temporary file to store the log
        fd, log = tempfile.mkstemp(suffix = '.log')
        os.close(fd)
        
        # Execute the command
        self.execute_with_log_monitoring(script, log, progress_callback)


    def build_plc_acd(self, output_path, controller_name=None, progress_callback=None):
            """
            This function builds the PLC project
            
            :return: None
    
            :rtype: None
    
            :raises ValueError: If an error occurs during the execution of the ACM command
    
            """
    
            if controller_name is None:
                controller_name = self.__acm_data_handler.get_controller_name()
    
            if not controller_name:
                raise ValueError('No Controller. Please go Tools > Create ACM Project or maunally create a controller in ACM.')
    
    
            textbox_entry = 'Building '+ controller_name + ' PLC'
            label_text = 'Building '+ controller_name + ' PLC'
            percentage = 0
    
            if progress_callback:
                progress_callback(textbox_entry,label_text,percentage)
    
            # Create a temporary file to store the command
            fd, script = tempfile.mkstemp(suffix = '.tp')
            os.close(fd)
            with open(script, "w") as text_file:
                text_file.write(build_plc_acm_command.format(
                    project_name = self._get_acm_project_name(),
                    controller_name = controller_name,
                    output_path = output_path + '\\' + controller_name + '.ACD'
                    ))
            
            # Create a temporary file to store the log
            fd, log = tempfile.mkstemp(suffix = '.log')
            os.close(fd)
            
            # Execute the command
            self.execute_with_log_monitoring(script, log, progress_callback)


    def create_alarm_object(self):
        """
        This function creates the Alarm object

        :return: None
        :rtype: None
        """

        alarm_object = {
        'FTView_Alarms': {'task':'', 'program':'' ,'description':'FactoryTalk View Alarms'}
        }

        core_type, catalog_number, major_version, minor_version = self.__config.get_alarm_library()

        controller_name = self.__acm_data_handler.get_controller_name()

        if not controller_name:
            raise ValueError('No Controller. Please go Tools > Create ACM Project or maunally create a controller in ACM.')

        self.create_acm_objects(controller_name,alarm_object, core_type ,catalog_number ,major_version ,minor_version)


    def create_hmi_object(self):
        """
        This function creates the HMI object

        :return: None
        :rtype: None
        """

        hmi_object = {
        'FTView_Server': {'task':'', 'program':'' ,'description':'FactoryTalk View Display'}
        }

        core_type, catalog_number, major_version, minor_version = self.__config.get_hmi_library()

        controller_name = self.__acm_data_handler.get_controller_name()

        if not controller_name:
            raise ValueError('No Controller. Please go Tools > Create ACM Project or maunally create a controller in ACM.')

        self.create_acm_objects(controller_name,hmi_object, core_type ,catalog_number ,major_version ,minor_version)
        


    def build_hmi(self, output_path, ft_view_display_object=None, progress_callback=None, min_progress=0, max_progress=100):
        """
        This function builds the HMI project
        
        :return: None
        :rtype: None

        :raises ValueError: If an error occurs during the execution of the ACM command

        """

        if ft_view_display_object is None:
            ft_view_display_object = self.__project_name+'_controller'

        textbox_entry = 'Building '+ ft_view_display_object + ' HMI'
        label_text = 'Building '+ ft_view_display_object + ' HMI'


        if progress_callback:
            progress_callback(textbox_entry,label_text,min_progress)

        # Create a temporary file to store the command
        fd, script = tempfile.mkstemp(suffix = '.tp')
        os.close(fd)
        with open(script, "w") as text_file:
            text_file.write(build_hmi_acm_command.format(
                project_name = self._get_acm_project_name(),
                ft_view_display_object = ft_view_display_object,
                output_path = output_path
                ))
        
        # Create a temporary file to store the log
        fd, log = tempfile.mkstemp(suffix = '.log')
        os.close(fd)
        
        # Execute the command
        self.execute_with_log_monitoring(script, log, progress_callback)



    def export_alarms(self, output_path, controller_name=None, alarm_object=None, progress_callback=None):
        """
        This function builds the alarms
        
        :return: None
        :rtype: None
        """
            
        if controller_name is None:
            controller_name = ""

        if alarm_object is None:
            alarm_object = self.__project_name+'_controller'

        textbox_entry = 'Building '+ alarm_object + ' Alarms'
        label_text = 'Building '+ alarm_object + ' Alarms'
        percentage = 0

        if progress_callback:
            progress_callback(textbox_entry,label_text,percentage)

        # Create a temporary file to store the command
        fd, script = tempfile.mkstemp(suffix = '.tp')
        os.close(fd)
        with open(script, "w") as text_file:
            text_file.write(build_alarms_acm_command.format(
                project_name = self._get_acm_project_name(),
                controller_name = controller_name,
                alarm_object = alarm_object,
                output_path = output_path
                ))
        
        # Create a temporary file to store the log
        fd, log = tempfile.mkstemp(suffix = '.log')
        os.close(fd)
        
        # Execute the command
        self.execute_with_log_monitoring(script, log, progress_callback)
                    
        


if __name__ == '__main__':
    project_name = 'ACMObjectCreationTestProject1'
    acm_creator = ACM_Console(project_name)
    acm_creator.create_acm_project('(RA-LIB) Process 5', 'Basic_Project', '2', '0')
    acm_creator.create_acm_controller('(RA-LIB) Process 5', 'Basic_Controller', '2', '0')

    def progress_callback(progress):
        print(f'Progress: {progress * 100}%')

    # A list with the object name as the key and a list of task, program and description as the value
    test_objects = {
                    'TIT001': {'task':'Fast', 'program':'FastProgram' ,'description':'Process 5 Title Object'},
                    'PIT002': {'task':'Fast', 'program':'FastProgram' ,'description':'Process 5 Picture Object'},
                    'FIT003': {'task':'Fast', 'program':'FastProgram' ,'description':'Process 5 Frame Object'},
                    'SIT004': {'task':'Fast', 'program':'FastProgram' ,'description':'Process 5 Screen Object'},
                    'BIT005': {'task':'Fast', 'program':'FastProgram' ,'description':'Process 5 Button Object'},
                    'LIT006': {'task':'Fast', 'program':'FastProgram' ,'description':'Process 5 Line Object'},
                    'CIT007': {'task':'Fast', 'program':'FastProgram' ,'description':'Process 5 Circle Object'},
                    'RIT008': {'task':'Fast', 'program':'FastProgram' ,'description':'Process 5 Rectangle Object'},
                    'AIT009': {'task':'Fast', 'program':'FastProgram' ,'description':'Process 5 Arc Object'},
                    'GIT010': {'task':'Fast', 'program':'FastProgram' ,'description':'Process 5 Graphic Object'},
                    'DIT011': {'task':'Fast', 'program':'FastProgram' ,'description':'Process 5 Data Object'},
                    
                    }
    acm_creator.create_acm_objects(test_objects, '(RA-LIB) Process 5', 'PAI', '2', '0', progress_callback)

    ftv_object = {
        'FT_View_Sever': {'task':'', 'program':'' ,'description':'Process 5 Data Object'}
    }

    acm_creator.create_acm_objects(ftv_object, "FT_View_Sever" ,"(RA-LIB) Process 5" ,"FTViewSE" ,"5" ,"21")