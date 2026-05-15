"""
Postprocessing Utilities for Coconut Tree Segmentation
=======================================================
Smart filtering to select ONLY the main focused tree and connected parts.

Logic:
1. Score stem candidates based on: area, center proximity, verticality, bottom reach, connected leaves/buds
2. Pick the highest scoring stem (if above threshold)
3. Keep only leaves/buds that are connected to the main stem's crown zone
4. Handle special cases: stem-only close-up, leaf/bud close-up

Author: Coconut Segmentation Project
"""

import cv2
import numpy as np
from scipy import ndimage

# Avoid division by zero
EPS = 1e-8

# ============ TUNABLE PARAMETERS ============
PARAMS = {
    # Center crop for focus detection
    'CENTER_CROP_W': 0.30,          # center width fraction
    'CENTER_CROP_H': 0.40,          # center height fraction
    'P_CENTER_THRESH': 0.6,         # center dominance threshold
    
    # Stem filtering
    'MIN_AREA_FRAC': 0.002,         # min stem area (0.2% of image)
    'SCORE_THRESHOLD': 0.4,         # min score to accept main stem
    
    # Connection zone
    'DILATE_KERNEL_FRAC': (0.02, 0.02),  # dilation kernel (h, w) as fraction
    'CROWN_FRAC': 0.30,             # top fraction of stem for crown zone
    
    # Vertical alignment (for video stem tracking)
    'VERTICAL_CORRIDOR_W': 0.15,    # width of vertical corridor as fraction of image width
    
    # Scoring weights
    'w_area': 1.0,
    'w_center': 1.2,
    'w_vertical': 1.0,
    'w_bottom': 0.8,
    'w_connected': 1.5,
    'w_width': 0.2,
}


def connected_components_props(binary_mask):
    """
    Get connected components with properties.
    
    Returns list of dicts with:
    - 'mask': binary mask of component
    - 'area': pixel count
    - 'bbox': (xmin, ymin, xmax, ymax)
    - 'centroid': (cx, cy)
    - 'coords': array of (row, col) coordinates
    """
    # Label connected components
    labeled, num_features = ndimage.label(binary_mask)
    
    if num_features == 0:
        return []
    
    components = []
    for label_id in range(1, num_features + 1):
        mask = (labeled == label_id).astype(np.uint8)
        coords = np.array(np.where(mask > 0)).T  # (N, 2) as (row, col)
        
        if len(coords) == 0:
            continue
        
        area = len(coords)
        ymin, ymax = coords[:, 0].min(), coords[:, 0].max()
        xmin, xmax = coords[:, 1].min(), coords[:, 1].max()
        cx = (xmin + xmax) / 2
        cy = (ymin + ymax) / 2
        
        components.append({
            'mask': mask,
            'area': area,
            'bbox': (xmin, ymin, xmax, ymax),
            'centroid': (cx, cy),
            'coords': coords
        })
    
    return components


def compute_verticality_and_angle(coords):
    """
    Compute PCA-based verticality measure and main axis angle.
    
    Returns:
    - verticality: ratio of eigenvalues (higher = straighter/more linear)
    - angle_deg: angle of principal axis (90 = vertical)
    """
    if len(coords) < 3:
        return 0.0, 90.0
    
    # coords is (N, 2) as (row, col), convert to (x, y) = (col, row)
    pts = coords.astype(np.float32)
    X = np.stack([pts[:, 1], pts[:, 0]], axis=1)  # (x, y)
    
    # Center the points
    Xc = X - X.mean(axis=0)
    
    # Compute covariance matrix
    cov = np.cov(Xc, rowvar=False)
    
    try:
        eigenvalues, eigenvectors = np.linalg.eigh(cov)
    except Exception:
        return 0.0, 90.0
    
    # Sort by eigenvalue descending
    idx = np.argsort(eigenvalues)[::-1]
    eigenvalues = eigenvalues[idx]
    eigenvectors = eigenvectors[:, idx]
    
    # Verticality: ratio of first to second eigenvalue
    if eigenvalues[1] <= 0:
        verticality = eigenvalues[0] / EPS
    else:
        verticality = eigenvalues[0] / (eigenvalues[1] + EPS)
    
    # Angle of principal axis
    vx, vy = eigenvectors[:, 0]
    angle_rad = np.arctan2(vy, vx)
    angle_deg = abs(angle_rad * 180.0 / np.pi)
    
    # Convert to "how vertical" (90 is perfectly vertical)
    if angle_deg > 90:
        angle_deg = 180 - angle_deg
    
    return verticality, angle_deg


