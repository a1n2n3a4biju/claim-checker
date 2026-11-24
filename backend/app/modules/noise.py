"""
Noise residual analysis (E2.2).

Every camera adds a fine, even grain to a photo. A region pasted from another
photo, or filled in by AI, usually has a different amount of grain, like a
patch of different fabric sewn onto a shirt.

Steps:
  1. Separate the grain from the picture with a small median filter.
  2. Measure grain only in smooth 16x16 blocks (paint, sky). In textured
     blocks (gravel, leaves, edges) the picture's own detail looks like grain,
     so those are skipped.
  3. Grain is naturally stronger in dark areas than in bright ones, so learn
     this photo's own grain-vs-brightness curve and compare each block with
     the curve at its own brightness.
  4. Areas whose grain is clearly higher or lower than expected stand out.

Score: how far the most unusual area is from the expected grain, on a smooth
0-1 curve (an area with 3x more or 3x less grain than expected scores about 0.63).
"""

from pathlib import Path

import cv2
import numpy as np
from PIL import Image

BLOCK = 16                  # block size in pixels
AREA = 5                    # areas of 5x5 blocks are compared, so single blocks don't count
SMOOTH_SHARE = 0.5          # at most the smoothest half of the blocks is used...
MAX_TEXTURE = 20.0          # ...and never blocks with more picture detail than this (gravel, leaves)
BRIGHTNESS_BINS = 6         # pieces of the grain-vs-brightness curve
MIN_BLOCKS = 20             # fewer measurable blocks than this -> can't judge
RATIO_SCALE = 3.0           # 3x more (or less) grain than expected -> score 0.63
                            # (genuine photos often vary up to ~1.5x, e.g. glossy dark paint)
FLAG_THRESHOLD = 0.4        # add a reason for the reviewer at or above this score

ROOT_DIR = Path(__file__).resolve().parents[3]
IMAGE_DATA_PATH =  ROOT_DIR / "data" / "images"
IMAGE_DIR = "Scripted_edits"
TEST_FILE_NAME = "CM_P_012.jpg"
TEST_IMAGE = IMAGE_DATA_PATH / IMAGE_DIR / TEST_FILE_NAME
TEST_OUT_DIR = IMAGE_DATA_PATH / "out_dir"


def to_blocks(array):
    h = array.shape[0] // BLOCK * BLOCK
    w = array.shape[1] // BLOCK * BLOCK
    blocks = array[:h, :w].reshape(h // BLOCK, BLOCK, w // BLOCK, BLOCK)
    return blocks.transpose(0, 2, 1, 3).reshape(h // BLOCK, w // BLOCK, BLOCK * BLOCK)


def block_measurements(gray):
    """Grain, brightness and picture texture of every block."""
    image = gray.astype(np.float32)
    grain = np.abs(image - cv2.medianBlur(gray, 3).astype(np.float32))
    # picture detail: edges of a lightly blurred copy (the blur hides grain, not gravel or leaves)
    blurred = cv2.GaussianBlur(image, (0, 0), 1.0)
    edges = cv2.magnitude(cv2.Sobel(blurred, cv2.CV_32F, 1, 0), cv2.Sobel(blurred, cv2.CV_32F, 0, 1))
    return (to_blocks(grain).mean(axis=2),
            to_blocks(image).mean(axis=2),
            to_blocks(edges).mean(axis=2))


def usable_blocks(brightness, texture):
    not_clipped = (brightness > 20) & (brightness < 230)   # near black/white, grain gets clipped away
    smoothest = not_clipped & (texture <= np.percentile(texture, SMOOTH_SHARE * 100))
    usable = smoothest & (texture <= MAX_TEXTURE)
    # a photo that is detailed everywhere: fall back to its smoothest half
    return usable if usable.sum() >= MIN_BLOCKS else smoothest


def expected_grain(grain, brightness, usable):
    """This photo's typical grain at each brightness (median per brightness range)."""
    edges = np.percentile(brightness[usable], np.linspace(0, 100, BRIGHTNESS_BINS + 1))
    centres, levels = [], []
    for low, high in zip(edges[:-1], edges[1:]):
        in_bin = usable & (brightness >= low) & (brightness <= high)
        if in_bin.sum() >= 3:
            centres.append(brightness[in_bin].mean())
            levels.append(np.median(grain[in_bin]))
    return np.interp(brightness, centres, levels)


def area_average(values, valid):
    """Average each block with its neighbours, ignoring unusable blocks."""
    total = cv2.blur(np.where(valid, values, 0).astype(np.float32), (AREA, AREA))
    count = cv2.blur(valid.astype(np.float32), (AREA, AREA))
    out = np.full(values.shape, np.nan, np.float32)
    enough = count >= 0.5          # at least half the area must be measurable
    out[enough] = total[enough] / count[enough]
    return out


def hotspot_location(deviation):
    row, col = np.unravel_index(np.nanargmax(deviation), deviation.shape)
    vertical = ["upper", "middle", "lower"][row * 3 // deviation.shape[0]]
    horizontal = ["left", "centre", "right"][col * 3 // deviation.shape[1]]
    if vertical == "middle" and horizontal == "centre":
        return "centre"
    return f"{vertical} {horizontal}"


def save_map(deviation, size, path):
    """Blue = grain matches, red = doesn't match, grey = not measured (detailed areas)."""
    scaled = 1 - np.exp(-np.nan_to_num(deviation, nan=0.0) / np.log(RATIO_SCALE))
    gray = cv2.resize((scaled * 255).astype(np.uint8), size, interpolation=cv2.INTER_LINEAR)
    color = cv2.applyColorMap(gray, cv2.COLORMAP_JET)[..., ::-1].copy()   # OpenCV colours are BGR
    unmeasured = cv2.resize(np.isnan(deviation).astype(np.uint8), size, interpolation=cv2.INTER_NEAREST)
    color[unmeasured > 0] = (90, 90, 90)
    Image.fromarray(color).save(path)


def analyze_noise(image_path, out_dir):
    image_path, out_dir = Path(image_path), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    with Image.open(image_path) as img:
        gray = np.asarray(img.convert("L"))
    if min(gray.shape) < 3 * BLOCK * AREA:
        raise ValueError(f"image too small for noise analysis: {gray.shape[::-1]}")

    grain, brightness, texture = block_measurements(gray)
    usable = usable_blocks(brightness, texture)
    if usable.sum() < MIN_BLOCKS:
        raise ValueError("not enough smooth area to measure grain")

    expected = expected_grain(grain, brightness, usable)
    # log ratio: 2x more and 2x less grain count the same; +0.5 keeps very smooth blocks sane
    ratio = np.abs(np.log((grain + 0.5) / (expected + 0.5)))
    deviation = area_average(ratio, usable)

    worst = np.nanmax(deviation) if np.any(~np.isnan(deviation)) else 0.0
    score = float(1 - np.exp(-worst / np.log(RATIO_SCALE)))

    map_path = out_dir / f"{image_path.stem}_noise.png"
    save_map(deviation, (gray.shape[1], gray.shape[0]), map_path)

    flags = []
    if score >= FLAG_THRESHOLD:
        flags.append(f"Grain in the {hotspot_location(deviation)} of the photo "
                     f"doesn't match the rest of the image")

    return {
        "module": "noise",
        "score": round(score, 3),
        "flags": flags,
        "artifacts": {"heatmap_path": map_path.as_posix()},
    }


if __name__ == "__main__":
    print(analyze_noise(TEST_IMAGE, TEST_OUT_DIR))