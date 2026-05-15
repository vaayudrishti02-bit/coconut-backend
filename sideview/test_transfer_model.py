import os
import sys
import json

import numpy as np
import tensorflow as tf
from tensorflow.keras.applications import MobileNetV2
from tensorflow.keras import layers, models
from tensorflow.keras.preprocessing import image


def load_labels(labels_path: str):
    with open(labels_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    # keys are strings of indices; convert to int
    return {int(k): v for k, v in data.items()}


def build_model(num_classes: int):
    base_model = MobileNetV2(
        input_shape=(224, 224, 3),
        include_top=False,
        weights="imagenet",
    )
    base_model.trainable = False

    model = models.Sequential(
        [
            base_model,
            layers.GlobalAveragePooling2D(),
            layers.Dense(256, activation="relu"),
            layers.Dropout(0.4),
            layers.Dense(128, activation="relu"),
            layers.Dropout(0.3),
            layers.Dense(num_classes, activation="softmax"),
        ]
    )
    return model


# Indices that correspond to healthy classes
HEALTHY_INDICES = {2, 5, 7}

# Allowed disease names per part for sanity filtering when a trusted
# part (from segmentation) is provided. These names mirror
# VALID_DISEASES_BY_PART in scripts/aggregate_dashboard.py.
ALLOWED_DISEASES_BY_PART = {
    "bud": {"bud root dropping", "bud rot", "healthy"},
    "leaves": {"leaf rot", "Grey leaf rot", "Whitefly", "healthy"},
    "stem": {"stem bleeding", "healthy"},
}


class TransferModelPredictor:
    """Reusable predictor that wraps the transfer model for image-level inference.

    This is used both by the CLI in this file and by the
    video pipeline (scripts/video_to_phase2.py).
    """

    def __init__(self, model_path: str = None, labels_path: str = None):
        script_dir = os.path.dirname(os.path.abspath(__file__))

        if model_path is None:
            model_path = os.path.join(script_dir, "plant_disease_transfer_model.h5")
        if labels_path is None:
            labels_path = os.path.join(script_dir, "labels.json")

        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found at {model_path}")
        if not os.path.exists(labels_path):
            raise FileNotFoundError(f"Labels file not found at {labels_path}")

        self.model_path = model_path
        self.labels_path = labels_path

        # Load labels and build the model once
        self.index_to_class = load_labels(labels_path)
        num_classes = len(self.index_to_class)

        self.model = build_model(num_classes)
        self.model.load_weights(model_path)

    @staticmethod
    def _index_to_part(predicted_index: int, label: str) -> str:
        """Map class index or label string to anatomical part name."""
        # Prefer explicit index ranges (matches original CLI logic)
        if predicted_index in {0, 1, 2}:
            return "bud"
        if predicted_index in {3, 4, 5, 6}:
            return "leaves"
        if predicted_index in {7, 8}:
            return "stem"

        # Fallback: infer from label prefix if possible
        if "_" in label:
            prefix = label.split("_", 1)[0]
            if prefix in {"bud", "leaves", "stem"}:
                return prefix

        return "unknown"

    @staticmethod
    def _label_to_status(label: str) -> str:
        """Convert label string (e.g. 'leaves_Grey_leaf_rot') to disease/health name.

        This produces names compatible with VALID_DISEASES_BY_PART in
        scripts/aggregate_dashboard.py (e.g. 'Grey leaf rot', 'bud rot').
        """
        if "_" not in label:
            return label

        _, rest = label.split("_", 1)
        if rest == "healthy":
            return "healthy"
        # Convert underscores to spaces: 'Grey_leaf_rot' -> 'Grey leaf rot'
        return rest.replace("_", " ")

    def predict(self, img_path: str, forced_part: str | None = None) -> dict:
        """Run the transfer model on a single image path.

        Returns a dict shaped for the phase2 / dashboard pipeline, with keys:
        - predicted_index, predicted_label
        - top2: list of top-2 predictions with confidences
        - status: {prediction, confidence}
        - part: {prediction, confidence}
        - health: 'healthy' | 'unhealthy'
        - combined: label string
        - reliability: confidence (0-100)
        - is_out_of_distribution: False (no OOD detection here)
        """
        if not os.path.exists(img_path):
            raise FileNotFoundError(f"Image not found at {img_path}")

        # Load and preprocess image
        img = image.load_img(img_path, target_size=(224, 224))
        img_array = image.img_to_array(img) / 255.0
        img_array = np.expand_dims(img_array, axis=0)

        # Predict probabilities
        probs = self.model.predict(img_array, verbose=0)[0]

        predicted_index = int(np.argmax(probs))
        predicted_label = self.index_to_class.get(predicted_index, str(predicted_index))
        confidence = float(np.max(probs) * 100.0)

        # Top-2 predictions for debugging / CLI output
        top_indices = probs.argsort()[-2:][::-1]
        top2 = [
            {
                "index": int(i),
                "label": self.index_to_class.get(int(i), str(i)),
                "confidence": float(probs[i] * 100.0),
            }
            for i in top_indices
        ]

        # Map to part first
        inferred_part = self._index_to_part(predicted_index, predicted_label)
        # If caller provides a trusted part (e.g. from segmentation), override
        part_name = forced_part or inferred_part

        # Initial health from class index
        health_status = "healthy" if predicted_index in HEALTHY_INDICES else "unhealthy"

        # Disease / status string compatible with dashboard expectations
        disease_name = self._label_to_status(predicted_label)

        # If we know the true part (from segmentation), and the disease name
        # is not valid for that part, mark it as Unknown so it won't be counted.
        if forced_part is not None:
            allowed = ALLOWED_DISEASES_BY_PART.get(part_name)
            if allowed and disease_name not in allowed:
                disease_name = "Unknown"
                health_status = "unknown"

        return {
            "predicted_index": predicted_index,
            "predicted_label": predicted_label,
            "top2": top2,
            "status": {
                "prediction": disease_name,
                "confidence": confidence,
            },
            "part": {
                "prediction": part_name,
                "confidence": confidence,
            },
            "health": health_status,
            "combined": predicted_label,
            "reliability": confidence,
            "is_out_of_distribution": False,
        }


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Test the transfer model on a single image.",
        epilog="Example: python test_transfer_model.py image.png --forced_part leaves"
    )
    parser.add_argument("image", help="Path to the image file")
    parser.add_argument(
        "--forced_part",
        choices=["bud", "leaves", "stem"],
        help="Force the part name (from segmentation) to override classifier's part inference and enforce disease compatibility"
    )
    args = parser.parse_args()

    img_path = args.image
    if not os.path.exists(img_path):
        print(f"Error: Image not found at {img_path}")
        sys.exit(1)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    model_path = os.path.join(script_dir, "plant_disease_transfer_model.h5")
    labels_path = os.path.join(script_dir, "labels.json")

    try:
        predictor = TransferModelPredictor(model_path=model_path, labels_path=labels_path)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    print(f"Loading model from {model_path} ...")
    print("Model loaded successfully!\n")

    result = predictor.predict(img_path, forced_part=args.forced_part)

    print("Top-2 predictions (raw classifier output):")
    for item in result.get("top2", []):
        print(f"  {item['label']}: {item['confidence']:.2f}%")

    part_name = result.get("part", {}).get("prediction", "unknown")
    predicted_status = result.get("status", {}).get("prediction", "unknown")
    confidence = result.get("reliability", 0.0)
    health_status = result.get("health", "unknown")

    print(f"\nPart: {part_name}")
    if args.forced_part:
        print(f"  (forced from segmentation: {args.forced_part})")

    print(f"\nFinal Status: {predicted_status}")
    print(f"Confidence: {confidence:.2f}%")
    print(f"Health: {health_status}")


if __name__ == "__main__":
    main()
