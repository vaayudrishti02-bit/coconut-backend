# Deekshith/map/service.py
"""
Health Map Service - Generate health maps with tree positions and health status
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Storage root
STORAGE_ROOT = Path(__file__).parent.parent / "storage" / "surveys"


class HealthMapService:
    """Service for generating health maps."""
    
    def __init__(self):
        self.storage_root = STORAGE_ROOT
    
    def _get_topview_path(self, survey_id: int, topview_order: str) -> Path:
        """Get topview directory path."""
        survey_path = self.storage_root / f"SURVEY_{survey_id}"
        return survey_path / "topviews" / f"{survey_id}{topview_order}"
    
    def generate_health_map(self, survey_id: int, topview_order: str) -> dict:
        """
        Generate health map by merging topview geometry with tree health.
        
        Args:
            survey_id: Survey identifier
            topview_order: Topview order (a, b, c, etc.)
            
        Returns:
            Health map with tree positions and colors
        """
        topview_path = self._get_topview_path(survey_id, topview_order)
        
        if not topview_path.exists():
            raise FileNotFoundError(f"Topview {survey_id}{topview_order} not found")
        
        # Load topview detection (geometry)
        detection_path = topview_path / "topview_detection.json"
        if not detection_path.exists():
            raise FileNotFoundError(f"Topview detection not found for {survey_id}{topview_order}")
        
        with open(detection_path, "r") as f:
            detection = json.load(f)
        
        # Load tree health from dashboards
        trees_path = topview_path / "trees"
        tree_health_map = {}
        
        if trees_path.exists():
            for tree_dir in trees_path.iterdir():
                if tree_dir.is_dir():
                    tree_index = tree_dir.name  # e.g., "tree_01"
                    dashboard_path = tree_dir / "dashboard.json"
                    
                    if dashboard_path.exists():
                        with open(dashboard_path, "r") as f:
                            dashboard = json.load(f)
                            health = dashboard.get("tree", {}).get("health", "unknown")
                            tree_health_map[tree_index] = health
        
        # Merge geometry + health
        map_data = []
        trees = detection.get("trees", [])
        
        for tree in trees:
            # Topview detection uses 'tree_number' field and direct cx/cy coordinates
            tree_id = tree.get("tree_number") or tree.get("id")
            
            # Handle both formats: direct cx/cy or nested centroid array
            if "cx" in tree and "cy" in tree:
                x, y = tree["cx"], tree["cy"]
            elif "centroid" in tree:
                centroid = tree["centroid"]
                x, y = centroid[0], centroid[1]
            else:
                x, y = 0, 0
            
            tree_index = f"tree_{tree_id:02d}"
            
            # Get health status
            health = tree_health_map.get(tree_index, "unknown")
            
            # Map health to color
            color = self._health_to_color(health)
            
            map_data.append({
                "tree": tree_id,
                "tree_index": tree_index,
                "x": x,
                "y": y,
                "health": health,
                "color": color
            })
        
        topview_id = f"{survey_id}{topview_order}"
        
        # Check if topview image exists
        image_path = topview_path / "image.jpg"
        image_url = None
        if image_path.exists():
            # Return relative path for API access
            image_url = f"/storage/surveys/SURVEY_{survey_id}/topviews/{topview_id}/image.jpg"
        
        health_map = {
            "survey_id": survey_id,
            "topview_id": topview_id,
            "total_trees": len(map_data),
            "topview_image": image_url,
            "map": map_data
        }
        
        # Save health map
        output_path = topview_path / f"health_map_{topview_id}.json"
        with open(output_path, "w") as f:
            json.dump(health_map, f, indent=2)
        
        logger.info(f"Health map saved: {output_path}")
        
        return health_map
    
    def generate_annotated_image(self, survey_id: int, topview_order: str) -> Optional[Path]:
        """
        Generate annotated topview image with colored health pins.
        
        Args:
            survey_id: Survey identifier
            topview_order: Topview order (a, b, c, etc.)
            
        Returns:
            Path to annotated image or None if image not found
        """
        topview_path = self._get_topview_path(survey_id, topview_order)
        topview_id = f"{survey_id}{topview_order}"
        
        # Load original image
        image_path = topview_path / "image.jpg"
        if not image_path.exists():
            logger.warning(f"Topview image not found: {image_path}")
            return None
        
        # Load health map
        health_map_path = topview_path / f"health_map_{topview_id}.json"
        if not health_map_path.exists():
            # Generate health map first
            self.generate_health_map(survey_id, topview_order)
        
        with open(health_map_path, "r") as f:
            health_map = json.load(f)
        
        # Read image
        img = cv2.imread(str(image_path))
        if img is None:
            logger.error(f"Failed to load image: {image_path}")
            return None
        
        # Draw health pins
        for tree_data in health_map.get("map", []):
            x = int(tree_data["x"])
            y = int(tree_data["y"])
            color_name = tree_data["color"]
            tree_num = tree_data["tree"]
            
            # Map color names to BGR values
            color_map = {
                "green": (0, 255, 0),      # Healthy - Green
                "red": (0, 0, 255),        # Unhealthy - Red
                "grey": (128, 128, 128)    # Unknown - Grey
            }
            bgr_color = color_map.get(color_name, (128, 128, 128))
            
            # Draw outer black circle (border)
            cv2.circle(img, (x, y), 62, (0, 0, 0), 8)
            
            # Draw colored circle (pin)
            cv2.circle(img, (x, y), 60, bgr_color, -1)
            
            # Add tree number text
            font = cv2.FONT_HERSHEY_SIMPLEX
            text = str(tree_num)
            text_size = cv2.getTextSize(text, font, 1.2, 3)[0]
            text_x = x - text_size[0] // 2
            text_y = y + text_size[1] // 2
            
            # Draw text with black outline for better visibility
            cv2.putText(img, text, (text_x, text_y), font, 1.2, (0, 0, 0), 5)
            cv2.putText(img, text, (text_x, text_y), font, 1.2, (255, 255, 255), 3)
        
        # Save annotated image
        output_path = topview_path / f"health_map_annotated_{topview_id}.jpg"
        cv2.imwrite(str(output_path), img)
        
        logger.info(f"Annotated health map image saved: {output_path}")
        
        return output_path
    
    def _health_to_color(self, health: str) -> str:
        """
        Map health status to color.
        
        Args:
            health: Health status string
            
        Returns:
            Color string
        """
        color_map = {
            "healthy": "green",
            "unhealthy": "red",
            "unknown": "grey"
        }
        return color_map.get(health.lower(), "grey")
