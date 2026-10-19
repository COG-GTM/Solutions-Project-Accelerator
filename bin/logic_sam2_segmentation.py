import logging
import math
import threading
import time
from typing import Any, Optional

import cv2
import numpy as np
import onnxruntime
from numpy import ndarray
from scipy.spatial.distance import cdist
from shapely import BufferJoinStyle, Polygon
from skimage.morphology import binary_dilation
from scipy.ndimage import label

def point_point_distance(point1, point2):
    """Calculates the Euclidean distance between two points."""
    return math.sqrt((point1[0] - point2[0])**2 + (point1[1] - point2[1])**2)

def point_segment_distance(point, segment_p1, segment_p2):
    """Calculates the shortest distance from a point to a line segment.

    Args:
        point: The point (tuple or list of two coordinates).
        segment_p1: The first endpoint of the segment (tuple or list of two coordinates).
        segment_p2: The second endpoint of the segment (tuple or list of two coordinates).

    Returns:
        A tuple containing:
            - The shortest distance from the point to the segment.
            - The nearest point on the segment to the given point.
    """
    x0, y0 = point
    x1, y1 = segment_p1
    x2, y2 = segment_p2

    dx = x2 - x1
    dy = y2 - y1

    if dx == 0 and dy == 0:  # Segment is just a point
        return point_point_distance(point, segment_p1), segment_p1

    t = ((x0 - x1) * dx + (y0 - y1) * dy) / (dx**2 + dy**2)

    if t < 0:
        nearest_point = segment_p1
        return point_point_distance(point, segment_p1), nearest_point
    elif t > 1:
        nearest_point = segment_p2
        return point_point_distance(point, segment_p2), nearest_point
    else:
        nearest_point = (x1 + t * dx, y1 + t * dy)
        return point_point_distance(point, nearest_point), nearest_point

def polygon_polygon_nearest_points(polygon1_contour, polygon2_contour):
    """Finds the nearest points between two polygons represented as OpenCV contours.

    Args:
        polygon1_contour: An OpenCV contour representing the first polygon (NumPy array).
        polygon2_contour: An OpenCV contour representing the second polygon (NumPy array).

    Returns:
        A tuple containing:
            - The minimum distance between the two polygons.
            - A tuple containing the nearest point on polygon1 and the nearest point on polygon2 (tuples).
              Returns float('inf'), (None, None) if polygons are the same.
    """
    if np.array_equal(polygon1_contour, polygon2_contour): # Compare contours directly
        return float('inf'), (None, None)

    min_distance = float('inf')
    nearest_points = (None, None)

    # 1. Check distance from each vertex of polygon1 to each edge of polygon2
    for p1_vertex_arr in polygon1_contour: # Iterate through points in contour1
        p1_vertex = tuple(p1_vertex_arr[0]) # Extract vertex as tuple (x, y)
        for i in range(len(polygon2_contour)):
            p2_segment_start = tuple(polygon2_contour[i][0])
            p2_segment_end = tuple(polygon2_contour[(i + 1) % len(polygon2_contour)][0])
            distance, nearest_p2_segment_point = point_segment_distance(p1_vertex, p2_segment_start, p2_segment_end)
            if distance < min_distance:
                min_distance = distance
                nearest_points = (p1_vertex, nearest_p2_segment_point)

    # 2. Check distance from each vertex of polygon2 to each edge of polygon1
    for p2_vertex_arr in polygon2_contour: # Iterate through points in contour2
        p2_vertex = tuple(p2_vertex_arr[0]) # Extract vertex as tuple (x, y)
        for i in range(len(polygon1_contour)):
            p1_segment_start = tuple(polygon1_contour[i][0])
            p1_segment_end = tuple(polygon1_contour[(i + 1) % len(polygon1_contour)][0])
            distance, nearest_p1_segment_point = point_segment_distance(p2_vertex, p1_segment_start, p1_segment_end)
            if distance < min_distance:
                min_distance = distance
                nearest_points = (nearest_p1_segment_point, p2_vertex) # Order matters: polygon1, polygon2

    return min_distance, nearest_points


