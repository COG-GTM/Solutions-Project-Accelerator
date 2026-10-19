from __future__ import print_function
import time
import cv2
import numpy as np
import matplotlib
matplotlib.use('Agg')
from matplotlib import pyplot as plt
import imutils
from imutils.object_detection import non_max_suppression


def get_template_max_score(template: np.ndarray, mask: np.ndarray) -> float:
    """
    Calculate the maximum score of template matching.

    :param template: The template image to be matched.
    :type template: numpy.ndarray
    :param mask: The optional mask specifying where to look for the template.
    :type mask: numpy.ndarray
    :return: The maximum score of template matching.
    :rtype: float

    This function calculates the maximum score of template matching using the specified template and mask.

    Example:
        >>> get_template_max_score(template, mask)
        0.99
    """
    
    result = cv2.matchTemplate(template, template, cv2.TM_CCOEFF, mask=mask)
    _, maxVal, _, _ = cv2.minMaxLoc(result)
    return maxVal



def find_template_in_image(image: np.ndarray, template_image: np.ndarray, mask: np.ndarray,
                           min_size: tuple, found: tuple = None, progress = None, page=0, threshold=0.7) -> tuple:
    """
    Find the template in the image using scale invariant scanning.

    :param image: The image to search for the template.
    :type image: numpy.ndarray
    :param template_image: The template image to be matched.
    :type template_image: numpy.ndarray
    :param mask: The optional mask specifying where to look for the template.
    :type mask: numpy.ndarray
    :param min_size: The minimum size of the template.
    :type min_size: tuple
    :param found: The previously found template.
    :type found: tuple
    :param progress: The object used to update the ui progress string.
    :type progress: object
    :return: The found template.
    :rtype: tuple

    This function finds the template in the image using scale invariant scanning by resizing the image and template over a range of scales.

    Example:
        >>> find_template_in_image(image, template_image, mask, min_size, found, progress)
        (0.99, (x, y), scale, result, max_score)
    """
    scales = np.concatenate((np.linspace(0.5,1,20,endpoint=False),np.linspace(1,2,20)))

    # Order the scales based on their absolute distance from 1 to improve performance
    scales = scales[np.argsort(abs(scales - 1))]
    count = 0
    
    max_score = get_template_max_score(template_image,mask)
    for scale in scales:
        resized = imutils.resize(image, width=int(image.shape[1] * scale))
        r = image.shape[1] / float(resized.shape[1])
        

        if resized.shape[0] < min_size[0] or resized.shape[1] < min_size[1]:
            break

        
        result = cv2.matchTemplate(resized, template_image, cv2.TM_CCOEFF, mask=mask)
        
        _, maxVal, _, maxLoc = cv2.minMaxLoc(result)
        
        if found is None or maxVal > found[0] :
            result = cv2.normalize(result, None, 0, 1, cv2.NORM_MINMAX, -1)
            found = (maxVal, maxLoc, r, result, max_score)

            if maxVal/max_score > threshold:
                if progress:
                    progress("Finding linked graphic template using scale invariant scan 100% complete")
                return found

            
        if progress:
            count = count + 1
            progress("Finding linked graphic template using scale invariant scan " + str(int(count/scales.size*100)) + "% complete")
            


    return found





def scale_invariant_template_matching(image_scene: np.ndarray, template_image: np.ndarray, 
                                        template_mask: np.ndarray, threshold: float = 0.7,
                                        progress = None, use_invariant = False, page=0) -> tuple:
    """
    Perform scale invariant template matching on the image scene.

    :param image_scene: The image scene to search for the template.
    :type image_scene: numpy.ndarray
    :param template_image: The template image to be matched.
    :type template_image: numpy.ndarray
    :param template_mask: The optional mask specifying where to look for the template.
    :type template_mask: numpy.ndarray
    :param threshold: The threshold value for template matching. Default is 0.7.
    :type threshold: float
    :param progress: The object used to update the ui progress string.
    :type progress: object
    :param use_invariant: A flag to indicate whether to use scale invariant template matching. Default is False.
    :type use_invariant: bool
    :return: The result of the template matching.
    :rtype: tuple

    This function performs scale invariant template matching on the image scene using the specified template image and mask.

    Example:
        >>> scale_invariant_template_matching(image_scene, template_image, template_mask, threshold, progress, use_invariant)
        (1, result, locations)
    """

    tH, tW = template_image.shape[:2]
    mask=np.uint8(template_mask)
    result = cv2.matchTemplate(image_scene,template_image,cv2.TM_CCOEFF_NORMED,mask=mask)

    locations = np.where((result >= threshold) & (result != np.inf))

    if len(locations[0]) > 0 or not use_invariant:
        return (1,result,locations)
    
    found = find_template_in_image(image_scene.copy(), template_image.copy(), mask.copy(), (tH, tW)
                                   , progress=progress, page=page)
    if found is None:
        return (0,np.array([]),np.array([]))

    maxVal, _, scale, result, max_score = found

    if maxVal > max_score/2:
        locations = np.where((result >= threshold) & (result != np.inf))
        return (scale,result,locations)
    
    return (0,np.array([]),np.array([]))

    


if __name__== "__main__":
    # Example usage:
    
    img_object = cv2.imread('./data/JM_template.png', cv2.IMREAD_GRAYSCALE)
    img_mask = cv2.imread('./data/JM_mask.png',0)
    img_scene = cv2.imread('./data/JM_page-6.png', cv2.IMREAD_GRAYSCALE)
    img_object = cv2.threshold(img_object, 254, 255, cv2.THRESH_BINARY)[1]
    img_scene = cv2.threshold(img_scene, 254, 255, cv2.THRESH_BINARY)[1]


    result = scale_invariant_template_matching(img_scene, img_object, img_mask, 0.7)

    tH, tW = img_object.shape[:2]

    scale, scan_result, locations = result

    rects = []
    probs = []
    # loop over the starting (x, y)-coordinates again
    for pt in zip(*locations[::-1]):
        # get the probablity for the point
        probs.append(scan_result[pt[1]][pt[0]])

        # update our list of rectangles
        rects.append((pt[0] * scale, pt[1] * scale, int((pt[0] + tW) * scale), int((pt[1] + tH) * scale)))
                    
    pick = non_max_suppression(np.array(rects),probs)

    clone = np.dstack([img_scene, img_scene, img_scene])
    for (startX, startY, endX, endY) in pick:
        # draw the bounding box on the image
        cv2.rectangle(clone, (startX, startY), (endX, endY), (0,0,255), 10)

    plt.imshow(clone, 'gray')
    plt.show()
    ()
    
