import re, pandas as pd
df = pd.read_csv(r"data\claim-dataset\manifest.csv")

def true_source(f):
    name = f.replace("\\", "/").split("/")[-1]
    ai = re.search(r"AI_(SD|GPT|GEM)_\d{3}", name)
    p = re.search(r"[Pp]_\d{3}", name)
    return ai.group() if ai else (p.group().upper() if p else name)

df["true_source"] = df["file"].map(true_source)
n = df.groupby("true_source")["split"].nunique()
bad = n[n > 1].index
print("Source photos split across tuning and test:", len(bad))
print(df[df.true_source.isin(bad)][["file", "true_source", "split"]].sort_values("true_source").to_string())