def find_nearest_points_between_contour_list(contour_list):
    """Finds the nearest points between all pairs of contours in a list.

    Args:
        contour_list: A list of OpenCV contours.

    Returns:
        A list of dictionaries, each with nearest points info for a contour pair.
    """
    nearest_points_results = []
    num_contours = len(contour_list)

    for i in range(num_contours):
        for j in range(i + 1, num_contours):
            contour1 = contour_list[i]
            contour2 = contour_list[j]

            min_distance, nearest_points = polygon_polygon_nearest_points(contour1, contour2)

            nearest_points_results.append({
                'polygon1_index': i, # Still using 'polygon_index' for consistency, but it's contours now
                'polygon2_index': j,
                'min_distance': min_distance,
                'nearest_points': nearest_points
            })

    return nearest_points_results

def unify_contours_with_connections(contour_list, nearest_points_results, img_width, img_height):
    """Unifies contours by connecting them with lines based on nearest points.

    Args:
        contour_list: A list of OpenCV contours.
        nearest_points_results: A list of dictionaries with nearest points info.
        img_width: Width of the image.
        img_height: Height of the image.    

    Returns:
        A list of contours representing the unified polygons.
    """


    # 1. Create a black image
    img = np.zeros((img_height, img_width), dtype=np.uint8)


    color = (255, 255, 255)
    line_thickness = 20

    # 2. Draw contours as masks
    for i, contour in enumerate(contour_list):
        cv2.drawContours(img, [contour], -1, color, thickness=cv2.FILLED) # Use drawContours with filled masks


    # 3. Connect nearest contours
    connected_pairs = set()
    for i in range(len(contour_list)):
        min_distance_for_contour_i = float('inf')
        nearest_pair_for_contour_i = None

        for result in nearest_points_results:
            if result['polygon1_index'] == i: # Still using polygon_index for result dict keys
                if result['min_distance'] < min_distance_for_contour_i:
                    min_distance_for_contour_i = result['min_distance']
                    nearest_pair_for_contour_i = result
            elif result['polygon2_index'] == i:
                if result['min_distance'] < min_distance_for_contour_i:
                    min_distance_for_contour_i = result['min_distance']
                    nearest_pair_for_contour_i = result

        if nearest_pair_for_contour_i:
            p1_index = nearest_pair_for_contour_i['polygon1_index']
            p2_index = nearest_pair_for_contour_i['polygon2_index']
            nearest_p1 = nearest_pair_for_contour_i['nearest_points'][0]
            nearest_p2 = nearest_pair_for_contour_i['nearest_points'][1]

            pair_tuple = tuple(sorted((p1_index, p2_index)))
            if pair_tuple not in connected_pairs:
                connected_pairs.add(pair_tuple)

                start_point = (int(nearest_p1[0]), int((nearest_p1[1])))
                end_point = (int(nearest_p2[0]), int((nearest_p2[1])))
                cv2.line(img, start_point, end_point, color, line_thickness)

    return cv2.findContours(img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)[0]


def simplify_mask_polygon( mask: np.ndarray) -> list:
    
    # Apply errode to image 
    kernel = np.ones((10, 10), np.uint8)
    mask = cv2.dilate(mask, kernel, iterations=1)
    mask = cv2.erode(mask, kernel, iterations=1)

     
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    c = max(contours, key=cv2.contourArea)
    peri = cv2.arcLength(c, True)
    simplified_polygon = cv2.approxPolyDP(c, 0.001 * peri, True)
    
    # Convert the simplified polygon to a list of points
    simplified_polygon = simplified_polygon.squeeze()
    simplified_polygon = simplified_polygon.tolist()
    return simplified_polygon


