# backend/sideview/aggregator.py
"""
Health Aggregation Utilities for Sideview

AGGREGATION FORMULAS (Formally Defined):
========================================

1. CONSENSUS AGGREGATION (aggregate_health_robust):
   - Input: List of {status, confidence} observations
   - Method: Majority voting weighted by confidence
   - Formula:
     final_status = mode(statuses)  # Most common status
     base_confidence = mean(confidence[status == final_status])
     consensus_factor = count(final_status) / total_count
     final_confidence = base_confidence × (0.7 + 0.3 × consensus_factor)
   
2. HEALTH SCORE CALCULATION:
   - healthy: weighted_score >= HEALTH_THRESHOLD (65)
   - unhealthy: weighted_score < HEALTH_THRESHOLD
   
3. OOD (Out-of-Distribution) PENALTY:
   - If ood_ratio > OOD_THRESHOLD (0.3):
     confidence_penalty = ood_ratio × 0.5
     final_confidence = max(0.1, final_confidence - confidence_penalty)
   - This prevents false high scores from unreliable predictions

4. TREE HEALTH AGGREGATION:
   - Priority order: unhealthy > healthy
   - If ANY part is unhealthy → tree is unhealthy
   - Only if ALL parts are healthy → tree is healthy
"""

import logging
from typing import List, Dict, Any
from collections import Counter

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION THRESHOLDS (Documented for reproducibility)
# ============================================================================
HEALTH_THRESHOLD = 65       # weighted_score >= 65 → healthy (updated from 70)
OOD_THRESHOLD = 0.3         # ood_ratio > 0.3 triggers penalty
OOD_PENALTY_FACTOR = 0.5    # How much to penalize per OOD ratio
MIN_CONFIDENCE = 0.1        # Floor for confidence after penalties
# ============================================================================


def aggregate_health_robust(data, ood_count: int = 0) -> Dict[str, Any]:
    """
    Aggregate health status from multiple observations using robust voting.
    
    FORMULA:
        final_status = mode(statuses)
        base_confidence = mean(confidence where status == final_status)
        consensus_factor = count(final_status) / len(statuses)
        final_confidence = base_confidence × (0.7 + 0.3 × consensus_factor)
        
        # OOD penalty (for avoiding false positives)
        if ood_ratio > OOD_THRESHOLD:
            penalty = ood_ratio × OOD_PENALTY_FACTOR
            final_confidence = max(MIN_CONFIDENCE, final_confidence - penalty)
    
    Args:
        data: Either a List of observation dictionaries with 'status' or 'health' fields,
              OR a Dict mapping part names to lists of observations (e.g. {"stem": [...], "bud": [...]})
        ood_count: Number of out-of-distribution frames (previously ignored!)
        
    Returns:
        Dictionary with aggregated status, confidence, and reliability metrics
    """
    # Handle dict format (tree-level data from drone_router)
    if isinstance(data, dict) and all(isinstance(v, list) for v in data.values()):
        # Flatten all observations from all parts
        flat_data = []
        for part_name, observations in data.items():
            for obs in observations:
                flat_data.append(obs)
        data = flat_data
    
    if not data:
        return {
            "status": "unknown",
            "confidence": 0.0,
            "total_observations": 0,
            "reliability_score": 0.0,
            "ood_penalty_applied": False,
            "final_status": "unknown",
            "final_tree_health": 0.0,
            "critical_alert": False
        }
    
    # Extract statuses from data
    statuses = []
    confidences = []
    
    for item in data:
        status = item.get('status') or item.get('health') or item.get('prediction', {}).get('status')
        
        if status:
            if isinstance(status, dict):
                status_val = status.get('prediction') or status.get('status')
                conf = float(status.get('confidence', 0.0))
            else:
                status_val = status
                conf = float(item.get('confidence', 0.5))
            
            if status_val:
                statuses.append(str(status_val).lower())
                confidences.append(conf)
    
    if not statuses:
        return {
            "status": "unknown",
            "confidence": 0.0,
            "total_observations": len(data),
            "reliability_score": 0.0,
            "ood_penalty_applied": False,
            "final_status": "unknown",
            "final_tree_health": 0.0,
            "critical_alert": False
        }
    
    # Step 1: Majority voting
    status_counter = Counter(statuses)
    most_common_status, count = status_counter.most_common(1)[0]
    
    # Step 2: Calculate base confidence (mean of matching statuses)
    status_confidences = [
        conf for status, conf in zip(statuses, confidences)
        if status == most_common_status
    ]
    base_confidence = sum(status_confidences) / len(status_confidences) if status_confidences else 0.0
    
    # Step 3: Apply consensus factor
    consensus_factor = count / len(statuses)
    final_confidence = base_confidence * (0.7 + 0.3 * consensus_factor)
    
    # Step 4: OOD PENALTY (CRITICAL FIX - was previously ignored!)
    total_frames = len(data) + ood_count
    ood_ratio = ood_count / total_frames if total_frames > 0 else 0.0
    ood_penalty_applied = False
    
    if ood_ratio > OOD_THRESHOLD:
        penalty = ood_ratio * OOD_PENALTY_FACTOR
        final_confidence = max(MIN_CONFIDENCE, final_confidence - penalty)
        ood_penalty_applied = True
        logger.warning(f"OOD penalty applied: ratio={ood_ratio:.2f}, penalty={penalty:.2f}")
    
    # Calculate reliability score (0-100 scale for API)
    reliability_score = final_confidence * 100
    
    return {
        "status": most_common_status,
        "confidence": round(final_confidence, 3),
        "reliability_score": round(reliability_score, 1),
        "total_observations": len(data),
        "ood_frames": ood_count,
        "ood_ratio": round(ood_ratio, 3),
        "ood_penalty_applied": ood_penalty_applied,
        "consensus": round(consensus_factor, 3),
        "status_distribution": dict(status_counter),
        # Backward compatibility fields for drone_router
        "final_status": most_common_status,
        "final_tree_health": round(reliability_score, 1),
        "critical_alert": False  # Removed critical concept
    }


