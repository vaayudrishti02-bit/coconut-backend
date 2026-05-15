#!/usr/bin/env python3
"""
DATABASE CLEANUP SCRIPT - Remove Legacy 'Critical' Values
==========================================================
This script fixes:
1. Trees with final_status='critical' -> 'unhealthy'
2. Trees with critical_alert=True -> False
3. TreeParts with status='critical' -> 'unhealthy'
4. Recalculates health status based on current threshold (65%)

Run with: python fix_legacy_critical_data.py
"""

from db.database import SessionLocal
from db.models import Survey, Tree, TreePart
from sqlalchemy import func

HEALTH_THRESHOLD = 65  # Trees with health >= 65% are healthy

def main():
    db = SessionLocal()
    
    print("="*70)
    print("DATABASE CLEANUP - FIXING LEGACY 'CRITICAL' VALUES")
    print("="*70)
    
    changes = {
        'trees_status_fixed': 0,
        'trees_alert_fixed': 0,
        'parts_fixed': 0,
        'health_status_fixed': 0
    }
    
    # Fix 1: Trees with final_status='critical'
    print("\n1. Fixing trees with final_status='critical'...")
    critical_trees = db.query(Tree).filter(Tree.final_status == 'critical').all()
    print(f"   Found: {len(critical_trees)} trees")
    
    for tree in critical_trees:
        tree.final_status = 'unhealthy'
        changes['trees_status_fixed'] += 1
    
    # Fix 2: Trees with critical_alert=True
    print("\n2. Fixing trees with critical_alert=True...")
    alert_trees = db.query(Tree).filter(Tree.critical_alert == True).all()
    print(f"   Found: {len(alert_trees)} trees")
    
    for tree in alert_trees:
        tree.critical_alert = False
        changes['trees_alert_fixed'] += 1
    
    # Fix 3: TreeParts with status='critical'
    print("\n3. Fixing tree parts with status='critical'...")
    critical_parts = db.query(TreePart).filter(TreePart.status == 'critical').all()
    print(f"   Found: {len(critical_parts)} parts")
    
    for part in critical_parts:
        part.status = 'unhealthy'
        changes['parts_fixed'] += 1
    
    # Fix 4: Recalculate health status based on threshold
    print(f"\n4. Recalculating health status (threshold={HEALTH_THRESHOLD}%)...")
    
    # Trees with health >= 65% should be healthy
    trees_should_be_healthy = db.query(Tree).filter(
        Tree.final_health_percentage >= HEALTH_THRESHOLD,
        Tree.final_status != 'healthy'
    ).all()
    
    for tree in trees_should_be_healthy:
        if tree.final_status:  # Only fix if already analyzed
            old_status = tree.final_status
            tree.final_status = 'healthy'
            changes['health_status_fixed'] += 1
            print(f"   Tree {tree.id}: {old_status} -> healthy (health={tree.final_health_percentage}%)")
    
    # Trees with health < 65% should be unhealthy
    trees_should_be_unhealthy = db.query(Tree).filter(
        Tree.final_health_percentage < HEALTH_THRESHOLD,
        Tree.final_health_percentage != None,
        Tree.final_status == 'healthy'
    ).all()
    
    for tree in trees_should_be_unhealthy:
        old_status = tree.final_status
        tree.final_status = 'unhealthy'
        changes['health_status_fixed'] += 1
        print(f"   Tree {tree.id}: {old_status} -> unhealthy (health={tree.final_health_percentage}%)")
    
    # Commit changes
    print("\n" + "="*70)
    print("COMMITTING CHANGES...")
    print("="*70)
    
    try:
        db.commit()
        print("✅ Changes committed successfully!")
    except Exception as e:
        db.rollback()
        print(f"❌ Error: {e}")
        return
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"Trees status fixed (critical->unhealthy): {changes['trees_status_fixed']}")
    print(f"Trees alert fixed (True->False): {changes['trees_alert_fixed']}")
    print(f"Parts fixed (critical->unhealthy): {changes['parts_fixed']}")
    print(f"Health status corrected: {changes['health_status_fixed']}")
    print(f"\nTotal changes: {sum(changes.values())}")
    
    # Verify
    print("\n" + "="*70)
    print("VERIFICATION")
    print("="*70)
    
    remaining_critical_trees = db.query(Tree).filter(Tree.final_status == 'critical').count()
    remaining_critical_alerts = db.query(Tree).filter(Tree.critical_alert == True).count()
    remaining_critical_parts = db.query(TreePart).filter(TreePart.status == 'critical').count()
    
    print(f"Remaining critical trees: {remaining_critical_trees}")
    print(f"Remaining critical alerts: {remaining_critical_alerts}")
    print(f"Remaining critical parts: {remaining_critical_parts}")
    
    if remaining_critical_trees == 0 and remaining_critical_alerts == 0 and remaining_critical_parts == 0:
        print("\n✅ All legacy 'critical' values have been cleaned!")
    else:
        print("\n⚠️  Some critical values still remain!")
    
    db.close()

if __name__ == "__main__":
    main()
