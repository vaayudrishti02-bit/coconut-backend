import os
from topview.config import MODEL_PATH

def get_model_path():
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(f"TopView YOLO model not found: {MODEL_PATH}")
    return MODEL_PATH
