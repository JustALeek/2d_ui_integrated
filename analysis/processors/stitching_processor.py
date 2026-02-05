from analysis.processors.geometry_processor import GeometryProcessor
import numpy as np
import shapely
from shapely import MultiPolygon, Point

class StitchingProcessor:
    """
    Ordering and grouping stitching points along boundaries.
    """
    @staticmethod
    def resolve_overlaps(points, inner_points, overlap_points, polygons, k=6, confidence_ratio=0.4):
        """
        Iteratively resolve overlap points.

        Each resolved overlap point becomes part of the neighbor set.
        """

        # Sort overlap points by proximity to existing points
        def nearest_labeled_distance(p):
            d1 = min([p.distance(q) for q in points], default=np.inf)
            d2 = min([p.distance(q) for q in inner_points], default=np.inf)
            return min(d1, d2)

        overlap_sorted = sorted(overlap_points, key=nearest_labeled_distance)
        debug_geometries = []

        for p in overlap_sorted:
            # No information to classify this point - default to "point"
            if not points or not inner_points:
                points.append(p)
                debug_geometries.append(geom_p)

            # Recollect knn each time an overlay point is processed
            pn = StitchingProcessor.k_nearest_neighbors(p, points, k, polygons)
            inn = StitchingProcessor.k_nearest_neighbors(p, inner_points, k, polygons)

            d_p, geom_p = GeometryProcessor.best_model_with_geometry(p, pn)
            d_i, geom_i = GeometryProcessor.best_model_with_geometry(p, inn)

            if d_p < confidence_ratio * d_i :
                points.append(p)
                debug_geometries.append(geom_p)
            else:
                inner_points.append(p)
                debug_geometries.append(geom_i)
        return points, inner_points, debug_geometries
    
    @staticmethod
    def k_nearest_neighbors(center_pt, candidates, k, polygons):
        """
        Returns the k nearest candidate points to center_pt in a set radius
        """
        max_radius = GeometryProcessor.get_2d_width(polygons)/20
        candidates = [p for p in candidates if p.distance(center_pt) <= max_radius]
        candidates = sorted(candidates, key=lambda p: p.distance(center_pt))
        return candidates[:k]
    
    @staticmethod
    def fit_local_quadratic(points):
        """
        Fit a local quadratic curve.
        Returns a callable distance function.
        """
        if len(points) < 3:
            return None

        coords = np.array([[p.x, p.y] for p in points])
        min_v, max_v = coords.min(axis=0), coords.max(axis=0)

        # Decide dominant axis
        horizontal = (max_v[0] - min_v[0]) > (max_v[1] - min_v[1])

        try:
            if horizontal:
                coeffs = np.polyfit(coords[:, 0], coords[:, 1], 2)
                poly = np.poly1d(coeffs)

                def distance_fn(pt):
                    x, y = pt.x, pt.y
                    return abs(y - poly(x))

            else:
                coeffs = np.polyfit(coords[:, 1], coords[:, 0], 2)
                poly = np.poly1d(coeffs)

                def distance_fn(pt):
                    x, y = pt.x, pt.y
                    return abs(x - poly(y))

            return distance_fn

        except np.linalg.LinAlgError:
            return None

    def process_points_by_outline(points_xy, ring):
        """
        Reorders a scattered list of points to follow the sequence of the polygon boundary.
        
        Logic:
        1. Project every point onto the boundary line (finding distance from start & projected point on the boundary).
        2. Sort points based on that linear distance.
        """
        mapping = []
        for point in points_xy:
            d = ring.project(point)

            mapping.append({
                "point": point,
                "sorting_distance": d,
                "projected_point": ring.interpolate(d),
                "distance": point.distance(ring)
            })

        mapping_sorted = sorted(mapping, key = lambda x: x["sorting_distance"])
        
        return mapping_sorted

    @staticmethod
    def process_point_groups(polygons, points, mapping, combined_geom):
        """
        Group points by outline and generate ordered connections.
        """
        combined_components = (list(combined_geom.geoms) if isinstance(combined_geom, MultiPolygon) else [combined_geom])

        map_point_to_projection_outline = {}

        for poly_idx, pt_indices in mapping.items():
            polygon = polygons[poly_idx]
            label = polygon["label"]
            pts = [points[i] for i in pt_indices]

            # Case A: Standard layers - use the polygon's own boundary
            if polygon["label"] != "layer2":
                map_point_to_projection_outline[(polygon["polygon"].boundary, label)] = pts

            # Case B: Layer 2 - use the constructed combined geometry components
            else:
                # Find WHICH part of the MultiPolygon the point belongs to
                for layer2_component in combined_components:
                    # Check the first point (assumption: group belongs to same component)
                    if layer2_component.covers(points[pt_indices[0]]):
                        map_point_to_projection_outline.setdefault((layer2_component.boundary, label), []).extend(pts)

        connected = {}

        for ring_info, pts in map_point_to_projection_outline.items():
            # Order the points so they form a continuous line along the shape
            ring = ring_info[0]
            processed_pts = StitchingProcessor.process_points_by_outline(pts, ring)

            n = len(processed_pts)
            
            # Skip if there are too few points to form a connection
            if n < 2:
                continue
            
            # Close the loop: connect the last point back to the first
            processed_pts.append(processed_pts[0]) 
            connected[ring_info] = processed_pts

        return connected
    
    @staticmethod
    def alignment_check(connected_points, stitching_alignment_closest_boundary, stitching_alignment_candidates):
        """
        Identify stitching segments that should be checked for alignment error.
        """
        # Extract overlay quad points
        quad_points = []
        for ring_info, processed_pts in connected_points.items():
            if ring_info[1] == "layer3":
                coords = [processed_pt["point"].coords[0] for processed_pt in processed_pts]
                quad_points.extend(GeometryProcessor.simplify_to_quad(coords))

        # Select closest stitching candidate to each overlay boundary
        stitching_lines_to_check = []
        for boundary in stitching_alignment_closest_boundary:
            distances = []
            for line in stitching_alignment_candidates:
                distances.append((line, shapely.distance(boundary.centroid, line.centroid)))
            distances = sorted(distances, key = lambda x:x[1])
            stitching_lines_to_check.append(distances[0][0])

        # Measure distances from stitching lines to quad points
        stitching_alignment_to_check = []
        for line in stitching_lines_to_check:
            distances = []
            for point in quad_points:
                distances.append(line.distance(Point(point)))
            distances = sorted(distances, key = lambda x:x)
            stitching_alignment_to_check.append([line, distances[:2]])

        return stitching_alignment_to_check
