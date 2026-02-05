import json
import cv2
import numpy as np
from shapely.geometry import Polygon, LineString, Point, MultiLineString
from shapely.wkt import loads
import mariadb

from .processors.data_processor import DataProcessor
from .processors.geometry_processor import GeometryProcessor
from .processors.stitching_processor import StitchingProcessor
from .processors.data_processor import DataProcessor
from .processors.visualization_processor import VisualizationProcessor
from config import post_processor_const

class MainManager:
    """Handles saving, loading, and running pipelines. Only class that has a connection to DB."""
    def __init__(self):
        self.conn = mariadb.connect(
            user="testuser",
            password="testpass",
            host="127.0.0.1",
            database="testdb")
    
    def save_dbdata(self, img_name, frame, polygons, connected_points, connected_inner_points, slider_values, matches, sacb):
        cur = self.conn.cursor()

        #Saving images
        _, buffer = cv2.imencode(".jpg", frame)
        img_bytes = buffer.tobytes()

        cur.execute(post_processor_const.IMAGES_SAVE_SQL, (img_name, img_bytes))

        #Saving polygons
        for poly_dict in polygons:
            polygon_index = poly_dict["id"]
            label = poly_dict.get("label", "")
            polygon_obj = poly_dict["polygon"]
            
            # Convert Shapely Polygon to list of coordinates
            vertices_list = list(polygon_obj.exterior.coords)

            # Convert to JSON string for storage
            vertices_json = json.dumps(vertices_list)
            
            cur.execute(post_processor_const.POLYGONS_SAVE_SQL, (img_name, polygon_index, label, vertices_json))

        # Saving connected_points and connected_inner_points
        self.save_point_data("connected_points", connected_points, img_name)
        self.save_point_data("connected_inner_points", connected_inner_points, img_name)

        # Saving slider_values
        cur.execute(
            post_processor_const.SLIDER_VALUES_SAVE_SQL,
            (
                img_name,
                slider_values.get("neighbour_margin_factor"),
                slider_values.get("boundary_margin_factor"),
                slider_values.get("max_connected_line_dist"),
                slider_values.get("max_component_offset_dist"),
                slider_values.get("max_stitching_offset_dist")
            )
        )

        # Saving matches
        serializable_matches = []
        for m in matches:
            entry = {}
            for key in ["overlay_line", "mudguard_line"]:
                line = m.get(key)
                if line is None:
                    entry[key] = None
                    continue
                # Convert numpy arrays to lists
                entry[key] = {
                    "x": line["x"].tolist() if hasattr(line["x"], "tolist") else list(line["x"]),
                    "y": line["y"].tolist() if hasattr(line["y"], "tolist") else list(line["y"]),
                    "id": line.get("id"),
                    "shapely": line["shapely"].wkt if isinstance(line["shapely"], LineString) else line["shapely"]
                }
            entry["distance"] = float(m.get("distance", 0))
            serializable_matches.append(entry)

        match_json = None if not serializable_matches else json.dumps(serializable_matches)
        cur.execute(post_processor_const.MATCHES_SAVE_SQL, (img_name, match_json))

        # Saving stitching_alignment_closest_boundary
        lines = []

        for line in sacb:
            if isinstance(line, LineString):
                lines.append(line.wkt)
            elif isinstance(line, str):
                lines.append(line)
            else:
                raise TypeError("Invalid line type")

        if not lines:
            cur.execute(post_processor_const.SACB_SAVE_SQL, (img_name, None))
        else:
            cur.execute(post_processor_const.SACB_SAVE_SQL, (img_name, json.dumps(lines)))

        self.conn.commit()

    def save_point_data(self, table_name, points, img_name):
        cur = self.conn.cursor()
        sql = f"""
        INSERT INTO {table_name} (
            img_name, boundary_linestring, layer,
            point_data
        )
        VALUES (%s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            boundary_linestring = VALUES(boundary_linestring),
            layer = VALUES(layer),
            point_data = VALUES(point_data)
        """
        
        for (linestring_obj, layer), points_list in points.items():
            if isinstance(linestring_obj, str):
                linestring_obj = loads(linestring_obj)
            # Convert LineString to list of coordinates and JSON-encode
            if isinstance(linestring_obj, LineString):
                linestring_coords = list(linestring_obj.coords)
            elif isinstance(linestring_obj, MultiLineString):
                # Flatten all coordinates from all LineStrings into a single list
                linestring_coords = []
                for ls in linestring_obj.geoms:
                    linestring_coords.extend(ls.coords)
            else:
                raise TypeError("Expected LineString or MultiLineString")
            linestring_json = json.dumps(linestring_coords)
                        
            point_data_json = json.dumps([
                {
                    "point": [pt_dict["point"].x, pt_dict["point"].y],
                    "sorting_distance": float(pt_dict["sorting_distance"]),
                    "projected_point": [pt_dict["projected_point"].x, pt_dict["projected_point"].y]
                                    if pt_dict.get("projected_point") else None,
                    "distance": float(pt_dict["distance"]) if pt_dict.get("distance") is not None else None
                }
                for pt_dict in points_list
            ])

            cur.execute(sql, (
                img_name,
                linestring_json,
                layer,
                point_data_json
            ))

    def load_dbdata(self, img_name):
        """
        Load data from database based on image name. Will handle any empty values or NULLs EXCEPT for when image is not found.
        """
        cur = self.conn.cursor()
        #Loading image
        cur.execute(post_processor_const.IMAGES_LOAD_SQL, (img_name,))
        row = cur.fetchone()
        if row is None:
            raise FileNotFoundError(f"Image '{img_name}' not found in database") 
        img_bytes = row[1]
        np_arr = np.frombuffer(img_bytes, dtype=np.uint8)
        img_data = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        #Loading polygons
        cur.execute(post_processor_const.POLYGONS_LOAD_SQL, (img_name,))
        rows = cur.fetchall()
        polygons = [
            {"id": r[0], "label": r[1], "polygon": Polygon(json.loads(r[2]))} 
            for r in rows
        ]

        #Loading points
        connected_points = self.load_point_data(img_name, "connected_points")
        connected_inner_points = self.load_point_data(img_name, "connected_inner_points")

        #Loading slider values
        cur2 = self.conn.cursor(dictionary = True)
        cur2.execute(post_processor_const.SLIDER_VALUES_LOAD_SQL, (img_name,))

        row = cur2.fetchone()

        slider_values = {key: float(value) if value is not None else None for key, value in row.items()}

        #Loading matches
        cur.execute(post_processor_const.MATCHES_LOAD_SQL, (img_name,))
        row = cur.fetchone()

        if not row or row[0] is None:
            matches = []
        else:
            match_data = row[0]
            if isinstance(match_data, str):
                matches = json.loads(match_data)
            else:
                matches = match_data

        cur.execute(post_processor_const.SACB_LOAD_SQL, (img_name,))

        row = cur.fetchone()

        # Default to empty list
        sacb = []

        if row and row[0] is not None:
            line_data = row[0]

            # If stored as JSON string
            if isinstance(line_data, str):
                wkt_list = json.loads(line_data)
            else:
                wkt_list = line_data  # already decoded JSON

            # Reconstruct Shapely LineStrings
            sacb = [loads(wkt) for wkt in wkt_list]
        return img_data, polygons, connected_points, connected_inner_points, slider_values, matches, sacb
    
    def load_point_data(self, img_name, table_name):
        cur = self.conn.cursor()
        cur.execute(f"""
            SELECT boundary_linestring, layer, point_data
            FROM {table_name}
            WHERE img_name = %s
        """, (img_name,))

        points = {}
        for boundary_json, layer, point_data_json in cur:
            # Convert JSON string to list of coordinates
            if isinstance(boundary_json, str):
                coords = json.loads(boundary_json)
            else:
                coords = boundary_json  # already a list

            line = LineString(coords)
            if line.is_empty:
                continue
            key = (line.wkt, layer)

            # Parse point_data JSON and reconstruct points
            point_list = []
            point_data_list = json.loads(point_data_json)
            for pt_dict in point_data_list:
                pt = Point(pt_dict["point"])
                proj = Point(pt_dict["projected_point"]) if pt_dict.get("projected_point") else None
                point_list.append({
                    "point": pt,
                    "sorting_distance": float(pt_dict["sorting_distance"]),
                    "projected_point": proj,
                    "distance": float(pt_dict["distance"]) if pt_dict.get("distance") is not None else None
                })
            points[key] = point_list
        return points
    
    def run_save_pipeline(self, img_name, img_data, points, inner_points, overlap_points, polygons):
        """
        Given inferred data from point_detection and segmentation, postprocess and save data to database.
        
        :param img_name: name of the formatted image
        :param img_data: image data as NumPy ndarray
        :param points: points with label "point"
        :param inner_points: points with label "inner"
        :param overlap_points: points with label "overlap"
        :param polygons: polygonal data - lineStrings matched with labels 
        """
        points = DataProcessor.to_shapely_points(points)
        inner_points = DataProcessor.to_shapely_points(inner_points)
        overlap_points = DataProcessor.to_shapely_points(overlap_points)
        polygons = GeometryProcessor.reformat_to_polygon_objects(polygons)
        polygons, connected_points, connected_inner_points, slider_values, matches, sacb = DataProcessor.process_raw_points(points, inner_points, overlap_points, polygons)
        self.save_dbdata(img_name, img_data, polygons, connected_points, connected_inner_points, slider_values, matches, sacb)

    def run_load_pipeline(self, img_name):
        """
        Given the name of the image, load saved data, perform error checking, and return fully visualized frame. 
        """
        img, polygons, points, inner_points, slider_values, matches, sacb = self.load_dbdata(img_name)
        nmf = slider_values["neighbour_margin_factor"]
        bmf = slider_values["boundary_margin_factor"]
        mcld = slider_values["max_connected_line_dist"]
        mcod = slider_values["max_component_offset_dist"]
        msod = slider_values["max_stitching_offset_dist"]
        # Visualization base
        alpha = 0.7
        vis = img.copy()
        vis = cv2.addWeighted(vis, alpha, np.full_like(img, 255), 1 - alpha, 0)

        # Draw stitching
        vis, stitching_alignment_candidates = (
            VisualizationProcessor.visualize_stitching_error(vis, points, nmf, bmf, mcld, 'points')
            if points else (vis, [])
        )
        vis, _ = (
            VisualizationProcessor.visualize_stitching_error(vis, inner_points, nmf, bmf, mcld, 'inner_points')
            if inner_points else (vis, [])
        )

        # Draw component alignment
        vis = VisualizationProcessor.visualize_component_alignment_error(vis, matches, mcod) if matches else vis

        # Stitching alignment
        stitching_alignment_to_check = StitchingProcessor.alignment_check(points, sacb, stitching_alignment_candidates) if sacb and stitching_alignment_candidates and points else []
        vis = VisualizationProcessor.visualize_stitching_alignment_error(vis, stitching_alignment_to_check, msod) if stitching_alignment_to_check else vis

        return vis, slider_values
        