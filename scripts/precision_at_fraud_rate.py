"""
E8.3: estimate precision at a realistic fraud rate.

The test split is about half fake, but real claims are mostly honest. This
script takes the detection rate (TPR) and false-positive rate (FPR) measured
on the test split and works out what they mean when only FRAUD_RATE of claims
are fraudulent:

    precision = (TPR x rate) / (TPR x rate + FPR x (1 - rate))
              = share of flagged claims that really are fraud

It does this for two routing decisions:
    "any review"  claims in medium or high (a person looks at them)
    "fraud team"  claims in high only

Usage:  python scripts/precision_at_fraud_rate.py scores.csv
Saves:  evaluation/results/precision_at_fraud_rate.csv
        evaluation/results/precision_vs_fraud_rate.png
"""

import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

FRAUD_RATE = 0.05
PER_CLAIMS = 1000                       # the "out of 1000 claims" example in the report

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "backend" / "fusion" / "fusion_model.joblib"
RESULTS = ROOT / "evaluation" / "results"


def wilson(k, n, z=1.96):
    """95% range for a rate measured as k out of n (honest for small n)."""
    if n == 0:
        return 0.0, 1.0
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, centre - half), min(1.0, centre + half)


def precision(tpr, fpr, rate):
    caught, false_alarms = tpr * rate, fpr * (1 - rate)
    return caught / (caught + false_alarms) if caught + false_alarms > 0 else float("nan")


saved = joblib.load(MODEL)
model, features, low, high = saved["model"], saved["features"], saved["low"], saved["high"]

df = pd.read_csv(sys.argv[1])
if "error" in df.columns:
    df = df[df["error"].isna()]
test = df[df["split"] == "test"].copy()
score = model.predict_proba(test[features].values)[:, 1]
is_fake = (test["label"] == "fake").values

rows = []
for decision, threshold in (("any review (medium+high)", low), ("fraud team (high)", high)):
    flagged = score >= threshold
    k_tp, n_fake = int((flagged & is_fake).sum()), int(is_fake.sum())
    k_fp, n_real = int((flagged & ~is_fake).sum()), int((~is_fake).sum())
    tpr, fpr = k_tp / n_fake, k_fp / n_real
    tpr_lo, tpr_hi = wilson(k_tp, n_fake)
    fpr_lo, fpr_hi = wilson(k_fp, n_real)

    fraud = PER_CLAIMS * FRAUD_RATE
    honest = PER_CLAIMS - fraud
    rows.append({
        "decision": decision,
        "TPR (fakes flagged)": f"{k_tp} of {n_fake} = {tpr:.0%}",
        "FPR (genuine flagged)": f"{k_fp} of {n_real} = {fpr:.0%}",
        f"precision at {FRAUD_RATE:.0%}": round(precision(tpr, fpr, FRAUD_RATE), 3),
        # worst case: fewest fakes caught, most false alarms; best case: the opposite
        "likely range": f"{precision(tpr_lo, fpr_hi, FRAUD_RATE):.2f} to "
                        f"{precision(tpr_hi, fpr_lo, FRAUD_RATE):.2f}",
        f"per {PER_CLAIMS} claims: fraud flagged": round(fraud * tpr),
        f"per {PER_CLAIMS} claims: honest flagged": round(honest * fpr),
        f"per {PER_CLAIMS} claims: fraud missed": round(fraud * (1 - tpr)),
        "_tpr": tpr, "_fpr": fpr,
    })

table = pd.DataFrame(rows)
print(f"Test split: {is_fake.sum()} fake, {(~is_fake).sum()} genuine. "
      f"Fraud rate assumed: {FRAUD_RATE:.0%}\n")
print(table.drop(columns=["_tpr", "_fpr"]).T.to_string(header=False))

for r in rows:
    flagged_total = r[f"per {PER_CLAIMS} claims: fraud flagged"] + r[f"per {PER_CLAIMS} claims: honest flagged"]
    print(f"\n{r['decision']}: out of {PER_CLAIMS} claims ({PER_CLAIMS * FRAUD_RATE:.0f} fraudulent), "
          f"{flagged_total} are flagged, of which {r[f'per {PER_CLAIMS} claims: fraud flagged']} are fraud "
          f"and {r[f'per {PER_CLAIMS} claims: honest flagged']} are honest; "
          f"{r[f'per {PER_CLAIMS} claims: fraud missed']} fraudulent claims pass as low risk.")


table.drop(columns=["_tpr", "_fpr"]).to_csv(RESULTS / "precision_at_fraud_rate.csv", index=False)
print(f"\nSaved {RESULTS / 'precision_at_fraud_rate.csv'}")


# ready-to-paste report section (worked calculation + figure)
r_any, r_high = rows
n_fake, n_real = int(is_fake.sum()), int((~is_fake).sum())


def worked(r):
    tpr, fpr, rate = r["_tpr"], r["_fpr"], FRAUD_RATE
    top, bottom = tpr * rate, tpr * rate + fpr * (1 - rate)
    return (f"precision = ({tpr:.3f} × {rate:.2f}) / ({tpr:.3f} × {rate:.2f} + {fpr:.3f} × {1 - rate:.2f})\n"
            f"                  = {top:.4f} / {bottom:.4f} = {precision(tpr, fpr, rate):.3f}")


def story(r):
    fraud_flagged = r[f"per {PER_CLAIMS} claims: fraud flagged"]
    honest_flagged = r[f"per {PER_CLAIMS} claims: honest flagged"]
    missed = r[f"per {PER_CLAIMS} claims: fraud missed"]
    return (f"Out of {PER_CLAIMS} claims, {PER_CLAIMS * FRAUD_RATE:.0f} of them fraudulent, "
            f"{fraud_flagged + honest_flagged} would be flagged: {fraud_flagged} fraudulent and "
            f"{honest_flagged} honest. {missed} fraudulent claims would pass as low risk.")