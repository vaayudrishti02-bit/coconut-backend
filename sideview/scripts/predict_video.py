"""
Coconut Tree Segmentation - VIDEO Processing (v2.0)
====================================================
Smart segmentation that selects the MAIN FOCUSED TREE only, with temporal tracking.

Algorithm:
    1. Run segmentation model on each frame
    2. Score stem candidates: area, center proximity, verticality, bottom reach, connected leaves
    3. Pick highest scoring stem (with temporal smoothing)
    4. Keep only leaves/buds connected to the main stem's crown zone
    5. Track main stem across frames using IoU linking + smoothing

Features:
    - Frame-by-frame smart filtering
    - Temporal smoothing to prevent flicker
    - IoU-based stem tracking across frames
    - Debug mode with frame-by-frame stats

Usage:
    python predict_video.py --video "path/to/video.mp4"
    python predict_video.py --video "path/to/video.mp4" --debug
    python predict_video.py --folder "path/to/folder"
    python predict_video.py --video video.mp4 --frame-interval 5
"""

import os
import cv2
import json
import numpy as np
import torch
from pathlib import Path
from datetime import datetime
import argparse
from PIL import Image
from tqdm import tqdm
import sys

# Ensure local scripts dir is on sys.path so local imports work when executed from repo root
scripts_dir = Path(__file__).parent
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))

try:
    import segmentation_models_pytorch as smp
except ImportError:
    print("⚠️ segmentation-models-pytorch not found. Attempting to install...")
    try:
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "segmentation-models-pytorch"])
        import segmentation_models_pytorch as smp
        print("✅ Installed segmentation-models-pytorch")
    except Exception as e:
        print(f"❌ Failed to install segmentation-models-pytorch: {e}")
        print("Please install it manually: pip install segmentation-models-pytorch")
        sys.exit(1)

# Import the postprocessing utilities (shared with image/)
from postprocess_utils import (
    smart_postprocess,
    connected_components_props,
    compute_stem_scores,
    StemTracker,
    PARAMS
)


# ============ CONFIGURATION ============
# Adjust BASE_DIR so that Combined/video/model is used when running from Combined
BASE_DIR = Path(__file__).resolve().parents[1]
MODEL_DIR = BASE_DIR / "model"
RESULTS_DIR = BASE_DIR / "results"

IMG_SIZE = 512
NUM_CLASSES = 4

# Image quality settings
PNG_COMPRESSION = 0  # Lossless

# Video settings
VIDEO_FPS = None  # None = use original FPS
DEFAULT_FRAME_INTERVAL = 1  # 1 = every frame

# Supported formats
VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm'}

# Class configuration
CLASSES = {
    0: {"name": "background", "color": (0, 0, 0, 0), "color_bgr": (0, 0, 0)},
    1: {"name": "bud", "color": (0, 255, 0, 255), "color_bgr": (0, 255, 0)},
    2: {"name": "leaf", "color": (255, 0, 0, 255), "color_bgr": (0, 0, 255)},
    3: {"name": "stem", "color": (0, 0, 255, 255), "color_bgr": (255, 0, 0)},
}

# Video tracking parameters
VIDEO_TRACKING_PARAMS = {
    'SMOOTH_ALPHA': 0.4,          # EMA smoothing factor for bbox
    'IOU_THRESH': 0.3,            # IoU threshold for track matching
    'MIN_CONSISTENT_FRAMES': 3,   # Frames before new track is stable
    'MAX_MISSING_FRAMES': 5,      # Frames before track is lost
}


