"""Pydantic models for sideview endpoints"""
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class TreePartUpdate(BaseModel):
    """Single tree part health update."""
    tree_number: int = Field(..., gt=0, description="Tree number (must be positive)")
    part_name: str = Field(..., description="Part name: stem, bud, or leaves")
    status: str = Field(..., description="Health status")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score 0.0-1.0")
    
    @field_validator('part_name')
    @classmethod
    def normalize_part_name(cls, v):
        return v.lower().strip() if v else v
    
    @field_validator('status')
    @classmethod
    def normalize_status(cls, v):
        return v.lower().strip() if v else v


class UpdateTreeRequest(BaseModel):
    """Request body for POST /sideview/update-tree endpoint."""
    farmer_id: int = Field(..., description="Farmer ID for authorization")
    survey_id: int = Field(..., description="Survey ID")
    tree_number: int = Field(..., gt=0, description="Tree number (must be positive)")
    part_name: str = Field(..., description="Part name: stem, bud, or leaves")
    status: str = Field(..., description="Health status")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score 0.0-1.0")
    
    @field_validator('part_name')
    @classmethod
    def normalize_part_name(cls, v):
        return v.lower().strip() if v else v
    
    @field_validator('status')
    @classmethod
    def normalize_status(cls, v):
        return v.lower().strip() if v else v


class MockRequest(BaseModel):
    """Request body for POST /sideview/mock endpoint."""
    farmer_id: int = Field(..., description="Farmer ID for authorization")
    survey_id: int = Field(..., description="Survey ID")
    tree_number: int = Field(..., gt=0, description="Tree number (must be positive)")
    status: str = Field(..., description="Health status")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score 0.0-1.0")
    part_name: str = Field(default="stem", description="Part name: stem, bud, or leaves")
    
    @field_validator('part_name')
    @classmethod
    def normalize_part_name(cls, v):
        return v.lower().strip() if v else v
    
    @field_validator('status')
    @classmethod
    def normalize_status(cls, v):
        return v.lower().strip() if v else v


class BatchTreesRequest(BaseModel):
    """Request body for POST /sideview/mock-batch endpoint."""
    farmer_id: int = Field(..., description="Farmer ID for authorization")
    survey_id: int = Field(..., description="Survey ID")
    trees: List[TreePartUpdate] = Field(..., min_items=1, description="List of tree part updates")


class TreeHealthResponse(BaseModel):
    """Response for a single tree health update."""
    tree_number: int
    part_name: str
    status: str
    confidence: float
    success: bool = True


class TreeHealthError(BaseModel):
    """Error for a single tree in batch."""
    tree_number: Optional[int] = None
    error: str
    item: Optional[dict] = None


class AggregatedHealth(BaseModel):
    """Aggregated health for a tree."""
    tree_number: int
    final_status: str
    final_health: float
    critical_alert: bool


class BatchUpdateResponse(BaseModel):
    """Response for batch tree update."""
    message: str
    survey_id: int
    processed_parts: int
    updated_trees: int
    results: List[dict]  # Mixed success/error dicts
    aggregated_health: List[AggregatedHealth]
    annotated_image_updated: bool
    image_url: str


class HealthCheckResponse(BaseModel):
    """Health check response."""
    status: str = "healthy"
    timestamp: str
    version: str
    models: dict
