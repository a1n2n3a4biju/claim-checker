"""
AI-generated image detection (E4, owner: M1).

analyze(image_path, out_dir) returns two results in the module contract:
    {"module": "ai_detector_1" | "ai_detector_2", "score": float 0-1, "flags": [...], "artifacts": {}}
Score = probability that the photo is AI-generated (0 = real, 1 = AI).

Which pretrained detector sits behind each slot is set in DETECTOR_1 / DETECTOR_2 below.
Provisional choice until the E4.2 comparison: Community Forensics + B-Free.
Models load once, on first use, and stay in memory. CPU only.

Setup (weights, third_party code): see docs/DETECTORS_README.md.
"""
import importlib.util
import sys
from pathlib import Path

import torch
from PIL import Image
from torchvision import transforms

# ------------------------------------------------------------------ configuration
DETECTOR_1 = "community_forensics"     # options: community_forensics, bfree, ufd, siglip
DETECTOR_2 = "bfree"
FLAG_THRESHOLD = 0.5                   # provisional; fusion (E5) decides the real weighting

ROOT = Path(__file__).resolve().parents[3]          # Claim_Checker/
WEIGHTS = ROOT / "weights"
THIRD_PARTY = ROOT / "third_party"
DEVICE = "cpu"

CF_MODEL_ID = "OwensLab/commfor-model-384"
BFREE_MODEL = "BFREE_dino2reg4"
SIGLIP_ID = "Ateeqq/ai-vs-human-image-detector"


# ------------------------------------------------------------------ loaders
# Each loader returns predict(path) -> AI probability as a plain Python float.

def _load_ufd():
    import clip
    model, preprocess = clip.load("ViT-L/14", device=DEVICE, download_root=str(WEIGHTS / "clip"))
    fc = torch.nn.Linear(768, 1)
    fc.load_state_dict(torch.load(WEIGHTS / "ufd_fc_weights.pth", map_location=DEVICE))
    model.eval()

    def predict(path):
        x = preprocess(Image.open(path).convert("RGB")).unsqueeze(0)
        with torch.no_grad():
            return float(torch.sigmoid(fc(model.encode_image(x).float())).item())
    return predict


def _load_community_forensics():
    spec = importlib.util.spec_from_file_location(
        "cf_models", THIRD_PARTY / "Community-Forensics" / "models.py")
    cf_models = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cf_models)
    model = cf_models.ViTClassifier.from_pretrained(CF_MODEL_ID, device=DEVICE).to(DEVICE).eval()
    tf = transforms.Compose([
        transforms.Resize(440),
        transforms.CenterCrop(384),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

    def predict(path):
        x = tf(Image.open(path).convert("RGB")).unsqueeze(0)
        with torch.no_grad():
            return float(torch.sigmoid(model(x)).flatten()[0].item())
    return predict


def _load_bfree():
    code_dir = str(THIRD_PARTY / "B-Free" / "code")
    if code_dir not in sys.path:
        sys.path.insert(0, code_dir)
    from main_bfree_single import get_config
    from networks import get_network, load_weights
    from utils.normalization import get_list_norm

    _, model_path, arch, norm_type = get_config(BFREE_MODEL, weights_dir=str(WEIGHTS))
    model = load_weights(get_network(arch), model_path).to(DEVICE).eval()
    tf = transforms.Compose(get_list_norm(norm_type))      # no resizing: B-Free uses 504px crops

    def predict(path):
        x = tf(Image.open(path).convert("RGB")).unsqueeze(0)
        with torch.no_grad():
            out = model(x)
        logit = out[:, 0] if out.shape[1] == 1 else out[:, 1] - out[:, 0]
        return float(torch.sigmoid(logit).item())
    return predict


def _load_siglip():
    from transformers import pipeline
    clf = pipeline("image-classification", model=SIGLIP_ID, device=-1)

    def predict(path):
        preds = clf(Image.open(path).convert("RGB"), top_k=None)
        return float(next(p["score"] for p in preds if p["label"].lower() == "ai"))
    return predict


LOADERS = {
    "ufd": _load_ufd,
    "community_forensics": _load_community_forensics,
    "bfree": _load_bfree,
    "siglip": _load_siglip,
}

_cache = {}   # detector name -> predict function


def _detector(name):
    if name not in _cache:
        if name not in LOADERS:
            raise ValueError(f"Unknown AI detector '{name}'. Options: {', '.join(LOADERS)}")
        try:
            _cache[name] = LOADERS[name]()
        except Exception as e:
            raise RuntimeError(
                f"AI detector '{name}' could not be loaded ({type(e).__name__}: {e}). "
                "Check the weights and third_party setup in docs/DETECTORS_README.md.") from e
    return _cache[name]


# ------------------------------------------------------------------ module entry point

# Reviewer-facing reason per detector: says what kind of AI fake it points to.
REASONS = {
    "community_forensics": "This photo may be fully AI-generated ({pct})",
    "bfree": "Parts of this photo may have been created or altered with AI ({pct})",
    "ufd": "This photo may be AI-generated ({pct})",
    "siglip": "This photo may be AI-generated ({pct})",
}


def _result(slot, name, image_path):
    score = round(float(_detector(name)(image_path)), 4)
    score = min(max(score, 0.0), 1.0)
    flags = []
    if score >= FLAG_THRESHOLD:
        flags.append(REASONS.get(name, "This photo may be AI-generated ({pct})").format(pct=f"{score:.0%}"))
    return {"module": slot, "score": score, "flags": flags, "artifacts": {}}


def analyze(image_path: str, out_dir: str = "results") -> list[dict]:
    """Run both AI detectors on one photo. out_dir is unused (no heatmaps), kept for the contract."""
    return [
        _result("ai_detector_1", DETECTOR_1, image_path),
        _result("ai_detector_2", DETECTOR_2, image_path),
    ]


def warm_up():
    """Optional: load both models in advance (e.g. at backend startup) so the first claim isn't slow."""
    _detector(DETECTOR_1)
    _detector(DETECTOR_2)