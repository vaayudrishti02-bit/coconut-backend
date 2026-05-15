# backend/api/drone_router.py
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
import os
import cv2
import numpy as np

from db.database import get_db
from db import crud
from topview.model import TopViewModel
from topview.config import MODEL_PATH
from topview.utils import assign_numbers, draw_overlay
from sideview.model import SideViewModel
from sideview import aggregator
from utils.video_utils import get_video_duration, extract_frame_at

router = APIRouter(prefix="/api/drone", tags=["Drone"])

# Validation constants
VALID_PARTS = {"stem", "bud", "leaves"}
VALID_STATUSES = {"healthy", "unhealthy", "bud_rot", "bud_root_dropping", "stem_bleeding"}

def validate_part_name(part_name: str) -> str:
    """Validate and normalize part name to lowercase."""
    if not part_name:
        raise HTTPException(status_code=400, detail="part_name is required")
    part_name = part_name.lower().strip()
    if part_name not in VALID_PARTS:
        raise HTTPException(status_code=400, detail=f"Invalid part_name '{part_name}'. Must be one of: {VALID_PARTS}")
    return part_name

def validate_status(status: str) -> str:
    """Validate status value."""
    if not status:
        raise HTTPException(status_code=400, detail="status is required")
    status = status.lower().strip()
    if status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status '{status}'. Must be one of: {VALID_STATUSES}")
    return status

def validate_tree_number(tree_number: int) -> int:
    """Validate tree number is positive integer."""
    try:
        tree_number = int(tree_number)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail=f"tree_number must be a number, got {tree_number}")
        
    if tree_number <= 0:
        raise HTTPException(status_code=400, detail=f"tree_number must be positive integer, got {tree_number}")
    return tree_number

def validate_confidence(confidence: float) -> float:
    """Validate confidence is in valid range."""
    try:
        confidence = float(confidence)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail=f"confidence must be a number, got {confidence}")
    if not (0.0 <= confidence <= 1.0):
        raise HTTPException(status_code=400, detail=f"confidence must be between 0.0-1.0, got {confidence}")
    return confidence

# Initialize models (lazy loading)
topview_model = None
sideview_model = SideViewModel()

def get_topview_model(model_path: str = None):
    """Lazily instantiate TopViewModel. Returns None if weights file missing."""
    global topview_model
    if topview_model is None:
        try:
            topview_model = TopViewModel(model_path or MODEL_PATH)
        except FileNotFoundError:
            # Defer error to request time so app can start without weights present
            return None
        except Exception:
            # Any other error during init — re-raise to make debugging visible at runtime
            raise
    return topview_model


