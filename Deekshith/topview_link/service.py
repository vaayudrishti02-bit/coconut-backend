# Deekshith/topview_link/service.py
"""
Topview Link Service - Processes topview images and stores detection results
"""

import json
import logging
import shutil
from pathlib import Path
from typing import Optional

import httpx
from fastapi import UploadFile

# Database imports for syncing
from db.database import SessionLocal
from db import crud

logger = logging.getLogger(__name__)

# Storage root
STORAGE_ROOT = Path(__file__).parent.parent / "storage" / "surveys"

# Topview API endpoint (internal)
TOPVIEW_API_URL = "http://localhost:8000/topview/detect"


class TopviewLinkService:
    """Service for linking surveys with topview detection."""
    
    def __init__(self):
        self.storage_root = STORAGE_ROOT
    
    def _get_survey_path(self, survey_id: int) -> Path:
        """Get survey directory path."""
        return self.storage_root / f"SURVEY_{survey_id}"
    
    def _get_topview_path(self, survey_id: int, topview_order: str) -> Path:
        """Get topview directory path."""
        survey_path = self._get_survey_path(survey_id)
        return survey_path / "topviews" / f"{survey_id}{topview_order}"
    
    async def process_topview(self, survey_id: int, topview_order: str, image: UploadFile) -> dict:
        """
        Process topview image: detect trees and store results.
        DATABASE-FIRST: Checks database for survey, stores results in both DB and files.
        
        Args:
            survey_id: Survey identifier
            topview_order: Topview order (a, b, c, etc.)
            image: Uploaded image file
            
        Returns:
            Processing result with topview_id and tree_count
        """
        # Validate survey exists in DATABASE first
        db = SessionLocal()
        try:
            survey = crud.get_survey(db, survey_id)
            if not survey:
                raise FileNotFoundError(f"Survey {survey_id} not found in database")
            logger.info(f"✅ Survey {survey_id} found in database")
        finally:
            db.close()
        
        # Create survey file storage if it doesn't exist (for image uploads)
        survey_path = self._get_survey_path(survey_id)
        survey_path.mkdir(parents=True, exist_ok=True)
        (survey_path / "topviews").mkdir(exist_ok=True)
        
        # Create topview directory
        topview_id = f"{survey_id}{topview_order}"
        topview_path = self._get_topview_path(survey_id, topview_order)
        topview_path.mkdir(parents=True, exist_ok=True)
        
        # Create trees directory
        trees_path = topview_path / "trees"
        trees_path.mkdir(exist_ok=True)
        
        # Save image
        image_path = topview_path / "image.jpg"
        with open(image_path, "wb") as f:
            shutil.copyfileobj(image.file, f)
        
        logger.info(f"📁 Image saved: {image_path}")
        
        # Call topview detection API
        detection_result = await self._call_topview_api(image_path)
        
        # Store detection result
        detection_output_path = topview_path / "topview_detection.json"
        with open(detection_output_path, "w") as f:
            json.dump(detection_result, f, indent=2)
        
        logger.info(f"📄 Detection saved: {detection_output_path}")
        
        # Create tree subdirectories
        tree_count = detection_result.get("count", 0)
        for i in range(1, tree_count + 1):
            tree_dir = trees_path / f"tree_{i:02d}"
            tree_dir.mkdir(exist_ok=True)
        
        # Update DATABASE: survey topview info + upsert Topview row + create Tree records
        db = SessionLocal()
        try:
            # Upsert topview record FIRST (need the topview_id for tree records)
            topview_record = crud.upsert_topview(
                db,
                survey_id=survey_id,
                topview_order=topview_order,
                image_path=str(image_path),
                total_trees=tree_count,
            )
            
            # Create Tree records for each detected tree
            # The detection API returns 'trees' with cx/cy fields (not 'centroids')
            detected_trees = detection_result.get("trees", [])
            for i, tree_data in enumerate(detected_trees, 1):
                cx = int(tree_data.get("cx", 0))
                cy = int(tree_data.get("cy", 0))
                crud.create_tree(
                    db=db,
                    survey_id=survey_id,
                    tree_number=i,
                    cx=cx,
                    cy=cy,
                    topview_id=topview_record.id if topview_record else None
                )
            
            # Update survey total_trees as SUM across ALL topviews (not just this one)
            all_topviews = crud.get_topviews_by_survey(db, survey_id)
            total_across_topviews = sum(tv.total_trees or 0 for tv in all_topviews)
            crud.update_survey_topview_info(
                db,
                survey_id,
                total_trees=total_across_topviews,
                topview_image_path=str(image_path)
            )
            
            logger.info(f"✅ Database updated: survey {survey_id} topview {topview_order} with {tree_count} trees")
        except Exception as e:
            logger.warning(f"Failed to update database for survey {survey_id}: {e}")
        finally:
            db.close()
        
        return {
            "topview_id": topview_id,
            "tree_count": tree_count,
            "detection_path": str(detection_output_path)
        }
    
    async def _call_topview_api(self, image_path: Path) -> dict:
        """
        Call the topview detection API.
        
        Args:
            image_path: Path to image file
            
        Returns:
            Detection result from API
        """
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                with open(image_path, "rb") as f:
                    files = {"file": (image_path.name, f, "image/jpeg")}
                    response = await client.post(TOPVIEW_API_URL, files=files)
                
                if response.status_code != 200:
                    raise Exception(f"Topview API returned {response.status_code}: {response.text}")
                
                return response.json()
        
        except httpx.RequestError as e:
            logger.error(f"Failed to connect to topview API: {str(e)}")
            raise Exception(f"Topview API connection failed: {str(e)}")
        except Exception as e:
            logger.error(f"Topview API call failed: {str(e)}")
            raise

