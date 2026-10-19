
from tkinter import messagebox
import pyodbc
import logging
import sys
import time
from functools import wraps
import socket
from collections import OrderedDict


SQL_BROWSER_DEFAULT_PORT = 1434
BUFFER_SIZE = 4096
TIMEOUT = 4


class SQL_Database():
    """
    A class representing a SQL database used to browse for SQL Databases and handle database connections.
    """

    def __init__(self, connection_string, database):
        """
        Initializes the SQL_Database object.

        :param connection_string: The connection string for the database.
        :type connection_string: str
        :param database: The name of the database.
        :type database: str

        :return: None
        :rtype: None

        This function initializes the SQL_Database object with the provided connection string and database name.
        """
        self.__connection_string = connection_string
        self.__database = database
        self.__project = None


    def set_project(self, project):
        """
        Sets the project for the database.
        
        :param project: The project to be set.
        :type project: str
        
        :return: None
        :rtype: None
        
        This function sets the project for the database.
        """
        self.__project = project

    
    def get_all_projects(self):
        """
        Retrieves all projects from the database.

        :return: A list of projects.
        :rtype: list

        This function retrieves all projects from the database and returns them as a list.
        """

        @db_connector(self.__connection_string)
        def query(cnn):
            cur = cnn.cursor()
            cur.execute(
                'SELECT * FROM [{}].[dbo].[Projects]'
                .format(self.__database)) # or something else 
            rows = cur.fetchall()
            return rows

        return query()


def get_instance_info(host, instance=None, sql_browser_port=SQL_BROWSER_DEFAULT_PORT,
                    buffer_size=BUFFER_SIZE, timeout=TIMEOUT):
    """
    Retrieves information about the SQL Server instances running on the specified host.

    :param host: The name or IP address of the host.
    :type host: str
    :param instance: The name of the SQL Server instance (optional).
    :type instance: str
    :param sql_browser_port: The port number for the SQL Browser service (optional).
    :type sql_browser_port: int
    :param buffer_size: The size of the buffer for receiving data (optional).
    :type buffer_size: int
    :param timeout: The timeout value for the socket connection (optional).
    :type timeout: int
    :return: A list of dictionaries containing information about the SQL Server instances.
    :rtype: list[dict]

    This function retrieves information about the SQL Server instances running on the specified host using the SQL Browser service.
    If the instance parameter is provided, it retrieves information about the specified instance.
    The function sends a CLNT_UCAST_INST packet to the SQL Browser service to get information about the instances.
    It then parses the response data and returns a list of dictionaries containing information about the instances.


    Example:
        >>> get_instance_info('localhost')
        [{'InstanceName': 'MSSQLSERVER', 'IsCluster': 'No', 'Version': '14.0.1000.169', 'tcp': '1433', 'np': '\\\\.\\pipe\\sql\\query'}]
    """
    
    # Create a UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # Set a timeout
    sock.settimeout(timeout)

    server_address = (host, sql_browser_port)

    if instance:
        # The message is a CLNT_UCAST_INST packet to get a single instance
        # https://msdn.microsoft.com/en-us/library/cc219746.aspx
        message = '\x04%s\x00' % instance
        # Encode the message as a bytesarray
    else:
        # The message is a CLNT_UCAST_EX packet to get all instances
        # https://msdn.microsoft.com/en-us/library/cc219745.aspx
        message = '\x03'

    # Encode the message as a bytesarray
    message = message.encode()

    # Send data
    sock.sendto(message, server_address)

    # Receive response
    data, server = sock.recvfrom(buffer_size)

    results = []

    # Loop through the server data
    for server in data[3:].decode().split(';;'):
        server_info = OrderedDict()
        chunk = server.split(';')

        if len(chunk) > 1:
            for i in range(1, len(chunk), 2):
                server_info[chunk[i - 1]] = chunk[i]

            results.append(server_info)

    # Close socket
    sock.close()

    return results


           