@router.post("/topview")
async def upload_topview(
    farmer_id: int = Form(...),
    survey_id: int = Form(...), 
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload topview image, detect trees, assign numbers, create Tree rows, and save annotated image.
    Requires farmer_id for authorization.
    """
    survey = crud.get_survey(db, survey_id)
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    
    if survey.farmer_id != farmer_id:
        raise HTTPException(status_code=403, detail="Farmer mismatch - survey belongs to different farmer")

    # Save uploaded image
    ext = os.path.splitext(file.filename)[1] or ".jpg"
    dest_dir = f"uploads/surveys/{survey_id}"
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, f"topview_raw{ext}")
    
    with open(dest, "wb") as f:
        f.write(await file.read())

    # Read image for model
    img = cv2.imdecode(np.fromfile(dest, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=400, detail="Invalid image file")

    # Detect trees
    model = get_topview_model()
    if model is None:
        raise HTTPException(status_code=503, detail="Topview model weights not found on server; place 'topview/final_best.pt' in the project or configure MODEL_PATH")
    boxes = model.detect_trees(img)
    
    # Convert to centroids and assign numbers
    centroids = []
    for b in boxes:
        # If output is dict with 'cx'/'cy', use them
        if isinstance(b, dict):
            if "cx" in b and "cy" in b:
                centroids.append({
                    "cx": b["cx"],
                    "cy": b["cy"],
                    "conf": b.get("conf", 1.0)
                })
            elif "centroid" in b and isinstance(b["centroid"], (list, tuple)) and len(b["centroid"]) == 2:
                centroids.append({
                    "cx": b["centroid"][0],
                    "cy": b["centroid"][1],
                    "conf": b.get("conf", 1.0)
                })
            elif "bbox" in b and isinstance(b["bbox"], (list, tuple)) and len(b["bbox"]) >= 4:
                x1, y1, x2, y2 = b["bbox"][:4]
                cx = float(x1 + x2) / 2
                cy = float(y1 + y2) / 2
                centroids.append({"cx": cx, "cy": cy, "conf": b.get("conf", 1.0)})
            else:
                raise HTTPException(status_code=500, detail=f"Unexpected box dict format: {b}")
        elif isinstance(b, (list, tuple, np.ndarray)) and len(b) >= 4:
            x1, y1, x2, y2 = b[:4]
            cx = float(x1 + x2) / 2
            cy = float(y1 + y2) / 2
            conf = float(b[4]) if len(b) > 4 else 1.0
            centroids.append({"cx": cx, "cy": cy, "conf": conf})
        else:
            raise HTTPException(status_code=500, detail=f"Unexpected box format: {b}")
    numbered = assign_numbers(centroids, img.shape[0])
    
    # Get existing trees - start numbering from highest existing + 1
    from db.models import Tree
    existing_trees = db.query(Tree).filter(Tree.survey_id == survey_id).all()
    next_tree_number = max([t.tree_number for t in existing_trees], default=0) + 1
    
    # Create Tree rows in database with sequential numbers
    for nb in numbered:
        crud.create_tree(
            db=db,
            survey_id=survey_id, 
            tree_number=next_tree_number, 
            cx=int(nb["cx"]), 
            cy=int(nb["cy"])
        )
        nb["tree_number"] = next_tree_number  # Update for display
        next_tree_number += 1
    
    # Create annotated image with numbered pins (larger radius for visibility)
    annotated_path = os.path.join(dest_dir, "topview_annotated.jpg")
    annotated_img = draw_overlay(img, numbered, pin_radius=60)
    cv2.imwrite(annotated_path, annotated_img)
    
    # Update survey with total trees and image path
    crud.update_survey_topview_info(
        db=db,
        survey_id=survey_id, 
        total_trees=len(numbered), 
        topview_image_path=annotated_path
    )
    
    return JSONResponse({
        "survey_id": survey_id, 
        "total_trees": len(numbered), 
        "topview_image": annotated_path,
        "annotated_image_url": f"/api/drone/{farmer_id}/{survey_id}/image",
        "centroids": [{"tree_number": nb["tree_number"], "cx": nb["cx"], "cy": nb["cy"]} for nb in numbered]
    })


@router.post("/sideview")
async def upload_sideview(
    farmer_id: int = Form(...),
    survey_id: int = Form(...), 
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload sideview video, split by tree count, extract frames, run predictions, and aggregate health.
    Requires farmer_id for authorization.
    """
    survey = crud.get_survey(db, survey_id)
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    
    if survey.farmer_id != farmer_id:
        raise HTTPException(status_code=403, detail="Farmer mismatch - survey belongs to different farmer")

    # Save video
    dest_dir = f"uploads/surveys/{survey_id}/sideview"
    os.makedirs(dest_dir, exist_ok=True)
    video_path = os.path.join(dest_dir, "sideview.mp4")
    
    with open(video_path, "wb") as f:
        f.write(await file.read())

    # Get trees from survey
    trees = crud.get_trees_by_survey(db, survey_id)
    trees = sorted(trees, key=lambda t: t.tree_number)
    N = len(trees)
    
    if N == 0:
        raise HTTPException(status_code=400, detail="No trees found for this survey. Run topview detection first.")

    # Get video duration and split into N segments
    duration = get_video_duration(video_path)
    results = []
    
    for i, tree in enumerate(trees, start=1):
        # Calculate mid-point of this tree's segment
        mid = duration * (i - 0.5) / N
        frame_path = os.path.join(dest_dir, f"tree_{tree.tree_number}_frame.jpg")
        
        # Extract frame at midpoint
        ok = extract_frame_at(video_path, mid, frame_path)
        if not ok:
            results.append({"tree": tree.tree_number, "error": "Frame extraction failed"})
            continue
        
        # Run sideview prediction
        try:
            pred = sideview_model.predict(frame_path)
            
            # Extract predictions (adapt based on your model output format)
            part_name = pred.get("part", "unknown")
            status_name = pred.get("status", "unknown")
            status_conf = pred.get("status_confidence", pred.get("part_confidence", 1.0))
            
            # Store prediction as TreePart
            crud.add_tree_part(
                db=db,
                tree_id=tree.id, 
                part_name=part_name, 
                status=status_name, 
                confidence=status_conf
            )
            
            results.append({
                "tree": tree.tree_number, 
                "part": part_name, 
                "status": status_name, 
                "confidence": status_conf
            })
        except Exception as e:
            results.append({"tree": tree.tree_number, "error": str(e)})
            continue

    # Aggregate health for each tree
    for t in trees:
        parts = crud.get_parts_for_tree(db, t.id)
        
        # Convert to aggregator format
        data = {"stem": [], "bud": [], "leaves": []}
        for p in parts:
            if p.part_name in data:
                data[p.part_name].append({"status": p.status, "confidence": p.confidence})
            else:
                # Default unknown parts to leaves
                data["leaves"].append({"status": p.status, "confidence": p.confidence})

        # Run aggregator
        agg = aggregator.aggregate_health_robust(data)
        
        # Update tree with final health
        crud.update_tree_health(
            db=db,
            tree_id=t.id, 
            final_health=agg["final_tree_health"], 
            final_status=agg["final_status"], 
            critical_alert=agg["critical_alert"]
        )

    return JSONResponse({
        "survey_id": survey_id, 
        "processed": len(results), 
        "results": results
    })


@router.post("/sideview/update-tree")
async def update_single_tree_health(
    farmer_id: int = Form(...),
    survey_id: int = Form(...),
    tree_number: int = Form(...),
    part_name: str = Form(...),  # stem, bud, or leaves
    status: str = Form(...),  # healthy, unhealthy, critical, etc.
    confidence: float = Form(...),
    db: Session = Depends(get_db)
):
    """
    Update health data for a single tree part (one by one updates).
    After updating, regenerates the annotated image with updated colors.
    Requires farmer_id for authorization.
    """
    from db.models import Tree
    
    # Validate inputs
    tree_number = validate_tree_number(tree_number)
    part_name = validate_part_name(part_name)
    status = validate_status(status)
    confidence = validate_confidence(confidence)
    
    survey = crud.get_survey(db, survey_id)
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    
    if survey.farmer_id != farmer_id:
        raise HTTPException(status_code=403, detail="Farmer mismatch - survey belongs to different farmer")
    
    tree = db.query(Tree).filter(Tree.survey_id == survey_id, Tree.tree_number == tree_number).first()
    if not tree:
        raise HTTPException(status_code=404, detail=f"Tree #{tree_number} not found in survey")
    
    # Add tree part
    crud.add_tree_part(
        db=db,
        tree_id=tree.id,
        part_name=part_name,
        status=status,
        confidence=confidence
    )
    
    # Get all parts for this tree and aggregate
    parts = crud.get_parts_for_tree(db, tree.id)
    data = {"stem": [], "bud": [], "leaves": []}
    for p in parts:
        if p.part_name in data:
            data[p.part_name].append({"status": p.status, "confidence": p.confidence})
    
    # Run aggregator
    agg = aggregator.aggregate_health_robust(data)
    
    # Update tree health
    crud.update_tree_health(
        db=db,
        tree_id=tree.id,
        final_health=agg["final_tree_health"],
        final_status=agg["final_status"],
        critical_alert=agg["critical_alert"]
    )
    
    # Regenerate annotated image with updated colors
    if survey.topview_image_path and os.path.exists(survey.topview_image_path):
        # Read original image
        original_path = survey.topview_image_path.replace("topview_annotated.jpg", "topview_raw.jpg")
        if os.path.exists(original_path):
            img = cv2.imread(original_path)
            if img is not None:
                # Get all trees with their health status
                all_trees = db.query(Tree).filter(Tree.survey_id == survey_id).order_by(Tree.tree_number).all()
                centroids = []
                for t in all_trees:
                    centroids.append({
                        "cx": t.cx,
                        "cy": t.cy,
                        "tree_number": t.tree_number,
                        "final_status": t.final_status,
                        "critical_alert": t.critical_alert
                    })

                # Redraw with updated colors and larger pins for visibility
                annotated_img = draw_overlay(img, centroids, pin_radius=60)
                cv2.imwrite(survey.topview_image_path, annotated_img)
    
    return {
        "message": "Tree health updated successfully",
        "survey_id": survey_id,
        "tree_number": tree_number,
        "part_name": part_name,
        "final_status": agg["final_status"],
        "final_health": agg["final_tree_health"],
        "critical_alert": agg["critical_alert"],
        "annotated_image_updated": True
    }


@router.post("/sideview/mock")
async def mock_sideview_analysis(
    farmer_id: int = Form(...),
    survey_id: int = Form(...),
    tree_number: int = Form(...),
    status: str = Form(...),
    confidence: float = Form(...),
    part_name: str = Form("stem"),  # Default to stem
    db: Session = Depends(get_db)
):
    """
    Mock endpoint for testing tree health updates without actual video processing.
    Updates one tree at a time and regenerates the annotated image.
    Requires farmer_id for authorization.
    """
    # Validate inputs
    tree_number = validate_tree_number(tree_number)
    part_name = validate_part_name(part_name)
    status = validate_status(status)
    confidence = validate_confidence(confidence)
    
    return await update_single_tree_health(
        farmer_id=farmer_id,
        survey_id=survey_id,
        tree_number=tree_number,
        part_name=part_name,
        status=status,
        confidence=confidence,
        db=db
    )


@router.post("/sideview/mock-batch")
async def mock_sideview_batch(
    farmer_id: int = Form(...),
    survey_id: int = Form(...),
    db: Session = Depends(get_db),
    trees_json: str = Form(...)
):
    """
    Mock endpoint for batch testing - update multiple trees at once.
    Requires farmer_id for authorization.
    
    trees_json format can be:
    [
      {"tree_number": 1, "part_name": "stem", "status": "healthy", "confidence": 0.92},
      {"tree_number": 2, "part_name": "bud", "status": "bud_rot", "confidence": 0.95}
    ]
    OR:
    {
      "survey_id": 1,
      "trees": [
        {"tree_number": 1, "part_name": "stem", "status": "healthy", "confidence": 0.92},
        ...
      ]
    }
    """
    import json
    from db.models import Tree
    
    survey = crud.get_survey(db, survey_id)
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    
    if survey.farmer_id != farmer_id:
        raise HTTPException(status_code=403, detail="Farmer mismatch - survey belongs to different farmer")
    
    try:
        parsed = json.loads(trees_json)
        # Handle both flat array and wrapped format
        if isinstance(parsed, dict) and "trees" in parsed:
            trees_data = parsed["trees"]
        else:
            trees_data = parsed
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON in trees_json: {str(e)}")
    
    if not trees_data:
        raise HTTPException(status_code=400, detail="trees array is required")
    
    results = []
    updated_tree_ids = set()
    
    # Process each tree part update
    for item in trees_data:
        tree_number = item.get("tree_number")
        part_name = item.get("part_name", "stem")
        status = item.get("status")
        confidence = item.get("confidence", 0.0)
        
        # Validate inputs - use try/except to catch validation errors
        try:
            if not tree_number:
                raise HTTPException(status_code=400, detail="tree_number is required")
            if not status:
                raise HTTPException(status_code=400, detail="status is required")
            
            tree_number = validate_tree_number(tree_number)
            part_name = validate_part_name(part_name)
            status = validate_status(status)
            confidence = validate_confidence(confidence)
            
        except HTTPException as ve:
            # Validation error - add to results but continue
            results.append({
                "error": ve.detail,
                "item": item,
                "tree_number": tree_number
            })
            continue
        except Exception as e:
            # Catch unexpected errors during processing of a single item
            results.append({
                "error": f"Unexpected error: {str(e)}",
                "item": item,
                "tree_number": tree_number
            })
            continue
        
        tree = db.query(Tree).filter(
            Tree.survey_id == survey_id,
            Tree.tree_number == tree_number
        ).first()
        
        if not tree:
            results.append({"error": f"Tree #{tree_number} not found", "tree_number": tree_number})
            continue
        
        # Add tree part
        crud.add_tree_part(
            db=db,
            tree_id=tree.id,
            part_name=part_name,
            status=status,
            confidence=confidence
        )
        
        updated_tree_ids.add(tree.id)
        results.append({
            "tree_number": tree_number,
            "part_name": part_name,
            "status": status,
            "confidence": confidence,
            "success": True
        })
    
    # Aggregate health for all updated trees
    aggregated = []
    for tree_id in updated_tree_ids:
        tree = db.get(Tree, tree_id)
        parts = crud.get_parts_for_tree(db, tree_id)
        
        # Convert to aggregator format
        data_agg = {"stem": [], "bud": [], "leaves": []}
        for p in parts:
            if p.part_name in data_agg:
                data_agg[p.part_name].append({"status": p.status, "confidence": p.confidence})
        
        # Run aggregator
        agg = aggregator.aggregate_health_robust(data_agg)
        
        # Update tree health
        crud.update_tree_health(
            db=db,
            tree_id=tree_id,
            final_health=agg["final_tree_health"],
            final_status=agg["final_status"],
            critical_alert=agg["critical_alert"]
        )
        
        aggregated.append({
            "tree_number": tree.tree_number,
            "final_status": agg["final_status"],
            "final_health": agg["final_tree_health"],
            "critical_alert": agg["critical_alert"]
        })
    
    # Regenerate annotated image with updated colors
    if survey.topview_image_path and os.path.exists(survey.topview_image_path):
        original_path = survey.topview_image_path.replace("topview_annotated.jpg", "topview_raw.jpg")
        if os.path.exists(original_path):
            img = cv2.imread(original_path)
            if img is not None:
                all_trees = db.query(Tree).filter(Tree.survey_id == survey_id).order_by(Tree.tree_number).all()
                centroids = []
                for t in all_trees:
                    centroids.append({
                        "cx": t.cx,
                        "cy": t.cy,
                        "tree_number": t.tree_number,
                        "final_status": t.final_status,
                        "critical_alert": t.critical_alert
                    })
                annotated_img = draw_overlay(img, centroids, pin_radius=60)
                cv2.imwrite(survey.topview_image_path, annotated_img)
    
    return {
        "message": "Batch mock analysis completed",
        "survey_id": survey_id,
        "processed_parts": len(results),
        "updated_trees": len(updated_tree_ids),
        "results": results,
        "aggregated_health": aggregated,
        "annotated_image_updated": True,
        "image_url": f"/api/drone/{farmer_id}/{survey_id}/image"
    }


@router.get("/{farmer_id}/{survey_id}/annotated-image")
def get_annotated_image_info(farmer_id: int, survey_id: int, db: Session = Depends(get_db)):
    """
    Get the path to the latest annotated topview image with health-colored pins.
    Requires farmer_id for authorization.
    """
    survey = crud.get_survey(db, survey_id)
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    
    if survey.farmer_id != farmer_id:
        raise HTTPException(status_code=403, detail="Farmer mismatch - survey belongs to different farmer")
    
    if not survey.topview_image_path:
        raise HTTPException(status_code=404, detail="No annotated image found for this survey")
    
    return {
        "survey_id": survey_id,
        "annotated_image_path": survey.topview_image_path,
        "annotated_image_url": f"/api/drone/{farmer_id}/{survey_id}/image",
        "total_trees": survey.total_trees
    }


@router.get("/{farmer_id}/{survey_id}/image")
def serve_annotated_image(farmer_id: int, survey_id: int, db: Session = Depends(get_db)):
    """
    Serve the annotated topview image with big colored pins showing tree health.
    Access this directly in browser or <img> tag.
    Requires farmer_id for authorization.
    """
    from fastapi.responses import FileResponse
    
    survey = crud.get_survey(db, survey_id)
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    
    if survey.farmer_id != farmer_id:
        raise HTTPException(status_code=403, detail="Farmer mismatch - survey belongs to different farmer")
    
    if not survey.topview_image_path or not os.path.exists(survey.topview_image_path):
        raise HTTPException(status_code=404, detail="Annotated image not found")
    
    return FileResponse(
        survey.topview_image_path,
        media_type="image/jpeg",
        headers={"Content-Disposition": f"inline; filename=survey_{survey_id}_annotated.jpg"}
    )


@router.get("/{farmer_id}/{survey_id}/tree/{tree_number}/recommendation")
def get_tree_recommendation(
    farmer_id: int, 
    survey_id: int, 
    tree_number: int, 
    db: Session = Depends(get_db)
):
    """
    Get comprehensive treatment recommendation for a specific tree.
    Returns full treatment plan (all severity levels combined) for detected diseases.
    Skips recommendations for 'unknown' status trees.
    Requires farmer_id for authorization.
    """
    from db.models import Tree
    from recommendation import get_simple_recommendation
    
    # Validate survey and farmer
    survey = crud.get_survey(db, survey_id)
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    
    if survey.farmer_id != farmer_id:
        raise HTTPException(status_code=403, detail="Farmer mismatch - survey belongs to different farmer")
    
    # Get tree by number
    tree = db.query(Tree).filter(
        Tree.survey_id == survey_id,
        Tree.tree_number == tree_number
    ).first()
    
    if not tree:
        raise HTTPException(status_code=404, detail=f"Tree #{tree_number} not found in survey")
    
    # Skip recommendations for unknown status
    if not tree.final_status or tree.final_status.lower() == "unknown":
        return {
            "tree_number": tree_number,
            "status": "unknown",
            "message": "Health status unknown - recommendation not available",
            "recommendation": None
        }
    
    # Get tree parts to determine affected part and disease
    parts = crud.get_parts_for_tree(db, tree.id)
    
    if not parts:
        # No part data - return basic recommendation based on final_status
        if tree.final_status.lower() == "healthy":
            rec = get_simple_recommendation("healthy", part="tree")
        else:
            # No specific disease info, return general unhealthy recommendation
            return {
                "tree_number": tree_number,
                "status": tree.final_status,
                "health_percentage": tree.final_health_percentage,
                "message": "No detailed analysis available yet",
                "recommendation": None
            }
    else:
        # Find the most critical part (lowest health/highest severity)
        critical_part = None
        for p in parts:
            if p.status and p.status.lower() != "healthy":
                critical_part = p
                break
        
        if not critical_part:
            # All parts healthy
            critical_part = parts[0]
        
        # Generate recommendation based on the critical part
        # Construct label in format: part_disease (e.g., "leaves_Grey_leaf_rot")
        if critical_part.status.lower() == "healthy":
            predicted_label = "healthy"
        else:
            # Use the status as disease name with part prefix
            predicted_label = f"{critical_part.part_name}_{critical_part.status}"
        
        rec = get_simple_recommendation(predicted_label, part=critical_part.part_name)
    
    return {
        "tree_number": tree_number,
        "tree_uuid": tree.tree_uuid,
        "status": tree.final_status,
        "health_percentage": tree.final_health_percentage,
        "critical_alert": tree.critical_alert,
        "recommendation": rec
    }

