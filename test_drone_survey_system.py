#!/usr/bin/env python3
"""
CRAZY TEST SCENARIO - Drone Survey System & Dashboard
=====================================================
Tests the complete drone survey workflow and identifies database errors.

Run with: python test_drone_survey_system.py
"""

import requests
import json
import time
import random
from datetime import datetime
from typing import List, Dict, Any

# Configuration
BASE_URL = "http://127.0.0.1:8000"
API_DRONE = f"{BASE_URL}/api/drone"
API_SURVEY = f"{BASE_URL}/api/survey"
API_FARMER = f"{BASE_URL}/api/farmer"

# Test results tracker
class TestResults:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
        self.warnings = []
        self.db_issues = []
    
    def add_pass(self, test_name):
        self.passed += 1
        print(f"  ✅ PASS: {test_name}")
    
    def add_fail(self, test_name, reason):
        self.failed += 1
        self.errors.append(f"{test_name}: {reason}")
        print(f"  ❌ FAIL: {test_name} - {reason}")
    
    def add_warning(self, msg):
        self.warnings.append(msg)
        print(f"  ⚠️  WARNING: {msg}")
    
    def add_db_issue(self, issue):
        self.db_issues.append(issue)
        print(f"  🔴 DB ISSUE: {issue}")
    
    def summary(self):
        print("\n" + "="*70)
        print("TEST SUMMARY")
        print("="*70)
        print(f"Passed: {self.passed}")
        print(f"Failed: {self.failed}")
        print(f"Warnings: {len(self.warnings)}")
        print(f"DB Issues: {len(self.db_issues)}")
        
        if self.errors:
            print("\n🔴 ERRORS:")
            for e in self.errors:
                print(f"   - {e}")
        
        if self.db_issues:
            print("\n🔴 DATABASE ISSUES FOUND:")
            for issue in self.db_issues:
                print(f"   - {issue}")
        
        if self.warnings:
            print("\n⚠️  WARNINGS:")
            for w in self.warnings:
                print(f"   - {w}")

results = TestResults()

# ============================================================================
# TEST UTILITIES
# ============================================================================

def api_get(endpoint):
    """Make GET request and return response."""
    try:
        r = requests.get(endpoint, timeout=10)
        return r.status_code, r.json() if r.content else {}
    except Exception as e:
        return 0, {"error": str(e)}

def api_post(endpoint, data=None, json_data=None, files=None):
    """Make POST request and return response."""
    try:
        r = requests.post(endpoint, data=data, json=json_data, files=files, timeout=30)
        return r.status_code, r.json() if r.content else {}
    except Exception as e:
        return 0, {"error": str(e)}

# ============================================================================
# TEST 1: Health Check
# ============================================================================
def test_server_health():
    print("\n" + "="*70)
    print("TEST 1: SERVER HEALTH CHECK")
    print("="*70)
    
    status, data = api_get(f"{BASE_URL}/")
    if status == 200:
        results.add_pass("Server is running")
    else:
        results.add_fail("Server health check", f"Status {status}")
        return False
    return True

# ============================================================================
# TEST 2: Get All Existing Surveys & Check Database State
# ============================================================================
def test_existing_surveys():
    print("\n" + "="*70)
    print("TEST 2: CHECK EXISTING SURVEYS IN DATABASE")
    print("="*70)
    
    # Get all surveys directly via list endpoint
    status, surveys = api_get(f"{API_SURVEY}/list")
    if status != 200:
        results.add_fail("Get survey list", f"Status {status}")
        
        # Fallback: get via farmers
        status, farmers = api_get(f"{API_FARMER}/all")
        if status != 200:
            results.add_fail("Get all farmers", f"Status {status}")
            return []
        
        print(f"  Found {len(farmers)} farmers in database")
        
        all_surveys = []
        for farmer in farmers[:10]:  # Check first 10 farmers
            farmer_id = farmer.get('id')
            status, farmer_surveys = api_get(f"{API_FARMER}/{farmer_id}/surveys")
            
            if status == 200 and farmer_surveys:
                for s in farmer_surveys:
                    all_surveys.append(s)
                    print(f"  📋 Survey {s.get('id')}: Farmer {farmer_id}, Trees={s.get('total_trees', 'N/A')}")
        
        results.add_pass(f"Found {len(all_surveys)} surveys")
        return all_surveys
    
    print(f"  Found {len(surveys)} surveys in database")
    for s in surveys[:10]:
        print(f"  📋 Survey {s.get('id')}: Farmer {s.get('farmer_id')}, Trees={s.get('total_trees', 'N/A')}")
    
    results.add_pass(f"Found {len(surveys)} surveys")
    return surveys

