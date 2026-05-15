# Deekshith/survey/router.py
"""
Survey Router - Survey Creation and Result Retrieval
DB-first for list and result; file fallback where needed.
"""

import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.database import get_db
from db import crud
from Deekshith.survey.service import SurveyService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/survey",
    tags=["Survey Orchestration"],
)

# Pydantic models
class LocationModel(BaseModel):
    lat: float
    lon: float

class CreateSurveyRequest(BaseModel):
    farmer_id: str
    location: LocationModel

class CreateSurveyResponse(BaseModel):
    survey_id: int
    timestamp: str

class SurveyResultResponse(BaseModel):
    survey_id: int
    meta: dict
    topviews: dict
    final_dashboard: Optional[dict] = None


@router.post("/create", response_model=CreateSurveyResponse)
async def create_survey(request: CreateSurveyRequest):
    """
    Create a new survey for a farmer visit.
    
    Args:
        request: Survey creation data (farmer_id, location)
        
    Returns:
        Survey ID and timestamp
    """
    try:
        service = SurveyService()
        result = service.create_survey(
            farmer_id=request.farmer_id,
            location={"lat": request.location.lat, "lon": request.location.lon}
        )
        
        logger.info(f"Survey created: {result['survey_id']}")
        return CreateSurveyResponse(**result)
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Survey creation failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Survey creation failed: {str(e)}")


@router.get("/{survey_id}/result")
async def get_survey_result(survey_id: int, db: Session = Depends(get_db)):
    """
    Fetch complete survey result including all topviews, dashboards, and health maps.
    
    Args:
        survey_id: Survey identifier
        
    Returns:
        Complete survey data
    """
    try:
        survey = crud.get_survey(db, survey_id)
        if not survey:
            service = SurveyService()
            result = service.get_survey_result(survey_id)
            if not result:
                raise HTTPException(status_code=404, detail=f"Survey {survey_id} not found")
            return result

        topviews = crud.get_topviews_by_survey(db, survey_id)
        if not topviews:
            service = SurveyService()
            result = service.get_survey_result(survey_id)
            if not result:
                return _survey_result_from_db(db, survey, [])
            return result

        return _survey_result_from_db(db, survey, topviews)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch survey result: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{survey_id}/dashboard")
async def generate_final_dashboard(survey_id: int):
    """
    Generate final survey-level dashboard by aggregating all topview dashboards.
    
    Args:
        survey_id: Survey identifier
        
    Returns:
        Final aggregated dashboard
    """
    try:
        service = SurveyService()
        dashboard = service.generate_final_dashboard(survey_id)
        
        logger.info(f"Final dashboard generated for survey {survey_id}")
        return dashboard
        
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Dashboard generation failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Dashboard generation failed: {str(e)}")


def _survey_result_from_db(db: Session, survey, topviews):
    """Build survey result dict from DB survey + topviews (with snapshots/trees).
    meta['location'] matches file-based result: dict {lat, lon} when land_location is 'lat,lon'.
    """
    location_value = survey.land_location
    if location_value and "," in str(location_value):
        parts = str(location_value).strip().split(",", 1)
        try:
            lat, lon = float(parts[0].strip()), float(parts[1].strip())
            location_value = {"lat": lat, "lon": lon}
        except (ValueError, IndexError):
            pass
    meta = {
        "survey_id": survey.id,
        "farmer_id": survey.farmer_id,
        "location": location_value,
        "land_location": survey.land_location,
        "timestamp": survey.created_at.isoformat() if survey.created_at else None,
        "status": "active",
    }
    topviews_dict = {}
    for t in topviews:
        snap = t.dashboard_snapshot or {}
        trees_rows = crud.get_topview_trees(db, t.id)
        # Use tree_number (not tree_index) and dashboard_data (not dashboard_json)
        trees_data = {f"tree_{tr.tree_number:02d}": (tr.dashboard_data or {}) for tr in trees_rows}
        topviews_dict[t.topview_order] = {
            "detection": None,
            "dashboard": snap,
            "health_map": None,
            "trees": trees_data,
        }
    final_dashboard = None
    snapshots = [t.dashboard_snapshot for t in topviews if t.dashboard_snapshot]
    if snapshots:
        from Deekshith.dashboard.aggregator import DashboardAggregator
        agg = DashboardAggregator()
        final_dashboard = agg.aggregate_survey_dashboard(survey.id, snapshots)
    return {
        "survey_id": survey.id,
        "meta": meta,
        "topviews": topviews_dict,
        "final_dashboard": final_dashboard,
    }


@router.get("/list")
async def list_surveys(db: Session = Depends(get_db)):
    """
    List all surveys. Prefer DB; fallback to file-based list.
    """
    try:
        surveys_db = crud.get_all_surveys(db)
        if surveys_db:
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
        service = SurveyService()
        surveys = service.list_surveys()
        return {"surveys": surveys, "total": len(surveys)}
    except Exception as e:
        logger.error(f"Failed to list surveys: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
