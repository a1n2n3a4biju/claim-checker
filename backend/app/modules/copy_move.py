"""
Copy-move detection with keypoint matching (E2.3).

A common trick is copying a dent or scratch and pasting it elsewhere in the
same photo to make damage look bigger. The check finds distinctive points
(corners, edges, specks) and looks for two separate areas with the same
pattern of points. Real photos almost never contain two identical patches.

Steps:
  1. Enlarge small photos (a copied dent may be only ~50 px wide) and boost
     local contrast (CLAHE) so faint damage on smooth paint gets keypoints.
  2. Find SIFT keypoints (or ORB, see DETECTOR) and match each one with the
     others in the same photo, keeping only clear, far-apart matches.
  3. RANSAC keeps matches that agree on one move (shift + small rotation/scale)
     from one area to another. This repeats to find up to MAX_GROUPS copies.
  4. Mark the whole copied area, not just the matched points: move the photo
     by the found shift/rotation and keep the pixels around the matches where
     the moved photo looks the same as the photo (local correlation).
  5. Tell original from copy: a pasted copy has usually been resized or
     rotated, which smooths away some of the camera's fine grain, so the
     grainier side is labelled "Original". A copy moved without resizing or
     rotating is pixel-for-pixel the same as its source, so then nobody can
     tell which is which: both labels get a "?".

Score: matches in the largest group, scaled to 0-1
(0 = fewer than MIN_INLIERS, 1 = INLIERS_FOR_MAX_SCORE or more).
"""

from pathlib import Path

import cv2
import numpy as np
from PIL import Image

DETECTOR = "sift"           # "sift" (finds far more copies) or "orb"
MIN_SIDE = 1600             # smaller photos are enlarged to this size first
MAX_SIDE = 2000             # larger photos are shrunk to this size first
RATIO = 0.7                 # best match must be clearly better than the next (0.8 for ORB)
MIN_DISTANCE = 0.03         # matched points at least 3% of the shorter side apart
RANSAC_PIXELS = 4.0         # how far a match may be from its group's move
MIN_INLIERS = 5             # smaller groups are ignored
INLIERS_FOR_MAX_SCORE = 15  # this many matches in one group -> score 1
MAX_GROUPS = 3              # copied areas looked for per photo
GRAIN_MARGIN = 1.10         # one side must have 10% more grain to call it the original
NCC_WINDOW = 11             # window (pixels, at analysis size) for comparing the two areas
NCC_THRESHOLD = 0.75        # how alike the moved photo and the photo must be to count as copied
MIN_TEXTURE = 3.0           # flat paint is skipped: it looks alike everywhere
SEARCH_RADIUS = 0.08        # copied area is searched up to 8% of the shorter side around the matches
FLAG_THRESHOLD = 0.5        # add a reason for the reviewer at or above this score

ORIGINAL_COLOR = (0, 200, 0)    # green (RGB)
COPY_COLOR = (230, 30, 30)      # red
LINE_COLOR = (255, 220, 0)      # yellow
MAX_LINES = 12                  # match lines drawn per copy

ROOT_DIR = Path(__file__).resolve().parents[3]
IMAGE_DATA_PATH =  ROOT_DIR / "data" / "images"
IMAGE_DIR = "careful_manual_edits"
TEST_FILE_NAME = "ME_P_011.jpg"
TEST_IMAGE = IMAGE_DATA_PATH / IMAGE_DIR / TEST_FILE_NAME
TEST_OUT_DIR = IMAGE_DATA_PATH / "out_dir"


def find_keypoints(gray):
    gray = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    if DETECTOR == "sift":
        keypoints, descriptors = cv2.SIFT_create(contrastThreshold=0.01).detectAndCompute(gray, None)
        matcher = cv2.FlannBasedMatcher(dict(algorithm=1, trees=5), dict(checks=64))
        ratio = RATIO
    else:
        orb = cv2.ORB_create(nfeatures=30000, fastThreshold=5, edgeThreshold=15)
        keypoints, descriptors = orb.detectAndCompute(gray, None)
        matcher = cv2.BFMatcher(cv2.NORM_HAMMING)
        ratio = 0.8
    return keypoints, descriptors, matcher, ratio


