"""
Quick check for the real AI detector module (E4.3 / E4.4).
Run from the backend folder:  python test_ai_detector.py path/to/photo.jpg [more.jpg ...]
"""
import json
import sys
import time

from app.modules import ai_detector

images = sys.argv[1:]
if not images:
    sys.exit("Usage: python test_ai_detector.py photo1.jpg [photo2.jpg ...]")

print(f"Detector 1 = {ai_detector.DETECTOR_1}, detector 2 = {ai_detector.DETECTOR_2}")

start = time.perf_counter()
ai_detector.warm_up()
print(f"Models loaded in {time.perf_counter() - start:.1f}s\n")

times = []
for path in images:
    start = time.perf_counter()
    results = ai_detector.analyze(path, "results")
    times.append(time.perf_counter() - start)

    # contract checks
    assert isinstance(results, list) and len(results) == 2
    for r in results:
        assert set(r) == {"module", "score", "flags", "artifacts"}, r
        assert type(r["score"]) is float and 0.0 <= r["score"] <= 1.0, r
        assert isinstance(r["flags"], list) and isinstance(r["artifacts"], dict), r
    json.dumps(results)   # must be JSON-serialisable for the database

    print(path)
    for r in results:
        print(f"  {r['module']}: {r['score']:.4f}  {r['flags']}")
    print(f"  time: {times[-1]:.2f}s")

print(f"\nContract OK. Average time per photo (both detectors, CPU): {sum(times) / len(times):.2f}s")