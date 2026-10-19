import logging
import math
import time
from typing import List
import numpy as np
import cv2

from bin.logic_internal_database import Database
from bin.logic_linked_graphic_scanner import Template_Flip, Template_Rotate

class SIFTMatcher:
    def __init__(self):
        # Initialize SIFT detector
        self.sift = cv2.SIFT_create(edgeThreshold=1000, contrastThreshold=0.04)
        

    def match(self, template_image, search_image, template_mask
              ,template_flip:List[Template_Flip]=[Template_Flip.NONE],template_rotate:List[Template_Rotate]=[Template_Rotate.NONE]
              ,document_type=Database.DRAWING):
        """ Perform SIFT feature matching between the template and search images.
        
        Parameters:
        -----------
        template_image : numpy.ndarray
            The template image to search for
        search_image : numpy.ndarray
            The image to search in
        mask : numpy.ndarray
            Optional mask for feature detection
            
        Returns:
        --------
        new_template_image : numpy.ndarray
            The transformed template image
        new_template_mask : numpy.ndarray
            The transformed template mask
        template_roi : numpy.ndarray
            The transformed template polygon
        scale_factor : float
            The scale factor between the original and transformed polygons
        homography : numpy.ndarray
            The homography matrix
        success : bool
            True if the transformation was successful, False otherwise
        """

        debug = True 

        template_flip = [Template_Flip.NONE, Template_Flip.HORIZONTALLY]

        start = time.time()
        
        _template_image = cv2.cvtColor(template_image, cv2.COLOR_RGB2GRAY)
        _search_image = cv2.cvtColor(search_image, cv2.COLOR_RGB2GRAY)

        matching_results = {
                                'best_match' : None,
                                'best_match_count' : 0,
                                'best_match_mask' : None,
                                'best_homography' : None,
                                'best_flip' : Template_Flip.NONE,
                                'best_rotation' : Template_Rotate.NONE
                            }

        keypoints2, descriptors2 = self.sift.detectAndCompute(_search_image, None)

        # Check if we have enough keypoints
        if descriptors2 is None or len(keypoints2) < 4:
            raise ValueError("Not enough keypoints detected in the selected region")
        
        # Process each template variant
        for flip in template_flip:
            if flip is not Template_Flip.NONE:
                _template = cv2.flip(_template_image, flip.value)
                _mask = cv2.flip(template_mask, flip.value)
            else:
                _template = _template_image
                _mask = template_mask
            
            

            matching_results = self.run_matching(debug
                            , search_image
                            , keypoints2
                            , descriptors2
                            , flip
                            , _template
                            , _mask
                            , matching_results)

        if matching_results['best_match'] is None:
            logging.error("No matches found")
            raise ValueError("No good matches found")
            
        logging.info(f"Best match: Flip {matching_results['best_flip']} and " +
                     f"rotation {matching_results['best_rotation']} with {matching_results['best_match_count']} inliers")

        
        (transformed_corners
         , new_template_image
         , scale_factor
         , new_template_mask) = self.process_result(template_image
                                                    , search_image
                                                    , matching_results)
        
        if debug:
            # Visualize the results
            cv2.imshow('best_match_mask', matching_results['best_match_mask'])
            cv2.waitKey(0)

            
            # Make a copy of the search image
            match_img = search_image.copy()
            match_img_cv = np.array(match_img)
            
            # Draw the polygon
            cv2.polylines(match_img_cv, [np.int32(transformed_corners)], True, (0, 255, 0), 3)
            
            cv2.imshow('Match', match_img_cv)
            cv2.waitKey(0)

        logging.info(f"SIFT matching took {time.time() - start:.2f} seconds")
    
        return new_template_image, new_template_mask, scale_factor
    


    def run_matching(self, debug, search_image, keypoints2, descriptors2, flip, __template, __mask, result):
        """Run the SIFT feature matching algorithm."""

        # Detect keypoints and compute descriptors
        keypoints1, descriptors1 = self.sift.detectAndCompute(__template, __mask)
        
        
        # Check if we have enough keypoints
        if descriptors1 is None or  len(keypoints1) < 4:
            raise ValueError("Not enough keypoints detected in the template")
    
            
        # Match descriptors (FLANN for better performance)
        FLANN_INDEX_KDTREE = 1
        index_params = dict(algorithm=FLANN_INDEX_KDTREE, trees=5)
        search_params = dict(checks=50)
        flann = cv2.FlannBasedMatcher(index_params, search_params)
            
        matches = flann.knnMatch(descriptors1, descriptors2, k=2)
            
        # Apply Lowe's ratio test
        good_matches = []
        for m, n in matches:
            if m.distance < 0.75 * n.distance:
                good_matches.append(m)

        if debug:
            # Draw matches
            img_matches = cv2.drawMatches(__template, keypoints1, search_image, keypoints2, good_matches, None, flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS)
            cv2.imshow('Matches', img_matches)
            cv2.waitKey(0)
            
        # Check if we have enough good matches
        min_matches = 5
        if len(good_matches) >= min_matches:
                # Extract the matched keypoints
            src_pts = np.float32([keypoints1[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
            dst_pts = np.float32([keypoints2[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)
                
                # Find homography using RANSAC
            homography, homography_mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
                
            if homography is not None:
                    # Count inliers (matches that fit the homography)
                inlier_count = np.sum(homography_mask)
                rotation = self.determine_rotation(homography)
                if rotation == Template_Rotate.NONE:
                    rotated_mask = __mask
                else:
                    rotated_mask = cv2.rotate(__mask, rotation.value)
                    # Update best match
                if not inlier_count or inlier_count > result['best_match_count']:
                    result = {
                        'best_match' : good_matches,
                        'best_match_count' : inlier_count,
                        'best_match_mask' : rotated_mask,
                        'best_homography' : homography,
                        'best_flip' : flip.value,
                        'best_rotation' : rotation
                    }
            else:
                logging.warning(f"Flip {flip.value}: Failed to find homography")

        return result
    


    def process_result(self, template_image, search_image, matching_results):
        '''Process the result of the SIFT matching to extract the transformed template image and mask.'''

        # Reshape the polygon to the format expected by perspectiveTransform
        h, w = template_image.shape[:2]
        
        # Define the corners of the template image
        corners = np.float32([[0, 0], [0, h-1], [w-1, h-1], [w-1, 0]]).reshape(-1, 1, 2)

        # Flip the polygon if needed
        if matching_results['best_flip'] == Template_Flip.HORIZONTALLY:
            # Flip x-coordinates
            corners[:, :, 0] = template_image.shape[1] - corners[:, :, 0]
        elif matching_results['best_flip'] == Template_Flip.VERTICALLY:
            # Flip y-coordinates
            corners[:, :, 1] = template_image.shape[0] - corners[:, :, 1]
        elif matching_results['best_flip'] == Template_Flip.VERTICALLY_HORIZONTALLY:
            # Flip both x and y
            corners[:, :, 0] = template_image.shape[1] - corners[:, :, 0]
            corners[:, :, 1] = template_image.shape[0] - corners[:, :, 1]

        # Rotate the polygon if needed
        if matching_results['best_rotation'] == Template_Rotate.CW_90:
            # Rotate 90 degrees clockwise
            corners = np.float32([[corners[1, 0], corners[0, 0], corners[3, 0], corners[2, 0]]])
        elif matching_results['best_rotation'] == Template_Rotate.CW_180:
            # Rotate 180 degrees clockwise
            corners = np.float32([[corners[2, 0], corners[1, 0], corners[0, 0], corners[3, 0]]])
        elif matching_results['best_rotation'] == Template_Rotate.CW_270:
            # Rotate 270 degrees clockwise
            corners = np.float32([[corners[3, 0], corners[2, 0], corners[1, 0], corners[0, 0]]])
        
        # Apply the perspective transformation
        transformed_corners = cv2.perspectiveTransform(corners, matching_results['best_homography'])

        # Create a new template image using the transformed corners and the search image
        minx = max(0, int(np.min(transformed_corners[:, :, 0])))
        maxx = min(search_image.shape[1], int(np.max(transformed_corners[:, :, 0])))
        miny = max(0, int(np.min(transformed_corners[:, :, 1])))
        maxy = min(search_image.shape[0], int(np.max(transformed_corners[:, :, 1])))
        new_template_image = search_image.copy()[miny:maxy, minx:maxx]

        # Determine the scale factor between the original and transformed corners
        scale_factor = np.linalg.norm(transformed_corners[0] - transformed_corners[1]) / np.linalg.norm(corners[0] - corners[1])
        
        # Scale the mask if provided using the scale factor
        new_template_mask = cv2.resize(matching_results['best_match_mask'], (new_template_image.shape[1], new_template_image.shape[0]))
        return transformed_corners,new_template_image,scale_factor,new_template_mask
    

    def determine_rotation(self, homography):
        """Uses the angle of rotation to determine the rotation of the template image.
        Returning a Rotation enum value."""

        angle = self.extract_rotation_angle(homography)

        if -5 < angle < 5:
            return Template_Rotate.NONE
        elif 85 < angle < 95:
            return Template_Rotate.CW_90
        elif 175 < angle < 185:
            return Template_Rotate.CW_180
        elif 265 < angle < 275:
            return Template_Rotate.CW_270
        else:
            return Template_Rotate.NONE
    

    def extract_rotation_angle(self, homography):
        # Decompose the homography matrix
        # We're interested in the rotation component
        
        # Normalize the homography matrix
        homography = homography / homography[2, 2]
        
        # Extract rotation part (top-left 2x2 submatrix)
        rotation_part = homography[0:2, 0:2]
        
        # Compute the scale factors
        scale_x = math.sqrt(rotation_part[0, 0]**2 + rotation_part[1, 0]**2)
        scale_y = math.sqrt(rotation_part[0, 1]**2 + rotation_part[1, 1]**2)
        
        # Normalize to remove scaling
        a = rotation_part[0, 0] / scale_x
        b = rotation_part[1, 0] / scale_x
        
        # Calculate the rotation angle in radians
        angle_rad = math.atan2(b, a)
        
        # Convert to degrees
        angle_deg = math.degrees(angle_rad)
        
        return angle_deg
            

