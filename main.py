import sys
import os
import cv2
import json
import platform
import subprocess
import picologging as logging

from PyQt6.QtCore import pyqtSlot, Qt
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout, 
                             QFrame, QVBoxLayout, QLabel, QGroupBox, QComboBox,
                             QPushButton, QSlider, QSizePolicy, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QCheckBox, QFileDialog,
                             QMessageBox)
from PyQt6.QtGui import QImage, QPixmap

from realtime.camera import Camera
from analysis.history import History
from config import main_const
from config.log_config import log_fomatter
from analysis.post_processor import MainManager

class MyApp(QMainWindow):

    def __init__(self):
        """Initializes the main window, logging system, and focus policy."""
        self.logger = logging.getLogger("main")
        self.logger.setLevel(logging.DEBUG)
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(log_fomatter.LogColorFormatter())
        self.logger.addHandler(ch)
        self.manager = MainManager()
        
        # Initialize UI and focus setting
        super().__init__()
        self.initUI()

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFocus()

    def initUI(self):
        """Configures the main layout structure and arranges all frames."""
        self.logger.info("Start init UI.")
        self.color = None
        self.img_data = None
        self.all_checked = True
        self.history = History()
        
        self.current_val = 10
        self.neighbour_margin_factor = 330
        self.boundary_margin_factor = 330
        self.max_connected_line_dist = 40
        self.max_component_offset_distance = 210
        self.max_stitching_offset_distance = 630
        self.resolution_current_index = main_const.RESOLUTION_DEFAULT_INDEX

        # Configure window properties
        self.setWindowTitle(main_const.WINDOW_TITLE)
        self.resize(main_const.WINDOW_RESIZE[0], main_const.WINDOW_RESIZE[1])

        # Create central widget and main horizontal layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # Create and add left/right main frames
        self.left_frame = QFrame()
        self.right_frame = QFrame()
        main_layout.addWidget(self.left_frame)
        main_layout.addWidget(self.right_frame)

        # Set up nested layouts for each frame
        left_layout = QVBoxLayout(self.left_frame)
        right_layout = QVBoxLayout(self.right_frame)

        # Assemble left side (Streaming monitor)
        left_layout.addWidget(self.initLeftStreamingUI())

        # Assemble right side (Result, Threshold, and History)
        self.label_result = self.initRightImageUI()
        self.label_stats = self.initRightThresholdUI()
        self.label_log = self.initRightHistoryUI()

        right_layout.addWidget(self.label_result, stretch=12)
        right_layout.addWidget(self.label_stats, stretch=1)
        right_layout.addWidget(self.label_log, stretch=7)

        # Start camera thread and display window
        self.camera.start()
        self.show()

        self.init_last_inspection()

        self.logger.info("End init UI")

    def initLeftStreamingUI(self):
        """Creates the UI group for real-time video streaming and resolution control."""
        self.logger.info("Start init realtime Streaming monitor UI.")

        left_realtime_streaming = QGroupBox(main_const.REALTIME_STREAMING_TITLE_TEXT)
        left_realtime_streaming.setStyleSheet("""
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

        # Instantiate camera thread and connect signals
        self.camera = Camera()
        self.camera.change_pixmap_signal.connect(self.update_image)

        # Create widgets (Video Label, Resolution Combo, Capture Button)
        layout = QVBoxLayout(left_realtime_streaming)
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

        self.resolution_config_text = QLabel(main_const.RESOLUTION_CONFIG_TEXT)
        self.video_resolution = QComboBox()
        self.video_resolution.addItems(main_const.RESOLUTION_ITEAMS)
        self.video_resolution.setCurrentIndex(self.resolution_current_index)

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

        layout.addWidget(self.video_label, stretch=16)
        layout.addWidget(self.resolution_config_text)
        layout.addWidget(self.video_resolution, stretch=2)
        layout.addWidget(self.capture_button, stretch=2)
        
        self.video_resolution.currentIndexChanged.connect(self.on_resolution_changed)
        self.capture_button.clicked.connect(self.capture_click_event)
        self.camera.capture_finished_signal.connect(self.capture_change_image)

        self.logger.info("End init realtime streaming monitor UI.")
        return left_realtime_streaming
    
    def initRightImageUI(self):
        """Initializes the UI area for displaying inspection result images."""
        self.logger.info("Start init test analysis result UI.")

        analysis_result = QGroupBox(main_const.ANALYSIS_RESULT_TITLE_TEXT)
        analysis_result.setStyleSheet("""
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
        
        self.result_image = QLabel(main_const.RESULT_IMAGE_TEXT)
        self.result_image.setStyleSheet("""
            QLabel {
                border-radius: 6px;
            }
        """)
        self.result_image.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout = QVBoxLayout(analysis_result)
        layout.addWidget(self.result_image)

        self.logger.info("End init test analysis result UI.")

        return analysis_result
    
    def initRightThresholdUI(self):
        """Initializes the UI for adjusting the error threshold via a slider."""
        self.logger.info("Start init threshold setting UI.")
    
        threshold = QGroupBox(main_const.THRESHOLD_TITLE_TEXT)
        threshold.setStyleSheet("""
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
        main_v_layout = QVBoxLayout(threshold)
        self.sliders = []
        self.initSlider("인접 땀수 여백", main_v_layout, threshold, 0)
        self.initSlider("외곽 경계 여백", main_v_layout, threshold, 1)
        self.initSlider("선 연결 허용치", main_v_layout, threshold, 2)
        self.initSlider("부품 이탈 허용치", main_v_layout, threshold, 3)
        self.initSlider("땀수 이탈 허용치", main_v_layout, threshold, 4)
        
        self.history.get_log()
        self.logger.info("End init threshold setting UI.")

        return threshold
    
    def initSlider(self, label, main_v_layout, threshold, idx):
        threshold_text = QLabel(label + ": ")
        threshold_text.setFixedWidth(100)
        threshold_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        err_bar = QSlider(Qt.Orientation.Horizontal)
        err_bar.setRange(0, 500)
        err_bar.setValue(main_const.THRESHOLDS[idx])
        err_bar.setMinimumWidth(threshold.width() - 100)
        err_bar.setMaximumWidth(threshold.width() + 150)
        err_bar.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        value_label = QLabel(str(main_const.THRESHOLDS[idx]) + "px")
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value_label.setFixedWidth(40)
        layout = QHBoxLayout()
        layout.addWidget(threshold_text)
        layout.addWidget(err_bar)
        layout.addWidget(value_label)
        main_v_layout.addLayout(layout)
        err_bar.valueChanged.connect(lambda val: self.update_label_text(val, idx))
        slider_dict = {
            "idx": idx,
            "label": label,
            "bar": err_bar,
            "value": main_const.THRESHOLDS[idx],
            "value_label": value_label
            }
        self.sliders.append(slider_dict)

    def initRightHistoryUI(self):
        self.logger.info("Start init history UI.")
        
        self.single_execution = True
        self.selected_files = []

        history = QGroupBox(main_const.HISTORY_TITLE_TEXT)
        history.setStyleSheet("""
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

        self.all_select_checkbox = QCheckBox(main_const.ALL_SELECT_CHECKBOX_TEXT)
        self.row_checkboxes = []

        export_log = QPushButton(main_const.EXPORT_LOG_TEXT)
        export_log.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

        checked_upload = QPushButton(main_const.CHECKED_UPLOAD_TEXT)
        checked_upload.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        checked_upload.setStyleSheet("""
                background-color:#4CAF50;
            """)

        open_folder = QPushButton(main_const.OPEN_FOLDER_TEXT)
        open_folder.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

        # Setup history table
        file_names_with_ext, formatted_list, path = self.history.get_all_jpg()
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(5)
        self.history_table.setRowCount(len(file_names_with_ext))
        self.history_table.setHorizontalHeaderLabels([
            main_const.HISTORY_TABLE_HEADER_SELECT_TEXT, 
            main_const.HISTORY_TABLE_HEADER_FILENAME_TEXT, 
            main_const.HISTORY_TABLE_HEADER_TEST_TIME_TEXT, 
            main_const.HISTORY_TABLE_HEADER_STATUS_TEXT, 
            main_const.HISTORY_TABLE_HEADER_ACTION_TEXT
            ])
        self.history_table.setMinimumWidth(history.width() - 100)
        self.history_table.setMaximumHeight(history.width() + 150)
        self.history_table.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        header = self.history_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)

        for i, f_name in enumerate(file_names_with_ext):
            checkbox = QCheckBox()
            checkbox.stateChanged.connect(self.update_selected_info)

            action = self.create_action_buttons(f_name, path)

            item1 = QTableWidgetItem(f_name)
            item2 = QTableWidgetItem(formatted_list[i])
            item3 = QTableWidgetItem(main_const.HISTORY_TABLE_DEFAULT_STATUS_VALUE_TEXT)

            item1.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item2.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item3.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            self.history_table.setCellWidget(i, 0, checkbox)
            self.history_table.setItem(i, 1, item1)
            self.history_table.setItem(i, 2, item2)
            self.history_table.setItem(i, 3, item3)
            self.history_table.setCellWidget(i, 4, action)

            self.row_checkboxes.append((checkbox, f_name))

        qv_layout = QVBoxLayout(history)
        qh_layout = QHBoxLayout()

        qh_layout.addWidget(self.all_select_checkbox)
        qh_layout.addWidget(export_log)
        qh_layout.addWidget(checked_upload)
        qh_layout.addWidget(open_folder)

        qv_layout.addLayout(qh_layout, 1)
        qv_layout.addWidget(self.history_table, 9)

        self.all_select_checkbox.stateChanged.connect(self.select_all_rows)
        self.all_select_checkbox.clicked

        export_log.clicked.connect(self.export_log_file)
        checked_upload.clicked.connect(self.upload_all)
        open_folder.clicked.connect(self.open_folder)

        self.history_table.cellClicked.connect(self.on_cell_clicked)

        self.logger.info("End init history UI.")

        return history

    @pyqtSlot(QImage)
    def update_image(self, qt_img):
        """Updates the streaming video label with a new frame, maintaining aspect ratio."""
        label_width = self.video_label.width()
        label_height = self.video_label.height()
        
        pixmap = QPixmap.fromImage(qt_img).scaled(
            label_width, label_height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.video_label.setPixmap(pixmap)

    def on_resolution_changed(self, index):
        """Handles camera resolution changes based on the user's combo box selection."""
        if index == 0:
            self.camera.width_resize = main_const.RESOLUTION_LOW[0]
            self.camera.height_resize = main_const.RESOLUTION_LOW[1]
            self.logger.info(f"Change resolution {main_const.RESOLUTION_LOW[0]}x{main_const.RESOLUTION_LOW[1]}.")
            
        elif index == 1:
            self.camera.width_resize = main_const.RESOLUTION_MEDIUM[0]
            self.camera.height_resize = main_const.RESOLUTION_MEDIUM[1]
            self.logger.info(f"Change resolution {main_const.RESOLUTION_MEDIUM[0]}x{main_const.RESOLUTION_MEDIUM[1]}.")
            
        elif index == 2:
            self.camera.width_resize = main_const.RESOLUTION_HIGH[0]
            self.camera.height_resize = main_const.RESOLUTION_HIGH[1]
            self.logger.info(f"Change resolution {main_const.RESOLUTION_HIGH[0]}x{main_const.RESOLUTION_HIGH[1]}.")

        elif index == 3:
            self.camera.width_resize = main_const.RESOLUTION_4K_HIGH[0]
            self.camera.height_resize = main_const.RESOLUTION_4K_HIGH[1]
            self.logger.info(f"Change resolution {main_const.RESOLUTION_4K_HIGH[0]}x{main_const.RESOLUTION_4K_HIGH[1]}.") 

        else:
            self.logger.error("Failed change resolution")
            
        self.resolution_current_index = index

        self.camera.need_resize = True

    def capture_click_event(self):
        """Triggers a 4K frame capture request via the camera thread."""
        self.camera.need_capture = True

    def clamp(v, lo, hi):
        return max(lo, min(hi, v))


    def keyPressEvent(self, event):
        k = event.key()
        cam = self.camera

        # ---------- Group 1: Capture / Reset ----------
        if k in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            cam.need_capture = True
            return

        if k == Qt.Key.Key_Q:
            self.logger.info("Change default")
            cam.editor_trigger = 0
            cam.init_motion_engine = True
            return

        # ---------- Group 2: Editor Selection ----------
        editor_map = {
            Qt.Key.Key_1: ("Change Roi editor", 1),
            Qt.Key.Key_2: ("Change Focus editor", 2),
            Qt.Key.Key_3: ("Change Exposure editor", 3),
        }
        if k in editor_map:
            msg, val = editor_map[k]
            self.logger.info(msg)
            cam.editor_trigger = val
            return

        # ---------- Group 3: Save ----------
        if k == Qt.Key.Key_S:
            save_map = {
                1: ("Save ROI to configuration file", cam.roi_editor.save_config),
                2: ("Save focus settings to configuration file", cam.focus_editor.save_config),
                3: ("Save exposure settings to configuration file", cam.exposure_editor.save_config),
            }
            if cam.editor_trigger in save_map:
                msg, fn = save_map[cam.editor_trigger]
                self.logger.info(msg)
                fn()
            return

        # ---------- Group 4: Auto / Manual Toggle ----------
        if k == Qt.Key.Key_M:
            if cam.editor_trigger == 2:
                fe = cam.focus_editor
                fe.focus_mode = "manual" if fe.focus_mode == "auto" else "auto"
                self.logger.info("Apply current focus settings to camera")
                fe.apply_focus_settings(cam.q_control)

            elif cam.editor_trigger == 3:
                ee = cam.exposure_editor
                ee.exposure_mode = "manual" if ee.exposure_mode == "auto" else "auto"
                self.logger.info("Apply current exposure settings to camera")
                ee.apply_exposure_settings(cam.q_control)
            return

        # ---------- Group 5: Reset ----------
        if k == Qt.Key.Key_R:
            if cam.editor_trigger == 1:
                self.logger.info("[RESET] ROI reset to defaults (center 50%)")
                cam.roi_editor.roi_normalized = dict(x1=0.25, y1=0.25, x2=0.75, y2=0.75)

            elif cam.editor_trigger == 2 and cam.focus_editor.focus_mode == "auto":
                self.logger.info("[RESET] Focus region reset to defaults (center 20%)")
                cam.focus_editor.focus_normalized = dict(x1=0.4, y1=0.4, x2=0.6, y2=0.6)
                cam.focus_editor.apply_focus_settings(cam.q_control)

            elif cam.editor_trigger == 3 and cam.exposure_editor.exposure_mode == "auto":
                self.logger.info("[RESET] Exposure compensation reset to 0")
                cam.exposure_editor.exp_compensation = 0
                cam.exposure_editor.apply_exposure_settings(cam.q_control)
            return

        # ---------- Group 6: Manual Adjustments ----------
        fe, ee = cam.focus_editor, cam.exposure_editor

        if fe.focus_mode == "manual":
            delta = {
                Qt.Key.Key_A: +1, Qt.Key.Key_D: -1,
                Qt.Key.Key_Right: +10, Qt.Key.Key_Left: -10,
            }.get(k)
            if delta is not None:
                fe.manual_focus_value = self.clamp(fe.manual_focus_value + delta, 0, 255)
                fe.apply_focus_settings(cam.q_control)
            return

        if ee.exposure_mode == "auto":
            delta = {Qt.Key.Key_A: +1, Qt.Key.Key_D: -1}.get(k)
            if delta is not None:
                ee.exp_compensation = self.clamp(ee.exp_compensation + delta, -3, 3)
                ee.apply_exposure_settings(cam.q_control)
            return

        if ee.exposure_mode == "manual":
            if k in (Qt.Key.Key_W, Qt.Key.Key_E, Qt.Key.Key_S, Qt.Key.Key_D):
                step = {Qt.Key.Key_W: 500, Qt.Key.Key_E: 100,
                        Qt.Key.Key_S: -500, Qt.Key.Key_D: -100}[k]
                ee.exposure_time = self.clamp(
                    ee.exposure_time + step, 1, cam.max_exposure
                )
                ee.apply_exposure_settings(cam.q_control)

            elif k in (Qt.Key.Key_A, Qt.Key.Key_Z):
                step = {Qt.Key.Key_A: 50, Qt.Key.Key_Z: -50}[k]
                ee.iso_value = self.clamp(ee.iso_value + step, 100, 1600)
                ee.apply_exposure_settings(cam.q_control)

    def mousePressEvent(self, event):
        """Records initial normalized mouse position on click for ROI/Focus configuration."""
        if self.camera.editor_trigger == 1 and event.button() == Qt.MouseButton.LeftButton:
            self.start_nx, self.start_ny = self.get_adjusted_coords(event)
        elif self.camera.editor_trigger == 2 and self.camera.focus_editor.focus_mode == 'auto' and event.button() == Qt.MouseButton.LeftButton:
            self.start_nx, self.start_ny = self.get_adjusted_coords(event)

    def mouseReleaseEvent(self, event):
        """Finalizes ROI or Focus area selection based on release coordinates."""
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
        """Calculates normalized coordinates (0.0 to 1.0) adjusted for video letterboxing/offsets."""
        if self.video_label.pixmap() is None:
            return 0.0, 0.0
        
        # Fetch container and displayed image dimensions
        label_w = self.video_label.width()
        label_h = self.video_label.height()
        pix_w = self.video_label.pixmap().width()
        pix_h = self.video_label.pixmap().height()

        # Calculate drawing offsets caused by KeepAspectRatio
        dx = (label_w - pix_w) / 2
        dy = (label_h - pix_h) / 2

        # Map global mouse position to label local coordinates
        label_pos = self.video_label.mapFromGlobal(event.globalPosition().toPoint())
        
        # Correct for offsets and normalize
        adj_x = (label_pos.x() - dx) / pix_w
        adj_y = (label_pos.y() - dy) / pix_h

        # Clamping between 0 and 1
        final_x = max(0.0, min(1.0, adj_x))
        final_y = max(0.0, min(1.0, adj_y))

        return final_x, final_y

    def capture_change_image(self): 
        self.logger.info("Start change image after caputre.")
        if self.camera.data_dict is not None:
            # Saving to database and loading it back
            d = self.camera.data_dict
            self.manager.run_save_pipeline(d["img_name"], d["frame"], d["points"], d["inner_points"], d["overlap_points"], d["polygons"])
            frame = self.manager.run_load_pipeline(d["img_name"])
            
            rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_image.shape
            bytes_per_line = ch * w
            self.temp_buffer = rgb_image
            self.img_data = QImage(self.temp_buffer.data, w, h, bytes_per_line, QImage.Format.Format_RGB888).copy()

            self.set_result_pixmap(self.img_data)
            self.history_update()

            self.logger.info("End change image after caputre.")
        else:
            self.logger.error("Fail change image after caputre.")

    def update_label_text(self, val, idx):
        """Updates the threshold percentage display and refreshes the visualization change."""
        self.sliders[idx]["value_label"].setText(f"{val}%")
        self.sliders[idx]["value"] = val

    # 로그 파일 내보내기
    def export_log_file(self):
        """Exports accumulated inspection logs to a formatted JSONL file."""
        self.logger.info("Start export log file.")

        log, timestamp = self.history.get_log()

        if not log:
            QMessageBox.warning(
                self,
                main_const.LOG_EXPORT_FALILED_TITLE_TEXT,
                main_const.LOG_EXPORT_FALILED_CONTENT_TEXT,
                QMessageBox.StandardButton.Ok
            )
            self.logger.warning("Not exist log information.")
            return

        # Trigger file dialog for save path
        file_path, _ = QFileDialog.getSaveFileName(
            self, main_const.LOG_EXPORT_TEXT, f"{main_const.LOG_EXPORT_FILENAME}{timestamp}.{main_const.LOG_EXPORT_EXTENTION}", "JSON Lines Files (*.jsonl)"
        )

        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    for entry in log:
                        json_record = json.dumps(entry, ensure_ascii=False)
                        f.write(json_record + '\n')
            except Exception as e:
                print(f"{main_const.LOG_EXPORT_ERROR_TEXT}{e}")
                self.logger.error(f"Can't open file: {e}.")

        self.logger.info("End export log file.")
    
    # 전체 선택 클릭
    def select_all_rows(self):
        """Bulk selects or deselects all rows in the history table."""
        if self.all_checked:
            for checkbox, _ in self.row_checkboxes:
                checkbox.setChecked(True)

            self.all_checked = False
        else:
            for checkbox, _ in self.row_checkboxes:
                checkbox.setChecked(False)
                
            self.all_checked = True

    # 체크박스 클릭
    def update_selected_info(self):
        """Synchronizes the list of filenames currently checked in the history table."""
        self.selected_files = [fname for cb, fname in self.row_checkboxes if cb.isChecked()]

    # 캡처 시 히스토리 업데이트
    def history_update(self):
        """Inserts a new entry at the top of the history table after a successful capture."""
        f_name, time, path = self.history.get_last_img()

        self.history_table.insertRow(0)

        checkbox = QCheckBox()
        checkbox.stateChanged.connect(self.update_selected_info)

        action = self.create_action_buttons(f_name, path)

        # Build table items
        item1 = QTableWidgetItem(f_name)
        item2 = QTableWidgetItem(time)
        item3 = QTableWidgetItem(main_const.HISTORY_TABLE_DEFAULT_STATUS_VALUE_TEXT)

        item1.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        item2.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        item3.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        # Insert items and widgets into row 0
        self.history_table.setCellWidget(0, 0, checkbox)
        self.history_table.setItem(0, 1, item1)
        self.history_table.setItem(0, 2, item2)
        self.history_table.setItem(0, 3, item3)
        self.history_table.setCellWidget(0, 4, action)

        self.row_checkboxes.append((checkbox, f_name))

    def open_folder(self):
        """Opens the directory containing capture files using the OS native file browser."""
        self.logger.info("Start open folder.")

        path = self.history.get_path()
        system_name = platform.system()
    
        try:
            if system_name == "Windows":
                os.startfile(path)
            elif system_name == "Darwin":
                subprocess.run(["open", path])
            else:
                subprocess.run(["xdg-open", path])
                
        except Exception as e:
            QMessageBox.critical(self, main_const.EXCEPTION_TITLE_TEXT, f"{main_const.EXCEPTION_CONTENT_TEXT}{e}")
            self.logger.error(f"Failed open folder: {e}.")

        self.logger.info("End open folder.")

    def create_action_buttons(self, f_name, path):
        """Generates a widget container with 'View', 'Delete', and 'Upload' buttons for each row."""
        container = QWidget()
        layout = QHBoxLayout(container)

        btn_look_file = QPushButton(main_const.LOOK_TEXT)
        btn_delete_file = QPushButton(main_const.DELETE_TEXT)
        btn_delete_file.setStyleSheet("color: red;")
        btn_upload_file = QPushButton(main_const.UPLOAD_TEXT)

        for btn in [btn_look_file, btn_delete_file, btn_upload_file]:
            layout.addWidget(btn)

        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(5)

        btn_look_file.clicked.connect(lambda: self.look_file(f_name, path))
        btn_delete_file.clicked.connect(lambda: self.delete_file(f_name, path))
        btn_upload_file.clicked.connect(lambda: self.upload_file(f_name))

        return container
    
    def look_file(self, f_name, path):
        """Opens the individual capture file with the system default viewer."""
        self.logger.info("Start open file.")

        try:
            full_path = os.path.abspath(os.path.join(path, f_name))
            if platform.system() == "Windows":
                os.startfile(full_path)
            elif platform.system() == "Darwin":
                subprocess.run(["open", full_path])
            else:
                subprocess.run(["xdg-open", full_path])
        except:
            self.logger.info("Failed open file.")

        self.logger.info("End open file.")

    def delete_file(self, f_name, path):
        """Prompts for confirmation and deletes JPG from disk."""
        self.logger.info("Start delete files.")
        reply = QMessageBox.question(
            self, main_const.DELETE_REPLY_TITLE_TEXT, 
            f"{f_name}{main_const.DELETE_REPLY_CONTENT_TEXT}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                jpg_path = os.path.join(path, f_name)
                os.remove(jpg_path)
            except Exception as e:
                QMessageBox.critical(self, main_const.DELETE_FAILED_TITLE_TEXT, f"{main_const.DELETE_FAILED_CONTENT_TEXT}{e}")
                self.logger.error("Failed delete files.")
                return
            
            target_row = -1
            for i in range(self.history_table.rowCount()):
                if self.history_table.item(i, 1).text() == f_name:
                    target_row = i
                    break

            if target_row != -1:
                self.history_table.removeRow(target_row)

                self.row_checkboxes = [(cb, name) for cb, name in self.row_checkboxes if name != f_name]
                self.update_selected_info()

        self.logger.info("End delete files.")

    def upload_file(self, f_name):
        """Simulates file upload and updates status to 'Done' in the UI."""
        target_row = -1
        for i in range(self.history_table.rowCount()):
            if self.history_table.item(i, 1).text() == f_name:
                target_row = i
                break
        
        if target_row == -1: return

        for cb, name in self.row_checkboxes:
            if name == f_name:
                cb.setChecked(True)
                cb.setEnabled(False)
                break

        status_item = self.history_table.item(target_row, 3)
        status_item.setText(main_const.CHANGE_STATUS_TEXT)
        status_item.setForeground(Qt.GlobalColor.green)

        action_widget = self.history_table.cellWidget(target_row, 4)
        if action_widget:
            for btn in action_widget.findChildren(QPushButton):
                if btn.text() == main_const.BUTTON_TEXT:
                    btn.setParent(None)
                    break
        
        self.row_checkboxes = [(cb, name) for cb, name in self.row_checkboxes if name != f_name]
        self.update_selected_info()

        if self.single_execution:
            QMessageBox.information(self, main_const.SUCCESS_TITLE_TEXT, f"{main_const.SUCCESS_CONTENT_TEXT}\n{f_name}")

    # 일괄 업로드
    def upload_all(self):
        if self.selected_files:
            self.single_execution = False
            success_count = 0

            for f_name in self.selected_files[:]:
                self.upload_file(f_name)
                success_count += 1
                
            self.row_checkboxes = [(cb, name) for cb, name in self.row_checkboxes if name != f_name]
            self.update_selected_info()

            self.all_select_checkbox.setChecked(False)

            QMessageBox.information(
                self, main_const.BATCH_UPLOAD_SUCCESS_TITLE_TEXT, 
                f"{success_count}{main_const.BATCH_UPLOAD_SUCCESS_CONTENT_TEXT}"
            )
            self.single_execution = True
        else:
            QMessageBox.warning(
                self, 
                main_const.NO_CHECK_EXCEPTION_TITLE_TEXT,
                main_const.NO_CHECK_EXCEPTION_CONTENT_TEXT,
                QMessageBox.StandardButton.Ok
            )

    # 셀 클릭 시 검사결과 이미지 업로드
    def on_cell_clicked(self, row, column):
        self.logger.info("Start image, bbox update.")

        clicked_item = self.history_table.item(row, column)
        if clicked_item:
            filename = clicked_item.text()
            if "-" in filename:
                date_part = filename[0:4] + filename[5:7] + filename[8:10]
                time_part = filename[11:13] + filename[14:16] + filename[17:19]
                ms_part = filename[20:23]

                filename = f"IMG_{date_part}_{time_part}_{ms_part}.jpg" 
            try:
                frame, slider_values = self.manager.run_load_pipeline(filename)
            except FileNotFoundError as e:
                self.logger.error("Failed image load - image not found in DB")
                return
            rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            h, w, ch = rgb_image.shape
            bytes_per_line = ch * w

            self.temp_buffer = rgb_image
            self.img_data = QImage(self.temp_buffer.data, w, h, bytes_per_line, QImage.Format.Format_RGB888).copy()

            self.update_sliders(slider_values)

            self.set_result_pixmap(self.img_data)

            self.logger.info("End image update.")
        else:
            self.logger.error("Failed image update.")

    def set_result_pixmap(self, q_img):
        if q_img.isNull():
            return
        
        pixmap = QPixmap.fromImage(q_img)

        label_size = self.result_image.size()

        scaled_pixmap = pixmap.scaled(
            label_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        self.result_image.setScaledContents(False) 
        self.result_image.setPixmap(scaled_pixmap)

    def update_sliders(self, slider_values):
        for i in range(5):
            self.sliders[i]["value_label"].setText(str(list(slider_values.values())[i]) + "px")
            self.sliders[i]["value"] = list(slider_values.values())[i]
            label=self.sliders[i]["label"]
            vallabel=self.sliders[i]["value_label"].text()
            self.logger.info(f"Updated slider {label} to {vallabel}")

    def init_last_inspection(self):
        """Initializes the visualization interface by retrieving the most recent inspection record from the local repository."""
        try:
            # Fetch latest inspection record
            jpg_file, _, _= self.history.get_last_img()
            
            if jpg_file:
                # Sync data to camera buffer
                frame, slider_values = self.manager.run_load_pipeline(jpg_file)
                rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                h, w, ch = rgb_image.shape
                bytes_per_line = ch * w

                self.temp_buffer = rgb_image
                self.img_data = QImage(self.temp_buffer.data, w, h, bytes_per_line, QImage.Format.Format_RGB888).copy()

                self.set_result_pixmap(self.img_data)

                self.update_sliders(slider_values)

                self.logger.info("Successfully synchronized view with the latest inspection record.")
            else:
                self.logger.warning("No prior inspection records identified; maintaining default state.")
        except Exception as e:
            self.logger.error(f"Critical failure during initial data synchronization: {e}")

def main():
    app = QApplication(sys.argv)
    window = MyApp()

    app.exec()

if __name__ == '__main__':
    main()
    