import cv2

def compute_iou(boxA, boxB):
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])

    inter = max(0, xB - xA) * max(0, yB - yA)
    if inter <= 0:
        return 0.0

    areaA = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
    areaB = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])

    return inter / (areaA + areaB - inter)


def assign_numbers(dets, img_height, row_eps_px=None):
    """
    dets: list of {"id": int, "bbox": [...], "centroid": [cx, cy]}
    Converts detections into per-row numbering based on centroid Y coordinate.
    Returns list of centroids with keys: `cx`, `cy`, `bbox`, `tree_number`.
    """

    if not dets:
        return []

    # Convert detection format → centroid dicts
    centroids = []
    for d in dets:
        if "centroid" in d and d["centroid"]:
            cx, cy = d["centroid"]
        else:
            # fallback to keys used in older code
            cx = d.get("cx")
            cy = d.get("cy")

        centroids.append({
            "cx": int(cx),
            "cy": int(cy),
            "bbox": d.get("bbox")
        })

    # Auto row grouping threshold
    if row_eps_px is None:
        row_eps_px = max(25, int(img_height * 0.07))

    # Sort by vertical order
    centroids_sorted = sorted(centroids, key=lambda c: c["cy"])

    rows = []
    current_row = [centroids_sorted[0]]

    # Group into rows using average Y for stability
    for c in centroids_sorted[1:]:
        avg_y = sum(p["cy"] for p in current_row) / len(current_row)

        if abs(c["cy"] - avg_y) <= row_eps_px:
            current_row.append(c)
        else:
            rows.append(sorted(current_row, key=lambda p: p["cx"]))
            current_row = [c]

    # Add final row
    rows.append(sorted(current_row, key=lambda p: p["cx"]))

    # Assign tree numbers in reading order (top→bottom, left→right)
    numbered = []
    num = 1
    for row in rows:
        for c in row:
            c["tree_number"] = num
            numbered.append(c)
            num += 1

    return numbered


def draw_overlay(img, centroids, pin_radius=60):
    out = img.copy()

    for c in centroids:
        x, y = int(c["cx"]), int(c["cy"])
        num = c["tree_number"]

        cv2.circle(out, (x, y), pin_radius + 4, (0, 0, 0), 8)
        cv2.circle(out, (x, y), pin_radius, (0, 255, 0), -1)

        cv2.putText(out, str(num),
                    (x - 20, y + 15),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.2,
                    (255, 255, 255),
                    3)

    return out
