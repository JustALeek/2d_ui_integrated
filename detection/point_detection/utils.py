def get_slice_bboxes(image_height, image_width, slice_height, slice_width, overlap_height_ratio, overlap_width_ratio):
    """
    Generates bounding boxes for sliding window slicing (SAHI-style).
    Returns list of [x_min, y_min, x_max, y_max].
    """
    slice_bboxes = []
    y_max = y_min = 0
    y_overlap = int(slice_height * overlap_height_ratio)
    x_overlap = int(slice_width * overlap_width_ratio)

    while y_max < image_height:
        x_min = x_max = 0
        y_max = y_min + slice_height
        while x_max < image_width:
            x_max = x_min + slice_width
            
            # Adjust if we go out of bounds (snap to edge)
            if y_max > image_height:
                y_max = image_height
                y_min = image_height - slice_height
            if x_max > image_width:
                x_max = image_width
                x_min = image_width - slice_width
                
            slice_bboxes.append([x_min, y_min, x_max, y_max])
            x_min = x_max - x_overlap
        y_min = y_max - y_overlap
        
    return slice_bboxes