"""
Two-Stage Instance Segmentation Model
Detector + MobileSAM with Box Prompts

Architecture:
1. Shared MobileSAM encoder (with LoRA)
2. Lightweight detection head for instance proposals
3. MobileSAM prompt encoder + mask decoder for precise masks
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from mobile_sam import sam_model_registry
from peft import LoraConfig, get_peft_model


class LightweightDetectionHead(nn.Module):
    """
    Custom lightweight detection head (YOLO-inspired, no license issues).
    Predicts bounding boxes, objectness, and classes at multiple scales.
    """
    
    def __init__(self, in_channels=256, num_classes=80, num_anchors=3):
        super().__init__()
        
        self.num_classes = num_classes
        self.num_anchors = num_anchors
        
        # Predictions per anchor: (x, y, w, h, objectness, class_scores)
        self.pred_per_anchor = 5 + num_classes
        
        # Multi-scale feature pyramid
        # Upsample 64x64 features to get 128x128 and keep 64x64
        self.upsample = nn.Sequential(
            nn.ConvTranspose2d(in_channels, 128, kernel_size=2, stride=2),
            nn.BatchNorm2d(128),
            nn.ReLU(inplace=True)
        )
        
        # Detection heads for two scales
        self.det_head_large = self._make_detection_head(128, self.pred_per_anchor * num_anchors)  # 128x128
        self.det_head_small = self._make_detection_head(in_channels, self.pred_per_anchor * num_anchors)  # 64x64
        
        # Initialize weights
        self._initialize_weights()
    
    def _make_detection_head(self, in_channels, out_channels):
        """Create a detection head with conv layers."""
        return nn.Sequential(
            nn.Conv2d(in_channels, in_channels, kernel_size=3, padding=1),
            nn.BatchNorm2d(in_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(in_channels, in_channels // 2, kernel_size=3, padding=1),
            nn.BatchNorm2d(in_channels // 2),
            nn.ReLU(inplace=True),
            nn.Conv2d(in_channels // 2, out_channels, kernel_size=1)
        )
    
    def _initialize_weights(self):
        """Initialize detection head weights."""
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')
                if m.bias is not None:
                    nn.init.constant_(m.bias, 0)
            elif isinstance(m, nn.BatchNorm2d):
                nn.init.constant_(m.weight, 1)
                nn.init.constant_(m.bias, 0)
    
    def forward(self, features):
        """
        Args:
            features: (B, 256, 64, 64) from encoder
            
        Returns:
            predictions: List of predictions at different scales
                Each: (B, num_anchors, grid_h, grid_w, 5+num_classes)
        """
        # Scale 1: 64x64 (small objects)
        pred_small = self.det_head_small(features)  # (B, num_anchors*(5+C), 64, 64)
        pred_small = self._reshape_predictions(pred_small, grid_size=64)
        
        # Scale 2: 128x128 (large objects)
        features_up = self.upsample(features)  # (B, 128, 128, 128)
        pred_large = self.det_head_large(features_up)  # (B, num_anchors*(5+C), 128, 128)
        pred_large = self._reshape_predictions(pred_large, grid_size=128)
        
        return [pred_small, pred_large]
    
    def _reshape_predictions(self, pred, grid_size):
        """Reshape predictions to (B, num_anchors, H, W, 5+C)."""
        B = pred.size(0)
        pred = pred.view(B, self.num_anchors, self.pred_per_anchor, grid_size, grid_size)
        pred = pred.permute(0, 1, 3, 4, 2).contiguous()  # (B, num_anchors, H, W, 5+C)
        return pred


class TwoStageInstanceSeg(nn.Module):
    """
    Two-stage instance segmentation model.
    
    Stage 1: Detector identifies instance bounding boxes
    Stage 2: MobileSAM generates precise masks for each box
    """
    
    def __init__(self, mobilesam_ckpt, num_classes, lora_config, num_anchors=3, detector_only=False):
        super().__init__()
        
        self.num_classes = num_classes
        self.num_anchors = num_anchors
        self.detector_only = detector_only
        
        # Load MobileSAM
        sam = sam_model_registry["vit_t"](checkpoint=mobilesam_ckpt)
        
        # Freeze SAM initially
        for p in sam.parameters():
            p.requires_grad = False
        
        # Apply LoRA to image encoder
        lora_cfg = LoraConfig(
            r=lora_config['r'],
            lora_alpha=lora_config['lora_alpha'],
            target_modules=lora_config['target_modules'],
            lora_dropout=lora_config['lora_dropout'],
            bias=lora_config['bias']
        )
        sam.image_encoder = get_peft_model(sam.image_encoder, lora_cfg)
        
        self.sam = sam
        
        # Lightweight detection head
        self.detector = LightweightDetectionHead(
            in_channels=256,
            num_classes=num_classes,
            num_anchors=num_anchors
        )
        
        # Anchor boxes for different scales (relative to grid cell)
        # Format: (w, h) relative to grid cell
        self.anchors = {
            64: torch.tensor([[0.1, 0.1], [0.2, 0.2], [0.4, 0.4]]),  # Small objects
            128: torch.tensor([[0.05, 0.05], [0.1, 0.1], [0.2, 0.2]])  # Large objects
        }
    
    def forward(self, images, boxes=None, mode='detector'):
        """
        Forward pass with different modes.
        
        Args:
            images: (B, 3, 1024, 1024)
            boxes: Optional box prompts for SAM mode (B, N, 4) in xyxy format
            mode: 'detector' or 'sam' or 'full'
                - 'detector': Only run detector head
                - 'sam': Run SAM with provided box prompts
                - 'full': Run both (detector -> SAM)
                
        Returns:
            If mode == 'detector':
                predictions: List of detection predictions at multiple scales
            If mode == 'sam':
                masks: (B, N, H, W) instance masks for provided boxes
            If mode == 'full':
                detections: Detection results
                masks: Instance masks for detected boxes
        """
        B = images.size(0)
        
        # Encode image
        features = self.sam.image_encoder(images)  # (B, 256, 64, 64)
        
        if mode == 'detector' or mode == 'full':
            # Run detector
            det_predictions = self.detector(features)
            
            if mode == 'detector':
                return det_predictions
        
        if mode == 'sam' or mode == 'full':
            if mode == 'sam' and boxes is None:
                raise ValueError("boxes must be provided in 'sam' mode")
            
            # Get boxes from detector if in full mode
            if mode == 'full':
                boxes = self._postprocess_detections(det_predictions, conf_threshold=0.5)
            
            # Run SAM for each box
            masks = self._segment_boxes(images, boxes, features)
            
            if mode == 'full':
                return {'detections': det_predictions, 'boxes': boxes, 'masks': masks}
            else:
                return masks
        
        return det_predictions
    
    def _segment_boxes(self, images, boxes, features=None):
        """
        Segment instances using MobileSAM with box prompts.
        
        Args:
            images: (B, 3, 1024, 1024)
            boxes: List of tensors, each (N, 4) in xyxy format normalized [0,1], or (B, N, 4)
            features: Pre-computed encoder features (optional)
            
        Returns:
            masks: List of (N, H, W) masks per batch item
        """
        if features is None:
            features = self.sam.image_encoder(images)
        
        all_masks = []
        
        # Handle different box formats
        if isinstance(boxes, torch.Tensor) and boxes.ndim == 3:
            # (B, N, 4) format
            boxes_list = [boxes[i] for i in range(boxes.size(0))]
        else:
            boxes_list = boxes
        
        for b_idx, b_boxes in enumerate(boxes_list):
            if len(b_boxes) == 0:
                # No boxes, return empty mask
                all_masks.append(torch.zeros(0, images.size(2), images.size(3), device=images.device))
                continue
            
            # Convert normalized boxes [0,1] to pixel coordinates
            # SAM expects boxes in pixel coordinates matching input image size
            img_size = images.size(2)  # Assuming square images
            boxes_pixel = b_boxes * img_size  # (N, 4) in pixel coords
            
            # Process each box individually (SAM processes one prompt at a time)
            batch_masks = []
            for box in boxes_pixel:
                # Reshape to (1, 1, 4) for prompt encoder
                box_prompt = box.unsqueeze(0).unsqueeze(0)  # (1, 1, 4)
                
                # Get image embedding for this batch item
                image_embedding = features[b_idx:b_idx+1]  # (1, 256, 64, 64)
                
                # Encode prompts
                sparse_embeddings, dense_embeddings = self.sam.prompt_encoder(
                    points=None,
                    boxes=box_prompt,
                    masks=None,
                )
                
                # Decode mask
                low_res_masks, iou_predictions = self.sam.mask_decoder(
                    image_embeddings=image_embedding,
                    image_pe=self.sam.prompt_encoder.get_dense_pe(),
                    sparse_prompt_embeddings=sparse_embeddings,
                    dense_prompt_embeddings=dense_embeddings,
                    multimask_output=False,
                )
                
                # Upsample mask to original resolution
                mask = F.interpolate(
                    low_res_masks,
                    (images.size(2), images.size(3)),
                    mode="bilinear",
                    align_corners=False,
                )
                
                batch_masks.append(mask.squeeze(0).squeeze(0))  # Remove batch and channel dims
            
            # Stack all masks for this batch item
            if len(batch_masks) > 0:
                batch_masks = torch.stack(batch_masks, dim=0)  # (N, H, W)
            else:
                batch_masks = torch.zeros(0, images.size(2), images.size(3), device=images.device)
            
            all_masks.append(batch_masks)
        
        return all_masks
    
    def _postprocess_detections(self, predictions, conf_threshold=0.5, nms_threshold=0.5):
        """
        Post-process detector predictions to get final boxes.
        
        Args:
            predictions: List of predictions at multiple scales
            conf_threshold: Confidence threshold
            nms_threshold: NMS IoU threshold
            
        Returns:
            boxes: List of (N, 4) tensors in xyxy format for each batch
        """
        # This is a placeholder - will implement proper NMS
        # For now, return empty boxes
        batch_size = predictions[0].size(0)
        return [torch.zeros(0, 4, device=predictions[0].device) for _ in range(batch_size)]
