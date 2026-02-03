"""
Detection losses and utilities for two-stage instance segmentation
"""

import torch
import torch.nn as nn
import torch.nn.functional as F


def decode_predictions(predictions, anchors, conf_threshold=0.5, nms_threshold=0.5, input_size=1024):
    """
    Decode detector predictions to bounding boxes.
    
    Args:
        predictions: List of predictions at different scales
            Each: (B, num_anchors, grid_h, grid_w, 5+num_classes)
        anchors: Dict mapping grid_size -> anchor boxes
        conf_threshold: Confidence threshold
        nms_threshold: NMS IoU threshold
        input_size: Input image size
        
    Returns:
        detections: List of dicts per batch with 'boxes', 'scores', 'labels'
    """
    device = predictions[0].device
    B = predictions[0].size(0)
    
    all_detections = []
    
    for b_idx in range(B):
        boxes_list = []
        scores_list = []
        labels_list = []
        
        for pred in predictions:
            grid_h, grid_w = pred.size(2), pred.size(3)
            num_anchors = pred.size(1)
            
            # Get anchor boxes for this scale
            anchor_boxes = anchors[grid_h].to(device) * grid_w
            
            # Extract predictions for this batch item
            pred_b = pred[b_idx]  # (num_anchors, grid_h, grid_w, 5+C)
            
            pred_xy = torch.sigmoid(pred_b[..., 0:2])
            pred_wh = pred_b[..., 2:4]
            pred_obj = torch.sigmoid(pred_b[..., 4:5])
            pred_cls = pred_b[..., 5:]
            
            # Calculate confidence scores
            if pred_cls.size(-1) > 1:
                class_probs = torch.softmax(pred_cls, dim=-1)
                class_scores, class_indices = class_probs.max(dim=-1)
            else:
                class_scores = torch.ones_like(pred_obj.squeeze(-1))
                class_indices = torch.zeros_like(pred_obj.squeeze(-1), dtype=torch.long)
            
            confidence = pred_obj.squeeze(-1) * class_scores
            
            # Filter by confidence
            mask = confidence > conf_threshold
            
            if mask.sum() == 0:
                continue
            
            # Get grid coordinates
            grid_y, grid_x = torch.meshgrid(
                torch.arange(grid_h, device=device),
                torch.arange(grid_w, device=device),
                indexing='ij'
            )
            grid_x = grid_x.unsqueeze(0).expand(num_anchors, -1, -1)
            grid_y = grid_y.unsqueeze(0).expand(num_anchors, -1, -1)
            
            # Decode boxes
            cx = (pred_xy[..., 0] + grid_x.float()) / grid_w
            cy = (pred_xy[..., 1] + grid_y.float()) / grid_h
            
            # Decode width and height
            anchor_w = anchor_boxes[:, 0].view(-1, 1, 1).expand(-1, grid_h, grid_w) / grid_w
            anchor_h = anchor_boxes[:, 1].view(-1, 1, 1).expand(-1, grid_h, grid_w) / grid_h
            
            w = anchor_w * torch.exp(pred_wh[..., 0])
            h = anchor_h * torch.exp(pred_wh[..., 1])
            
            # Convert to xyxy
            x1 = cx - w / 2
            y1 = cy - h / 2
            x2 = cx + w / 2
            y2 = cy + h / 2
            
            # Apply mask and collect
            boxes = torch.stack([x1[mask], y1[mask], x2[mask], y2[mask]], dim=1)
            scores = confidence[mask]
            labels = class_indices[mask]
            
            boxes_list.append(boxes)
            scores_list.append(scores)
            labels_list.append(labels)
        
        if len(boxes_list) == 0:
            all_detections.append({
                'boxes': torch.zeros(0, 4, device=device),
                'scores': torch.zeros(0, device=device),
                'labels': torch.zeros(0, dtype=torch.long, device=device)
            })
            continue
        
        # Concatenate all scales
        boxes = torch.cat(boxes_list, dim=0)
        scores = torch.cat(scores_list, dim=0)
        labels = torch.cat(labels_list, dim=0)
        
        # Apply NMS
        keep = nms(boxes, scores, nms_threshold)
        
        all_detections.append({
            'boxes': boxes[keep],
            'scores': scores[keep],
            'labels': labels[keep]
        })
    
    return all_detections


def nms(boxes, scores, iou_threshold):
    """Non-Maximum Suppression."""
    if len(boxes) == 0:
        return torch.zeros(0, dtype=torch.long)
    
    # Sort by score
    order = torch.argsort(scores, descending=True)
    keep = []
    
    while len(order) > 0:
        i = order[0]
        keep.append(i)
        
        if len(order) == 1:
            break
        
        # Compute IoU with remaining boxes
        ious = box_iou(boxes[i:i+1], boxes[order[1:]])
        
        # Keep boxes with IoU less than threshold
        inds = torch.where(ious[0] <= iou_threshold)[0]
        order = order[inds + 1]
    
    return torch.tensor(keep, dtype=torch.long, device=boxes.device)


def box_iou(boxes1, boxes2):
    """Compute IoU between two sets of boxes."""
    area1 = (boxes1[:, 2] - boxes1[:, 0]) * (boxes1[:, 3] - boxes1[:, 1])
    area2 = (boxes2[:, 2] - boxes2[:, 0]) * (boxes2[:, 3] - boxes2[:, 1])
    
    lt = torch.max(boxes1[:, None, :2], boxes2[:, :2])
    rb = torch.min(boxes1[:, None, 2:], boxes2[:, 2:])
    
    wh = (rb - lt).clamp(min=0)
    inter = wh[:, :, 0] * wh[:, :, 1]
    
    union = area1[:, None] + area2 - inter
    iou = inter / (union + 1e-6)
    
    return iou
