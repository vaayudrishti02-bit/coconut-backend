# Deekshith/sideview_link/router.py
"""
Sideview Link Router - Connects survey system to sideview disease detection

IDENTITY MAPPING:
    API paths use `tree_index` (integer) for user convenience. This is the
    DISPLAY-ONLY tree_number, NOT a stable identifier.
    
    Internally, all operations resolve to `tree_uuid` for stable identity.
    tree_number may change on YOLO re-runs; tree_uuid is permanent.
    
    Flow:
        API: /survey/{survey_id}/topview/{topview_order}/tree/{tree_index}/video
        Service: tree_index → looks up tree_uuid via (survey_id, topview_id, tree_number)
        DB: Operations use tree.id and tree.tree_uuid as stable references
        
SECURITY: All endpoints currently @public (no auth required)
    Auth integration is PREPARED but NOT IMPLEMENTED.
    See STEP 5 comments for @requires_auth annotations.
"""

import logging
from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException, UploadFile, File, Form

from Deekshith.sideview_link.service import SideviewLinkService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/survey",
    tags=["Sideview Link"],
)


@router.post("/{survey_id}/topview/{topview_order}/tree/{tree_index}/video")
async def upload_tree_video(
    survey_id: int,
    topview_order: str,
    tree_index: int,
    video: UploadFile = File(..., description="Tree video file")
):
    """
    Upload video for a specific tree, run disease detection, and store tree dashboard.
    
    IDENTITY NOTE:
        `tree_index` in URL is the DISPLAY-ONLY tree_number (from YOLO detection order).
        Internally resolved to stable tree_uuid. tree_number may change on re-detection;
        tree_uuid is the permanent identity stored in responses.
    
    Args:
        survey_id: Survey identifier
        topview_order: Topview order (a, b, c, etc.)
        tree_index: Tree number from topview detection (display-only, NOT stable ID)
        video: Video file of the tree
        
    Returns:
        Tree dashboard with health status. Contains tree_uuid for stable reference.
        
    Security: @public (no authentication required currently)
    """
    try:
        # Validate file type
        if not video.content_type or not video.content_type.startswith('video/'):
            raise HTTPException(
                status_code=400,
                detail="Invalid file type. Please upload a video file."
            )
        
        service = SideviewLinkService()
        result = await service.process_tree_video(
            survey_id=survey_id,
            topview_order=topview_order,
            tree_index=tree_index,
            video=video
        )
        
        logger.info(f"Tree video processed: {survey_id}{topview_order}_tree_{tree_index:02d}")
        
        return result
        
    except HTTPException:
        raise
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Tree video processing failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Tree video processing failed: {str(e)}")


@router.post("/{survey_id}/topview/{topview_order}/trees/videos/bulk")
async def upload_multiple_tree_videos(
    survey_id: int,
    topview_order: str,
    videos: List[UploadFile] = File(..., description="Multiple tree video files in selection order"),
    tree_indices: str = Form(None, description="Optional comma-separated tree indices (e.g., '1,2,3')"),
):
    """
    Upload multiple tree videos at once for batch processing.
    
    IDENTITY NOTE:
        `tree_indices` are DISPLAY-ONLY tree_numbers (from YOLO detection).
        Internally resolved to stable tree_uuids. Response contains tree_uuid
        for each processed tree as the permanent identifier.
    
    **SELECTION-ORDER MAPPING** (User-Friendly):
    - Videos are mapped based on selection order: 1st video → tree 1, 2nd → tree 2, etc.
    - Optional: Provide explicit tree_indices if custom mapping needed
    
    Args:
        survey_id: Survey identifier
        topview_order: Topview order (a, b, c, etc.)
        videos: List of video files in order
        tree_indices: Optional explicit indices (e.g., "1,2,5,8")
        
    Returns:
        Results for all processed videos
        
    Example:
        - Select videos in order: video1.mp4, video2.mp4, video3.mp4
        - Automatically mapped to trees: 1, 2, 3
    """
    try:
        # Validate file types
        for video in videos:
            if not video.content_type or not video.content_type.startswith('video/'):
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid file type for {video.filename}. Please upload video files only."
                )
        
        # Determine tree indices
        if tree_indices:
            # Use explicit indices if provided
            try:
                indices = [int(idx.strip()) for idx in tree_indices.split(',')]
                if len(indices) != len(videos):
                    raise HTTPException(
                        status_code=400,
                        detail=f"Mismatch: {len(videos)} videos but {len(indices)} indices provided"
                    )
                video_tree_pairs = list(zip(videos, indices))
                mapping_method = "explicit_indices"
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid tree_indices format. Expected comma-separated numbers like '1,2,3'"
                )
        else:
            # Use selection order (1-based)
            indices = list(range(1, len(videos) + 1))
            video_tree_pairs = list(zip(videos, indices))
            mapping_method = "selection_order"
        
        # Sort by tree index for consistent processing
        video_tree_pairs.sort(key=lambda x: x[1])
        
        logger.info(f"Processing {len(video_tree_pairs)} videos using {mapping_method} mapping")
        
        service = SideviewLinkService()
        results = []
        errors = []
        
        # Process each video
        for idx, (video, tree_index) in enumerate(video_tree_pairs, 1):
            try:
                logger.info(f"Processing video {idx}/{len(video_tree_pairs)}: {video.filename} → tree {tree_index}")
                
                result = await service.process_tree_video(
                    survey_id=survey_id,
                    topview_order=topview_order,
                    tree_index=tree_index,
                    video=video
                )
                
                results.append({
                    "tree_index": tree_index,
                    "filename": video.filename,
                    "status": "success",
                    "data": result
                })
                
                logger.info(f"✅ Tree {tree_index} processed successfully")
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"❌ Failed to process tree {tree_index}: {error_msg}")
                
                errors.append({
                    "tree_index": tree_index,
                    "filename": video.filename,
                    "status": "failed",
                    "error": error_msg
                })
        
        # Summary
        success_count = len(results)
        failed_count = len(errors)
        
        response = {
            "survey_id": survey_id,
            "topview_id": f"{survey_id}{topview_order}",
            "total_videos": len(videos),
            "processed": success_count,
            "failed": failed_count,
            "results": results,
            "errors": errors,
            "mapping_method": mapping_method
        }
        
        logger.info(
            f"Bulk upload complete: {success_count} succeeded, {failed_count} failed "
            f"for {survey_id}{topview_order}"
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Bulk video upload failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Bulk video upload failed: {str(e)}")
