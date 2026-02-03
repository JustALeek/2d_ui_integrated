#!/usr/bin/env python3
"""
Focus Editor for DepthAI Motion Capture System
Interactive tool to set autofocus region or manual/fixed focus
"""

import cv2
import depthai as dai
import json
import numpy as np


class FocusEditor:
    def __init__(self, config_path='config.json'):
        """Initialize Focus editor"""
        self.config_path = config_path
        self.config = self.load_config()
        
        # Focus region selection state
        self.selecting = False
        self.start_point = None
        self.end_point = None
        self.current_frame = None
        
        # Focus mode: "auto" or "manual"
        self.focus_mode = self.config.get('focus', {}).get('mode', 'auto')
        
        # Manual focus value (0-255)
        self.manual_focus_value = self.config.get('focus', {}).get('manual_value', 130)
        
        # Normalized coordinates for auto mode
        self.focus_normalized = {
            'x1': self.config.get('focus', {}).get('x1', 0.4),
            'y1': self.config.get('focus', {}).get('y1', 0.4),
            'x2': self.config.get('focus', {}).get('x2', 0.6),
            'y2': self.config.get('focus', {}).get('y2', 0.6)
        }
        
    def load_config(self):
        """Load existing configuration"""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            # Return default config if file doesn't exist
            return {
                'camera': {'resolution': '1080p', 'fps': 30},
                'roi': {'x1': 0.25, 'y1': 0.25, 'x2': 0.75, 'y2': 0.75},
                'focus': {
                    'mode': 'auto',
                    'x1': 0.4, 'y1': 0.4, 'x2': 0.6, 'y2': 0.6,
                    'manual_value': 130,
                    'enabled': True
                },
                'motion_detection': {'threshold': 25, 'min_contour_area': 500, 'gaussian_blur_kernel': 21},
                'capture': {'output_dir': 'captures', 'image_format': 'jpg', 'quality': 95, 'cooldown_seconds': 1.0}
            }
    
    def save_config(self):
        """Save focus settings to configuration file"""
        if 'focus' not in self.config:
            self.config['focus'] = {}
            
        self.config['focus']['mode'] = self.focus_mode
        self.config['focus']['x1'] = self.focus_normalized['x1']
        self.config['focus']['y1'] = self.focus_normalized['y1']
        self.config['focus']['x2'] = self.focus_normalized['x2']
        self.config['focus']['y2'] = self.focus_normalized['y2']
        self.config['focus']['manual_value'] = self.manual_focus_value
        self.config['focus']['enabled'] = self.config.get('focus', {}).get('enabled', True)
        
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=2)
        
        print(f"\n[SAVED] Focus settings saved to {self.config_path}")
        if self.focus_mode == 'auto':
            print(f"Mode: AUTO | Region: ({self.focus_normalized['x1']:.3f}, {self.focus_normalized['y1']:.3f}) to "
                  f"({self.focus_normalized['x2']:.3f}, {self.focus_normalized['y2']:.3f})")
        else:
            print(f"Mode: MANUAL | Focus Value: {self.manual_focus_value}")
        print()
    
    def mouse_callback(self, event, x, y, flags, param):
        """Handle mouse events for focus region selection (auto mode only)"""
        if self.focus_mode != 'auto':
            return
            
        if event == cv2.EVENT_LBUTTONDOWN:
            # Start selecting
            self.selecting = True
            self.start_point = (x, y)
            self.end_point = (x, y)
            
        elif event == cv2.EVENT_MOUSEMOVE:
            # Update selection
            if self.selecting:
                self.end_point = (x, y)
                
        elif event == cv2.EVENT_LBUTTONUP:
            # Finish selection
            self.selecting = False
            self.end_point = (x, y)
            
            # Update normalized coordinates
            if self.current_frame is not None:
                h, w = self.current_frame.shape[:2]
                
                # Ensure proper ordering (top-left to bottom-right)
                x1 = min(self.start_point[0], self.end_point[0])
                x2 = max(self.start_point[0], self.end_point[0])
                y1 = min(self.start_point[1], self.end_point[1])
                y2 = max(self.start_point[1], self.end_point[1])
                
                # Normalize
                self.focus_normalized['x1'] = max(0.0, min(1.0, x1 / w))
                self.focus_normalized['y1'] = max(0.0, min(1.0, y1 / h))
                self.focus_normalized['x2'] = max(0.0, min(1.0, x2 / w))
                self.focus_normalized['y2'] = max(0.0, min(1.0, y2 / h))
                
                print(f"Focus region selected: ({x1}, {y1}) to ({x2}, {y2})")
                print(f"Normalized: ({self.focus_normalized['x1']:.3f}, {self.focus_normalized['y1']:.3f}) "
                      f"to ({self.focus_normalized['x2']:.3f}, {self.focus_normalized['y2']:.3f})")
    
    def get_focus_coords(self, frame_shape):
        """Convert normalized focus region to pixel coordinates"""
        h, w = frame_shape[:2]
        
        x1 = int(self.focus_normalized['x1'] * w)
        y1 = int(self.focus_normalized['y1'] * h)
        x2 = int(self.focus_normalized['x2'] * w)
        y2 = int(self.focus_normalized['y2'] * h)
        
        return x1, y1, x2, y2
    
    def draw_visualization(self, frame):
        """Draw focus visualization on frame"""
        vis_frame = frame.copy()
        
        if self.focus_mode == 'auto':
            # Draw autofocus region
            x1, y1, x2, y2 = self.get_focus_coords(frame.shape)
            cv2.rectangle(vis_frame, (x1, y1), (x2, y2), (255, 0, 255), 2)  # Magenta
            cv2.putText(vis_frame, "Autofocus Region", (x1, y1 - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 255), 2)
            
            # Draw selection in progress
            if self.selecting and self.start_point and self.end_point:
                cv2.rectangle(vis_frame, self.start_point, self.end_point, (255, 255, 0), 2)
                cv2.putText(vis_frame, "Selecting...", (self.start_point[0], self.start_point[1] - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
        
        # Add instructions based on mode
        if self.focus_mode == 'auto':
            instructions = [
                "MODE: AUTOFOCUS REGION",
                "Click and drag to define focus region",
                "Press 'm' to switch to MANUAL mode",
                "Press 's' to save",
                "Press 'r' to reset region",
                "Press 'q' to quit"
            ]
        else:
            instructions = [
                "MODE: MANUAL/FIXED FOCUS",
                f"Current value: {self.manual_focus_value} (0=far, 255=near)",
                "Press 'a'/'d': Adjust ±1",
                "Arrow LEFT/RIGHT: Adjust ±10",
                "Press 'm' to switch to AUTO mode",
                "Press 's' to save",
                "Press 'q' to quit"
            ]
        
        y_offset = 30
        for i, instruction in enumerate(instructions):
            color = (0, 255, 255) if i == 0 else (255, 255, 255)  # Cyan for mode indicator
            thickness = 2 if i == 0 else 1
            cv2.putText(vis_frame, instruction, (10, y_offset),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, thickness)
            y_offset += 25
        
        # Show current settings at bottom
        if self.focus_mode == 'auto':
            status_text = f"Auto Region: ({self.focus_normalized['x1']:.3f}, {self.focus_normalized['y1']:.3f}) to ({self.focus_normalized['x2']:.3f}, {self.focus_normalized['y2']:.3f})"
        else:
            status_text = f"Manual Focus: {self.manual_focus_value}/255"
        
        enabled_status = "ENABLED" if self.config.get('focus', {}).get('enabled', True) else "DISABLED"
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
    
    def apply_focus_settings(self, q_control):
        """Apply current focus settings to camera"""
        ctrl = dai.CameraControl()
        
        if self.focus_mode == 'manual':
            # Set manual focus
            ctrl.setManualFocus(self.manual_focus_value)
            print(f"[APPLIED] Manual focus: {self.manual_focus_value}")
        else:
            # Set autofocus with region
            ctrl.setAutoFocusMode(dai.CameraControl.AutoFocusMode.AUTO)
            ctrl.setAutoFocusRegion(
                int(self.focus_normalized['x1'] * 65535),
                int(self.focus_normalized['y1'] * 65535),
                int(self.focus_normalized['x2'] * 65535),
                int(self.focus_normalized['y2'] * 65535)
            )
            print(f"[APPLIED] Autofocus region: ({self.focus_normalized['x1']:.3f}, {self.focus_normalized['y1']:.3f}) "
                  f"to ({self.focus_normalized['x2']:.3f}, {self.focus_normalized['y2']:.3f})")
        
        q_control.send(ctrl)
    
    def run(self):
        """Main execution loop"""
        pipeline = self.create_pipeline()
        
        print("=" * 60)
        print("Focus Editor - DepthAI Motion Capture System")
        print("=" * 60)
        print("\nFocus Modes:")
        print("  AUTO   - Camera autofocuses within a defined region")
        print("  MANUAL - Focus locked at a specific distance (0-255)")
        print("\nControls:")
        print("  - Press 'm' to toggle between AUTO and MANUAL modes")
        print("  - Press 's' to save settings to config.json")
        print("  - Press 'q' to quit")
        print("\nAUTO mode:")
        print("  - Click and drag to define autofocus region")
        print("  - Press 'r' to reset to default region")
        print("\nMANUAL mode:")
        print("  - Arrow UP/DOWN: Adjust focus ±1")
        print("  - Arrow LEFT/RIGHT: Adjust focus ±10")
        print("  - 0=Far objects, 255=Near objects")
        print("\n" + "=" * 60 + "\n")
        
        with dai.Device(pipeline) as device:
            q_rgb = device.getOutputQueue(name="rgb", maxSize=4, blocking=False)
            q_control = device.getInputQueue(name="control")
            
            # Create window and set mouse callback
            window_name = "Focus Editor"
            cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(window_name, 960, 540)
            cv2.setMouseCallback(window_name, self.mouse_callback)
            
            # Apply initial focus settings
            self.apply_focus_settings(q_control)
            
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
                    self.focus_mode = 'manual' if self.focus_mode == 'auto' else 'auto'
                    print(f"\n[MODE] Switched to {self.focus_mode.upper()} mode\n")
                    self.apply_focus_settings(q_control)
                elif key == ord('r') and self.focus_mode == 'auto':
                    # Reset autofocus region to defaults
                    self.focus_normalized = {'x1': 0.4, 'y1': 0.4, 'x2': 0.6, 'y2': 0.6}
                    print("\n[RESET] Focus region reset to defaults (center 20%)\n")
                    self.apply_focus_settings(q_control)
                elif self.focus_mode == 'manual':
                    # Manual focus adjustments
                    if key == ord('a'):  # Up arrow (Windows/Linux)
                        self.manual_focus_value = min(255, self.manual_focus_value + 1)
                        self.apply_focus_settings(q_control)
                    elif key == ord('d'):  # Down arrow
                        self.manual_focus_value = max(0, self.manual_focus_value - 1)
                        self.apply_focus_settings(q_control)
                    elif key == 83 or key == 2:  # Right arrow
                        self.manual_focus_value = min(255, self.manual_focus_value + 10)
                        self.apply_focus_settings(q_control)
                    elif key == 81 or key == 3:  # Left arrow
                        self.manual_focus_value = max(0, self.manual_focus_value - 10)
                        self.apply_focus_settings(q_control)
        
        cv2.destroyAllWindows()
        print("\nFocus Editor closed.")


if __name__ == "__main__":
    editor = FocusEditor()
    editor.run()
