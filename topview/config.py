import os

# YOLO Model Location
MODEL_DIR = os.path.join(os.path.dirname(__file__), "api", "models")
MODEL_NAME = "final_best.pt"
MODEL_PATH = os.path.join(MODEL_DIR, MODEL_NAME)

# YOLO settings (optional)
CONFIDENCE_THRESHOLD = 0.40
IOU_THRESHOLD = 0.45

# Minimum detected tree area as fraction of image area (friend logic used 0.018)
MIN_TREE_AREA_RATIO = 0.018

# Vertical grouping tolerance in pixels (friend logic used 150)
ROW_TOLERANCE = 150

IMGSZ = 640