def dilate_mask(mask, img_shape, kernel_frac=(0.02, 0.02)):
    """Dilate mask with kernel sized as fraction of image dimensions."""
    h, w = img_shape[:2]
    kh = max(3, int(kernel_frac[0] * h))
    kw = max(3, int(kernel_frac[1] * w))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kw, kh))
    return cv2.dilate(mask.astype(np.uint8), kernel, iterations=1)


def create_vertical_corridor(stem_comp, img_shape, corridor_width_frac=0.15):
    """
    Create a vertical corridor mask based on stem's x-position.
    
    This ensures only parts aligned vertically with the main stem are kept.
    The corridor extends from top to bottom of the image, centered on the stem.
    
    Args:
        stem_comp: stem component dict with 'centroid' and 'bbox'
        img_shape: (H, W, C) or (H, W)
        corridor_width_frac: width of corridor as fraction of image width
    
    Returns:
        corridor_mask: HxW binary mask
    """
    h, w = img_shape[:2]
    
    # Get stem center x-position
    stem_cx = stem_comp['centroid'][0]
    xmin, ymin, xmax, ymax = stem_comp['bbox']
    stem_width = xmax - xmin
    
    # Corridor width: max of stem width or fraction of image
    corridor_half = max(stem_width, int(corridor_width_frac * w)) // 2
    
    # Expand a bit more at the top for the crown
    corridor_xmin = max(0, int(stem_cx - corridor_half * 1.5))
    corridor_xmax = min(w, int(stem_cx + corridor_half * 1.5))
    
    # Create corridor mask (full height)
    corridor = np.zeros((h, w), dtype=np.uint8)
    corridor[:, corridor_xmin:corridor_xmax] = 1
    
    return corridor


def overlap_fraction(mask_a, mask_b):
    """Fraction of mask_b that overlaps with mask_a."""
    inter = np.logical_and(mask_a > 0, mask_b > 0).sum()
    denom = mask_b.sum() + EPS
    return inter / denom


def compute_stem_scores(stem_comps, leaf_mask, bud_mask, img_shape, params=None):
    """
    Score each stem component based on multiple features.
    
    Features:
    - area: larger is better
    - center_dist: closer to center is better
    - verticality: straighter/more vertical is better
    - bottom_reach: reaching bottom of image is better
    - connected_frac: having more leaves/buds nearby is better
    - width: narrower (relative to height) is better
    
    Returns list of scored components, sorted by score descending.
    """
    if params is None:
        params = PARAMS
    
    if not stem_comps:
        return []
    
    h, w = img_shape[:2]
    img_area = h * w
    img_center = (w / 2.0, h / 2.0)
    bottom_margin = int(0.05 * h)
    
    # Combined leaf+bud mask for connection checking
    lb_mask = np.logical_or(leaf_mask > 0, bud_mask > 0).astype(np.uint8)
    
    # Collect raw features
    features = []
    for comp in stem_comps:
        area = comp['area']
        xmin, ymin, xmax, ymax = comp['bbox']
        width = xmax - xmin
        height = ymax - ymin
        cx, cy = comp['centroid']
        
        # Aspect ratio (height / width)
        aspect = height / (width + EPS)
        
        # Verticality from PCA
        verticality, angle_deg = compute_verticality_and_angle(comp['coords'])
        
        # Bottom reach: does stem extend to bottom of image?
        bottom_reach = 1.0 if (ymax >= (h - bottom_margin)) else 0.0
        
        # Connected fraction: how much leaf/bud is near this stem?
        stem_dil = dilate_mask(comp['mask'], img_shape, params['DILATE_KERNEL_FRAC'])
        connected_frac = overlap_fraction(stem_dil, lb_mask)
        
        # Distance from center
        center_dist = np.sqrt((cx - img_center[0])**2 + (cy - img_center[1])**2)
        max_dist = np.sqrt(img_center[0]**2 + img_center[1]**2)
        
        features.append({
            'comp': comp,
            'area': area / img_area,
            'center_dist': center_dist / (max_dist + EPS),
            'aspect': aspect,
            'verticality': verticality,
            'angle_deg': angle_deg,
            'bottom_reach': bottom_reach,
            'connected_frac': connected_frac,
            'width': width / (w + EPS)
        })
    
    # Normalize features to [0, 1]
    def normalize(values):
        arr = np.array(values, dtype=np.float32)
        mn, mx = arr.min(), arr.max()
        if mx - mn < EPS:
            return np.ones_like(arr) * 0.5
        return (arr - mn) / (mx - mn + EPS)
    
    n_area = normalize([f['area'] for f in features])
    n_center = normalize([f['center_dist'] for f in features])
    n_aspect = normalize([f['aspect'] for f in features])
    n_vertical = normalize([f['verticality'] for f in features])
    n_connected = normalize([f['connected_frac'] for f in features])
    n_width = normalize([f['width'] for f in features])
    
    # Compute scores
    scored = []
    for i, feat in enumerate(features):
        # Combine verticality and aspect for vertical score
        vert_score = (n_vertical[i] + n_aspect[i]) / 2.0
        
        score = (
            params['w_area'] * n_area[i]
            + params['w_center'] * (1.0 - n_center[i])  # closer to center = higher
            + params['w_vertical'] * vert_score
            + params['w_bottom'] * feat['bottom_reach']
            + params['w_connected'] * n_connected[i]
            - params['w_width'] * n_width[i]  # penalize very wide blobs
        )
        
        scored.append({
            'comp': feat['comp'],
            'score': float(score),
            'area': feat['area'],
            'center_dist': feat['center_dist'],
            'verticality': feat['verticality'],
            'angle_deg': feat['angle_deg'],
            'bottom_reach': feat['bottom_reach'],
            'connected_frac': feat['connected_frac']
        })
    
    # Sort by score descending
    scored.sort(key=lambda x: x['score'], reverse=True)
    return scored


