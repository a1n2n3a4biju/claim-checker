"""
Smoke test (E4.1, updated): run images through each AI-image detector candidate
and print one results table.

Candidates:
  1. UniversalFakeDetect  (CVPR 2023)  - baseline, CLIP ViT-L/14 + linear head
  2. Community Forensics  (CVPR 2025)  - ViT-S/16 @ 384, trained on thousands of generators
  3. B-Free               (CVPR 2025)  - DINOv2-reg4 ViT, trained with inpainted fakes
  4. SigLIP detector      (optional)   - Hugging Face community model

Usage (from the project root):
    python scripts/smoke_test_detectors.py samples/real.jpg samples/ai.jpg

Every score is shown as "AI probability" (0 = real, 1 = AI-generated).
Verdict uses 0.5 as the cut-off - real thresholds are chosen on Day 3/5, not here.
"""
import importlib.util
import sys
import time
from pathlib import Path

import torch
from PIL import Image
from torchvision import transforms

ROOT = Path(__file__).resolve().parents[1]          # Claim_Checker/
WEIGHTS = ROOT / "weights"
THIRD_PARTY = ROOT / "third_party"
DEVICE = "cpu"

CF_REPO_DIR = THIRD_PARTY / "Community-Forensics"
CF_MODEL_ID = "OwensLab/commfor-model-384"
BFREE_CODE_DIR = THIRD_PARTY / "B-Free" / "code"
BFREE_MODEL = "BFREE_dino2reg4"
SIGLIP_ID = "Ateeqq/ai-vs-human-image-detector"
RUN_SIGLIP = True   # set False to skip the optional 4th model


# ---------------------------------------------------------------- loaders
# Each loader returns a function: image_path -> AI probability (float 0-1)

def load_ufd():
    import clip
    model, preprocess = clip.load("ViT-L/14", device=DEVICE,
                                  download_root=str(WEIGHTS / "clip"))
    fc = torch.nn.Linear(768, 1)
    fc.load_state_dict(torch.load(WEIGHTS / "ufd_fc_weights.pth", map_location=DEVICE))
    model.eval()

    def predict(path):
        x = preprocess(Image.open(path).convert("RGB")).unsqueeze(0)
        with torch.no_grad():
            return torch.sigmoid(fc(model.encode_image(x).float())).item()
    return predict


def load_community_forensics():
    # Import only models.py from the authors' repo (avoids its training-only dependencies)
    spec = importlib.util.spec_from_file_location("cf_models", CF_REPO_DIR / "models.py")
    cf_models = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cf_models)

    # device="cpu" overrides the "cuda" stored in the model's config.json
    model = cf_models.ViTClassifier.from_pretrained(CF_MODEL_ID, device=DEVICE).to(DEVICE).eval()

    # Same as the authors' test transform: resize 440 -> centre crop 384 -> ImageNet norm
    tf = transforms.Compose([
        transforms.Resize(440),
        transforms.CenterCrop(384),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

    def predict(path):
        x = tf(Image.open(path).convert("RGB")).unsqueeze(0)
        with torch.no_grad():
            return torch.sigmoid(model(x)).flatten()[0].item()
    return predict


def load_bfree():
    sys.path.insert(0, str(BFREE_CODE_DIR))
    from main_bfree_single import get_config
    from networks import get_network, load_weights
    from utils.normalization import get_list_norm

    _, model_path, arch, norm_type = get_config(BFREE_MODEL, weights_dir=str(WEIGHTS))
    model = load_weights(get_network(arch), model_path).to(DEVICE).eval()
    tf = transforms.Compose(get_list_norm(norm_type))   # no resizing - B-Free uses 504px crops

    def predict(path):
        x = tf(Image.open(path).convert("RGB")).unsqueeze(0)
        with torch.no_grad():
            out = model(x)
        logit = out[:, 0] if out.shape[1] == 1 else out[:, 1] - out[:, 0]
        return torch.sigmoid(logit).item()                  # logit > 0 means AI
    return predict


def load_siglip():
    from transformers import pipeline
    clf = pipeline("image-classification", model=SIGLIP_ID, device=-1)

    def predict(path):
        preds = clf(Image.open(path).convert("RGB"), top_k=None)
        return next(p["score"] for p in preds if p["label"].lower() == "ai")
    return predict


CANDIDATES = {
    "UniversalFakeDetect": load_ufd,
    "Community Forensics": load_community_forensics,
    "B-Free": load_bfree,
}
if RUN_SIGLIP:
    CANDIDATES["SigLIP (optional)"] = load_siglip


# ---------------------------------------------------------------- main
def main():
    images = sys.argv[1:]
    if not images:
        sys.exit("Usage: python scripts/smoke_test_detectors.py img1.jpg [img2.jpg ...]")
    for img in images:
        if not Path(img).is_file():
            sys.exit(f"Image not found: {img}")

    rows = []        # (model, image, ai_prob or None, seconds, note)
    load_times = {}

    for name, loader in CANDIDATES.items():
        print(f"Loading {name} ...", flush=True)
        start = time.perf_counter()
        try:
            predict = loader()
        except Exception as e:
            print(f"  [FAIL] could not load: {type(e).__name__}: {e}")
            for img in images:
                rows.append((name, img, None, 0.0, "load failed"))
            continue
        load_times[name] = time.perf_counter() - start

        for img in images:
            start = time.perf_counter()
            try:
                prob = predict(img)
                rows.append((name, img, prob, time.perf_counter() - start, ""))
            except Exception as e:
                rows.append((name, img, None, 0.0, f"{type(e).__name__}: {e}"))

    # results table
    print("\n" + "=" * 86)
    print(f"{'Model':<22}{'Image':<24}{'AI prob':>9}  {'Verdict':<9}{'Time (s)':>9}  Note")
    print("-" * 86)
    for name, img, prob, secs, note in rows:
        prob_s = f"{prob:.4f}" if prob is not None else "-"
        verdict = ("AI" if prob >= 0.5 else "Real") if prob is not None else "ERROR"
        print(f"{name:<22}{Path(img).name:<24}{prob_s:>9}  {verdict:<9}{secs:>9.2f}  {note}")
    print("=" * 86)
    print("Load time (once per model): "
          + ", ".join(f"{n} {t:.1f}s" for n, t in load_times.items()))


if __name__ == "__main__":
    main()