import sys
import cv2
import depthai as dai
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QImage
import picologging as logging

from realtime.inspection import Inspection
from config import camera_const
from config.log_config import log_fomatter
from realtime.depthai_capture_trigger.motion_capture import MotionCaptureSystem

class Camera(QThread):
    change_pixmap_signal = pyqtSignal(QImage)
    capture_finished_signal = pyqtSignal()

    def __init__(self):
        self.logger = logging.getLogger("camera")
        self.logger.setLevel(logging.DEBUG)

        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(log_fomatter.LogColorFormatter())
        self.logger.addHandler(ch)

        super().__init__()
        self.motion_engine = MotionCaptureSystem(config_path="realtime/depthai_capture_trigger/config.json")
        self._run_flag = True

        self.need_resize = False
        self.need_capture = False
        self.last_frame_shape = None

        self.json_data = None
        self.img_frame = None
        
        self.width_resize = camera_const.DEFAULT_CAMERA_SIZE[0]
        self.height_resize = camera_const.DEFAULT_CAMERA_SIZE[1]

        self.pipeline = dai.Pipeline()

        self.cam = self.pipeline.create(dai.node.ColorCamera)
        self.cam.setResolution(dai.ColorCameraProperties.SensorResolution.THE_4_K)
        self.cam.setInterleaved(False)
        self.cam.setColorOrder(dai.ColorCameraProperties.ColorOrder.BGR)
        self.cam.setFps(60)

        self.cam.setIspScale(1, 3) 

        self.video_out = self.pipeline.create(dai.node.XLinkOut)
        self.video_out.setStreamName(camera_const.VIDEO_OUT_STREAM_NAME)
        self.cam.isp.link(self.video_out.input)
        
        self.xout_image = self.pipeline.create(dai.node.XLinkOut)
        self.xout_image.setStreamName("image_4k")
        self.cam.video.link(self.xout_image.input)

        self.video_out.input.setQueueSize(1)
        self.video_out.input.setBlocking(False)
        self.xout_image.input.setQueueSize(1)
        self.xout_image.input.setBlocking(False)

    def run(self):
        self.logger.info("Start 4K Camera System")
        try:
            with dai.Device(self.pipeline) as self.device:
                self.logger.info(f"USB Speed: {self.device.getUsbSpeed()}")
                
                self.q_video = self.device.getOutputQueue(name=camera_const.VIDEO_OUT_STREAM_NAME, maxSize=1, blocking=False)
                q_image = self.device.getOutputQueue(name="image_4k", maxSize=1, blocking=False)
                
                while self._run_flag:
                    data = self.q_video.tryGet()
                    if data is None: continue

                    self.frame = data.getCvFrame()

                    current_shape = self.frame.shape
                    if self.last_frame_shape is not None and self.last_frame_shape != current_shape:
                        self.motion_engine = MotionCaptureSystem(config_path="realtime/depthai_capture_trigger/config.json")
                    self.last_frame_shape = current_shape

                    # Get ROI coordinates
                    start_roi_coords = self.motion_engine.get_roi_coords('start_roi', self.frame.shape)
                    end_roi_coords = self.motion_engine.get_roi_coords('end_roi', self.frame.shape)
                    
                    # Detect motion
                    motion_contours, thresh = self.motion_engine.detect_motion(self.frame)
                    
                    # Check if motion is in ROI
                    motion_in_start_roi = self.motion_engine.check_motion_in_roi(motion_contours, start_roi_coords)
                    motion_in_end_roi = self.motion_engine.check_motion_in_roi(motion_contours, end_roi_coords)

                    if self.motion_engine.capture_state == 'waiting' and motion_in_end_roi:
                        self.logger.info("[AUTO] Motion in ROI! Getting 4K Frame.")
                        self.motion_engine.capture_state = 'captured'
                        in_4k = q_image.get()
                        self.capture(in_4k.getCvFrame())

                    elif self.motion_engine.capture_state == 'captured' and not motion_in_end_roi:
                        self.motion_engine.frames_without_motion += 1
                        if self.motion_engine.frames_without_motion >= 3:
                            self.motion_engine.capture_state = 'waiting'
                            self.motion_engine.frames_without_motion = 0

                    if self.need_capture:
                        in_4k = q_image.get()
                        self.capture(in_4k.getCvFrame())

                    if self.need_resize:
                        self.resolution()

                    vis_frame = self.motion_engine.draw_visualization(self.frame, start_roi_coords, end_roi_coords, motion_contours, motion_in_start_roi, motion_in_end_roi)
                    
                    if self.width_resize != self.frame.shape[1] or self.height_resize != self.frame.shape[0]:
                        vis_frame = cv2.resize(vis_frame, (self.width_resize, self.height_resize), interpolation=cv2.INTER_LINEAR)

                    h, w, ch = vis_frame.shape
                    qt_img = QImage(vis_frame.data, w, h, ch * w, QImage.Format.Format_BGR888)
                    self.change_pixmap_signal.emit(qt_img.copy())
        except:
            self.logger.info("Run without camera")

    def stop(self):
        self._run_flag = False
        self.wait()

    def resolution(self):
        """해상도 변경"""
        self.logger.info(f"Applying Resolution: {self.width_resize}x{self.height_resize}")
        self.need_resize = False

    def capture(self, frame_4k):
        """캡처"""
        self.logger.info("Start capture (4K Original)")
        self.data_dict = Inspection().temporary(frame_4k)
        self.img_frame = frame_4k
        self.need_capture = False
        self.capture_finished_signal.emit()
        self.logger.info("End capture")