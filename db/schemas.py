from pydantic import BaseModel
from typing import List, Optional


class FarmerCreate(BaseModel):
    name: str
    phone: str


class FarmerOut(BaseModel):
    id: int
    name: str
    phone: str
    class Config:
        orm_mode = True


class SurveyCreate(BaseModel):
    farmer_id: int
    land_location: str
    total_trees: int


class SurveyOut(BaseModel):
    id: int
    farmer_id: int
    land_location: str
    total_trees: int
    class Config:
        orm_mode = True


class TreePartCreate(BaseModel):
    part_name: str
    health_percentage: float
    top_disease: Optional[str]
    confidence: float


class TreePartOut(TreePartCreate):
    id: int
    class Config:
        orm_mode = True


class TreeCreate(BaseModel):
    survey_id: int
    tree_number: int
    final_status: str
    final_health_percentage: float
    critical_alert: bool
    cx: Optional[int] = None
    cy: Optional[int] = None
    parts: List[TreePartCreate]


class TreeOut(BaseModel):
    id: int
    tree_number: int
    final_status: str
    final_health_percentage: float
    critical_alert: bool
    cx: Optional[int] = None
    cy: Optional[int] = None
    parts: List[TreePartOut]
    class Config:
        orm_mode = True
