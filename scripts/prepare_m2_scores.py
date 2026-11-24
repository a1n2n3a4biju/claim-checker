import pandas as pd

src = r"data\claim-dataset\scores_m2_final.csv"
out = r"data\claim-dataset\scores.csv"

d = pd.read_csv(src)
man = pd.read_csv(r"data\claim-dataset\manifest.csv")
for t in (d, man):
    t["file"] = t["file"].str.replace("\\", "/", regex=False)

# same names the backend uses for the AI modules
d = d.rename(columns={"community_forensics": "ai_detector_1", "bfree": "ai_detector_2"})

# columns the scripts need
if "manipulation" not in d:
    d = d.merge(man[["file", "manipulation"]], on="file", how="left")
d["error"] = pd.NA

need = ["file", "category", "label", "manipulation", "split",
        "ela", "noise", "copy_move", "jpeg", "ai_detector_1", "ai_detector_2"]
missing = [c for c in need if c not in d]
print("Rows:", len(d), "| missing columns:", missing,
      "| rows without manipulation:", int(d["manipulation"].isna().sum()))
print("Split:", d["split"].value_counts().to_dict())

if not missing and d["manipulation"].notna().all():
    d.to_csv(out, index=False)
    print("Saved", out)
else:
    print("NOT saved: fix the problems above first")
