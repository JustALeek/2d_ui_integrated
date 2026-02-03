#!/usr/bin/env python3
"""
DepthAI Motion Detection Capture System
Detects moving objects in a predefined ROI and captures images
"""

import cv2
import depthai as dai
import numpy as np
import json
import os
from pathlib import Path
from datetime import datetime
import time
from concurrent.futures import ThreadPoolExecutor


class MotionCaptureSystem:
    def __init__(self, config_path='config.json'):
        """Initialize the motion capture system with configuration"""
        self.config = self.load_config(config_path)
        self.prev_frame = None
        self.capture_count = 0
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.future = None
        self.all_frames = []
        self.frames_without_motion = 0

        
        # State tracking for event-based capture
        # States: 'waiting' - ready to capture, 
        #         'recording' - appending frames and waiting for object to enter end ROI
        self.capture_state = 'waiting'
        
        # Create output directory
        output_dir = self.config['capture']['output_dir']
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
    def load_config(self, config_path):
        """Load configuration from JSON file"""
        with open(config_path, 'r') as f:
            return json.load(f)
    
    def create_pipeline(self):
        """Create DepthAI pipeline with camera"""
        pipeline = dai.Pipeline()
        
        # Create ColorCamera node
        cam_rgb = pipeline.create(dai.node.ColorCamera)
        
        # Set camera properties
        resolution_map = {
            '1080p': dai.ColorCameraProperties.SensorResolution.THE_1080_P,
            '4k': dai.ColorCameraProperties.SensorResolution.THE_4_K,
            '12mp': dai.ColorCameraProperties.SensorResolution.THE_12_MP,
        }
        cam_rgb.setResolution(resolution_map.get(
            self.config['camera']['resolution'], 
            dai.ColorCameraProperties.SensorResolution.THE_4_K
        ))
        cam_rgb.setFps(self.config['camera']['fps'])
        cam_rgb.setInterleaved(False)
        cam_rgb.setColorOrder(dai.ColorCameraProperties.ColorOrder.BGR)
        
        # Set autofocus mode
        cam_rgb.initialControl.setAutoFocusMode(dai.CameraControl.AutoFocusMode.AUTO)
        
        # Create output node
        xout_rgb = pipeline.create(dai.node.XLinkOut)
        xout_rgb.setStreamName("rgb")
        cam_rgb.video.link(xout_rgb.input)
        
        # Create control input for focus region
        xin_control = pipeline.create(dai.node.XLinkIn)
        xin_control.setStreamName("control")
        xin_control.out.link(cam_rgb.inputControl)
        
        return pipeline
    
    def get_roi_coords(self, roi_to_get, frame_shape):
        """Convert normalized ROI coordinates to pixel coordinates"""
        h, w = frame_shape[:2]
        roi = self.config[roi_to_get]
        
        x1 = int(roi['x1'] * w)
        y1 = int(roi['y1'] * h)
        x2 = int(roi['x2'] * w)
        y2 = int(roi['y2'] * h)
        
        return x1, y1, x2, y2
    
    def detect_motion(self, frame):
        """Detect motion using frame differencing"""
        # Convert to grayscale
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Apply Gaussian blur to reduce noise
        kernel_size = self.config['motion_detection']['gaussian_blur_kernel']
        gray = cv2.GaussianBlur(gray, (kernel_size, kernel_size), 0)
        
        # Initialize previous frame if needed
        if self.prev_frame is None:
            self.prev_frame = gray
            return [], None
        
        # Compute absolute difference between frames
        frame_delta = cv2.absdiff(self.prev_frame, gray)
        
        # Apply threshold
        threshold_val = self.config['motion_detection']['threshold']
        _, thresh = cv2.threshold(frame_delta, threshold_val, 255, cv2.THRESH_BINARY)
        
        # Dilate to fill in holes
        thresh = cv2.dilate(thresh, None, iterations=2)
        
        # Find contours
        contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Filter contours by area
        min_area = self.config['motion_detection']['min_contour_area']
        motion_contours = [c for c in contours if cv2.contourArea(c) >= min_area]
        
        # Update previous frame
        self.prev_frame = gray
        
        return motion_contours, thresh
    
    def check_motion_in_roi(self, contours, roi_coords):
        """Check if any motion contours intersect with ROI"""
        x1, y1, x2, y2 = roi_coords
        
        for contour in contours:
            # Get bounding box of contour
            cx, cy, cw, ch = cv2.boundingRect(contour)
            
            # Check if contour intersects with ROI
            # Intersection occurs if:
            # - contour right edge is right of ROI left edge AND
            # - contour left edge is left of ROI right edge AND
            # - contour bottom edge is below ROI top edge AND
            # - contour top edge is above ROI bottom edge
            if (cx + cw > x1 and cx < x2 and cy + ch > y1 and cy < y2):
                return True
        
        return False
    
    def save_image(self, frame):
        """Save captured image"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        output_dir = self.config['capture']['output_dir']
        image_format = self.config['capture']['image_format']
        quality = self.config['capture']['quality']
        
        filename = f"{output_dir}/capture_{timestamp}_{self.capture_count:04d}.{image_format}"
        
        if image_format.lower() in ['jpg', 'jpeg']:
            cv2.imwrite(filename, frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
        else:
            cv2.imwrite(filename, frame)
        
        self.capture_count += 1
        print(f"[CAPTURED] {filename}")
        
        return filename
    
    def setup_roi(self, roi_coords, motion_in_roi, vis_frame, label):
        x1, y1, x2, y2 = roi_coords
        roi_color = (0, 255, 0) if motion_in_roi else (255, 0, 0)
        # Draw ROI rectangle
        cv2.rectangle(vis_frame, (x1, y1), (x2, y2), roi_color, 2)
        
        # Draw ROI label
        cv2.putText(vis_frame, label, (x1, y1 - 10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, roi_color, 2)

    def draw_visualization(self, frame, start_roi_coords, end_roi_coords, motion_contours, motion_in_start_roi, motion_in_end_roi):
        """Draw ROI and motion visualization on frame"""
        vis_frame = frame.copy()
        self.setup_roi(start_roi_coords, motion_in_start_roi, vis_frame, "START_ROI")
        self.setup_roi(end_roi_coords, motion_in_end_roi, vis_frame, "END_ROI")
        
        # Draw motion contours
        for contour in motion_contours:
            cx, cy, cw, ch = cv2.boundingRect(contour)
            cv2.rectangle(vis_frame, (cx, cy), (cx + cw, cy + ch), (0, 255, 255), 1)
        
        # Draw status info
        state_color = (0, 255, 0) if self.capture_state == 'waiting' else (0, 165, 255)  # Green=ready, Orange=waiting
        state_text = f"State: {self.capture_state.upper()}"
        status_text = f"Captures: {self.capture_count} | {state_text} | Motion: {'YES' if motion_in_start_roi else 'NO'}"
        cv2.putText(vis_frame, status_text, (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, state_color, 2)
        
        # Draw instructions
        cv2.putText(vis_frame, "Press 'q' to quit | 'r' to reload config", (10, frame.shape[0] - 10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        return vis_frame
    
    def compute_sharpest(self, frames_copy):
        gray_frames = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) for f in frames_copy]
        scores = [cv2.Laplacian(gf, cv2.CV_32F).var() for gf in gray_frames]
        print("PICKED FROM ", str(len(scores)), " FRAMES")
        idx = int(np.argmax(scores))
        return frames_copy[idx]
    
    def get_sharpest_frame_async(self):
        frames_copy = list(self.all_frames)
        # Asynchronous so it doesn't block visualization
        return self.executor.submit(self.compute_sharpest, frames_copy)

    # saves all images in all_frames (used to debug)
    def save_all(self):
        for frame in self.all_frames:
            self.save_image(frame)
        
    def run(self):
        """Main execution loop"""
        pipeline = self.create_pipeline()
        
        print("Starting DepthAI Motion Capture System...")
        print(f"Config: {self.config}")
        print(f"Output directory: {self.config['capture']['output_dir']}")
        print("\nPress 'q' to quit, 'r' to reload config\n")
        
        with dai.Device(pipeline) as device:
            # Get output queue
            q_rgb = device.getOutputQueue(name="rgb", maxSize=4, blocking=False)
            q_control = device.getInputQueue(name="control")
            
            # Apply focus settings from config if enabled
            if self.config.get('focus', {}).get('enabled', False):
                focus = self.config.get('focus', {})
                focus_mode = focus.get('mode', 'auto')
                ctrl = dai.CameraControl()

                if focus_mode == 'manual':
                    # Apply manual/fixed focus
                    manual_value = focus.get('manual_value', 130)
                    ctrl.setManualFocus(manual_value)
                    print(f"[FOCUS] Applied MANUAL focus: {manual_value} (0=far, 255=near)")
                else:
                    # Apply autofocus region
                    ctrl.setAutoFocusMode(dai.CameraControl.AutoFocusMode.AUTO)
                    ctrl.setAutoFocusRegion(
                        int(focus.get('x1', 0.4) * 65535),
                        int(focus.get('y1', 0.4) * 65535),
                        int(focus.get('x2', 0.6) * 65535),
                        int(focus.get('y2', 0.6) * 65535)
                    )
                    print(f"[FOCUS] Applied AUTO focus region: ({focus.get('x1', 0.4):.3f}, {focus.get('y1', 0.4):.3f}) to ({focus.get('x2', 0.6):.3f}, {focus.get('y2', 0.6):.3f})")

                q_control.send(ctrl)

            # Apply exposure settings from config if enabled
            if self.config.get('exposure', {}).get('enabled', False):
                exposure = self.config.get('exposure', {})
                exposure_mode = exposure.get('mode', 'auto')
                ctrl = dai.CameraControl()

                if exposure_mode == 'manual':
                    # Apply manual exposure
                    time_us = exposure.get('time_us', 10000)
                    iso = exposure.get('iso', 800)
                    ctrl.setManualExposure(time_us, iso)
                    print(f"[EXPOSURE] Applied MANUAL exposure: {time_us}us @ ISO {iso}")
                else:
                    # Apply auto exposure with compensation
                    ctrl.setAutoExposureEnable()
                    compensation = exposure.get('compensation', 0)
                    if compensation != 0:
                        ctrl.setAutoExposureCompensation(compensation)
                    print(f"[EXPOSURE] Applied AUTO exposure with compensation: {compensation:+d}")

                q_control.send(ctrl)

            # Create single combined window
            cv2.namedWindow("Motion Capture System", cv2.WINDOW_NORMAL)
            cv2.resizeWindow("Motion Capture System", 1280, 540)  # Wide enough for side-by-side

            while True:
                # Checking for potential cases of infinitely appending frames 
                if(len(self.all_frames) >= 200):
                    self.capture_state == 'waiting'
                    self.all_frames.clear()

                # Get frame
                in_rgb = q_rgb.get()
                frame = in_rgb.getCvFrame()

                # Get ROI coordinates
                start_roi_coords = self.get_roi_coords('start_roi', frame.shape)
                end_roi_coords = self.get_roi_coords('end_roi', frame.shape)
                
                # Detect motion
                motion_contours, thresh = self.detect_motion(frame)
                
                # Check if motion is in ROI
                motion_in_start_roi = self.check_motion_in_roi(motion_contours, start_roi_coords)
                motion_in_end_roi = self.check_motion_in_roi(motion_contours, end_roi_coords)
                
                # State tracking for event-based capture
                # States: 'waiting' - ready to capture, 
                #         'recording' - appending frames and waiting for object to enter end ROI
        
                if self.capture_state == 'waiting':
                    if motion_in_start_roi and not motion_in_end_roi:
                        # New object entered starting ROI - begin recording and change state
                        self.all_frames.append(frame)
                        self.capture_state = 'recording'
                        self.frames_without_motion = 0
                        print("[STATE] Changed to RECORDING - waiting for ROI to clear")
                elif self.capture_state == 'recording':
                    if motion_in_end_roi:
                        self.capture_state = 'waiting'
                        self.frames_without_motion = 0
                        # Only save if more than 3 frames - prevents saving when ROIs 깜빡깜빡
                        if len(self.all_frames) > 3:
                            self.future = self.get_sharpest_frame_async()
                            print("[STATE] ROI clear - ready for next capture")
                        else:
                            self.all_frames = []
                    else:
                        # Did not reach end_roi - continue recording
                        self.all_frames.append(frame)

                # Visualize
                vis_frame = self.draw_visualization(frame, start_roi_coords, end_roi_coords, motion_contours, motion_in_start_roi, motion_in_end_roi)

                # Resolve the sharpest frame calculation and save
                if self.future and self.future.done():
                    print("SAVE")
                    sharpest = self.future.result()
                    self.save_image(sharpest)
                    self.all_frames = []
                    self.future = None

                # Combine live view and threshold into single window
                if thresh is not None:
                    # Convert threshold to BGR for concatenation
                    thresh_bgr = cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)

                    # Resize both to same height if needed
                    h = vis_frame.shape[0]
                    thresh_bgr = cv2.resize(thresh_bgr, (int(thresh_bgr.shape[1] * h / thresh_bgr.shape[0]), h))

                    # Add labels
                    cv2.putText(vis_frame, "Live View", (10, 60), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
                    cv2.putText(thresh_bgr, "Motion Threshold", (10, 60), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

                    # Concatenate horizontally
                    combined = np.hstack([vis_frame, thresh_bgr])
                    cv2.imshow("Motion Capture System", combined)
                else:
                    cv2.imshow("Motion Capture System", vis_frame)

                # Handle keyboard input
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    break
                elif key == ord('r'):
                    # Reload configuration
                    self.config = self.load_config('config.json')
                    print("\n[CONFIG RELOADED]")
                    print(f"New config: {self.config}\n")

        cv2.destroyAllWindows()
        print(f"\nSession ended. Total captures: {self.capture_count}")

if __name__ == "__main__":
    system = MotionCaptureSystem()
    system.run()
