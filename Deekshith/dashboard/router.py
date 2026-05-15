# Deekshith/dashboard/router.py
"""
Dashboard Router - Generate topview and survey-level dashboards.
Stores topview a/b/c and tree results in DB for a single source of truth.
"""

import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from db.database import get_db
from db import crud
from Deekshith.dashboard.aggregator import DashboardAggregator

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/survey",
    tags=["Dashboard"],
)


def _storage_topview_path(survey_id: int, topview_order: str) -> Path:
    storage_root = Path(__file__).parent.parent / "storage" / "surveys"
    return storage_root / f"SURVEY_{survey_id}" / "topviews" / f"{survey_id}{topview_order}"


@router.get("/{survey_id}/topviews")
async def get_survey_topviews(survey_id: int, db: Session = Depends(get_db)):
    """
    List all topviews (a, b, c, ...) for a survey from DB. Use for dashboard navigation.
    Returns summary per topview: topview_order, total_trees, healthy, unhealthy, health_score.
    """
    topviews = crud.get_topviews_by_survey(db, survey_id)
    if not topviews:
        return {"survey_id": survey_id, "topviews": []}
    out = []
    for t in topviews:
        out.append({
            "topview_order": t.topview_order,
            "topview_id": f"{survey_id}{t.topview_order}",
            "total_trees": t.total_trees,
            "healthy": t.healthy_count,
            "unhealthy": t.unhealthy_count,
            "health_score": t.health_score,
            "dominant_disease": t.dominant_disease,
        })
    return {"survey_id": survey_id, "topviews": out}


@router.get("/{survey_id}/topview")
async def get_survey_full_result(survey_id: int, db: Session = Depends(get_db)):
    """
    Get full survey result with all topviews and their trees from DB.
    This is the main endpoint for Flutter app to get survey history/results.
    Returns: survey_id, total_trees, topviews (each with trees array).
    """
    from db.models import Tree
    
    survey = crud.get_survey(db, survey_id)
    if not survey:
        raise HTTPException(status_code=404, detail=f"Survey {survey_id} not found")
    
    topviews = crud.get_topviews_by_survey(db, survey_id)
    result_topviews = []
    
    for tv in topviews:
        # Get trees for this topview
        trees = db.query(Tree).filter(Tree.topview_id == tv.id).all()
        tree_list = []
        for t in trees:
            tree_list.append({
                "tree_number": t.tree_number,
                "cx": t.cx,
                "cy": t.cy,
                "final_status": t.final_status,
                "final_health_percentage": t.final_health_percentage,
                "dashboard_data": t.dashboard_data,
            })
        
        result_topviews.append({
            "topview_order": tv.topview_order,
            "topview_id": f"{survey_id}{tv.topview_order}",
            "total_trees": tv.total_trees,
            "healthy": tv.healthy_count,
            "unhealthy": tv.unhealthy_count,
            "health_score": tv.health_score,
            "dominant_disease": tv.dominant_disease,
            "trees": tree_list,
        })
    
    return {
        "survey_id": survey_id,
        "total_trees": survey.total_trees,
        "topviews": result_topviews,
    }