def parametrized(dec):
    """
    Decorator that adds parameters to a function.

    :param dec: The decorator function to be applied.
    :type dec: function
    :param args: Positional arguments to be passed to the decorator.
    :type args: tuple
    :param kwargs: Keyword arguments to be passed to the decorator.
    :type kwargs: dict
        
    :return: The decorated function.
    :rtype: function

    This decorator allows you to add parameters to a function by applying another decorator. The `dec` parameter is the decorator function that will be applied to the function. The `args` and `kwargs` parameters are the positional and keyword arguments that will be passed to the decorator.

    Example:
        >>> @parametrized(some_decorator, arg1='value1', arg2='value2')
        ... def my_function():
        ...     pass
    """
    def layer(*args, **kwargs):
        def repl(f):
            return dec(f, *args, **kwargs)
        return repl
    return layer            
 
 
@parametrized 
def db_connector(func, connection_string):
    """
    Connects to a database using the provided connection string and executes the given function.

    :param func: The function to be executed with the database connection.
    :type func: function
    :param connection_string: The connection string for the database.
    :type connection_string: str
    
    :return: The result of the executed function.
    :rtype: Any

    This function connects to a database using the provided connection string and executes the given function
    with the database connection. It handles exceptions, rolls back the transaction in case of an error,
    and commits the transaction if successful. Finally, it closes the database connection.

    Example:
        >>> db_connector(my_function, "connection_string")
        'Result'
    """
    def with_connection_(*args,**kwargs):
        try:
            cnn = pyodbc.connect(connection_string)
            rv = func(cnn, *args,**kwargs)
        except Exception as error:
            cnn.rollback()
            logging.error("Database connection error: "+str(error))
            raise ValueError(error)
        else:
            cnn.commit()
        finally:
            cnn.close()
        return rv
    return with_connection_	


@parametrized
def non_commit_db_connector(func, connection_string):
    """
    Connects to a database using the provided connection string and executes the given function without committing changes.

    :param func: The function to be executed with the database connection.
    :type func: function
    :param connection_string: The connection string for the database.
    :type connection_string: str
    
    :return: The result of the executed function.
    :rtype: Any

    This function connects to a database using the provided connection string and executes the given function
    with the database connection. It handles exceptions and rolls back the transaction in case of an error.
    Finally, it closes the database connection without committing any changes.

    Example:
        >>> non_commit_db_connector(my_function, "connection_string")
        'Result'
    """
    def with_connection_(*args,**kwargs):
        try:
            if 'connection' in kwargs and kwargs['connection'] is not None:
                cnn = kwargs['connection']
            else:
                cnn = pyodbc.connect(connection_string)
            del kwargs['connection']
            rv = func(cnn, *args,**kwargs)
        except Exception as error:
            cnn.rollback()
            logging.error("Database connection error: "+str(error))
            raise ValueError(error)
        return rv
    return with_connection_


def get_all_databases(server, user='', password='', use_windows_authentication=True):
    """
    Retrieves a list of all databases on the specified SQL Server.
    :param server: The name or IP address of the SQL Server.
    :type server: str
    :param user: The username for authentication (optional).
    :type user: str
    :param password: The password for authentication (optional).
    :type password: str
    :param use_windows_authentication: Flag indicating whether to use Windows authentication (optional).
    :type use_windows_authentication: bool
    :return: A list of all databases on the SQL Server.
    :rtype: list[str]
    This function connects to the specified SQL Server and retrieves the names of all databases using the sys.databases table.
    If no SQL Server drivers are found, an empty list is returned.
    If Windows authentication is used, the connection string will include 'Trusted_Connection=yes;'.
    If username and password are provided, the connection string will include 'UID=<user>;PWD=<password>;' for authentication.
    Example:
        >>> get_all_databases('localhost')
        ['database1', 'database2', 'database3']
    """
    databases = []
    sql_drivers = [x for x in pyodbc.drivers() if x.endswith('SQL Server')]
    
    if len(sql_drivers) == 0:
        return databases

    auth_string = ''
    if use_windows_authentication:
        auth_string = 'Trusted_Connection=yes;'
    else:
        auth_string = 'UID='+user+';PWD='+password+';'

    connection_string =   ('DRIVER={'+sql_drivers[0]+'};'+
                    'SERVER='+server+';'+
                    'DATABASE=master;'+auth_string)
    cn = pyodbc.connect(connection_string, timeout=1)
    with cn.cursor() as cursor:
        cursor.execute("select name from sys.databases")
        rows = cursor.fetchall()
        for row in rows:
            databases.append(row.name)
        return databases



