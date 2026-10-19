import os
from .logic_logger import logging, handle_exception

class Project_Files:

    def __init__(self, path='projects'):
        self.project_dir = path

    @handle_exception(0)
    def create_project(self):
       pass 
