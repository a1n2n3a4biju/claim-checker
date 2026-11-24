# Claim-Checker: AI-Image Detector Setup (M1, Day 1)

Owner: M1 (Detection engineer) · Epics: E4 AI-generated detection, E7 React frontend (E3 moved to M3)
Branch: `alex-data` · Status: **E4.1 done** (all candidate detectors run on CPU)

This document records what was set up on Day 1, how to reproduce it, the first results,
and the decisions the team still needs to confirm.

---

## 1. Summary of Day 1

- Project folder structure created and pushed (`detection/`, `fusion/`, `backend/`, `frontend/`,
  `data/`, `evaluation/`, `scripts/`, `notebooks/`, `samples/`, `report/`, `contract/`).
- Python environment set up on the VM (Python 3.12, CPU-only PyTorch).
- Smoke test script written: `scripts/smoke_test_detectors.py`. It loads each AI-image detector once,
  runs any number of images, and prints one results table (model, image, AI probability, verdict, time).
- **Detector candidates changed** from the plan (needs team confirmation, see section 6):
  - Kept: **UniversalFakeDetect** (baseline)
  - Added: **Community Forensics** (CVPR 2025) and **B-Free** (CVPR 2025)
  - Optional: **SigLIP** community model
  - Dropped: **NYUAD ViT** (fails to load; its config is missing the image-processor type)
- First finding: on the AI images tested so far (ChatGPT / Gemini / Stable Diffusion), the detectors
  often score AI images as real. This is a known limitation of current detectors on new commercial
  generators and will be measured properly on Day 3 (E4.2).

---

## 2. Environment setup (Windows VM)

### Python version
Use **Python 3.12**. Python 3.14 (the VM default) is too new for parts of the ML stack.
Everyone on the team should use the same version.

```powershell
py -0                                   # list installed Python versions
pymanager install 3.12                  # if the Python Install Manager is present
# otherwise: python.org installer for 3.12, untick "Use admin privileges"
```

> On this VM the old `py.exe` launcher blocks `py install`. Use `pymanager` instead, or the
> python.org installer. Do not uninstall the old launcher.

### Virtual environment
```powershell
py -3.12 -m venv venv                   # or: pymanager exec -V:3.12 -m venv venv
venv\Scripts\activate
python --version                        # must show 3.12.x
```
If PowerShell blocks activation: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

### Packages
Always install with `python -m pip` so packages go into the venv:
```powershell
python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
python -m pip install transformers pillow opencv-python numpy "setuptools==69.5.1"
python -m pip install git+https://github.com/openai/CLIP.git
python -m pip install timm huggingface_hub pyyaml pandas
```

Notes:
- **CPU-only PyTorch** is intentional (smaller, and the demo machine has no GPU).
  `pip install -r requirements.txt` would pull the large GPU build, so install torch with the
  command above first.
- **`setuptools==69.5.1` is pinned** because OpenAI's CLIP package imports `pkg_resources`,
  which newer setuptools versions changed.
- If pip in the venv ever breaks (half-finished upgrade), delete `venv` and recreate it.
  Do not run `pip install --upgrade pip` on the VM.

---

## 3. Detector setup

All model files live in `weights/` and third-party code in `third_party/`.
**Both folders are git-ignored**; each member downloads them locally.

### 3.1 Authors' code (needed for Community Forensics and B-Free)
```powershell
mkdir third_party
git clone --depth 1 https://github.com/JeongsooP/Community-Forensics.git third_party\Community-Forensics
git clone --depth 1 https://github.com/grip-unina/B-Free.git third_party\B-Free
```

### 3.2 Weights

