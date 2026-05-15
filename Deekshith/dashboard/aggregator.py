# Deekshith/dashboard/aggregator.py
"""
Dashboard Aggregator - Aggregation logic for tree, topview, and survey dashboards.

DESIGN PRINCIPLE: Database is the single source of truth.
- Files are OPTIONAL cache/debug artifacts only
- Dashboard data is COMPUTED from trees table
- Never read dashboards from files for production use

METRICS CLARITY:
    This module computes AGGREGATED metrics from tree data.
    
    health_score (COMPUTED, stored in topviews):
        Formula: (healthy_trees / total_trees) * 100
        Range: 0.0 - 100.0
        Represents: Percentage of healthy trees in a topview/survey.
        Stored in: topviews.health_score (cached), computed fresh from trees.
        
    final_health_percentage (STORED per-tree):
        The tree's individual health metric from ML analysis.
        Stored in: trees.final_health_percentage
        Represents: Single tree's health state.
        
    reliability_score (NOT stored, from ML output):
        ML model's confidence in its classification.
        Available in: tree.ml_raw_output["reliability_score"]
        Represents: How confident the model is (NOT the health state itself).
        
    DO NOT confuse:
        - health_score (aggregate, topview-level) 
        - final_health_percentage (individual tree)
        - reliability_score (ML confidence, not health)
"""

import json
import logging
from collections import Counter
from pathlib import Path
from typing import List, Dict, Any, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Storage root (for CACHE/DEBUG only, NOT source of truth)
STORAGE_ROOT = Path(__file__).parent.parent / "storage" / "surveys"

# Health thresholds
HEALTH_THRESHOLD = 70  # weighted_score >= 70 → healthy


