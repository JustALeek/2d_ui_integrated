"""
Two-Stage Instance Segmentation Inference Pipeline
Stage 1: Detector → Stage 2: MobileSAM → Instance Masks
"""

import os
import argparse
import torch
import cv2
import numpy as np
from config import inspection_const
from detection.segmentation.model import TwoStageInstanceSeg
from detection.segmentation.utils import decode_predictions


class TwoStageInference:
    """End-to-end two-stage instance segmentation inference."""
    
    def __init__(self):
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        
        print(f"Loading model on {self.device}...")
        
        # Load model
        self.model = TwoStageInstanceSeg(
            mobilesam_ckpt=inspection_const.MOBILESAM_CKPT,
            num_classes=inspection_const.NUM_CLASSES,
            lora_config=inspection_const.LORA_CONFIG,
            num_anchors=inspection_const.NUM_ANCHORS
        ).to(self.device)
        
        # Load detector checkpoint
        det_ckpt = torch.load(inspection_const.DETECTOR_CKPT, map_location=self.device)
        self.model.load_state_dict(det_ckpt['model_state_dict'], strict=False)
        
        # Load SAM checkpoint (if provided and different from detector)
        sam_ckpt_data = torch.load(inspection_const.SAM_CKPT, map_location=self.device)
        self.model.load_state_dict(sam_ckpt_data['model_state_dict'], strict=False)
        
        self.model.eval()
        
        # Anchors for decoding
        self.anchors = {
            64: torch.tensor(inspection_const.ANCHORS_64),
            128: torch.tensor(inspection_const.ANCHORS_128)
        }
        
        print("✓ Model loaded successfully\n")
    
    def preprocess_image(self, img):
        """Load and preprocess image."""
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        orig_h, orig_w = img.shape[:2]
        
        # Resize to target size
        img_resized = cv2.resize(img, (inspection_const.TARGET_SIZE, inspection_const.TARGET_SIZE))
        
        # Convert to tensor
        img_t = torch.from_numpy(img_resized).permute(2, 0, 1).float() / 255.0
        img_t = img_t.unsqueeze(0).to(self.device)
        
        return img_t, img, (orig_h, orig_w)
    
    @torch.no_grad()
    def predict(self, image, mask_threshold=0.5, min_mask_area=100, smooth_masks=True):
        """
        Run two-stage inference on an image.
        
        Args:
            image: Image as ndarray
            conf_threshold: Detection confidence threshold
            nms_threshold: NMS IoU threshold
            mask_threshold: Mask binarization threshold
            min_mask_area: Minimum mask area in pixels to keep (filters noise)
            smooth_masks: Apply Gaussian blur for smoother masks (default: True)
            
        Returns:
            dict with 'boxes', 'masks', 'scores', 'labels'
        """
        
        # Preprocess
        img_t, orig_img, (orig_h, orig_w) = self.preprocess_image(image)
        
        # Stage 1: Run detector to get bounding boxes
        print("Stage 1: Running detector...")
        det_predictions = self.model(img_t, mode='detector')
        
        # Decode detections
        detections = decode_predictions(
            det_predictions,
            self.anchors,
            conf_threshold=inspection_const.CONF_THRESHOLD,
            nms_threshold=inspection_const.NMS_THRESHOLD,
            input_size=inspection_const.TARGET_SIZE
        )
        
        det = detections[0]  # First (and only) batch item
        
        if len(det['boxes']) == 0:
            print("No instances detected")
            return {
                'labels': np.zeros(0, dtype=int),
                'contours': []
            }
        
        print(f"Detected {len(det['boxes'])} instances")
        
        # Stage 2: Run MobileSAM with detected boxes to get precise masks
        print("Stage 2: Running MobileSAM with detected boxes...")
        boxes_list = [det['boxes']]
        pred_masks = self.model(img_t, boxes=boxes_list, mode='sam')
        
        # Process masks - resize FIRST, then threshold
        masks = torch.sigmoid(pred_masks[0]).cpu().numpy()
        
        # Scale boxes back to original image size
        boxes_np = det['boxes'].cpu().numpy()
        boxes_np[:, [0, 2]] *= orig_w
        boxes_np[:, [1, 3]] *= orig_h
        
        # Resize masks to original image size (resize sigmoid values, then threshold)
        contours_filtered = []
        labels_filtered = []
        
        for i, mask in enumerate(masks):
            # Resize the float mask first for better interpolation
            mask_resized = cv2.resize(mask, (orig_w, orig_h), interpolation=cv2.INTER_LINEAR)
            # Then apply threshold
            mask_binary = (mask_resized > mask_threshold).astype(np.uint8)
            
            # Apply smoothing BEFORE filtering to ensure consistency with visualization
            mask_uint8 = (mask_binary * 255).astype(np.uint8)
            mask_uint8 = cv2.GaussianBlur(mask_uint8, (5, 5), 0)
            # Re-threshold after blur
            _, mask_uint8 = cv2.threshold(mask_uint8, 127, 255, cv2.THRESH_BINARY)
            mask_binary = (mask_uint8 > 0).astype(np.uint8)
            
            # Clip mask to its corresponding bounding box (SAM can generate masks outside box prompts)
            x1, y1, x2, y2 = boxes_np[i].astype(int)
            # Ensure bbox coordinates are within image bounds
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(orig_w, x2), min(orig_h, y2)
            
            # Create a mask of zeros and only keep the region inside the bbox
            clipped_mask = np.zeros_like(mask_binary)
            clipped_mask[y1:y2, x1:x2] = mask_binary[y1:y2, x1:x2]
            mask_binary = clipped_mask
            
            # Filter by minimum area AFTER smoothing and clipping
            mask_area = np.sum(mask_binary)
            if mask_area < min_mask_area:
                continue
            
            # Convert mask to contour and then to Shapely Polygon
            mask_uint8 = (mask_binary * 255).astype(np.uint8)
            # Expand mask if requested (dilate)
            if inspection_const.CONTOUR_EXPANSION > 0:
                kernel = np.ones((inspection_const.CONTOUR_EXPANSION, inspection_const.CONTOUR_EXPANSION), np.uint8)
                mask_uint8 = cv2.dilate(mask_uint8, kernel, iterations=1)
            
            # Use CHAIN_APPROX_NONE to preserve all contour points for maximum accuracy
            contours, _ = cv2.findContours(mask_uint8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)

            if len(contours) > 0:
                max_contour = max(contours, key=cv2.contourArea)
                # Convert OpenCV contour to Shapely Polygon
                # Contour shape is (N, 1, 2), reshape to (N, 2)
                contour_points = max_contour.reshape(-1, 2)
            
            else:
                continue
            
            contours_filtered.append(contour_points)
            labels_filtered.append(int(det['labels'][i]))
        
        
        return {
            'contours': contours_filtered,
            'labels': labels_filtered
        }
        