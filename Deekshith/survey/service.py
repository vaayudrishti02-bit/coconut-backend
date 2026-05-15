# Deekshith/survey/service.py
"""
Survey Service - Business Logic for Survey Management
NOW DATABASE-FIRST: Uses PostgreSQL as primary storage, files as optional export/backup
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

# Database imports - NOW PRIMARY
from db.database import SessionLocal
from db import crud

logger = logging.getLogger(__name__)

# Storage root for file exports/backups (optional)
STORAGE_ROOT = Path(__file__).parent.parent / "storage" / "surveys"
STORAGE_ROOT.mkdir(parents=True, exist_ok=True)


class SurveyService:
    """Service for managing surveys - DATABASE-FIRST approach."""
    
    def __init__(self):
        self.storage_root = STORAGE_ROOT
    
    def _get_survey_path(self, survey_id: int) -> Path:
        """Get survey directory path for optional file exports."""
        return self.storage_root / f"SURVEY_{survey_id}"
    
    def create_survey(self, farmer_id: str, location: dict) -> dict:
        """
        Create a new survey in DATABASE (PostgreSQL).
        File storage is created only for uploads, not for metadata.
        
        Args:
            farmer_id: Farmer identifier (will be converted to int for database)
            location: GPS coordinates {lat, lon}
            
        Returns:
            Survey creation result
        """
        # Convert farmer_id to int for database
        try:
            farmer_id_int = int(farmer_id) if farmer_id not in (None, "") else 0
        except (TypeError, ValueError):
            raise ValueError("farmer_id must be a valid integer or numeric string")
        if farmer_id_int <= 0:
            raise ValueError("farmer_id must be a positive integer")

        # Create location string from coordinates
        location_str = None
        if location:
            lat = location.get('lat')
            lon = location.get('lon')
            if lat is not None and lon is not None:
                location_str = f"{lat},{lon}"
        
        # Create survey in DATABASE (primary storage)
        db = SessionLocal()
        try:
            # Verify farmer exists
            farmer = crud.get_farmer(db, farmer_id_int)
            if not farmer:
                raise ValueError(f"Farmer {farmer_id_int} not found in database")
            
            # Create survey in database
            db_survey = crud.create_survey(db, farmer_id_int, location_str)
            survey_id = db_survey.id
            timestamp = db_survey.created_at.isoformat() if db_survey.created_at else datetime.utcnow().isoformat()
            logger.info(f"✅ Survey {survey_id} created in DATABASE for farmer {farmer_id_int}")
        finally:
            db.close()
        
        # Create file storage ONLY for uploads (images/videos), not metadata
        survey_path = self._get_survey_path(survey_id)
        survey_path.mkdir(parents=True, exist_ok=True)
        (survey_path / "topviews").mkdir(exist_ok=True)
        
        logger.info(f"📁 Survey {survey_id} upload directory created")
        
        return {
            "survey_id": survey_id,
            "timestamp": timestamp
        }
    
    def get_survey_result(self, survey_id: int) -> Optional[dict]:
        """
        Fetch complete survey result from DATABASE FIRST.
        Falls back to files only if database is empty.
        
        Args:
            survey_id: Survey identifier
            
        Returns:
            Complete survey data or None if not found
        """
        # Try DATABASE first
        db = SessionLocal()
        try:
            survey = crud.get_survey(db, survey_id)
            if survey:
                topviews = crud.get_topviews_by_survey(db, survey_id)
                logger.info(f"✅ Survey {survey_id} retrieved from DATABASE")
                return self._build_survey_result_from_db(db, survey, topviews)
        finally:
            db.close()
        
        # Fallback to file storage if database is empty
        logger.warning(f"⚠️  Survey {survey_id} not in database, checking files...")
        return self._get_survey_result_from_files(survey_id)
    
    def _build_survey_result_from_db(self, db, survey, topviews):
        """Build survey result from DATABASE records."""
        # Parse location
        location_value = survey.land_location
        if location_value and "," in str(location_value):
            parts = str(location_value).strip().split(",", 1)
            try:
                lat, lon = float(parts[0].strip()), float(parts[1].strip())
                location_value = {"lat": lat, "lon": lon}
            except (ValueError, IndexError):
                pass
        
        meta = {
            "survey_id": survey.id,
            "farmer_id": survey.farmer_id,
            "location": location_value,
            "land_location": survey.land_location,
            "timestamp": survey.created_at.isoformat() if survey.created_at else None,
            "status": "active",
        }
        
        # Build topviews dict from database
        topviews_dict = {}
        for t in topviews:
            snap = t.dashboard_snapshot or {}
            trees_rows = crud.get_topview_trees(db, t.id) if hasattr(crud, 'get_topview_trees') else []
            # Use tree_number (not tree_index) and dashboard_data (not dashboard_json)
            trees_data = {f"tree_{tr.tree_number:02d}": (tr.dashboard_data or {}) for tr in trees_rows}
            topviews_dict[t.topview_order] = {
                "detection": None,  # Can be reconstructed from trees if needed
                "dashboard": snap,
                "health_map": None,  # Generated on-demand
                "trees": trees_data,
            }
        
        # Generate final dashboard from database
        final_dashboard = None
        snapshots = [t.dashboard_snapshot for t in topviews if t.dashboard_snapshot]
        if snapshots:
            from Deekshith.dashboard.aggregator import DashboardAggregator
            agg = DashboardAggregator()
            final_dashboard = agg.aggregate_survey_dashboard(survey.id, snapshots)
        
        return {
            "survey_id": survey.id,
            "meta": meta,
            "topviews": topviews_dict,
            "final_dashboard": final_dashboard,
        }
    
    def _get_survey_result_from_files(self, survey_id: int) -> Optional[dict]:
        """Fallback: Load survey result from files."""
        survey_path = self._get_survey_path(survey_id)
        
        if not survey_path.exists():
            return None
        
        # Load meta
        meta_path = survey_path / "meta.json"
        if not meta_path.exists():
            return None
        
        with open(meta_path, "r") as f:
            meta = json.load(f)
        
        # Load topviews
        topviews = {}
        topviews_path = survey_path / "topviews"
        if topviews_path.exists():
            for topview_dir in topviews_path.iterdir():
                if topview_dir.is_dir():
                    topview_order = topview_dir.name
                    topviews[topview_order] = self._load_topview_data(topview_dir)
        
        # Load final dashboard if exists
        final_dashboard = None
        dashboard_path = survey_path / f"dashboard_{survey_id}.json"
        if dashboard_path.exists():
            with open(dashboard_path, "r") as f:
                final_dashboard = json.load(f)
        
        return {
            "survey_id": survey_id,
            "meta": meta,
            "topviews": topviews,
            "final_dashboard": final_dashboard
        }
    
    def _load_topview_data(self, topview_dir: Path) -> dict:
        """Load all data for a specific topview."""
        data = {
            "detection": None,
            "dashboard": None,
            "health_map": None,
            "trees": {}
        }
        
        # Load detection
        detection_path = topview_dir / "topview_detection.json"
        if detection_path.exists():
            with open(detection_path, "r") as f:
                data["detection"] = json.load(f)
        
        # Load topview dashboard
        dashboard_path = topview_dir / f"dashboard_{topview_dir.name}.json"
        if dashboard_path.exists():
            with open(dashboard_path, "r") as f:
                data["dashboard"] = json.load(f)
        
        # Load health map
        health_map_path = topview_dir / f"health_map_{topview_dir.name}.json"
        if health_map_path.exists():
            with open(health_map_path, "r") as f:
                data["health_map"] = json.load(f)
        
        # Load tree dashboards
        trees_dir = topview_dir / "trees"
        if trees_dir.exists():
            for tree_dir in trees_dir.iterdir():
                if tree_dir.is_dir():
                    tree_index = tree_dir.name
                    dashboard_path = tree_dir / "dashboard.json"
                    if dashboard_path.exists():
                        with open(dashboard_path, "r") as f:
                            data["trees"][tree_index] = json.load(f)
        
        return data
    
    def generate_final_dashboard(self, survey_id: int) -> dict:
        """
        Generate final survey-level dashboard from all topview dashboards.
        
        Args:
            survey_id: Survey identifier
            
        Returns:
            Final aggregated dashboard
        """
        from Deekshith.dashboard.aggregator import DashboardAggregator
        
        survey_path = self._get_survey_path(survey_id)
        if not survey_path.exists():
            raise FileNotFoundError(f"Survey {survey_id} not found")
        
        topviews_path = survey_path / "topviews"
        
        # Collect all topview dashboards
        topview_dashboards = []
        for topview_dir in topviews_path.iterdir():
            if topview_dir.is_dir():
                dashboard_path = topview_dir / f"dashboard_{topview_dir.name}.json"
                if dashboard_path.exists():
                    with open(dashboard_path, "r") as f:
                        topview_dashboards.append(json.load(f))
        
        if not topview_dashboards:
            raise FileNotFoundError(f"No topview dashboards found for survey {survey_id}")
        
        # Aggregate
        aggregator = DashboardAggregator()
        final_dashboard = aggregator.aggregate_survey_dashboard(survey_id, topview_dashboards)
        
        # Save
        output_path = survey_path / f"dashboard_{survey_id}.json"
        with open(output_path, "w") as f:
            json.dump(final_dashboard, f, indent=2)
        
        logger.info(f"Final dashboard saved: {output_path}")
        
        return final_dashboard
    
    def list_surveys(self) -> list:
        """List all surveys with basic metadata."""
        surveys = []
        for survey_dir in self.storage_root.iterdir():
            if survey_dir.is_dir() and survey_dir.name.startswith("SURVEY_"):
                meta_path = survey_dir / "meta.json"
                if meta_path.exists():
                    with open(meta_path, "r") as f:
                        meta = json.load(f)
                        surveys.append(meta)
        
        return sorted(surveys, key=lambda x: x["survey_id"], reverse=True)
