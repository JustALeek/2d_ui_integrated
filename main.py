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
from analysis.filter import MainManager

# 메인 윈도우
class MyApp(QMainWindow):

    def __init__(self):
        self.logger = logging.getLogger("main")
        self.logger.setLevel(logging.DEBUG)

        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(log_fomatter.LogColorFormatter())
        self.logger.addHandler(ch)
        
        super().__init__()
        self.initUI()

    def initUI(self):
        self.logger.info("Start init UI.")
        self.color = None
        
        self.img_data = None

        self.all_checked = True
        
        self.resolution_current_index = main_const.RESOLUTION_DEFAULT_INDEX

        self.setWindowTitle(main_const.WINDOW_TITLE)
        self.resize(main_const.WINDOW_RESIZE[0], main_const.WINDOW_RESIZE[1])

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        self.left_frame = QFrame()
        self.right_frame = QFrame()

        main_layout.addWidget(self.left_frame)
        main_layout.addWidget(self.right_frame)

        left_layout = QVBoxLayout(self.left_frame)
        right_layout = QVBoxLayout(self.right_frame)

        left_layout.addWidget(self.initLeftStreamingUI())

        self.label_result = self.initRightImageUI()
        self.label_stats = self.initRightThresholdUI()
        self.label_log = self.initRightHistoryUI()

        right_layout.addWidget(self.label_result, stretch=12)
        right_layout.addWidget(self.label_stats, stretch=1)
        right_layout.addWidget(self.label_log, stretch=7)

        self.camera.start()
        
        self.show()
        self.logger.info("End init UI")

    # 좌측 UI
    def initLeftStreamingUI(self):
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

        self.camera = Camera()
        
        self.camera.change_pixmap_signal.connect(self.update_image)

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
    
    # 우측 UI
    def initRightImageUI(self):
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

        threshold_text = QLabel(main_const.THRESHOLD_TEXT)
        threshold_text.setFixedWidth(40)

        self.current_val = 10
        self.bar = QSlider(Qt.Orientation.Horizontal)
        self.bar.setRange(0, 100)
        self.bar.setValue(self.current_val)
        self.bar.setMinimumWidth(threshold.width() - 100)
        self.bar.setMaximumWidth(threshold.width() + 150)
        self.bar.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self.value_label = QLabel(main_const.THRESHOLD_DEFAULT_VALUE)
        self.value_label.setFixedWidth(40)

        layout = QHBoxLayout(threshold)
        
        layout.addWidget(threshold_text)
        layout.addWidget(self.bar)
        layout.addWidget(self.value_label)

        self.bar.valueChanged.connect(self.update_label_text)
        self.history = History()

        self.history.get_log()

        self.logger.info("End init threshold setting UI.")

        return threshold
    
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
        label_width = self.video_label.width()
        label_height = self.video_label.height()
        
        pixmap = QPixmap.fromImage(qt_img).scaled(
            label_width, label_height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.video_label.setPixmap(pixmap)

    # 해상도 변환
    def on_resolution_changed(self, index):
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

    # 마우스 캡처 클릭
    def capture_click_event(self):
        self.camera.need_capture = True

    # 키보드 캡처 Space/Enter
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Space or event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.camera.need_capture = True

    # 캡처 시 이미지 변경
    def capture_change_image(self): 
        self.logger.info("Start change image after caputre.")
        print("AHGEOAIEGOIAEHGOIHAOIEGHOIAHEOIGHAOEHGOHAEIGHOAEHGOAHEOIGOAIEHGOHAEOIGHOIAEGOI")
        if self.camera.img_name is not None:
            manager = MainManager()
            frame = manager.run_load_pipeline(self.camera.img_name)

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

    # 임계값 텍스트 업데이트
    def update_label_text(self):
        self.current_val = self.bar.value()

        self.value_label.setText(f"{self.current_val}%")

        self.update_bbox_color()

    # bbox 업데이트
    def update_bbox_color(self):
        self.logger.info("Start bbox update.")
        
        if self.img_data is not None:
            threshold = self.current_val / 100
            error_val = self.camera.json_data[0]['error_val']

            if error_val > threshold:
                self.color = (0, 0, 255)
            else:
                self.color = (0, 255, 0)

            frame = self.camera.img_frame.copy()

            bbox_h, bbox_w = frame.shape[:2]
    
            base_thickness = max(2, int(bbox_w / 300)) 
            base_font_scale = bbox_w / 1200

            x1, y1, x2, y2 = self.camera.json_data[0]['bbox']

            cv2.rectangle(frame, (x1, y1), (x2, y2), self.color, base_thickness)

            label = f"Err: {error_val:.2f}"
            text_y = y1 - base_thickness if y1 - base_thickness > 40 else y1 + 40
            cv2.putText(frame, label, (x1, text_y), cv2.FONT_HERSHEY_SIMPLEX, base_font_scale, self.color, base_thickness)

            rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            h, w, ch = rgb_image.shape
            bytes_per_line = ch * w

            self.temp_buffer = rgb_image
            self.img_data = QImage(self.temp_buffer.data, w, h, bytes_per_line, QImage.Format.Format_RGB888).copy()

            self.set_result_pixmap(self.img_data)

            self.logger.info("End bbox update.")

    # 로그 파일 내보내기
    def export_log_file(self):
        self.logger.info("Start export log file.")

        log, timestamp = self.history.get_log()

        if not log:
            QMessageBox.warning(
                self,
                main_const.LOG_EXPORT_FALILED_TITLE_TEXT,
                main_const.LOG_EXPORT_FALILED_CONTENT_TEXT,
                QMessageBox.StandardButton.Ok
            )
            self.logger.warning("Not exist log imformation.")
            return

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
        self.selected_files = [fname for cb, fname in self.row_checkboxes if cb.isChecked()]

    # 캡처 시 히스토리 업데이트
    def history_update(self):
        f_name, time, path = self.history.get_last_img()

        self.history_table.insertRow(0)

        checkbox = QCheckBox()
        checkbox.stateChanged.connect(self.update_selected_info)

        action = self.create_action_buttons(f_name, path)

        item1 = QTableWidgetItem(f_name)
        item2 = QTableWidgetItem(time)
        item3 = QTableWidgetItem(main_const.HISTORY_TABLE_DEFAULT_STATUS_VALUE_TEXT)

        item1.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        item2.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        item3.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        self.history_table.setCellWidget(0, 0, checkbox)
        self.history_table.setItem(0, 1, item1)
        self.history_table.setItem(0, 2, item2)
        self.history_table.setItem(0, 3, item3)
        self.history_table.setCellWidget(0, 4, action)

        self.row_checkboxes.append((checkbox, f_name))

    # 폴더 열기
    def open_folder(self):
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

    # action 내 버튼 생성
    def create_action_buttons(self, f_name, path):
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
    
    # 보기 버튼 클릭
    def look_file(self, f_name, path):
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

    # 삭제 버튼 클릭
    def delete_file(self, f_name, path):
        self.logger.info("Start delete files.")
        reply = QMessageBox.question(
            self, main_const.DELETE_REPLY_TITLE_TEXT, 
            f"{f_name}{main_const.DELETE_REPLY_CONTENT_TEXT}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                jpg_path = os.path.join(path, f_name)
                json_path = os.path.join(path, f_name.replace(".jpg", ".json"))

                os.remove(jpg_path)
                os.remove(json_path)
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

    # 업로드 버튼 클릭
    def upload_file(self, f_name):
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
            self.camera.img_frame, self.camera.json_data = self.history.get_jpg_json_by_filename(clicked_item.text())

            frame = self.camera.img_frame

            h, w = frame.shape[:2]
    
            base_thickness = max(2, int(w / 300)) 
            base_font_scale = w / 1200

            x1, y1, x2, y2 = self.camera.json_data[0]['bbox']
            error_val = self.camera.json_data[0]['error_val']

            current_thresh = self.current_val / 100.0

            self.color = (0, 255, 0) if error_val < current_thresh else (0, 0, 255)
            cv2.rectangle(frame, (x1, y1), (x2, y2), self.color, base_thickness)

            label = f"Err: {error_val:.2f}"
            text_y = y1 - base_thickness if y1 - base_thickness > 40 else y1 + 40

            cv2.putText(frame, label, (x1, text_y), cv2.FONT_HERSHEY_SIMPLEX, base_font_scale, self.color, base_thickness)

            rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            h, w, ch = rgb_image.shape
            bytes_per_line = ch * w

            self.temp_buffer = rgb_image
            self.img_data = QImage(self.temp_buffer.data, w, h, bytes_per_line, QImage.Format.Format_RGB888).copy()

            self.set_result_pixmap(self.img_data)

            self.logger.info("End image, bbox update.")
        else:
            self.logger.error("Failed image, bbox update.")

    # 이미지 크기에 맞게 조절
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


def main():
    app = QApplication(sys.argv)
    window = MyApp()

    app.exec()

if __name__ == '__main__':
    main()
    