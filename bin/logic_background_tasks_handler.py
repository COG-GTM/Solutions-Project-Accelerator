class background_tasks_handler():
    def __init__(self) -> None:
        self.__background_tasks_dict = {}

    def add_background_task(self,name, object):
        self.__background_tasks_dict[name+type(object).__name__] = object

    def remove_background_task(self, name, object):
        key = name+type(object).__name__
        if key in self.__background_tasks_dict:
            self.__background_tasks_dict.pop(key)

    def get_object_if_running(self, name, cell_class):
        key = name+type(cell_class).__name__
        if key not in self.__background_tasks_dict:
            return None 
        else:
            return self.__background_tasks_dict[key]

    def get_running_background_tasks(self):
        return self.__background_tasks_dict