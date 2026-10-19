import cv2
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def detect_character_boundaries(image, debug=False):
    """
    Detect character boundaries in an image containing text using histogram analysis.
    
    Args:
        image (np.array): The input image
        debug (bool): If True, displays intermediate processing steps
        
    Returns:
        tuple: (original_image, character_contours, background_color)
    """
    
    # Create a copy for visualization
    original = image.copy()
    
    # Convert to grayscale for processing
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Determine background color by sampling the image border
    border_pixels = []
    h, w = gray.shape
    
    # Sample top, bottom, left, and right borders
    border_pixels.extend(gray[0, :])  # Top row
    border_pixels.extend(gray[h-1, :])  # Bottom row
    border_pixels.extend(gray[:, 0])  # Left column
    border_pixels.extend(gray[:, w-1])  # Right column
    
    # Find the most common value (mode) as the background color
    border_pixels = np.array(border_pixels)
    background_value = int(np.bincount(border_pixels).argmax())

    
    if debug:
        plt.figure(figsize=(12, 8))
        plt.subplot(221)
        plt.imshow(cv2.cvtColor(original, cv2.COLOR_BGR2RGB))
        plt.title('Original Image')
        
        plt.subplot(222)
        plt.imshow(gray, cmap='gray')
        plt.title('Grayscale Image')
    

    scaled = False
    scale_factor = 1.0

    # Resize the binary image to have a minimum height or width of 50 pixels
    h, w = gray.shape
    if min(h, w) < 50:
        scale_factor = 50 / min(h, w)
        new_w = int(w * scale_factor)
        new_h = int(h * scale_factor)
        gray = cv2.resize(gray, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
        scaled = True
        
        if debug:
            print(f"Resized binary image from {w}x{h} to {new_w}x{new_h}")
    
    # Create a binary image (text vs background)
    # If background is light (> 127), we invert the threshold
    if background_value > 127:
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    else:
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    if debug:
        plt.subplot(224)
        plt.imshow(binary, cmap='gray')
        plt.title('Binary Image')
        plt.tight_layout()
        plt.show()

    # Apply some morphological operations to improve character separation
    #kernel = np.ones((3,3), np.uint8)
    #binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)

    if debug:
        cv2.imshow('binary', binary)
        cv2.waitKey(0)
    
    # Find contours of characters
    contours, hierarchy = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Filter out small contours (noise)
    min_contour_area = 10  # Adjust based on your image resolution
    filtered_contours = [cnt for cnt in contours if cv2.contourArea(cnt) > min_contour_area]
    
    # Scale contours back to original image size if we resized
    if scaled:
        inverse_scale = 1.0 / scale_factor
        for i in range(len(filtered_contours)):
            filtered_contours[i] = np.array([np.multiply(pt[0], inverse_scale).astype(int) for pt in filtered_contours[i]])
            
        if debug:
            print(f"Scaled contours back to original image dimensions (scale factor: {inverse_scale:.2f})")

    # Determine background color in BGR format for the original image
    if background_value > 127:
        # Light background
        background_color = (255, 255, 255)  # White
    else:
        # Dark background
        background_color = (0, 0, 0)  # Black
    
    # Draw contours on the original image for visualization
    result = original.copy()
    cv2.drawContours(result, filtered_contours, -1, (0, 255, 0), 2)
    
    if debug:
        plt.figure(figsize=(10, 6))
        plt.imshow(cv2.cvtColor(result, cv2.COLOR_BGR2RGB))
        plt.title(f'Detected Character Boundaries (Found {len(filtered_contours)} characters)')
        plt.axis('off')
        plt.show()

    # Sort contours from left to right, then top to bottom (reading order)
    bounding_boxes = [cv2.boundingRect(cnt) for cnt in filtered_contours]

    sorted_bounding_boxes = sorted(bounding_boxes, key=lambda box: box[0])

    text_dict = {}
    height, _ = original.shape
    for j, sorted_box in enumerate(sorted_bounding_boxes):
        x, y, w, h = sorted_box
        text_dict['top'].append(height - y)
        text_dict['bottom'].append(height - y - h)
        text_dict['left'].append(x)
        text_dict['right'].append(x + w)

    
    return text_dict

def analyze_character_spacing(contours):
    """
    Analyze the spacing between characters based on detected contours.
    
    Args:
        contours (list): List of character contours
        
    Returns:
        tuple: (avg_spacing, std_spacing) - Average spacing and standard deviation
    """
    if len(contours) < 2:
        return 0, 0
    
    # Sort contours from left to right
    bounding_boxes = [cv2.boundingRect(cnt) for cnt in contours]
    sorted_indices = sorted(range(len(bounding_boxes)), key=lambda i: bounding_boxes[i][0])
    
    # Calculate distances between adjacent characters
    distances = []
    for i in range(len(sorted_indices) - 1):
        current_idx = sorted_indices[i]
        next_idx = sorted_indices[i + 1]
        
        x1, _, w1, _ = bounding_boxes[current_idx]
        x2, _, _, _ = bounding_boxes[next_idx]
        
        # Distance from the end of current character to the start of next
        distance = x2 - (x1 + w1)
        distances.append(distance)
    
    # Calculate statistics
    avg_spacing = np.mean(distances) if distances else 0
    std_spacing = np.std(distances) if distances else 0
    
    return avg_spacing, std_spacing