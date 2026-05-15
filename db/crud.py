"""Database CRUD operations.

Design Principles:
- Let PostgreSQL handle auto-increment IDs (no manual generation)
- Use tree_uuid for stable tree identity
- Database is the single source of truth
- Support transactional operations for multi-step flows
"""
from contextlib import contextmanager
from sqlalchemy.orm import Session
from sqlalchemy import select
from . import models, schemas
from .database import SessionLocal


@contextmanager
def transaction(db: Session = None):
    """Context manager for transactional operations.
    
    Can be used with an existing session or will create its own:
    
    Usage (new session):
        with transaction() as db:
            crud.create_survey(db, ...)
            crud.create_tree(db, ...)
    
    Usage (existing session):
        db = SessionLocal()
        with transaction(db):
            crud.create_survey(db, ...)
    
    Automatically commits on success, rolls back on exception.
    """
    owns_session = db is None
    if owns_session:
        db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        if owns_session:
            db.close()


# ------------------ FARMER ------------------
def create_farmer(db: Session, name: str, phone: str = None, email: str = None):
    db_farmer = models.Farmer(name=name, phone=phone, email=email)
    db.add(db_farmer)
    db.commit()
    db.refresh(db_farmer)
    return db_farmer


def get_farmer_by_email(db: Session, email: str):
    # Normalize email to lowercase for case-insensitive lookup
    normalized_email = email.strip().lower() if email else None
    if not normalized_email:
        return None
    return db.query(models.Farmer).filter(models.Farmer.email == normalized_email).first()


def get_farmer(db: Session, farmer_id: int):
    return db.get(models.Farmer, farmer_id)


def get_farmer_by_phone(db: Session, phone: str):
    return db.query(models.Farmer).filter(models.Farmer.phone == phone).first()


# ------------------ SURVEY ------------------
def create_survey(db: Session, farmer_id: int, land_location: str = None):
    """Create a new survey. Let PostgreSQL auto-generate the ID.
    
    NOTE: We do NOT manually assign IDs. This was causing race conditions
    and ACID violations. PostgreSQL handles ID generation properly.
    """
    db_survey = models.Survey(
        farmer_id=farmer_id,
        land_location=land_location
    )
    db.add(db_survey)
    db.commit()
    db.refresh(db_survey)
    return db_survey


def get_survey(db: Session, survey_id: int):
    return db.get(models.Survey, survey_id)


def get_surveys_by_farmer(db: Session, farmer_id: int):
    return db.query(models.Survey).filter(models.Survey.farmer_id == farmer_id).all()


def get_all_surveys(db: Session, order_desc: bool = True):
    """List all surveys, optionally newest first."""
    q = db.query(models.Survey)
    if order_desc:
        q = q.order_by(models.Survey.id.desc())
    return q.all()


def update_survey_topview_info(db: Session, survey_id: int, total_trees: int = None, 
                                topview_image_path: str = None, extra_data: dict = None):
    db_survey = db.get(models.Survey, survey_id)
    if not db_survey:
        return None
    if total_trees is not None:
        db_survey.total_trees = total_trees
    if topview_image_path is not None:
        db_survey.topview_image_path = topview_image_path
    if extra_data is not None:
        db_survey.extra_data = extra_data
    db.add(db_survey)
    db.commit()
    db.refresh(db_survey)
    return db_survey


# ------------------ TREES (Unified) ------------------

# ML Version Constants
CURRENT_ML_MODEL_VERSION = "v1.0.0"  # Update when model changes
CURRENT_ML_SCHEMA_VERSION = "1"  # Update when ml_raw_output structure changes


def create_tree(db: Session, survey_id: int, tree_number: int, cx: int = None, cy: int = None,
                final_status: str = None, final_health_percentage: float = None, 
                critical_alert: bool = False, ml_raw_output: dict = None, topview_id: int = None,
                dashboard_data: dict = None, ml_model_version: str = None, ml_schema_version: str = None):
    """Create a new tree with auto-generated UUID.
    
    Args:
        survey_id: Parent survey ID
        tree_number: Display order (NOT a stable identifier, NOT unique)
        cx, cy: Centroid coordinates from YOLO detection
        final_status: healthy / unhealthy / critical
        final_health_percentage: 0.0 - 100.0
        ml_raw_output: Raw ML model output (for audit/debug)
        dashboard_data: Alias for ml_raw_output (backward compatibility)
        ml_model_version: Version of ML model that produced output (defaults to current)
        ml_schema_version: Schema version of ml_raw_output (defaults to current)
        
    Note:
        tree_number is NOT unique-constrained. YOLO may produce different
        orderings on re-run, so we allow duplicate tree_numbers per survey.
        Use tree_uuid for stable references.
    """
    # Handle backward compatibility
    raw_output = ml_raw_output or dashboard_data
    
    db_tree = models.Tree(
        survey_id=survey_id,
        tree_number=tree_number,
        cx=cx,
        cy=cy,
        final_status=final_status,
        final_health_percentage=final_health_percentage,
        critical_alert=critical_alert,
        ml_raw_output=raw_output,
        topview_id=topview_id,
        ml_model_version=ml_model_version or CURRENT_ML_MODEL_VERSION,
        ml_schema_version=ml_schema_version or CURRENT_ML_SCHEMA_VERSION
        # tree_uuid is auto-generated by default
    )
    db.add(db_tree)
    db.commit()
    db.refresh(db_tree)
    return db_tree


