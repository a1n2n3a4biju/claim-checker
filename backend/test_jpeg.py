from app.modules.jpeg_artifacts import estimate_quality

for f in ["P_001.jpg", "FW_P_001.jpg"]:
    print(f, "->", estimate_quality(f))