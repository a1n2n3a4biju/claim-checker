import random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def analyze(image_path: str, out_dir: str) -> list[dict]:
    """STUB: returns random scores. M2 replaces with real ELA, noise and copy-move."""
    image_id = Path(image_path).stem
    Path(out_dir).mkdir(parents=True, exist_ok=True)

    results = []
    for name in ["ela", "noise", "copy_move"]:
        heatmap = Path(out_dir) / f"{image_id}_{name}.png"

        img = Image.open(image_path).convert("L")
        font = ImageFont.load_default(size=max(20, img.width // 15))
        ImageDraw.Draw(img).text((20, 20), f"STUB {name.upper()}", fill=255, font=font)
        img.save(heatmap)

        results.append({
            "module": name,
            "score": round(random.random(), 2),
            "flags": [f"Stub {name} flag"] if random.random() > 0.5 else [],
            "artifacts": {"heatmap_path": heatmap.as_posix()},
        })
    return results