def process_mask_to_unified_polygon( mask: np.ndarray) -> list:
    """Converts a binary mask to a list of polygons and simplifies them to a single polygon."""
    
    # Apply errode to image 
    kernel = np.ones((10, 10), np.uint8)
    mask = cv2.dilate(mask, kernel, iterations=1)
    mask = cv2.erode(mask, kernel, iterations=1)

    polygons = []
     
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    # Tuple to list 
    contours = list(contours)
    c = max(contours, key=cv2.contourArea)
    # Remove all contours that make 1/10 of the biggest contour's area
    filtered_contours = []
    for i, contour in enumerate(contours):
        if cv2.contourArea(contour) > cv2.contourArea(c) / 10:
            filtered_contours.append(contour)
    simplified_filtered_contours = []

    # Simplify the contours
    for c in filtered_contours:
        peri = cv2.arcLength(c, True)
        polygon = cv2.approxPolyDP(c, 0.001 * peri, True)
        simplified_filtered_contours.append(polygon)
    
    # If there are more than one contour, find nearest points 
    # and connect them to form a single polygon
    if len(simplified_filtered_contours) > 1:
        results = find_nearest_points_between_contour_list(simplified_filtered_contours)
        simplified_filtered_contours = unify_contours_with_connections(simplified_filtered_contours
                                                                       , results
                                                                       , mask.shape[1]
                                                                       , mask.shape[0])
    # Convert the simplified polygons to a list of points
    for c in simplified_filtered_contours:
        polygon = c.squeeze()
        polygon = polygon.tolist()
        polygons.append(polygon)
    
    return polygons

