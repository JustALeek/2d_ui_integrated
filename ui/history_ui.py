"""
Management module for inspection history and captured 4K data records.
Handles data synchronization, table updates, and local file operations within the UI.
"""

import os
import cv2
import json
import platform
import subprocess

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QGroupBox, 
                             QPushButton, QSizePolicy, QTableWidget, QTableWidgetItem, 
                             QHeaderView, QCheckBox, QFileDialog,QMessageBox)
from PyQt6.QtGui import QImage, QPixmap

from config import main_const

class HistoryUi(QGroupBox):
    def __init__(self, camera, history, image, logger, manager, threshold, parent=None):
        super().__init__(main_const.HISTORY_TITLE_TEXT, parent)
        self.camera = camera
        self.history = history
        self.result_image = image.result_image
        self.logger = logger
        self.current_val = 10
        self.manager = manager
        self.threshold = threshold
        self.image = image
        
        self.all_checked = True
        self.single_execution = True
        self.selected_files = []
        self.row_checkboxes = []

        self._init_styling()
        self._setup_ui()

    def _init_styling(self):
        """Sets the visual CSS style for the history GroupBox container."""

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
        """Configures the table layout, headers, and bulk action control buttons."""

        self.all_select_checkbox = QCheckBox(main_const.ALL_SELECT_CHECKBOX_TEXT)
        self.row_checkboxes = []

        # Action buttons for log export, upload, and folder access
        export_log = QPushButton(main_const.EXPORT_LOG_TEXT)
        export_log.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

        checked_upload = QPushButton(main_const.CHECKED_UPLOAD_TEXT)
        checked_upload.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        checked_upload.setStyleSheet("""
                background-color:#4CAF50;
            """)

        open_folder = QPushButton(main_const.OPEN_FOLDER_TEXT)
        open_folder.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

        # Setup history table and fetch existing records
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
        self.history_table.setMinimumWidth(self.width() - 100)
        self.history_table.setMaximumHeight(self.width() + 150)
        self.history_table.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        # Configure table header resizing behavior
        header = self.history_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)

        # Populate rows with initial data from disk
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

        # Layout assembly for control bar and table
        qv_layout = QVBoxLayout(self)
        qh_layout = QHBoxLayout()
        qh_layout.addWidget(self.all_select_checkbox)
        qh_layout.addWidget(export_log)
        qh_layout.addWidget(checked_upload)
        qh_layout.addWidget(open_folder)
        qv_layout.addLayout(qh_layout, 1)
        qv_layout.addWidget(self.history_table, 9)

        # Connect event handlers
        self.all_select_checkbox.stateChanged.connect(self.select_all_rows)
        self.all_select_checkbox.clicked
        export_log.clicked.connect(self.export_log_file)
        checked_upload.clicked.connect(self.upload_all)
        open_folder.clicked.connect(self.open_folder)
        self.history_table.cellClicked.connect(self.on_cell_clicked)

        self.logger.info("End init history UI.")


    def create_action_buttons(self, f_name, path):
        """Generates a widget container with contextual buttons for each history entry."""

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

        # Connect actions with specific file context
        btn_look_file.clicked.connect(lambda: self.look_file(f_name, path))
        btn_delete_file.clicked.connect(lambda: self.delete_file(f_name, path))
        btn_upload_file.clicked.connect(lambda: self.upload_file(f_name))

        return container
    
    def update_selected_info(self):
        """Synchronizes the internal list of checked files from the history table."""

        self.selected_files = [fname for cb, fname in self.row_checkboxes if cb.isChecked()]

    def look_file(self, f_name, path):
        """Opens a selected capture file using the native system default viewer."""

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
        """Deletes the image and metadata from disk after user confirmation."""

        self.logger.info("Start delete files.")
        reply = QMessageBox.question(
            self, main_const.DELETE_REPLY_TITLE_TEXT, 
            f"{f_name}{main_const.DELETE_REPLY_CONTENT_TEXT}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                # Remove JPEG 
                jpg_path = os.path.join(path, f_name)

                os.remove(jpg_path)
            except Exception as e:
                QMessageBox.critical(self, main_const.DELETE_FAILED_TITLE_TEXT, f"{main_const.DELETE_FAILED_CONTENT_TEXT}{e}")
                self.logger.error("Failed delete files.")
                return
            
            # Update UI table and internal row tracking
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
        """Updates the inspection status and UI state to simulate a successful data upload."""

        target_row = -1
        for i in range(self.history_table.rowCount()):
            if self.history_table.item(i, 1).text() == f_name:
                target_row = i
                break
        
        if target_row == -1: return

        # Mark as checked and disable further selection for uploaded items
        for cb, name in self.row_checkboxes:
            if name == f_name:
                cb.setChecked(True)
                cb.setEnabled(False)
                break
        
        # Update the status column with visual cues
        status_item = self.history_table.item(target_row, 3)
        status_item.setText(main_const.CHANGE_STATUS_TEXT)
        status_item.setForeground(Qt.GlobalColor.green)

        # Cleanup internal trackers
        action_widget = self.history_table.cellWidget(target_row, 4)
        if action_widget:
            for btn in action_widget.findChildren(QPushButton):
                if btn.text() == main_const.BUTTON_TEXT:
                    btn.setParent(None)
                    break
        
        self.row_checkboxes = [(cb, name) for cb, name in self.row_checkboxes if name != f_name]
        self.update_selected_info()

        # Notify user if it's a single upload execution
        if self.single_execution:
            QMessageBox.information(self, main_const.SUCCESS_TITLE_TEXT, f"{main_const.SUCCESS_CONTENT_TEXT}\n{f_name}")

    def upload_all(self):
        """Sequentially processes uploads for all currently selected history records."""

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

    def export_log_file(self):
        """Exports the accumulated inspection log entries into a formatted JSONL file."""

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

        # Trigger native save file dialog
        file_path, _ = QFileDialog.getSaveFileName(
            self, main_const.LOG_EXPORT_TEXT, f"{main_const.LOG_EXPORT_FILENAME}{timestamp}.{main_const.LOG_EXPORT_EXTENTION}", "JSON Lines Files (*.jsonl)"
        )

        # Write each log entry as a new line in the JSONL file
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
    
    def select_all_rows(self):
        """Controls the bulk selection or deselection of all rows in the history table."""

        if self.all_checked:
            for checkbox, _ in self.row_checkboxes:
                checkbox.setChecked(True)

            self.all_checked = False
        else:
            for checkbox, _ in self.row_checkboxes:
                checkbox.setChecked(False)
                
            self.all_checked = True

    def open_folder(self):
        """Triggers the OS native file browser to open the local storage directory."""

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

    def on_cell_clicked(self, row, column):
        """Loads and displays the selected historical image upon a table cell interaction."""

        if column not in [1, 2]:
            return
        
        self.logger.info("Start image update.")

        clicked_item = self.history_table.item(row, column)     # Target filename column
        if clicked_item:
            # Sync camera buffers with historical data
            frame, slider_values, data_dict = self.manager.run_load_pipeline(clicked_item.text())

            # Store related data in the imageUI object 
            self.image.current_image_data = data_dict
            rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            h, w, ch = rgb_image.shape
            bytes_per_line = ch * w

            temp_buffer = rgb_image
            img_data = QImage(temp_buffer.data, w, h, bytes_per_line, QImage.Format.Format_RGB888).copy()

            self.set_result_pixmap(img_data)

            self.threshold._update_value_dict(slider_values)
            self.logger.info("End image update.")
        else:
            self.logger.error("Failed image update.")
        
    def set_result_pixmap(self, q_img):
        """Scales and applies the processed image to the central result display area."""
        
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

    def history_update(self):
        """Appends the latest capture record to the top of the history management table."""

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

        # Populate the newly inserted row at the top (index 0)
        self.history_table.setCellWidget(0, 0, checkbox)
        self.history_table.setItem(0, 1, item1)
        self.history_table.setItem(0, 2, item2)
        self.history_table.setItem(0, 3, item3)
        self.history_table.setCellWidget(0, 4, action)

        self.row_checkboxes.append((checkbox, f_name))
        