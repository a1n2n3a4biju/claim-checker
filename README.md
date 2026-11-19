## Contract (agreed Day 1, do not change without telling the team)

### 1. Detection modules

Every module is one Python file in `backend/app/modules/` with one function:

    def analyze(image_path: str, out_dir: str) -> dict

| File | Owner | module name |
|---|---|---|
| forensics.py | M2 | "ela", "noise", "copy_move" (returns a list of 3 dicts) |
| jpeg_artifacts.py | M3 | "jpeg" |
| ai_detector.py | M1 | "ai_detector_1", "ai_detector_2" (returns a list of 2 dicts) |

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

- `overall_risk` is "low", "medium" or "high"
- A claim's risk is the highest risk among its photos
- The backend turns `heatmap_path` into `heatmap_url` so React can show it
