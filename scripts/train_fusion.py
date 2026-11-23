import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

FEATURES = ["ela", "noise", "copy_move", "jpeg", "ai_detector_1", "ai_detector_2"]
OUT = Path(__file__).resolve().parents[1] / "backend" / "fusion" / "fusion_model.joblib"

df = pd.read_csv(sys.argv[1])
df = df[df["error"].isna()]
tune = df[df["split"] == "tuning"]

X = tune[FEATURES].values
y = (tune["label"] == "fake").astype(int).values
print(f"Training on {len(tune)} tuning images ({y.sum()} fake, {(y == 0).sum()} real)")

model = make_pipeline(StandardScaler(),
                      LogisticRegression(class_weight="balanced", max_iter=1000)).fit(X, y)
p = model.predict_proba(X)[:, 1]

# Suggested thresholds from the tuning data
high = float(np.quantile(p[y == 0], 0.95))   # about 5% of genuine reach "high"
low = float(np.quantile(p[y == 1], 0.10))    # about 90% of fakes reach "medium"
low = min(low, high)
print(f"Suggested thresholds: low {low:.3f}, high {high:.3f}")

# Team can override them: python scripts/train_fusion.py scores.csv 0.30 0.70
if len(sys.argv) == 4:
    low, high = float(sys.argv[2]), float(sys.argv[3])
    print(f"Using team-chosen thresholds: low {low:.3f}, high {high:.3f}")
print("\nHow much each module counts (bigger = stronger evidence of fake):")
for f, w in sorted(zip(FEATURES, model[-1].coef_[0]), key=lambda t: -abs(t[1])):
    print(f"  {f:15} {w:+.2f}")
print(f"\nTuning AUC: {roc_auc_score(y, p):.2f}  (optimistic: same data it learned from)")
print(f"Thresholds: low < {low:.3f} <= medium < {high:.3f} <= high")

band = np.where(p < low, "low", np.where(p < high, "medium", "high"))
print("\nRisk bands per category (tuning):")
print(pd.crosstab(tune["category"], band))

OUT.parent.mkdir(parents=True, exist_ok=True)
joblib.dump({"model": model, "features": FEATURES,
             "low": round(low, 3), "high": round(high, 3)}, OUT)
print(f"\nSaved {OUT}")