@router.get("/{survey_id}/dashboard")
async def get_survey_dashboard(survey_id: int, db: Session = Depends(get_db)):
    """
    Get full survey-level dashboard from DB (all topview a, b, c aggregated).
    Single call for proper dashboard with full data. Falls back to file-based if no DB data.
    """
    topviews = crud.get_topviews_by_survey(db, survey_id)
    
    # For each topview, check if the snapshot is valid (has trees).
    # If a snapshot is stale (0 trees but files exist), regenerate it first.
    snapshots = []
    aggregator = DashboardAggregator()
    for t in topviews:
        snap = t.dashboard_snapshot
        if snap is not None and snap.get("total_trees", 0) > 0:
            snapshots.append(snap)
        else:
            # Try to regenerate this topview's dashboard from files/DB
            try:
                new_snap = aggregator.generate_topview_dashboard(survey_id, t.topview_order)
                if new_snap and new_snap.get("total_trees", 0) > 0:
                    _save_dashboard_to_db(db, survey_id, t.topview_order, new_snap)
                    snapshots.append(new_snap)
                    logger.info(f"Regenerated stale topview snapshot: {survey_id}{t.topview_order}")
            except Exception as e:
                logger.warning(f"Could not regenerate topview {t.topview_order}: {e}")
    
    if snapshots:
        dashboard = aggregator.aggregate_survey_dashboard(survey_id, snapshots)
        logger.info(f"Survey dashboard from DB: survey {survey_id} ({len(snapshots)} topviews)")
        return dashboard
    # Fallback: file-based generation (e.g. POST then GET)
    try:
        from Deekshith.survey.service import SurveyService
        service = SurveyService()
        dashboard = service.generate_final_dashboard(survey_id)
        return dashboard
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Survey dashboard failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{survey_id}/topview/{topview_order}/dashboard")
async def get_topview_dashboard(
    survey_id: int, topview_order: str, db: Session = Depends(get_db)
):
    """
    Get topview dashboard from DB if stored; otherwise generate from files and store.
    Single source of truth for dashboard data.
    """
    topview = crud.get_topview(db, survey_id, topview_order)
    if topview is not None and topview.dashboard_snapshot is not None:
        # If snapshot exists but has 0 trees while topview record says otherwise,
        # the snapshot is stale - regenerate it
        snapshot_trees = topview.dashboard_snapshot.get("total_trees", 0)
        if snapshot_trees > 0:
            logger.info(f"Topview dashboard from DB: {survey_id}{topview_order}")
            return topview.dashboard_snapshot
        else:
            logger.info(f"Topview dashboard snapshot has 0 trees, regenerating: {survey_id}{topview_order}")
    # Fallback: generate from files and store (via POST or generate here)
    try:
        aggregator = DashboardAggregator()
        dashboard = aggregator.generate_topview_dashboard(survey_id, topview_order)
        _save_dashboard_to_db(db, survey_id, topview_order, dashboard)
        return dashboard
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Dashboard generation failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def _save_dashboard_to_db(db: Session, survey_id: int, topview_order: str, dashboard: dict):
    """Persist topview dashboard and per-tree results to DB."""
    try:
        crud.upsert_topview(
            db,
            survey_id=survey_id,
            topview_order=topview_order,
            total_trees=dashboard.get("total_trees"),
            healthy_count=dashboard.get("healthy"),
            unhealthy_count=dashboard.get("unhealthy"),
            health_score=dashboard.get("health_score"),
            dominant_disease=dashboard.get("dominant_disease"),
            dashboard_snapshot=dashboard,
        )
        topview = crud.get_topview(db, survey_id, topview_order)
        if topview is None:
            return
        trees_path = _storage_topview_path(survey_id, topview_order) / "trees"
        if trees_path.exists():
            for tree_dir in sorted(trees_path.iterdir()):
                if not tree_dir.is_dir():
                    continue
                tree_index = tree_dir.name
                dashboard_path = tree_dir / "dashboard.json"
                if dashboard_path.exists():
                    with open(dashboard_path, "r") as f:
                        tree_dash = json.load(f)
                    tree_health = tree_dash.get("tree", {}).get("health", "unknown")
                    tree_score = tree_dash.get("tree", {}).get("weighted_score", 0.0)
                    crud.upsert_topview_tree(
                        db,
                        topview_id=topview.id,
                        tree_index=tree_index,
                        health=tree_health,
                        weighted_score=float(tree_score) if tree_score is not None else None,
                        dashboard_json=tree_dash,
                    )
        logger.info(f"Saved topview {survey_id}{topview_order} to DB")
    except Exception as e:
        logger.warning(f"Could not save dashboard to DB: {e}")