class SAM2Image:

    DEFAULT_LABEL_ID = 1

    def __init__(self, encoder_path: str=r'SAM2.1\sam2.1_hiera_tiny_encoder.onnx'
                 , decoder_path: str=r'SAM2.1\sam2.1_hiera_tiny_decoder.onnx') -> None:
        # Initialize models
        self.encoder = SAM2ImageEncoder(encoder_path)
        self.orig_im_size = self.encoder.input_shape[2:]
        self.decoder_path = decoder_path
        self.decoders = {}

        self.point_coords = {}
        self.box_coords = {}
        self.point_labels = {}
        self.input_masks = {}
        self.masks = {}
        self.image_embeddings = None
        self.image_scale_factor = 1
        self.done_processing = False
        self.segmentation_region = [0,0,0,0]

    def set_image(self, image: np.ndarray, segmentation_region: tuple[int,int,int,int]) -> None:
        self.image_embeddings = None
        self.segmentation_region = segmentation_region
        self.image_embeddings = self.encoder(image)
        self.orig_im_size = (image.shape[0], image.shape[1])
        self.reset_points()
    
    def set_image_asynch(self, image: np.ndarray, segmentation_region: tuple[int,int,int,int]) -> None:

        self.image_embeddings = None
        self.segmentation_region = segmentation_region

        # Resize the image so that the smallest dimension is 512
        self.image_scale_factor = 512 / min(image.shape[:2])
        image = cv2.resize(image, (0, 0), fx=self.image_scale_factor, fy=self.image_scale_factor)
        

        def callback(outputs: list[np.ndarray]) -> None:
            self.reset_points()
            self.orig_im_size = (image.shape[0], image.shape[1])
            self.image_embeddings = outputs
        self.encoder.encode_image_asynch(image, callback)


    def image_is_set(self) -> bool:
        return self.image_embeddings is not None
        

    def add_point(self, point_coords: tuple[int, int], is_positive: bool, label_id: int=DEFAULT_LABEL_ID) -> dict[int, np.ndarray]:
        self.done_processing = False
        self.wait_for_image_embeddings()
        point_coords = self.adjust_point_to_cropped_region(point_coords)
        if label_id not in self.decoders:
            self.decoders[label_id] = SAM2ImageDecoder(self.decoder_path, self.encoder.input_shape[2:], self.orig_im_size)

        if label_id not in self.point_coords:
            self.point_coords[label_id] = np.array([point_coords])
            self.point_labels[label_id] = np.array([1 if is_positive else 0])
        else:
            self.point_coords[label_id] = np.append(self.point_coords[label_id], np.array([point_coords]), axis=0)
            self.point_labels[label_id] = np.append(self.point_labels[label_id], 1 if is_positive else 0)

        return self.decode_mask(label_id)
    

    def adjust_point_to_cropped_region(self, point_coords: tuple[int, int]) -> tuple[int, int]:
        """Adjusts point coordinates to be relative to the cropped image region."""
        x1, y1, _, _ = self.segmentation_region
        x = (point_coords[0] - x1) * self.image_scale_factor
        y = (point_coords[1] - y1) * self.image_scale_factor
        # Account for the scale factor
        return np.array((int(x), int(y)))
    

    def set_box(self, box_coords: tuple[tuple[int, int], tuple[int, int]], label_id: int=DEFAULT_LABEL_ID) -> dict[int, np.ndarray]:
        self.done_processing = False
        self.wait_for_image_embeddings()
        if label_id not in self.decoders:
            self.decoders[label_id] = SAM2ImageDecoder(self.decoder_path, self.encoder.input_shape[2:], self.orig_im_size)

        point_coords = np.array([box_coords[0], box_coords[1]]) # Convert from 1x4 to 2x2

        self.box_coords[label_id] = point_coords

        return self.decode_mask(label_id)
    
    def set_mask(self, mask: np.ndarray, label_id: int=DEFAULT_LABEL_ID) -> dict[int, np.ndarray]:
        """Add an input mask for refinement.
        
        Args:
            mask: Binary mask of shape (H, W)
            label_id: Identifier for the mask
            
        Returns:
            Dictionary of all current masks
        """
        self.done_processing = False
        self.wait_for_image_embeddings()
        if label_id not in self.decoders:
            self.decoders[label_id] = SAM2ImageDecoder(self.decoder_path, self.encoder.input_shape[2:], self.orig_im_size)

        # Ensure mask is binary and correct size
        mask = (mask > 0).astype(np.uint8)
        if mask.shape != self.orig_im_size:
            mask = cv2.resize(mask, (self.orig_im_size[1], self.orig_im_size[0]), interpolation=cv2.INTER_NEAREST)

        self.input_masks[label_id] = mask
        return self.decode_mask(label_id)
    


    def decode_mask(self, label_id: int=DEFAULT_LABEL_ID) -> dict[int, np.ndarray]:
        concat_coords, concat_labels = self.merge_points_and_boxes(label_id)
        input_mask = self.input_masks.get(label_id, None)

        decoder = self.decoders[label_id]
        high_res_feats_0, high_res_feats_1, image_embed = self.image_embeddings
        
        if input_mask is None and concat_coords.size == 0:
            mask = np.zeros(self.orig_im_size, dtype=np.uint8)
        else:
            mask, _ = decoder(
                image_embed, 
                high_res_feats_0, 
                high_res_feats_1, 
                concat_coords, 
                concat_labels,
                input_mask
            )
        self.masks[label_id] = mask
        self.done_processing = True
        return self.masks
    

    def wait_for_image_embeddings(self) -> None:
        if self.image_embeddings is None:
            start_time = time.time()
            while self.image_embeddings is None:
                if time.time() - start_time > 5:
                    logging.error("Image embeddings not set within 5 seconds.")
                    raise RuntimeError("Error in loading segmentation model. Please press 'Cancel' and try again.")
                time.sleep(0.1)
    

    def merge_points_and_boxes(self, label_id: int) -> tuple[np.ndarray, np.ndarray]:
        concat_coords = []
        concat_labels = []
        has_points = label_id in self.point_coords
        has_boxes = label_id in self.box_coords

        if not has_points and not has_boxes:
            return None, None

        if has_points:
            concat_coords.append(self.point_coords[label_id])
            concat_labels.append(self.point_labels[label_id])
        if has_boxes:
            concat_coords.append(self.box_coords[label_id])
            concat_labels.append(np.array([2, 3]))
        concat_coords = np.concatenate(concat_coords, axis=0)
        concat_labels = np.concatenate(concat_labels, axis=0)

        return concat_coords, concat_labels
    

    def remove_point(self,  point_coords: tuple[int, int], label_id: int=DEFAULT_LABEL_ID) -> dict[int, np.ndarray]:
        point_id = np.where((self.point_coords[label_id][:, 0] == point_coords[0]) & (self.point_coords[label_id][:, 1] == point_coords[1]))[0][0]
        self.point_coords[label_id] = np.delete(self.point_coords[label_id], point_id, axis=0)
        self.point_labels[label_id] = np.delete(self.point_labels[label_id], point_id, axis=0)

        return self.decode_mask(label_id)
    


    def remove_box(self, label_id: int) -> dict[int, np.ndarray]:
        del self.box_coords[label_id]
        return self.decode_mask(label_id)
    
    def remove_mask(self, label_id: int) -> dict[int, np.ndarray]:
        """Remove the input mask for the given label ID."""
        if label_id in self.input_masks:
            del self.input_masks[label_id]
        return self.decode_mask(label_id)
    

    def is_done_processing(self) -> bool:
        return self.done_processing 

    def get_polygons(self) -> dict[int, np.ndarray]:
        polygons = process_mask_to_unified_polygon(self.masks[self.DEFAULT_LABEL_ID])
        adjusted_polygons = []
        for polygon in polygons:
            polygon = [(int(p[0] / self.image_scale_factor + self.segmentation_region[0]), 
                        int(p[1] / self.image_scale_factor + self.segmentation_region[1])) for p in polygon]
            
            # Fix polypons with points that repeat one after the other
            if len(polygon) > 2:
                for i in range(len(polygon)):
                    if polygon[i] == polygon[(i + 1) % len(polygon)]:
                        del polygon[i]
                        break

            # Use Shapely to remove self-intersections
            shapely_polygon = Polygon(polygon)
            if not shapely_polygon.is_valid:
                polygon = shapely_polygon.buffer(0.1, join_style=BufferJoinStyle.mitre.value).exterior.coords[:-1]


            # If the first and last points are the same, remove the last point
            if polygon[0] == polygon[-1]:
                polygon = polygon[:-1]


            adjusted_polygons.append(polygon)

        return adjusted_polygons
    

    def reset(self) -> None:
        self.reset_points()
        self.image_embeddings = None
        self.image_scale_factor = 1
        self.done_processing = False
        self.segmentation_region = [0,0,0,0]
    
    

    def reset_points(self) -> None:
        self.point_coords = {}
        self.box_coords = {}
        self.point_labels = {}
        self.masks = {}
        self.decoders = {}