class VideoSegmenter:
    """Segmentation pipeline for coconut tree videos with smart postprocessing and tracking"""
    
    def __init__(self, model_path=None, debug=False):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.debug = debug
        print(f"🔧 Device: {self.device}")
        
        # Load model
        if model_path is None:
            model_path = MODEL_DIR / "coconut_best_dice.pth"
        
        self.model = self._load_model(model_path)
        print(f"✅ Model loaded: {model_path.name}")
        
        # Create output directory
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        
        # Initialize stem tracker (reset per video)
        self.tracker = None
    
    def _load_model(self, model_path):
        """Load the trained UNet++ model"""
        model = smp.UnetPlusPlus(
            encoder_name="efficientnet-b3",
            encoder_weights=None,
            in_channels=3,
            classes=NUM_CLASSES,
        )
        
        checkpoint = torch.load(model_path, map_location=self.device, weights_only=False)
        if 'model_state_dict' in checkpoint:
            model.load_state_dict(checkpoint['model_state_dict'])
            print(f"📊 Model mIoU: {checkpoint.get('miou', 'N/A'):.4f}")
        else:
            model.load_state_dict(checkpoint)
        
        model = model.to(self.device)
        model.eval()
        return model
    
    def _inference(self, img_rgb):
        """Run model inference on single frame"""
        orig_h, orig_w = img_rgb.shape[:2]
        
        # Preprocess
        resized = cv2.resize(img_rgb, (IMG_SIZE, IMG_SIZE))
        tensor = torch.from_numpy(resized).permute(2, 0, 1).float().unsqueeze(0) / 255.0
        tensor = tensor.to(self.device)
        
        # Predict
        with torch.no_grad():
            logits = self.model(tensor)
            pred = logits.argmax(dim=1).cpu().numpy()[0]
        
        # Resize to original size
        pred = cv2.resize(pred.astype(np.uint8), (orig_w, orig_h), 
                         interpolation=cv2.INTER_NEAREST)
        
        return pred
    
    def _get_main_stem_bbox(self, pred_mask, img_shape):
        """Extract bounding box of the main stem from filtered prediction."""
        stem_mask = (pred_mask == 3).astype(np.uint8)
        if stem_mask.sum() == 0:
            return None
        
        coords = np.where(stem_mask > 0)
        if len(coords[0]) == 0:
            return None
        
        ymin, ymax = coords[0].min(), coords[0].max()
        xmin, xmax = coords[1].min(), coords[1].max()
        
        return (xmin, ymin, xmax, ymax)
    
    def predict(self, video_path, output_dir=None, frame_interval=DEFAULT_FRAME_INTERVAL,
                crop_size=0, pad_bg=(255, 255, 255)):
        """Process a video file with smart postprocessing and tracking"""
        video_path = Path(video_path)
        
        # Open video
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise ValueError(f"Could not open video: {video_path}")
        
        # Get video properties
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        # Calculate frame interval for target fps (default 2 fps)
        if frame_interval <= 0:
            frame_interval = max(1, int(fps / 2))  # 2 fps
        
        frames_to_process = (total_frames + frame_interval - 1) // frame_interval
        output_fps = min(fps / frame_interval, 2.0)  # Cap at 2 fps for output
        
        print(f"\n📹 Video: {video_path.name}")
        print(f"   Resolution: {width}x{height}")
        print(f"   Source FPS: {fps:.2f}")
        print(f"   Total Frames: {total_frames}")
        print(f"   Duration: {total_frames/fps:.1f}s")
        print(f"   Processing: {frames_to_process} frames (~{output_fps:.1f} fps)")
        
        # Create output directory
        if output_dir is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = RESULTS_DIR / f"{video_path.stem}_{timestamp}"
        else:
            output_dir = Path(output_dir)
        
        output_dir.mkdir(parents=True, exist_ok=True)
        frames_dir = output_dir / "frames"
        frames_dir.mkdir(exist_ok=True)
        
        # Debug directory
        if self.debug:
            debug_dir = output_dir / "debug"
            debug_dir.mkdir(exist_ok=True)
        
        # Setup video writers at reduced fps
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out_fps = output_fps  # Use calculated output fps
        
        overlay_writer = cv2.VideoWriter(
            str(output_dir / "segmented_overlay.mp4"),
            fourcc, out_fps, (width, height)
        )
        mask_writer = cv2.VideoWriter(
            str(output_dir / "mask_only.mp4"),
            fourcc, out_fps, (width, height)
        )
        
        # Initialize stem tracker for this video
        self.tracker = StemTracker(
            alpha=VIDEO_TRACKING_PARAMS['SMOOTH_ALPHA'],
            iou_thresh=VIDEO_TRACKING_PARAMS['IOU_THRESH'],
            min_consistent=VIDEO_TRACKING_PARAMS['MIN_CONSISTENT_FRAMES'],
            max_missing=VIDEO_TRACKING_PARAMS['MAX_MISSING_FRAMES']
        )
        
        # Process frames
        results = {
            "type": "video",
            "name": video_path.name,
            "output_dir": str(output_dir),
            "video_info": {
                "width": width,
                "height": height,
                "fps": fps,
                "total_frames": total_frames,
                "duration_seconds": round(total_frames / fps, 2)
            },
            "frame_interval": frame_interval,
            "processed_frames": 0,
            "extracted_frames": [],
            "aggregate_stats": {"bud": 0, "leaf": 0, "stem": 0},
            "tracking_stats": {
                "track_switches": 0,
                "frames_tracked": 0,
                "frames_with_detection": 0
            },
            "files": {}
        }
        
        processed_count = 0
        extracted_count = 0
        debug_log = []
        
        pbar = tqdm(total=frames_to_process, desc=f"Processing ({frames_to_process} frames @ {output_fps:.1f}fps)")
        
        # Process only frames at target fps by seeking directly (much faster!)
        for frame_idx in range(0, total_frames, frame_interval):
            # Seek directly to the frame we need
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame_bgr = cap.read()
            if not ret:
                break
            
            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            
            # Run model inference
            raw_pred = self._inference(frame_rgb)
            
            # Apply smart postprocessing
            filtered_pred, debug_info = smart_postprocess(raw_pred, frame_rgb.shape, debug=True)
            
            # Get main stem bbox for tracking
            main_bbox = self._get_main_stem_bbox(filtered_pred, frame_rgb.shape)
            
            # Update tracker
            if main_bbox is not None:
                # Simple score: stem area
                stem_area = (filtered_pred == 3).sum()
                smoothed_bbox, accepted = self.tracker.update(main_bbox, float(stem_area))
                
                if accepted:
                    results["tracking_stats"]["frames_tracked"] += 1
                results["tracking_stats"]["frames_with_detection"] += 1
            else:
                smoothed_bbox, accepted = self.tracker.update(None, 0.0)
            
            # Create overlay and mask frames
            overlay = self._create_overlay(frame_rgb, filtered_pred)
            colored_mask = self._create_colored_mask_bgr(filtered_pred)
            
            # Draw tracking bbox if debug
            if self.debug and smoothed_bbox is not None:
                x1, y1, x2, y2 = smoothed_bbox
                cv2.rectangle(overlay, (x1, y1), (x2, y2), (255, 255, 0), 2)
                cv2.putText(overlay, f"F{frame_idx}", (x1, y1 - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 2)
            
            # Write to videos
            overlay_writer.write(cv2.cvtColor(overlay, cv2.COLOR_RGB2BGR))
            mask_writer.write(colored_mask)
            
            # Log debug info
            if self.debug:
                debug_log.append({
                    "frame": frame_idx,
                    "focus_type": debug_info.get('focus_type', 'unknown'),
                    "stem_detected": main_bbox is not None,
                    "track_accepted": accepted,
                    "stem_area": int((filtered_pred == 3).sum()),
                    "leaf_area": int((filtered_pred == 2).sum()),
                    "bud_area": int((filtered_pred == 1).sum())
                })
            
            # Extract individual frames with class crops
            frame_dir = frames_dir / f"frame_{frame_idx:06d}"
            frame_results = self._save_frame_results(
                frame_rgb, filtered_pred, frame_dir, frame_idx,
                crop_size=crop_size, pad_bg=pad_bg
            )
            if frame_results["classes_found"]:
                results["extracted_frames"].append(frame_results)
                extracted_count += 1
            
            # Update aggregate stats
            for cls, stats in frame_results.get("class_stats", {}).items():
                results["aggregate_stats"][cls] += stats["pixel_count"]
            
            processed_count += 1
            pbar.update(1)
        
        pbar.close()
        cap.release()
        overlay_writer.release()
        mask_writer.release()
        
        results["processed_frames"] = processed_count
        results["total_source_frames"] = total_frames
        results["files"] = {
            "segmented_video": str(output_dir / "segmented_overlay.mp4"),
            "mask_video": str(output_dir / "mask_only.mp4"),
            "frames_dir": str(frames_dir)
        }
        
        # Save summary
        with open(output_dir / "summary.json", 'w') as f:
            json.dump(results, f, indent=2)
        
        # Save debug log
        if self.debug:
            with open(debug_dir / "frame_log.json", 'w') as f:
                json.dump(debug_log, f, indent=2)
            
            # Save tracking stats summary
            with open(debug_dir / "tracking_stats.txt", 'w') as f:
                f.write("=== VIDEO TRACKING STATS ===\n\n")
                f.write(f"Total source frames: {total_frames}\n")
                f.write(f"Processed frames: {processed_count}\n")
                f.write(f"Frames with detection: {results['tracking_stats']['frames_with_detection']}\n")
                f.write(f"Frames successfully tracked: {results['tracking_stats']['frames_tracked']}\n")
                f.write(f"Detection rate: {100*results['tracking_stats']['frames_with_detection']/max(processed_count,1):.1f}%\n")
                f.write(f"Track stability: {100*results['tracking_stats']['frames_tracked']/max(results['tracking_stats']['frames_with_detection'],1):.1f}%\n")
        
        print(f"\n✅ Video processed!")
        print(f"   Source frames: {total_frames}")
        print(f"   Processed: {processed_count} frames (2 fps)")
        print(f"   Detected: {results['tracking_stats']['frames_with_detection']} frames")
        print(f"   Tracked: {results['tracking_stats']['frames_tracked']} frames (stable)")
        print(f"   Extracted: {extracted_count} frames with detections")
        
        return results
    
    def _save_frame_results(self, frame_rgb, pred_mask, frame_dir, frame_idx,
                            crop_size=0, pad_bg=(255, 255, 255)):
        """Save results for a single video frame"""
        results = {
            "frame_index": frame_idx,
            "classes_found": [],
            "class_stats": {}
        }
        
        total_pixels = pred_mask.size
        
        for class_id in [1, 2, 3]:
            class_info = CLASSES[class_id]
            class_name = class_info["name"]
            
            class_mask = (pred_mask == class_id).astype(np.uint8)
            pixel_count = np.sum(class_mask)
            
            if pixel_count == 0:
                continue
            
            results["classes_found"].append(class_name)
            results["class_stats"][class_name] = {
                "pixel_count": int(pixel_count),
                "percentage": round(pixel_count / total_pixels * 100, 2)
            }
            
            # Create class folder
            class_dir = frame_dir / class_name
            class_dir.mkdir(parents=True, exist_ok=True)
            
            # Save cropped (transparent) - bbox only to save space
            cropped = self._extract_with_transparency(frame_rgb, class_mask)
            bbox_crop = self._crop_to_bbox(cropped, class_mask)

            if bbox_crop is not None:
                self._save_rgba_lossless(bbox_crop, class_dir / f"{class_name}.png")

                # Also optionally save fixed-size centered padded crop (RGB)
                if crop_size and crop_size > 0:
                    # Obtain RGB crop (no alpha)
                    rgba = bbox_crop
                    if rgba.shape[2] == 4:
                        rgb_crop = rgba[:, :, :3]
                        alpha = rgba[:, :, 3]
                    else:
                        rgb_crop = rgba
                        alpha = np.ones((rgba.shape[0], rgba.shape[1]), dtype=np.uint8) * 255

                    ch_h, ch_w = rgb_crop.shape[0], rgb_crop.shape[1]

                    # Resize to fit within crop_size while preserving aspect ratio
                    scale = min(crop_size / max(ch_w, ch_h), 1.0)
                    if scale < 1.0:
                        new_w = int(ch_w * scale)
                        new_h = int(ch_h * scale)
                        resized = cv2.resize(rgb_crop, (new_w, new_h), interpolation=cv2.INTER_AREA)
                    else:
                        resized = rgb_crop
                        new_h, new_w = ch_h, ch_w

                    # Build background
                    if isinstance(pad_bg, int):
                        bg_color = (pad_bg, pad_bg, pad_bg)
                    else:
                        bg_color = tuple(int(x) for x in pad_bg)

                    pad_img = np.zeros((crop_size, crop_size, 3), dtype=np.uint8)
                    pad_img[:, :] = bg_color

                    x_off = (crop_size - new_w) // 2
                    y_off = (crop_size - new_h) // 2
                    pad_img[y_off:y_off+new_h, x_off:x_off+new_w] = resized

                    padded_filename = f"{class_name}_frame{frame_idx:06d}_pad_{crop_size}px.png"
                    padded_path = class_dir / padded_filename
                    Image.fromarray(pad_img).save(str(padded_path), 'PNG', compress_level=PNG_COMPRESSION)
                    # Record file in results
                    results.setdefault('padded_files', {}).setdefault(class_name, []).append(str(padded_path))
                # Also save a full RGB crop (original bbox size) with background (no transparency)
                try:
                    if bbox_crop.shape[2] == 4:
                        rgb_full = bbox_crop[:, :, :3]
                    else:
                        rgb_full = bbox_crop

                    full_filename = f"{class_name}_frame{frame_idx:06d}_full.png"
                    full_path = class_dir / full_filename
                    Image.fromarray(rgb_full).save(str(full_path), 'PNG', compress_level=PNG_COMPRESSION)
                    results.setdefault('full_files', {}).setdefault(class_name, []).append(str(full_path))
                except Exception:
                    pass
        
        return results
    
    def process_folder(self, folder_path, frame_interval=DEFAULT_FRAME_INTERVAL):
        """Process all videos in a folder"""
        folder_path = Path(folder_path)
        
        # Find all videos
        videos = [f for f in folder_path.iterdir() 
                  if f.suffix.lower() in VIDEO_EXTENSIONS]
        
        if not videos:
            print(f"❌ No videos found in {folder_path}")
            return []
        
        print(f"\n🎬 Processing {len(videos)} videos...\n")
        
        all_results = []
        for vid_path in videos:
            try:
                result = self.predict(vid_path, frame_interval=frame_interval)
                all_results.append(result)
            except Exception as e:
                print(f"   ❌ {vid_path.name}: {e}")
        
        print(f"\n✅ Processed {len(all_results)} videos")
        print(f"📁 Results: {RESULTS_DIR}")
        
        return all_results
    
    # ==================== UTILITY FUNCTIONS ====================
    
    def _save_rgba_lossless(self, img_rgba, path):
        """Save RGBA image as lossless PNG"""
        img_pil = Image.fromarray(img_rgba, 'RGBA')
        img_pil.save(str(path), 'PNG', compress_level=PNG_COMPRESSION)
    
    def _create_colored_mask_bgr(self, pred_mask):
        """Create BGR colored mask for video"""
        h, w = pred_mask.shape
        colored = np.zeros((h, w, 3), dtype=np.uint8)
        
        for class_id, info in CLASSES.items():
            if class_id > 0:
                colored[pred_mask == class_id] = info["color_bgr"]
        
        return colored
    
    def _create_overlay(self, img_rgb, pred_mask):
        """Create image with semi-transparent mask overlay"""
        overlay = img_rgb.copy()
        for class_id in [1, 2, 3]:
            mask = pred_mask == class_id
            if np.any(mask):
                color = CLASSES[class_id]["color"][:3]
                overlay[mask] = (0.6 * img_rgb[mask] + 0.4 * np.array(color)).astype(np.uint8)
        return overlay
    
    def _extract_with_transparency(self, img_rgb, mask):
        """Extract image region with transparent background"""
        h, w = img_rgb.shape[:2]
        rgba = np.zeros((h, w, 4), dtype=np.uint8)
        rgba[:, :, :3] = img_rgb
        rgba[:, :, 3] = mask * 255
        return rgba
    
    def _crop_to_bbox(self, rgba_img, mask):
        """Crop to bounding box"""
        coords = np.where(mask > 0)
        if len(coords[0]) == 0:
            return None
        
        y_min, y_max = coords[0].min(), coords[0].max()
        x_min, x_max = coords[1].min(), coords[1].max()
        
        pad = 10
        y_min = max(0, y_min - pad)
        y_max = min(rgba_img.shape[0], y_max + pad)
        x_min = max(0, x_min - pad)
        x_max = min(rgba_img.shape[1], x_max + pad)
        
        return rgba_img[y_min:y_max, x_min:x_max]


def main():
    parser = argparse.ArgumentParser(
        description='Coconut Tree Video Segmentation with Smart Postprocessing & Tracking',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python predict_video.py --video coconut.mp4
    python predict_video.py --video coconut.mp4 --debug
    python predict_video.py --video coconut.mp4 --frame-interval 5
    python predict_video.py --folder ./videos
        """
    )
    parser.add_argument('--video', type=str, help='Path to video file')
    parser.add_argument('--folder', type=str, help='Path to folder with videos')
    parser.add_argument('--output', type=str, help='Custom output directory')
    parser.add_argument('--model', type=str, help='Path to model file')
    parser.add_argument('--frame-interval', type=int, default=0,
                        help='Process every Nth frame (default: 0 = auto 2fps)')
    parser.add_argument('--debug', '-d', action='store_true', 
                        help='Generate debug outputs (tracking bbox, frame log)')
    parser.add_argument('--crop-size', type=int, default=0,
                        help='Optional fixed crop size (px). 0 = disabled. Default: 0')
    parser.add_argument('--pad-bg', type=str, default='255,255,255',
                        help='Background color for padded crops as R,G,B (default white)')
    
    args = parser.parse_args()
    
    # Initialize segmenter
    model_path = Path(args.model) if args.model else None
    segmenter = VideoSegmenter(model_path, debug=args.debug)
    
    print()
    
    if args.video:
        # Process video
        output_dir = Path(args.output) if args.output else None
        # Parse pad background color
        try:
            pad_bg = tuple(int(x) for x in args.pad_bg.split(','))
            if len(pad_bg) == 1:
                pad_bg = (pad_bg[0], pad_bg[0], pad_bg[0])
            elif len(pad_bg) != 3:
                pad_bg = (255, 255, 255)
        except:
            pad_bg = (255, 255, 255)

        result = segmenter.predict(args.video, output_dir, args.frame_interval,
                                   crop_size=args.crop_size, pad_bg=pad_bg)
        
        print(f"\n{'='*50}")
        print(f"🎬 VIDEO: {result['name']}")
        print(f"📐 Size: {result['video_info']['width']}x{result['video_info']['height']}")
        print(f"⏱️  Duration: {result['video_info']['duration_seconds']}s")
        print(f"🎞️  Processed: {result['processed_frames']} frames")
        print(f"{'='*50}")
        
        print(f"\n📊 Tracking Stats:")
        ts = result['tracking_stats']
        print(f"   Frames with stem: {ts['frames_with_detection']}")
        print(f"   Stable tracking: {ts['frames_tracked']}")
        
        print(f"\n📁 Output: {result['output_dir']}")
        print(f"   ├── segmented_overlay.mp4  (video with mask)")
        print(f"   ├── mask_only.mp4          (colored mask)")
        if args.debug:
            print(f"   ├── debug/")
            print(f"   │   ├── frame_log.json     (per-frame stats)")
            print(f"   │   └── tracking_stats.txt")
        print(f"   └── frames/")
        print(f"       └── frame_XXXXXX/")
        print(f"           ├── bud/")
        print(f"           ├── leaf/")
        print(f"           └── stem/")
        print(f"\n   📊 Frames with detections: {len(result['extracted_frames'])}")
        
    elif args.folder:
        segmenter.process_folder(args.folder, args.frame_interval)
        
    else:
        print("🌴 Coconut Tree VIDEO Segmentation v2.0")
        print("="*50)
        print("\n📋 Smart Postprocessing Features:")
        print("   • Scores stems: area, center, verticality, connected leaves")
        print("   • Picks the MAIN FOCUSED tree only")
        print("   • Keeps only connected leaves/buds")
        print("   • IoU-based tracking across frames")
        print("   • Exponential smoothing for stability")
        print("\nUsage:")
        print("  python predict_video.py --video <path>")
        print("  python predict_video.py --video <path> --debug")
        print("  python predict_video.py --video <path> --frame-interval 5")
        print("  python predict_video.py --folder <path>")
        print("\nOptions:")
        print("  --debug             Generate debug outputs (tracking log, bbox overlay)")
        print("  --frame-interval N  Extract crops every N frames (default: 1)")
        print("\n📊 Tracking Parameters:")
        for key, val in VIDEO_TRACKING_PARAMS.items():
            print(f"   {key}: {val}")


if __name__ == "__main__":
    main()