def aggregate_by_part(data: List[Dict[str, Any]], part: str) -> Dict[str, Any]:
    """
    Aggregate health status for a specific tree part.
    
    Args:
        data: List of observation dictionaries
        part: Part name (e.g., 'stem', 'bud', 'leaves')
        
    Returns:
        Aggregated results for the specified part
    """
    # Filter data for the specific part
    # Handle both flat format (part="leaves") and nested format (part={"prediction": "leaves"})
    def get_part_name(item):
        part_val = item.get('part') or item.get('part_name', '')
        if isinstance(part_val, dict):
            return part_val.get('prediction', '').lower()
        return str(part_val).lower()
    
    part_data = [
        item for item in data
        if get_part_name(item) == part.lower()
    ]
    
    if not part_data:
        return {
            "part": part,
            "status": "no_data",
            "confidence": 0.0,
            "observations": 0
        }
    
    agg_result = aggregate_health_robust(part_data)
    agg_result['part'] = part
    agg_result['observations'] = len(part_data)
    
    return agg_result


def aggregate_tree_health(tree_data: Dict[str, List[Dict[str, Any]]], ood_frames: int = 0) -> Dict[str, Any]:
    """
    Aggregate overall tree health from multiple parts.
    
    AGGREGATION RULES (Formally Defined):
    =====================================
    1. Priority: unhealthy > healthy
    2. If ANY part is unhealthy → tree is UNHEALTHY  
    3. Only if ALL assessed parts are healthy → tree is HEALTHY
    4. OOD frames reduce overall confidence
    
    CONFIDENCE CALCULATION:
        base = mean(part confidences)
        if ood_ratio > OOD_THRESHOLD: apply penalty
        
    Args:
        tree_data: Dictionary mapping part names to lists of observations
        ood_frames: Number of out-of-distribution frames
        
    Returns:
        Overall tree health assessment with explicit reliability metrics
    """
    part_results = {}
    all_statuses = []
    all_confidences = []
    
    for part, observations in tree_data.items():
        part_agg = aggregate_by_part(observations, part)
        part_results[part] = part_agg
        
        if part_agg['status'] not in ['no_data', 'unknown']:
            all_statuses.append(part_agg['status'])
            all_confidences.append(part_agg.get('confidence', 0.5))
    
    # Determine overall tree health using PRIORITY RULES
    if not all_statuses:
        overall_status = "unknown"
        overall_confidence = 0.0
        health_reason = "No valid observations"
    else:
        # Rule: Check for any unhealthy status (any status that's not healthy)
        has_unhealthy = any('unhealthy' in s or s not in ['healthy', 'no_data', 'unknown'] for s in all_statuses)
        
        if has_unhealthy:
            overall_status = "unhealthy"
            overall_confidence = 0.7
            health_reason = "Disease detected in one or more parts"
        elif all('healthy' in s for s in all_statuses):
            overall_status = "healthy"
            overall_confidence = 0.9
            health_reason = "All assessed parts are healthy"
        else:
            overall_status = "needs_inspection"
            overall_confidence = 0.5
            health_reason = "Mixed or inconclusive results"
    
    # Apply OOD penalty to overall confidence
    total_obs = sum(len(obs) for obs in tree_data.values())
    total_frames = total_obs + ood_frames
    ood_ratio = ood_frames / total_frames if total_frames > 0 else 0.0
    
    ood_penalty_applied = False
    if ood_ratio > OOD_THRESHOLD and overall_confidence > MIN_CONFIDENCE:
        penalty = ood_ratio * OOD_PENALTY_FACTOR
        overall_confidence = max(MIN_CONFIDENCE, overall_confidence - penalty)
        ood_penalty_applied = True
        logger.warning(f"Tree-level OOD penalty: ratio={ood_ratio:.2f}")
    
    # Calculate weighted score (0-100) for API compatibility
    weighted_score = overall_confidence * 100
    
    return {
        "overall_status": overall_status,
        "health": overall_status,  # Alias for backward compatibility
        "overall_confidence": round(overall_confidence, 3),
        "weighted_score": round(weighted_score, 1),
        "reliability_score": round(weighted_score, 1),  # Alias
        "health_reason": health_reason,
        "parts": part_results,
        "total_parts_assessed": len(part_results),
        "ood_frames": ood_frames,
        "ood_ratio": round(ood_ratio, 3),
        "ood_penalty_applied": ood_penalty_applied,
        # Explicit formula documentation
        "_aggregation_formula": "priority_voting_with_ood_penalty",
        "_thresholds": {
            "health": HEALTH_THRESHOLD,
            "ood": OOD_THRESHOLD
        }
    }