def candidate_pairs(gray):
    """Pairs of keypoints that look alike but are in different places."""
    cv2.setRNGSeed(0)   # FLANN and RANSAC are random; this gives the same result every run
    keypoints, descriptors, matcher, ratio = find_keypoints(gray)
    if descriptors is None or len(keypoints) < 3:
        return np.empty((0, 2, 2), np.float32)

    points = np.float32([kp.pt for kp in keypoints])
    min_distance = MIN_DISTANCE * min(gray.shape)
    pairs, seen = [], set()
    # k=3 because one of the three matches is the keypoint itself
    for matches in matcher.knnMatch(descriptors, descriptors, k=3):
        others = [m for m in matches if m.trainIdx != m.queryIdx]
        if len(others) < 2:
            continue
        best, second = others[0], others[1]
        if best.distance > ratio * second.distance:
            continue
        a, b = points[best.queryIdx], points[best.trainIdx]
        if np.linalg.norm(a - b) < min_distance:
            continue
        key = tuple(sorted((best.queryIdx, best.trainIdx)))
        if key in seen:
            continue
        seen.add(key)
        # left point first, so every pair from the same copy points the same way
        pairs.append((a, b) if (a[0], a[1]) <= (b[0], b[1]) else (b, a))
    return np.float32(pairs).reshape(-1, 2, 2)


def copy_groups(pairs):
    """Groups of pairs that share one move, largest first (repeated RANSAC)."""
    groups = []
    while len(pairs) >= MIN_INLIERS and len(groups) < MAX_GROUPS:
        _, inliers = cv2.estimateAffinePartial2D(
            np.ascontiguousarray(pairs[:, 0]), np.ascontiguousarray(pairs[:, 1]),
            method=cv2.RANSAC, ransacReprojThreshold=RANSAC_PIXELS)
        if inliers is None or inliers.sum() < MIN_INLIERS:
            break
        inliers = inliers.ravel() == 1
        groups.append(pairs[inliers])
        pairs = pairs[~inliers]
    return groups


def grain(gray, points, radius=12):
    """Mean camera grain (noise residual) in small windows around the points."""
    residual = np.abs(gray.astype(np.float32) - cv2.medianBlur(gray, 3).astype(np.float32))
    h, w = gray.shape
    values = []
    for x, y in points.astype(int):
        window = residual[max(0, y - radius):min(h, y + radius), max(0, x - radius):min(w, x + radius)]
        values.append(window.mean())
    return float(np.mean(values))


def a_is_original(gray, group):
    """Which side of a group is the original, and are we sure? (grainier side = original)"""
    grain_a, grain_b = grain(gray, group[:, 0]), grain(gray, group[:, 1])
    sure = max(grain_a, grain_b) >= GRAIN_MARGIN * min(grain_a, grain_b)
    return grain_a >= grain_b, sure