def center_focus_rule(stem_mask, leaf_mask, bud_mask, img_shape, params=None):
    """
    Check what dominates the center of the image.
    
    Returns:
    - 'stem_center': stem dominates center
    - 'leafbud_center': leaf/bud dominate center
    - None: mixed or no clear dominance
    """
    if params is None:
        params = PARAMS
    
    h, w = img_shape[:2]
    cw = int(params['CENTER_CROP_W'] * w)
    ch = int(params['CENTER_CROP_H'] * h)
    x0 = max(0, (w - cw) // 2)
    y0 = max(0, (h - ch) // 2)
    x1 = x0 + cw
    y1 = y0 + ch
    
    # Count pixels in center region
    c_stem = (stem_mask[y0:y1, x0:x1] > 0).sum()
    c_leaf = (leaf_mask[y0:y1, x0:x1] > 0).sum()
    c_bud = (bud_mask[y0:y1, x0:x1] > 0).sum()
    
    non_bg = c_stem + c_leaf + c_bud
    if non_bg == 0:
        return None
    
    stem_ratio = c_stem / non_bg
    leafbud_ratio = (c_leaf + c_bud) / non_bg
    
    if stem_ratio >= params['P_CENTER_THRESH']:
        return 'stem_center'
    if leafbud_ratio >= params['P_CENTER_THRESH']:
        return 'leafbud_center'
    
    return None


def get_connected_parts(main_stem_comp, leaf_comps, bud_comps, img_shape, params=None, use_vertical_corridor=True):
    """
    Get leaves and buds connected to the main stem using hierarchical logic.
    
    Connection hierarchy: STEM → BUD → LEAF
    - Buds must be connected to stem (at crown/top of stem)
    - Leaves must be connected to buds (not directly to stem)
    - If no buds found → no leaves shown
    
    Also uses vertical corridor to filter out background trees.
    
    Returns dict with filtered masks for each class.
    """
    if params is None:
        params = PARAMS
    
    h, w = img_shape[:2]
    
    # Get stem mask and bbox
    stem_mask = main_stem_comp['mask']
    xmin, ymin, xmax, ymax = main_stem_comp['bbox']
    stem_cx = main_stem_comp['centroid'][0]
    
    # Create vertical corridor based on stem position
    if use_vertical_corridor:
        vertical_corridor = create_vertical_corridor(
            main_stem_comp, img_shape, 
            params.get('VERTICAL_CORRIDOR_W', 0.15)
        )
    else:
        vertical_corridor = np.ones((h, w), dtype=np.uint8)
    
    # Define crown zone: top portion of stem where buds attach
    stem_h = ymax - ymin
    crown_ymin = max(0, ymin - int(0.1 * stem_h))  # Extend above stem top
    crown_ymax = ymin + int(max(1, params['CROWN_FRAC'] * stem_h))
    
    # Crown width centered on stem
    stem_width = xmax - xmin
    crown_expand = max(int(0.5 * stem_width), int(0.05 * w))
    crown_xmin = max(0, int(stem_cx - crown_expand))
    crown_xmax = min(w, int(stem_cx + crown_expand))
    
    # Create crown zone mask (where buds should be)
    crown_zone = np.zeros((h, w), dtype=np.uint8)
    crown_zone[crown_ymin:crown_ymax, crown_xmin:crown_xmax] = 1
    
    # Dilate stem for direct connection
    stem_dil = dilate_mask(stem_mask, img_shape, params['DILATE_KERNEL_FRAC'])
    
    # ========== STEP 1: Find buds connected to stem (crown zone) ==========
    bud_connection_zone = np.logical_or(stem_dil > 0, crown_zone > 0).astype(np.uint8)
    
    kept_buds = np.zeros((h, w), dtype=np.uint8)
    kept_bud_comps = []
    
    for bud in bud_comps:
        # Bud must be in vertical corridor AND connected to stem/crown
        in_corridor = overlap_fraction(vertical_corridor, bud['mask']) > 0.3
        is_connected = overlap_fraction(bud_connection_zone, bud['mask']) > 0.001
        
        if in_corridor and is_connected:
            kept_buds = np.logical_or(kept_buds, bud['mask']).astype(np.uint8)
            kept_bud_comps.append(bud)
    
    # ========== STEP 2: Find leaves connected to buds ==========
    kept_leaves = np.zeros((h, w), dtype=np.uint8)
    
    # Only look for leaves if buds were found
    if kept_buds.sum() > 0:
        # Create leaf connection zone: dilated buds + area around buds
        bud_dil = dilate_mask(kept_buds, img_shape, (0.03, 0.03))
        
        # Also allow leaves in the crown zone (above/around stem top)
        leaf_connection_zone = np.logical_or(bud_dil > 0, crown_zone > 0).astype(np.uint8)
        
        for leaf in leaf_comps:
            # Leaf must be in vertical corridor AND connected to buds
            in_corridor = overlap_fraction(vertical_corridor, leaf['mask']) > 0.3
            is_connected_to_bud = overlap_fraction(leaf_connection_zone, leaf['mask']) > 0.001
            
            if in_corridor and is_connected_to_bud:
                kept_leaves = np.logical_or(kept_leaves, leaf['mask']).astype(np.uint8)
    
    # If no buds found, check if leaves are directly at stem top (crown close-up)
    # This handles cases where bud is small/not visible but leaves are attached
    elif len(leaf_comps) > 0:
        # Only keep leaves that are directly at the stem top (strict)
        stem_top_zone = np.zeros((h, w), dtype=np.uint8)
        top_margin = int(0.05 * h)
        stem_top_zone[max(0,ymin-top_margin):ymin+int(0.1*stem_h), crown_xmin:crown_xmax] = 1
        stem_top_zone = np.logical_or(stem_top_zone > 0, stem_dil > 0).astype(np.uint8)
        
        for leaf in leaf_comps:
            in_corridor = overlap_fraction(vertical_corridor, leaf['mask']) > 0.3
            at_stem_top = overlap_fraction(stem_top_zone, leaf['mask']) > 0.1  # Strict: 10% overlap
            
            if in_corridor and at_stem_top:
                kept_leaves = np.logical_or(kept_leaves, leaf['mask']).astype(np.uint8)
    
    return {
        'stem': stem_mask,
        'leaf': kept_leaves,
        'bud': kept_buds,
        'crown_zone': crown_zone,
        'vertical_corridor': vertical_corridor,
        'connection_zone': bud_connection_zone,
        'num_buds_kept': len(kept_bud_comps)
    }


def smart_postprocess(pred_mask, img_shape, params=None, debug=False):
    """
    Main postprocessing function.
    
    Takes raw prediction mask (0=bg, 1=bud, 2=leaf, 3=stem) and returns
    filtered mask with only the main tree.
    
    Args:
        pred_mask: HxW array with class ids 0-3
        img_shape: (H, W, C) or (H, W)
        params: dict of parameters (uses PARAMS if None)
        debug: if True, return debug info
    
    Returns:
        filtered_mask: HxW array with filtered class ids
        debug_info: dict with intermediate results (if debug=True)
    """
    if params is None:
        params = PARAMS
    
    h, w = img_shape[:2]
    
    # Extract class masks
    stem_mask = (pred_mask == 3).astype(np.uint8)
    leaf_mask = (pred_mask == 2).astype(np.uint8)
    bud_mask = (pred_mask == 1).astype(np.uint8)
    
    debug_info = {}
    
    # Get connected components
    stem_comps = connected_components_props(stem_mask)
    leaf_comps = connected_components_props(leaf_mask)
    bud_comps = connected_components_props(bud_mask)
    
    debug_info['num_stem_candidates'] = len(stem_comps)
    debug_info['num_leaf_candidates'] = len(leaf_comps)
    debug_info['num_bud_candidates'] = len(bud_comps)
    
    # Check center focus rule
    center_case = center_focus_rule(stem_mask, leaf_mask, bud_mask, img_shape, params)
    debug_info['center_case'] = center_case
    
    # Initialize output
    filtered_stem = np.zeros((h, w), dtype=np.uint8)
    filtered_leaf = np.zeros((h, w), dtype=np.uint8)
    filtered_bud = np.zeros((h, w), dtype=np.uint8)
    
    if center_case == 'stem_center':
        # CASE 1: Stem dominates center - just pick the best centered stem
        debug_info['focus_type'] = 'stem_only'
        
        if stem_comps:
            # Pick stem closest to center with good size
            img_center = (w / 2, h / 2)
            cw = int(params['CENTER_CROP_W'] * w)
            ch = int(params['CENTER_CROP_H'] * h)
            x0, y0 = (w - cw) // 2, (h - ch) // 2
            x1, y1 = x0 + cw, y0 + ch
            
            # Find stems with centroid in center region
            center_stems = [s for s in stem_comps 
                          if x0 <= s['centroid'][0] <= x1 and y0 <= s['centroid'][1] <= y1]
            
            if center_stems:
                main = max(center_stems, key=lambda x: x['area'])
            else:
                main = max(stem_comps, key=lambda x: x['area'])
            
            filtered_stem = main['mask']
            debug_info['main_stem_area'] = main['area']

    elif center_case == 'leafbud_center':
        # CASE 2: Leaf/bud dominate center - close-up of crown
        # Use simpler, more permissive logic since it's a close-up
        debug_info['focus_type'] = 'leaf_bud'
        
        all_parts = leaf_comps + bud_comps
        if all_parts:
            img_center = (w / 2, h / 2)
            # Pick part closest to center
            main = min(all_parts, key=lambda x: 
                      (x['centroid'][0] - img_center[0])**2 + (x['centroid'][1] - img_center[1])**2)
            
            # Use larger dilation for close-ups (5% of image instead of 3%)
            main_dil = dilate_mask(main['mask'], img_shape, (0.05, 0.05))
            
            # Keep all leaves/buds that overlap with dilated center part
            for leaf in leaf_comps:
                if overlap_fraction(main_dil, leaf['mask']) > 0.001:
                    filtered_leaf = np.logical_or(filtered_leaf, leaf['mask']).astype(np.uint8)
            
            for bud in bud_comps:
                if overlap_fraction(main_dil, bud['mask']) > 0.001:
                    filtered_bud = np.logical_or(filtered_bud, bud['mask']).astype(np.uint8)
            
            # Also check for connected stem
            for stem in stem_comps:
                if overlap_fraction(main_dil, stem['mask']) > 0.001:
                    filtered_stem = np.logical_or(filtered_stem, stem['mask']).astype(np.uint8)
            
            # If we kept buds but no leaves, also check leaves connected to buds
            if filtered_bud.sum() > 0 and filtered_leaf.sum() == 0:
                bud_dil = dilate_mask(filtered_bud, img_shape, (0.05, 0.05))
                for leaf in leaf_comps:
                    if overlap_fraction(bud_dil, leaf['mask']) > 0.001:
                        filtered_leaf = np.logical_or(filtered_leaf, leaf['mask']).astype(np.uint8)

    else:
        # CASE 3: General case - score stems and pick best
        debug_info['focus_type'] = 'full_tree'
        
        if stem_comps:
            # Score all stem candidates
            scored = compute_stem_scores(stem_comps, leaf_mask, bud_mask, img_shape, params)
            
            debug_info['stem_scores'] = [(s['score'], s['area'], s['connected_frac']) for s in scored[:5]]
            
            # Pick best stem if score is good enough
            if scored and scored[0]['score'] >= params['SCORE_THRESHOLD']:
                main = scored[0]['comp']
            else:
                # Fallback: pick largest stem closest to center
                img_center = (w / 2, h / 2)
                main = max(stem_comps, key=lambda x: 
                          x['area'] / (1.0 + np.hypot(x['centroid'][0] - img_center[0], 
                                                      x['centroid'][1] - img_center[1])))
            
            # Get connected parts
            connected = get_connected_parts(main, leaf_comps, bud_comps, img_shape, params)
            
            filtered_stem = connected['stem']
            filtered_leaf = connected['leaf']
            filtered_bud = connected['bud']
            
            debug_info['main_stem_area'] = main['area']
            debug_info['kept_leaf_area'] = filtered_leaf.sum()
            debug_info['kept_bud_area'] = filtered_bud.sum()
        
        elif leaf_comps or bud_comps:
            # No stem found - keep largest leaf/bud group
            all_parts = leaf_comps + bud_comps
            if all_parts:
                main = max(all_parts, key=lambda x: x['area'])
                main_dil = dilate_mask(main['mask'], img_shape, (0.03, 0.03))
                
                for leaf in leaf_comps:
                    if overlap_fraction(main_dil, leaf['mask']) > 0.001:
                        filtered_leaf = np.logical_or(filtered_leaf, leaf['mask']).astype(np.uint8)
                
                for bud in bud_comps:
                    if overlap_fraction(main_dil, bud['mask']) > 0.001:
                        filtered_bud = np.logical_or(filtered_bud, bud['mask']).astype(np.uint8)
    
    # Reconstruct filtered mask
    filtered_mask = np.zeros((h, w), dtype=np.uint8)
    filtered_mask[filtered_stem > 0] = 3
    filtered_mask[filtered_leaf > 0] = 2
    filtered_mask[filtered_bud > 0] = 1
    
    if debug:
        return filtered_mask, debug_info
    return filtered_mask


# ============ VIDEO TRACKING ============

class StemTracker:
    """
    Simple tracker for main stem across video frames.
    Uses IoU-based linking and exponential smoothing.
    """
    
    def __init__(self, alpha=0.4, iou_thresh=0.3, min_consistent=3, max_missing=5):
        self.alpha = alpha  # smoothing factor
        self.iou_thresh = iou_thresh
        self.min_consistent = min_consistent
        self.max_missing = max_missing
        self.track = None
    
    def _iou_bbox(self, b1, b2):
        """Compute IoU between two bboxes (xmin, ymin, xmax, ymax)."""
        x1, y1, x2, y2 = b1
        X1, Y1, X2, Y2 = b2
        
        xa = max(x1, X1)
        ya = max(y1, Y1)
        xb = min(x2, X2)
        yb = min(y2, Y2)
        
        inter = max(0, xb - xa) * max(0, yb - ya)
        area1 = (x2 - x1) * (y2 - y1)
        area2 = (X2 - X1) * (Y2 - Y1)
        union = area1 + area2 - inter + EPS
        
        return inter / union
    
    def init_track(self, bbox, score):
        """Initialize new track."""
        self.track = {
            'bbox': bbox,
            'score': score,
            'hits': 1,
            'misses': 0
        }
    
    def update(self, candidate_bbox, candidate_score):
        """
        Update tracker with new candidate.
        
        Returns:
            smoothed_bbox: smoothed bbox
            accepted: whether candidate was accepted
        """
        if self.track is None:
            if candidate_bbox is not None:
                self.init_track(candidate_bbox, candidate_score)
                return self.track['bbox'], True
            return None, False
        
        if candidate_bbox is None:
            # No candidate - count miss
            self.track['misses'] += 1
            if self.track['misses'] > self.max_missing:
                self.track = None
                return None, False
            return self.track['bbox'], False
        
        iou = self._iou_bbox(self.track['bbox'], candidate_bbox)
        
        if iou > self.iou_thresh:
            # Same track - smooth bbox
            x1, y1, x2, y2 = self.track['bbox']
            X1, Y1, X2, Y2 = candidate_bbox
            
            new_bbox = (
                int(self.alpha * X1 + (1 - self.alpha) * x1),
                int(self.alpha * Y1 + (1 - self.alpha) * y1),
                int(self.alpha * X2 + (1 - self.alpha) * x2),
                int(self.alpha * Y2 + (1 - self.alpha) * y2)
            )
            
            self.track['bbox'] = new_bbox
            self.track['score'] = candidate_score
            self.track['hits'] += 1
            self.track['misses'] = 0
            
            return new_bbox, True
        else:
            # Different track - count miss
            self.track['misses'] += 1
            
            if self.track['misses'] > self.max_missing:
                # Switch to new track
                self.init_track(candidate_bbox, candidate_score)
                return self.track['bbox'], True
            
            # Keep old track for temporal smoothing
            return self.track['bbox'], False
    
    def reset(self):
        """Reset tracker state."""
        self.track = None
