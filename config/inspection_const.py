#######################################
# POINT DETECTION

POINT_DET_CKPT = "./checkpoints/point_det_best.onnx"
SLICE_SIZE = 256
OVERLAP_RATIO = 0.2
RESIZE_DIM = 512
BATCH_SIZE = 16

POINT_THRESHOLD = 0.5
NEIGHBOURHOOD_SIZE = 5
MATCH_DIST = 5


#######################################
# SEGMENTATION 

MOBILESAM_CKPT = "./checkpoints/mobile_sam.pt"
DETECTOR_CKPT = "./checkpoints/seg_detector_best.pth"
SAM_CKPT = "./checkpoints/sam_best.pth"

NUM_CLASSES = 6

LORA_CONFIG = {
    'r': 8,
    'lora_alpha': 16,
    'target_modules': ["qkv"],
    'lora_dropout': 0.1,
    'bias': "none"
}

NUM_ANCHORS = 3

ANCHORS_64 = [[0.1, 0.1], [0.2, 0.2], [0.4, 0.4]]
ANCHORS_128 = [[0.05, 0.05], [0.1, 0.1], [0.2, 0.2]]

TARGET_SIZE = 1024

CONF_THRESHOLD = 0.9
NMS_THRESHOLD = 0.5
MASK_THRESHOLD = 0.7
MIN_MASK_AREA = 1000
CONTOUR_EXPANSION=5