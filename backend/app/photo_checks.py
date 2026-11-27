"""Photo checks and fusion, unchanged from v1 (moved here out of main.py).

ELA, noise, copy-move, JPEG ghosts and two AI detectors, combined by the frozen
fusion model with thresholds 0.45 / 0.688. A claim's risk is its riskiest photo.

The detection modules are imported on first use, so the rest of the backend
(and its tests) can load without PyTorch.
"""
from pathlib import Path

import joblib

BACKEND_DIR = Path(__file__).resolve().parents[1]
FUSION_PATH = BACKEND_DIR / "fusion" / "fusion_model.joblib"
RESULTS_DIR = str(BACKEND_DIR / "results")    # served at /results

_fusion = None
_modules = None


def load():
    """Load the fusion model and warm up the AI detectors (call once at startup)."""
    global _fusion
    if FUSION_PATH.exists():
        _fusion = joblib.load(FUSION_PATH)
        print(f"Fusion model loaded (thresholds {_fusion['low']} / {_fusion['high']})")
    else:
        print("No fusion model found; using average of module scores")
    _get_modules()[2].warm_up()


def _get_modules():
    global _modules
    if _modules is None:
        from .modules import ai_detector, forensics, jpeg_artifacts
        _modules = (forensics, jpeg_artifacts, ai_detector)
    return _modules


def run_all_modules(image_path: str, out_dir: str = RESULTS_DIR):
    """Runs every module. A failing module is reported, not fatal."""
    forensics, jpeg_artifacts, ai_detector = _get_modules()
    results, problems = [], []
    for name, module in (("forensics", forensics), ("JPEG", jpeg_artifacts), ("AI", ai_detector)):
        try:
            r = module.analyze(image_path, out_dir)
            results.extend(r if isinstance(r, list) else [r])
        except Exception as e:
            problems.append(f"The {name} check failed on this photo")
            print(f"[photo checks] {name} failed on {image_path}: {type(e).__name__}: {e}")
    for r in results:
        r["score"] = float(r["score"])          # NumPy/PyTorch numbers -> plain Python
    return results, problems


def fuse(scores: dict) -> float | None:
    """Combine module scores into one risk score (0-1)."""
    if not scores:
        return None
    if _fusion and all(f in scores for f in _fusion["features"]):
        x = [[scores[f] for f in _fusion["features"]]]
        return round(float(_fusion["model"].predict_proba(x)[0, 1]), 2)
    return round(sum(scores.values()) / len(scores), 2)    # fallback: average


def risk_level(score: float) -> str:
    low, high = (_fusion["low"], _fusion["high"]) if _fusion else (0.45, 0.688)
    if score < low:
        return "low"
    return "medium" if score < high else "high"
