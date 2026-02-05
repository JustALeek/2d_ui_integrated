from shapely import LineString, Polygon, MultiPoint
from shapely.ops import split, linemerge, unary_union
import numpy as np

class GeometryProcessor:
    """
    Geometric utilities: polygon containment, simplification, splitting.
    """    
    @staticmethod
    def get_2d_width(polygons):
        all_bounds = [polygon["polygon"].bounds for polygon in polygons]
        global_min_x = min(b[0] for b in all_bounds)
        global_max_x = max(b[2] for b in all_bounds)
        return global_max_x - global_min_x
    
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
    
    @staticmethod
    def fit_line_pca(points):
        """
        Fit a line using PCA.
        points: list of shapely Points
        Returns: (centroid, direction_unit_vector)
        """
        if len(points) < 2:
            return None

        coords = np.array([[p.x, p.y] for p in points])
        centroid = coords.mean(axis=0)

        # PCA via SVD
        _, _, Vt = np.linalg.svd(coords - centroid)
        direction = Vt[0]          # principal direction
        direction /= np.linalg.norm(direction)

        return centroid, direction
    
    @staticmethod
    def pca_line_geometry(points, length=200):
        res = GeometryProcessor.fit_line_pca(points)
        if not res:
            return None

        centroid, direction = res
        p1 = centroid - direction * length
        p2 = centroid + direction * length
        return LineString([tuple(p1), tuple(p2)])
    
    @staticmethod
    def quadratic_geometry(points, samples=50):
        if len(points) < 3:
            return None

        coords = np.array([[p.x, p.y] for p in points])
        min_v, max_v = coords.min(axis=0), coords.max(axis=0)

        horizontal = (max_v[0] - min_v[0]) > (max_v[1] - min_v[1])

        try:
            if horizontal:
                poly = np.poly1d(np.polyfit(coords[:, 0], coords[:, 1], 2))
                xs = np.linspace(min_v[0], max_v[0], samples)
                ys = poly(xs)
            else:
                poly = np.poly1d(np.polyfit(coords[:, 1], coords[:, 0], 2))
                ys = np.linspace(min_v[1], max_v[1], samples)
                xs = poly(ys)

            return LineString(np.column_stack([xs, ys]))

        except np.linalg.LinAlgError:
            return None
    
    @staticmethod
    def best_model_with_geometry(point, neighbors):
        """
        Returns:
            best_distance, best_geometry
        """
        best_d = np.inf
        best_geom = None

        if not neighbors:
            return best_d, best_geom

        # PCA line
        pca_geom = GeometryProcessor.pca_line_geometry(neighbors)
        if pca_geom:
            d = pca_geom.distance(point)
            if d < best_d:
                best_d = d
                best_geom = pca_geom

        # Quadratic
        quad_geom = GeometryProcessor.quadratic_geometry(neighbors)
        if quad_geom:
            d = quad_geom.distance(point)
            if d < best_d:
                best_d = d
                best_geom = quad_geom

        return best_d, best_geom

    @staticmethod
    def assign_points_to_polygons(points, polygons):
        mapping = {}
        for idx, pt in enumerate(points):
            assigned_poly = None
            for j, poly in enumerate(polygons):
                if poly["polygon"].covers(pt):
                    assigned_poly = j
                    break

            if assigned_poly is not None:
                mapping.setdefault(assigned_poly, []).append(idx)

        return mapping
     
    @staticmethod
    def combined_geometry(polygons, buffer_distance):
        """
        Create cleaned Layer2 geometry:
        - union of layer2/layer3
        - subtract background

        Returns:
            MultiPolygon for layer2 components
        """
        layer2 = unary_union([p["polygon"] 
                              for p in polygons if p["label"] in ("layer2", "layer3")]
                              )
        background = unary_union([p["polygon"] 
                                  for p in polygons if p["label"] in ("layer0", "background")]
                                  )

        return layer2.buffer(buffer_distance).difference(background)
    
    @staticmethod
    def calculate_triangle_area(p1, p2, p3):
        """
        Triangle area for polygon simplification.
        """
        return 0.5 * abs(
            p1[0] * (p2[1] - p3[1]) +
            p2[0] * (p3[1] - p1[1]) +
            p3[0] * (p1[1] - p2[1])
        )

    @staticmethod
    def simplify_to_quad(coords):
        """
        Reduce polygon boundary to 4 dominant vertices (quad).
        Used to approximate rectangular components.
        """
        pts = list(coords)
        while len(pts) > 4:
            min_area = float("inf")
            remove_idx = -1
            for i in range(len(pts)):
                area = GeometryProcessor.calculate_triangle_area(
                    pts[i - 1], pts[i], pts[(i + 1) % len(pts)]
                )
                if area < min_area:
                    min_area = area
                    remove_idx = i
            del pts[remove_idx]
        return np.array(pts)

    @staticmethod
    def split_polygon_into_lines(polygon, quad_points=None):
        """
        Split polygon boundary into line segments using quad vertices.
        """
        coords = np.asarray(polygon.exterior.coords)[:-1]
        if quad_points is None:
            quad_points = GeometryProcessor.simplify_to_quad(coords)

        boundary = polygon.boundary
        cutters = MultiPoint(quad_points)
        segments = list(split(boundary, cutters).geoms)

        # Merge first/last if split wraps around
        if len(segments) > len(cutters.geoms):
            first, last = segments.pop(0), segments.pop(-1)
            segments.append(linemerge([last, first]))

        return segments
    
    @staticmethod
    def center_distance(f1, f2):
        """
        Distance between centers of two fitted outlines.
        """
        c1 = np.array([np.mean(f1['x']), np.mean(f1['y'])])
        c2 = np.array([np.mean(f2['x']), np.mean(f2['y'])])
        return np.linalg.norm(c1 - c2)