import csv, re
from pathlib import Path

# Note the leading space in the folder name as listed in your Google Drive
DATASET_PATH = "/content/drive/MyDrive/ claim-dataset"
base = Path(DATASET_PATH)

LABEL = {"genuine": "real", "hard_genuine": "real", "forwarded_genuine": "real",
         "Scripted_edits": "fake", "careful_manual_edits": "fake", "ai": "fake",
         "ai_inpaint": "fake", "forwarded_fake": "fake"}
MANIP = {"CM": "copy_move", "SP": "splice", "ME": "manual_edit", "IN": "ai_inpaint"}
GEN = {"SD": "stable_diffusion", "GPT": "chatgpt", "GEM": "gemini"}

rows = []
for folder, label in LABEL.items():
    for p in sorted((base / folder).glob("*.jpg")):
        name = p.stem
        core = name.removeprefix("FW_")
        ai = re.search(r"AI_(SD|GPT|GEM)_\d{3}", name)
        src = re.search(r"P_\d{3}", name)
        donor = re.search(r"D_\d{3}", name)
        mask = base / "masks" / f"{core}.png"
        rows.append({
            "file": f"{folder}/{p.name}",
            "category": folder,
            "label": label,
            "manipulation": "ai_full" if ai else MANIP.get(core.split("_")[0], "none"),
            "source_id": ai.group() if ai else (src.group() if src else name),
            "source": GEN[ai.group(1)] if ai else "humansintheloop_car_damages",
            "assumed_real": "no" if ai else "yes",
            "donor": donor.group() if donor else "",
            "mask_path": f"masks/{core}.png" if mask.exists() else "",
            "forwarded": "yes" if name.startswith("FW_") else "no",
            "split": "",
        })

if rows:
    with open(base / "manifest.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)

    print(len(rows), "images listed")
    for folder in LABEL:
        print(f"  {folder}: {sum(r['category'] == folder for r in rows)}")
else:
    print(f"No images found under {base}. Please verify if the subfolders contain any .jpg images.")