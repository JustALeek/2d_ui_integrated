import numpy as np
from shapely import LineString, Point
from analysis.processors.geometry_processor import GeometryProcessor

class ComponentProcessor:
    """
    Fit component outlines and measure inter-component misalignment.
    """
    @staticmethod
    def fit_outline(segment, trim_ratio=0.25, extension_ratio=0.3):
        """
        Fit quadratic curve to a boundary segment and extend it.
        """
        coords = np.array(segment.coords)
        if len(coords) < 2:
            return None

        min_v, max_v = np.min(coords, axis=0), np.max(coords, axis=0)
        orientation = 'horizontal' if (max_v[0] - min_v[0]) > (max_v[1] - min_v[1]) else 'vertical'

        dense = []
        for i in range(len(coords) - 1):
            p1, p2 = coords[i], coords[i + 1]
            steps = max(2, int(np.linalg.norm(p2 - p1)))
            for k in range(steps):
                dense.append(p1 + (k / steps) * (p2 - p1))
        dense.append(coords[-1])
        arr = np.array(dense)

        trim = int(len(arr) * trim_ratio)
        if len(arr) > 2 * trim + 5:
            arr = arr[trim:-trim]

        try:
            if orientation == 'vertical':
                coeffs = np.polyfit(arr[:, 1], arr[:, 0], 2)
            else:
                coeffs = np.polyfit(arr[:, 0], arr[:, 1], 2)
            poly = np.poly1d(coeffs)
        except:
            return None

        if orientation == 'vertical':
            iv = coords[:, 1]
        else:
            iv = coords[:, 0]

        iv_min, iv_max = iv.min(), iv.max()
        sample = np.linspace(iv_min, iv_max, 100)
        pred = poly(sample)

        d_iv = np.diff(sample)
        d_dv = np.diff(pred)
        arc_length = np.sum(np.sqrt(d_iv**2 + d_dv**2))

        extension_length = arc_length * extension_ratio

        deriv_func = poly.deriv()
        slope_min = deriv_func(iv_min)
        slope_max = deriv_func(iv_max)

        delta_min = extension_length / np.sqrt(1 + slope_min**2)
        delta_max = extension_length / np.sqrt(1 + slope_max**2)

        extended_iv_start = iv_min - delta_min
        extended_iv_end = iv_max + delta_max

        extrapolated_iv = np.linspace(extended_iv_start, extended_iv_end, 100)
        extrapolated_dv = poly(extrapolated_iv)

        if orientation == 'vertical':
            x, y = extrapolated_dv, extrapolated_iv
        else:
            x, y = extrapolated_iv, extrapolated_dv

        return {
            'x': x,
            'y': y,
            'shapely': LineString(np.column_stack((x, y)))
        }
    
    @staticmethod
    def quad_projected_distance(quad_points, overlay_fit, mudguard_fit):
        """
        quad_points: np.ndarray (4,2)  # mudguard quad
        ov_fit, mud_fit: fitted line dicts
        """
        overlay_line = overlay_fit['shapely']
        mudguard_line = mudguard_fit['shapely']

        dists = []

        for q in quad_points:
            qp = Point(q)

            # project quad point to overlay line
            overlay_proj_dist = overlay_line.project(qp)
            overlay_proj_pt = overlay_line.interpolate(overlay_proj_dist)

            # project quad point to mudguard line
            mudguard_proj_dist = mudguard_line.project(qp)
            mudguard_proj_pt = mudguard_line.interpolate(mudguard_proj_dist)

            # distance between projected points
            dists.append(overlay_proj_pt.distance(mudguard_proj_pt))

        # representative distance (min = closest structural alignment)
        return min(dists)
    
    @staticmethod
    def alignment_match(polygons):
        """
        Match overlay outlines to mudguard outlines.

        Returns:
            matches : list of best-fit overlay↔mudguard line pairs
            stitching_alignment_closest_boundary : overlay boundaries closest to mudguard
        """
        mudguards = [p for p in polygons if p["label"]=="layer0"]
        overlays = [p for p in polygons if p["label"]=="layer3"]

        matches, stitching_alignment_closest_boundary = [], []

        if not mudguards or not overlays:
            return matches, stitching_alignment_closest_boundary
        
        mid, old = 1, 1   # unique line IDs

        for mudguard in mudguards:
            # Approximate mudguard shape with quad
            coords = np.asarray(mudguard["polygon"].exterior.coords)[:-1]
            quad = GeometryProcessor.simplify_to_quad(coords)

            # Fit mudguard boundary segments
            mudguard_fits = []
            for line in GeometryProcessor.split_polygon_into_lines(mudguard["polygon"], quad):
                fitted_line = ComponentProcessor.fit_outline(line)
                if fitted_line:
                    fitted_line["id"] = mid
                    mid += 1
                    mudguard_fits.append(fitted_line)

            # Match closest overlay components
            for overlay in sorted(overlays, key=lambda x: mudguard["polygon"].distance(x["polygon"]))[:2]:
                overlay_fits = []
                for line in GeometryProcessor.split_polygon_into_lines(overlay["polygon"]):
                    fitted_line = ComponentProcessor.fit_outline(line)
                    if fitted_line:
                        fitted_line["id"] = old
                        old += 1
                        overlay_fits.append(fitted_line)

                # Generate all candidate pairings
                pairs = []
                for overlay_fit in overlay_fits:
                    for mudguard_fit in mudguard_fits:
                        pairs.append({
                            "overlay": overlay_fit,
                            "mudguard": mudguard_fit,
                            "center": GeometryProcessor.center_distance(overlay_fit, mudguard_fit),
                            "distance": ComponentProcessor.quad_projected_distance(quad, overlay_fit, mudguard_fit)
                        })

                if not pairs:
                    continue
                
                # Greedy matching with exclusivity
                start = len(matches)
                used_overlay, used_mudguard = set(), set()

                pairs.sort(key=lambda x: x["center"])
                p = pairs[0]
                used_overlay.add(p["overlay"]["id"])
                used_mudguard.add(p["mudguard"]["id"])
                matches.append({
                    "overlay_line": p["overlay"],
                    "mudguard_line": p["mudguard"],
                    "distance": p["distance"]
                })

                stitching_alignment_closest_boundary.append(p["overlay"]["shapely"])

                # Additional valid matches
                for r in sorted(pairs, key=lambda x:x["distance"]):
                    if r["overlay"]["id"] in used_overlay or r["mudguard"]["id"] in used_mudguard:
                        continue
                    used_overlay.add(r["overlay"]["id"])
                    used_mudguard.add(r["mudguard"]["id"])
                    matches.append({
                        "overlay_line": r["overlay"],
                        "mudguard_line": r["mudguard"],
                        "distance": r["distance"]
                    })

                # Remove worst extra match (enforce 1:1)
                if len(matches) - start > 1:
                    idx = max(range(start, len(matches)), key=lambda x: matches[x]["distance"])
                    matches.pop(idx)

        return matches, stitching_alignment_closest_boundary