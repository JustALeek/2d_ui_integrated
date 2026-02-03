import cv2
import numpy as np
from tqdm import tqdm
import albumentations as A
from albumentations.pytorch import ToTensorV2
from scipy.ndimage import maximum_filter
import onnxruntime as ort
from config import inspection_const
from detection.point_detection.utils import get_slice_bboxes


class PointDetInference:
    def __init__(self):
        self.batch_size = inspection_const.BATCH_SIZE

        self.sess = ort.InferenceSession(
            inspection_const.POINT_DET_CKPT,
            providers=["CUDAExecutionProvider", "CPUExecutionProvider"]
        )

        self.inf_transform = A.Compose([
            A.Normalize(mean=(0.485, 0.456, 0.406),
                        std=(0.229, 0.224, 0.225)),
            ToTensorV2()
        ])

    def preprocess_image(self, img_bgr):
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        h, w = img_rgb.shape[:2]

        bboxes = get_slice_bboxes(
            h, w,
            inspection_const.SLICE_SIZE,
            inspection_const.SLICE_SIZE,
            inspection_const.OVERLAP_RATIO,
            inspection_const.OVERLAP_RATIO
        )

        return img_rgb, h, w, bboxes

    def get_local_maxima(self, heatmap):
        mask = heatmap > inspection_const.POINT_THRESHOLD
        local_max = maximum_filter(
            heatmap,
            size=inspection_const.NEIGHBOURHOOD_SIZE
        ) == heatmap
        peaks = local_max & mask
        y, x = np.where(peaks)
        return list(zip(x, y))

    def predict(self, img_bgr):
        img_rgb, h, w, bboxes = self.preprocess_image(img_bgr)

        full_heatmap = None
        count_map = np.zeros((h, w), dtype=np.float32)

        # -----------------------------
        # Batched slicing inference
        # -----------------------------
        for i in tqdm(range(0, len(bboxes), self.batch_size), desc="Slicing"):
            batch_boxes = bboxes[i:i + self.batch_size]
            batch_imgs = []

            for (x1, y1, x2, y2) in batch_boxes:
                slice_img = img_rgb[y1:y2, x1:x2]
                slice_resized = cv2.resize(
                    slice_img,
                    (inspection_const.RESIZE_DIM, inspection_const.RESIZE_DIM)
                )
                tensor = self.inf_transform(image=slice_resized)['image'].numpy()
                batch_imgs.append(tensor)

            batch_input = np.stack(batch_imgs, axis=0)  # (B,3,H,W)
            batch_pred = self.sess.run(None, {"image": batch_input})[0]  # (B,C,H,W)

            if full_heatmap is None:
                num_classes = batch_pred.shape[1]
                full_heatmap = np.zeros((num_classes, h, w), dtype=np.float32)

            for b, (x1, y1, x2, y2) in enumerate(batch_boxes):
                slice_h = y2 - y1
                slice_w = x2 - x1

                pred = batch_pred[b].transpose(1, 2, 0)  # (H,W,C)
                pred = cv2.resize(pred, (slice_w, slice_h))

                if num_classes == 1:
                    pred = pred[:, :, None]

                full_heatmap[:, y1:y2, x1:x2] += pred.transpose(2, 0, 1)
                count_map[y1:y2, x1:x2] += 1

        # -----------------------------
        # Normalize overlapping regions
        # -----------------------------
        full_heatmap = np.divide(
            full_heatmap,
            count_map,
            out=np.zeros_like(full_heatmap),
            where=count_map != 0
        )

        # -----------------------------
        # Extract points
        # -----------------------------
        class_points = {
            c: self.get_local_maxima(full_heatmap[c])
            for c in range(num_classes)
        }

        points = np.array(class_points[0]) if class_points[0] else np.empty((0, 2), dtype=int)
        inner  = np.array(class_points[1]) if num_classes > 1 and class_points[1] else np.empty((0, 2), dtype=int)

        points_set = set(map(tuple, points))
        inner_set  = set(map(tuple, inner))

        overlap = points_set & inner_set

        return {
            'points': np.array(list(points_set - overlap)) if points_set else np.empty((0, 2), dtype=int),
            'inner':  np.array(list(inner_set - overlap)) if inner_set else np.empty((0, 2), dtype=int),
            'overlap': np.array(list(overlap)) if overlap else np.empty((0, 2), dtype=int)
        }