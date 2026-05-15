#!/usr/bin/env python3
"""
Quick Test Script for Deekshith Survey Orchestration

This script demonstrates the complete workflow:
1. Create survey
2. Upload topview image
3. Upload tree video (mock)
4. Generate dashboards
5. Generate health map
6. Get final result

Prerequisites:
- Server running on http://localhost:800
- Sample images/videos in test_data/
"""

import requests
import json
from pathlib import Path

BASE_URL = "http://localhost:8000"

def create_survey():
    """Create a new survey."""
    print("\n1️⃣ Creating survey...")
    
    response = requests.post(
        f"{BASE_URL}/survey/create",
        json={
            "farmer_id": "F001",
            "location": {"lat": 12.97, "lon": 77.59}
        }
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Survey created: {result['survey_id']}")
        return result['survey_id']
    else:
        print(f"❌ Failed: {response.text}")
        return None

def upload_topview(survey_id, topview_order, image_path):
    """Upload topview image."""
    print(f"\n2️⃣ Uploading topview {topview_order}...")
    
    with open(image_path, 'rb') as f:
        files = {'image': f}
        data = {'topview_order': topview_order}
        
        response = requests.post(
            f"{BASE_URL}/survey/{survey_id}/topview",
            files=files,
            data=data
        )
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Topview uploaded: {result['topview_id']} with {result['tree_count']} trees")
        return result['tree_count']
    else:
        print(f"❌ Failed: {response.text}")
        return 0

def upload_tree_video(survey_id, topview_order, tree_index, video_path):
    """Upload tree video."""
    print(f"\n3️⃣ Uploading tree {tree_index} video...")
    
    with open(video_path, 'rb') as f:
        files = {'video': f}
        
        response = requests.post(
            f"{BASE_URL}/survey/{survey_id}/topview/{topview_order}/tree/{tree_index}/video",
            files=files
        )
    
    if response.status_code == 200:
        result = response.json()
        health = result['dashboard']['tree']['health']
        print(f"✅ Tree video processed: {result['tree_id']} - Health: {health}")
        return True
    else:
        print(f"❌ Failed: {response.text}")
        return False

def generate_topview_dashboard(survey_id, topview_order):
    """Generate topview dashboard."""
    print(f"\n4️⃣ Generating topview dashboard...")
    
    response = requests.post(
        f"{BASE_URL}/survey/{survey_id}/topview/{topview_order}/dashboard"
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Dashboard generated: {result['total_trees']} trees, {result['healthy']} healthy")
        print(f"   Health Score: {result['health_score']}%")
        return True
    else:
        print(f"❌ Failed: {response.text}")
        return False

def generate_health_map(survey_id, topview_order):
    """Generate health map."""
    print(f"\n5️⃣ Generating health map...")
    
    response = requests.get(
        f"{BASE_URL}/survey/{survey_id}/topview/{topview_order}/health-map"
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Health map generated: {result['total_trees']} trees mapped")
        
        # Show color distribution
        colors = {}
        for item in result['map']:
            color = item['color']
            colors[color] = colors.get(color, 0) + 1
        
        print(f"   Colors: {colors}")
        return True
    else:
        print(f"❌ Failed: {response.text}")
        return False

def generate_final_dashboard(survey_id):
    """Generate final survey dashboard."""
    print(f"\n6️⃣ Generating final survey dashboard...")
    
    response = requests.post(
        f"{BASE_URL}/survey/{survey_id}/dashboard"
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Final dashboard generated:")
        print(f"   Total Trees: {result['total_trees']}")
        print(f"   Healthy: {result['healthy']}")
        print(f"   Unhealthy: {result['unhealthy']}")
        print(f"   Overall Health Score: {result['overall_health_score']}%")
        return True
    else:
        print(f"❌ Failed: {response.text}")
        return False

def get_survey_result(survey_id):
    """Get complete survey result."""
    print(f"\n7️⃣ Fetching complete survey result...")
    
    response = requests.get(
        f"{BASE_URL}/survey/{survey_id}/result"
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Survey result retrieved:")
        print(json.dumps(result, indent=2))
        return result
    else:
        print(f"❌ Failed: {response.text}")
        return None

def main():
    """Run complete workflow."""
    print("=" * 60)
    print("🌴 Deekshith Survey Orchestration - Test Script")
    print("=" * 60)
    
    # Check if server is running
    try:
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code != 200:
            print("❌ Server is not healthy. Please start the server first.")
            return
    except Exception as e:
        print(f"❌ Cannot connect to server at {BASE_URL}")
        print(f"   Error: {str(e)}")
        print("\nPlease start the server with:")
        print("   uvicorn main:app --reload --host 0.0.0.0 --port 800")
        return
    
    # Test data paths (you need to provide these)
    test_data_dir = Path("test_data")
    
    # Check if test data exists
    if not test_data_dir.exists():
        print("\n⚠️  test_data/ directory not found.")
        print("Please create test_data/ with:")
        print("  - topview_a.jpg (topview image)")
        print("  - tree_video.mp4 (tree video)")
        return
    
    topview_image = test_data_dir / "topview_a.jpg"
    tree_video = test_data_dir / "tree_video.mp4"
    
    if not topview_image.exists():
        print(f"❌ {topview_image} not found")
        return
    
    if not tree_video.exists():
        print(f"❌ {tree_video} not found")
        return
    
    # Run workflow
    survey_id = create_survey()
    if not survey_id:
        return
    
    tree_count = upload_topview(survey_id, 'a', topview_image)
    if not tree_count:
        return
    
    # Upload video for first tree only (for testing)
    if upload_tree_video(survey_id, 'a', 1, tree_video):
        generate_topview_dashboard(survey_id, 'a')
        generate_health_map(survey_id, 'a')
        generate_final_dashboard(survey_id)
        get_survey_result(survey_id)
    
    print("\n" + "=" * 60)
    print("✅ Test complete!")
    print("=" * 60)

if __name__ == "__main__":
    main()
