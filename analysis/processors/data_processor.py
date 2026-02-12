from analysis.processors.geometry_processor import GeometryProcessor
from analysis.processors.stitching_processor import StitchingProcessor
from analysis.processors.component_processor import ComponentProcessor
from shapely import Point

class DataProcessor:
    """
    Handles processes related to parsing, modifying, restructuring data
    """
    @staticmethod
    def process_raw_points(points, inner_points, overlap_points, polygons):
        points, inner_points, debug_fits = StitchingProcessor.resolve_overlaps(points, inner_points, overlap_points, polygons)
        width_2d = GeometryProcessor.get_2d_width(polygons) if polygons else 0
        buffer_distance = 402
        #initial slider values
        slider_values = {
            "neighbour_margin_factor": 330,
            "boundary_margin_factor": 330,
            "max_connected_line_dist": 40,
            "max_component_offset_dist": 210,
            "max_stitching_offset_dist": 630
        }

        mapping_points = GeometryProcessor.assign_points_to_polygons(points, polygons)
        mapping_inner_points = GeometryProcessor.assign_points_to_polygons(inner_points, polygons)
        combined = GeometryProcessor.combined_geometry(polygons, width_2d/buffer_distance) if polygons else []
        
        connected_points = StitchingProcessor.process_point_groups(polygons, points, mapping_points, combined)
        connected_inner_points = StitchingProcessor.process_point_groups(polygons, inner_points, mapping_inner_points, combined)
        matches, stitching_alignment_closest_boundary = ComponentProcessor.alignment_match(polygons)
        return polygons, connected_points, connected_inner_points, slider_values, matches, stitching_alignment_closest_boundary

    @staticmethod
    def to_shapely_points(points):
        shapely_points = []
        for p in points:
            shapely_points.append(Point(p[0], p[1]))
        return shapely_points
    
    @staticmethod
    def reformat_to_polygon_objects(raw_polygons):
        label_mapping={
            0: 'background',
            1: 'layer0',
            2: 'layer1',
            3: 'layer2',
            4: 'layer3',
            5: 'swoosh'
            }
        contours = raw_polygons.get("contours", [])
        labels = raw_polygons.get("labels", [])

        if len(contours) != len(labels):
            raise ValueError("Contours and labels length mismatch")

        objects = []

        for idx, (contour, label) in enumerate(zip(contours, labels)):
            # Shapely requires at least 3 unique points
            if contour is None or len(contour) < 3:
                continue

            poly = Polygon(contour)

            # Skip empty or invalid results
            if poly.is_empty:
                continue

            objects.append({
                "id": idx,
                "polygon": poly,
                "label": label_mapping[label]
            })

        return objects