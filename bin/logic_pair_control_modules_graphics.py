import copy
import logging
import math
import multiprocessing
import time

import pyastar2d
import concurrent.futures
from bin.logic_linked_graphic_scanner import get_page_image
import cv2
import numpy as np
from PIL import Image
from shapely.geometry import LineString

from bin.logic_logger import get_logger

import bin.logic_globals



def find_connection_between_linked_graphics(primary_poi, secondary_poi, image_to_search):
    """
    Find the connection between linked graphics.

    :param primary_poi: The primary point of interest.
    :type primary_poi: Tuple[int,int]
    :param secondary_poi: The secondary point of interest.
    :type secondary_poi: Tuple[int,int]
    :param image_to_search: The image to search for secondary points of interest.
    :type image_to_search: numpy.ndarray
    :return: A tuple containing the cost and the path.
    :rtype: Tuple[int,List[Tuple[int,int]]]

    This function finds the connection between linked graphics. It uses the primary and secondary points of interest to find the connection. The result is a tuple containing the cost and the path.
    """
    DEBUG = False
    grid = image_to_search.astype(np.float32)
    grid[grid == 0] = 1
    grid[grid == 255] = 16

    for i in range(len(primary_poi)):
        start = np.array(primary_poi[i])
        start = start*2

        for j in range(len(secondary_poi)):
            end = np.array(secondary_poi[j])

            t0 = time.time()
            
            end = end*2
            path = pyastar2d.astar_path(grid, [start[1],start[0]], [end[1],end[0]], allow_diagonal=False)
            dur = time.time() - t0

            if path is None:
                continue

            if path.shape[0] > 0:
                path = path
                #xs, ys = straighten_lines(path)  
                
                cost = np.array([grid[point[0],point[1]] for point in path],dtype=int)
                
                pts = np.flip(path, 1)
                pts = pts.reshape((-1, 1, 2))
                if DEBUG:
                    maze = np.stack((image_to_search, image_to_search, image_to_search), axis=2)
                    maze = cv2.polylines(maze, [pts], 
                            False, (0,0,255), 5)
                    cv2.imshow('test',cv2.resize(maze,(1500,int(maze.shape[0]*1500/maze.shape[1]))))
                    cv2.waitKey(0)
                return np.sum(cost).tolist(), pts.tolist()
            else:
                return None 

                    

def find_smallest_distance(image_to_search, secondary_poi, paths, smallest_distance_cost, sorted_page_primary_poi_dict):
    """
    Find the smallest distance between the primary and secondary points of interest.

    :param image_to_search: The image to search for secondary points of interest.
    :type image_to_search: numpy.ndarray
    :param secondary_poi: The secondary point of interest.
    :type secondary_poi: Tuple[int,int]
    :param paths: A list of paths.
    :type paths: List
    :param smallest_distance_cost: The smallest distance cost.
    :type smallest_distance_cost: int
    :param sorted_page_primary_poi_dict: A dictionary containing the primary points of interest.
    :type sorted_page_primary_poi_dict: Dict[str,Tuple[int,int]]

    :return: None
    :rtype: None

    This function finds the smallest distance between the primary and secondary points of interest. It uses the secondary point of interest to find the smallest distance between the primary and secondary points of interest. The result is a list of paths.
    """
    for tagname, primary_poi in sorted_page_primary_poi_dict.items():
        primary_poi = [int(primary_poi[0]/2),int(primary_poi[1]/2)]
        secondary_poi = [int(secondary_poi[0]/2),int(secondary_poi[1]/2)]
        min_possible_distance_cost = math.sqrt((primary_poi[0]-secondary_poi[0])**2 + (primary_poi[1]-secondary_poi[1])**2)
                
        half_page_height = image_to_search.shape[0]/4

        if smallest_distance_cost < min_possible_distance_cost or min_possible_distance_cost > half_page_height:
            continue
                
        result = find_connection_between_linked_graphics( [primary_poi], [secondary_poi], image_to_search)
        if result:
            paths.append((result,tagname))
            if result[0] < smallest_distance_cost:
                smallest_distance_cost = result[0]



