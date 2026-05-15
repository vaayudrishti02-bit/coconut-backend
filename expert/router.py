# backend/expert/router.py
"""
Expert Connect Router - For farmer-expert consultation requests
Sends email directly to deekshiaws@gmail.com when a ticket is created
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from datetime import datetime
from typing import Optional
import logging
import os
import uuid
import shutil

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/expert", tags=["Expert Connect"])

# Import email service
try:
    from utils.email_service import send_expert_request_email
    EMAIL_SERVICE_AVAILABLE = True
except ImportError:
    EMAIL_SERVICE_AVAILABLE = False
    logger.warning("Email service not available")


class TicketRequest(BaseModel):
    user_id: str
    farmer_name: str
    farmer_email: str
    farmer_phone: str
    category: str
    message: str
    image_url: Optional[str] = None


class Ticket(BaseModel):
    id: str
    user_id: str
    category: str
    message: str
    image_url: Optional[str] = None
    status: str
    created_at: str
    updated_at: str


# In-memory storage for demo (replace with database in production)
tickets_db = []

# Upload directory for expert consultation images
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads", "expert")
os.makedirs(UPLOAD_DIR, exist_ok=True)
logger.info(f"Expert uploads directory: {UPLOAD_DIR}")


@router.post("/upload-image")
async def upload_expert_image(file: UploadFile = File(...)):
    """
    Upload an image for expert consultation
    Returns the filename to be used when creating the ticket
    """
    try:
        # Validate file type
        if not file.content_type or not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="Only image files are allowed")
        
        # Generate unique filename
        file_extension = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = os.path.join(UPLOAD_DIR, unique_filename)
        
        # Save file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        logger.info(f"Uploaded expert image: {unique_filename}")
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "filename": unique_filename,
                "path": file_path,
                "message": "Image uploaded successfully"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error uploading image: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload image: {str(e)}"
        )


@router.post("/ticket")
async def create_ticket(ticket_request: TicketRequest):
    """
    Create a new expert consultation ticket and send email to company
    
    Args:
        ticket_request: Ticket details including farmer info, category, message
    
    Returns:
        Created ticket with ID and status
    """
    try:
        ticket_id = f"TKT{len(tickets_db) + 1:05d}"
        timestamp = datetime.utcnow().isoformat()
        
        ticket = {
            "id": ticket_id,
            "user_id": ticket_request.user_id,
            "farmer_name": ticket_request.farmer_name,
            "farmer_email": ticket_request.farmer_email,
            "farmer_phone": ticket_request.farmer_phone,
            "category": ticket_request.category,
            "message": ticket_request.message,
            "image_url": ticket_request.image_url,
            "status": "pending",
            "created_at": timestamp,
            "updated_at": timestamp
        }
        
        tickets_db.append(ticket)
        
        logger.info(f"Created expert ticket: {ticket_id} for user: {ticket_request.user_id}")
        
        # Send email notification with image attachment if provided
        email_result = {"email_sent": False, "message": "Email service not available"}
        if EMAIL_SERVICE_AVAILABLE:
            # If image_url is provided, construct the full path
            image_path = None
            if ticket_request.image_url:
                # image_url contains the filename from upload
                image_path = os.path.join(UPLOAD_DIR, ticket_request.image_url)
                logger.info(f"Looking for image at: {image_path}")
                if not os.path.exists(image_path):
                    logger.warning(f"Image file not found: {image_path}")
                    image_path = None
                else:
                    logger.info(f"Image file found: {image_path}, size: {os.path.getsize(image_path)} bytes")
            
            email_result = send_expert_request_email(
                farmer_name=ticket_request.farmer_name,
                farmer_email=ticket_request.farmer_email,
                farmer_phone=ticket_request.farmer_phone,
                category=ticket_request.category,
                issue_description=ticket_request.message,
                image_path=image_path
            )
            logger.info(f"Email result: {email_result}")
        
        return JSONResponse(
            status_code=201,
            content={
                "success": True,
                "ticket": ticket,
                "email_sent": email_result.get("email_sent", False),
                "message": "Expert consultation request submitted successfully! Our team will contact you within 24 hours."
            }
        )
        
    except Exception as e:
        logger.exception(f"Error creating ticket: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create ticket: {str(e)}"
        )


@router.get("/tickets/{user_id}")
async def get_user_tickets(user_id: str):
    """Get all tickets for a specific user"""
    try:
        user_tickets = [t for t in tickets_db if t["user_id"] == user_id]
        return JSONResponse(content={
            "success": True,
            "tickets": user_tickets,
            "count": len(user_tickets)
        })
    except Exception as e:
        logger.exception(f"Error fetching tickets: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch tickets: {str(e)}"
        )


@router.get("/ticket/{ticket_id}")
async def get_ticket(ticket_id: str):
    """Get specific ticket details"""
    try:
        ticket = next((t for t in tickets_db if t["id"] == ticket_id), None)
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")
        
        return JSONResponse(content={
            "success": True,
            "ticket": ticket
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error fetching ticket: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch ticket: {str(e)}"
        )