def get_tree(db: Session, tree_id: int):
    return db.get(models.Tree, tree_id)


def get_tree_by_uuid(db: Session, tree_uuid: str):
    """Get tree by stable UUID (preferred over tree_number)."""
    return db.query(models.Tree).filter(models.Tree.tree_uuid == tree_uuid).first()


def get_tree_by_survey_and_number(db: Session, survey_id: int, tree_number: int, topview_id: int = None):
    """Get tree by survey and number (use get_tree_by_uuid when possible)."""
    query = db.query(models.Tree).filter(
        models.Tree.survey_id == survey_id,
        models.Tree.tree_number == tree_number
    )
    if topview_id:
        query = query.filter(models.Tree.topview_id == topview_id)
    return query.first()


def get_trees_by_survey(db: Session, survey_id: int):
    return db.execute(select(models.Tree).where(models.Tree.survey_id == survey_id)).scalars().all()


def update_tree_health(db: Session, tree_id: int, final_health: float, 
                       final_status: str, critical_alert: bool = False, 
                       ml_raw_output: dict = None, dashboard_data: dict = None,
                       ml_model_version: str = None, ml_schema_version: str = None):
    """Update tree health data (source of truth).
    
    Args:
        tree_id: Database ID of the tree
        final_health: Health percentage (0.0 - 100.0)
        final_status: healthy / unhealthy / critical
        ml_raw_output: Raw ML model output (for audit)
        dashboard_data: Alias for ml_raw_output (backward compatibility)
        ml_model_version: Version of ML model (defaults to current if updating output)
        ml_schema_version: Schema version (defaults to current if updating output)
    """
    db_tree = db.get(models.Tree, tree_id)
    if not db_tree:
        return None
    db_tree.final_health_percentage = final_health
    db_tree.final_status = final_status
    db_tree.critical_alert = critical_alert
    
    raw_output = ml_raw_output or dashboard_data
    if raw_output is not None:
        db_tree.ml_raw_output = raw_output
        # Update versioning when ML output changes
        db_tree.ml_model_version = ml_model_version or CURRENT_ML_MODEL_VERSION
        db_tree.ml_schema_version = ml_schema_version or CURRENT_ML_SCHEMA_VERSION
    
    db.add(db_tree)
    db.commit()
    db.refresh(db_tree)
    return db_tree


# ------------------ TREE PARTS ------------------
def add_tree_part(db: Session, tree_id: int, part_name: str, status: str, 
                  confidence: float, extra: dict = None):
    db_part = models.TreePart(
        tree_id=tree_id,
        part_name=part_name,
        status=status,
        confidence=confidence,
        extra=extra or {}
    )
    db.add(db_part)
    db.commit()
    db.refresh(db_part)
    return db_part


def get_parts_for_tree(db: Session, tree_id: int):
    return db.execute(select(models.TreePart).where(models.TreePart.tree_id == tree_id)).scalars().all()


# ------------------ TOPVIEW (survey topview a, b, c, ...) ------------------
def get_topview(db: Session, survey_id: int, topview_order: str):
    return db.query(models.Topview).filter(
        models.Topview.survey_id == survey_id,
        models.Topview.topview_order == topview_order,
    ).first()


def get_topviews_by_survey(db: Session, survey_id: int):
    return db.query(models.Topview).filter(models.Topview.survey_id == survey_id).order_by(models.Topview.topview_order).all()


