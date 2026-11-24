"""
E5.1: run the edit-forensics checks on the whole dataset and save
scores.csv, one row per image with every check's score and the label.

Checks (backend/app/modules/forensics.py):
  ela, noise, copy_move

Rows are saved after every image, so if the run stops you can start it again
and it continues where it left off. Images that fail are kept with the error
message and empty scores, and are retried on the next run.

How to run: edit the SETTINGS below, then
    python run_all_modules.py
"""

import sys
import time
from pathlib import Path

import pandas as pd

# SETTINGS

ROOT_DIR = Path(__file__).resolve().parent.parent
IMAGES_DIR = ROOT_DIR / "data" / "images"  # folder the manifest's "file" column is relative to
MANIFEST = IMAGES_DIR / "manifest.csv"
BACKEND_DIR = ROOT_DIR / "backend"              # folder that contains app/modules/
OUTPUT_CSV = IMAGES_DIR / "scores.csv"
ARTIFACT_DIR = IMAGES_DIR / "run_artifacts"

FEATURES = ["ela", "noise", "copy_move"]
# later: FEATURES += ["jpeg", "ai_detector_1", "ai_detector_2"]
KEEP_COLUMNS = ["file", "category", "label", "split", "source_id", "forwarded"]

sys.path.insert(0, str(ROOT_DIR.resolve()))
from backend.app.modules import forensics  # noqa: E402

MODULE_FILES = [forensics]
# later: from app.modules import jpeg_artifacts, ai_detector
#        MODULE_FILES = [forensics, jpeg_artifacts, ai_detector]


def score_image(image_path):
    """Run every module on one image; return {module name: score}."""
    scores = {}
    for module_file in MODULE_FILES:
        results = module_file.analyze(str(image_path), str(ARTIFACT_DIR))
        if isinstance(results, dict):          # a module that returns one dict
            results = [results]
        for result in results:
            scores[result["module"]] = float(result["score"])
    missing = set(FEATURES) - set(scores)
    if missing:
        raise ValueError(f"modules did not return: {sorted(missing)}")
    return scores


def load_previous():
    """Rows from an earlier run that finished without error."""
    if not OUTPUT_CSV.exists():
        return {}
    old = pd.read_csv(OUTPUT_CSV, dtype={"error": str})
    if not set(FEATURES) <= set(old.columns):   # new modules were added: score everything again
        return {}
    done = old[old["error"].isna() & old[FEATURES].notna().all(axis=1)]
    return {row["file"]: row for row in done.to_dict("records")}


def main() -> int:
    manifest = pd.read_csv(MANIFEST, dtype=str)
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    previous = load_previous()
    rows = []
    start = time.time()
    for i, entry in enumerate(manifest.to_dict("records"), 1):
        row = {col: entry.get(col) for col in KEEP_COLUMNS}
        row["y"] = 1 if entry["label"] == "fake" else 0

        if entry["file"] in previous:
            row.update({f: previous[entry["file"]][f] for f in FEATURES})
            row["error"] = None
            status = "already done"
        else:
            try:
                row.update(score_image(IMAGES_DIR / entry["file"]))
                row["error"] = None
                status = "ok"
            except Exception as exc:
                row.update({f: None for f in FEATURES})
                row["error"] = str(exc)
                status = f"FAILED: {exc}"
        rows.append(row)

        # save after every image so a crash loses nothing
        pd.DataFrame(rows, columns=KEEP_COLUMNS + FEATURES + ["error"]).to_csv(OUTPUT_CSV, index=False)
        print(f"[{i}/{len(manifest)}] {entry['file']}: {status}")

    scores = pd.read_csv(OUTPUT_CSV)
    failed = scores["error"].notna().sum()
    print(f"\nSaved {OUTPUT_CSV}: {len(scores)} rows, {failed} failed, "
          f"{(time.time() - start) / 60:.1f} min")
    if failed:
        print("Failed images (run again to retry):")
        print(scores.loc[scores["error"].notna(), ["file", "error"]].to_string(index=False))

    print("\nMean score per module, genuine vs fake (fakes should be higher):")
    print(scores.groupby("label")[FEATURES].mean().round(2).to_string())
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())