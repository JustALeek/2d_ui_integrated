CREATE TABLE images(
    img_id INT AUTO_INCREMENT PRIMARY KEY,
    img_name VARCHAR(255) NOT NULL,
    img_data LONGBLOB NOT NULL,
    UNIQUE KEY uniq_img_name (img_name)
);

CREATE TABLE slider_values(
    img_id INT PRIMARY KEY NOT NULL,
    neighbour_margin_factor DECIMAL,
    boundary_margin_factor DECIMAL,
    max_connected_line_dist DECIMAL,
    max_component_offset_dist DECIMAL,
    max_stitching_offset_dist DECIMAL
);

CREATE TABLE polygons (
    img_id INT NOT NULL,
    polygon_index INT,
    label VARCHAR(255),
    vertices JSON NULL,
    PRIMARY KEY (img_id, polygon_index)
);

CREATE TABLE connected_points (
    point_id INT AUTO_INCREMENT PRIMARY KEY,
    img_id INT NOT NULL,
    boundary_linestring JSON NULL,
    layer VARCHAR(255) NULL,
    point_data JSON NULL,
    INDEX idx_image_id (img_id)
);

CREATE TABLE connected_inner_points (
    point_id INT AUTO_INCREMENT PRIMARY KEY,
    img_id INT NOT NULL,
    boundary_linestring JSON NULL,
    layer VARCHAR(255) NULL,
    point_data JSON NULL,
    INDEX idx_img_name (img_id)
);

CREATE TABLE matches (
    img_id INT PRIMARY KEY,
    match_data JSON NULL
);

CREATE TABLE stitching_alignment_closest_boundary (
    img_id INT PRIMARY KEY,
    lines_json JSON NULL
);