class DashboardAggregator:
    """Aggregator for multi-level dashboards.
    
    Source of Truth Hierarchy:
    1. trees table (final_status, final_health_percentage)
    2. tree_parts table (part-level details)
    3. topviews table (cached aggregations)
    
    Files are NEVER read for production dashboards.
    """
    
    def __init__(self, db: Optional[Session] = None):
        self.storage_root = STORAGE_ROOT
        self._db = db
    
    def _get_topview_path(self, survey_id: int, topview_order: str) -> Path:
        """Get topview directory path (for cache writes only)."""
        survey_path = self.storage_root / f"SURVEY_{survey_id}"
        return survey_path / "topviews" / f"{survey_id}{topview_order}"
    
    def generate_topview_dashboard_from_db(self, db: Session, survey_id: int, topview_order: str) -> dict:
        """
        Generate topview dashboard from DATABASE (source of truth).
        
        This is the PREFERRED method. Never read from files.
        
        Args:
            db: Database session
            survey_id: Survey identifier
            topview_order: Topview order (a, b, c, etc.)
            
        Returns:
            Topview dashboard computed from trees table
        """
        from db import crud
        from db.models import Tree, Topview
        
        # Get topview record
        topview = crud.get_topview(db, survey_id, topview_order)
        if not topview:
            raise FileNotFoundError(f"Topview {survey_id}{topview_order} not found in database")
        
        # Get trees from DATABASE (source of truth)
        trees = db.query(Tree).filter(Tree.topview_id == topview.id).all()
        
        if not trees:
            # No trees in DB for this topview - cannot compute dashboard from DB
            # Caller should fall back to file-based computation
            raise FileNotFoundError(
                f"No trees found in database for topview {survey_id}{topview_order}. "
                "Falling back to file-based dashboard generation."
            )
        
        # Aggregate from trees table (SOURCE OF TRUTH)
        total_trees = len(trees)
        healthy_count = 0
        unhealthy_count = 0
        disease_counter = Counter()
        
        for tree in trees:
            status = (tree.final_status or "unknown").lower()
            
            if status == "healthy":
                healthy_count += 1
            elif status in ("unhealthy", "critical"):
                unhealthy_count += 1
                
                # Extract disease from ml_raw_output if available
                if tree.ml_raw_output:
                    disease = tree.ml_raw_output.get("dominant_disease") or tree.ml_raw_output.get("primary_disease")
                    if disease:
                        disease_counter[disease] += 1
        
        health_score = round((healthy_count / total_trees) * 100, 2) if total_trees > 0 else 0.0
        dominant_disease = disease_counter.most_common(1)[0][0] if disease_counter else None
        
        dashboard = {
            "topview_id": f"{survey_id}{topview_order}",
            "total_trees": total_trees,
            "healthy": healthy_count,
            "unhealthy": unhealthy_count,
            "health_score": health_score,
            "dominant_disease": dominant_disease,
            "disease_distribution": dict(disease_counter)
        }
        
        logger.info(f"Dashboard computed from DB: {survey_id}{topview_order} ({total_trees} trees)")
        
        return dashboard
    
    def generate_topview_dashboard(self, survey_id: int, topview_order: str) -> dict:
        """
        Generate topview-level dashboard.
        
        DEPRECATED: Use generate_topview_dashboard_from_db() instead.
        This method falls back to files only if DB is unavailable.
        """
        # Try DB first (preferred)
        try:
            from db.database import SessionLocal
            db = SessionLocal()
            try:
                return self.generate_topview_dashboard_from_db(db, survey_id, topview_order)
            finally:
                db.close()
        except Exception as db_error:
            logger.warning(f"DB dashboard failed, falling back to files: {db_error}")
        
        # FALLBACK ONLY: Read from files (not preferred)
        topview_path = self._get_topview_path(survey_id, topview_order)
        
        if not topview_path.exists():
            raise FileNotFoundError(f"Topview {survey_id}{topview_order} not found")
        
        trees_path = topview_path / "trees"
        tree_dashboards = []
        
        for tree_dir in sorted(trees_path.iterdir()):
            if tree_dir.is_dir():
                dashboard_path = tree_dir / "dashboard.json"
                if dashboard_path.exists():
                    with open(dashboard_path, "r") as f:
                        tree_dashboards.append(json.load(f))
        
        if not tree_dashboards:
            raise FileNotFoundError(f"No tree dashboards found for topview {survey_id}{topview_order}")
        
        topview_id = f"{survey_id}{topview_order}"
        dashboard = self._aggregate_tree_dashboards(topview_id, tree_dashboards)
        
        # Write cache file (optional)
        output_path = topview_path / f"dashboard_{topview_id}.json"
        try:
            with open(output_path, "w") as f:
                json.dump(dashboard, f, indent=2)
        except Exception:
            pass  # Cache write failure is non-critical
        
        logger.info(f"Topview dashboard from files (fallback): {output_path}")
        
        return dashboard
    
    def _aggregate_tree_dashboards(self, topview_id: str, tree_dashboards: List[dict]) -> dict:
        """
        Aggregate multiple tree dashboards into topview dashboard.
        
        Args:
            topview_id: Topview identifier
            tree_dashboards: List of tree dashboard dictionaries
            
        Returns:
            Topview dashboard
        """
        total_trees = len(tree_dashboards)
        healthy_count = 0
        unhealthy_count = 0
        disease_counter = Counter()
        
        # Aggregate tree health
        for tree_dash in tree_dashboards:
            tree_health = tree_dash.get("tree", {}).get("health", "unknown")
            
            if tree_health == "healthy":
                healthy_count += 1
            elif tree_health == "unhealthy":
                unhealthy_count += 1
                
                # Count primary disease
                primary_disease = tree_dash.get("tree", {}).get("primary_disease")
                if primary_disease:
                    disease_counter[primary_disease] += 1
        
        # Calculate health score
        health_score = round((healthy_count / total_trees) * 100, 2) if total_trees > 0 else 0
        
        # Determine dominant disease
        dominant_disease = disease_counter.most_common(1)[0][0] if disease_counter else None
        
        return {
            "topview_id": topview_id,
            "total_trees": total_trees,
            "healthy": healthy_count,
            "unhealthy": unhealthy_count,
            "health_score": health_score,
            "dominant_disease": dominant_disease,
            "disease_distribution": dict(disease_counter)
        }
    
    def aggregate_survey_dashboard(self, survey_id: int, topview_dashboards: List[dict]) -> dict:
        """
        Aggregate multiple topview dashboards into final survey dashboard.
        
        Args:
            survey_id: Survey identifier
            topview_dashboards: List of topview dashboard dictionaries
            
        Returns:
            Final survey dashboard
        """
        if not topview_dashboards:
            raise ValueError("No topview dashboards provided")
        
        total_topviews = len(topview_dashboards)
        total_trees = sum(d.get("total_trees", 0) for d in topview_dashboards)
        total_healthy = sum(d.get("healthy", 0) for d in topview_dashboards)
        total_unhealthy = sum(d.get("unhealthy", 0) for d in topview_dashboards)
        
        # Calculate weighted health score
        weighted_sum = sum(
            d.get("health_score", 0) * d.get("total_trees", 0) 
            for d in topview_dashboards
        )
        overall_health_score = round(weighted_sum / total_trees, 2) if total_trees > 0 else 0
        
        # Aggregate disease distribution
        disease_counter = Counter()
        for topview_dash in topview_dashboards:
            for disease, count in topview_dash.get("disease_distribution", {}).items():
                disease_counter[disease] += count
        
        primary_disease = disease_counter.most_common(1)[0][0] if disease_counter else None
        
        return {
            "survey_id": survey_id,
            "total_topviews": total_topviews,
            "total_trees": total_trees,
            "healthy": total_healthy,
            "unhealthy": total_unhealthy,
            "overall_health_score": overall_health_score,
            "primary_disease": primary_disease,
            "dominant_disease": primary_disease,  # alias for app compatibility
            "disease_distribution": dict(disease_counter),
            "topview_summaries": [
                {
                    "topview_id": d.get("topview_id"),
                    "trees": d.get("total_trees"),
                    "health_score": d.get("health_score")
                }
                for d in topview_dashboards
            ]
        }
