# -*- coding: utf-8 -*-
import __main__
import codecs
import io
from functools import wraps
from multiprocessing import Manager, Queue, current_process
from threading import Thread

import os
import sys
try:
    import bin.logic_globals
except:
    import logic_globals
import logging
from logging import handlers
from tkinter import messagebox
from typing import Optional


class SafeStreamHandler(logging.StreamHandler):
    """A StreamHandler that handles Unicode encoding errors gracefully."""
    
    def emit(self, record):
        try:
            msg = self.format(record)
            stream = self.stream
            # Replace unencodable characters with '?'
            try:
                stream.write(msg + self.terminator)
            except UnicodeEncodeError:
                # Encode with errors='replace' then decode back to string
                encoding = getattr(stream, 'encoding', 'utf-8') or 'utf-8'
                safe_msg = msg.encode(encoding, errors='replace').decode(encoding, errors='replace')
                stream.write(safe_msg + self.terminator)
            self.flush()
        except RecursionError:
            raise
        except Exception:
            self.handleError(record)


def init_logging():
    """ Initialize logging and write info both into logfile and console
        Usage example: land.logger.logging.info('Your message here')
        Logger levels: critical, error, warning, info, debug, notset """
    this_dir = os.path.dirname(os.path.realpath(__main__.__file__))  # path to this directory
    log_dir = os.path.join(this_dir, 'temp')
    # Create logging directory if not exist
    if not os.path.isdir(log_dir):
        os.makedirs(log_dir)
    # specify logging configuration
    logging.basicConfig(level=logging.INFO,
                        format='%(levelname)s, %(asctime)s, %(filename)s, %(funcName)s, %(message)s',
                        filename='{dir_name}/logfile.log'.format(dir_name=log_dir),
                        filemode='a', encoding='utf-8')
    # define a handler which writes to the sys.stderr
    # Use SafeStreamHandler to handle Unicode characters on Windows
    console = SafeStreamHandler()
    # set a format which is simpler for console usage
    formatter = logging.Formatter('[%(levelname)s] %(message)s')
    # tell the handler to use this format
    console.setFormatter(formatter)
    # add the handler to the root logger
    logging.getLogger('').addHandler(console)
    # Override sys.excepthook to log uncaught exceptions
    sys.excepthook = handle_uncaught_exception

def handle_uncaught_exception(errtype, value, traceback):
    """ Handle all uncaught exceptions """
    logger = logging.getLogger('')
    logger.error('Uncaught exception occured', exc_info=(errtype, value, traceback))

def handle_exception(exit_code = 0):
    """ Use: @land.logger.handle_exception(0)
        before every function which could cast an exception """
    def wrapper(func):
        @wraps(func)
        def inner(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as error:
                logging.exception(error)
                if exit_code != 0:  # if zero, don't exit from the program
                    sys.exit(exit_code)  # exit from the program
        return inner
    return wrapper

def handle_exception_with_messagebox(exit_code = 0, parent=None):
    """ Use: @land.logger.handle_exception(0)
        before every function which could cast an exception """
    def wrapper(func):
        @wraps(func)
        def inner(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as error:
                logging.exception(error)
                messagebox.showerror("Error",str(error),parent=parent)
                if exit_code != 0:  # if zero, don't exit from the program
                    sys.exit(exit_code)  # exit from the program
        return inner
    return wrapper


def get_logger(name: str, queue: Optional[Queue]=None):
    ''' This function gets a logger instance'''

    if current_process().name != 'MainProcess' and not Queue:

        pass
    elif queue is not None:
        # Set up the queue handler for the logger instance
        queue_handler = handlers.QueueHandler(queue)
        queue_handler.set_name(name=current_process().pid.__str__())
        # Get root logger instance
        root = logging.getLogger()
        root.setLevel(logging.INFO)
        # Add the handler if it does not exist.
        if queue_handler.name not in [x.name for x in root.handlers]:
            root.addHandler(queue_handler)

    logger = logging.getLogger(name=name)

    return logger


class redirect_to_logger():

    def __init__(self, logger, log_level=logging.INFO) -> None:
        self.logger = logger
        self.log_level = log_level

    def write(self, message):
        for line in message.rstrip().splitlines():
            self.logger.log(self.log_level, line.rstrip())

    def flush(self):
        pass

class LoggerManager:
    def __init__(self, logger_thread: Thread):
        self.logger_thread = logger_thread

    def terminate_logger(self):
        bin.logic_globals.logger_queue.put(None)
        self.logger_thread.join()

def _lt(queue: Queue):
    ''' This function acts as the thread that listens to the logger queue and sends queued logs'''
    while True:
        record = queue.get()
        if record is None:
            break
        logger = logging.getLogger(record.name)
        logger.handle(record)


def _configure_logging_handlers():
    '''This function configure the logging handlers for the root logger.'''

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # Define the log formatter.
    log_formatter = logging.Formatter('[%(levelname)s], %(asctime)s, %(filename)s, %(funcName)s, %(message)s')

    # Define the log file handler.
    this_dir = os.path.dirname(os.path.realpath(__main__.__file__))  # path to this directory
    log_dir = os.path.join(this_dir, 'temp')
    # Create logging directory if not exist
    if not os.path.isdir(log_dir):
        os.makedirs(log_dir)
    file_hanlder = handlers.RotatingFileHandler('{dir_name}/logfile.log'.format(dir_name=log_dir),maxBytes=10000000,backupCount=6,encoding='utf-8')
    file_hanlder.setFormatter(log_formatter)
    root.addHandler(file_hanlder)

    # Define the stream handler.
    # Use SafeStreamHandler to handle Unicode characters on Windows
    stderr_handler = SafeStreamHandler(sys.stderr)
    stderr_handler.setFormatter(log_formatter)
    root.addHandler(stderr_handler)

    # Redirect stdout to a logger instance 
    stdout_logger = get_logger('stdout')
    stdout_logger = redirect_to_logger(logger=stdout_logger, log_level=logging.INFO)
    sys.stdout = stdout_logger

    # Redirect stderr to a logger instance 
    stderr_logger = get_logger('stderr')
    stderr_logger = redirect_to_logger(logger=stderr_logger, log_level=logging.ERROR)
    sys.stderr = stderr_logger
      

def logger_init():
    _configure_logging_handlers()

    bin.logic_globals.logger_queue = Manager().Queue()

    logger_thread = Thread(target=_lt, args=(bin.logic_globals.logger_queue,))
    logger_thread.start()

    return LoggerManager(logger_thread=logger_thread)


