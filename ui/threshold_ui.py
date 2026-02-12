"""
Threshold Configuration Module for the 4K Inspection System.
Provides a GUI to adjust and persist image processing thresholds to JSON.
"""

import os

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QHBoxLayout, QVBoxLayout, QLabel, QGroupBox,
                             QSlider, QSizePolicy, QPushButton)

from config import main_const
from util.file import File

class ThresholdUi(QGroupBox):

    threshold_changed_signal = pyqtSignal()

    def __init__(self, logger, manager, history, image, parent=None):
        super().__init__(main_const.THRESHOLD_TITLE_TEXT, parent)
        self.logger = logger
        self.config_path = os.path.join("config", "main_config.json")
        self.manager = manager
        self.image = image
        
        self._load_config()
        self._init_styling()
        self._setup_ui()

    def _init_styling(self):
        """Sets the visual CSS style for the GroupBox container."""

        self.setStyleSheet("""
            QGroupBox { font-weight: bold; border: 2px solid #BCBCBC; border-radius: 6px; margin-top: 12px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 3px 0 3px; }
        """)

    def _setup_ui(self):
        """Configures the vertical layout and initializes individual slider rows."""

        layout = QVBoxLayout(self)

        # Create rows for each threshold parameter
        self.val_lab1, self.slider1 = self._create_slider_row(layout, "인접 땀수 여백: ", 165, 660, self.n_margin, 1)
        self.val_lab2, self.slider2 = self._create_slider_row(layout, "외곽 경계 여백: ", 165, 660, self.b_margin, 2)
        self.val_lab3, self.slider3 = self._create_slider_row(layout, "선 연결 허용치: ", 10, 100, self.conn_dist, 3)
        self.val_lab4, self.slider4 = self._create_slider_row(layout, "부품 이탈 허용치: ", 105, 420, self.comp_dist, 4)
        self.val_lab5, self.slider5 = self._create_slider_row(layout, "땀수 이탈 허용치: ", 315, 1260, self.stitch_dist, 5)

        save_button = QPushButton("저장")
        save_button.clicked.connect(self._save_config)

        save_button.setFixedWidth(100)
        save_button.setStyleSheet("""
            QPushButton {
                font-size: 14px;
                background-color: #2D89EF;
                color: white;
                border-radius: 6px;
            }
        """)

        layout.addWidget(save_button, alignment=Qt.AlignmentFlag.AlignRight)

    def _create_slider_row(self, parent_layout, label_text, min_v, max_v, init_v, idx):
        """Generates a horizontal slider row with a title, slider, and value label."""

        h_layout = QHBoxLayout()
        
        # Label for the parameter name
        title_lab = QLabel(label_text)
        title_lab.setFixedWidth(100)
        title_lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Slider for adjustment
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(min_v, max_v)
        slider.setValue(init_v)
        slider.setMinimumWidth(self.width() - 100)
        slider.setMaximumWidth(self.width() + 150)
        slider.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        
        # Label to display current pixel value
        val_lab = QLabel(f"{init_v}px")
        val_lab.setFixedWidth(40)
        val_lab.setAlignment(Qt.AlignmentFlag.AlignCenter)

        h_layout.addWidget(title_lab)
        h_layout.addWidget(slider)
        h_layout.addWidget(val_lab)
        parent_layout.addLayout(h_layout)

        # Trigger update on slider movement
        slider.valueChanged.connect(lambda val: self._update_value(val, idx))
        
        return val_lab, slider
    
    def _update_value(self, val, idx):
        """Updates internal state variables and UI labels based on slider input."""

        # Map indices to specific threshold variables
        if   idx == 1: self.n_margin = val; self.val_lab1.setText(f"{val}px"); self.slider1.setValue(int(val)) 
        elif idx == 2: self.b_margin = val; self.val_lab2.setText(f"{val}px"); self.slider2.setValue(int(val))
        elif idx == 3: self.conn_dist = val; self.val_lab3.setText(f"{val}px"); self.slider3.setValue(int(val))
        elif idx == 4: self.comp_dist = val; self.val_lab4.setText(f"{val}px"); self.slider4.setValue(int(val))
        elif idx == 5: self.stitch_dist = val; self.val_lab5.setText(f"{val}px"); self.slider5.setValue(int(val))
        
        # Persist changes and notify other modules
        self.threshold_changed_signal.emit()

    def _update_value_dict(self, slider_values):
        """Updates internal state variables and UI labels based on slider input."""

        # Map indices to specific threshold variables
        self._update_value(slider_values["neighbour_margin_factor"], 1)
        self._update_value(slider_values["boundary_margin_factor"], 2)
        self._update_value(slider_values["max_connected_line_dist"], 3)
        self._update_value(slider_values["max_component_offset_dist"], 4)
        self._update_value(slider_values["max_stitching_offset_dist"], 5)
        
        # Persist changes and notify other modules
        self.threshold_changed_signal.emit()

    def _load_config(self):
        """initializes default slider values."""

        self.n_margin, self.b_margin = 330, 330
        self.conn_dist, self.comp_dist, self.stitch_dist = 40, 210, 630
        

    def _save_config(self):
        """Persists the current threshold configuration to the database."""
        data = self.image.current_image_data
        slider_values = {
            "neighbour_margin_factor": self.n_margin,
            "boundary_margin_factor": self.b_margin,
            "max_connected_line_dist": self.conn_dist,
            "max_component_offset_dist": self.comp_dist,
            "max_stitching_offset_dist": self.stitch_dist
        }
        try:
            self.manager.run_save_pipeline(data["img_name"], 
                                           data["frame"], 
                                           data["points"],
                                           data["inner_points"],
                                           [],
                                           data["polygons"],
                                           processed = True,
                                           slider_values = slider_values,
                                           matches = data["matches"],
                                           sacb = data["sacb"])
            frame, _, _ = self.manager.run_load_pipeline(data["img_name"])
            self.image.update_view(frame)
            file = File()
            file.save_jpg(frame, data["img_name"][4:-4], True)
        except Exception as e:
            self.logger.error(f"Failed save threshold data: {e}")