def upsert_topview(
    db: Session,
    survey_id: int,
    topview_order: str,
    image_path: str = None,
    total_trees: int = None,
    healthy_count: int = None,
    unhealthy_count: int = None,
    health_score: float = None,
    dominant_disease: str = None,
    dashboard_snapshot: dict = None,
):
    row = get_topview(db, survey_id, topview_order)
    if row is None:
        row = models.Topview(
            survey_id=survey_id,
            topview_order=topview_order,
        )
        db.add(row)
        db.flush()
    if image_path is not None:
        row.image_path = image_path
    if total_trees is not None:
        row.total_trees = total_trees
    if healthy_count is not None:
        row.healthy_count = healthy_count
    if unhealthy_count is not None:
        row.unhealthy_count = unhealthy_count
    if health_score is not None:
        row.health_score = health_score
    if dominant_disease is not None:
        row.dominant_disease = dominant_disease
    if dashboard_snapshot is not None:
        row.dashboard_snapshot = dashboard_snapshot
    db.commit()
    db.refresh(row)
    return row


def get_topview_trees(db: Session, topview_id: int):
    # Redirect to Tree table
    # TopviewTree doesn't exist anymore; return Trees linked to this topview
    return db.execute(select(models.Tree).where(models.Tree.topview_id == topview_id).order_by(models.Tree.tree_number)).scalars().all()


def upsert_topview_tree(
    db: Session,
    topview_id: int,
    tree_index: str,
    health: str = None,
    weighted_score: float = None,
    dashboard_json: dict = None,
):
    """
    Legacy adapter: writes to Tree table.
    Assumes tree_index is like 'tree_01' -> tree_number=1
    """
    # Parse tree number from string "tree_X"
    try:
        num_part = tree_index.replace("tree_", "").strip()
        tree_number = int(num_part)
    except ValueError:
        tree_number = 9999 # Fallback if naming is weird
    
    # Get associated survey_id via Topview
    topview = db.get(models.Topview, topview_id)
    if not topview:
        return None  # Should not happen
    
    # Find existing Tree by topview_id + tree_number (NOT survey_id)
    # Different topviews (a, b, c) can each have tree_01, tree_02, etc.
    row = db.query(models.Tree).filter(
        models.Tree.topview_id == topview_id,
        models.Tree.tree_number == tree_number
    ).first()
    
    if row is None:
        row = models.Tree(
            survey_id=topview.survey_id, 
            tree_number=tree_number,
            topview_id=topview_id
        )
        db.add(row)
        db.flush()
    else:
        # Link to topview if not already
        if not row.topview_id:
            row.topview_id = topview_id

    if health is not None:
        row.final_status = health
    if weighted_score is not None:
        row.final_health_percentage = weighted_score
    if dashboard_json is not None:
        row.dashboard_data = dashboard_json
        
    db.commit()
    db.refresh(row)
    return row


# =============================================================================
# UPLOAD LOCKS (Concurrency Protection)
# =============================================================================

def acquire_upload_lock(db: Session, survey_id: int, topview_order: str, 
                        locked_by: str = None, timeout_seconds: int = 300) -> bool:
    """
    Attempt to acquire an upload lock for (survey_id, topview_order).
    
    LOCK SAFETY & TRACEABILITY:
        - Each lock is tied to a request/job ID (locked_by)
        - Expiry enables crash recovery (timeout_seconds)
        - All lock operations are logged for observability
        - Lock is held per (survey_id, topview_order) scope
    
    Args:
        survey_id: Survey to lock
        topview_order: Topview order to lock  
        locked_by: REQUIRED identifier for the locker (request_id or job_id)
                   Format: 8-char hex like "a1b2c3d4" or full UUID
        timeout_seconds: Lock expiry time (default 5 min for crash recovery)
        
    Returns:
        True if lock acquired, False if already locked
        
    Logging:
        - INFO on successful acquire
        - WARNING on blocked (lock exists)
        - DEBUG on expired lock cleanup
        
    Note:
        The lock is advisory - it relies on all writers checking before write.
        This prevents race conditions when two uploads arrive simultaneously.
    """
    from datetime import datetime, timedelta, timezone
    from sqlalchemy.exc import IntegrityError
    import logging
    
    logger = logging.getLogger(__name__)
    lock_key = f"{survey_id}:{topview_order}"
    
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=timeout_seconds)
    
    # First, clean up expired locks
    expired_count = db.query(models.UploadLock).filter(
        models.UploadLock.expires_at < datetime.now(timezone.utc)
    ).delete()
    if expired_count > 0:
        logger.debug(f"🧹 Cleaned {expired_count} expired lock(s)")
    
    try:
        lock = models.UploadLock(
            survey_id=survey_id,
            topview_order=topview_order,
            locked_by=locked_by,
            expires_at=expires_at
        )
        db.add(lock)
        db.commit()
        logger.info(f"🔓 Lock ACQUIRED: {lock_key} by {locked_by or 'unknown'} (expires {timeout_seconds}s)")
        return True
    except IntegrityError:
        db.rollback()
        # Check who holds the lock for diagnostics
        existing = db.query(models.UploadLock).filter(
            models.UploadLock.survey_id == survey_id,
            models.UploadLock.topview_order == topview_order
        ).first()
        holder = existing.locked_by if existing else "unknown"
        logger.warning(f"🔒 Lock BLOCKED: {lock_key} - already held by {holder}")
        return False


