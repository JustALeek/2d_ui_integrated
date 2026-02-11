IMAGES_SAVE_SQL = """
INSERT INTO images (img_name, img_data) 
VALUES (%s, %s)
ON DUPLICATE KEY UPDATE 
    img_name = VALUES(img_name),
    img_data = VALUES(img_data)
"""

POLYGONS_SAVE_SQL = """
INSERT INTO polygons (img_id, polygon_index, label, vertices)
VALUES (%s, %s, %s, %s)
ON DUPLICATE KEY UPDATE
    label = VALUES(label),
    vertices = VALUES(vertices)
"""

SLIDER_VALUES_SAVE_SQL = """
INSERT INTO slider_values (
    img_id,
    neighbour_margin_factor,
    boundary_margin_factor,
    max_connected_line_dist,
    max_component_offset_dist,
    max_stitching_offset_dist
)
VALUES (%s, %s, %s, %s, %s, %s)
ON DUPLICATE KEY UPDATE
    neighbour_margin_factor = VALUES(neighbour_margin_factor),
    boundary_margin_factor = VALUES(boundary_margin_factor),
    max_connected_line_dist = VALUES(max_connected_line_dist),
    max_component_offset_dist = VALUES(max_component_offset_dist),
    max_stitching_offset_dist = VALUES(max_stitching_offset_dist)
"""

MATCHES_SAVE_SQL = """
INSERT INTO matches (img_id, match_data)
VALUES (%s, %s)
ON DUPLICATE KEY UPDATE
    match_data = VALUES(match_data)
"""

SACB_SAVE_SQL = """
INSERT INTO stitching_alignment_closest_boundary (img_id, lines_json)
VALUES (%s, %s)
ON DUPLICATE KEY UPDATE lines_json = VALUES(lines_json)
"""

IMAGES_LOAD_SQL = "SELECT * FROM images WHERE img_name = %s"

POLYGONS_LOAD_SQL = "SELECT polygon_index, label, vertices FROM polygons WHERE img_id = %s"

SLIDER_VALUES_LOAD_SQL = """
SELECT neighbour_margin_factor,
    boundary_margin_factor,
    max_connected_line_dist,
    max_component_offset_dist,
    max_stitching_offset_dist
    FROM slider_values
WHERE img_id = %s
"""

MATCHES_LOAD_SQL = "SELECT match_data FROM matches WHERE img_id = %s"

SACB_LOAD_SQL = "SELECT lines_json FROM stitching_alignment_closest_boundary WHERE img_id = %s"
