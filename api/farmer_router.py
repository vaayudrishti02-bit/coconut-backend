# backend/api/farmer_router.py
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from db.database import get_db
from db import crud

router = APIRouter(prefix="/api/farmer", tags=["Farmer"])


class FarmerCreate(BaseModel):
    name: str
    phone: str | None = None
    email: str | None = None
    onboarding_completed: bool | None = None


@router.post("/create")
def create_farmer(data: FarmerCreate, db: Session = Depends(get_db)):
    """Create a new farmer or return existing one"""
    # Normalize empty strings to None
    phone = data.phone.strip() if data.phone else None
    if phone == "":
        phone = None
    # Normalize email: strip whitespace and convert to lowercase for consistent lookups
    email = data.email.strip().lower() if data.email else None
    if email == "":
        email = None
    
    # Try to find existing farmer by email first (preferred), then phone
    farmer = None
    
    if email:
        farmer = crud.get_farmer_by_email(db, email)
    if farmer is None and phone:
        farmer = crud.get_farmer_by_phone(db, phone)
    
    if farmer is None:
        # Create new farmer - they need to complete onboarding
        farmer = crud.create_farmer(db=db, name=data.name, phone=phone, email=email)
    else:
        # Existing user - update their info if needed
        if phone and not farmer.phone:
            farmer.phone = phone
        if email and not farmer.email:
            farmer.email = email
        if data.name and farmer.name != data.name:
            farmer.name = data.name
        # Update onboarding_completed if explicitly provided (from farm details screen)
        if data.onboarding_completed is not None:
            farmer.onboarding_completed = data.onboarding_completed
        db.commit()
        db.refresh(farmer)
    
    # Return the actual onboarding_completed value from database
    # This ensures consistent behavior across logins
    return {
        "id": farmer.id, 
        "name": farmer.name, 
        "phone": farmer.phone,
        "email": farmer.email,
        "onboarding_completed": farmer.onboarding_completed,  # Use actual DB value
        "created_at": farmer.created_at
    }


@router.get("/all")
def get_all_farmers(db: Session = Depends(get_db)):
    """Get all farmers"""
    from db.models import Farmer
    farmers = db.query(Farmer).all()
    return [
        {
            "id": f.id,
            "name": f.name,
            "phone": f.phone,
            "email": f.email,
            "onboarding_completed": f.onboarding_completed,
            "created_at": f.created_at,
            "total_surveys": len(f.surveys)
        }
        for f in farmers
    ]


@router.get("/by-email/{email}")
def get_farmer_by_email(email: str, db: Session = Depends(get_db)):
    """Get farmer by email address"""
    farmer = crud.get_farmer_by_email(db, email)
    if not farmer:
        raise HTTPException(status_code=404, detail="Farmer not found")
    
    return {
        "id": farmer.id,
        "name": farmer.name,
        "phone": farmer.phone,
        "email": farmer.email,
        "onboarding_completed": farmer.onboarding_completed,
        "created_at": farmer.created_at,
        "total_surveys": len(farmer.surveys)
    }


@router.get("/{farmer_id}")
def get_farmer(farmer_id: int, db: Session = Depends(get_db)):
    """Get specific farmer details"""
    farmer = crud.get_farmer(db, farmer_id)
    if not farmer:
        raise HTTPException(status_code=404, detail="Farmer not found")
    
    return {
        "id": farmer.id,
        "name": farmer.name,
        "phone": farmer.phone,
        "email": farmer.email,
        "onboarding_completed": farmer.onboarding_completed,
        "created_at": farmer.created_at,
        "total_surveys": len(farmer.surveys)
    }


@router.delete("/{farmer_id}")
def delete_farmer(farmer_id: int, db: Session = Depends(get_db)):
    """Delete a farmer and all their surveys"""
    from db.models import Farmer
    farmer = db.query(Farmer).filter(Farmer.id == farmer_id).first()
    if not farmer:
        raise HTTPException(status_code=404, detail="Farmer not found")
    
    farmer_name = farmer.name
    db.delete(farmer)
    db.commit()
    
    return {"message": f"Farmer '{farmer_name}' deleted successfully", "farmer_id": farmer_id}


@router.get("/{farmer_id}/surveys")
def list_surveys(farmer_id: int, db: Session = Depends(get_db)):
    """Get all surveys for a farmer"""
    farmer = crud.get_farmer(db, farmer_id)
    if not farmer:
        raise HTTPException(status_code=404, detail="Farmer not found")

    return [
        {
            "survey_id": s.id,
            "farmer_id": farmer_id,
            "location": s.land_location,
            "land_location": s.land_location,
            "total_trees": s.total_trees,
            "topview_image": s.topview_image_path,
            "topview_image_path": s.topview_image_path,
            "created_at": s.created_at
        }
        for s in farmer.surveys
    ]
