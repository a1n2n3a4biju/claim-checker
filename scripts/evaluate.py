import argparse
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[1]

ap = argparse.ArgumentParser(description="Evaluate the fusion model and modules.")
ap.add_argument("scores", help="path to scores.csv")
ap.add_argument("--model", default=str(ROOT / "backend" / "fusion" / "fusion_model.joblib"))
ap.add_argument("--final", action="store_true",
                help="evaluate on the TEST split. Run once, on the final model only.")
ap.add_argument("--fraud-rate", type=float, default=0.05)
a = ap.parse_args()

split = "test" if a.final else "tuning"
bundle = joblib.load(a.model)
feats, low, high = bundle["features"], bundle["low"], bundle["high"]

df = pd.read_csv(a.scores)
df = df[df["error"].isna()]
d = df[df["split"] == split].copy()
d["fake"] = (d["label"] == "fake").astype(int)
d["p"] = bundle["model"].predict_proba(d[feats].values)[:, 1]
d["band"] = np.select([d["p"] < low, d["p"] < high], ["low", "medium"], "high")

lines = []
out = lines.append
out(f"# Evaluation on the {split.upper()} split")
if not a.final:
    out("_Dry run on tuning data: optimistic, NOT the final result._")
out(f"\nImages: {len(d)} ({d.fake.sum()} fake, {(d.fake == 0).sum()} real). "
    f"Thresholds: low < {low} <= medium < {high} <= high.\n")

# 1. Per category
out("## Results per category\n")
out("| Category | Label | Images | Medium or high | High |")
out("|---|---|---|---|---|")
for cat, g in d.groupby("category"):
    n, med, hi = len(g), int((g.band != "low").sum()), int((g.band == "high").sum())
    lab = "fake" if g.fake.iloc[0] else "real"
    out(f"| {cat} | {lab} | {n} | {med} of {n} ({med / n:.0%}) | {hi} of {n} ({hi / n:.0%}) |")

# 2. Overall separation
out(f"\n## Overall\n\nFusion AUC (fake vs real): **{roc_auc_score(d.fake, d.p):.2f}**\n")

# 3 + 4. Operating points and precision at a realistic fraud rate
r = a.fraud_rate
out(f"## Operating points (precision assumes {r:.0%} of claims are fraudulent)\n")
out("| Flagged as | Fakes caught | Genuine wrongly flagged | Precision |")
out("|---|---|---|---|")
for name, flag in [("medium or high (sent to a human)", d.band != "low"),
                   ("high only (fraud team)", d.band == "high")]:
    tpr, fpr = flag[d.fake == 1].mean(), flag[d.fake == 0].mean()
    prec = tpr * r / (tpr * r + fpr * (1 - r)) if (tpr + fpr) > 0 else float("nan")
    out(f"| {name} | {tpr:.0%} | {fpr:.0%} | {prec:.0%} |")

# 5. Per module, on the fakes each module is meant to catch
TARGETS = {
    "ela": ["copy_move", "splice", "manual"],
    "noise": ["copy_move", "splice", "manual"],
    "copy_move": ["copy_move"],
    "jpeg": ["splice"],
    "ai_detector_1": ["ai_full", "ai_inpaint"],
    "ai_detector_2": ["ai_full", "ai_inpaint"],
}
out("\n## Each module on the fakes it targets\n")
out("| Module | Fakes it targets | Fakes | AUC vs all real |")
out("|---|---|---|---|")
real = d[d.fake == 0]
for m, targets in TARGETS.items():
    fakes = d[d.manipulation.isin(targets)]
    if len(fakes) and m in d:
        s = pd.concat([real[m], fakes[m]])
        y = [0] * len(real) + [1] * len(fakes)
        out(f"| {m} | {', '.join(targets)} | {len(fakes)} | {roc_auc_score(y, s):.2f} |")

out("\n_Small groups (under about 10 images) give rough numbers; report counts, not just percentages._")

text = "\n".join(lines)
print(text)
dest = ROOT / "evaluation" / f"results_{split}.md"
dest.parent.mkdir(exist_ok=True)
dest.write_text(text, encoding="utf-8")
print(f"\nSaved {dest}")