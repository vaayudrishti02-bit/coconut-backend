# Deekshith/sideview_link/service.py
"""
Sideview Link Service - Processes tree videos and stores health dashboards
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

# Sideview API endpoint (internal)
SIDEVIEW_API_URL = "http://localhost:8000/sideview/process_video"


class SideviewLinkService:
    """Service for linking surveys with sideview disease detection."""
    
    def __init__(self):
        self.storage_root = STORAGE_ROOT
    
    def _get_tree_path(self, survey_id: int, topview_order: str, tree_index: int) -> Path:
        """Get tree directory path."""
        survey_path = self.storage_root / f"SURVEY_{survey_id}"
        topview_path = survey_path / "topviews" / f"{survey_id}{topview_order}"
        return topview_path / "trees" / f"tree_{tree_index:02d}"
    
    async def process_tree_video(
        self, 
        survey_id: int, 
        topview_order: str, 
        tree_index: int, 
        video: UploadFile
    ) -> dict:
        """
        Process tree video: run disease detection and store dashboard.
        
        Args:
            survey_id: Survey identifier
            topview_order: Topview order (a, b, c, etc.)
            tree_index: Tree number
            video: Uploaded video file
            
        Returns:
            Tree dashboard with health status
        """
        # Get tree directory
        tree_path = self._get_tree_path(survey_id, topview_order, tree_index)
        
        if not tree_path.exists():
            raise FileNotFoundError(
                f"Tree directory not found: {survey_id}{topview_order}_tree_{tree_index:02d}. "
                "Ensure topview image has been uploaded and processed first."
            )
        
        # Save video
        video_path = tree_path / f"tree_{tree_index:02d}.mp4"
        with open(video_path, "wb") as f:
            shutil.copyfileobj(video.file, f)
        
        logger.info(f"Video saved: {video_path}")
        
        # Call sideview API
        sideview_result = await self._call_sideview_api(video_path)
        
        # Extract tree dashboard from sideview result
        tree_dashboard = sideview_result.get("dashboard", {})
        
        # Add tree identification
        tree_id = f"{survey_id}{topview_order}_tree_{tree_index:02d}"
        tree_dashboard["tree_id"] = tree_id
        tree_dashboard["tree_index"] = f"tree_{tree_index:02d}"
        
        # Store tree dashboard
        dashboard_path = tree_path / "dashboard.json"
        with open(dashboard_path, "w") as f:
            json.dump(tree_dashboard, f, indent=2)
        
        logger.info(f"Tree dashboard saved: {dashboard_path}")
        
        # Also store full sideview result for reference
        full_result_path = tree_path / "sideview_full_result.json"
        with open(full_result_path, "w") as f:
            json.dump(sideview_result, f, indent=2)
        
        # Update Tree record in DATABASE with health data
        db = SessionLocal()
        try:
            # Get the topview to find the tree
            topview = crud.get_topview(db, survey_id, topview_order)
            if topview:
                # Find tree by topview_id and tree_number (NOT just survey_id)
                # Different topviews (a, b, c) can each have tree_01, tree_02, etc.
                from db.models import Tree
                tree = db.query(Tree).filter(
                    Tree.topview_id == topview.id,
                    Tree.tree_number == tree_index
                ).first()
                
                if tree:
                    # Extract health info from dashboard
                    tree_health = tree_dashboard.get("tree", {})
                    health_status = tree_health.get("health", "unknown")
                    health_score = tree_health.get("weighted_score", 0.0)
                    
                    # Update tree record
                    crud.update_tree_health(
                        db,
                        tree_id=tree.id,
                        final_health=health_score,
                        final_status=health_status,
                        critical_alert=(health_status == "critical"),
                        dashboard_data=tree_dashboard
                    )
                    logger.info(f"✅ Tree {tree_index} health updated in DB: {health_status} ({health_score}%)")
                else:
                    # Create tree if it doesn't exist
                    crud.create_tree(
                        db=db,
                        survey_id=survey_id,
                        tree_number=tree_index,
                        topview_id=topview.id,
                        final_status=tree_dashboard.get("tree", {}).get("health", "unknown"),
                        final_health_percentage=tree_dashboard.get("tree", {}).get("weighted_score", 0.0),
                        dashboard_data=tree_dashboard
                    )
                    logger.info(f"✅ Tree {tree_index} created in DB with health data")
        except Exception as e:
            logger.warning(f"Failed to sync tree health to database: {e}")
        finally:
            db.close()
        
        return {
            "tree_id": tree_id,
            "tree_index": f"tree_{tree_index:02d}",
            "dashboard": tree_dashboard,
            "video_path": str(video_path),
            "dashboard_path": str(dashboard_path)
        }
    
    async def _call_sideview_api(self, video_path: Path) -> dict:
        """
        Call the sideview video processing API.
        
        Args:
            video_path: Path to video file
            
        Returns:
            Sideview processing result
        """
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:  # 5min timeout for video processing
                with open(video_path, "rb") as f:
                    files = {"file": (video_path.name, f, "video/mp4")}
                    response = await client.post(SIDEVIEW_API_URL, files=files)
                
                if response.status_code != 200:
                    raise Exception(f"Sideview API returned {response.status_code}: {response.text}")
                
                return response.json()
        
        except httpx.RequestError as e:
            logger.error(f"Failed to connect to sideview API: {str(e)}")
            raise Exception(f"Sideview API connection failed: {str(e)}")
        except Exception as e:
            logger.error(f"Sideview API call failed: {str(e)}")
            raise
