import sys
import pandas as pd

path = sys.argv[1] if len(sys.argv) > 1 else r"C:\claim_checker\claim-dataset\manifest - manifest.csv"
df = pd.read_csv(path)

print("Rows:", len(df))
print("Columns:", list(df.columns))

print("\nImages per category and split:")
print(df.groupby(["category", "split"]).size().unstack(fill_value=0))

both = set(df[df.split == "tuning"].source_id) & set(df[df.split == "test"].source_id)
print("\nSource photos in both tune and test:", len(both), sorted(both)[:5])

missing = df[df["split"].isna() | (df["split"] == "")]
print("Images with no split:", len(missing))