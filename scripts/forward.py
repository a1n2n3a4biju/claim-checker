from pathlib import Path
from PIL import Image

base = Path(DATASET_PATH)
src_dir = base / "genuine"
out_dir = base / "forwarded_genuine"
out_dir.mkdir(exist_ok=True)

photos = sorted(src_dir.glob("P_*.jpg"))[:35]   # P_001 to P_025

for p in photos:
    img = Image.open(p).convert("RGB")
    img.thumbnail((1600, 1600))                  # shrink like WhatsApp does
    img.save(out_dir / f"FW_{p.name}", "JPEG", quality=75)   # recompress, no EXIF kept
    print("made", f"FW_{p.name}")

print(len(photos), "forwarded copies created")