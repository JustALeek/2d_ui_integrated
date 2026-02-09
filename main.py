import sys
import picologging as logging

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout, 
                             QFrame, QVBoxLayout)

from realtime.camera import Camera
from analysis.history import History
from config import main_const
from config.log_config import log_fomatter
from analysis.post_processor import MainManager

from ui.streaming_ui import StreamingUi
from ui.image_ui import ImageUi
from ui.threshold_ui import ThresholdUi
from ui.history_ui import HistoryUi

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

    def initUI(self):
        """Configures the main layout structure and arranges all frames."""
        self.logger.info("Start init UI.")
        self.history = History()
        
        # Initialize global variables for threshold and resolution
        self.resolution_current_index = main_const.RESOLUTION_DEFAULT_INDEX

        # Set main window properties from constants
        self.setWindowTitle(main_const.WINDOW_TITLE)
        self.resize(main_const.WINDOW_RESIZE[0], main_const.WINDOW_RESIZE[1])

        # Define the central widget and main horizontal layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # Create primary container frames for left and right sections
        self.left_frame = QFrame()
        self.right_frame = QFrame()
        main_layout.addWidget(self.left_frame)
        main_layout.addWidget(self.right_frame)

        # Initialize the camera background thread
        self.camera = Camera()

        # Establish nested layouts for modular widget placement
        left_layout = QVBoxLayout(self.left_frame)
        right_layout = QVBoxLayout(self.right_frame)

        # Instantiate right-side modules: Result Display, Threshold Control, and History Table
        self.image_view = ImageUi(self.logger, self.history, self.manager)
        self.threshold_view = ThresholdUi(self.logger, self.manager, self.history, self.image_view)
        self.history_view = HistoryUi(self.camera, self.history, self.image_view, self.logger, self.manager, self.threshold_view)

        # Add right-side widgets with specific stretch ratios
        right_layout.addWidget(self.image_view, stretch=12)
        right_layout.addWidget(self.threshold_view, stretch=1)
        right_layout.addWidget(self.history_view, stretch=7)

        # Instantiate and add the left-side real-time streaming module
        self.streaming_view = StreamingUi(self.camera, self.history_view, self.image_view, self.logger, self.resolution_current_index, self.manager, self.threshold_view)
        left_layout.addWidget(self.streaming_view)

        # Start camera thread and display window
        self.camera.start()
        self.show()

        # Set default focus to the streaming view for immediate keyboard interaction
        self.streaming_view.setFocus()

        # Synchronize view with the most recent inspection data
        self.init_last_inspection()

        self.logger.info("End init UI")

    def init_last_inspection(self):
        """Initializes the visualization interface by retrieving the most recent inspection record from the local repository."""
        try:
            # Fetch latest inspection record
            jpg_file, _, _= self.history.get_last_img()
            
            if jpg_file:
                # Sync data to camera buffer
                frame, slider_values, data_dict = self.manager.run_load_pipeline(jpg_file)
                self.image_view.current_image_data = data_dict
                self.threshold_view
                self.image_view.update_view(frame)
                self.threshold_view._update_value(slider_values["neighbour_margin_factor"], 1)
                self.threshold_view._update_value(slider_values["boundary_margin_factor"], 2)
                self.threshold_view._update_value(slider_values["max_connected_line_dist"], 3)
                self.threshold_view._update_value(slider_values["max_component_offset_dist"], 4)
                self.threshold_view._update_value(slider_values["max_stitching_offset_dist"], 5)
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
    