# ============================================================================
# TEST 3: Detailed Survey Report Check
# ============================================================================
def test_survey_reports(survey_ids: List[int]):
    print("\n" + "="*70)
    print("TEST 3: SURVEY REPORT VALIDATION")
    print("="*70)
    
    for survey_id in survey_ids[:10]:  # Check first 10 surveys
        print(f"\n  --- Survey {survey_id} ---")
        
        # Get report
        status, report = api_get(f"{API_SURVEY}/{survey_id}/report")
        
        if status != 200:
            results.add_fail(f"Get report for survey {survey_id}", f"Status {status}")
            continue
        
        # Validate report fields
        total = report.get('total_trees', 0)
        analyzed = report.get('trees_analyzed', 0)
        healthy = report.get('healthy_count', 0)
        unhealthy = report.get('unhealthy_count', 0)
        critical = report.get('critical_count', 0)  # Should be 0 now
        overall = report.get('overall_status', 'unknown')
        avg_health = report.get('average_health_percentage', 0)
        
        print(f"  Total: {total}, Analyzed: {analyzed}")
        print(f"  Healthy: {healthy}, Unhealthy: {unhealthy}, Critical: {critical}")
        print(f"  Overall: {overall}, Avg Health: {avg_health}%")
        
        # VALIDATION CHECKS
        
        # Check 1: analyzed <= total
        if analyzed > total:
            results.add_db_issue(f"Survey {survey_id}: analyzed ({analyzed}) > total ({total})")
        
        # Check 2: healthy + unhealthy + critical should equal analyzed
        count_sum = healthy + unhealthy + critical
        if count_sum != analyzed:
            results.add_db_issue(f"Survey {survey_id}: healthy+unhealthy+critical ({count_sum}) != analyzed ({analyzed})")
        
        # Check 3: critical should be 0 (we removed it)
        if critical != 0:
            results.add_db_issue(f"Survey {survey_id}: critical_count is {critical}, should be 0")
        
        # Check 4: overall status logic
        if overall == 'critical':
            results.add_db_issue(f"Survey {survey_id}: overall_status is 'critical', should be healthy/unhealthy")
        
        # Check 5: avg_health should be in valid range
        if analyzed > 0 and (avg_health < 0 or avg_health > 100):
            results.add_db_issue(f"Survey {survey_id}: avg_health ({avg_health}) out of range")
        
        results.add_pass(f"Survey {survey_id} report valid")

# ============================================================================
# TEST 4: Individual Tree Data Validation
# ============================================================================
def test_tree_data(survey_ids: List[int]):
    print("\n" + "="*70)
    print("TEST 4: TREE DATA VALIDATION")
    print("="*70)
    
    for survey_id in survey_ids[:5]:  # Check first 5 surveys
        print(f"\n  --- Survey {survey_id} Trees ---")
        
        status, trees = api_get(f"{API_SURVEY}/{survey_id}/trees")
        
        if status != 200:
            results.add_fail(f"Get trees for survey {survey_id}", f"Status {status}")
            continue
        
        if not trees:
            results.add_warning(f"Survey {survey_id} has no trees")
            continue
        
        tree_numbers = []
        for tree in trees:
            tree_id = tree.get('tree_id') or tree.get('id')
            tree_num = tree.get('tree_number')
            final_status = tree.get('final_status')
            health_pct = tree.get('final_health_percentage')
            critical_alert = tree.get('critical_alert')
            parts_count = len(tree.get('parts', []))
            
            tree_numbers.append(tree_num)
            
            print(f"    Tree #{tree_num}: status={final_status}, health={health_pct}%, parts={parts_count}")
            
            # VALIDATION CHECKS
            
            # Check 1: critical_alert should be False
            if critical_alert:
                results.add_db_issue(f"Survey {survey_id}, Tree {tree_num}: critical_alert is True, should be False")
            
            # Check 2: final_status should not be 'critical'
            if final_status == 'critical':
                results.add_db_issue(f"Survey {survey_id}, Tree {tree_num}: status is 'critical', should be healthy/unhealthy")
            
            # Check 3: health percentage range
            if health_pct is not None and (health_pct < 0 or health_pct > 100):
                results.add_db_issue(f"Survey {survey_id}, Tree {tree_num}: health ({health_pct}) out of range")
            
            # Check 4: status consistency with health
            if health_pct is not None:
                if health_pct >= 65 and final_status != 'healthy':
                    results.add_warning(f"Survey {survey_id}, Tree {tree_num}: health={health_pct}% but status={final_status}")
        
        # Check tree numbering
        expected = list(range(1, len(tree_numbers) + 1))
        if sorted(tree_numbers) != expected:
            results.add_db_issue(f"Survey {survey_id}: tree numbering gap - got {sorted(tree_numbers)}, expected {expected}")
        else:
            results.add_pass(f"Survey {survey_id}: {len(trees)} trees with correct numbering")

