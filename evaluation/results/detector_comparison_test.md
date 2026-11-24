# AI detector comparison (E4.2)

Scope: test split. Flag threshold: 0.5. Generated 2026-11-24.

| Group | n | UniversalFakeDetect | Community Forensics | B-Free | SigLIP |
|---|---|---|---|---|---|
| **AI fakes (should be caught)** | | | | | |
| Fully AI: ChatGPT | 6 | 0 of 6 | 0 of 6 | 1 of 6 | 0 of 6 |
| Fully AI: Gemini | 3 | 0 of 3 | 0 of 3 | 1 of 3 | 1 of 3 |
| Fully AI: Stable Diffusion | 3 | 1 of 3 | 3 of 3 | 3 of 3 | 0 of 3 |
| AI-inpainted | 6 | 0 of 6 | 0 of 6 | 0 of 6 | 2 of 6 |
| Forwarded AI fakes | 4 | 1 of 4 | 2 of 4 | 2 of 4 | 0 of 4 |
| All AI fakes | 22 | 2 of 22 | 5 of 22 | 7 of 22 | 3 of 22 |
| **Genuine photos (any flag is a false positive)** | | | | | |
| Genuine | 20 | 0 of 20 | 0 of 20 | 0 of 20 | 5 of 20 |
| Hard genuine | 6 | 1 of 6 | 0 of 6 | 0 of 6 | 1 of 6 |
| Forwarded genuine | 14 | 0 of 14 | 0 of 14 | 0 of 14 | 5 of 14 |
| All genuine | 40 | 1 of 40 | 0 of 40 | 0 of 40 | 11 of 40 |
| **Edited photos (not the AI detectors' job; for information)** | | | | | |
| Scripted edits | 12 | 0 of 12 | 0 of 12 | 0 of 12 | 3 of 12 |
| Careful manual edits | 4 | 0 of 4 | 0 of 4 | 0 of 4 | 1 of 4 |

## Summary

| Detector | AI fakes caught | Genuine flagged | Forwarded genuine flagged | AUC |
|---|---|---|---|---|
| UniversalFakeDetect | 2 of 22 | 1 of 40 | 0 of 14 | 0.590 |
| Community Forensics | 5 of 22 | 0 of 40 | 0 of 14 | 0.553 |
| B-Free | 7 of 22 | 0 of 40 | 0 of 14 | 0.790 |
| SigLIP | 3 of 22 | 11 of 40 | 5 of 14 | 0.276 |

AUC: chance that a random AI fake scores higher than a random genuine photo (1.0 = perfect, 0.5 = no better than guessing). It does not depend on the threshold.

## Chosen detectors

_To fill in: the best two, with reasons._