"""
Class for real-time video streaming display and camera control interface.
Handles video frames, resolution settings, and manual capture triggers.
"""

from PyQt6.QtCore import pyqtSlot, Qt
from PyQt6.QtWidgets import QVBoxLayout, QLabel, QGroupBox, QComboBox,QPushButton
from PyQt6.QtGui import QImage, QPixmap, QShortcut, QKeySequence

from config import main_const
from realtime.inspection import Inspection

class StreamingUi(QGroupBox):
    def __init__(self, camera, history, image, logger, res_idx, manager, threshold, parent=None):
        super().__init__(main_const.REALTIME_STREAMING_TITLE_TEXT, parent)
        
        # Initialize core components and dependencies
        self.camera = camera
        self.history = history
        self.image = image
        self.logger = logger
        self.res_idx = res_idx
        self.manager = manager
        self.threshold = threshold

        # Initialize UI Components and Event Connections
        self._init_styling()
        self._setup_ui()
        self._connect_signals()

        # Set focus policy to handle keyboard events at the widget level
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        
    def _init_styling(self):
        """Sets the visual style for the GroupBox container."""

        self.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #BCBCBC;
                border-radius: 6px;
                margin-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px 0 3px;
            }
        """)
    
    def _setup_ui(self):
        """Creates and arranges UI widgets within the layout."""
        layout = QVBoxLayout(self)

        # Video stream display label
        self.video_label = QLabel(main_const.VIDEO_STREAMING_TEXT)
        self.video_label.setStyleSheet("""
            QLabel {
                background-color: black;
                color: white; 
                border-radius: 6px;
            }
        """)
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setScaledContents(False)

        # Resolution configuration components
        resolution_config_text = QLabel(main_const.RESOLUTION_CONFIG_TEXT)
        self.video_resolution = QComboBox()
        self.video_resolution.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.video_resolution.addItems(main_const.RESOLUTION_ITEAMS)
        self.video_resolution.setCurrentIndex(self.res_idx)

        # Capture excution button
        self.capture_button = QPushButton(main_const.CAPTURE_BUTTON_TEXT)
        self.capture_button.setMinimumHeight(main_const.CAPTURE_BUTTON_MINIMUM_HEIGHT)
        self.capture_button.setStyleSheet("""
            QPushButton {
                font-size: 20px;
                font-weight: bold;
                text-align: center;
                background-color: #2D89EF;
                color: white;
                border-radius: 6px;
            }
        """)

        # Add widgets to the vertical layout with defined stretch factors
        layout.addWidget(self.video_label, stretch=16)
        layout.addWidget(resolution_config_text)
        layout.addWidget(self.video_resolution, stretch=2)
        layout.addWidget(self.capture_button, stretch=2)

    def _connect_signals(self):
        """Connects UI signals to their respective handler methods and defines global shortcuts."""

        self.video_resolution.currentIndexChanged.connect(self.on_resolution_changed)
        self.capture_button.clicked.connect(self.capture_click_event)
        self.camera.capture_finished_signal.connect(self.capture_change_image)
        self.camera.change_pixmap_signal.connect(self.update_image)

        # Global shortcuts for capture execution (Bypasses focus issues)
        QShortcut(QKeySequence(Qt.Key.Key_Return), self, self.capture_click_event)
        QShortcut(QKeySequence(Qt.Key.Key_Enter), self, self.capture_click_event)
        QShortcut(QKeySequence(Qt.Key.Key_Space), self, self.capture_click_event)

    @pyqtSlot(QImage)
    def update_image(self, qt_img):
        """Scales and updates the streaming video label with the incoming frame."""

        label_w, label_h = self.video_label.width(), self.video_label.height()
        if not qt_img.isNull():
            # Maintain aspect ratio and apply smooth transformation for 4K downscaling
            pixmap = QPixmap.fromImage(qt_img).scaled(
                label_w, label_h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.video_label.setPixmap(pixmap)

    def on_resolution_changed(self, index):
        """Handles camera resolution updates based on the mapping index."""

        res_map = {
            0: main_const.RESOLUTION_LOW,
            1: main_const.RESOLUTION_MEDIUM,
            2: main_const.RESOLUTION_HIGH,
            3: main_const.RESOLUTION_4K_HIGH
        }
        
        res = res_map.get(index)
        if res:
            self.camera.width_resize, self.camera.height_resize = res
            self.camera.need_resize = True
            self.logger.info(f"Resolution changed to {res[0]}x{res[1]}")

    def capture_click_event(self):
        """Triggers a high-resolution capture request to the camera thread."""

        self.camera.need_capture = True
        self.logger.info("Capture request sent to camera thread.")

    def capture_change_image(self):
        """Updates the analysis view and inspection history after a successful capture."""
        # get raw ai-predicted point/polygon data
        d = Inspection().temporary(self.camera.img_frame)
        
        # unpack and save to database
        self.manager.run_save_pipeline(d["img_name"], d["frame"], d["points"], d["inner_points"], d["overlap_points"], d["polygons"])

        # load back processed data from database
        frame, slider_values, data_dict = self.manager.run_load_pipeline(d["img_name"])

        # update image view and store currently loaded data
        self.image.update_view(frame)
        self.image.current_image_data = data_dict

        # update threshold sliders 
        self.threshold._update_value(slider_values["neighbour_margin_factor"], 1)
        self.threshold._update_value(slider_values["boundary_margin_factor"], 2)
        self.threshold._update_value(slider_values["max_connected_line_dist"], 3)
        self.threshold._update_value(slider_values["max_component_offset_dist"], 4)
        self.threshold._update_value(slider_values["max_stitching_offset_dist"], 5)
        self.history.history_update()

    def keyPressEvent(self, event):
        """Handles legacy keyboard events for editor modes and configuration management."""

        key_code = event.key()
        
        # Group 1: General (Capture and Reset)
        if key_code == Qt.Key.Key_Space or key_code in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.camera.need_capture = True
        elif key_code == Qt.Key.Key_Q:
            self.logger.info("Change default")
            self.camera.editor_trigger = 0
            self.camera.init_motion_engine = True
        
        # Group 2: Editor Mode Selection
        elif key_code == Qt.Key.Key_1:
            self.logger.info("Change Roi editor")
            self.camera.editor_trigger = 1
        elif key_code == Qt.Key.Key_2:
            self.logger.info("Change Focus editor")
            self.camera.editor_trigger = 2
        elif key_code == Qt.Key.Key_3:
            self.logger.info("Change Exposure editor")
            self.camera.editor_trigger = 3
        
        # Group 3: Save Configurations
        elif key_code == Qt.Key.Key_S:
            if self.camera.editor_trigger == 1:
                self.logger.info("Save ROI to configuration file")
                self.camera.roi_editor.save_config()
            elif self.camera.editor_trigger == 2:
                self.logger.info("Save focus settings to configuration file")
                self.camera.focus_editor.save_config()
            elif self.camera.editor_trigger == 3:
                self.logger.info("Save exposure settings to configuration file")
                self.camera.exposure_editor.save_config()
        
        # Group 4: Mode Toggles (Auto/Manual)
        elif key_code == Qt.Key.Key_M:
            if self.camera.editor_trigger == 2:
                self.camera.focus_editor.focus_mode = 'manual' if self.camera.focus_editor.focus_mode == 'auto' else 'auto'
                self.logger.info("Apply current focus settings to camera")
                self.camera.focus_editor.apply_focus_settings(self.camera.q_control)
            elif self.camera.editor_trigger == 3:
                self.camera.exposure_editor.exposure_mode = 'manual' if self.camera.exposure_editor.exposure_mode == 'auto' else 'auto'
                self.logger.info("Apply current exposure settings to camera")
                self.camera.exposure_editor.apply_exposure_settings(self.camera.q_control)

        elif self.camera.exposure_editor.exposure_mode == 'manual' and self.camera.editor_trigger == 3:
            if key_code == Qt.Key.Key_E:
                self.camera.exposure_editor.exposure_time = min(self.camera.max_exposure, self.camera.exposure_editor.exposure_time + 500)
                self.camera.exposure_editor.apply_exposure_settings(self.camera.q_control)
            elif key_code == Qt.Key.Key_R:
                self.camera.exposure_editor.exposure_time = max(1, self.camera.exposure_editor.exposure_time - 500)
                self.camera.exposure_editor.apply_exposure_settings(self.camera.q_control)
            elif key_code == Qt.Key.Key_D:
                self.camera.exposure_editor.exposure_time = min(self.camera.max_exposure, self.camera.exposure_editor.exposure_time + 100)
                self.camera.exposure_editor.apply_exposure_settings(self.camera.q_control)
            elif key_code == Qt.Key.Key_F:
                self.camera.exposure_editor.exposure_time = max(1, self.camera.exposure_editor.exposure_time - 100)
                self.camera.exposure_editor.apply_exposure_settings(self.camera.q_control)
            elif key_code == Qt.Key.Key_C:
                self.camera.exposure_editor.iso_value = min(1600, self.camera.exposure_editor.iso_value + 50)
                self.camera.exposure_editor.apply_exposure_settings(self.camera.q_control)
            elif key_code == Qt.Key.Key_V:
                self.camera.exposure_editor.iso_value = max(100, self.camera.exposure_editor.iso_value - 50)
                self.camera.exposure_editor.apply_exposure_settings(self.camera.q_control)
        
        # Group 5: Reset Actions
        elif key_code == Qt.Key.Key_R:
            if self.camera.editor_trigger == 1:
                self.logger.info("[RESET] ROI reset to defaults (center 50%)")
                self.camera.roi_editor.roi_normalized = {'x1': 0.25, 'y1': 0.25, 'x2': 0.75, 'y2': 0.75}
            elif self.camera.editor_trigger == 2 and self.camera.focus_editor.focus_mode == 'auto':
                self.logger.info("[RESET] Focus region reset to defaults (center 20%)")
                self.camera.focus_editor.focus_normalized = {'x1': 0.4, 'y1': 0.4, 'x2': 0.6, 'y2': 0.6}
                self.camera.focus_editor.apply_focus_settings(self.camera.q_control)
            elif self.camera.editor_trigger == 3 and self.camera.exposure_editor.exposure_mode == 'auto':
                self.logger.info("[RESET] Exposure compensation reset to 0")
                self.camera.exposure_editor.exp_compensation = 0
                self.camera.exposure_editor.apply_exposure_settings(self.camera.q_control)
        
        # Group 6: Incremental Manual Adjustments
        elif self.camera.focus_editor.focus_mode == 'manual' and self.camera.editor_trigger == 2:
            if key_code == Qt.Key.Key_A:
                self.camera.focus_editor.manual_focus_value = min(255, self.camera.focus_editor.manual_focus_value + 1)
                self.camera.focus_editor.apply_focus_settings(self.camera.q_control)
            elif key_code == Qt.Key.Key_D:
                self.camera.focus_editor.manual_focus_value = max(0, self.camera.focus_editor.manual_focus_value - 1)
                self.camera.focus_editor.apply_focus_settings(self.camera.q_control)
            elif key_code == Qt.Key.Key_Right:
                self.camera.focus_editor.manual_focus_value = min(255, self.camera.focus_editor.manual_focus_value + 10)
                self.camera.focus_editor.apply_focus_settings(self.camera.q_control)
            elif key_code == Qt.Key.Key_Left:
                self.camera.focus_editor.manual_focus_value = max(0, self.camera.focus_editor.manual_focus_value - 10)
                self.camera.focus_editor.apply_focus_settings(self.camera.q_control)

        elif self.camera.exposure_editor.exposure_mode == 'auto' and self.camera.editor_trigger == 3:
            if key_code == Qt.Key.Key_A:
                self.camera.exposure_editor.exp_compensation = min(3, self.camera.exposure_editor.exp_compensation + 1)
                self.camera.exposure_editor.apply_exposure_settings(self.camera.q_control)
            elif key_code == Qt.Key.Key_D:
                self.camera.exposure_editor.exp_compensation = max(-3, self.camera.exposure_editor.exp_compensation - 1)
                self.camera.exposure_editor.apply_exposure_settings(self.camera.q_control)

    def mousePressEvent(self, event):
        """Stores starting normalized coordinates for ROI or focus selection."""

        if self.camera.editor_trigger == 1 and event.button() == Qt.MouseButton.LeftButton:
            self.start_nx, self.start_ny = self.get_adjusted_coords(event)
        elif self.camera.editor_trigger == 2 and self.camera.focus_editor.focus_mode == 'auto' and event.button() == Qt.MouseButton.LeftButton:
            self.start_nx, self.start_ny = self.get_adjusted_coords(event)

    def mouseReleaseEvent(self, event):
        """Calculates the final bounding box area for ROI or focus on mouse release."""

        # Handle ROI Editor Mode
        if self.camera.editor_trigger == 1:
            end_nx, end_ny = self.get_adjusted_coords(event)
            roi = self.camera.roi_editor
            roi.roi_normalized['x1'] = min(self.start_nx, end_nx)
            roi.roi_normalized['y1'] = min(self.start_ny, end_ny)
            roi.roi_normalized['x2'] = max(self.start_nx, end_nx)
            roi.roi_normalized['y2'] = max(self.start_ny, end_ny)

        elif self.camera.editor_trigger == 2 and self.camera.focus_editor.focus_mode == 'auto':
            end_nx, end_ny = self.get_adjusted_coords(event)
            focus = self.camera.focus_editor
            focus.focus_normalized['x1'] = min(self.start_nx, end_nx)
            focus.focus_normalized['y1'] = min(self.start_ny, end_ny)
            focus.focus_normalized['x2'] = max(self.start_nx, end_nx)
            focus.focus_normalized['y2'] = max(self.start_ny, end_ny)
            
    def get_adjusted_coords(self, event):
        """Normalizes mouse coordinates (0.0 - 1.0) while accounting for video letterboxing."""

        if self.video_label.pixmap() is None:
            return 0.0, 0.0
        
        label_w = self.video_label.width()
        label_h = self.video_label.height()
        pix_w = self.video_label.pixmap().width()
        pix_h = self.video_label.pixmap().height()

        # Calculate offsets caused by AspectRatioMode.KeepAspectRatio
        dx = (label_w - pix_w) / 2
        dy = (label_h - pix_h) / 2

        label_pos = self.video_label.mapFromGlobal(event.globalPosition().toPoint())
        
        # Clamp normalized coordinates to [0.0, 1.0]
        adj_x = (label_pos.x() - dx) / pix_w
        adj_y = (label_pos.y() - dy) / pix_h

        final_x = max(0.0, min(1.0, adj_x))
        final_y = max(0.0, min(1.0, adj_y))

        return final_x, final_y
        