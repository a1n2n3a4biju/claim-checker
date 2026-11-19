import random

def analyze(image_path: str, out_dir: str) -> list[dict]:
    """STUB: returns random scores. M1 replaces with real detectors."""
    return [
        {"module": "ai_detector_1", "score": round(random.random(), 2), "flags": [], "artifacts": {}},
        {"module": "ai_detector_2", "score": round(random.random(), 2), "flags": [], "artifacts": {}},
    ]