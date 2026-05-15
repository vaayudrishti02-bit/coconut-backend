"""
Data Repair Script: Fix survey 46 topview B data
=================================================
Problem: Topview B has 0 trees in DB because the topview_link service
was reading 'centroids' instead of 'trees' from the detection API response.
The sideview_link service was also finding trees by survey_id+tree_number
instead of topview_id+tree_number, so topview B's video analysis results
were written to topview A's trees.

This script:
1. Creates Tree records in DB for topview B (from file-based detection data)
2. Updates those trees with health data from file-based dashboard.json files
3. Regenerates topview B's dashboard snapshot from the new DB records
4. Updates survey total_trees to reflect BOTH topviews
5. Regenerates the survey-level dashboard
"""

import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

STORAGE_ROOT = Path(__file__).parent / "Deekshith" / "storage" / "surveys"
SURVEY_ID = 46


def repair():
    from db.database import SessionLocal
    from db import crud, models
    from Deekshith.dashboard.aggregator import DashboardAggregator

    db = SessionLocal()
    try:
        # Step 1: Get topview B record
        topview_b = crud.get_topview(db, SURVEY_ID, "b")
        if not topview_b:
            logger.error("Topview B not found in DB!")
            return
        
        logger.info(f"Topview B: id={topview_b.id}, total_trees={topview_b.total_trees}")
        
        # Step 2: Check existing trees for topview B
        existing_trees = db.query(models.Tree).filter(
            models.Tree.topview_id == topview_b.id
        ).all()
        logger.info(f"Existing trees for topview B: {len(existing_trees)}")
        
        # Step 3: Load detection data from files
        topview_b_path = STORAGE_ROOT / f"SURVEY_{SURVEY_ID}" / "topviews" / f"{SURVEY_ID}b"
        detection_path = topview_b_path / "topview_detection.json"
        
        if not detection_path.exists():
            logger.error(f"Detection file not found: {detection_path}")
            return
        
        with open(detection_path) as f:
            detection = json.load(f)
        
        tree_count = detection.get("count", 0)
        detected_trees = detection.get("trees", [])
        logger.info(f"Detection data: {tree_count} trees detected")
        
        # Step 4: Create Tree records for topview B if they don't exist
        for tree_data in detected_trees:
            tree_number = tree_data.get("tree_number", 0)
            cx = int(tree_data.get("cx", 0))
            cy = int(tree_data.get("cy", 0))
            
            # Check if tree already exists for this topview
            existing = db.query(models.Tree).filter(
                models.Tree.topview_id == topview_b.id,
                models.Tree.tree_number == tree_number
            ).first()
            
            if existing:
                logger.info(f"  Tree {tree_number} already exists (id={existing.id}), updating cx/cy")
                existing.cx = cx
                existing.cy = cy
            else:
                new_tree = models.Tree(
                    survey_id=SURVEY_ID,
                    tree_number=tree_number,
                    topview_id=topview_b.id,
                    cx=cx,
                    cy=cy,
                )
                db.add(new_tree)
                logger.info(f"  Created tree {tree_number} for topview B")
        
        db.commit()
        
        # Step 5: Update tree health from file-based dashboard.json files
        trees_path = topview_b_path / "trees"
        for tree_dir in sorted(trees_path.iterdir()):
            if not tree_dir.is_dir():
                continue
            
            dashboard_file = tree_dir / "dashboard.json"
            if not dashboard_file.exists():
                continue
            
            with open(dashboard_file) as f:
                tree_dash = json.load(f)
            
            tree_index_str = tree_dir.name  # e.g., "tree_01"
            tree_number = int(tree_index_str.replace("tree_", ""))
            
            tree_health = tree_dash.get("tree", {})
            health_status = tree_health.get("health", "unknown")
            health_score = tree_health.get("weighted_score", 0.0)
            
            tree_record = db.query(models.Tree).filter(
                models.Tree.topview_id == topview_b.id,
                models.Tree.tree_number == tree_number
            ).first()
            
            if tree_record:
                tree_record.final_status = health_status
                tree_record.final_health_percentage = float(health_score) if health_score else 0.0
                tree_record.ml_raw_output = tree_dash
                logger.info(f"  Updated tree {tree_number}: {health_status} ({health_score}%)")
        
        db.commit()
        
        # Step 6: Regenerate topview B dashboard from DB
        aggregator = DashboardAggregator(db=db)
        try:
            dashboard_b = aggregator.generate_topview_dashboard_from_db(db, SURVEY_ID, "b")
            logger.info(f"Topview B dashboard: {json.dumps(dashboard_b, indent=2)}")
            
            # Save to DB
            crud.upsert_topview(
                db,
                survey_id=SURVEY_ID,
                topview_order="b",
                total_trees=dashboard_b.get("total_trees"),
                healthy_count=dashboard_b.get("healthy"),
                unhealthy_count=dashboard_b.get("unhealthy"),
                health_score=dashboard_b.get("health_score"),
                dominant_disease=dashboard_b.get("dominant_disease"),
                dashboard_snapshot=dashboard_b,
            )
        except FileNotFoundError:
            logger.warning("Could not generate topview B dashboard from DB, using file-based")
            dashboard_b = aggregator.generate_topview_dashboard(SURVEY_ID, "b")
        
        # Step 7: Also fix topview A's trees (they might have been updated with B's data)
        topview_a = crud.get_topview(db, SURVEY_ID, "a")
        if topview_a:
            trees_a_path = STORAGE_ROOT / f"SURVEY_{SURVEY_ID}" / "topviews" / f"{SURVEY_ID}a" / "trees"
            if trees_a_path.exists():
                for tree_dir in sorted(trees_a_path.iterdir()):
                    if not tree_dir.is_dir():
                        continue
                    dashboard_file = tree_dir / "dashboard.json"
                    if not dashboard_file.exists():
                        continue
                    with open(dashboard_file) as f:
                        tree_dash = json.load(f)
                    tree_number = int(tree_dir.name.replace("tree_", ""))
                    tree_record = db.query(models.Tree).filter(
                        models.Tree.topview_id == topview_a.id,
                        models.Tree.tree_number == tree_number
                    ).first()
                    if tree_record:
                        tree_health = tree_dash.get("tree", {})
                        tree_record.final_status = tree_health.get("health", "unknown")
                        tree_record.final_health_percentage = float(tree_health.get("weighted_score", 0.0))
                        tree_record.ml_raw_output = tree_dash
                        logger.info(f"  Restored topview A tree {tree_number}: {tree_record.final_status}")
                
                db.commit()
                
                # Regenerate topview A dashboard
                try:
                    dashboard_a = aggregator.generate_topview_dashboard_from_db(db, SURVEY_ID, "a")
                    crud.upsert_topview(
                        db, survey_id=SURVEY_ID, topview_order="a",
                        total_trees=dashboard_a.get("total_trees"),
                        healthy_count=dashboard_a.get("healthy"),
                        unhealthy_count=dashboard_a.get("unhealthy"),
                        health_score=dashboard_a.get("health_score"),
                        dominant_disease=dashboard_a.get("dominant_disease"),
                        dashboard_snapshot=dashboard_a,
                    )
                    logger.info(f"Topview A dashboard regenerated: {json.dumps(dashboard_a, indent=2)}")
                except Exception as e:
                    logger.warning(f"Could not regenerate topview A: {e}")
        
        # Step 8: Update survey total_trees to sum across all topviews
        all_topviews = crud.get_topviews_by_survey(db, SURVEY_ID)
        total = sum(tv.total_trees or 0 for tv in all_topviews)
        survey = crud.get_survey(db, SURVEY_ID)
        if survey:
            survey.total_trees = total
            db.commit()
            logger.info(f"Survey {SURVEY_ID} total_trees updated to {total}")
        
        # Step 9: Verify
        print("\n" + "=" * 60)
        print("REPAIR COMPLETE - Verification:")
        print("=" * 60)
        
        for tv in all_topviews:
            db.refresh(tv)
            trees = db.query(models.Tree).filter(models.Tree.topview_id == tv.id).all()
            print(f"\nTopview {tv.topview_order}: total_trees={tv.total_trees}, "
                  f"healthy={tv.healthy_count}, unhealthy={tv.unhealthy_count}, "
                  f"health_score={tv.health_score}")
            for t in trees:
                print(f"  Tree {t.tree_number}: status={t.final_status}, health={t.final_health_percentage}%")
        
        db.refresh(survey)
        print(f"\nSurvey {SURVEY_ID}: total_trees={survey.total_trees}")
        
    finally:
        db.close()


if __name__ == "__main__":
    repair()
