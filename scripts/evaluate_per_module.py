"""
E8.2 (M1 + M2): evaluate each detection module on the categories it is
responsible for, using the module's own score (no fusion).

For every module it prints one table:
  should catch   the fake categories this check is designed to detect
  genuine        genuine, hard genuine and forwarded genuine (false alarms)
  not its job    other fake categories, shown for context only
with counts ("6 of 8") at the module's threshold, plus the AUC of its own
categories against all genuine photos (threshold-free, fair across modules).

Usage:  python scripts/evaluate_per_modules.py scores.csv          (test split)
        python scripts/evaluate_per_modules.py scores.csv tuning   (tuning split)
Saves:  evaluation/results/module_<name>_<split>.csv  one table per module
        evaluation/results/modules_summary_<split>.csv
"""

import sys
from pathlib import Path

import pandas as pd
from sklearn.metrics import roc_auc_score

# SETTINGS: which categories each module should catch, and its threshold

EDITS = ["edit_script", "edit_manual", "ai_inpaint"]
AI = ["ai", "ai_inpaint", "forwarded_fake"]
RESPONSIBLE = {
    "ela": EDITS,
    "noise": EDITS,
    "copy_move": ["edit_script"],          # only the CM_ files, see FILE_PREFIX
    "ufd": AI,
    "community_forensics": AI,
    "bfree": AI,
    "siglip": AI,
}
FILE_PREFIX = {"copy_move": "CM_"}         # copy-move should catch copy-move edits, not splices
THRESHOLDS = {"ela": 0.5, "noise": 0.4, "copy_move": 0.4}   # score at which a module "flags"
DEFAULT_THRESHOLD = 0.5                    # used for modules not listed (AI detector probabilities)
GENUINE = ["genuine", "hard_genuine", "forwarded_genuine"]

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "evaluation" / "results"


def module_table(data, module):
    threshold = THRESHOLDS.get(module, DEFAULT_THRESHOLD)
    names = data["file"].map(lambda f: Path(str(f)).name)
    prefix = FILE_PREFIX.get(module)

    def should_catch(df):
        rows = df[df["category"].isin(RESPONSIBLE[module])]
        if prefix:
            rows = rows[names.loc[rows.index].str.startswith(prefix)]
        return rows

    targets = should_catch(data)
    genuine = data[data["category"].isin(GENUINE)]
    others = data[(data["label"] == "fake") & ~data.index.isin(targets.index)]

    rows = []
    for role, part in (("should catch", targets), ("genuine (false alarms)", genuine),
                       ("not its job", others)):
        for category, group in part.groupby("category"):
            label = f"{category} ({prefix}* only)" if role == "should catch" and prefix else category
            if role == "not its job" and prefix and category in RESPONSIBLE[module]:
                label = f"{category} (other files)"
            flagged = (group[module] >= threshold).sum()
            rows.append({"role": role, "category": label, "images": len(group),
                         "flagged": f"{flagged} of {len(group)}",
                         "mean score": round(group[module].mean(), 2)})
    table = pd.DataFrame(rows)

    both = pd.concat([targets, genuine])
    y = (both["label"] == "fake").astype(int)
    auc = roc_auc_score(y, both[module]) if 0 < y.sum() < len(y) else float("nan")
    fwd = genuine[genuine["category"] == "forwarded_genuine"]
    summary = {
        "module": module,
        "threshold": threshold,
        "AUC (own categories vs genuine)": round(auc, 2),
        "caught": f"{(targets[module] >= threshold).sum()} of {len(targets)}",
        "genuine flagged": f"{(genuine[module] >= threshold).sum()} of {len(genuine)}",
        "forwarded genuine flagged": f"{(fwd[module] >= threshold).sum()} of {len(fwd)}",
    }
    return table, summary


def main():
    df = pd.read_csv(sys.argv[1])
    split = sys.argv[2] if len(sys.argv) > 2 else "test"
    if "error" in df.columns:
        df = df[df["error"].isna()]
    data = df[df["split"] == split]
    if data.empty:
        sys.exit(f"No rows with split == '{split}'")

    modules = [m for m in RESPONSIBLE if m in data.columns]
    skipped = [m for m in RESPONSIBLE if m not in data.columns]
    RESULTS.mkdir(parents=True, exist_ok=True)
    print(f"Per-module evaluation on the {split} split ({len(data)} images)")
    if skipped:
        print(f"Not in scores.csv, skipped: {skipped}")

    summaries = []
    for module in modules:
        table, summary = module_table(data, module)
        summaries.append(summary)
        print(f"\n{module}  (flags at score >= {summary['threshold']}, "
              f"AUC {summary['AUC (own categories vs genuine)']})")
        print(table.to_string(index=False))
        table.to_csv(RESULTS / f"module_{module}_{split}.csv", index=False)

    summary = pd.DataFrame(summaries)
    print(f"\nSummary ({split})")
    print(summary.to_string(index=False))
    summary.to_csv(RESULTS / f"modules_summary_{split}.csv", index=False)
    print(f"\nSaved one table per module and the summary in {RESULTS}")


if __name__ == "__main__":
    main()