from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List

from db.database import get_db
from db import crud
# Import services if needed (assumed available or needs migration)
# from Deekshith.survey.service import SurveyService 

router = APIRouter(prefix="/api/survey", tags=["Survey Management"])

class SurveyStart(BaseModel):
    farmer_id: int
    land_location: Optional[str] = None

class TreeAdd(BaseModel):
    tree_number: int
    cx: float
    cy: float

@router.post("/start")
def start_survey(body: SurveyStart, db: Session = Depends(get_db)):
    """
    Create a new survey for a farmer
    """
    # Verify farmer exists
    farmer = crud.get_farmer(db, body.farmer_id)
    if not farmer:
        raise HTTPException(status_code=404, detail=f"Farmer {body.farmer_id} not found")
    
    survey = crud.create_survey(db, body.farmer_id, body.land_location)
    return {
        "survey_id": survey.id,
        "farmer_id": survey.farmer_id,
        "land_location": survey.land_location,
        "created_at": survey.created_at
    }

@router.post("/{survey_id}/add-tree")
def add_tree_manually(survey_id: int, body: TreeAdd, db: Session = Depends(get_db)):
    """
    Manually add a tree to a survey (for testing without drone upload)
    """
    # Verify survey exists
    survey = crud.get_survey(db, survey_id)
    if not survey:
        raise HTTPException(status_code=404, detail=f"Survey {survey_id} not found")
    
    # Create tree
    tree = crud.create_tree(db, survey_id, body.tree_number, body.cx, body.cy)
    
    return {
        "tree_id": tree.id,
        "survey_id": survey_id,
        "tree_number": tree.tree_number,
        "cx": tree.cx,
        "cy": tree.cy,
        "created_at": tree.created_at
    }

