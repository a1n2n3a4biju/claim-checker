import io
from PIL import Image
from app.modules.jpeg_artifacts import analyze, estimate_quality


def make_fake(src, out, shift):
    """Give one square of the photo a quality-60 history, shifted `shift` px off the 8x8 grid."""
    photo = Image.open(src).convert("RGB")
    w, h = photo.size
    size = (min(w, h) // 3) // 8 * 8
    x0 = (w // 3) // 8 * 8 + shift
    y0 = (h // 3) // 8 * 8 + shift
    buf = io.BytesIO()
    photo.crop((x0, y0, x0 + size, y0 + size)).save(buf, "JPEG", quality=60)
    buf.seek(0)
    photo.paste(Image.open(buf), (x0, y0))
    photo.save(out, quality=90)


make_fake("P_001.jpg", "test_splice.jpg", 0)              # aligned to the grid
for s in (1, 3, 5):
    make_fake("P_001.jpg", f"test_splice_shift{s}.jpg", s)  # not aligned

files = ["P_001.jpg", "FW_P_001.jpg", "test_splice.jpg",
         "test_splice_shift1.jpg", "test_splice_shift3.jpg", "test_splice_shift5.jpg"]
for f in files:
    r = analyze(f, "results")
    print(f"{f:26} quality {estimate_quality(f):3}   score {r['score']:.2f}   {r['flags']}")