# AI detector comparison (E4.2)

Scope: all images (no split applied). Flag threshold: 0.5. Generated 2026-11-23.

| Group | n | UniversalFakeDetect | Community Forensics | B-Free | SigLIP |
|---|---|---|---|---|---|
| **AI fakes (should be caught)** | | | | | |
| Fully AI: ChatGPT | 10 | 0 of 10 | 0 of 10 | 1 of 10 | 0 of 10 |
| Fully AI: Gemini | 10 | 0 of 10 | 0 of 10 | 4 of 10 | 3 of 10 |
| Fully AI: Stable Diffusion | 10 | 1 of 10 | 8 of 10 | 10 of 10 | 1 of 10 |
| AI-inpainted | 15 | 1 of 15 | 0 of 15 | 2 of 15 | 6 of 15 |
| Forwarded AI fakes | 10 | 1 of 10 | 3 of 10 | 4 of 10 | 2 of 10 |
| All AI fakes | 55 | 3 of 55 | 11 of 55 | 21 of 55 | 12 of 55 |
| **Genuine photos (any flag is a false positive)** | | | | | |
| Genuine | 50 | 1 of 50 | 0 of 50 | 1 of 50 | 18 of 50 |
| Hard genuine | 15 | 1 of 15 | 0 of 15 | 0 of 15 | 3 of 15 |
| Forwarded genuine | 35 | 1 of 35 | 0 of 35 | 1 of 35 | 15 of 35 |
| All genuine | 100 | 3 of 100 | 0 of 100 | 2 of 100 | 36 of 100 |
| **Edited photos (not the AI detectors' job; for information)** | | | | | |
| Scripted edits | 30 | 1 of 30 | 0 of 30 | 1 of 30 | 10 of 30 |
| Careful manual edits | 10 | 2 of 10 | 1 of 10 | 1 of 10 | 3 of 10 |

## Summary

| Detector | AI fakes caught | Genuine flagged | Forwarded genuine flagged | AUC |
|---|---|---|---|---|
| UniversalFakeDetect | 3 of 55 | 3 of 100 | 1 of 35 | 0.572 |
| Community Forensics | 11 of 55 | 0 of 100 | 0 of 35 | 0.596 |
| B-Free | 21 of 55 | 2 of 100 | 1 of 35 | 0.827 |
| SigLIP | 12 of 55 | 36 of 100 | 15 of 35 | 0.317 |

AUC: chance that a random AI fake scores higher than a random genuine photo (1.0 = perfect, 0.5 = no better than guessing). It does not depend on the threshold.

## Chosen detectors

_To fill in: the best two, with reasons._