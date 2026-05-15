"""Database models with proper integrity constraints.

Design Principles:
- Database is the single source of truth
- Use auto-incrementing IDs (no manual generation)
- Use UUIDs for stable tree identity across re-uploads
- Proper unique constraints to prevent duplicates
"""
import uuid
from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime, JSON, func, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from .database import Base


def generate_uuid():
    """Generate a new UUID string."""
    return str(uuid.uuid4())


class Farmer(Base):
    __tablename__ = "farmers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)  # User's email from Google/Firebase auth
    onboarding_completed = Column(Boolean, default=False)  # True after farm details filled
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    surveys = relationship("Survey", back_populates="farmer", cascade="all, delete-orphan")


class Survey(Base):
    __tablename__ = "surveys"

    id = Column(Integer, primary_key=True, index=True)
    farmer_id = Column(Integer, ForeignKey("farmers.id"), nullable=False)
    land_location = Column(String)
    total_trees = Column(Integer, nullable=True)
    topview_image_path = Column(String, nullable=True)
    extra_data = Column(JSON, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    farmer = relationship("Farmer", back_populates="surveys")
    trees = relationship("Tree", back_populates="survey", cascade="all, delete-orphan")
    topviews = relationship("Topview", back_populates="survey", cascade="all, delete-orphan")


class Topview(Base):
    """Per-survey topview (a, b, c, ...). Stores computed dashboard summary.
    
    NOTE: dashboard_snapshot is a CACHE only, computed from trees table.
    The trees table is the source of truth for health data.
    """
    __tablename__ = "topviews"
    __table_args__ = (
        UniqueConstraint('survey_id', 'topview_order', name='uq_survey_topview_order'),
    )

    id = Column(Integer, primary_key=True, index=True)
    survey_id = Column(Integer, ForeignKey("surveys.id"), nullable=False)
    topview_order = Column(String, nullable=False)  # "a", "b", "c", ...
    image_path = Column(String, nullable=True)
    total_trees = Column(Integer, nullable=True)
    healthy_count = Column(Integer, nullable=True)
    unhealthy_count = Column(Integer, nullable=True)
    health_score = Column(Float, nullable=True)
    dominant_disease = Column(String, nullable=True)
    # CACHE ONLY: Computed from trees table, not source of truth
    dashboard_snapshot = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    survey = relationship("Survey", back_populates="topviews")
    # Trees now relate directly to Topview if needed for grouping, 
    # but primarily they belong to Survey. We can keep a relationship here if helpful.
    trees = relationship("Tree", back_populates="topview")


class Tree(Base):
    """Tree entity with stable UUID identity.
    
    IDENTITY: tree_uuid is THE SOLE stable identifier for a tree.
    
    tree_number is for DISPLAY/ORDERING ONLY:
    - May change on YOLO re-run (different detection order)
    - NOT enforced as unique (allows reprocessing without constraint violations)
    - Use tree_uuid for all cross-references and video linkage
    
    METRICS CLARITY:
        final_health_percentage (0-100):
            The STORED health metric for this tree, derived from ML output.
            Represents the tree's overall health state.
            Typically: weighted_score from sideview analysis.
            
        health_score (COMPUTED at topview/survey level, NOT stored per-tree):
            Aggregated metric: (healthy_trees / total_trees) * 100
            Computed by DashboardAggregator, stored in topviews.health_score.
            
        reliability_score (COMPUTED, NOT stored in Tree model):
            ML model confidence in the classification.
            Returned in API responses via ml_raw_output["reliability_score"].
            NOT a separate column - extract from ml_raw_output if needed.
    
    Re-detection Safety:
    - YOLO may produce different tree counts/ordering on same image
    - No uniqueness constraint on tree_number prevents insert failures
    - tree_uuid ensures stable references across re-uploads
    """
    __tablename__ = "trees"
    # NO UNIQUENESS on tree_number - it's display-only and may change
    # tree_uuid (below) is unique and is the sole identity

    id = Column(Integer, primary_key=True, index=True)
    
    # STABLE IDENTITY: Use this UUID for all external references
    tree_uuid = Column(String(36), default=generate_uuid, unique=True, nullable=False, index=True)
    
    survey_id = Column(Integer, ForeignKey("surveys.id"), nullable=False)
    topview_id = Column(Integer, ForeignKey("topviews.id"), nullable=True)

    # Display order only - NOT a stable identifier
    tree_number = Column(Integer, nullable=False)  # e.g. 1, 2, 3...
    
    # Unified Status Fields (source of truth for health)
    final_status = Column(String, nullable=True)    # healthy / unhealthy / critical
    final_health_percentage = Column(Float, nullable=True)  # Always 0.0 - 100.0
    critical_alert = Column(Boolean, default=False)
    
    # Spatial data from YOLO detection
    cx = Column(Integer, nullable=True)  # centroid x
    cy = Column(Integer, nullable=True)  # centroid y
    
    # Raw ML output (for debugging/audit, NOT source of truth)
    ml_raw_output = Column(JSON, nullable=True)
    
    # ML VERSIONING: Required for backward compatibility
    # When model changes, old data can still be interpreted correctly
    ml_model_version = Column(String(50), default="v1.0.0")  # e.g., "yolo-v8.1", "cnn-v2.0"
    ml_schema_version = Column(String(20), default="1")  # Schema version of ml_raw_output structure
    
    extra_data = Column(JSON, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    survey = relationship("Survey", back_populates="trees")
    topview = relationship("Topview", back_populates="trees")
    parts = relationship("TreePart", back_populates="tree", cascade="all, delete-orphan")
    
    @property
    def dashboard_data(self):
        """Backward compatibility: alias for ml_raw_output."""
        return self.ml_raw_output
    
    @dashboard_data.setter
    def dashboard_data(self, value):
        self.ml_raw_output = value


class TreePart(Base):
    __tablename__ = "tree_parts"

    id = Column(Integer, primary_key=True, index=True)
    tree_id = Column(Integer, ForeignKey("trees.id"), nullable=False)

    part_name = Column(String, nullable=False)  # stem, bud, leaves
    status = Column(String, nullable=False)  # e.g. "healthy", "whitefly"
    confidence = Column(Float, nullable=False)
    extra = Column(JSON, default={})
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    tree = relationship("Tree", back_populates="parts")


class AnalysisHistory(Base):
    """
    Stores analysis history for users (replaces local SQLite in Flutter).
    Supports both sideview (image) and sidevideo (video) analyses.
    """
    __tablename__ = "analysis_history"

    id = Column(Integer, primary_key=True, index=True)
    farmer_id = Column(Integer, ForeignKey("farmers.id"), nullable=True)  # Optional link to farmer
    
    # Analysis details
    image_path = Column(String, nullable=False)  # Path or URL to the analyzed image/video
    analysis_type = Column(String, default="image")  # "image" or "video"
    
    # Results
    score = Column(Float, nullable=False)  # Health/confidence score (0-100)
    label = Column(String, nullable=False)  # Disease/status label
    part = Column(String, nullable=True)  # Tree part: stem, bud, leaves
    status = Column(String, nullable=True)  # healthy/unhealthy
    
    # Confidence values
    part_confidence = Column(Float, nullable=True)
    status_confidence = Column(Float, nullable=True)
    
    # Recommendation
    recommendation_summary = Column(String, nullable=True)
    
    # Full result JSON for detailed view
    result_data = Column(JSON, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    farmer = relationship("Farmer", backref="analysis_history")


# =============================================================================
# CONCURRENCY & JOB MANAGEMENT (v2.1)
# =============================================================================

class UploadLock(Base):
    """
    Advisory lock table for preventing race conditions on concurrent uploads.
    
    Usage: Before processing (survey_id, topview_order), acquire lock.
    Only one process can hold the lock at a time.
    
    Why not use PostgreSQL advisory locks?
    - Advisory locks are session-scoped (released on disconnect)
    - This table provides persistent, inspectable lock state
    - Can implement lock expiry for crash recovery
    """
    __tablename__ = "upload_locks"
    __table_args__ = (
        UniqueConstraint('survey_id', 'topview_order', name='uq_upload_lock_survey_topview'),
    )

    id = Column(Integer, primary_key=True, index=True)
    survey_id = Column(Integer, nullable=False, index=True)
    topview_order = Column(String(10), nullable=False)
    locked_at = Column(DateTime(timezone=True), server_default=func.now())
    locked_by = Column(String(100), nullable=True)  # Worker ID or request ID
    expires_at = Column(DateTime(timezone=True), nullable=True)  # For stale lock cleanup


class MLJob(Base):
    """
    ML Job abstraction for async-ready processing.
    
    Current behavior: Synchronous execution (job created → runs → completes inline)
    Future behavior: Queue-based async execution (Celery, etc.)
    
    The interface is designed now so migration to async is non-breaking.
    
    Job lifecycle:
        pending → running → completed | failed
    """
    __tablename__ = "ml_jobs"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String(36), unique=True, nullable=False, index=True)  # UUID
    
    # Job type: 'topview_detection', 'sideview_health', etc.
    job_type = Column(String(50), nullable=False)
    
    # Status: pending, running, completed, failed
    status = Column(String(20), default="pending", index=True)
    
    # Target identifiers
    survey_id = Column(Integer, ForeignKey("surveys.id"), nullable=True)
    topview_order = Column(String(10), nullable=True)
    tree_number = Column(Integer, nullable=True)
    
    # I/O paths
    input_path = Column(String(500), nullable=True)
    output_path = Column(String(500), nullable=True)
    
    # Result storage
    result = Column(JSON, nullable=True)
    error_message = Column(String, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # ML versioning (for result interpretation)
    ml_model_version = Column(String(50), nullable=True)
    ml_schema_version = Column(String(20), nullable=True)