| Model | What to download | Where it goes |
|---|---|---|
| UniversalFakeDetect head | `fc_weights.pth` from the UniversalFakeDetect GitHub repo (`pretrained_weights/`) | `weights\ufd_fc_weights.pth` |
| CLIP ViT-L/14 (for UFD) | Automatic on first run (~890 MB) | `weights\clip\ViT-L-14.pt` |
| Community Forensics | Automatic on first run from Hugging Face (`OwensLab/commfor-model-384`) | Hugging Face cache |
| B-Free | `BFREE_dino2reg4.zip` from the B-Free code README (GRIP download page) | Extract to `weights\BFREE_dino2reg4\` |
| SigLIP (optional) | Automatic on first run (`Ateeqq/ai-vs-human-image-detector`) | Hugging Face cache |

UFD head:
```powershell
Invoke-WebRequest -Uri "https://github.com/WisconsinAIVision/UniversalFakeDetect/raw/main/pretrained_weights/fc_weights.pth" -OutFile "weights\ufd_fc_weights.pth"
```

B-Free (use `curl.exe`, not `curl`; check the MD5 before extracting):
```powershell
curl.exe -L -o weights\BFREE_dino2reg4.zip https://www.grip.unina.it/download/prog/B-Free/weights/BFREE_dino2reg4.zip
Get-FileHash weights\BFREE_dino2reg4.zip -Algorithm MD5     # must be F3F53FA647848B16CF81C913F148A198
Expand-Archive weights\BFREE_dino2reg4.zip -DestinationPath weights -Force
```
Expected layout:
```
weights/
├── clip/ViT-L-14.pt
├── ufd_fc_weights.pth
└── BFREE_dino2reg4/
    ├── config.yaml
    └── model_epoch_best.pth
