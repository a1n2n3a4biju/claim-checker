import pandas as pd
scores_path = r"data\claim-dataset\scores.csv"
s = pd.read_csv(scores_path).drop(columns="split")
m = pd.read_csv(r"data\claim-dataset\manifest.csv")[["file", "split"]]

s["file"] = s["file"].str.replace("\\", "/", regex=False)
m["file"] = m["file"].str.replace("\\", "/", regex=False)

out = s.merge(m, on="file", how="left")
print("Rows:", len(out), "| missing split:", out["split"].isna().sum())
print(out["split"].value_counts().to_dict())
if out["split"].isna().sum() == 0:
    out.to_csv(scores_path, index=False)
    print("Saved scores.csv with the fixed split")
else:
    print("NOT saved: some files still don't match")
