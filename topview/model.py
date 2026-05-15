import cv2
import numpy as np
from ultralytics import YOLO

from topview.config import (
    MODEL_PATH,
    CONFIDENCE_THRESHOLD,
    IOU_THRESHOLD,
    MIN_TREE_AREA_RATIO,
    ROW_TOLERANCE
)

from topview.utils import compute_iou


class TopViewModel:

    def __init__(self, model_path=MODEL_PATH):
        self.model = YOLO(model_path)

    def detect_trees(self, img):

        H, W = img.shape[:2]

        results = self.model.predict(
            source=img,
            conf=CONFIDENCE_THRESHOLD,
            iou=IOU_THRESHOLD,
            verbose=False
        )[0]

        boxes = results.boxes.xyxy.cpu().numpy()
        scores = results.boxes.conf.cpu().numpy()

        filtered = []

        for (x1, y1, x2, y2), sc in zip(boxes, scores):

            w, h = x2 - x1, y2 - y1
            area = w * h

            if area < MIN_TREE_AREA_RATIO * (H * W):
                continue

            if w < 120 or h < 120:
                continue

            ratio = w / h
            if ratio < 0.45 or ratio > 1.80:
                continue

            filtered.append((float(x1), float(y1), float(x2), float(y2)))

        cleaned = []
        for box in filtered:
            if all(compute_iou(box, kept) <= 0.40 for kept in cleaned):
                cleaned.append(box)

        rows = []
        for box in cleaned:
            x1, y1, x2, y2 = box
            cy = (y1 + y2) / 2
            placed = False

            for r in rows:
                if abs(r["cy"] - cy) < ROW_TOLERANCE:
                    r["items"].append(box)
                    placed = True
                    break

            if not placed:
                rows.append({"cy": cy, "items": [box]})

        rows = sorted(rows, key=lambda r: r["cy"])

        ordered = []
        for r in rows:
            ordered.extend(sorted(r["items"], key=lambda b: (b[0] + b[2]) / 2))

        detections = []
        for idx, (x1, y1, x2, y2) in enumerate(ordered, 1):
            cx = int((x1 + x2) / 2)
            cy = int((y1 + y2) / 2)

            detections.append({
                "id": idx,
                "bbox": [float(x1), float(y1), float(x2), float(y2)],
                "centroid": [cx, cy]
            })

        return detections
