# Claim Checker: Insurance Claim Photo Manipulation Detection

Checks each photo uploaded with an insurance claim and gives it a risk score for image manipulation, using two checks:

1. **Edit forensics:** ELA, noise analysis, copy-move detection and JPEG artifact analysis
2. **AI-generated image detection:** pretrained CLIP-based and ViT/SigLIP-based detectors

A logistic regression model combines the scores into one risk score (low / medium / high). A human reviewer makes every final decision.

---

## Repository structure

```
claim-checker/
├── backend/
│   ├── app/
│   │   ├── main.py            FastAPI app and routes
│   │   ├── database.py        Database connection
│   │   ├── models.py          Database tables
│   │   ├── pipeline.py        Runs all modules and the fusion model
│   │   └── modules/           ALL detection module code goes here
│   │       ├── forensics.py
│   │       ├── jpeg_artifacts.py
│   │       └── ai_detector.py
│   └── test_stubs.py          Quick test for the modules
├── frontend/                  React app
├── notebooks/                 Experiments only, not used by the app
└── README.md
```

Module code must live in `backend/app/modules/`. Other folders are for notebooks, scripts, docs and reports, not for code the app runs.

---

## Getting started

Requirements: Python 3.10+, Node.js 18+, Git.

```bash
git clone https://github.com/a1n2n3a4biju/claim-checker.git
cd claim-checker
git checkout -b <your-branch>
git push -u origin <your-branch>
```

### Test the detection modules

Put any JPEG photo in `backend/` as `test.jpg`, then:

```bash
cd backend
pip install pillow
python test_stubs.py
```

You should see a result for every module and heatmap images in `backend/results/`.

The current module files are **stubs**: they return random scores in the agreed format. Replace the body of your own module with real code, keeping the function name and output format exactly the same.

---

## Team workflow

Each member works on their own branch and merges working code into `main` at least once a day.

**Start of day** (get everyone's latest work):

```bash
git checkout main
git pull
git checkout <your-branch>
git merge main
```

**During the day:**

```bash
git add .
git commit -m "Short description of what changed"
git push
```

**Merge into main:** open a pull request on GitHub, or run `git checkout main`, `git merge <your-branch>`, `git push`, then switch back to your branch.

### Rules

- Only edit your own module file. Ask before editing `pipeline.py`.
- Never commit images, model weights, the database or `results/` (they are in `.gitignore`).
- Pull before you start working each day.

---

## Dataset

The dataset is in the team's shared Google Drive folder, not in this repository.

Genuine photos come from the **Car Parts and Car Damages** dataset by Humans in the Loop (CC0 1.0 licence). All fakes are made from these photos.

### Folders

| Folder | Label | Contents |
|---|---|---|
| `genuine` | real | Clear genuine photos |
| `hard_genuine` | real | Darker, blurrier or lower-quality genuine photos |
| `forwarded_genuine` | real | Genuine photos resized and recompressed to simulate WhatsApp |
| `Scripted_edits` | fake | Copy-move and splice edits made by script |
| `careful_manual_edits` | fake | Edits made by hand in GIMP |
| `ai` | fake | Fully AI-generated images |
| `ai_inpaint` | fake | Genuine photos with AI-added damage |
| `forwarded_fake` | fake | Edited and AI images, resized and recompressed |
| `masks` | – | One mask per edited image (white = edited area) |

Donor photos for splices are in a separate `donors` folder **outside** the dataset.

### File naming rules

The manifest is built automatically from file names, so follow these exactly.

| Example | Meaning |
|---|---|
| `P_014.jpg` | Original genuine photo P_014 |
| `FW_P_014.jpg` | P_014, forwarded |
| `CM_P_014.jpg` | Copy-move edit made from P_014 |
| `SP_P_014__D_007.jpg` | Splice into P_014 using donor D_007 |
| `ME_P_020.jpg` | Manual edit of P_020 |
| `AI_SD_003.jpg` | AI image from Stable Diffusion (`AI_GPT_`, `AI_GEM_` for ChatGPT, Gemini) |
| `IN_P_030.jpg` | AI damage inpainted into P_030 |
| `D_007.jpg` | Donor photo (not in the dataset) |

- Always keep the original's full ID (`P_014`) in the name.
- Use `__` (double underscore) only before a donor ID.
- All images are `.jpg` (lowercase). Masks are `.png` with the same name as the edit.
- No spaces in folder or file names.

### Forwarding

Forwarded images are made by script: resize so the longest side is at most 1600 pixels, then save as JPEG at quality 75. Use the same settings for `forwarded_fake`.

---

## Contract (do not change without telling the team)

### 1. Detection modules

Every module is one Python file in `backend/app/modules/` with one function:

```python
def analyze(image_path: str, out_dir: str) -> dict | list[dict]
```

| File | Module names | Returns |
|---|---|---|
| `forensics.py` | `"ela"`, `"noise"`, `"copy_move"` | list of 3 dicts |
| `jpeg_artifacts.py` | `"jpeg"` | 1 dict |
| `ai_detector.py` | `"ai_detector_1"`, `"ai_detector_2"` | list of 2 dicts |

Each dict looks like this:

```json
{
  "module": "ela",
  "score": 0.72,
  "flags": ["Unusual error level near the rear bumper"],
  "artifacts": {"heatmap_path": "results/31_ela.png"}
}
```

Rules:

- `score` is between 0 and 1: 0 = looks genuine, 1 = looks manipulated
- `flags` are plain-English sentences for the reviewer (empty list if nothing found)
- Heatmaps are saved as PNG in `out_dir`, named `<image_id>_<module>.png`
- `artifacts` is `{}` if the module makes no image (e.g. AI detector)
- If something fails, raise an error; don't return a fake score
- Paths in `artifacts` use forward slashes (use `Path.as_posix()`)
- All module code lives in `backend/app/modules/`

### 2. Results API (backend → React)

`GET /claims/{id}/results` returns:

```json
{
  "claim_id": 12,
  "overall_risk": "medium",
  "risk_score": 0.54,
  "reasons": ["Possible edited region near the rear bumper"],
  "images": [
    {
      "image_id": 31,
      "url": "/uploads/31.jpg",
      "risk_score": 0.54,
      "modules": [
        {"module": "ela", "score": 0.71, "flags": ["..."], "artifacts": {"heatmap_url": "/results/31_ela.png"}},
        {"module": "ai_detector_1", "score": 0.12, "flags": [], "artifacts": {}}
      ]
    }
  ]
}
```

- `overall_risk` is `"low"`, `"medium"` or `"high"`
- A claim's risk is the highest risk among its photos
- The backend turns `heatmap_path` into `heatmap_url` so React can show it
