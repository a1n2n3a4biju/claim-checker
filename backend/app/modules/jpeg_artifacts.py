import random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def analyze(image_path: str, out_dir: str) -> dict:
    """STUB: returns a random score. Replace with the real double-compression check."""
    image_id = Path(image_path).stem
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    block_map = Path(out_dir) / f"{image_id}_jpeg.png"

    img = Image.open(image_path).convert("L")
    font = ImageFont.load_default(size=max(20, img.width // 15))
    ImageDraw.Draw(img).text((20, 20), "STUB JPEG", fill=255, font=font)
    img.save(block_map)

    return {
        "module": "jpeg",
        "score": round(random.random(), 2),
        "flags": [],
        "artifacts": {"heatmap_path": block_map.as_posix()},
    }