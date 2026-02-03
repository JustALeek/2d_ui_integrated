#!/usr/bin/env python3
"""
ROI (Region of Interest) Editor for DepthAI Motion Capture System
Interactive tool to define and adjust the detection area
"""

import cv2
import depthai as dai
import json
import numpy as np


class ROIEditor:
    def __init__(self, config_path='config.json'):
        """Initialize ROI editor"""
        self.config_path = config_path
        self.config = self.load_config()
        
        # ROI selection state
        self.selecting = False
        self.start_point = None
        self.end_point = None
        self.current_frame = None
        
        # Normalized coordinates
        self.roi_normalized = {
            'x1': self.config['roi']['x1'],
            'y1': self.config['roi']['y1'],
            'x2': self.config['roi']['x2'],
            'y2': self.config['roi']['y2']
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
                'motion_detection': {'threshold': 25, 'min_contour_area': 500, 'gaussian_blur_kernel': 21},
                'capture': {'output_dir': 'captures', 'image_format': 'jpg', 'quality': 95, 'cooldown_seconds': 1.0}
            }
    
    def save_config(self):
        """Save ROI to configuration file"""
        self.config['roi']['x1'] = self.roi_normalized['x1']
        self.config['roi']['y1'] = self.roi_normalized['y1']
        self.config['roi']['x2'] = self.roi_normalized['x2']
        self.config['roi']['y2'] = self.roi_normalized['y2']
        
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=2)
        
        print(f"\n[SAVED] ROI coordinates saved to {self.config_path}")
        print(f"ROI: x1={self.roi_normalized['x1']:.3f}, y1={self.roi_normalized['y1']:.3f}, "
              f"x2={self.roi_normalized['x2']:.3f}, y2={self.roi_normalized['y2']:.3f}\n")
    
    def mouse_callback(self, event, x, y, flags, param):
        """Handle mouse events for ROI selection"""
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
                self.roi_normalized['x1'] = max(0.0, min(1.0, x1 / w))
                self.roi_normalized['y1'] = max(0.0, min(1.0, y1 / h))
                self.roi_normalized['x2'] = max(0.0, min(1.0, x2 / w))
                self.roi_normalized['y2'] = max(0.0, min(1.0, y2 / h))
                
                print(f"ROI selected: ({x1}, {y1}) to ({x2}, {y2})")
                print(f"Normalized: ({self.roi_normalized['x1']:.3f}, {self.roi_normalized['y1']:.3f}) "
                      f"to ({self.roi_normalized['x2']:.3f}, {self.roi_normalized['y2']:.3f})")
    
    def get_roi_coords(self, frame_shape):
        """Convert normalized ROI to pixel coordinates"""
        h, w = frame_shape[:2]
        
        x1 = int(self.roi_normalized['x1'] * w)
        y1 = int(self.roi_normalized['y1'] * h)
        x2 = int(self.roi_normalized['x2'] * w)
        y2 = int(self.roi_normalized['y2'] * h)
        
        return x1, y1, x2, y2
    
    def draw_roi(self, frame):
        """Draw ROI on frame"""
        vis_frame = frame.copy()
        
        # Draw current ROI
        x1, y1, x2, y2 = self.get_roi_coords(frame.shape)
        cv2.rectangle(vis_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(vis_frame, "Current ROI", (x1, y1 - 10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
        # Draw selection in progress
        if self.selecting and self.start_point and self.end_point:
            cv2.rectangle(vis_frame, self.start_point, self.end_point, (255, 255, 0), 2)
            cv2.putText(vis_frame, "Selecting...", (self.start_point[0], self.start_point[1] - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
        
        # Add instructions
        instructions = [
            "Click and drag to define ROI",
            "Press 's' to save",
            "Press 'r' to reset to defaults",
            "Press 'q' to quit"
        ]
        
        y_offset = 30
        for instruction in instructions:
            cv2.putText(vis_frame, instruction, (10, y_offset),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            y_offset += 25
        
        # Show current normalized coordinates
        coord_text = f"ROI: ({self.roi_normalized['x1']:.3f}, {self.roi_normalized['y1']:.3f}) to ({self.roi_normalized['x2']:.3f}, {self.roi_normalized['y2']:.3f})"
        cv2.putText(vis_frame, coord_text, (10, frame.shape[0] - 10),
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
        
        return pipeline
    
    def run(self):
        """Main execution loop"""
        pipeline = self.create_pipeline()
        
        print("=" * 60)
        print("ROI Editor - DepthAI Motion Capture System")
        print("=" * 60)
        print("\nInstructions:")
        print("  - Click and drag on the video feed to define ROI")
        print("  - Press 's' to save ROI to config.json")
        print("  - Press 'r' to reset to default ROI (center 50%)")
        print("  - Press 'q' to quit")
        print("\n" + "=" * 60 + "\n")
        
        with dai.Device(pipeline) as device:
            q_rgb = device.getOutputQueue(name="rgb", maxSize=4, blocking=False)
            
            # Create window and set mouse callback
            window_name = "ROI Editor"
            cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(window_name, 960, 540)  # 50% of 1080p resolution
            cv2.setMouseCallback(window_name, self.mouse_callback)
            
            while True:
                # Get frame
                in_rgb = q_rgb.get()
                frame = in_rgb.getCvFrame()
                self.current_frame = frame
                
                # Draw ROI
                vis_frame = self.draw_roi(frame)
                
                # Display
                cv2.imshow(window_name, vis_frame)
                
                # Handle keyboard
                key = cv2.waitKey(1) & 0xFF
                
                if key == ord('q'):
                    break
                elif key == ord('s'):
                    self.save_config()
                elif key == ord('r'):
                    # Reset to defaults
                    self.roi_normalized = {'x1': 0.25, 'y1': 0.25, 'x2': 0.75, 'y2': 0.75}
                    print("\n[RESET] ROI reset to defaults (center 50%)\n")
        
        cv2.destroyAllWindows()
        print("\nROI Editor closed.")


if __name__ == "__main__":
    editor = ROIEditor()
    editor.run()