def location(point, width, height):
    vertical = ["upper", "middle", "lower"][min(2, int(point[1] * 3 // height))]
    horizontal = ["left", "centre", "right"][min(2, int(point[0] * 3 // width))]
    if vertical == "middle" and horizontal == "centre":
        return "centre"
    return f"{vertical} {horizontal}"


def local_correlation(a, b):
    """Correlation of a and b in small windows (1 = same pattern), and where both have texture."""
    a, b = a.astype(np.float32), b.astype(np.float32)
    k = (NCC_WINDOW, NCC_WINDOW)
    mean_a, mean_b = cv2.blur(a, k), cv2.blur(b, k)
    var_a = cv2.blur(a * a, k) - mean_a ** 2
    var_b = cv2.blur(b * b, k) - mean_b ** 2
    cov = cv2.blur(a * b, k) - mean_a * mean_b
    textured = (var_a > MIN_TEXTURE ** 2) & (var_b > MIN_TEXTURE ** 2)
    return cov / np.sqrt(np.maximum(var_a * var_b, 1e-6)), textured


def points_mask(points, shape, radius):
    mask = np.zeros(shape, np.uint8)
    cv2.fillPoly(mask, [cv2.convexHull(points.astype(np.int32))], 255)
    size = 2 * int(radius) + 1
    return cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size)))


def copied_areas(gray, group):
    """Masks of the two matching areas (side A, side B) at analysis size."""
    a, b = np.ascontiguousarray(group[:, 0]), np.ascontiguousarray(group[:, 1])
    h, w = gray.shape
    move, _ = cv2.estimateAffinePartial2D(a, b)          # where each A pixel went in B
    if move is None:
        return points_mask(a, gray.shape, 10), points_mask(b, gray.shape, 10)

    moved = cv2.warpAffine(gray, move, (w, h))           # A content placed on top of B
    inside = cv2.warpAffine(np.full_like(gray, 255), move, (w, h), flags=cv2.INTER_NEAREST) > 0
    corr, textured = local_correlation(gray, moved)
    near = points_mask(b, gray.shape, SEARCH_RADIUS * min(h, w)) > 0
    alike = ((corr > NCC_THRESHOLD) & textured & inside & near).astype(np.uint8) * 255
    alike = cv2.morphologyEx(alike, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))

    # keep only the alike regions that contain matched points
    n, labels = cv2.connectedComponents(alike)
    hit = {labels[min(h - 1, int(y)), min(w - 1, int(x))] for x, y in b} - {0}
    area_b = np.isin(labels, list(hit)).astype(np.uint8) * 255
    area_b |= points_mask(b, gray.shape, 4)               # always cover the matched points
    area_a = cv2.warpAffine(area_b, cv2.invertAffineTransform(move), (w, h), flags=cv2.INTER_NEAREST)
    return area_a, area_b


def draw_label(image, text, contours, color, scale):
    x, y, w, h = cv2.boundingRect(np.vstack(contours))
    thickness = max(1, round(2 * scale))
    (tw, th), base = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, thickness)
    top = y - th - base - 8 if y - th - base - 8 >= 0 else y + h + 4   # below the box if no room above
    cv2.rectangle(image, (x, top), (x + tw + 8, top + th + base + 6), color, -1)
    cv2.putText(image, text, (x + 4, top + th + 3), cv2.FONT_HERSHEY_SIMPLEX, scale,
                (255, 255, 255), thickness, cv2.LINE_AA)


def draw_result(image, labelled, path):
    out = image.copy()
    size = max(image.shape[:2])
    scale = max(0.5, size / 1500)
    thickness = max(2, round(3 * scale))
    for original, copy, original_mask, copy_mask, sure in labelled:
        step = max(1, len(original) // MAX_LINES)                 # a few lines are enough to show the link
        for a, b in zip(original[::step].astype(int), copy[::step].astype(int)):
            cv2.line(out, tuple(a), tuple(b), LINE_COLOR, 1, cv2.LINE_AA)
        mark = "" if sure else "?"
        for mask, color, text in ((original_mask, ORIGINAL_COLOR, "Original" + mark),
                                  (copy_mask, COPY_COLOR, "Copy-move" + mark)):
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                cv2.drawContours(out, contours, -1, color, thickness)
                draw_label(out, text, contours, color, scale)
    Image.fromarray(out).save(path)


def analyze_copy_move(image_path, out_dir):
    image_path, out_dir = Path(image_path), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    with Image.open(image_path) as img:
        image = np.asarray(img.convert("RGB"))
    height, width = image.shape[:2]
    full_gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

    longest = max(height, width)
    scale = min(MAX_SIDE, max(MIN_SIDE, longest)) / longest
    gray = cv2.resize(full_gray, (round(width * scale), round(height * scale)),
                      interpolation=cv2.INTER_CUBIC if scale > 1 else cv2.INTER_AREA)

    groups = copy_groups(candidate_pairs(gray))
    labelled = []
    for group in groups:
        area_a, area_b = copied_areas(gray, group)
        area_a = cv2.resize(area_a, (width, height), interpolation=cv2.INTER_NEAREST)
        area_b = cv2.resize(area_b, (width, height), interpolation=cv2.INTER_NEAREST)
        points = group / scale                                    # back to full-size coordinates
        a_first, sure = a_is_original(full_gray, points)
        if a_first:
            labelled.append((points[:, 0], points[:, 1], area_a, area_b, sure))
        else:
            labelled.append((points[:, 1], points[:, 0], area_b, area_a, sure))

    n = len(groups[0]) if groups else 0
    # score = 0.0 if n < MIN_INLIERS else float(
    #     np.clip((n - MIN_INLIERS + 1) / (INLIERS_FOR_MAX_SCORE - MIN_INLIERS + 1), 0, 1))

    score = 0.0 if n < MIN_INLIERS else float(1 - np.exp(-(n - MIN_INLIERS + 1) / 5))

    out_path = out_dir / f"{image_path.stem}_copy_move.png"
    draw_result(image, labelled, out_path)

    flags = []
    if score >= FLAG_THRESHOLD:
        original, copy, _, _, sure = labelled[0]
        src = location(original.mean(axis=0), width, height)
        dst = location(copy.mean(axis=0), width, height)
        where = f"both near the {src}" if src == dst else f"{src} and {dst}"
        if sure and src != dst:
            flags.append(f"Area in the {dst} of the photo looks copied from the {src}")
        else:
            flags.append(f"Two areas of the photo look copied from each other ({where})")

    return {
        "module": "copy_move",
        "score": round(score, 3),
        "flags": flags,
        "artifacts": {"heatmap_path": out_path.as_posix()},
    }


if __name__ == "__main__":
    print(analyze_copy_move(TEST_IMAGE, TEST_OUT_DIR))