def generate_shortest_path_pairs(pno, page_primary_poi_dict, image_to_search,secondary_poi_dict):
    """
    Generates shortest path pairs between primary and secondary points of interest.
    :param pno: The page number.
    :type pno: int
    :param page_primary_poi_dict: A dictionary containing primary points of interest on the page.
    :type page_primary_poi_dict: dict
    :param image_to_search: The image to search for secondary points of interest.
    :type image_to_search: numpy.ndarray
    :param secondary_poi_dict: A dictionary containing secondary points of interest.
    :type secondary_poi_dict: dict
    :returns: A dictionary containing the control modules matching the given type and path.
    :rtype: dict
    
    This function generates the shortest path pairs between primary and secondary points of interest. It uses the primary and secondary points of interest to generate the pairs. The result is a dictionary containing the primary points of interest as keys and a list of tuples containing the cost, the secondary ROI, the path, the flip, the rotation, and the scale as values.
    """
    

    result = {}

    for secondary_poi, secondary_roi, secondary_flip, secondary_rotation, scale in secondary_poi_dict:
        paths = []
        smallest_distance_cost = 99999999999999999

        sorted_page_primary_poi_dict= {k: v for k, v in sorted(page_primary_poi_dict.items(), 
                key=lambda item: (item[1][0]-secondary_poi[0])**2 + (item[1][1]-secondary_poi[1])**2)}

        find_smallest_distance(image_to_search, secondary_poi, paths, smallest_distance_cost, sorted_page_primary_poi_dict)
            
            
        costs = np.array([path[0][0] for path in paths],dtype=int)
            
        if costs.size == 0:
            continue

        index_min = np.argmin(costs)
        
        primary_tagname = paths[index_min][1]

        if primary_tagname not in result:
            result[primary_tagname] = []

    

        result[primary_tagname].append((costs[index_min].tolist(),secondary_roi,paths[index_min],secondary_flip,secondary_rotation,scale))
       

    return result, pno

    


def generate_shortest_path_pairs_process(doc_path, pno, page_primary_poi_dict,secondary_poi_dict,queue):
    """
    
    Generate the shortest path pairs for a specific page of a PDF document.

    :param doc_path: The path to the PDF document.
    :type doc_path: str

    :param pno: The page number.
    :type pno: int

    :param page_primary_poi_dict: A dictionary containing the primary POIs.
    :type page_primary_poi_dict: Dict[str,Tuple[int,int]]

    :param secondary_poi_dict: A dictionary containing the secondary POIs.
    :type secondary_poi_dict: Dict[str,List[Tuple[int,int,Tuple[int,int,int,int,int]]]]

    :param queue: The queue to log messages to.
    :type queue: multiprocessing.Queue

    :return: A tuple containing the result and the page number.
    :rtype: Tuple[Dict[str,List[Tuple[int,Tuple[int,int,int,int,int]]],int]

    This function generates the shortest path pairs for a specific page of a PDF document. It uses the primary and secondary POIs to generate the pairs. The result is a dictionary containing the primary POIs as keys and a list of tuples containing the cost, the secondary ROI, the path, the flip, the rotation, and the scale as values. The page number is also returned.
    """
    retries = 3
    process_logger = get_logger(__name__, queue=queue)

    process_error = None

    
    for attempt in range(retries):

        try:
            if pno not in secondary_poi_dict:
                return ({}, pno), doc_path

            process_logger.info('Generating Shortest Path Pairs for document: {} on page {}'.format(doc_path,pno))
            img = np.array(get_page_image(doc_path,int(pno),zoom_level=1))
                
            _, image_to_search = cv2.threshold(cv2.cvtColor(img,cv2.COLOR_RGB2GRAY), 250, 255, cv2.THRESH_BINARY)
                
            
            result = generate_shortest_path_pairs(pno, page_primary_poi_dict, image_to_search,secondary_poi_dict[pno])
            process_logger.info('Done pairing in page: {} of path {}.'.format(pno + 1,doc_path))
        except Exception as error:
            process_error = error
            process_logger.error('Exception found while Generating Shortest Path Pairs in page {} of path {}. Error: {}'.format(pno + 1,path,error))
            process_logger.info('Retry {}/{} page {} of path {}.'.format(attempt+1,retries,pno + 1,doc_path))
            time.sleep(retries*(pno * 10 +  10)) # reduce chance of retires happening at same time
        else:
            return result, doc_path
    process_logger.info('Failed after retrying {} times. page {} of path {}.'.format(retries,pno + 1,doc_path)) 
    raise process_error


