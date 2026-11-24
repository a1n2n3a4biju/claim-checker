import pandas as pd

m2 = pd.read_csv(r"data\claim-dataset\scores.csv")
ref = pd.read_csv(r"data\archive\scores_anna.csv")
for t in (m2, ref):
    t["file"] = t["file"].str.replace("\\", "/", regex=False)

cols = ["ela", "noise", "copy_move", "jpeg", "ai_detector_1", "ai_detector_2"]
r = ref.set_index("file")[cols]
fixed = 0
for i, row in m2.iterrows():
    correct = r.loc[row["file"]]
    if any(abs(row[c] - correct[c]) > 1e-3 for c in cols):
        m2.loc[i, cols] = correct.values
        fixed += 1

m2.to_csv(r"data\claim-dataset\scores.csv", index=False)
print("Rows corrected:", fixed)
