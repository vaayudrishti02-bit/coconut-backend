# backend/sideview/router.py
"""
Sideview Router - Coconut Tree Disease Detection (Transfer Model)
Provides API endpoints for disease detection in coconut trees using:
- Single image prediction
- Video processing with frame-by-frame analysis
"""

import sys
import os
import json
import shutil
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, UploadFile, HTTPException, Header
from fastapi.responses import JSONResponse

# Setup logging
logger = logging.getLogger(__name__)

# Configure paths
SIDEVIEW_ROOT = Path(__file__).parent
SCRIPTS_DIR = SIDEVIEW_ROOT / "scripts"
UPLOADS_DIR = SIDEVIEW_ROOT / "uploads"
RESULTS_DIR = SIDEVIEW_ROOT / "results"
MODEL_PATH = SIDEVIEW_ROOT / "plant_disease_transfer_model.h5"
LABELS_PATH = SIDEVIEW_ROOT / "labels.json"

# Ensure directories exist
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# Add scripts directory to path for imports
if str(SIDEVIEW_ROOT) not in sys.path:
    sys.path.insert(0, str(SIDEVIEW_ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

# Import local modules
try:
    from sideview.test_transfer_model import TransferModelPredictor
    from sideview.scripts.video_to_phase2 import run_pipeline
    from sideview.scripts.generate_video_report_v2 import generate_report
    from sideview.scripts.aggregate_dashboard import aggregate_dashboard, VALID_DISEASES_BY_PART
    from recommendation import get_recommendation, get_recommendation_for_video, get_simple_recommendation, get_simple_recommendation_for_video
    
    MODULES_AVAILABLE = True
    logger.info("Sideview modules loaded successfully")
except ImportError as e:
    MODULES_AVAILABLE = False
    logger.error(f"Failed to import sideview modules: {e}")
    TransferModelPredictor = None
    run_pipeline = None
    generate_report = None
    aggregate_dashboard = None
    VALID_DISEASES_BY_PART = None
    get_recommendation = None
    get_recommendation_for_video = None
    get_simple_recommendation = None
    get_simple_recommendation_for_video = None

# Create router
router = APIRouter(
    prefix="/sideview",
    tags=["Sideview - Disease Detection"],
    responses={
        500: {"description": "Internal server error"},
        400: {"description": "Bad request"},
    }
)

# Lazy-loaded global predictor for single-image endpoint
_image_predictor: Optional[TransferModelPredictor] = None

# Store last prediction for recommendation endpoint
_last_prediction: Optional[dict] = None


def _get_predictor() -> TransferModelPredictor:
    """Initialize and return the image predictor (singleton pattern)."""
    global _image_predictor
    
    if _image_predictor is None:
        if not MODULES_AVAILABLE or TransferModelPredictor is None:
            raise HTTPException(
                status_code=500,
                detail="Prediction modules not available"
            )
        
        if not MODEL_PATH.exists():
            raise HTTPException(
                status_code=500,
                detail=f"Model not found at {MODEL_PATH}"
            )
        if not LABELS_PATH.exists():
            raise HTTPException(
                status_code=500,
                detail=f"Labels file not found at {LABELS_PATH}"
            )
        
        _image_predictor = TransferModelPredictor(
            model_path=str(MODEL_PATH),
            labels_path=str(LABELS_PATH)
        )
        logger.info("Transfer model loaded successfully")
    
    return _image_predictor


@router.get("/", summary="Sideview API Info")
async def sideview_root():
    """Get information about the Sideview Disease Detection API."""
    return {
        "message": "Coconut Tree Disease Detection API (Sideview)",
        "version": "1.0.0",
        "status": "operational" if MODULES_AVAILABLE else "degraded",
        "endpoints": {
            "predict_image": "/sideview/predict_image",
            "process_video": "/sideview/process_video"
        },
        "capabilities": {
            "image_prediction": MODULES_AVAILABLE and MODEL_PATH.exists(),
            "video_processing": MODULES_AVAILABLE and MODEL_PATH.exists()
        }
    }


import uuid

# In-memory store for predictions (replace with Redis/DB for production)
_prediction_store = {}

def _save_prediction_backup(analysis_id: str, prediction: dict):
    """Save prediction to backup file for durability."""
    try:
        backup_dir = RESULTS_DIR / "predictions_backup"
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_file = backup_dir / f"{analysis_id}.json"
        with open(backup_file, "w") as f:
            json.dump(prediction, f, indent=2)
        logger.debug(f"Prediction backup saved: {backup_file}")
    except Exception as e:
        logger.warning(f"Failed to save prediction backup: {e}")

def _load_prediction_backup(analysis_id: str) -> Optional[dict]:
    """Load prediction from backup file if in-memory store is empty."""
    try:
        backup_file = RESULTS_DIR / "predictions_backup" / f"{analysis_id}.json"
        if backup_file.exists():
            with open(backup_file, "r") as f:
                data = json.load(f)
                logger.debug(f"Prediction loaded from backup: {backup_file}")
                return data
    except Exception as e:
        logger.warning(f"Failed to load prediction backup: {e}")
    return None

@router.post("/predict_image", summary="Predict Disease from Image")
async def predict_image_endpoint(file: UploadFile = File(...)):
    """
    Predict disease, part, and health status for a single uploaded image.
    
    Args:
        file: Image file (JPG, PNG) of coconut tree part
        
    Returns:
        JSON containing:
        - image: Path to uploaded image
        - prediction: Disease classification results with confidence scores
    """
    try:
        # Validate file type
        if not file.content_type or not file.content_type.startswith('image/'):
            raise HTTPException(
                status_code=400,
                detail="Invalid file type. Please upload an image file."
            )
        
        # Get predictor (loads model if needed)
        predictor = _get_predictor()
        
        # Save uploaded image
        image_upload_dir = UPLOADS_DIR / "images"
        image_upload_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = image_upload_dir / file.filename
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Run prediction
        result = predictor.predict(str(file_path))
        
        # Generate unique analysis ID
        analysis_id = str(uuid.uuid4())
        _prediction_store[analysis_id] = result
        _save_prediction_backup(analysis_id, result)

        logger.info(f"Image prediction completed: {file.filename} (ID: {analysis_id})")

        return {
            "success": True,
            "image": str(file_path),
            "filename": file.filename,
            "prediction": result,
            "analysis_id": analysis_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Image prediction error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Prediction failed: {str(e)}"
        )


from fastapi import Query

def _get_locale_from_header(accept_language: str = None) -> str:
    """Extract locale from Accept-Language header."""
    logger.info(f"Received Accept-Language header: {accept_language}")
    if not accept_language:
        logger.info("No Accept-Language header, defaulting to 'en'")
        return "en"
    # Parse Accept-Language header (e.g., "kn-IN,kn;q=0.9,en;q=0.8")
    lang = accept_language.split(",")[0].split("-")[0].lower().strip()
    result = lang if lang in ["en", "kn"] else "en"
    logger.info(f"Parsed locale: {result}")
    return result

@router.get("/recommendation", summary="Get Disease Recommendation")
async def get_recommendation_endpoint(
    id: str = Query(..., description="Analysis ID from /predict_image"),
    accept_language: str = Header(None, alias="Accept-Language", description="Language preference (en or kn)")
):
    """
    Get treatment recommendation for the last analyzed image.
    
    Must be called after /predict_image endpoint.
    
    Returns:
        JSON containing:
        - source: "image" (indicates this is from image analysis)
        - predicted_label: Disease label from the model
        - confidence: Confidence score (0-100)
        - recommendation: Treatment details with:
            - disease: Disease name
            - status: "illness" or "healthy"
            - part: Affected tree part
            - severity: "mild", "medium", or "severe" (based on confidence)
            - fertilizers: List of recommended treatments
            - practices: List of recommended practices
    """
    # Look up prediction by analysis ID (stored value is raw predictor output)
    raw_prediction = _prediction_store.get(id)
    if not raw_prediction:
        # Try loading from backup file
        raw_prediction = _load_prediction_backup(id)
    if not raw_prediction:
        raise HTTPException(
            status_code=404,
            detail=f"No prediction found for analysis ID: {id}. The analysis may have expired or the server was restarted."
        )
    try:
        # raw_prediction is the full predictor output: {status, part, combined, predicted_label, ...}
        prediction = raw_prediction
        
        # Use combined/predicted_label for DISEASE_DB lookup (e.g. "leaves_Grey_leaf_rot")
        # status.prediction is display name ("Grey leaf rot") which doesn't match DB keys
        predicted_label = prediction.get("combined") or prediction.get("predicted_label")
        status_field = prediction.get("status", {})
        if predicted_label is None and isinstance(status_field, dict):
            predicted_label = status_field.get("prediction", "healthy")
        if predicted_label is None:
            predicted_label = "healthy"
        
        confidence = float(status_field.get("confidence", 0.0)) if isinstance(status_field, dict) else 0.0
        
        # Normalize confidence to 0-100 range (if it's 0-1, multiply by 100)
        if confidence <= 1.0:
            confidence = confidence * 100
        
        # Get part information
        part_field = prediction.get("part", {})
        if isinstance(part_field, dict):
            part = part_field.get("prediction", "tree")
        else:
            part = part_field or "tree"
        
        # Normalize part name
        if part == "leaf":
            part = "leaves"
        
        # Get recommendation using the recommendation module
        if not get_recommendation:
            raise HTTPException(
                status_code=500,
                detail="Recommendation module not available"
            )
        
        locale = _get_locale_from_header(accept_language)
        recommendation_data = get_recommendation(predicted_label, confidence, part, locale)
        
        logger.info(f"Recommendation generated: {predicted_label} with confidence {confidence} (locale: {locale})")
        
        return {
            "success": True,
            "source": "image",
            "predicted_label": predicted_label,
            "confidence": confidence,
            "part": part,
            "recommendation": recommendation_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Recommendation error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate recommendation: {str(e)}"
        )


@router.get("/simple_recommendation", summary="Get Simple Disease Recommendation (No Severity)")
async def get_simple_recommendation_endpoint(
    id: str = Query(..., description="Analysis ID from /predict_image"),
    accept_language: str = Header(None, alias="Accept-Language", description="Language preference (en or kn)")
):
    """
    Get simplified treatment recommendation based ONLY on disease type and part.
    Does NOT use confidence score or severity grading.
    
    Must be called after /predict_image endpoint.
    
    Returns:
        JSON containing:
        - source: "image" (indicates this is from image analysis)
        - predicted_label: Disease label from the model
        - part: Affected tree part
        - recommendation: Comprehensive treatment details with:
            - disease: Disease name
            - status: "illness" or "healthy"
            - part: Affected tree part
            - fertilizers: All recommended treatments (combined from all severity levels)
            - practices: All recommended practices (combined from all severity levels)
    """
    # Look up prediction by analysis ID
    raw_prediction = _prediction_store.get(id)
    if not raw_prediction:
        raw_prediction = _load_prediction_backup(id)
    if not raw_prediction:
        raise HTTPException(
            status_code=404,
            detail=f"No prediction found for analysis ID: {id}. The analysis may have expired or the server was restarted."
        )
    
    try:
        prediction = raw_prediction
        
        # Extract disease label (same logic as original endpoint)
        predicted_label = prediction.get("combined") or prediction.get("predicted_label")
        status_field = prediction.get("status", {})
        if predicted_label is None and isinstance(status_field, dict):
            predicted_label = status_field.get("prediction", "healthy")
        if predicted_label is None:
            predicted_label = "healthy"
        
        # Get part information
        part_field = prediction.get("part", {})
        if isinstance(part_field, dict):
            part = part_field.get("prediction", "tree")
        else:
            part = part_field or "tree"
        
        # Normalize part name
        if part == "leaf":
            part = "leaves"
        
        # Get simple recommendation (no confidence needed)
        if not get_simple_recommendation:
            raise HTTPException(
                status_code=500,
                detail="Recommendation module not available"
            )
        
        locale = _get_locale_from_header(accept_language)
        recommendation_data = get_simple_recommendation(predicted_label, part, locale)
        
        logger.info(f"Simple recommendation generated: {predicted_label} for part {part} (locale: {locale})")
        
        return {
            "success": True,
            "source": "image",
            "predicted_label": predicted_label,
            "part": part,
            "recommendation": recommendation_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Simple recommendation error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate simple recommendation: {str(e)}"
        )


@router.post("/process_video", summary="Process Video for Disease Detection")
async def process_video_endpoint(
    file: UploadFile = File(...),
    accept_language: str = Header(None, alias="Accept-Language", description="Language preference (en or kn)")
):
    """
    Process video file to detect diseases frame-by-frame.
    
    Args:
        file: Video file (MP4, AVI, MOV) of coconut tree
        
    Returns:
        JSON containing:
        - video: Path to uploaded video
        - predictions: Frame-by-frame prediction results
        - dashboard: Aggregated analysis dashboard
        - report_url: URL to HTML report
    """
    locale = _get_locale_from_header(accept_language)
    try:
        # Check module availability
        if not MODULES_AVAILABLE or run_pipeline is None or generate_report is None:
            raise HTTPException(
                status_code=500,
                detail="Video pipeline modules not available"
            )
        
        # Validate file type
        if not file.content_type or not file.content_type.startswith('video/'):
            raise HTTPException(
                status_code=400,
                detail="Invalid file type. Please upload a video file."
            )
        
        # Check model availability
        if not MODEL_PATH.exists():
            raise HTTPException(
                status_code=500,
                detail=f"Model not found at {MODEL_PATH}"
            )
        
        # Save uploaded video
        file_path = UPLOADS_DIR / file.filename
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        logger.info(f"Processing video: {file.filename}")
        
        # Run the video processing pipeline
        output_json_path = run_pipeline(
            video_path=str(file_path),
            phase2_model=str(MODEL_PATH),
            frame_interval=0,  # Auto-detect interval
            debug=False,
        )
        
        # Generate HTML report
        generate_report(Path(output_json_path))
        
        # Load the result JSON
        with open(output_json_path, "r") as f:
            result_data = json.load(f)

        # Extract and format predictions
        predictions = result_data.get("predictions", [])
        formatted_predictions = _format_predictions(predictions)
        
        # Generate dashboard
        dashboard = aggregate_dashboard(formatted_predictions)
        
        # Get report URL and paths
        json_path_obj = Path(output_json_path)
        timestamp_folder = json_path_obj.parent.name
        result_dir = json_path_obj.parent
        
        # Save dashboard.json
        dashboard_path = result_dir / "dashboard.json"
        with open(dashboard_path, "w") as f:
            json.dump(dashboard, f, indent=2)
        
        logger.info(f"Dashboard saved: {dashboard_path}")

        # Build video recommendations for Flutter (stem, leaves, bud)
        recommendations = _build_video_recommendations(dashboard, locale)

        logger.info(f"Video processing completed: {file.filename} (locale: {locale})")

        return {
            "success": True,
            "video": str(file_path),
            "filename": file.filename,
            "predictions": formatted_predictions,
            "dashboard": dashboard,
            "dashboard_path": str(dashboard_path),
            "report_url": f"/results/{timestamp_folder}/video_report.html",
            "total_frames": len(formatted_predictions),
            "recommendations": recommendations,
            "source": "video",
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Video processing error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Video processing failed: {str(e)}"
        )


def _build_video_recommendations(dashboard: dict, locale: str = "en") -> dict:
    """
    Build per-part recommendations from dashboard for Flutter VideoRecommendations.
    Returns: { stem: {...}, leaves: {...}, bud: {...} }
    """
    if not get_simple_recommendation_for_video:
        return {"stem": _default_part_rec("stem"), "leaves": _default_part_rec("leaves"), "bud": _default_part_rec("bud")}

    parts_data = dashboard.get("parts", {})
    result = {}

    for part in ("stem", "leaves", "bud"):
        part_info = parts_data.get(part, {})
        health = part_info.get("health", "unknown")
        diseases = part_info.get("diseases", {})

        if health == "healthy" or not diseases:
            rec_data = get_simple_recommendation_for_video("healthy", part, locale)
        else:
            # Primary disease: highest-weighted
            primary = max(diseases.items(), key=lambda x: x[1])
            disease_display = primary[0]
            rec_data = get_simple_recommendation_for_video(disease_display, part, locale)

        result[part] = {
            "part": part,
            "health": health if health in ("healthy", "unhealthy") else "unknown",
            "predicted_label": rec_data.get("disease"),
            "recommendation": rec_data,
        }

    return result


def _default_part_rec(part: str) -> dict:
    """Fallback when recommendation module unavailable."""
    return {
        "part": part,
        "health": "unknown",
        "recommendation": {
            "disease": "Unknown",
            "status": "healthy",
            "part": part,
            "practices": [],
        },
    }


def _format_predictions(predictions: list) -> list:
    """
    Format and filter predictions from the video pipeline.
    
    - Normalize part names ('leaf' -> 'leaves')
    - Enforce part-disease compatibility
    - Filter out Unknown predictions
    
    Args:
        predictions: Raw predictions from pipeline
        
    Returns:
        List of formatted prediction dictionaries
    """
    if not VALID_DISEASES_BY_PART:
        return []
    
    formatted_predictions = []
    
    for pred_entry in predictions:
        prediction_detail = pred_entry.get("prediction", {}) or {}
        
        # Extract status
        status_field = prediction_detail.get("status")
        if isinstance(status_field, dict):
            raw_status = status_field.get("prediction")
            status_conf = float(status_field.get("confidence") or 0.0)
        else:
            raw_status = status_field
            status_conf = 0.0
        raw_status = raw_status or "Unknown"
        
        # Extract and normalize part
        part_field = prediction_detail.get("part")
        if isinstance(part_field, dict):
            part = part_field.get("prediction")
            part_conf = float(part_field.get("confidence") or 0.0)
        else:
            part = part_field
            part_conf = 0.0
        
        # Normalize 'leaf' to 'leaves'
        if part == "leaf":
            part = "leaves"
        
        # Enforce part-disease compatibility
        display_status = raw_status
        if part and raw_status not in (None, "Unknown"):
            allowed = VALID_DISEASES_BY_PART.get(part, set())
            if allowed and raw_status not in allowed:
                display_status = "Unknown"
        
        # Skip Unknown statuses
        if display_status == "Unknown" or not part:
            continue
        
        formatted_predictions.append({
            "frame_index": pred_entry.get("frame_index"),
            "class": pred_entry.get("class"),
            "image_path": prediction_detail.get("image_path") or pred_entry.get("file"),
            "part": {
                "prediction": part,
                "confidence": part_conf,
            },
            "status": {
                "prediction": display_status,
                "confidence": status_conf,
            },
            "health": prediction_detail.get("health"),
            "combined": prediction_detail.get("combined"),
            "is_out_of_distribution": prediction_detail.get("is_out_of_distribution", False),
            "ood_reason": prediction_detail.get("ood_reason"),
            "ood_signals": prediction_detail.get("ood_signals"),
            "reliability": prediction_detail.get("reliability", 0),
        })
    
    return formatted_predictions
