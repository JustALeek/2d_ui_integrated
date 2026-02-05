import numpy as np
from shapely import Point, LineString
import cv2

class VisualizationProcessor:
    """
    Visualization utilities for stitching and component alignment errors.
    """
    @staticmethod
    def visualize_best_fit_lines(vis, geometries, color=(0, 255, 0), thickness=1):
        """
        Visualizes best fit lines used to sort overlap points.
        """
        for geom in geometries:
            if geom is None:
                continue

            coords = np.array(geom.coords, dtype=int)
            for i in range(len(coords) - 1):
                cv2.line(vis, tuple(coords[i]), tuple(coords[i + 1]), color, thickness)
        return vis
    
    @staticmethod
    def compute_distance_along_connections(processed_pts):
        """
        Compute distances between consecutive stitching points.
        """
        dists = []
        for i in range(len(processed_pts)-1):
            dists.append(processed_pts[i+1]["point"].distance(processed_pts[i]["point"]))

        med_dist = np.median(dists)

        return dists, med_dist
    
    @staticmethod
    def visualize_stitching_error(vis, connected_points, neighbour_margin, boundary_margin, max_line_dist, type='points'):
        """
        Visualize stitching point spacing and boundary deviation.
        """
        stitching_alignment_candidates = []

        for ring_info, processed_pts in connected_points.items():
            pts = np.array([[pt["point"].x, pt["point"].y] for pt in processed_pts], dtype=np.float32)
            projected_pts = np.array([[pt["projected_point"].x, pt["projected_point"].y] for pt in processed_pts], dtype=np.float32)
            distances = np.array([pt["distance"] for pt in processed_pts])
            neighbour_dist, med_neighbour_dist = VisualizationProcessor.compute_distance_along_connections(processed_pts)

            num_connected_lines = np.zeros(len(processed_pts), dtype=np.int32)
            med_boundary_dist = np.median(distances)

            # ---- Connections ----
            p1s = pts[:-1]
            p2s = pts[1:]
            neighbour_dist = np.array(neighbour_dist)

            mask_connected = neighbour_dist < max_line_dist
            num_connected_lines[:-1] += mask_connected.astype(int)
            num_connected_lines[1:] += mask_connected.astype(int)

            # Batch draw connected lines
            for i in np.where(mask_connected)[0]:
                spi_ok = abs(neighbour_dist[i] - med_neighbour_dist) < neighbour_margin
                color = (255, 0, 0) if spi_ok else (0, 0, 255)
                cv2.line(vis, tuple(p1s[i].astype(int)), tuple(p2s[i].astype(int)), color, 1)

            # Candidate stitching misalignment
            if type == 'points' and ring_info[1] == "layer2":
                mask_candidate = (neighbour_dist < max_line_dist * 5.3) & (~mask_connected)
                for i in np.where(mask_candidate)[0]:
                    stitching_alignment_candidates.append(LineString([Point(*p1s[i]), Point(*p2s[i])]))

            # ---- Points & projections ----
            margin_ok = (np.abs(distances - med_boundary_dist) < boundary_margin) | (num_connected_lines < 2)
            for i in range(len(pts)):
                color = (255, 0, 0) if margin_ok[i] else (0, 0, 255)
                cv2.circle(vis, tuple(pts[i].astype(int)), 1, color, -1)

            # Projected points
            dists_proj = np.linalg.norm(pts - projected_pts, axis=1)
            mask_proj = dists_proj < max_line_dist
            for i in np.where(mask_proj)[0]:
                cv2.line(vis, tuple(pts[i].astype(int)), tuple(projected_pts[i].astype(int)), (0, 255, 255), 1)
                cv2.circle(vis, tuple(projected_pts[i].astype(int)), 1, (0, 0, 0), 1)
        return vis, stitching_alignment_candidates
    
    @staticmethod
    def visualize_component_alignment_error(vis, matches, max_component_offset_distance):
        for match in matches:
            alignment_ok = match["distance"] < max_component_offset_distance
            color = (255, 0, 0) if alignment_ok else (0, 0, 255)
            thickness = 1 if alignment_ok else 3

            # Overlay line (vectorized)
            overlay_pts = np.column_stack((
                match["overlay_line"]["x"],
                match["overlay_line"]["y"]
            )).astype(np.int32)

            if len(overlay_pts) > 1:
                cv2.polylines(vis,[overlay_pts],isClosed=False,color=color,thickness=thickness)

            # Mudguard line (vectorized)
            mudguard_pts = np.column_stack((
                match["mudguard_line"]["x"],
                match["mudguard_line"]["y"]
            )).astype(np.int32)

            if len(mudguard_pts) > 1:
                cv2.polylines(vis, [mudguard_pts], isClosed=False, color=(0, 0, 0), thickness=3)
        return vis
    
    @staticmethod
    def visualize_stitching_alignment_error(vis, stitching_alignment_to_check, max_stitching_offset_distance):
        """
        Highlight stitching segments exceeding allowed offset.
        """
        for line, val in stitching_alignment_to_check:
            if not val:
                continue
            d1, d2 = val
            if d1 > max_stitching_offset_distance or d2 > max_stitching_offset_distance:
                pts = np.asarray(line.coords, dtype=np.int32)
                cv2.polylines(vis, [pts], isClosed=False, color=(0, 0, 255), thickness=3)
        return vis