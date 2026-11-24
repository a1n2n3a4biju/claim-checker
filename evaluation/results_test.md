# Evaluation on the TEST split

Images: 78 (38 fake, 40 real). Thresholds: low < 0.45 <= medium < 0.688 <= high.

## Results per category

| Category | Label | Images | Medium or high | High |
|---|---|---|---|---|
| ai | fake | 12 | 7 of 12 (58%) | 5 of 12 (42%) |
| ai_inpaint | fake | 6 | 1 of 6 (17%) | 0 of 6 (0%) |
| edit_manual | fake | 4 | 1 of 4 (25%) | 1 of 4 (25%) |
| edit_script | fake | 12 | 3 of 12 (25%) | 1 of 12 (8%) |
| forwarded_fake | fake | 4 | 2 of 4 (50%) | 2 of 4 (50%) |
| forwarded_genuine | real | 14 | 5 of 14 (36%) | 0 of 14 (0%) |
| genuine | real | 20 | 5 of 20 (25%) | 0 of 20 (0%) |
| hard_genuine | real | 6 | 1 of 6 (17%) | 0 of 6 (0%) |

## Overall

Fusion AUC (fake vs real): **0.57**

## Operating points (precision assumes 5% of claims are fraudulent)

| Flagged as | Fakes caught | Genuine wrongly flagged | Precision |
|---|---|---|---|
| medium or high (sent to a human) | 37% | 28% | 7% |
| high only (fraud team) | 24% | 0% | 100% |

## Each module on the fakes it targets

| Module | Fakes it targets | Fakes | AUC vs all real |
|---|---|---|---|
| ela | copy_move, splice, manual | 16 | 0.42 |
| noise | copy_move, splice, manual | 16 | 0.62 |
| copy_move | copy_move | 8 | 0.78 |
| jpeg | splice | 4 | 0.70 |
| ai_detector_1 | ai_full, ai_inpaint | 22 | 0.55 |
| ai_detector_2 | ai_full, ai_inpaint | 22 | 0.79 |

_Small groups (under about 10 images) give rough numbers; report counts, not just percentages._