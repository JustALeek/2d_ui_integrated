"""
Class for managing and displaying the results of a 4K inspection.
Provides visualization of bounding boxes, error values, and pass/fail status.
"""

import cv2

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QVBoxLayout, QLabel, QGroupBox
from PyQt6.QtGui import QImage, QPixmap

from config import main_const

class ImageUi(QGroupBox):
    def __init__(self, logger, history, parent=None):
        super().__init__(main_const.ANALYSIS_RESULT_TITLE_TEXT, parent)
        self.logger = logger
        self.history = history
        self.current_image_data = None
        
        self._init_styling()
        self._setup_ui()

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
        """Initializes the layout and the label used to display the processed image."""

        layout = QVBoxLayout(self)

        # Label for displaying the inspection result image
        self.result_image = QLabel(main_const.RESULT_IMAGE_TEXT)
        self.result_image.setStyleSheet("border-radius: 6px;")
        self.result_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(self.result_image)

    def update_view(self, frame):
        """Processes and renders the inspection frame with error overlays."""

        if frame is None:
            self.logger.warning("Frame is missing. Update skipped.")
            return
        
        # Create a copy to prevent modifying the original source frame
        draw_frame = frame.copy()
        h, w = draw_frame.shape[:2]
        
        # Convert the OpenCV BGR image to RGB and then to a QImage for PyQt6 compatibility
        rgb_image = cv2.cvtColor(draw_frame, cv2.COLOR_BGR2RGB)
        q_img = QImage(rgb_image.data, w, h, 3 * w, QImage.Format.Format_RGB888).copy()

        self.set_result_pixmap(q_img)

    def set_result_pixmap(self, q_img):
        """Scales the provided QImage and applies it to the display label."""

        if q_img is None or q_img.isNull():
            return

        pixmap = QPixmap.fromImage(q_img)
        label_size = self.result_image.size()
        
        # Scale pixmap to fit the UI container while maintaining aspect ratio
        scaled_pixmap = pixmap.scaled(
            label_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        
        self.result_image.setScaledContents(False) 
        self.result_image.setPixmap(scaled_pixmap)
        self.logger.info("Result view updated successfully.")