def build_connection_string(server, database, user='', password='', use_windows_authentication=True):
    """
    Builds a connection string for connecting to a SQL database.

    :param server: The name of the SQL server.
    :type server: str
    :param database: The name of the database.
    :type database: str
    :param user: The username for authentication (optional).
    :type user: str
    :param password: The password for authentication (optional).
    :type password: str
    :param use_windows_authentication: Flag indicating whether to use Windows authentication (optional).
    :type use_windows_authentication: bool
    :return: The connection string.
    :rtype: str

    Builds a connection string using the provided server, database, user, password, and use_windows_authentication parameters.
    If no SQL database driver is installed, an error message is logged and an error dialog is shown.
    The connection string is constructed based on the provided parameters and returned.
    """
    # server name format: DESKTOP-DQKTOF4\SQLEXPRESS

    sql_drivers = [x for x in pyodbc.drivers() if x.endswith('SQL Server')]
    
    if len(sql_drivers) == 0:
        logging.error('No SQL database driver installed')
        messagebox.showerror('No SQL database driver installed','Please contact support')
        return ''

    auth_string = ''
    if use_windows_authentication:
        auth_string = 'Trusted_Connection=yes;'
    else:
        auth_string = 'UID='+user+';PWD='+password+';'

    connection_string =   ('DRIVER={'+get_highest_sql_driver(sql_drivers)+'};'+
                    'SERVER='+server+';'+
                    'DATABASE='+database+';'+auth_string)
    logging.info('SQL connection string: '+connection_string) 
    return connection_string


def get_highest_sql_driver(sql_drivers):
    """
    Get the highest version SQL driver from a list of SQL drivers.
    :param sql_drivers: A list of SQL drivers.
    :type sql_drivers: list[str]
    :return: The SQL driver with the highest version.
    :rtype: str
    This function iterates through the list of SQL drivers and extracts the version number from each driver. It then compares the version numbers and returns the SQL driver with the highest version.
    Example:
        >>> get_highest_sql_driver(['SQL Driver 1.0', 'SQL Driver 2.0', 'SQL Driver 1.5'])
        'SQL Driver 2.0'
    """
    highest_version = 0
    highest_version_index = 0
    for i in range(len(sql_drivers)):
        driver = sql_drivers[i]
        text_list = driver.split(' ')
        for text in text_list:
            if text.isdigit() and int(text)>highest_version:
                highest_version = int(text)
                highest_version_index = i
    
    return sql_drivers[highest_version_index]



def test_connection(connection_string):
    """
    Test the database connection using the provided connection string.

    :param connection_string: The connection string to connect to the database.
    :type connection_string: str
    
    :return: None
    :rtype: None

    This function tests the connection to the database using the provided connection string. 
    It attempts to establish a connection and closes it afterwards. If an error occurs during 
    the connection attempt, an exception is raised.

    Example:
        >>> test_connection("Driver={SQL Server};Server=localhost;Database=testdb;Trusted_Connection=yes;")
    """
    cnn = None
    try:
        cnn = pyodbc.connect(connection_string)
    except pyodbc.Error as ex:
        sqlstate = ex.args[1]
        logging.error("Database connection error: "+sqlstate)
        raise Exception(sqlstate)
    finally:
        if cnn:
            cnn.close()

            
	

if __name__ == "__main__":
    
    try:
        instance_info = get_instance_info(socket.gethostname())
    except socket.error as error:
        sys.stderr.write('Connection to %s failed: %s' % (socket.gethostname(), error))
        sys.exit(1)

    for i in instance_info:
        print('')

        for key, value in i.items():
            print('%s: %s' % (key, value))
    
    sql_drivers = [x for x in pyodbc.drivers() if x.endswith('SQL Server')]
    
    print(sql_drivers)
    
    
    
    conntion_string =   ('DRIVER={'+sql_drivers[0]+'};'+
                        'SERVER='+socket.gethostname()+'\\'+instance_info[0]['InstanceName']+';'+
                        'DATABASE=ACM;UID=test;PWD=;')
    print(conntion_string) 
    
    start = time.time() *1000
    
    @db_connector(conntion_string)
    def do_some_job(cnn):
        cur = cnn.cursor()
        cur.execute('SELECT * FROM [ACM].[dbo].[Objects]') # or something else
        rows = cur.fetchall()
        #for row in rows:
        #    print(row, end='\n')
    
    
    
    do_some_job()
    
    print("Time taken: " + str(time.time()*1000 - start))
    
    