def release_upload_lock(db: Session, survey_id: int, topview_order: str,
                        released_by: str = None) -> bool:
    """
    Release an upload lock.
    
    TRACEABILITY:
        - Log who released and when
        - Verify releaser matches holder (warning if mismatch)
    
    Args:
        survey_id: Survey to unlock
        topview_order: Topview order to unlock
        released_by: Request/job ID releasing the lock (for audit trail)
        
    Returns:
        True if lock was released, False if no lock existed
    """
    import logging
    logger = logging.getLogger(__name__)
    lock_key = f"{survey_id}:{topview_order}"
    
    # Check current holder for audit
    existing = db.query(models.UploadLock).filter(
        models.UploadLock.survey_id == survey_id,
        models.UploadLock.topview_order == topview_order
    ).first()
    
    if existing and released_by and existing.locked_by != released_by:
        logger.warning(
            f"⚠️ Lock release MISMATCH: {lock_key} held by {existing.locked_by}, "
            f"released by {released_by}"
        )
    
    result = db.query(models.UploadLock).filter(
        models.UploadLock.survey_id == survey_id,
        models.UploadLock.topview_order == topview_order
    ).delete()
    db.commit()
    
    if result > 0:
        logger.info(f"🔓 Lock RELEASED: {lock_key} by {released_by or 'unknown'}")
    return result > 0


def check_upload_lock(db: Session, survey_id: int, topview_order: str) -> bool:
    """
    Check if an upload lock exists (without acquiring).
    
    Returns:
        True if locked, False if available
    """
    from datetime import datetime, timezone
    
    lock = db.query(models.UploadLock).filter(
        models.UploadLock.survey_id == survey_id,
        models.UploadLock.topview_order == topview_order
    ).first()
    
    if not lock:
        return False
    
    # Check if expired
    if lock.expires_at and lock.expires_at < datetime.now(timezone.utc):
        # Clean up expired lock
        db.delete(lock)
        db.commit()
        return False
    
    return True


# =============================================================================
# ML JOBS (Async-Ready Abstraction)
# =============================================================================

def create_ml_job(db: Session, job_id: str, job_type: str, survey_id: int = None,
                  topview_order: str = None, tree_number: int = None,
                  input_path: str = None, ml_model_version: str = None,
                  ml_schema_version: str = None) -> models.MLJob:
    """
    Create a new ML job record.
    
    Job types:
        - 'topview_detection': YOLO tree detection
        - 'sideview_health': Tree health classification
        
    This is the async-ready interface. Currently runs synchronously,
    but the abstraction allows migration to queue-based execution.
    """
    job = models.MLJob(
        job_id=job_id,
        job_type=job_type,
        status="pending",
        survey_id=survey_id,
        topview_order=topview_order,
        tree_number=tree_number,
        input_path=input_path,
        ml_model_version=ml_model_version or CURRENT_ML_MODEL_VERSION,
        ml_schema_version=ml_schema_version or CURRENT_ML_SCHEMA_VERSION
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def update_ml_job_status(db: Session, job_id: str, status: str, 
                          result: dict = None, error_message: str = None,
                          output_path: str = None):
    """
    Update ML job status.
    
    Status transitions:
        pending → running → completed | failed
    """
    from datetime import datetime, timezone
    
    job = db.query(models.MLJob).filter(models.MLJob.job_id == job_id).first()
    if not job:
        return None
    
    job.status = status
    
    if status == "running":
        job.started_at = datetime.now(timezone.utc)
    elif status in ("completed", "failed"):
        job.completed_at = datetime.now(timezone.utc)
    
    if result is not None:
        job.result = result
    if error_message is not None:
        job.error_message = error_message
    if output_path is not None:
        job.output_path = output_path
    
    db.commit()
    db.refresh(job)
    return job


def get_ml_job(db: Session, job_id: str) -> models.MLJob:
    """Get ML job by ID."""
    return db.query(models.MLJob).filter(models.MLJob.job_id == job_id).first()


def get_ml_jobs_by_survey(db: Session, survey_id: int, status: str = None):
    """Get all ML jobs for a survey, optionally filtered by status."""
    query = db.query(models.MLJob).filter(models.MLJob.survey_id == survey_id)
    if status:
        query = query.filter(models.MLJob.status == status)
    return query.order_by(models.MLJob.created_at.desc()).all()
