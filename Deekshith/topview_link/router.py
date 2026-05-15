# Deekshith/topview_link/router.py
"""
Topview Link Router - Connects survey system to topview detection

SECURITY ANNOTATIONS:
    All endpoints marked with security requirements for future auth integration.
    @public - No authentication required
    @requires_auth - Will require valid token when auth is implemented
    
    NOTE: Auth is NOT implemented. These are preparation annotations only.
"""

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Form

from Deekshith.topview_link.service import TopviewLinkService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/survey",
    tags=["Topview Link"],
)


# @requires_auth (when implemented: farmer must own the survey)
@router.post("/{survey_id}/topview")
async def upload_topview_image(
    survey_id: int,
    topview_order: str = Form(..., description="Topview order (a, b, c, etc.)"),
    image: UploadFile = File(..., description="Topview image file")
):
    """
    Upload a topview image, run detection, and store results.
    
    Args:
        survey_id: Survey identifier
        topview_order: Topview order letter (a, b, c, etc.)
        image: Topview image file
        
    Returns:
        Topview ID and tree count
    """
    try:
        # Validate file type
        if not image.content_type or not image.content_type.startswith('image/'):
            raise HTTPException(
                status_code=400,
                detail="Invalid file type. Please upload an image file."
            )
        
        service = TopviewLinkService()
        result = await service.process_topview(survey_id, topview_order, image)
        
        logger.info(f"Topview {result['topview_id']} processed with {result['tree_count']} trees")
        
        return result
        
    except HTTPException:
        raise
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Topview processing failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Topview processing failed: {str(e)}")
