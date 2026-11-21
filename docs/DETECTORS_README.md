# Claim-Checker: AI-Image Detector Setup (M1, Day 1)

Owner: M1 (Detection engineer) · Epics: E3 JPEG artifact analysis, E4 AI-generated detection
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

## 5. First results (Day 1, CPU)

These are smoke-test results, not an evaluation. Single images say little about accuracy.

| Image | Source | UFD | Community Forensics | B-Free | SigLIP |
|---|---|---|---|---|---|
| real.jpg | Genuine photo | 0.0006 | _fill in_ | _fill in_ | 0.0002 |
| ai.jpg | AI-generated | 0.0118 | _fill in_ | _fill in_ | 0.0006 |
| ai2.png | AI-generated | 0.3102 | 0.0292 | _fill in_ | 0.0004 |

Per-source test (3–5 images per generator, saved directly from the tool):

| Generator | # images | UFD caught | Community Forensics caught | B-Free caught | SigLIP caught |
|---|---|---|---|---|---|
| ChatGPT | | | | | |
| Gemini | | | | | |
| Stable Diffusion | | | | | |
| Genuine (false flags) | | | | | |

Timing on the VM (CPU):

| Model | Load time (once) | Time per image |
|---|---|---|
| UniversalFakeDetect | 12.7 s | 0.54 s |
| Community Forensics | 2.8 s | 0.21 s |
| B-Free | _fill in_ | _fill in_ |
| SigLIP | 4.6 s | 0.28 s |

### What this means
- Detectors learn the fingerprints of the generators in their training data. Newer commercial
  generators (current ChatGPT and Gemini image models) are often not covered, so their images
  can be scored as real.
- A 2026 zero-shot benchmark of open detectors (arXiv 2602.07814) ranked Community Forensics best
  overall, including on GPT-4o, Nano Banana (Gemini) and Stable Diffusion test sets. It also found
  that the newest commercial generators defeat most detectors, so misses are expected.
- B-Free is included because it was trained on **inpainted** fakes and is designed to survive
  compression, which matches our AI-inpainted and WhatsApp-forwarded categories.
- This supports the system design: edit forensics (branch A) and human review cover what the AI
  detectors miss. Limitations will be reported in the report.

---

## 6. Decisions for the team

1. **Detector candidates (E4.1/E4.2).** Replace the plan's NYUAD/SigLIP candidates with
   Community Forensics and B-Free, keeping UFD as baseline. The best 2 are still chosen on Day 3
   from the tuning split. Still within scope: pretrained only, no training.
2. **Contract: two AI scores.** The AI module produces two detector probabilities, but the
   contract has one `score`. Options:
   - (a) Two module results, e.g. `ai_det1` and `ai_det2`, each with its own score (simplest for fusion), or
   - (b) One `ai_detection` result with per-model scores in `artifacts.model_scores`.
   Proposed: **(a)**.
3. **Optional provenance flag (new idea).** Read C2PA "Content Credentials" metadata: ChatGPT and
   newer Gemini images often carry it. If present, it is near-proof of AI generation; if absent it
   proves nothing (screenshots and WhatsApp strip it). Proposed as an extra flag, not a fusion feature.
4. **Dataset format.** AI images from generators often come as PNG. Convert to JPEG for the
   dataset (plan requires JPEG), and save directly from the tool, not via screenshots.

---

## 7. Harmless warnings you will see

- `torch.jit.load is deprecated`: from CLIP, safe to ignore.
- `unauthenticated requests to the HF Hub` / `HF_TOKEN`: optional, only affects download speed.
- Hugging Face `symlinks` warnings: Windows VM limitation, uses slightly more disk.
- SigLIP `bos_token_id` / `eos_token_id` notices: safe to ignore.

---

## 8. Next steps (M1)

- **Day 2 (E1.4):** generate 30 AI images (10 each from ChatGPT, Gemini, Stable Diffusion) with
  claim-like prompts, plus 15 AI-inpainted real photos on Colab. Save as JPEG, record the generator
  and source photo in `manifest.csv`.
- **Day 3 (E4.2, E3.1):** run all candidates on the tuning split, report results per generator,
  choose the best 2. Start the JPEG quality estimate.
- **Day 4 (E4.3, E4.4, E3.2, E3.3):** wrap the chosen detectors as one module returning the contract
  JSON, measure CPU time, build the double-compression check.

  M3:
  DAY 2:
  “Run the backend” section (PostgreSQL database claim_checker, copy .env.example to .env, pip install -r requirements.txt, uvicorn app.main:app --reload), and add the extra results fields to the contract