class RunAsyncData:
    def __init__(self):
        self.results = []
        self.error = None
    
    def save_results(self, results: np.ndarray):
        """Save the inference results"""
        self.results.append(results)
    
    def save_error(self, error: str):
        """Save any error that occurred"""
        self.error = error


class SAM2ImageEncoder:
    def __init__(self, path: str) -> None:
        # Initialize model
        self.session = onnxruntime.InferenceSession(path, providers=onnxruntime.get_available_providers())

        # Get model info
        self.get_input_details()
        self.get_output_details()

    def __call__(self, image: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        '''Encode an image synchronously'''
        return self.encode_image(image)
    

    def encode_image_asynch(self, image: np.ndarray, callback) -> None:
        '''Encode an image asynchronously and call a callback function when done
        
        Callback function should take the form:
        def callback(outputs: tuple[np.ndarray, np.ndarray, np.ndarray]) -> None:
            pass
        '''


        input_tensor = self.prepare_input(image)
        run_result = self.infer_asynch(input_tensor)

        # Threaded function to check for results
        def check_results():
            while not run_result.results and not run_result.error:
                time.sleep(0.1)
            outputs = self.process_output(run_result.results[0])
            callback(outputs)

        # Start the thread
        thread = threading.Thread(target=check_results)
        thread.start()


    def encode_image(self, image: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        input_tensor = self.prepare_input(image)

        outputs = self.infer(input_tensor)
        return self.process_output(outputs)
    

    def prepare_input(self, image: np.ndarray) -> np.ndarray:
        self.img_height, self.img_width = image.shape[:2]

        input_img = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        # Resize input image
        input_img = cv2.resize(input_img, (self.input_width, self.input_height))

        mean = np.array([0.485, 0.456, 0.406])
        std = np.array([0.229, 0.224, 0.225])
        input_img = (input_img / 255.0 - mean) / std
        input_img = input_img.transpose(2, 0, 1)
        input_tensor = input_img[np.newaxis, :, :, :].astype(np.float32)

        return input_tensor

    def infer(self, input_tensor: np.ndarray) -> list[np.ndarray]:
        start = time.perf_counter()
        outputs = self.session.run(self.output_names, {self.input_names[0]: input_tensor})

        print(f"infer time: {(time.perf_counter() - start) * 1000:.2f} ms")
        return outputs
    
    def infer_asynch(self, input_tensor: np.ndarray) -> RunAsyncData:

        

        def callback_wrapper(results: np.ndarray, result_data: RunAsyncData, error: str = None) -> None:
            """Wrapper function to handle the callback from ONNX Runtime"""
            if error:
                result_data.save_error(error)
                print(f"Error during inference: {error}")
            else:
                result_data.save_results(results)


        # Create data object to store results
        result_data = RunAsyncData()
        
        # Run the model asynchronously
        try:
            self.session.run_async(self.output_names, 
                                   {self.input_names[0]: input_tensor}
                                   , callback=callback_wrapper
                                   , user_data=result_data
                                   , run_options=None)
        except Exception as e:
            result_data.save_error(str(e))
        return result_data


    def process_output(self, outputs: list[np.ndarray]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        return outputs[0], outputs[1], outputs[2]

    def get_input_details(self) -> None:
        model_inputs = self.session.get_inputs()
        self.input_names = [model_inputs[i].name for i in range(len(model_inputs))]

        self.input_shape = model_inputs[0].shape
        self.input_height = self.input_shape[2]
        self.input_width = self.input_shape[3]

    def get_output_details(self) -> None:
        model_outputs = self.session.get_outputs()
        self.output_names = [model_outputs[i].name for i in range(len(model_outputs))]


class SAM2ImageDecoder:
    def __init__(self, path: str,
                 encoder_input_size: tuple[int, int],
                 orig_im_size: tuple[int, int] = None,
                 mask_threshold: float = 0.0) -> None:
        # Initialize model
        self.session = onnxruntime.InferenceSession(path, providers=onnxruntime.get_available_providers())

        self.orig_im_size = orig_im_size if orig_im_size is not None else encoder_input_size
        self.encoder_input_size = encoder_input_size
        self.mask_threshold = mask_threshold
        self.scale_factor = 4

        # Get model info
        self.get_input_details()
        self.get_output_details()

    def __call__(self, image_embed: np.ndarray,
                 high_res_feats_0: np.ndarray, 
                 high_res_feats_1: np.ndarray,
                 point_coords: np.ndarray, 
                 point_labels: np.ndarray,
                 input_mask: Optional[np.ndarray] = None) -> tuple[np.ndarray, ndarray]:

        return self.predict(
            image_embed, 
            high_res_feats_0, 
            high_res_feats_1, 
            point_coords, 
            point_labels,
            input_mask)

    def predict(self, image_embed: np.ndarray,
                 high_res_feats_0: np.ndarray, 
                 high_res_feats_1: np.ndarray,
                 point_coords: np.ndarray, 
                 point_labels: np.ndarray,
                 input_mask: Optional[np.ndarray] = None) -> tuple[np.ndarray, ndarray]:

        inputs = self.prepare_inputs(image_embed, high_res_feats_0, high_res_feats_1, point_coords, point_labels, input_mask)

        outputs = self.infer(inputs)

        return self.process_output(outputs)


    def prepare_inputs(self, image_embed: np.ndarray,
                       high_res_feats_0: np.ndarray, high_res_feats_1: np.ndarray,
                       point_coords: np.ndarray, point_labels: np.ndarray,
                       input_mask: Optional[np.ndarray] = None) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:

        
        input_point_coords, input_point_labels = self.prepare_points(point_coords, point_labels)
        

        

        # Prepare mask input
        if input_mask is not None:
            mask_input = cv2.resize(
                input_mask.astype(np.float32),
                (self.encoder_input_size[1] // self.scale_factor, 
                 self.encoder_input_size[0] // self.scale_factor),
                interpolation=cv2.INTER_LINEAR
            )
            mask_input = mask_input[None, None, ...]  # Add batch and channel dimensions
            has_mask_input = np.array([1], dtype=np.float32)
        else:
            num_labels = input_point_labels.shape[0]
            mask_input = np.zeros((num_labels, 1, 
                                 self.encoder_input_size[0] // self.scale_factor,
                                 self.encoder_input_size[1] // self.scale_factor), 
                                dtype=np.float32)
            has_mask_input = np.array([0], dtype=np.float32)


        original_size = np.array([self.orig_im_size[0], self.orig_im_size[1]], dtype=np.int32)

        return image_embed, high_res_feats_0, high_res_feats_1, input_point_coords, input_point_labels, mask_input, has_mask_input, original_size


    def prepare_points(self, point_coords: np.ndarray, point_labels: np.ndarray) -> tuple[np.ndarray, np.ndarray]:

        if point_coords is None or point_labels is None:
            # Default case for mask-only operation
            input_point_coords = np.zeros((1, 0, 2), dtype=np.float32)
            input_point_labels = np.zeros((1, 0), dtype=np.float32)
            return input_point_coords, input_point_labels

        input_point_coords = point_coords[np.newaxis, ...]
        input_point_labels = point_labels[np.newaxis, ...]

        input_point_coords[..., 0] = input_point_coords[..., 0] / self.orig_im_size[1] * self.encoder_input_size[1]  # Normalize x
        input_point_coords[..., 1] = input_point_coords[..., 1] / self.orig_im_size[0] * self.encoder_input_size[0]  # Normalize y

        return input_point_coords.astype(np.float32), input_point_labels.astype(np.float32)

    def infer(self, inputs: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]) -> list[np.ndarray]:
        start = time.perf_counter()

        outputs = self.session.run(self.output_names,
                                   {self.input_names[i]: inputs[i] for i in range(len(self.input_names))})

        print(f"infer time: {(time.perf_counter() - start) * 1000:.2f} ms")
        return outputs

    def process_output(self, outputs: list[np.ndarray]) -> tuple[np.ndarray, np.ndarray]:

        scores = outputs[1].squeeze()
        masks = outputs[0]
        masks = masks > self.mask_threshold
        masks = masks.astype(np.uint8).squeeze()

        return masks, scores

    def set_image_size(self, orig_im_size: tuple[int, int]) -> None:
        self.orig_im_size = orig_im_size

    def get_input_details(self) -> None:
        model_inputs = self.session.get_inputs()
        self.input_names = [model_inputs[i].name for i in range(len(model_inputs))]

    def get_output_details(self) -> None:
        model_outputs = self.session.get_outputs()
        self.output_names = [model_outputs[i].name for i in range(len(model_outputs))]


if __name__ == '__main__':
    from imread_from_url import imread_from_url
    import matplotlib.pyplot as plt

    encoder_model_path = "../models/sam2_hiera_base_plus_encoder.onnx"
    decoder_model_path = "../models/decoder.onnx"

    img_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c1/Racing_Terriers_%282490056817%29.jpg/1280px-Racing_Terriers_%282490056817%29.jpg"
    img = imread_from_url(img_url)

    # Initialize model
    sam2 = SAM2Image(encoder_model_path, decoder_model_path)

    # Encode image
    sam2.set_image(img)

    point_coords = (345, 300)
    box_coords = ((0, 100), (600, 700))
    label_id = 0
    is_positive = False

    # Decode image
    sam2.add_point(point_coords, is_positive, label_id)
    sam2.set_box(box_coords, label_id)
    masks, fine_masks = sam2.get_masks()

    cv2.circle(masked_img, point_coords, 5, (0, 0, 255), -1)
    cv2.rectangle(masked_img, box_coords[0], box_coords[1], (0, 255, 0), 2)

    cv2.imwrite("../doc/img/sam2_masked_img.jpg", masked_img)

    cv2.imshow("masked_img", masked_img)
    cv2.waitKey(0)
