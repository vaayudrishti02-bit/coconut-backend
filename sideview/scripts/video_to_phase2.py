"""Pipeline: Video segmentation -> transfer model prediction

Usage:
    python video_to_phase2.py --video path/to/video.mp4 \
        --phase2 path/to/plant_disease_transfer_model.h5 --output results.json

This script runs the existing VideoSegmenter to produce per-frame crops
and then runs the TransferModelPredictor (Keras MobileNetV2 transfer model)
on each `*_full.png` crop. Predictions are saved to an aggregated JSON
file in the video result folder, ready for dashboard/report generation.
"""
import argparse
import json
import os
from pathlib import Path

import importlib.util
import importlib.machinery
import sys

# Load VideoSegmenter from local predict_video.py (file-based import so script
# works when executed directly without installing the `Sam` package)
pv_path = Path(__file__).parent / "predict_video.py"
spec = importlib.util.spec_from_file_location("predict_video_mod", str(pv_path))
pv_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pv_mod)
VideoSegmenter = pv_mod.VideoSegmenter

# Ensure project root (containing test_transfer_model.py) is on sys.path
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from test_transfer_model import TransferModelPredictor


def run_pipeline(video_path, phase2_model, frame_interval=0, debug=False, output_json=None):
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    # 1) Run video segmentation
    seg = VideoSegmenter(model_path=None, debug=debug)
    print(f"Running segmentation on {video_path} ...")
    seg_result = seg.predict(str(video_path), frame_interval=frame_interval)

    output_dir = Path(seg_result.get('output_dir', '.'))

    # 2) Load transfer model predictor
    print(f"Loading transfer model: {phase2_model}")
    predictor = TransferModelPredictor(model_path=str(phase2_model))

    predictions = []

    # 3) Iterate extracted frames and predict on full crops
    for frame_res in seg_result.get('extracted_frames', []):
        frame_idx = frame_res.get('frame_index')
        full_files = frame_res.get('full_files', {})
        # full_files is a dict mapping class_name -> list of file paths
        for cls, files in full_files.items():
            for fpath in files:
                try:
                    # Normalize segmentation class to match dashboard expected keys
                    norm_part = cls
                    if cls == 'leaf':
                        norm_part = 'leaves'

                    print(f"Predicting frame {frame_idx} {cls}: {fpath}")
                    # Force part to segmentation class (normalized)
                    pred = predictor.predict(fpath, forced_part=norm_part)
                    predictions.append({
                        'frame_index': frame_idx,
                        'class': cls,
                        'file': fpath,
                        'prediction': pred
                    })
                except Exception as e:
                    print(f"  ❌ Prediction failed for {fpath}: {e}")

    # 4) Save aggregated predictions
    if output_json is None:
        output_json = output_dir / 'phase2_predictions.json'
    else:
        output_json = Path(output_json)

    with open(output_json, 'w') as f:
        json.dump({'video': str(video_path), 'segmentation_result': seg_result, 'predictions': predictions}, f, indent=2)

    print(f"✅ Phase2 predictions saved: {output_json}")
    return output_json


def main():
    parser = argparse.ArgumentParser(description='Run video -> transfer-model prediction pipeline')
    parser.add_argument('--video', required=True, help='Path to video file')
    # Default to the transfer model at the project root (one level above scripts/)
    default_phase2 = Path(__file__).resolve().parents[1] / "plant_disease_transfer_model.h5"
    parser.add_argument('--phase2', default=str(default_phase2), help='Path to transfer model (.h5)')
    parser.add_argument('--frame-interval', type=int, default=0, help='Frame interval to process (0 = auto)')
    parser.add_argument('--debug', action='store_true', help='Enable debug in video segmentation')
    parser.add_argument('--output', help='Optional output JSON path')

    args = parser.parse_args()

    run_pipeline(args.video, args.phase2, frame_interval=args.frame_interval, debug=args.debug, output_json=args.output)


if __name__ == '__main__':
    main()
