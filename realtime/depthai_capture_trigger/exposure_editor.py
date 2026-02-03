#!/usr/bin/env python3
"""
Exposure Editor for DepthAI Motion Capture System
Interactive tool to set auto exposure or manual exposure settings
"""

import cv2
import depthai as dai
import json
import numpy as np


class ExposureEditor:
    def __init__(self, config_path='config.json'):
        """Initialize Exposure editor"""
        self.config_path = config_path
        self.config = self.load_config()
        
        self.current_frame = None
        
        # Exposure mode: "auto" or "manual"
        self.exposure_mode = self.config.get('exposure', {}).get('mode', 'auto')
        
        # Manual exposure settings
        # Exposure time in microseconds (1-33000 for 30fps, 1-20000 for 50fps)
        self.exposure_time = self.config.get('exposure', {}).get('time_us', 10000)
        
        # ISO/Sensitivity (100-1600)
        self.iso_value = self.config.get('exposure', {}).get('iso', 800)
        
        # Exposure compensation for auto mode (-3 to +3)
        self.exp_compensation = self.config.get('exposure', {}).get('compensation', 0)
        
    def load_config(self):
        """Load existing configuration"""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            # Return default config
            return {
                'camera': {'resolution': '1080p', 'fps': 30},
                'roi': {'x1': 0.25, 'y1': 0.25, 'x2': 0.75, 'y2': 0.75},
                'focus': {'mode': 'auto', 'x1': 0.4, 'y1': 0.4, 'x2': 0.6, 'y2': 0.6, 'manual_value': 130, 'enabled': True},
                'exposure': {'mode': 'auto', 'time_us': 10000, 'iso': 800, 'compensation': 0, 'enabled': True},
                'motion_detection': {'threshold': 25, 'min_contour_area': 500, 'gaussian_blur_kernel': 21},
                'capture': {'output_dir': 'captures', 'image_format': 'jpg', 'quality': 95, 'cooldown_seconds': 1.0}
            }
    
    def save_config(self):
        """Save exposure settings to configuration file"""
        if 'exposure' not in self.config:
            self.config['exposure'] = {}
            
        self.config['exposure']['mode'] = self.exposure_mode
        self.config['exposure']['time_us'] = self.exposure_time
        self.config['exposure']['iso'] = self.iso_value
        self.config['exposure']['compensation'] = self.exp_compensation
        self.config['exposure']['enabled'] = self.config.get('exposure', {}).get('enabled', True)
        
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=2)
        
        print(f"\n[SAVED] Exposure settings saved to {self.config_path}")
        if self.exposure_mode == 'auto':
            print(f"Mode: AUTO | Compensation: {self.exp_compensation}")
        else:
            print(f"Mode: MANUAL | Time: {self.exposure_time}us | ISO: {self.iso_value}")
        print()
    
    def draw_visualization(self, frame):
        """Draw exposure visualization on frame"""
        vis_frame = frame.copy()
        
        # Calculate brightness for visual feedback
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        avg_brightness = np.mean(gray)
        
        # Add instructions based on mode
        if self.exposure_mode == 'auto':
            instructions = [
                "MODE: AUTO EXPOSURE",
                f"Compensation: {self.exp_compensation:+d} (-3 to +3)",
                f"Avg Brightness: {avg_brightness:.1f}/255",
                "Press 'a'/'d': Adjust compensation ±1",
                "Press 'm' to switch to MANUAL mode",
                "Press 's' to save",
                "Press 'r' to reset",
                "Press 'q' to quit"
            ]
        else:
            instructions = [
                "MODE: MANUAL EXPOSURE",
                f"Exposure Time: {self.exposure_time}us",
                f"ISO: {self.iso_value}",
                f"Avg Brightness: {avg_brightness:.1f}/255",
                "W/S: Exposure time ±500us",
                "E/D: Exposure time ±100us",
                "A/D (hold Shift): ISO ±50",
                "Press 'm' to switch to AUTO mode",
                "Press 's' to save | 'q' to quit"
            ]
        
        y_offset = 30
        for i, instruction in enumerate(instructions):
            color = (0, 255, 255) if i == 0 else (255, 255, 255)  # Cyan for mode indicator
            thickness = 2 if i == 0 else 1
            cv2.putText(vis_frame, instruction, (10, y_offset),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, thickness)
            y_offset += 25
        
        # Draw brightness bar
        bar_width = 400
        bar_height = 30
        bar_x = frame.shape[1] - bar_width - 20
        bar_y = 20
        
        # Background
        cv2.rectangle(vis_frame, (bar_x, bar_y), (bar_x + bar_width, bar_y + bar_height), (50, 50, 50), -1)
        
        # Brightness indicator
        brightness_width = int((avg_brightness / 255.0) * bar_width)
        brightness_color = (0, 255, 0) if 80 < avg_brightness < 180 else (0, 165, 255)
        cv2.rectangle(vis_frame, (bar_x, bar_y), (bar_x + brightness_width, bar_y + bar_height), brightness_color, -1)
        
        # Border
        cv2.rectangle(vis_frame, (bar_x, bar_y), (bar_x + bar_width, bar_y + bar_height), (255, 255, 255), 2)
        
        # Label
        cv2.putText(vis_frame, "Brightness", (bar_x, bar_y - 5),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        # Show current settings at bottom
        if self.exposure_mode == 'auto':
            status_text = f"Auto Exposure | Compensation: {self.exp_compensation:+d}"
        else:
            status_text = f"Manual: {self.exposure_time}us @ ISO {self.iso_value}"
        
        enabled_status = "ENABLED" if self.config.get('exposure', {}).get('enabled', True) else "DISABLED"
        cv2.putText(vis_frame, f"{status_text} [{enabled_status}]", (10, frame.shape[0] - 10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        return vis_frame
    
    def create_pipeline(self):
        """Create DepthAI pipeline"""
        pipeline = dai.Pipeline()
        
        # Create ColorCamera
        cam_rgb = pipeline.create(dai.node.ColorCamera)
        resolution_map = {
            '1080p': dai.ColorCameraProperties.SensorResolution.THE_1080_P,
            '4k': dai.ColorCameraProperties.SensorResolution.THE_4_K,
            '12mp': dai.ColorCameraProperties.SensorResolution.THE_12_MP,
        }
        cam_rgb.setResolution(resolution_map.get(
            self.config['camera']['resolution'],
            dai.ColorCameraProperties.SensorResolution.THE_1080_P
        ))
        cam_rgb.setFps(self.config['camera']['fps'])
        cam_rgb.setInterleaved(False)
        cam_rgb.setColorOrder(dai.ColorCameraProperties.ColorOrder.BGR)
        
        # Create output
        xout_rgb = pipeline.create(dai.node.XLinkOut)
        xout_rgb.setStreamName("rgb")
        cam_rgb.video.link(xout_rgb.input)
        
        # Create control input
        xin_control = pipeline.create(dai.node.XLinkIn)
        xin_control.setStreamName("control")
        xin_control.out.link(cam_rgb.inputControl)
        
        return pipeline
    
    def apply_exposure_settings(self, q_control):
        """Apply current exposure settings to camera"""
        ctrl = dai.CameraControl()
        
        if self.exposure_mode == 'manual':
            # Set manual exposure
            ctrl.setManualExposure(self.exposure_time, self.iso_value)
            print(f"[APPLIED] Manual exposure: {self.exposure_time}us @ ISO {self.iso_value}")
        else:
            # Set auto exposure with compensation
            ctrl.setAutoExposureEnable()
            if self.exp_compensation != 0:
                ctrl.setAutoExposureCompensation(self.exp_compensation)
            print(f"[APPLIED] Auto exposure with compensation: {self.exp_compensation:+d}")
        
        q_control.send(ctrl)
    
    def get_max_exposure_time(self):
        """Calculate maximum exposure time based on FPS"""
        fps = self.config['camera'].get('fps', 30)
        # Max exposure is roughly (1/fps) in microseconds, with some margin
        return int((1000000 / fps) * 0.95)
    
    def run(self):
        """Main execution loop"""
        pipeline = self.create_pipeline()
        
        max_exposure = self.get_max_exposure_time()
        
        print("=" * 60)
        print("Exposure Editor - DepthAI Motion Capture System")
        print("=" * 60)
        print("\nExposure Modes:")
        print("  AUTO   - Camera automatically adjusts exposure")
        print("  MANUAL - Lock exposure time and ISO")
        print("\nControls:")
        print("  - Press 'm' to toggle between AUTO and MANUAL modes")
        print("  - Press 's' to save settings to config.json")
        print("  - Press 'q' to quit")
        print("\nAUTO mode:")
        print("  - Press 'a'/'d' to adjust compensation ±1")
        print("  - Compensation range: -3 to +3")
        print("\nMANUAL mode:")
        print("  - W/S: Exposure time ±500us")
        print("  - E/D: Exposure time ±100us")
        print(f"  - Exposure range: 1-{max_exposure}us")
        print("  - ISO range: 100-1600")
        print("\n" + "=" * 60 + "\n")
        
        with dai.Device(pipeline) as device:
            q_rgb = device.getOutputQueue(name="rgb", maxSize=4, blocking=False)
            q_control = device.getInputQueue(name="control")
            
            # Create window
            window_name = "Exposure Editor"
            cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(window_name, 960, 540)
            
            # Apply initial exposure settings
            self.apply_exposure_settings(q_control)
            
            while True:
                # Get frame
                in_rgb = q_rgb.get()
                frame = in_rgb.getCvFrame()
                self.current_frame = frame
                
                # Draw visualization
                vis_frame = self.draw_visualization(frame)
                
                # Display
                cv2.imshow(window_name, vis_frame)
                
                # Handle keyboard
                key = cv2.waitKey(1) & 0xFF
                
                if key == ord('q'):
                    break
                elif key == ord('s'):
                    self.save_config()
                elif key == ord('m'):
                    # Toggle mode
                    self.exposure_mode = 'manual' if self.exposure_mode == 'auto' else 'auto'
                    print(f"\n[MODE] Switched to {self.exposure_mode.upper()} mode\n")
                    self.apply_exposure_settings(q_control)
                elif key == ord('r') and self.exposure_mode == 'auto':
                    # Reset auto exposure compensation
                    self.exp_compensation = 0
                    print("\n[RESET] Exposure compensation reset to 0\n")
                    self.apply_exposure_settings(q_control)
                elif self.exposure_mode == 'auto':
                    # Auto mode adjustments
                    if key == ord('a'):
                        self.exp_compensation = min(3, self.exp_compensation + 1)
                        self.apply_exposure_settings(q_control)
                    elif key == ord('d'):
                        self.exp_compensation = max(-3, self.exp_compensation - 1)
                        self.apply_exposure_settings(q_control)
                elif self.exposure_mode == 'manual':
                    # Manual mode adjustments
                    if key == ord('w'):  # Increase exposure time (coarse)
                        self.exposure_time = min(max_exposure, self.exposure_time + 500)
                        self.apply_exposure_settings(q_control)
                    elif key == ord('s'):  # Decrease exposure time (coarse)
                        self.exposure_time = max(1, self.exposure_time - 500)
                        self.apply_exposure_settings(q_control)
                    elif key == ord('e'):  # Increase exposure time (fine)
                        self.exposure_time = min(max_exposure, self.exposure_time + 100)
                        self.apply_exposure_settings(q_control)
                    elif key == ord('d'):  # Decrease exposure time (fine)
                        self.exposure_time = max(1, self.exposure_time - 100)
                        self.apply_exposure_settings(q_control)
                    elif key == ord('a'):  # Increase ISO
                        self.iso_value = min(1600, self.iso_value + 50)
                        self.apply_exposure_settings(q_control)
                    elif key == ord('z'):  # Decrease ISO
                        self.iso_value = max(100, self.iso_value - 50)
                        self.apply_exposure_settings(q_control)
        
        cv2.destroyAllWindows()
        print("\nExposure Editor closed.")


if __name__ == "__main__":
    editor = ExposureEditor()
    editor.run()
