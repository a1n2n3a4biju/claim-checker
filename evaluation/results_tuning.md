# Evaluation on the TUNING split
_Dry run on tuning data: optimistic, NOT the final result._

Images: 117 (57 fake, 60 real). Thresholds: low < 0.335 <= medium < 0.642 <= high.

## Results per category

| Category | Label | Images | Medium or high | High |
|---|---|---|---|---|
| ai | fake | 18 | 16 of 18 (89%) | 10 of 18 (56%) |
| ai_inpaint | fake | 9 | 8 of 9 (89%) | 2 of 9 (22%) |
| edit_manual | fake | 6 | 6 of 6 (100%) | 2 of 6 (33%) |
| edit_script | fake | 18 | 16 of 18 (89%) | 3 of 18 (17%) |
| forwarded_fake | fake | 6 | 5 of 6 (83%) | 2 of 6 (33%) |
| forwarded_genuine | real | 21 | 18 of 21 (86%) | 1 of 21 (5%) |
| genuine | real | 30 | 26 of 30 (87%) | 2 of 30 (7%) |
| hard_genuine | real | 9 | 8 of 9 (89%) | 0 of 9 (0%) |

## Overall

Fusion AUC (fake vs real): **0.68**

## Operating points (precision assumes 5% of claims are fraudulent)

| Flagged as | Fakes caught | Genuine wrongly flagged | Precision |
|---|---|---|---|
| medium or high (sent to a human) | 89% | 87% | 5% |
| high only (fraud team) | 33% | 5% | 26% |

## Each module on the fakes it targets

| Module | Fakes it targets | Fakes | AUC vs all real |
|---|---|---|---|
| ela | copy_move, splice, manual | 24 | 0.43 |
| noise | copy_move, splice, manual | 24 | 0.55 |
| copy_move | copy_move | 8 | 0.35 |
| jpeg | splice | 10 | 0.63 |
| ai_detector_1 | ai_full, ai_inpaint | 33 | 0.55 |
| ai_detector_2 | ai_full, ai_inpaint | 33 | 0.81 |

_Small groups (under about 10 images) give rough numbers; report counts, not just percentages._