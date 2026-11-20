import io
from PIL import Image
from app.modules.jpeg_artifacts import analyze, estimate_quality

# Make a test fake: one square of P_001 gets a quality-60 history
photo = Image.open("P_001.jpg").convert("RGB")
w, h = photo.size
x0, y0, size = (w // 3) // 8 * 8, (h // 3) // 8 * 8, (min(w, h) // 3) // 8 * 8
buf = io.BytesIO()
photo.crop((x0, y0, x0 + size, y0 + size)).save(buf, "JPEG", quality=60)
buf.seek(0)
photo.paste(Image.open(buf), (x0, y0))
photo.save("test_splice.jpg", quality=90)

for f in ["P_001.jpg", "FW_P_001.jpg", "test_splice.jpg"]:
    r = analyze(f, "results")
    print(f"{f:18} quality {estimate_quality(f):3}   score {r['score']:.2f}   {r['flags']}")