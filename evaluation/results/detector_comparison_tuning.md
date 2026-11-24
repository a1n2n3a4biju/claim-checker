# AI detector comparison (E4.2)

Scope: tuning split. Flag threshold: 0.5. Generated 2026-11-24.

| Group | n | UniversalFakeDetect | Community Forensics | B-Free | SigLIP |
|---|---|---|---|---|---|
| **AI fakes (should be caught)** | | | | | |
| Fully AI: ChatGPT | 4 | 0 of 4 | 0 of 4 | 0 of 4 | 0 of 4 |
| Fully AI: Gemini | 7 | 0 of 7 | 0 of 7 | 3 of 7 | 2 of 7 |
| Fully AI: Stable Diffusion | 7 | 0 of 7 | 5 of 7 | 7 of 7 | 1 of 7 |
| AI-inpainted | 9 | 1 of 9 | 0 of 9 | 2 of 9 | 4 of 9 |
| Forwarded AI fakes | 6 | 0 of 6 | 1 of 6 | 2 of 6 | 2 of 6 |
| All AI fakes | 33 | 1 of 33 | 6 of 33 | 14 of 33 | 9 of 33 |
| **Genuine photos (any flag is a false positive)** | | | | | |
| Genuine | 30 | 1 of 30 | 0 of 30 | 1 of 30 | 13 of 30 |
| Hard genuine | 9 | 0 of 9 | 0 of 9 | 0 of 9 | 2 of 9 |
| Forwarded genuine | 21 | 1 of 21 | 0 of 21 | 1 of 21 | 10 of 21 |
| All genuine | 60 | 2 of 60 | 0 of 60 | 2 of 60 | 25 of 60 |
| **Edited photos (not the AI detectors' job; for information)** | | | | | |
| Scripted edits | 18 | 1 of 18 | 0 of 18 | 1 of 18 | 7 of 18 |
| Careful manual edits | 6 | 2 of 6 | 1 of 6 | 1 of 6 | 2 of 6 |

## Summary

| Detector | AI fakes caught | Genuine flagged | Forwarded genuine flagged | AUC |
|---|---|---|---|---|
| UniversalFakeDetect | 1 of 33 | 2 of 60 | 1 of 21 | 0.572 |
| Community Forensics | 6 of 33 | 0 of 60 | 0 of 21 | 0.636 |
| B-Free | 14 of 33 | 2 of 60 | 1 of 21 | 0.857 |
| SigLIP | 9 of 33 | 25 of 60 | 10 of 21 | 0.343 |

AUC: chance that a random AI fake scores higher than a random genuine photo (1.0 = perfect, 0.5 = no better than guessing). It does not depend on the threshold.

## Chosen detectors

_To fill in: the best two, with reasons._