@router.delete("/{farmer_id}/survey/{survey_id}")
def delete_survey(farmer_id: int, survey_id: int, db: Session = Depends(get_db)):
    """
    Delete a specific survey belonging to a farmer.
    Removes DB row and both API uploads dir and Deekshith storage dir so no orphaned files.
    """
    from pathlib import Path
    import shutil
    from db.models import Survey

    survey = db.query(Survey).filter(Survey.id == survey_id, Survey.farmer_id == farmer_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found for this farmer")

    # Delete API uploads dir (api/drone flow)
    survey_dir = Path(__file__).resolve().parent.parent / "uploads" / "surveys" / str(survey_id)
    if survey_dir.exists():
        shutil.rmtree(survey_dir)

    # Delete Deekshith storage dir (survey create + topview/tree flow)
    deekshith_survey = Path(__file__).resolve().parent.parent / "Deekshith" / "storage" / "surveys" / f"SURVEY_{survey_id}"
    if deekshith_survey.exists():
        shutil.rmtree(deekshith_survey)

    db.delete(survey)
    db.commit()

    return {"message": f"Survey {survey_id} deleted successfully", "survey_id": survey_id, "farmer_id": farmer_id}


@router.delete("/{survey_id}/tree/{tree_id}")
def delete_tree(survey_id: int, tree_id: int, db: Session = Depends(get_db)):
    """
    Delete a specific tree from a survey. The tree number becomes available for reuse.
    """
    from db.models import Tree
    import os
    import cv2
    # from topview.model import draw_overlay # Keep imports local if needed
    
    tree = db.query(Tree).filter(Tree.id == tree_id, Tree.survey_id == survey_id).first()
    if not tree:
        raise HTTPException(status_code=404, detail="Tree not found")
    
    deleted_tree_number = tree.tree_number
    
    db.delete(tree)
    # Update survey total_trees count
    survey = crud.get_survey(db, survey_id)
    if survey:
        remaining_count = db.query(Tree).filter(Tree.survey_id == survey_id).count()
        survey.total_trees = remaining_count
    
    db.commit()
    
    return {
        "message": f"Tree #{deleted_tree_number} deleted",
        "tree_id": tree_id,
        "deleted_tree_number": deleted_tree_number
    }


def _parts_from_dashboard_json(dashboard_data):
    """Build API-style parts list from dashboard_data (formerly dashboard_json)."""
    if not dashboard_data:
        return []
    parts_dict = dashboard_data.get("parts") or {}
    result = []
    for k, v in parts_dict.items():
        if not isinstance(v, dict):
            continue
        # Get status from 'health' field (video analysis) or 'status' field (image analysis)
        status = v.get("health") or v.get("status")
        # Get disease name if unhealthy
        diseases = v.get("diseases", {})
        if diseases and status not in ("healthy", "unknown"):
            # Use the disease name as status for better disease insights
            disease_name = list(diseases.keys())[0] if diseases else status
            status = disease_name
        result.append({
            "part_name": k,
            "status": status,
            "confidence": float(v.get("avg_status_confidence", v.get("confidence", 0))) if v else None,
            "extra": v,
            "timestamp": None,
        })
    return result


@router.get("/{survey_id}/trees")
def get_survey_trees(survey_id: int, db: Session = Depends(get_db)):
    """
    Get all trees in a survey with their health data and parts.
    Fully unified to use single Tree table.
    """
    survey = crud.get_survey(db, survey_id)
    if not survey:
        raise HTTPException(status_code=404, detail=f"Survey {survey_id} not found")

    from db.models import Tree
    trees = db.query(Tree).filter(Tree.survey_id == survey_id).order_by(Tree.tree_number).all()

    result = []
    for tree in trees:
        # Prefer direct parts first
        parts = crud.get_parts_for_tree(db, tree.id)
        if parts:
            parts_payload = [
                {"part_name": p.part_name, "status": p.status, "confidence": p.confidence, "extra": p.extra, "timestamp": p.timestamp}
                for p in parts
            ]
        else:
            # Fallback to dashboard_data if parts table empty (migration case)
            parts_payload = _parts_from_dashboard_json(tree.dashboard_data)

        result.append({
            "tree_id": tree.id,
            "tree_number": tree.tree_number,
            "cx": tree.cx,
            "cy": tree.cy,
            "final_status": tree.final_status,
            "final_health_percentage": tree.final_health_percentage,
            "critical_alert": tree.critical_alert,
            "parts": parts_payload,
            "created_at": tree.created_at
        })
    
    return {"survey_id": survey_id, "total_trees": survey.total_trees, "trees": result}


@router.get("/{survey_id}/report")
def get_survey_report(survey_id: int, db: Session = Depends(get_db)):
    """
    Generate comprehensive survey report using Unified Tree Data.
    """
    survey = crud.get_survey(db, survey_id)
    if not survey:
        raise HTTPException(status_code=404, detail=f"Survey {survey_id} not found")

    from db.models import Tree
    trees = db.query(Tree).filter(Tree.survey_id == survey_id).all()

    if not trees:
        return {
            "survey_id": survey_id,
            "farmer_id": survey.farmer_id,
            "land_location": survey.land_location,
            "total_trees": survey.total_trees,
            "trees_analyzed": 0,
            "healthy_count": 0,
            "unhealthy_count": 0,
            "critical_count": 0,
            "average_health_percentage": 0.0,
            "overall_status": "unknown",
            "topview_image_path": survey.topview_image_path,
            "created_at": survey.created_at,
            "message": "No trees analyzed yet"
        }

    # Tree table has data (Unified source)
    total = len(trees)
    
    # Logic: Status is case insensitive, None/empty means not analyzed yet
    def get_status(t):
        return (t.final_status or "").lower()
    
    # Only count trees that have been analyzed (have a status)
    analyzed_trees = [t for t in trees if t.final_status is not None and t.final_status != ""]
    trees_analyzed = len(analyzed_trees)

    healthy_count = sum(1 for t in analyzed_trees if get_status(t) == "healthy")
    # Unhealthy: NOT healthy (includes all disease statuses)
    unhealthy_count = sum(1 for t in analyzed_trees if get_status(t) != "healthy")
    
    valid_health = [t.final_health_percentage for t in trees if t.final_health_percentage is not None]
    avg_health = sum(valid_health) / len(valid_health) if valid_health else 0.0
    
    if trees_analyzed == 0:
        overall_status = "pending"
    elif unhealthy_count > healthy_count:
        overall_status = "unhealthy"
    else:
        overall_status = "healthy"
        
    return {
        "survey_id": survey_id,
        "farmer_id": survey.farmer_id,
        "land_location": survey.land_location,
        "total_trees": total,  # All trees in survey (detected from topviews)
        "trees_analyzed": trees_analyzed,  # Trees with sideview analysis completed
        "healthy_count": healthy_count,
        "unhealthy_count": unhealthy_count,
        "critical_count": 0,  # Deprecated - always 0
        "average_health_percentage": round(avg_health, 2),
        "overall_status": overall_status,
        "topview_image_path": survey.topview_image_path,
        "created_at": survey.created_at
    }


# --- Migrated from Deekshith/Router ---
@router.post("/{survey_id}/dashboard-gen")
async def generate_final_dashboard(survey_id: int, db: Session = Depends(get_db)):
    """
    Generate final survey-level dashboard by aggregating all topview dashboards.
    Unified version that looks at Tree table instead of snapshots if possible.
    """
    # Logic to aggregate tree data would go here.
    # For now, just return success to indicate endpoint exists.
    return {"message": "Dashboard generation triggered (Unified)", "survey_id": survey_id}

# --- Standardized List ---
@router.get("/list")
async def list_all_surveys(db: Session = Depends(get_db)):
    """
    List all surveys. 
    """
    surveys_db = crud.get_all_surveys(db)
    surveys = [
        {
            "survey_id": s.id,
            "farmer_id": s.farmer_id,
            "land_location": s.land_location,
            "total_trees": s.total_trees,
            "topview_image_path": s.topview_image_path,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in surveys_db
    ]
    return {"surveys": surveys, "total": len(surveys)}
