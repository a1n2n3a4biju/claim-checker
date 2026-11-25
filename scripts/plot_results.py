"""Remake the tuning-vs-test figures from the official scores and the committed model.
Usage: python scripts/plot_results.py data/claim-dataset/scores.csv
"""
import sys
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score, roc_curve

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "evaluation" / "figures"
FIG.mkdir(parents=True, exist_ok=True)

bundle = joblib.load(ROOT / "backend" / "fusion" / "fusion_model.joblib")
feats, low, high = bundle["features"], bundle["low"], bundle["high"]
df = pd.read_csv(sys.argv[1])
df["fake"] = (df["label"] == "fake").astype(int)
df["p"] = bundle["model"].predict_proba(df[feats].values)[:, 1]

splits = {"tuning": df[df.split == "tuning"], "test": df[df.split == "test"]}
colours = {"tuning": "#90caf9", "test": "#1565c0"}

fig, ax = plt.subplots(figsize=(6, 5.5))
for name, d in splits.items():
    fpr, tpr, _ = roc_curve(d.fake, d.p)
    auc = roc_auc_score(d.fake, d.p)
    ax.plot(fpr, tpr, color=colours[name], lw=2.5, label=f"{name} (AUC {auc:.2f}, n={len(d)})")
    g, f = d[d.fake == 0], d[d.fake == 1]
    for t, marker in ((low, "o"), (high, "s")):
        ax.plot((g.p >= t).mean(), (f.p >= t).mean(), marker, ms=9,
                color=colours[name], markeredgecolor="black")
ax.plot([0, 1], [0, 1], ":", color="grey", label="guessing (AUC 0.50)")
ax.plot([], [], "o", color="white", markeredgecolor="black", label=f"low threshold ({low})")
ax.plot([], [], "s", color="white", markeredgecolor="black", label=f"high threshold ({high})")
ax.set(xlabel="Genuine photos flagged (false-positive rate)",
       ylabel="Fakes caught (detection rate)", title="Fusion model ROC: tuning vs test")
ax.legend(loc="lower right", fontsize=8)
fig.tight_layout()
fig.savefig(FIG / "roc_tuning_vs_test.png", dpi=150)

rows = {}
for name, d in splits.items():
    g, f = d[d.fake == 0], d[d.fake == 1]
    rows[name] = [(f.p >= low).mean(), (f.p >= high).mean(),
                  (g.p >= low).mean(), (g.p >= high).mean()]
labels = ["fakes caught\n(medium+high)", "fakes to fraud team\n(high)",
          "genuine to review\n(medium+high)", "genuine to fraud team\n(high)"]
x = np.arange(len(labels))
fig, ax = plt.subplots(figsize=(8, 4))
for i, (name, vals) in enumerate(rows.items()):
    bars = ax.bar(x + (i - 0.5) * 0.35, vals, 0.35, color=colours[name], label=name)
    ax.bar_label(bars, labels=[f"{v:.0%}" for v in vals], fontsize=8)
ax.set_xticks(x, labels, fontsize=8)
ax.set(ylim=(0, 1.1), ylabel="Share of images", title="Tuning (seen in training) vs test (held out)")
ax.legend(title="split")
fig.tight_layout()
fig.savefig(FIG / "tuning_vs_test.png", dpi=150)

for name, v in rows.items():
    print(f"{name:7} fakes->review {v[0]:.0%}  fakes->high {v[1]:.0%}  "
          f"genuine->review {v[2]:.0%}  genuine->high {v[3]:.0%}")
print("Saved both figures in", FIG)
