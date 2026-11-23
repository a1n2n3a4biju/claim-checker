import sys
import time
from pathlib import Path

from app.modules import ai_detector, forensics, jpeg_artifacts

EXPECTED = {forensics: ["ela", "noise", "copy_move"],
            jpeg_artifacts: ["jpeg"],
            ai_detector: ["ai_detector_1", "ai_detector_2"]}
img = sys.argv[1] if len(sys.argv) > 1 else "P_001.jpg"
problems = 0


def check(ok, msg):
    global problems
    print(("  OK    " if ok else "  FAIL  ") + msg)
    problems += 0 if ok else 1


ai_detector.warm_up()
for mod, names in EXPECTED.items():
    print(f"\n{mod.__name__.split('.')[-1]}")
    runs, start = [], time.time()
    for _ in range(2):
        r = mod.analyze(img, "results")
        runs.append(r if isinstance(r, list) else [r])
    print(f"  time per run: {(time.time() - start) / 2:.1f} s")
    first, second = runs
    check([x["module"] for x in first] == names, f"module names {[x['module'] for x in first]}")
    for a, b in zip(first, second):
        n, s = a["module"], a["score"]
        check(type(s) is float, f"{n}: score is a plain float (got {type(s).__name__})")
        check(0 <= s <= 1, f"{n}: score {s} is between 0 and 1")
        check(isinstance(a["flags"], list), f"{n}: flags is a list")
        hp = a["artifacts"].get("heatmap_path")
        if hp:
            check("\\" not in hp, f"{n}: heatmap path uses forward slashes")
            check(Path(hp).exists(), f"{n}: heatmap file exists")
        check(a["score"] == b["score"], f"{n}: same score on a second run")

print(f"\n{'All checks passed' if problems == 0 else f'{problems} problem(s) found'}")