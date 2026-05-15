# backend/utils/video_utils.py
import cv2
import os
import tempfile
from typing import List
import logging

logger = logging.getLogger(__name__)


def extract_frames(video_path: str, max_frames: int = 10, sample_interval: float = 1.0) -> List[str]:
    """
    Extract frames from a video file for ML processing.
    
    Args:
        video_path: Path to the video file
        max_frames: Maximum number of frames to extract
        sample_interval: Time interval between frames in seconds
        
    Returns:
        List of paths to extracted frame images
    """
    frame_paths = []
    cap = cv2.VideoCapture(video_path)
    
    if not cap.isOpened():
        logger.error(f"Could not open video: {video_path}")
        return []
    
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration = total_frames / fps if fps > 0 else 0
    
    # Calculate frame indices to extract
    frame_interval = int(fps * sample_interval)
    if frame_interval < 1:
        frame_interval = 1
    
    # Create temp directory for frames
    temp_dir = tempfile.mkdtemp(prefix="video_frames_")
    
    frames_extracted = 0
    current_frame = 0
    
    while frames_extracted < max_frames and current_frame < total_frames:
        cap.set(cv2.CAP_PROP_POS_FRAMES, current_frame)
        ret, frame = cap.read()
        
        if not ret:
            break
            
        # Save frame
        frame_path = os.path.join(temp_dir, f"frame_{frames_extracted:04d}.jpg")
        cv2.imwrite(frame_path, frame)
        frame_paths.append(frame_path)
        
        frames_extracted += 1
        current_frame += frame_interval
    
    cap.release()
    logger.info(f"Extracted {len(frame_paths)} frames from {video_path}")
    return frame_paths


def get_video_duration(video_path):
    """Get video duration in seconds"""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened(): 
        return 0.0
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
    cap.release()
    return frame_count / fps if fps else 0.0

def extract_frame_at(video_path, t_seconds, out_path):
    """Extract a frame at specific timestamp and save to file"""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return False
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_no = int(round(t_seconds * fps))
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
    ok, frame = cap.read()
    if not ok:
        cap.release()
        return False
    # ensure directory exists
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    cv2.imwrite(out_path, frame)
    cap.release()
    return True