class linked_graphic_pairing:
    def __init__(self,doc_path, primary_poi_dict, secondary_poi_dict, done_callback) -> None:
        """
        Initialize the linked graphic pairing process.

        :param doc_path: The path to the PDF document.
        :type doc_path: str

        :param primary_poi_dict: A dictionary containing the primary POIs.
        :type primary_poi_dict: Dict[int,Dict[str,Tuple[int,int]]]

        :param secondary_poi_dict: A dictionary containing the secondary POIs.
        :type secondary_poi_dict: Dict[int,List[Tuple[int,int,Tuple[int,int,int,int,int]]]]

        :param done_callback: The callback function to call when the process is done.
        :type done_callback: Callable[[Dict[str,List[Tuple[int,Tuple[int,int,int,int,int]]]]]

        :return: None
        :rtype: None

        This function initializes the linked graphic pairing process. It creates a list of future objects to run the process in parallel.
        """
        self.__results = []
        self.__done_callback = done_callback
        self.__results_sent = False
        self.__error_description = ''
        self.__error_found = False
        if multiprocessing.cpu_count() > 4:
            max_worker =  multiprocessing.cpu_count()- 4
        else: 
            max_worker = 1
        executor = concurrent.futures.ProcessPoolExecutor(max_workers=max_worker)
        self.__results = [executor.submit(generate_shortest_path_pairs_process, doc_path, pno, page_primary_poi_dict,secondary_poi_dict, bin.logic_globals.logger_queue) 
                                    for pno, page_primary_poi_dict in copy.deepcopy(primary_poi_dict).items()]
    


    def check_multiprocess_graphic_pairing_progress(self):
        """
        Check the progress of the graphic pairing process

        :return: A tuple containing the number of tasks, the number of tasks done, the percentage of tasks done, a boolean indicating if the process is done, and an error description if an error is found.
        :rtype: Tuple[int,int,int,bool,str]

        This function checks the progress of the graphic pairing process. It returns the number of tasks, the number of tasks done, the percentage of tasks done, a boolean indicating if the process is done, and an error description if an error is found.
        """
        if not self.__results:
            return 0,0,0,False,None

        tasks_done = 0 
        for result in self.__results:
            if result.done():
                tasks_done = tasks_done + 1
            self.__check_for_exceptions(result)

        if tasks_done == len(self.__results) and not self.__error_found:
            done = True
            if self.__done_callback and not self.__results_sent:
                data = {}
                for result in self.__results:
                    res = result.result()

                    path = res[1]
                    pno = res[0][1]
                    if path not in data:
                        data[path] = {}
                    data[path][pno] = res[0]

                self.__done_callback(data, path)

                self.__results_sent = True
        else:
            done = False
        precentage = tasks_done/len(self.__results) * 100
        return len(self.__results),tasks_done, precentage, done, self.__error_description


    def __cancel_search(self):
        """
        Cancel the search

        :return: None
        :rtype: None

        This function cancels the search by cancelling all the future objects in the results list.
        """
        for result in self.__results:
            result.cancel()


    def __check_for_exceptions(self, result: concurrent.futures.Future):
        """
        check for exceptions in the result of the future object

        :param result: The future object to check for exceptions
        :type result: concurrent.futures.Future

        :return: None
        :rtype: None

        This function checks for exceptions in the result of the future object. If an exception is found, the search is cancelled and the error is stored.
        """
        if self.__error_found:
            return 
        try:
            error = result.exception(0.01)
            if error:
                self.__cancel_search()
                self.__error_found = True 
                if (isinstance(error, cv2.error) and error.code == -4) or str(error) == 'Overly large image':
                    self.__error_description = "Failed because of Insufficient Memory. Your system does not have enough RAM to process the current template.\n\nTry creating a larger template."
                else:
                    self.__error_description = "Failed to run scan. Please contact support.\n\nError: "+str(error)
        except concurrent.futures.TimeoutError:
            pass
