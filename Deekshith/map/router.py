# Deekshith/map/router.py
"""
Health Map Router - Generate and retrieve health maps

SECURITY ANNOTATIONS:
    All endpoints marked with security requirements for future auth integration.
    @public - No authentication required
    @requires_auth - Will require valid token when auth is implemented
    
    NOTE: Auth is NOT implemented. These are preparation annotations only.
"""

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from Deekshith.map.service import HealthMapService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/survey",
    tags=["Health Map"],
)


# @requires_auth (when implemented: farmer must own the survey)
@router.get("/{survey_id}/topview/{topview_order}/health-map")
async def get_health_map(survey_id: int, topview_order: str):
    """
    Generate or retrieve health map for a topview.
    Merges topview detection geometry with tree health status.
    
    Args:
        survey_id: Survey identifier
        topview_order: Topview order (a, b, c, etc.)
        
    Returns:
        Health map with tree positions and color-coded health status
    """
    try:
        service = HealthMapService()
        health_map = service.generate_health_map(survey_id, topview_order)
        
        logger.info(f"Health map generated: {survey_id}{topview_order}")
        
        return health_map
        
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Health map generation failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Health map generation failed: {str(e)}")


# @requires_auth (when implemented: farmer must own the survey)
@router.get("/{survey_id}/topview/{topview_order}/health-map/image")
async def get_health_map_image(survey_id: int, topview_order: str):
    """
    Generate and return annotated topview image with colored health pins.
    
    Args:
        survey_id: Survey identifier
        topview_order: Topview order (a, b, c, etc.)
        
    Returns:
        Annotated image with colored pins (green=healthy, red=unhealthy, grey=unknown)
    """
    try:
        service = HealthMapService()
        image_path = service.generate_annotated_image(survey_id, topview_order)
        
        if not image_path or not image_path.exists():
            raise HTTPException(status_code=404, detail="Annotated image could not be generated")
        
        logger.info(f"Health map image generated: {survey_id}{topview_order}")
        
        return FileResponse(
            path=str(image_path),
            media_type="image/jpeg",
            filename=f"health_map_{survey_id}{topview_order}.jpg"
        )
        
    except HTTPException:
        raise
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Health map image generation failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Health map image generation failed: {str(e)}")