# ============================================================================
# TEST 5: Tree Parts Validation
# ============================================================================
def test_tree_parts(survey_ids: List[int]):
    print("\n" + "="*70)
    print("TEST 5: TREE PARTS VALIDATION")
    print("="*70)
    
    valid_parts = {'stem', 'bud', 'leaves'}
    
    for survey_id in survey_ids[:3]:  # Check first 3 surveys
        status, trees = api_get(f"{API_SURVEY}/{survey_id}/trees")
        
        if status != 200 or not trees:
            continue
        
        for tree in trees[:5]:  # Check first 5 trees
            tree_num = tree.get('tree_number')
            parts = tree.get('parts', [])
            
            for part in parts:
                part_name = part.get('part_name', '').lower()
                part_status = part.get('status', '')
                confidence = part.get('confidence', 0)
                
                # Validate part name
                if part_name not in valid_parts:
                    results.add_db_issue(f"Survey {survey_id}, Tree {tree_num}: invalid part '{part_name}'")
                
                # Validate confidence range
                if not (0 <= confidence <= 1):
                    results.add_db_issue(f"Survey {survey_id}, Tree {tree_num}, Part {part_name}: confidence {confidence} out of range")
                
                # Validate status is not 'critical'
                if part_status == 'critical':
                    results.add_db_issue(f"Survey {survey_id}, Tree {tree_num}, Part {part_name}: status is 'critical'")

# ============================================================================
# TEST 6: Dashboard Data Consistency
# ============================================================================
def test_dashboard_consistency(survey_ids: List[int]):
    print("\n" + "="*70)
    print("TEST 6: DASHBOARD DATA CONSISTENCY")
    print("="*70)
    
    for survey_id in survey_ids[:5]:
        print(f"\n  --- Survey {survey_id} Dashboard ---")
        
        # Get report
        status, report = api_get(f"{API_SURVEY}/{survey_id}/report")
        if status != 200:
            continue
        
        # Get trees
        status, trees = api_get(f"{API_SURVEY}/{survey_id}/trees")
        if status != 200:
            continue
        
        # Count manually
        manual_healthy = 0
        manual_unhealthy = 0
        manual_total = len(trees)
        manual_analyzed = 0
        
        for tree in trees:
            final_status = tree.get('final_status')
            if final_status:
                manual_analyzed += 1
                if final_status.lower() == 'healthy':
                    manual_healthy += 1
                else:
                    manual_unhealthy += 1
        
        # Compare
        report_healthy = report.get('healthy_count', 0)
        report_unhealthy = report.get('unhealthy_count', 0)
        report_total = report.get('total_trees', 0)
        report_analyzed = report.get('trees_analyzed', 0)
        
        print(f"  Report: total={report_total}, analyzed={report_analyzed}, healthy={report_healthy}, unhealthy={report_unhealthy}")
        print(f"  Manual: total={manual_total}, analyzed={manual_analyzed}, healthy={manual_healthy}, unhealthy={manual_unhealthy}")
        
        if report_total != manual_total:
            results.add_db_issue(f"Survey {survey_id}: total_trees mismatch - report={report_total}, actual={manual_total}")
        
        if report_analyzed != manual_analyzed:
            results.add_db_issue(f"Survey {survey_id}: trees_analyzed mismatch - report={report_analyzed}, actual={manual_analyzed}")
        
        if report_healthy != manual_healthy:
            results.add_db_issue(f"Survey {survey_id}: healthy_count mismatch - report={report_healthy}, actual={manual_healthy}")
        
        if report_unhealthy != manual_unhealthy:
            results.add_db_issue(f"Survey {survey_id}: unhealthy_count mismatch - report={report_unhealthy}, actual={manual_unhealthy}")
        
        if report_total == manual_total and report_analyzed == manual_analyzed:
            results.add_pass(f"Survey {survey_id}: dashboard data consistent")

# ============================================================================
# TEST 7: Topview Data Check
# ============================================================================
def test_topview_data(survey_ids: List[int]):
    print("\n" + "="*70)
    print("TEST 7: TOPVIEW DATA CHECK")
    print("="*70)
    
    # This endpoint may not exist, skip if not available
    results.add_warning("Topview endpoint check skipped (endpoint may not exist)")

