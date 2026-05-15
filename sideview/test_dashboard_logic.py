"""Lightweight checks for label→disease mapping and dashboard aggregation.

Run with:
    python test_dashboard_logic.py

Raises AssertionError if something is inconsistent.
"""
from pathlib import Path
import json

from test_transfer_model import TransferModelPredictor
from scripts.aggregate_dashboard import aggregate_dashboard, VALID_DISEASES_BY_PART


def test_label_to_disease_mapping():
    root = Path(__file__).parent
    labels_path = root / "labels.json"
    labels = json.loads(labels_path.read_text(encoding="utf-8"))

    # Instantiate predictor just to access _label_to_status
    predictor = TransferModelPredictor(
        model_path=str(root / "plant_disease_transfer_model.h5"),
        labels_path=str(labels_path),
    )

    for idx_str, label in labels.items():
        # Infer part from label prefix (bud_, leaves_, stem_)
        if "_" not in label:
            continue
        part_prefix, _ = label.split("_", 1)
        if part_prefix not in {"bud", "leaves", "stem"}:
            continue

        disease = predictor._label_to_status(label)

        # Healthy labels must map to "healthy" (and be allowed for the part)
        if label.endswith("_healthy"):
            assert disease == "healthy", f"{label} should map to 'healthy', got {disease}"
            assert "healthy" in VALID_DISEASES_BY_PART[part_prefix], (
                f"'healthy' missing from VALID_DISEASES_BY_PART for {part_prefix}"
            )
        else:
            # Non-healthy labels must be allowed for that part
            assert disease in VALID_DISEASES_BY_PART[part_prefix], (
                f"Disease '{disease}' (from {label}) not allowed for part {part_prefix}"
            )


def test_dashboard_aggregation_minimal():
    """Sanity-check aggregate_dashboard on a tiny synthetic set."""
    preds = [
        # Two healthy stem frames
        {
            "frame_index": 0,
            "class": "stem",
            "image_path": "stem0.png",
            "part": {"prediction": "stem", "confidence": 90.0},
            "status": {"prediction": "healthy", "confidence": 90.0},
            "health": "healthy",
            "combined": "stem_healthy",
            "is_out_of_distribution": False,
            "ood_reason": None,
            "ood_signals": None,
            "reliability": 90.0,
        },
        {
            "frame_index": 1,
            "class": "stem",
            "image_path": "stem1.png",
            "part": {"prediction": "stem", "confidence": 80.0},
            "status": {"prediction": "healthy", "confidence": 80.0},
            "health": "healthy",
            "combined": "stem_healthy",
            "is_out_of_distribution": False,
            "ood_reason": None,
            "ood_signals": None,
            "reliability": 80.0,
        },
        # One diseased leaves frame
        {
            "frame_index": 2,
            "class": "leaves",
            "image_path": "leaf2.png",
            "part": {"prediction": "leaves", "confidence": 85.0},
            "status": {"prediction": "Grey leaf rot", "confidence": 85.0},
            "health": "unhealthy",
            "combined": "leaves_Grey_leaf_rot",
            "is_out_of_distribution": False,
            "ood_reason": None,
            "ood_signals": None,
            "reliability": 85.0,
        },
    ]

    dashboard = aggregate_dashboard(preds)

    # Tree should be unhealthy because we have an unhealthy leaves frame
    assert dashboard["tree"]["health"] == "unhealthy"

    # Stem part should be healthy, leaves unhealthy
    assert dashboard["parts"]["stem"]["health"] == "healthy"
    assert dashboard["parts"]["leaves"]["health"] == "unhealthy"

    # Primary disease should be Grey leaf rot
    assert dashboard["tree"]["primary_disease"] == "Grey leaf rot"


if __name__ == "__main__":
    test_label_to_disease_mapping()
    test_dashboard_aggregation_minimal()
    print("All dashboard/label mapping checks passed.")
