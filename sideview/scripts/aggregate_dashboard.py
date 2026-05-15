"""
Aggregation utility for model predictions.

Drop-in file that produces a frontend-ready dashboard JSON from
the per-frame prediction list produced by the pipeline.

Usage:
    from video.scripts.aggregate_dashboard import aggregate_dashboard
    dashboard = aggregate_dashboard(predictions)

"""
from collections import Counter

PARTS = ["stem", "leaves", "bud"]
MIN_RELIABILITY = 70
TREE_HEALTH_THRESHOLD = 70

# Additional thresholds
LOW_CONFIDENCE_THRESHOLD = 50  # frames below this are considered low-confidence

# Semantic compatibility: which diseases are valid for which part
VALID_DISEASES_BY_PART = {
    "bud": {"bud root dropping", "bud rot", "healthy"},
    "leaves": {"leaf rot", "Grey leaf rot", "Whitefly", "healthy"},
    "stem": {"stem bleeding", "healthy"},
}


def _safe_conf(p, key_path, default=0.0):
    """Safely get a nested numeric confidence from a prediction dict."""
    cur = p
    try:
        for k in key_path:
            cur = cur.get(k, {})
        return float(cur) if cur is not None else default
    except Exception:
        return default


def aggregate_dashboard(predictions):
    """
    Input  : predictions (list) → your existing per-frame JSON list
    Output : dashboard summary JSON
    """

    # -----------------------------
    # 1️⃣ Basic counts and filtering
    # -----------------------------
    total_frames = len(predictions)
    ood_count = sum(1 for p in predictions if p.get("is_out_of_distribution", False))
    low_conf_count = sum(1 for p in predictions if p.get("reliability", 0) < LOW_CONFIDENCE_THRESHOLD)

    # Frames considered valid for dashboard (high reliability and not OOD)
    valid_frames = [
        p for p in predictions
        if p.get("reliability", 0) >= MIN_RELIABILITY
        and not p.get("is_out_of_distribution", False)
    ]

    if not valid_frames:
        return {
            "meta": {
                "total_frames": total_frames,
                "valid_frames": 0,
                "ood_frames": ood_count,
                "low_confidence_frames": low_conf_count
            },
            "tree": {
                "health": "unknown",
                "score": 0,
                "weighted_score": 0,
                "primary_disease": None
            },
            "parts": {}
        }

    # -----------------------------
    # 2️⃣ TREE-LEVEL AGGREGATION
    # -----------------------------
    # -----------------------------
    # 2️⃣ TREE-LEVEL AGGREGATION (counts + weighted by reliability)
    # -----------------------------
    healthy_count = sum(1 for p in valid_frames if p.get("health") == "healthy")
    total_count = len(valid_frames)

    # Simple fraction-based score
    tree_score = round((healthy_count / total_count) * 100, 2)

    # Weighted score uses reliability as weight so high-reliability frames count more
    total_weight = sum(p.get("reliability", 0) for p in valid_frames) or 1
    healthy_weight = sum(p.get("reliability", 0) for p in valid_frames if p.get("health") == "healthy")
    weighted_score = round((healthy_weight / total_weight) * 100, 2)

    # Health decision: prefer weighted score but keep a fallback to simple score
    tree_health = "healthy" if weighted_score >= TREE_HEALTH_THRESHOLD else "unhealthy"

    # Primary disease detection among unhealthy valid frames (weighted)
    tree_primary_disease = None
    primary_disease_part = None
    unhealthy_frames = [p for p in valid_frames if p.get("health") != "healthy"]
    if unhealthy_frames:
        disease_counter = Counter()
        part_disease_map = {}  # Track which part has which disease
        for p in unhealthy_frames:
            d = p.get("status", {}).get("prediction")
            part = p.get("part", {}).get("prediction")
            # Enforce part–disease compatibility and skip healthy at tree-disease level
            if not d or d == "healthy":
                continue
            if part not in VALID_DISEASES_BY_PART or d not in VALID_DISEASES_BY_PART[part]:
                continue
            disease_counter[d] += p.get("reliability", 0)
            part_disease_map[d] = part  # Remember which part has this disease

        if disease_counter:
            most_common_disease = disease_counter.most_common(1)[0][0]
            tree_primary_disease = most_common_disease
            primary_disease_part = part_disease_map.get(most_common_disease)

    # -----------------------------
    # 3️⃣ PART-WISE AGGREGATION
    # -----------------------------
    part_results = {}

    for part in PARTS:
        part_frames = [
            p for p in valid_frames
            if p.get("part", {}).get("prediction") == part
        ]

        if not part_frames:
            part_results[part] = {
                "health": "unknown",
                "score": 0,
                "weighted_score": 0,
                "frames": 0,
                "avg_part_confidence": 0,
                "avg_status_confidence": 0,
                "diseases": {}
            }
            continue

        part_total = len(part_frames)
        part_healthy = sum(1 for p in part_frames if p.get("health") == "healthy")

        # Simple score
        part_score = round((part_healthy / part_total) * 100, 2)

        # Weighted score by reliability
        total_w = sum(p.get("reliability", 0) for p in part_frames) or 1
        healthy_w = sum(p.get("reliability", 0) for p in part_frames if p.get("health") == "healthy")
        part_weighted = round((healthy_w / total_w) * 100, 2)

        # Average confidences (if present)
        avg_part_conf = round(sum(_safe_conf(p, ("part", "confidence")) for p in part_frames) / part_total, 2)
        avg_status_conf = round(sum(_safe_conf(p, ("status", "confidence")) for p in part_frames) / part_total, 2)

        # Disease breakdown (weighted by reliability)
        diseases = {}
        diseased_frames = [p for p in part_frames if p.get("health") != "healthy"]
        if diseased_frames:
            d_counter = Counter()
            for p in diseased_frames:
                d = p.get("status", {}).get("prediction")
                if not d or d == "healthy":
                    continue
                # Enforce part–disease compatibility
                if part not in VALID_DISEASES_BY_PART or d not in VALID_DISEASES_BY_PART[part]:
                    continue
                d_counter[d] += p.get("reliability", 0)

            total_diseased_w = sum(d_counter.values()) or 1
            diseases = {d: round((w / total_diseased_w) * 100, 2) for d, w in d_counter.items()}

        part_results[part] = {
            "health": "healthy" if part_weighted >= TREE_HEALTH_THRESHOLD else "unhealthy",
            "score": part_score,
            "weighted_score": part_weighted,
            "frames": part_total,
            "avg_part_confidence": avg_part_conf,
            "avg_status_confidence": avg_status_conf,
            "diseases": diseases
        }

    # ✅ CONDITIONAL PROPAGATION: Only set primary_disease if tree is unhealthy
    # This prevents the semantic contradiction of "healthy tree with a disease"
    final_primary_disease = None
    primary_issue = None
    
    if tree_health == "unhealthy" and tree_primary_disease:
        final_primary_disease = tree_primary_disease
        primary_issue = {
            "disease": tree_primary_disease,
            "part": primary_disease_part,
            "severity": "localized" if weighted_score > 50 else "critical"
        }
    elif tree_health == "healthy" and tree_primary_disease:
        # Tree is healthy overall but has a localized issue
        primary_issue = {
            "disease": tree_primary_disease,
            "part": primary_disease_part,
            "severity": "localized",
            "note": "Tree is healthy overall with a localized part issue"
        }

    # -----------------------------
    # 4️⃣ FINAL DASHBOARD JSON
    # -----------------------------
    return {
        "meta": {
            "total_frames": total_frames,
            "valid_frames": total_count,
            "ood_frames": ood_count,
            "low_confidence_frames": low_conf_count
        },
        "tree": {
            "health": tree_health,
            "score": tree_score,
            "weighted_score": weighted_score,
            "primary_disease": final_primary_disease,
            "primary_issue": primary_issue
        },
        "parts": part_results
    }
