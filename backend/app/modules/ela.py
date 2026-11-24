"""
Error Level Analysis (E2.1).

Re-saves the JPEG at a known quality and measures how much each pixel changes.
An edited area has usually been compressed a different number of times than
the rest of the photo, so its error level stands out in the heatmap.

Score: the error level of the brightest area (about 80x80 pixels) compared
with a typical area, scaled to 0-1 (0 = even error level, 1 = strongly uneven).
Strong edges and fine texture also raise the error level, so a genuine photo
with a lot of detail can score high; the fusion model weighs this against the
other checks.
"""

import io
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

RESAVE_QUALITY = 90
BLOCK = 16                  # block size in pixels, a multiple of the 8x8 JPEG grid
AREA = 5                    # areas of 5x5 blocks are compared, so single noisy pixels don't count
RATIO_FOR_MAX_SCORE = 2.0   # brightest area at 2x the typical area -> score 1.0
FLAG_THRESHOLD = 0.5        # add a reason for the reviewer at or above this score

ROOT_DIR = Path(__file__).resolve().parents[3]
IMAGE_DATA_PATH =  ROOT_DIR / "data" / "images"
IMAGE_DIR = "careful_manual_edits"
TEST_FILE_NAME = "ME_P_011.jpg"
TEST_IMAGE = IMAGE_DATA_PATH / IMAGE_DIR / TEST_FILE_NAME
TEST_OUT_DIR = IMAGE_DATA_PATH / "out_dir"


def error_levels(image):
    """Per-pixel difference between the image and a re-saved copy."""
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=RESAVE_QUALITY) # subsampling=0, optimize=False, progressive=False
    resaved = Image.open(buffer).convert("RGB")
    diff = np.abs(np.asarray(image, np.int16) - np.asarray(resaved, np.int16))
    return diff.max(axis=2).astype(np.float32)


def area_means(errors):
    """Mean error of each 16x16 block, then averaged over neighbouring blocks."""
    h = errors.shape[0] // BLOCK * BLOCK
    w = errors.shape[1] // BLOCK * BLOCK
    blocks = errors[:h, :w].reshape(h // BLOCK, BLOCK, w // BLOCK, BLOCK).mean(axis=(1, 3))
    return cv2.blur(blocks, (AREA, AREA), borderType=cv2.BORDER_REFLECT)


def ela_score(areas):
    typical = np.median(areas)
    brightest = areas.max() # np.percentile(areas, 99)
    ratio = (brightest + 1) / (typical + 1)   # +1 avoids dividing by ~0 in flat photos
    # return float(np.clip((ratio - 1) / (RATIO_FOR_MAX_SCORE - 1), 0, 1))
    return float(1 - np.exp(-(ratio - 1) / (RATIO_FOR_MAX_SCORE - 1)))


def hotspot_location(areas):
    """Where the brightest area is, in words: 'upper left', 'centre', ..."""
    row, col = np.unravel_index(np.argmax(areas), areas.shape)
    vertical = ["upper", "middle", "lower"][row * 3 // areas.shape[0]]
    horizontal = ["left", "centre", "right"][col * 3 // areas.shape[1]]
    if vertical == "middle" and horizontal == "centre":
        return "centre"
    return f"{vertical} {horizontal}"


def save_heatmap(errors, path):
    errors = cv2.GaussianBlur(errors, (0, 0), 2)   # smoother map, easier for a reviewer to read
    # stretch so the brightest 0.5% of pixels are full red, whatever the photo's overall level
    scale = 255 / max(np.percentile(errors, 99.5), 1)
    gray = np.clip(errors * scale, 0, 255).astype(np.uint8)
    color = cv2.applyColorMap(gray, cv2.COLORMAP_JET)
    Image.fromarray(color[..., ::-1]).save(path)   # OpenCV colours are BGR


def analyze_ela(image_path, out_dir):
    image_path, out_dir = Path(image_path), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    with Image.open(image_path) as img:
        image = img.convert("RGB")
    if min(image.size) < 3 * BLOCK * AREA:
        raise ValueError(f"image too small for ELA: {image.size}")

    errors = error_levels(image)
    areas = area_means(errors)
    score = ela_score(areas)

    heatmap_path = out_dir / f"{image_path.stem}_ela.png"
    save_heatmap(errors, heatmap_path)

    flags = []
    if score >= FLAG_THRESHOLD:
        flags.append(f"Unusual error level in the {hotspot_location(areas)} of the photo")

    return {
        "module": "ela",
        "score": round(score, 3),
        "flags": flags,
        "artifacts": {"heatmap_path": heatmap_path.as_posix()},
    }


if __name__ == "__main__":
    print(analyze_ela(TEST_IMAGE, TEST_OUT_DIR))