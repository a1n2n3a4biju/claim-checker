# ClaimProof v2: what changed

Everything that was added or changed while turning ClaimProof v1 (a photo checker) into v2 (a
claims workflow with three roles), in the order it was done.

Before merging, note that the team's rule is that only a
file's owner (M1, M2 or M3) edits it, so send each member their part to review.

The complete list of added, changed, deleted and unchanged files is in
[Every file compared with the starting point](#every-file-compared-with-the-starting-point) near the end.

For how to run it, see [SETUP_GUIDE.md](SETUP_GUIDE.md). For how the new code works, see
[CODE_GUIDE.md](CODE_GUIDE.md).

---

## Summary

| Area | Before (v1) | After (v2) |
|---|---|---|
| Users | No accounts: anyone could submit a claim; reviewers signed in with a name from `REVIEWER_NAMES` and one shared password | User accounts in the database with three roles: claimant, assessor, insurer. Customers can create an account. |
| Passwords | One shared reviewer password in `.env` | Each user's own password, stored only as a bcrypt hash |
| Claims | Name, date, description, photos and a tracking code; a reviewer recorded a verdict (`verdicts` table) | A claim belongs to a policy and vehicle, and moves through 8 statuses from submission to settlement, each move recorded |
| Photo checks | In `main.py`, run by calling `POST /claims/{id}/analyze` | Same checks and thresholds, moved to `photo_checks.py`, run automatically in the background after upload |
| Assessors | – | Claims are routed automatically to the least busy assessor, who writes a parts-and-labour quotation |
| Insurer | – | Reviews, asks for more information, decides (approve / reject / further review) and settles, with a suggested payout |
| Claimants | Followed a claim with a tracking code (`/track`) | Sign in to see their claims, with friendly status labels; never see risk scores, levels, heatmaps, reasons or fraud flags |
| Photo viewer | `EvidenceViewer`: a slider to wipe between the photo and one heatmap | `PhotoViewer`: zoom, pan, reset, heatmap overlay with a transparency slider, open full size |
| Database | `claim_checker` (per v1's `.env.example`), 4 tables | New database `claimproof_v2`, 9 tables (v1 data kept) |
| Demo data | – | Seed script: 30 claimants, 1 assessor, 1 insurer, 48 claims, made through the real workflow |

**Unchanged:** the detection modules in `backend/app/modules/`, the fusion model
(`backend/fusion/fusion_model.joblib`) and its thresholds (0.45 / 0.688), so the v1 evaluation
results still hold.

---

## Step 1: M2's own part (routing, price list, checklist)

The first pass added only the files the document gives to M2:

| File | What it is |
|---|---|
| `backend/app/routing.py` (new) | `route_claim(risk_level, assessors)`: sets the fraud flag for high risk and picks the assessor with the fewest open claims (lower id on a tie). No database code. Raises `ValueError` for an unknown risk level or no assessors. |
| `tests/test_routing.py` (new) | 9 unit tests for the routing rules, using Python's built-in `unittest`. |
| `data/price_list.json` (new) | 18 parts and labour items in whole rupees, used by the assessor's quotation form. The first four come from the document; the rest are typical garage rates to be checked by the team. |
| `tests/e2e_checklist.md` (new) | A pass/fail checklist for the running app: seeded data, sign-in, each role's journey, the access rules (403/409), formats, and that the photo checks are unchanged. |

---

## Step 2: the code for all three members

### Backend (M3's part)

| File | Change |
|---|---|
| `backend/app/models.py` | Rewritten: nine tables (`users`, `policies`, `vehicles`, `claims`, `images`, `analysis_results`, `quotations`, `quotation_items`, `status_history`). |
| `backend/app/database.py` | Reads `DATABASE_URL` from `backend/.env`; works with PostgreSQL and SQLite. |
| `backend/app/auth.py` (new) | bcrypt password hashing, signed sign-in tokens (8 hours), "must be signed in" and "must have this role" checks. |
| `backend/app/workflow.py` (new) | The status engine: allows only the agreed moves (otherwise 409), checks who may make each move (otherwise 403), and records every move in `status_history`. Also all the actions: create claim, upload photos, run checks and route, quotation, review, info request, reply, decision, settle. |
| `backend/app/photo_checks.py` (new) | The v1 photo checks and fusion, moved out of `main.py` unchanged. |
| `backend/app/main.py` | Rewritten: every endpoint in the contract, with separate response shapes for claimants (no risk data) and staff. |
| `backend/.env.example` | `DATABASE_URL` (now `claimproof_v2`), `TOKEN_SECRET`, `DEMO_PASSWORD`. |
| `requirements.txt` | Added `bcrypt` (password hashing) and `httpx` (needed by FastAPI's test client). |

### Demo data (M2's part)

`scripts/seed_demo.py` (new) builds the demo by calling the real workflow functions, never by writing
statuses into tables, so running it also tests the workflow. It creates the `claimproof_v2`
database if it's missing. (Its demo accounts were changed in step 6.)

### Frontend (M1's part)

The v1 pages were replaced by one React app with role-based pages:

| Role | Pages |
|---|---|
| Anyone | Sign in |
| Claimant | My claims, submit a claim (with photo upload), claim details (with reply to an info request), my policies |
| Assessor | Assigned claims, claim view with the quotation form |
| Insurer | Claims queue (filter by status and risk), claim view with the actions |

Also added: `src/api/` (one function per endpoint, plus a filter that strips risk fields from claimant
responses), `src/auth/` (sign-in state that survives a page refresh), `src/mocks/mockServer.js` (a
full mock backend for `VITE_USE_MOCK=true`) and `frontend/.env.example`.

### Docs

`docs/CONTRACT.md` (names, statuses, endpoints and formats), the main `README.md` and
`frontend/README.md`. Choices the document left open are listed at the end of `CONTRACT.md` under
"Implementation notes".

---

## Step 3: fixing the test and requirements errors

The errors (`ArgsKwargs` from pydantic, a DLL error from torch) were not caused by
`requirements.txt`. The `venv` had been created with **Python 3.14**, but the packages in it were
built for **Python 3.12**. The fix was to rebuild the venv with `py -3.12 -m venv venv` and reinstall.
`requirements.txt` was left as it was.

The other error came from running both test commands on one line; they must be run separately:

```powershell
python -m unittest tests/test_routing.py
python tests/test_backend.py
```

---

## Step 4: customer sign-up

| File | Change |
|---|---|
| `backend/app/auth.py` | `register()`: checks name, email (format, not already used) and password (at least 8 characters), saves only the bcrypt hash, and signs the new user in. |
| `backend/app/main.py` | New endpoint `POST /auth/register` (201). |
| `frontend/src/pages/Register.jsx` (new) | "Create an account" form: name, email, password and confirmation, with errors shown next to each field. |
| `frontend/src/pages/Login.jsx` | Link to "Create an account". |
| `frontend/src/App.jsx` | Routes `/` (home) and `/register`; "Sign in" and "Create account" buttons in the header when signed out. |
| `frontend/src/auth/AuthContext.jsx`, `src/api/index.js`, mock server | `register` added. |
| `tests/test_backend.py` | 8 sign-up checks. |
| `docs/CONTRACT.md`, `tests/e2e_checklist.md` (1.7–1.12) | Written up as a **proposed** contract change for the team. |

Decisions:

- Sign-up **always creates a claimant**, even if the request asks for another role. Assessor and
  insurer accounts can see every claim and approve payouts, so only the seed script creates them.
- A new customer has no policy yet, so they can't submit a claim until one is linked to their
  account. Nothing in the app links one yet.

---

## Step 5: the home page

The v1 home page was brought back (`frontend/src/pages/Landing.jsx` and
`frontend/src/components/CoverArt.jsx`, taken from the team's GitHub `main`) with two changes:

- The two cards are now **"Create a new account"** (new customers) and **"Sign in"** (existing
  customers and staff).
- A signed-in user sees "Welcome back, *name*" with a button to their home page instead.

The v1 "Check its status" tracking-code link was removed, since v2 has no such page, and the step
"You get a claim number and a tracking code" now reads "You can follow your claim from your account".

---

## Step 6: claim history, payout breakdown, zoom viewer and new demo accounts

This step implemented the team message about claim history and payout, the zoom viewer and demo
logins, and changed the demo data to 30 claimants, 1 assessor and 1 insurer.

### 6.1 Claim history and payout breakdown

| File | Change |
|---|---|
| `backend/app/workflow.py` | New `recent_approved_claims()`, `payout_breakdown()` and `rupees()`. `suggested_payout()` now uses the breakdown and takes `db` as its first argument. |
| `backend/app/main.py` | Assessor and insurer views: `previous_claims` now has `approved_amount`, plus a new `recent_approved_claims` list. Insurer view: new `payout_breakdown` object, and `suggested_payout` taken from it. |
| `frontend/src/pages/insurer/InsurerClaim.jsx` | New **Payout** box: quotation total, minus deductible, after deductible, claim-history deduction, suggested payout and a one-sentence explanation. |
| `frontend/src/pages/insurer/ClaimActions.jsx` | The approve amount is pre-filled with `suggested_payout`. |
| `frontend/src/components/StaffClaim.jsx` | The previous-claims table shows the approved amounts, highlights claims from the last 12 months and adds a line such as "2 approved claims in the 12 months before this incident, ₹X paid in total". |
| `frontend/src/pages/assessor/AssessorClaim.jsx` | Passes the recent claims to that table too. |

**The payout rule** (the message named the fields but gave no numbers, so these need the team's
confirmation; they are constants at the top of the payout code in `workflow.py`):

```
after deductible  = max(0, quotation total − deductible)
history rate      = 5% for each approved claim by this claimant in the 12 months
                    before this incident, at most 20%
history deduction = after deductible × history rate (rounded to whole rupees)
suggested payout  = min(after deductible − history deduction, sum insured), never below 0
```

Example: quotation ₹10,900, deductible ₹2,000, one recent approved claim → ₹8,900 − 5% (₹445) =
**₹8,455**.

It is only a suggestion: the insurer can change the amount before approving.

### 6.2 "Further review" replaces "fraud review"

| File | Change |
|---|---|
| `backend/app/workflow.py`, `main.py`, `models.py` | The third decision outcome is now `further_review`. The old value `fraud_review` is refused (422). A claim in further review can't be settled (409). |
| `frontend/src/utils/status.js` | Staff label: "Further review". |
| `frontend/src/pages/insurer/ClaimActions.jsx` | Button "Send for further review". |
| `frontend/src/pages/claimant/ClaimDetails.jsx` | Claimant label: "Needs further review". The claimant never sees anything about fraud or risk. |

### 6.3 Zoomable photo viewer

| File | Change |
|---|---|
| `frontend/src/components/PhotoViewer.jsx` (new) | Zoom (buttons, mouse wheel, pinch, double-click, up to 800%), drag to pan, Reset, a heatmap overlay with a transparency slider and a choice of which check's heatmap, "Open full size" and "Heatmap" links. |
| `frontend/src/components/EvidenceViewer.jsx` | Deleted (replaced by `PhotoViewer`). |
| `frontend/package.json` | Added `react-zoom-pan-pinch` 3.7.0 (exact version). |

Used on the assessor and insurer pages only. No backend change.

### 6.4 Demo data: 30 claimants, 1 assessor, 1 insurer

`scripts/seed_demo.py` was rewritten:

- **Accounts:** `claimant1` to `claimant30@demo.in`, `assessor1@demo.in` (Suresh Babu) and
  `insurer1@demo.in` (Priya Menon), all with `DEMO_PASSWORD`.
- **Policies:** one policy and one vehicle per claimant.
- **Claim history:** claimants 1–16 have earlier approved and settled claims (1–10: one, 11–14: two,
  15–16: four), so their current claims show 5%, 10% and 20% deductions.
- **Other cases:** AI photo (17), copy-move edit (18), awaiting assessment (19), more information
  requested (20), further review (21), settled (22), claim refused because the policy had ended (23).
  Claimants 24–30 have no claims, for live demos.
- **Photos:** each photo is used only once, because the same photo uploaded twice is flagged as a
  duplicate.
- At the end, a summary shows each claim's risk, status, payout and history percentage, and marks
  anything unexpected with `CHECK`.

The mock server (`frontend/src/mocks/mockServer.js`) and the demo list on the sign-in page were
changed to the same accounts.

### 6.5 Tests and docs

- `tests/test_backend.py`: a new "claim history and payout breakdown" section (breakdown values and
  explanation, the 12-month window, the 20% cap, `further_review`, the old `fraud_review` refused,
  and claimant responses never containing history or payout fields). Result: all **77** checks pass
  (65 before this step).
- `docs/CONTRACT.md`: `further_review`, an insurer response example with `payout_breakdown`, the
  payout rule, the new demo accounts.
- `README.md`, `frontend/README.md`: new accounts table, viewer and payout notes.
- `tests/e2e_checklist.md`: new accounts, payout checks (2.4.3, 2.4.3a, 2.4.3b, 2.4.6a), a new photo
  viewer section (2.7).

---

## Step 7: these documents

- `docs/SETUP_GUIDE.md`: how to run it from any starting point.
- `docs/CHANGES.md`: this file.
- `docs/CODE_GUIDE.md`: how the new code works.

---

## Every file compared with the starting point

The starting point is the team repository's `main` branch at commit **`043e7b7`** (26 Nov 2026,
"Correct tuning per-category results from the official scores and frozen model"), which is what this
work began from. Every file tracked by Git was compared with it, byte for byte (ignoring Windows/Unix
line endings).

| | Files |
|---|---|
| Added | 36 |
| Changed | 15 |
| Deleted | 11 |
| Unchanged | 99 |

Not included: files Git ignores, such as `backend/.env`, `frontend/.env`, `frontend/.env.local`,
`venv/`, `node_modules/`, `weights/`, `data/images/`, `backend/uploads/` and `backend/results/`.

### Added (36)

**Backend (4)**

| File | Step | What it does |
|---|---|---|
| `backend/app/auth.py` | 2, 4 | bcrypt password hashing and checking, signed 8-hour sign-in tokens, "signed in" and "has this role" checks, sign-up and sign-in |
| `backend/app/workflow.py` | 2, 6 | Status engine (allowed moves, who may make them, history rows) and every claim action; claim history and payout breakdown |
| `backend/app/photo_checks.py` | 2 | The v1 photo checks and fusion, moved out of `main.py` without changing how they work |
| `backend/app/routing.py` | 1 | Picks the assessor with the fewest open claims and sets the fraud flag for high risk |

**Data, scripts and tests (5)**

| File | Step | What it does |
|---|---|---|
| `data/price_list.json` | 1 | 18 parts and labour prices for the assessor's quotation form |
| `scripts/seed_demo.py` | 2, 6 | Builds the demo (32 accounts, 30 policies, 48 claims) through the real workflow |
| `tests/test_routing.py` | 1 | 9 unit tests for the routing rules |
| `tests/test_backend.py` | 2, 4, 6 | 77 API checks on a temporary SQLite database: journeys, 403/409 rules, sign-up, payout, no risk data for claimants |
| `tests/e2e_checklist.md` | 1, 4, 6 | Manual pass/fail checklist for the running app |

**Docs (4)**

| File | Step | What it is |
|---|---|---|
| `docs/CONTRACT.md` | 2, 4, 6 | The shared contract: roles, statuses, allowed moves, endpoints, response shapes, demo accounts, open choices |
| `docs/SETUP_GUIDE.md` | 7 | How to run it from any starting point |
| `docs/CHANGES.md` | 7 | This file |
| `docs/CODE_GUIDE.md` | 7 | How the new code works |

**Frontend: data and sign-in (4)**

| File | Step | What it does |
|---|---|---|
| `frontend/src/api/client.js` | 2 | axios set-up: adds the token to every request, turns errors into readable messages, signs the user out on a 401; `assetUrl` for photos and heatmaps |
| `frontend/src/api/index.js` | 2, 4, 6 | One function per endpoint; switches to the mock in mock mode; strips risk fields from claimant responses |
| `frontend/src/mocks/mockServer.js` | 2, 4, 6 | A complete stand-in backend for `VITE_USE_MOCK=true`, with the same accounts, rules and payout formula |
| `frontend/src/utils/useLoad.js` | 2 | Hook that loads a page's data and gives `data`, `error`, `loading`, `reload`, `setData` |

**Frontend: shared components (5)**

| File | Step | What it does |
|---|---|---|
| `frontend/src/components/shared.jsx` | 2 | Small pieces used everywhere: status badge, risk badge, timeline, error box, loading spinner, empty-list message, page title, section, facts list |
| `frontend/src/components/RequireRole.jsx` | 2 | Protects pages by role: not signed in → sign-in page; wrong role → "You don't have access to this" |
| `frontend/src/components/PhotoPicker.jsx` | 2 | JPEG chooser with previews (up to 10 photos, 10 MB each), used to submit a claim and to reply with photos |
| `frontend/src/components/StaffClaim.jsx` | 2, 6 | Staff-only pieces: risk summary, photos with check results, claim facts, previous claims (with approved amounts and recent claims), quotation table |
| `frontend/src/components/PhotoViewer.jsx` | 6 | Zoom, pan, reset, heatmap overlay with transparency slider, open full size |

**Frontend: utilities (2)**

| File | Step | What it does |
|---|---|---|
| `frontend/src/utils/format.js` | 2 | Date and money formatting (whole rupees as `₹45,000`) |
| `frontend/src/utils/status.js` | 2, 6 | Status labels for staff and claimants, decision labels |

**Frontend: pages (12)**

| File | Step | Who | What it shows |
|---|---|---|---|
| `frontend/src/pages/Login.jsx` | 2, 4, 6 | Anyone | Sign-in form, link to sign-up, list of demo accounts |
| `frontend/src/pages/Register.jsx` | 4 | Anyone | "Create an account" form |
| `frontend/src/pages/claimant/MyClaims.jsx` | 2 | Claimant | List of their claims with friendly status labels |
| `frontend/src/pages/claimant/SubmitClaim.jsx` | 2 | Claimant | Claim form (vehicle, date, time, place, severity, description), then photo upload with a progress bar |
| `frontend/src/pages/claimant/ClaimDetails.jsx` | 2, 6 | Claimant | One claim: timeline, decision ("Needs further review" etc.), reply form when more information is asked for |
| `frontend/src/pages/claimant/Dashboard.jsx` | 2 | Claimant | "My policies": policies and vehicles |
| `frontend/src/pages/assessor/AssignedClaims.jsx` | 2 | Assessor | Claims assigned to them |
| `frontend/src/pages/assessor/AssessorClaim.jsx` | 2, 6 | Assessor | One claim with risk, photos (zoom viewer), previous claims and the quotation form |
| `frontend/src/pages/assessor/QuotationForm.jsx` | 2 | Assessor | Parts and labour rows from the price list, live total, note |
| `frontend/src/pages/insurer/ClaimsQueue.jsx` | 2 | Insurer | All claims, filterable by status and risk |
| `frontend/src/pages/insurer/InsurerClaim.jsx` | 2, 6 | Insurer | One claim with everything, including the payout breakdown |
| `frontend/src/pages/insurer/ClaimActions.jsx` | 2, 6 | Insurer | The buttons allowed for the current status; approve amount pre-filled with the suggested payout |

### Changed (15)

| File | Step | Before | Now |
|---|---|---|---|
| `README.md` | 2, 6, 7 | v1 project README | New v2 sections at the top (roles, status flow, setup, demo accounts, tests, file owners, links to these docs); the v1 sections are kept below |
| `requirements.txt` | 2 | v1 packages | `bcrypt` and `httpx` added. The file is still saved as UTF-16, as before |
| `backend/.env.example` | 2 | `DATABASE_URL` (database `claim_checker`), `REVIEWER_NAMES`, `REVIEWER_PASSWORD`, `TOKEN_SECRET` | `DATABASE_URL` (database `claimproof_v2`), `TOKEN_SECRET`, `DEMO_PASSWORD`, with comments |
| `backend/app/database.py` | 2 | Read `.env` from the folder the program was started in | Always reads `backend/.env`; also works with SQLite (for the tests) |
| `backend/app/models.py` | 2, 6 | 4 tables: `claims` (name, date, description, tracking code), `images`, `analysis_results`, `verdicts` | 9 tables: `users`, `policies`, `vehicles`, `claims`, `images`, `analysis_results`, `quotations`, `quotation_items`, `status_history`. `verdicts` is gone: the decision is stored on the claim |
| `backend/app/main.py` | 2, 4, 6 | Reviewer sign-in by name, tracking codes, `/claims`, `/claims/{id}/analyze`, `/results`, `PATCH /decision`, `/review-queue`, and the photo-check code | Rewritten: all v2 endpoints, separate claimant and staff responses, payout breakdown; photo checks moved to `photo_checks.py` |
| `frontend/.env.example` | 2 | Same two settings | Wording of the comments only |
| `frontend/README.md` | 2, 4, 6 | v1 frontend README | Rewritten for v2: pages per role, set-up, mock mode, structure, troubleshooting |
| `frontend/package.json` | 6 | – | `react-zoom-pan-pinch` 3.7.0 added (nothing else changed) |
| `frontend/package-lock.json` | 6 | – | Updated by `npm install` for that package |
| `frontend/src/App.jsx` | 2, 4 | Public routes `/claims/new`, `/submitted/:id`, `/track`; reviewer routes `/claims`, `/claims/:id` | Role-based header menus; routes for the home page, sign-up, sign-in and each role's pages, each protected by `RequireRole` |
| `frontend/src/auth/AuthContext.jsx` | 2, 4 | Reviewer name + shared password | Users with roles; sign-in, sign-up, sign-out; restores the user with `GET /me` after a refresh; reacts to a 401 |
| `frontend/src/auth/storage.js` | 2 | Saved the whole reviewer session (name, token, expiry) | Saves only the token; every storage access is protected against blocked storage |
| `frontend/src/pages/Landing.jsx` | 4, 5 | v1 home page: submit a claim, or check its status with a tracking code | Same page and drawing, with "Create a new account" and "Sign in" cards, a "Welcome back" box when signed in, and step 1's wording updated |
| `frontend/src/utils/risk.js` | 2 | Thresholds plus `claimStatus()` (v1's "Fast processing" / "Escalated to fraud team" text) | Thresholds only; `claimStatus()` removed because v2 uses real statuses |

### Deleted (11)

All were v1 frontend files, replaced by the v2 files above.

| File | What it was | Replaced by |
|---|---|---|
| `frontend/src/api/claims.js` | v1 API calls | `src/api/client.js` and `src/api/index.js` |
| `frontend/src/mocks/mockData.js` | v1 sample data | `src/mocks/mockServer.js` |
| `frontend/src/components/RequireReviewer.jsx` | Protected the reviewer pages | `RequireRole.jsx` |
| `frontend/src/components/SignInDialog.jsx` | Reviewer sign-in pop-up | `pages/Login.jsx` |
| `frontend/src/components/ReviewPanel.jsx` | Reviewer's decision form | `pages/insurer/ClaimActions.jsx` |
| `frontend/src/components/EvidenceViewer.jsx` | Photo / heatmap wipe slider (kept in step 2, removed in step 6) | `components/PhotoViewer.jsx` |
| `frontend/src/pages/NewClaim.jsx` | Public claim form | `pages/claimant/SubmitClaim.jsx` |
| `frontend/src/pages/Submitted.jsx` | "Claim received" page with the tracking code | The claim details page |
| `frontend/src/pages/Track.jsx` | Look up a claim by tracking code | `pages/claimant/MyClaims.jsx` and `ClaimDetails.jsx` (claimants now sign in) |
| `frontend/src/pages/ClaimsList.jsx` | Reviewer's claim list | `pages/insurer/ClaimsQueue.jsx` and `pages/assessor/AssignedClaims.jsx` |
| `frontend/src/pages/Results.jsx` | Reviewer's claim results page | `pages/insurer/InsurerClaim.jsx` and `pages/assessor/AssessorClaim.jsx` |

### Unchanged (99)

These are exactly as they were at the starting point.

| Area | Files |
|---|---|
| Repository (1) | `.gitignore` |
| Detection modules (8) | `backend/app/__init__.py`, and in `backend/app/modules/`: `__init__.py`, `ai_detector.py`, `copy_move.py`, `ela.py`, `forensics.py`, `jpeg_artifacts.py`, `noise.py` |
| Fusion (2) | `backend/fusion/fusion_model.joblib`, `fusion/run_all_modules.py` |
| v1 backend tests (5) | In `backend/`: `test_ai_detector.py`, `test_contract.py`, `test_ghost.py`, `test_jpeg.py`, `test_stubs.py` |
| `detection/` package (4) | `detection/__init__.py`, `detection/ai_detection/__init__.py`, `detection/edit_forensics/__init__.py`, `detection/jpeg_artifacts/__init__.py` |
| Data lists (2) | `data/manifest.csv`, `data/split_counts.csv` |
| Docs (1) | `docs/DETECTORS_README.md` |
| Evaluation (35) | `evaluation/detector_comparison.py`, `evaluation/results_test.md`, the 3 images in `evaluation/figures/`, and all 30 files in `evaluation/results/` (detector comparisons and summaries, per-module tables including `modules_summary_test.csv` and `modules_summary_tuning.csv`, per-category and band results, precision at fraud rate) |
| Scripts (16) | In `scripts/`: `align_scores.py`, `build_manifest.py`, `check_leaks.py`, `check_manifest.py`, `evaluate.py`, `evaluate_per_module.py`, `fix_split.py`, `forward.py`, `make_scripted_edits_auto.py`, `plot_results.py`, `precision_at_fraud_rate.py`, `prepare_m2_scores.py`, `run_all.py`, `smoke_test_detectors.py`, `sync_split.py`, `train_fusion.py` |
| Frontend set-up (4) | `frontend/.gitignore`, `frontend/.oxlintrc.json`, `frontend/index.html`, `frontend/vite.config.js` |
| Frontend assets (6) | `frontend/public/favicon.svg`, `frontend/public/icons.svg`, `frontend/public/mock/claim_photo.svg`, and in `frontend/src/assets/`: `hero.png`, `react.svg`, `vite.svg` |
| Frontend code (6) | In `frontend/src/`: `main.jsx`, `index.css`, `theme.js`, `components/CoverArt.jsx` (restored from v1 in step 5, identical), `components/SafeImage.jsx`, `utils/modules.js` |
| Empty-folder markers (9) | `.gitkeep` in `backend/`, `contract/`, `data/`, `evaluation/`, `fusion/`, `notebooks/`, `report/`, `samples/`, `scripts/` |

---

## What has and hasn't been checked

| Check | Result |
|---|---|
| `python -m unittest tests/test_routing.py` | Passes |
| `python tests/test_backend.py` (SQLite, stand-in photo checks) | ALL PASSED, 77 checks |
| Seed dry run on SQLite with the saved scores from `scores.csv` | Matches the plan: 32 users, 30 policies, 48 claims, −5% / −10% / −20% payouts |
| `npm run build` | Builds |
| `npm run lint` | 0 errors (3 older warnings) |
| Seed on PostgreSQL with the real photo checks | **Not run yet** |
| Pages in a browser | **Not checked yet**: use `tests/e2e_checklist.md` |

---

## Open decisions for the team

1. **The history deduction numbers** (5% per claim, 20% maximum, 12 months before the incident).
2. **Customer sign-up** (`POST /auth/register`) is a proposed addition to the contract.
3. **New customers have no policy**, so they can't claim. Either the insurer needs a page to link a
   policy, or each new account could get a demo policy.
4. **One assessor only** in the demo: the "another assessor gets 403" checks and the tie-break in
   routing can't be shown with the demo data. `tests/test_backend.py` and `tests/test_routing.py`
   still cover them.
5. The other choices listed under "Implementation notes" in `docs/CONTRACT.md` (`/price-list` open to
   insurers, background photo checks, reply photos being checked).

## Things to know before running it on a shared machine

- `python scripts\seed_demo.py --reset` **deletes all v2 data**, including accounts people registered.
- The seed saves photos as `backend/uploads/1.jpg`, `2.jpg` and so on, overwriting older files with
  the same names.
- A database seeded before step 6 still has `fraud_review` decisions; reset it, or run the one-line
  update in [SETUP_GUIDE.md](SETUP_GUIDE.md) section 6, case 3.
