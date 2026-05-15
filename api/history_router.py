# backend/api/history_router.py
"""
Analysis History API - Stores and retrieves analysis history from PostgreSQL.
Replaces local SQLite storage in Flutter app.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from db.database import get_db
from db.models import AnalysisHistory, Farmer

router = APIRouter(prefix="/api/history", tags=["History"])


# ============== Pydantic Schemas ==============

class HistoryCreate(BaseModel):
    """Schema for creating a new history entry"""
    farmer_id: Optional[int] = None
    image_path: str
    analysis_type: str = "image"  # "image" or "video"
    score: float
    label: str
    part: Optional[str] = None
    status: Optional[str] = None
    part_confidence: Optional[float] = None
    status_confidence: Optional[float] = None
    recommendation_summary: Optional[str] = None
    result_data: Optional[dict] = None


class HistoryResponse(BaseModel):
    """Schema for history response"""
    id: int
    farmer_id: Optional[int]
    image_path: str
    analysis_type: str
    score: float
    label: str
    part: Optional[str]
    status: Optional[str]
    part_confidence: Optional[float]
    status_confidence: Optional[float]
    recommendation_summary: Optional[str]
    result_data: Optional[dict]
    created_at: datetime

    class Config:
        from_attributes = True


# ============== API Endpoints ==============

@router.post("/create", response_model=HistoryResponse)
def create_history(data: HistoryCreate, db: Session = Depends(get_db)):
    """
    Create a new analysis history entry.
    Called after each sideview/sidevideo analysis in the Flutter app.
    """
    # Validate farmer_id if provided
    if data.farmer_id:
        farmer = db.get(Farmer, data.farmer_id)
        if not farmer:
            raise HTTPException(status_code=404, detail="Farmer not found")
    
    history_entry = AnalysisHistory(
        farmer_id=data.farmer_id,
        image_path=data.image_path,
        analysis_type=data.analysis_type,
        score=data.score,
        label=data.label,
        part=data.part,
        status=data.status,
        part_confidence=data.part_confidence,
        status_confidence=data.status_confidence,
        recommendation_summary=data.recommendation_summary,
        result_data=data.result_data,
    )
    
    db.add(history_entry)
    db.commit()
    db.refresh(history_entry)
    
    return history_entry


@router.get("/all", response_model=List[HistoryResponse])
def get_all_history(
    farmer_id: Optional[int] = Query(None, description="Filter by farmer ID"),
    analysis_type: Optional[str] = Query(None, description="Filter by type: image or video"),
    limit: int = Query(100, le=500, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: Session = Depends(get_db)
):
    """
    Get all analysis history entries, optionally filtered by farmer or type.
    Results are sorted by created_at descending (newest first).
    """
    query = db.query(AnalysisHistory)
    
    if farmer_id is not None:
        query = query.filter(AnalysisHistory.farmer_id == farmer_id)
    
    if analysis_type is not None:
        query = query.filter(AnalysisHistory.analysis_type == analysis_type)
    
    history = query.order_by(AnalysisHistory.created_at.desc()).offset(offset).limit(limit).all()
    
    return history


@router.get("/{history_id}", response_model=HistoryResponse)
def get_history_by_id(history_id: int, db: Session = Depends(get_db)):
    """Get a specific history entry by ID"""
    history = db.get(AnalysisHistory, history_id)
    if not history:
        raise HTTPException(status_code=404, detail="History entry not found")
    return history


@router.delete("/{history_id}")
def delete_history(history_id: int, db: Session = Depends(get_db)):
    """Delete a history entry by ID"""
    history = db.get(AnalysisHistory, history_id)
    if not history:
        raise HTTPException(status_code=404, detail="History entry not found")
    
    db.delete(history)
    db.commit()
    
    return {"message": "History entry deleted successfully", "id": history_id}


@router.delete("/farmer/{farmer_id}")
def delete_farmer_history(farmer_id: int, db: Session = Depends(get_db)):
    """Delete all history entries for a specific farmer"""
    deleted_count = db.query(AnalysisHistory).filter(
        AnalysisHistory.farmer_id == farmer_id
    ).delete()
    db.commit()
    
    return {"message": f"Deleted {deleted_count} history entries for farmer {farmer_id}"}


@router.get("/farmer/{farmer_id}/stats")
def get_farmer_stats(farmer_id: int, db: Session = Depends(get_db)):
    """Get analysis statistics for a farmer"""
    from sqlalchemy import func
    
    total = db.query(func.count(AnalysisHistory.id)).filter(
        AnalysisHistory.farmer_id == farmer_id
    ).scalar()
    
    healthy_count = db.query(func.count(AnalysisHistory.id)).filter(
        AnalysisHistory.farmer_id == farmer_id,
        AnalysisHistory.label.ilike('%healthy%')
    ).scalar()
    
    avg_score = db.query(func.avg(AnalysisHistory.score)).filter(
        AnalysisHistory.farmer_id == farmer_id
    ).scalar()
    
    return {
        "farmer_id": farmer_id,
        "total_analyses": total,
        "healthy_count": healthy_count,
        "unhealthy_count": total - healthy_count if total else 0,
        "average_score": round(avg_score, 2) if avg_score else 0,
    }
