from pathlib import Path

import joblib

from .modules import ai_detector, forensics, jpeg_artifacts

FUSION_PATH = Path(__file__).resolve().parents[1] / "fusion" / "fusion_model.joblib"
_fusion = None

# load_fusion(), run_all_modules(), fuse(), risk_level(): paste them here exactly as in v1

def load_fusion():
    """Load the trained fusion model if the file exists; otherwise keep averaging."""
    global _fusion
    if FUSION_PATH.exists():
        _fusion = joblib.load(FUSION_PATH)
        print(f"Fusion model loaded (thresholds {_fusion['low']} / {_fusion['high']})")
    else:
        print("No fusion model found; using average of module scores")

def run_all_modules(image_path: str, out_dir: str = "results"):
    """Runs every module. A failing module is reported, not fatal."""
    results, problems = [], []
    for name, module in (("forensics", forensics), ("JPEG", jpeg_artifacts), ("AI", ai_detector)):
        try:
            r = module.analyze(image_path, out_dir)
            results.extend(r if isinstance(r, list) else [r])
        except Exception as e:
            problems.append(f"The {name} check failed on this photo")
            print(f"[analyze] {name} failed on {image_path}: {type(e).__name__}: {e}")
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
    low, high = (_fusion["low"], _fusion["high"]) if _fusion else (0.4, 0.7)
    if score < low:
        return "low"
    return "medium" if score < high else "high"

