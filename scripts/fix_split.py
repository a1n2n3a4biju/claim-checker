import re
from pathlib import Path
import pandas as pd

path = Path(r"data\claim-dataset\manifest.csv")
df = pd.read_csv(path)
df.to_csv(path.with_name("manifest_before_fix.csv"), index=False)   # backup

def true_source(f):
    name = f.replace("\\", "/").split("/")[-1]
    ai = re.search(r"AI_(SD|GPT|GEM)_\d{3}", name)
    p = re.search(r"[Pp]_\d{3}", name)
    return ai.group() if ai else (p.group().upper() if p else name)

df["source_id"] = df["file"].map(true_source)

# the original photo of each group is the file whose own name is the source id
stem = df["file"].map(lambda f: Path(f.replace("\\", "/")).stem.upper())
originals = df[stem == df["source_id"]]
original_split = dict(zip(originals["source_id"], originals["split"]))
df["split"] = df["source_id"].map(original_split).fillna(df["split"])

df.to_csv(path, index=False)

n = df.groupby("source_id")["split"].nunique()
print("Source photos still in both halves:", int((n > 1).sum()))
print("\nNew balance:")
print(df.groupby(["category", "split"]).size().unstack(fill_value=0))
print("\nTotal:", df["split"].value_counts().to_dict())