```

### 3.3 The detectors

| Detector | Paper | Backbone | Input handling | Output used | License |
|---|---|---|---|---|---|
| UniversalFakeDetect | CVPR 2023 | Frozen CLIP ViT-L/14 + linear head | Resize + centre crop 224 | sigmoid(logit) | Research code |
| Community Forensics | CVPR 2025 | ViT-S/16 @ 384, trained on images from thousands of generators | Resize 440 → centre crop 384 → ImageNet norm (same as authors' test transform) | sigmoid(logit) | MIT |
| B-Free | CVPR 2025 | DINOv2 ViT with 4 registers, trained on SD inpainted fakes | **No resizing**; five 504×504 crops averaged | sigmoid(logit); logit > 0 means AI | Non-profit / research only |
| SigLIP (optional) | Community model | SigLIP classifier | Hugging Face pipeline | score of label `ai` (other label: `hum`) | See model card |

Implementation notes:
- Community Forensics: only `models.py` is imported from the authors' repo (its other files need
  training-only packages such as wandb). The model's config stores `device: cuda`; the script
  overrides this with `device="cpu"`.
- B-Free: uses the authors' own `get_config`, `get_network`, `load_weights` and normalisation code.
  It is the slowest on CPU because it analyses the full-resolution image.

---

## 4. Running the smoke test

From the project root, with the venv active:
```powershell
python scripts\smoke_test_detectors.py samples\real.jpg samples\ai.jpg
```
- Any number of images can be passed.
- Every score is reported as **AI probability** (0 = real, 1 = AI-generated).
- Verdict uses a 0.5 cut-off **only for this check**. Real thresholds come from Day 3 and Day 5.
- If one model fails, the others still run; the error appears in the Note column.
- Set `RUN_SIGLIP = False` at the top of the script to skip the optional model.

### B-Free correctness check
The B-Free repo ships demo images with the authors' scores. Run:
```powershell
python scripts\smoke_test_detectors.py third_party\B-Free\code\demo_images\img0000.png third_party\B-Free\code\demo_images\img0002.png
```
Expected B-Free AI probability: about **0.003** for `img0000.png` (real) and about **0.99** for
`img0002.png` (AI), matching the authors' logits of -5.94 and 4.43.

Result on our VM: _fill in_

---



## 7. Harmless warnings you will see

- `torch.jit.load is deprecated`: from CLIP, safe to ignore.
- `unauthenticated requests to the HF Hub` / `HF_TOKEN`: optional, only affects download speed.
- Hugging Face `symlinks` warnings: Windows VM limitation, uses slightly more disk.
- SigLIP `bos_token_id` / `eos_token_id` notices: safe to ignore.

---




## Final choice (E4.2) and held-out results (E8.2)

Final, leak-free split from `data/manifest.csv` (117 tuning / 78 test, 60/40 in every category).
Flag threshold 0.5. Counts are images flagged as AI.

**Chosen pair:** `ai_detector_1` = **Community Forensics**, `ai_detector_2` = **B-Free**
(set in `DETECTOR_1` / `DETECTOR_2` in `backend/app/modules/ai_detector.py`).

### Tuning split (used to choose)

| Detector | AI fakes caught | Genuine flagged | Forwarded genuine flagged | AUC |
|---|---|---|---|---|
| B-Free | 14 of 33 | 2 of 59 | 1 of 21 | 0.855 |
| Community Forensics | 6 of 33 | 0 of 59 | 0 of 21 | 0.636 |
| UniversalFakeDetect (rejected) | 1 of 33 | 2 of 59 | 1 of 21 | 0.570 |
| SigLIP (rejected) | 9 of 33 | 25 of 59 | 10 of 21 | 0.342 |

### Test split (held out)

| Detector | AI fakes caught | Genuine flagged | Forwarded genuine flagged | AUC |
|---|---|---|---|---|
| B-Free | 7 of 22 | 0 of 40 | 0 of 14 | 0.790 |
| Community Forensics | 5 of 22 | 0 of 40 | 0 of 14 | 0.553 |

By source on the test split: Stable Diffusion 3 of 3 (both detectors), Gemini 1 of 3 and
ChatGPT 1 of 6 (B-Free only), AI-inpainted 0 of 6, forwarded AI fakes 2 of 4.

**Why this pair:** B-Free separates AI fakes from genuine photos best and was trained on inpainted
fakes. Community Forensics is weaker on this dataset but raised no false alarm on any genuine
photo, so it cannot push honest claims into review; the fusion model weights it by its usefulness.
SigLIP was rejected for flagging a third of genuine photos (AUC below 0.5); UniversalFakeDetect for
weak separation.

**Lower threshold (0.2, tuning):** B-Free catches 18 of 33 (from 14) but flags 7 of 59 genuine
photos (from 2). The final thresholds are set on the fusion score, not per detector.

Full tables: `evaluation/results/detector_comparison_tuning.md` and `detector_comparison_test.md`.
Per-image scores: `evaluation/results/ai_scores_all.csv`. Script: `evaluation/detector_comparison.py`.

## Timing (E4.4, CPU)

| Step | Time |
|---|---|
| Loading both AI models (once, at first use) | about 13 s |
| Both AI detectors, per photo | about 3.2–4 s |
| All modules together (forensics, JPEG, AI), per photo | about 8–9 s |

Call `ai_detector.warm_up()` at backend startup to avoid the first-claim delay.

## Reviewer reasons (E5.4)

A detector adds a reason when its score is 0.5 or higher:

- Community Forensics: "This photo may be fully AI-generated (x%)"
- B-Free: "Parts of this photo may have been created or altered with AI (x%)"

## Tests

From the `backend` folder:

```powershell
python test_ai_detector.py <photo.jpg>             # AI module: contract checks and timing
python test_contract.py <photo.jpg>                # every detection module against the contract
```

## Known limitations

- Newest commercial generators are mostly missed (ChatGPT 1 of 10 across both splits).
- AI-inpainted photos are hard: the painted area is about 10% of a small photo, so most of the
  image is genuinely real. None was caught at 0.5 on the test split.
- The dataset is small (22 AI fakes in the test split), so each image moves the rates a lot.
- Public genuine photos are "assumed real"; their history can't be verified.