@router.post("/{survey_id}/topview/{topview_order}/dashboard")
async def generate_topview_dashboard(
    survey_id: int, topview_order: str, db: Session = Depends(get_db)
):
    """
    Generate dashboard from tree dashboards (files) and store in DB.
    Returns topview dashboard with aggregated health statistics.
    """
    try:
        aggregator = DashboardAggregator()
        dashboard = aggregator.generate_topview_dashboard(survey_id, topview_order)
        _save_dashboard_to_db(db, survey_id, topview_order, dashboard)
        logger.info(f"Topview dashboard generated and saved: {survey_id}{topview_order}")
        return dashboard
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Dashboard generation failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def _load_tree_recommendations(survey_id: int, topview_order: str, tree_index) -> dict | None:
    """Load recommendations from sideview_full_result.json for a tree."""
    try:
        # Handle both int and string tree_index
        if isinstance(tree_index, int):
            tree_dir_name = f"tree_{tree_index:02d}"
        else:
            tree_dir_name = tree_index  # Already formatted as "tree_01"
        
        topview_path = _storage_topview_path(survey_id, topview_order)
        sideview_path = topview_path / "trees" / tree_dir_name / "sideview_full_result.json"
        
        if sideview_path.exists():
            with open(sideview_path, "r") as f:
                full_result = json.load(f)
            return full_result.get("recommendations")
    except Exception as e:
        logger.debug(f"Could not load recommendations for tree {tree_index}: {e}")
    return None


@router.get("/{survey_id}/topview/{topview_order}/trees/results")
async def get_tree_results(
    survey_id: int, topview_order: str, db: Session = Depends(get_db)
):
    """
    Get individual tree results for a topview. Prefer DB; fallback to files and save to DB.
    Includes recommendations from sideview analysis for each tree.
    """
    # Prefer DB
    topview = crud.get_topview(db, survey_id, topview_order)
    if topview is not None:
        db_trees = crud.get_topview_trees(db, topview.id)
        if db_trees:
            tree_results = []
            for t in db_trees:
                recs = _load_tree_recommendations(survey_id, topview_order, t.tree_number)
                tree_results.append({
                    "tree_index": t.tree_number,
                    "health": t.final_status or "unknown",
                    "score": t.final_health_percentage or 0.0,
                    "dashboard": t.dashboard_data or {},
                    "recommendations": recs,  # Include recommendations for Flutter
                    "source": "video" if recs else None,
                })
            logger.info(f"Tree results from DB: {survey_id}{topview_order} ({len(tree_results)} trees)")
            return {
                "survey_id": survey_id,
                "topview_order": topview_order,
                "total_trees": len(tree_results),
                "trees": tree_results,
            }
    # Fallback: load from files
    try:
        topview_path = _storage_topview_path(survey_id, topview_order)
        trees_path = topview_path / "trees"
        if not trees_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"No trees found for survey {survey_id}{topview_order}"
            )
        tree_results = []
        for tree_dir in sorted(trees_path.iterdir()):
            if not tree_dir.is_dir():
                continue
            tree_index = tree_dir.name
            dashboard_path = tree_dir / "dashboard.json"
            if dashboard_path.exists():
                with open(dashboard_path, "r") as f:
                    dashboard = json.load(f)
                tree_health = dashboard.get("tree", {}).get("health", "unknown")
                tree_score = dashboard.get("tree", {}).get("weighted_score", 0.0)
                recs = _load_tree_recommendations(survey_id, topview_order, tree_index)
                tree_results.append({
                    "tree_index": tree_index,
                    "health": tree_health,
                    "score": tree_score,
                    "dashboard": dashboard,
                    "recommendations": recs,  # Include recommendations for Flutter
                    "source": "video" if recs else None,
                })
        if tree_results and topview is None:
            topview = crud.get_topview(db, survey_id, topview_order)
        if tree_results and topview is not None:
            for tr in tree_results:
                crud.upsert_topview_tree(
                    db,
                    topview_id=topview.id,
                    tree_index=tr["tree_index"],
                    health=tr.get("health"),
                    weighted_score=tr.get("score"),
                    dashboard_json=tr.get("dashboard"),
                )
        return {
            "survey_id": survey_id,
            "topview_order": topview_order,
            "total_trees": len(tree_results),
            "trees": tree_results,
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to load tree results: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
