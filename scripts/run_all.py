import csv
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.modules import forensics, jpeg_artifacts, ai_detector

DATASET = Path(sys.argv[1])                     # path to the local claim-dataset folder
out_dir = DATASET.parent / "run_all_results"    # heatmaps go here, outside the dataset
keep = ["file", "category", "label", "manipulation", "source_id", "split"]

with open(DATASET / "manifest - manifest.csv", newline="") as f:
    rows = list(csv.DictReader(f))

ai_detector.warm_up()
results, start = [], time.time()
for i, row in enumerate(rows, 1):
    out = {k: row.get(k, "") for k in keep}
    try:
        for module in (forensics, jpeg_artifacts, ai_detector):
            r = module.analyze(str(DATASET / row["file"]), str(out_dir))
            for x in (r if isinstance(r, list) else [r]):
                out[x["module"]] = float(x["score"])
    except Exception as e:
        out["error"] = str(e)
        print(f"  ERROR on {row['file']}: {e}")
    results.append(out)
    print(f"{i}/{len(rows)}  {row['file']}  ({time.time() - start:.0f}s)")

fields = keep + ["ela", "noise", "copy_move", "jpeg", "ai_detector_1", "ai_detector_2", "error"]
with open(DATASET / "scores.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
    w.writeheader()
    w.writerows(results)
print("Saved", DATASET / "scores.csv")
