from app.modules import forensics, jpeg_artifacts, ai_detector

img, out = "test.jpg", "results"
print(forensics.analyze(img, out))
print(jpeg_artifacts.analyze(img, out))
print(ai_detector.analyze(img, out))