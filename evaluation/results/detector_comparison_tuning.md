# AI detector comparison (E4.2)

Scope: tuning split. Flag threshold: 0.5. Generated 2026-11-23.

| Group | n | UniversalFakeDetect | Community Forensics | B-Free | SigLIP |
|---|---|---|---|---|---|
| **AI fakes (should be caught)** | | | | | |
| Fully AI: ChatGPT | 5 | 0 of 5 | 0 of 5 | 0 of 5 | 0 of 5 |
| Fully AI: Gemini | 7 | 0 of 7 | 0 of 7 | 3 of 7 | 2 of 7 |
| Fully AI: Stable Diffusion | 6 | 1 of 6 | 4 of 6 | 6 of 6 | 1 of 6 |
| AI-inpainted | 9 | 1 of 9 | 0 of 9 | 1 of 9 | 4 of 9 |
| Forwarded AI fakes | 6 | 0 of 6 | 0 of 6 | 1 of 6 | 1 of 6 |
| All AI fakes | 33 | 2 of 33 | 4 of 33 | 11 of 33 | 8 of 33 |
| **Genuine photos (any flag is a false positive)** | | | | | |
| Genuine | 30 | 1 of 30 | 0 of 30 | 1 of 30 | 10 of 30 |
| Hard genuine | 9 | 1 of 9 | 0 of 9 | 0 of 9 | 0 of 9 |
| Forwarded genuine | 21 | 1 of 21 | 0 of 21 | 1 of 21 | 10 of 21 |
| All genuine | 60 | 3 of 60 | 0 of 60 | 2 of 60 | 20 of 60 |
| **Edited photos (not the AI detectors' job; for information)** | | | | | |
| Scripted edits | 18 | 1 of 18 | 0 of 18 | 1 of 18 | 7 of 18 |
| Careful manual edits | 6 | 0 of 6 | 1 of 6 | 1 of 6 | 2 of 6 |

## Summary

| Detector | AI fakes caught | Genuine flagged | Forwarded genuine flagged | AUC |
|---|---|---|---|---|
| UniversalFakeDetect | 2 of 33 | 3 of 60 | 1 of 21 | 0.545 |
| Community Forensics | 4 of 33 | 0 of 60 | 0 of 21 | 0.548 |
| B-Free | 11 of 33 | 2 of 60 | 1 of 21 | 0.813 |
| SigLIP | 8 of 33 | 20 of 60 | 10 of 21 | 0.324 |

AUC: chance that a random AI fake scores higher than a random genuine photo (1.0 = perfect, 0.5 = no better than guessing). It does not depend on the threshold.

## Chosen detectors

._Detector 1: Community Forensics. Detector 2: B-Free.
B-Free separates AI fakes from genuine photos best (AUC 0.81, 11 of 33 caught, 2 of 60 genuine flagged). Community Forensics is weak on this dataset (AUC 0.55) but raised no false alarms on any genuine photo, including forwarded ones, so it can't push honest claims into review. The fusion model will weight it by how much it helps. SigLIP was rejected: AUC 0.32 (worse than guessing), with 20 of 60 genuine photos and 10 of 21 forwarded genuine photos flagged. UniversalFakeDetect was rejected: AUC 0.55, with 3 false alarms. No detector caught any ChatGPT image (0 of 5), a limitation for the newest commercial generators.