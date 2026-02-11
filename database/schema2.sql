CREATE TABLE polygons2 (
    img_id INT NOT NULL,
    polygon_index INT,
    label VARCHAR(255),
    vertices LONGTEXT NULL,
    PRIMARY KEY (img_id, polygon_index)
);

CREATE TABLE connected_points2 (
    point_id INT AUTO_INCREMENT PRIMARY KEY,
    img_id INT NOT NULL,
    boundary_linestring LONGTEXT CHARACTER SET ascii NULL,
    layer VARCHAR(255) NULL,
    point_data LONGTEXT CHARACTER SET ascii NULL,
    INDEX idx_image_id (img_id)
);

CREATE TABLE connected_inner_points2 (
    id INT AUTO_INCREMENT PRIMARY KEY,
    img_id INT NOT NULL,
    boundary_linestring LONGTEXT CHARACTER SET ascii NULL,
    layer VARCHAR(255) NULL,
    point_data LONGTEXT CHARACTER SET ascii NULL,
    INDEX idx_img_name (img_id)
);

CREATE TABLE matches2 (
    img_id INT PRIMARY KEY,
    match_data LONGTEXT NULL
);

CREATE TABLE stitching_alignment_closest_boundary2 (
    img_id INT PRIMARY KEY,
    line_data LONGTEXT CHARACTER SET ascii NULL
);