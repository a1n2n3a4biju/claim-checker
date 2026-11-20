import io
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

# ---------- Quality estimation ----------

STD_LUMA = [16, 11, 10, 16, 24, 40, 51, 61,
            12, 12, 14, 19, 26, 58, 60, 55,
            14, 13, 16, 24, 40, 57, 69, 56,
            14, 17, 22, 29, 51, 87, 80, 62,
            18, 22, 37, 56, 68, 109, 103, 77,
            24, 35, 55, 64, 81, 104, 113, 92,
            49, 64, 78, 87, 103, 121, 120, 101,
            72, 92, 95, 98, 112, 100, 103, 99]


def scaled_table(quality: int) -> list[int]:
    scale = 5000 / quality if quality < 50 else 200 - 2 * quality
    return [min(max(int((v * scale + 50) // 100), 1), 255) for v in STD_LUMA]


def estimate_quality(image_path: str) -> int:
    img = Image.open(image_path)
    if img.format != "JPEG":
        raise ValueError(f"Not a JPEG file: {image_path}")
    target = sum(img.quantization[0])
    return min(range(1, 101), key=lambda q: abs(sum(scaled_table(q)) - target))


# ---------- JPEG ghost analysis ----------

QUALITIES = list(range(50, 100, 5))   # 50, 55, ... 95
BLOCK = 16                            # block size in pixels
TEXTURE_MIN = 4.0                     # skip flat blocks (std of brightness below this)
GHOST_THRESHOLD = 0.3                 # block counts as "different" above this
SCORE_SCALE = 10                      # a region covering 10% of textured area -> score 1.0

def _blocks(a: np.ndarray, how: str) -> np.ndarray:
    h, w = a.shape[0] // BLOCK * BLOCK, a.shape[1] // BLOCK * BLOCK
    b = a[:h, :w].reshape(h // BLOCK, BLOCK, w // BLOCK, BLOCK)
    return b.mean(axis=(1, 3)) if how == "mean" else b.std(axis=(1, 3))


def ghost_map(image_path: str):
    """Returns (ghost map per block 0-1, textured-block mask, last quality)."""
    img = Image.open(image_path)
    if img.format != "JPEG":
        raise ValueError(f"Not a JPEG file: {image_path}")
    last_q = estimate_quality(image_path)
    rgb_img = img.convert("RGB")
    rgb = np.asarray(rgb_img, dtype=np.float32)
    textured = _blocks(rgb.mean(axis=2), "std") >= TEXTURE_MIN

    test_qs = [q for q in QUALITIES if q <= last_q - 10]
    if not test_qs:
        return None, textured, last_q

    diffs = []
    for q in QUALITIES:
        buf = io.BytesIO()
        rgb_img.save(buf, "JPEG", quality=q)
        buf.seek(0)
        resaved = np.asarray(Image.open(buf).convert("RGB"), dtype=np.float32)
        diffs.append(_blocks(((rgb - resaved) ** 2).mean(axis=2), "mean"))

    d = np.stack(diffs)                                      # (qualities, rows, cols)
    d = (d - d.min(axis=0)) / (d.max(axis=0) - d.min(axis=0) + 1e-6)

    idx = [QUALITIES.index(q) for q in test_qs]
    typical = np.median(d[idx][:, textured], axis=1)         # typical block, per quality
    ghost = (typical[:, None, None] - d[idx]).max(axis=0)    # how unusually unchanged
    ghost = np.clip(ghost, 0, 1)
    ghost[~textured] = 0
    return ghost, textured, last_q


def _where(x: float, y: float) -> str:
    v = "upper" if y < 1 / 3 else ("lower" if y > 2 / 3 else "middle")
    h = "left" if x < 1 / 3 else ("right" if x > 2 / 3 else "centre")
    return "centre" if (v, h) == ("middle", "centre") else f"{v} {h}"


def analyze(image_path: str, out_dir: str) -> dict:
    image_id = Path(image_path).stem
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    heat_path = Path(out_dir) / f"{image_id}_jpeg.png"
    width, height = Image.open(image_path).size

    ghost, textured, last_q = ghost_map(image_path)

    if ghost is None or textured.sum() < 20:
        cv2.imwrite(str(heat_path), np.zeros((height, width, 3), np.uint8))
        reason = ("Photo is too heavily compressed for JPEG ghost analysis" if ghost is None
                  else "Too few detailed areas to run JPEG ghost analysis")
        return {"module": "jpeg", "score": 0.0, "flags": [reason],
                "artifacts": {"heatmap_path": heat_path.as_posix()}}

    mask = (ghost > GHOST_THRESHOLD).astype(np.uint8)
    n, labels, stats, centres = cv2.connectedComponentsWithStats(mask, connectivity=8)
    flags = []
    if n > 1:
        k = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        largest = int(stats[k, cv2.CC_STAT_AREA])
    else:
        k, largest = 0, 0
    if largest < 3:                       # ignore tiny specks
        largest = 0

    fraction = largest / textured.sum()
    score = round(float(min(1.0, fraction * SCORE_SCALE)), 2)

    if score >= 0.5:
        cx, cy = centres[k]
        where = _where(cx / ghost.shape[1], cy / ghost.shape[0])
        flags.append(f"Part of the photo ({where}, about {fraction:.0%} of the detailed area) "
                     f"has a different compression history; possible pasted region")

    heat = cv2.resize((ghost * 255).astype(np.uint8), (width, height),
                      interpolation=cv2.INTER_NEAREST)
    cv2.imwrite(str(heat_path), cv2.applyColorMap(heat, cv2.COLORMAP_JET))

    return {"module": "jpeg", "score": score, "flags": flags,
            "artifacts": {"heatmap_path": heat_path.as_posix()}}