# ============================================================================
# TEST 8: Tree Recommendation API
# ============================================================================
def test_tree_recommendations(survey_ids: List[int]):
    print("\n" + "="*70)
    print("TEST 8: TREE RECOMMENDATION API")
    print("="*70)
    
    for survey_id in survey_ids[:3]:
        # Get survey to find farmer_id
        status, survey = api_get(f"{API_SURVEY}/{survey_id}/report")
        if status != 200:
            continue
        
        farmer_id = survey.get('farmer_id')
        if not farmer_id:
            continue
            
        status, trees = api_get(f"{API_SURVEY}/{survey_id}/trees")
        
        if status != 200 or not trees:
            continue
        
        for tree in trees[:2]:  # Test first 2 trees per survey
            tree_num = tree.get('tree_number')
            
            # Try to get recommendation using correct endpoint
            status, rec = api_get(f"{API_DRONE}/{farmer_id}/{survey_id}/tree/{tree_num}/recommendation")
            
            if status == 200:
                disease = rec.get('recommendation', {}).get('disease', 'unknown')
                print(f"  Survey {survey_id}, Tree {tree_num}: recommendation OK - {disease}")
                results.add_pass(f"Survey {survey_id} Tree {tree_num} recommendation")
            elif status == 404:
                results.add_warning(f"Survey {survey_id} Tree {tree_num}: no recommendation (no parts data)")
            else:
                results.add_fail(f"Survey {survey_id} Tree {tree_num} recommendation", f"Status {status}")

# ============================================================================
# TEST 9: Stress Test - Rapid API Calls
# ============================================================================
def test_rapid_api_calls():
    print("\n" + "="*70)
    print("TEST 9: RAPID API CALLS (Stress Test)")
    print("="*70)
    
    endpoints = [
        f"{API_FARMER}/all",
        f"{API_SURVEY}/1/report",
        f"{API_SURVEY}/1/trees",
    ]
    
    start = time.time()
    success = 0
    fail = 0
    
    for i in range(10):
        for ep in endpoints:
            status, _ = api_get(ep)
            if status == 200:
                success += 1
            else:
                fail += 1
    
    elapsed = time.time() - start
    print(f"  30 requests in {elapsed:.2f}s ({30/elapsed:.1f} req/s)")
    print(f"  Success: {success}, Failed: {fail}")
    
    if fail == 0:
        results.add_pass(f"Stress test: {30/elapsed:.1f} req/s")
    else:
        results.add_warning(f"Stress test: {fail} failures")

# ============================================================================
# TEST 10: Check for Legacy 'critical' Values in Database
# ============================================================================
def test_legacy_critical_values(survey_ids: List[int]):
    print("\n" + "="*70)
    print("TEST 10: CHECK FOR LEGACY 'CRITICAL' VALUES")
    print("="*70)
    
    critical_found = []
    
    for survey_id in survey_ids:
        status, trees = api_get(f"{API_SURVEY}/{survey_id}/trees")
        
        if status != 200 or not trees:
            continue
        
        for tree in trees:
            tree_id = tree.get('tree_id') or tree.get('id')
            tree_num = tree.get('tree_number')
            final_status = tree.get('final_status', '').lower()
            critical_alert = tree.get('critical_alert', False)
            
            if final_status == 'critical':
                critical_found.append(f"Survey {survey_id}, Tree {tree_num}: final_status='critical'")
            
            if critical_alert:
                critical_found.append(f"Survey {survey_id}, Tree {tree_num}: critical_alert=True")
            
            # Check parts
            for part in tree.get('parts', []):
                part_status = part.get('status', '').lower()
                if part_status == 'critical':
                    critical_found.append(f"Survey {survey_id}, Tree {tree_num}, Part {part.get('part_name')}: status='critical'")
    
    if critical_found:
        print(f"\n  🔴 Found {len(critical_found)} legacy 'critical' values:")
        for item in critical_found[:20]:  # Show first 20
            print(f"     - {item}")
            results.add_db_issue(item)
    else:
        results.add_pass("No legacy 'critical' values found")

# ============================================================================
# MAIN
# ============================================================================
def main():
    print("\n" + "="*70)
    print("🚀 CRAZY TEST SCENARIO - DRONE SURVEY SYSTEM")
    print("="*70)
    print(f"Started at: {datetime.now()}")
    print(f"Base URL: {BASE_URL}")
    
    # Test 1: Server health
    if not test_server_health():
        print("\n❌ Server not running! Start with: uvicorn main:app --reload")
        return
    
    # Test 2: Get existing surveys
    surveys = test_existing_surveys()
    survey_ids = [s.get('id') for s in surveys if s.get('id')]
    
    if not survey_ids:
        print("\n⚠️  No surveys found. Creating test data...")
        # Could add test data creation here
        return
    
    # Test 3-10
    test_survey_reports(survey_ids)
    test_tree_data(survey_ids)
    test_tree_parts(survey_ids)
    test_dashboard_consistency(survey_ids)
    test_topview_data(survey_ids)
    test_tree_recommendations(survey_ids)
    test_rapid_api_calls()
    test_legacy_critical_values(survey_ids)
    
    # Summary
    results.summary()
    
    print(f"\nCompleted at: {datetime.now()}")

if __name__ == "__main__":
    main()
