"""
Edit forensics module (E2.4).

Runs the three edit checks on one photo and returns them in the README contract:

    analyze(image_path, out_dir) -> [ela dict, noise dict, copy_move dict]

Each dict: {"module", "score" (0-1), "flags" (list of sentences),
            "artifacts": {"heatmap_path": "<out_dir>/<image_id>_<module>.png"}}

Quick test: set TEST_INPUT below to a photo or a folder of photos, then
    python forensics.py
"""

import sys
import time
from pathlib import Path

try:                                    # imported by the backend: app.modules.forensics
    from .copy_move import analyze_copy_move
    from .ela import analyze_ela
    from .noise import analyze_noise
except ImportError:                     # run directly: python forensics.py
    from copy_move import analyze_copy_move
    from ela import analyze_ela
    from noise import analyze_noise

CHECKS = [("ela", analyze_ela), ("noise", analyze_noise), ("copy_move", analyze_copy_move)]


ROOT_DIR = Path(__file__).resolve().parents[3]
IMAGE_DATA_PATH =  ROOT_DIR / "data" / "images"
IMAGE_DIR = "hard_genuine"
TEST_FILE_NAME = "P_051.jpg"
TEST_INPUT = IMAGE_DATA_PATH / IMAGE_DIR / TEST_FILE_NAME  # a photo, or a folder of .jpg photos
TEST_OUT_DIR = IMAGE_DATA_PATH / "out_dir"


def analyze(image_path, out_dir):
    image_path = Path(image_path)
    if not image_path.is_file():
        raise FileNotFoundError(f"image not found: {image_path}")

    results = []
    for module, check in CHECKS:
        try:
            result = check(image_path, out_dir)
        except Exception as exc:
            raise RuntimeError(f"{module} failed on {image_path.name}: {exc}") from exc
        results.append(result)
    return results


def run_test(target, out_dir):
    """Run analyze() on a photo or every .jpg in a folder and report any errors."""
    target = Path(target)
    photos = sorted(target.glob("*.jpg")) if target.is_dir() else [target]
    failed = 0
    for photo in photos:
        start = time.time()
        try:
            results = analyze(photo, out_dir)
            print(results)
        except Exception as exc:
            failed += 1
            print(f"FAILED {photo.name}: {exc}")
            continue
        scores = "  ".join(f"{r['module']} {r['score']:.2f}" for r in results)
        print(f"{photo.name}: {scores}  ({time.time() - start:.1f} s)")
        for r in results:
            for flag in r["flags"]:
                print(f"    - {flag}")
    print(f"\n{len(photos) - failed} of {len(photos)} photos ran without error.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run_test(TEST_INPUT, TEST_OUT_DIR))