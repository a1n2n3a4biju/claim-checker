# ClaimProof v2: end-to-end checklist

Owner: M2 (Hobhav). Run on the real app (`VITE_USE_MOCK=false`) after a fresh
`claimproof_v2` database and `python scripts/seed_demo.py`.

Every journey is tested **twice**: through the website, and directly in the
backend's `/docs` page. The backend must refuse access even if a page forgets
to hide a button.

Mark each line `PASS` or `FAIL`. Every `FAIL` gets a note and an owner for the fix.

**Run details**

| Date | Laptop | Branch / commit | Tester |
|------|--------|-----------------|--------|
|      |        |                 |        |

Demo accounts (password from `DEMO_PASSWORD`): `claimant1@demo.in` … `claimant30@demo.in`,
`assessor1@demo.in`, `insurer1@demo.in`. Claimants 1–16 have recent approved claims.
See the README for what each claimant's demo data shows.

---

## 0. Seeded demo data

| # | Check | Result | Note / fix owner |
|---|-------|--------|------------------|
| 0.1 | Seed script runs on an empty `claimproof_v2` database with no errors and prints users, policies and claims created | | |
| 0.2 | Running it again on a fresh database gives the same summary | | |
| 0.3 | 32 users (claimant1–30, assessor1, insurer1), 30 policies, 48 claims; no line marked CHECK | | |
| 0.4 | Claimants 1–8: current claim `under_review`; 9–16: `assessed`; payout shows −5% / −10% / −20% | | |
| 0.5 | claimant17, AI-generated `AI_SD_001`: high risk, fraud flag, ends `under_review` | | |
| 0.6 | claimant18, copy-move `CM_P_005`: medium or high, ends `assessed` | | |
| 0.7 | claimant19 `awaiting_assessment`; claimant20 `more_info_requested`; claimant21 `decided` (further review); claimant22 `settled` | | |
| 0.8 | claimant23, claim outside policy dates was refused with 400 and not created | | |

## 1. Sign-in

| # | Check | Result | Note / fix owner |
|---|-------|--------|------------------|
| 1.1 | `POST /auth/login` with a demo account returns `token` and `user` (`id`, `name`, `role`) | | |
| 1.2 | Wrong password gives 401 with a `detail` message | | |
| 1.3 | `GET /me` with the token returns the signed-in user; page refresh keeps the session | | |
| 1.4 | No token, or a changed token, gives 401 and the site goes to the login page | | |
| 1.5 | Claimant lands on "My claims", assessor on "Assigned claims", insurer on "Claims queue" | | |
| 1.6 | Every page has a sign-out button; after sign-out, protected pages go to login | | |
| 1.7 | Home page (`/`) shows "Create an account" and "Sign in" when signed out; signed in, it goes to the role's home | | |
| 1.8 | Create an account: new user is signed in as a claimant and lands on "My claims" | | |
| 1.9 | The new account can sign out and sign in again with the same password | | |
| 1.10 | Duplicate email gives 400; short password (<8) or bad email gives 422 shown next to the field | | |
| 1.11 | `POST /auth/register` with `"role": "insurer"` in `/docs` still creates a claimant | | |
| 1.12 | In the database, `users.password_hash` starts with `$2` (bcrypt), never the plain password | | |

## 2. Journeys

### 2.1 Claimant submits a claim

| # | Check | Result | Note / fix owner |
|---|-------|--------|------------------|
| 2.1.1 | claimant24's dashboard shows the policy (number, dates, sum insured) and the car | | |
| 2.1.2 | claimant24 submits a claim with a vehicle from the dropdown; `POST /claims` returns `id` and `"status": "submitted"` | | |
| 2.1.3 | claimant24 uploads JPEG photos (`files` field); claim shows as **"Received"** | | |
| 2.1.4 | Uploading a non-JPEG gives 400 with `detail` shown next to the form | | |
| 2.1.5 | A missing required field gives 422 and the page shows which field | | |
| 2.1.6 | A vehicle not on the claimant's policy gives 400 with a clear `detail` | | |
| 2.1.7 | claimant23's claim dated after the policy ended gives 400 with a clear `detail` | | |

### 2.2 Routing after the photo checks

| # | Check | Result | Note / fix owner |
|---|-------|--------|------------------|
| 2.2.1 | After the checks, status moves `submitted` → `photos_checked` → `awaiting_assessment` | | |
| 2.2.2 | The claim is assigned to assessor1 (with one assessor; the fewest-open-claims rule is covered by `test_routing.py`) | | |
| 2.2.3 | A high-risk claim gets `fraud_flag: true`; low and medium do not | | |
| 2.2.4 | `python -m unittest tests/test_routing.py` passes | | |

### 2.3 Assessor quotation

| # | Check | Result | Note / fix owner |
|---|-------|--------|------------------|
| 2.3.1 | The assigned assessor sees the claim in "Assigned claims", newest first | | |
| 2.3.2 | Claim view shows incident details, vehicle and claimant history, photos with heatmaps, risk level, reasons | | |
| 2.3.3 | Quotation form: price list fills the dropdown; a custom item can be typed; rows can be added and removed | | |
| 2.3.4 | Live total preview matches the total the backend returns | | |
| 2.3.5 | Submitting the quotation moves the claim to **"Assessed"** | | |

### 2.4 Insurer review, decision and settlement

| # | Check | Result | Note / fix owner |
|---|-------|--------|------------------|
| 2.4.1 | Claims queue lists all claims, fraud flags and high risk first; `?status=` and `?risk=` filters work | | |
| 2.4.2 | Claim view shows claimant, policy, premium, dates, vehicle and claim history, photo checks and reasons, quotation, suggested payout, full history | | |
| 2.4.3 | Payout breakdown: quotation total, deductible, after deductible, recent approved claims, history rate and deduction, suggested payout and the explanation sentence | | |
| 2.4.3a | claimant1 (1 past claim) shows −5%; claimant11 −10%; claimant15 −20%; claimant17 (no history) 0% | | |
| 2.4.3b | Assessor and insurer history tables show each earlier claim's approved amount and the count in the last 12 months | | |
| 2.4.4 | Only "Start review" is shown on an `assessed` claim; it moves the claim to `under_review` | | |
| 2.4.5 | Approve box is pre-filled with the suggested payout; the insurer can type a different amount | | |
| 2.4.6 | Approve without an amount gives 422; reject or further review without a note gives 422 | | |
| 2.4.6a | "Further review" moves the claim to `decided`; it cannot be settled (409); the claimant sees "Needs further review" | | |
| 2.4.7 | Approving moves the claim to `decided`; "Mark settled" then moves it to `settled` | | |

### 2.5 More information

| # | Check | Result | Note / fix owner |
|---|-------|--------|------------------|
| 2.5.1 | Insurer asks for more info with a message; claim moves to `more_info_requested` | | |
| 2.5.2 | Claimant sees **"We need more information"** and the insurer's message | | |
| 2.5.3 | Reply form is shown only in `more_info_requested`; claimant replies with a note and optional photos | | |
| 2.5.4 | Claim returns to **"Under review"** | | |

### 2.6 Claimant timeline

| # | Check | Result | Note / fix owner |
|---|-------|--------|------------------|
| 2.6.1 | Claimant timeline shows every step, with claimant labels and local times | | |
| 2.6.2 | Money is shown as ₹45,000 (API sends `45000`) | | |

### 2.7 Photo viewer (assessor and insurer)

| # | Check | Result | Note / fix owner |
|---|-------|--------|------------------|
| 2.7.1 | Zoom in and out with the buttons, mouse wheel, pinch, and double-click; the % shows the zoom | | |
| 2.7.2 | When zoomed, drag moves around the photo; Reset goes back to 100% | | |
| 2.7.3 | Heatmap buttons switch the overlay (or "Photo only"); the slider changes its transparency; it zooms with the photo | | |
| 2.7.4 | "Open full size" opens the original photo in a new tab; "Heatmap" opens the heatmap | | |
| 2.7.5 | No photo viewer, heatmap or zoom controls appear on any claimant page | | |

## 3. Access rules (the most important part)

Check each one in `/docs` (or with `curl`) as well as in the website.

| # | Check | Expected | Result | Note / fix owner |
|---|-------|----------|--------|------------------|
| 3.1 | claimant1 opens claimant2's claim: `GET /me/claims/{id}` | 403 | | |
| 3.2 | claimant1 uploads photos to, or replies on, claimant20's claim | 403 | | |
| 3.3 | Assessor opens a claim assigned to another assessor: `GET /assessor/claims/{id}` (the demo has one assessor, so this is covered by `tests/test_backend.py`) | 403 | | |
| 3.4 | Assessor submits a quotation on a claim assigned to someone else (covered by `tests/test_backend.py`) | 403 | | |
| 3.5 | Claimant calls `GET /assessor/claims`, `GET /price-list`, `GET /insurer/claims`, `GET /insurer/claims/{id}` | 403 | | |
| 3.6 | Claimant calls `POST /claims/{id}/quotation`, `start-review`, `request-info`, `decision`, `settle` | 403 | | |
| 3.7 | Assessor calls insurer endpoints; insurer calls `POST /claims` | 403 | | |
| 3.8 | Claimant opens an assessor or insurer page in the browser | "You don't have access to this" | | |
| 3.9 | No claimant response (`/me/claims`, `/me/claims/{id}`, `POST /claims`, reply) contains `risk_score`, `risk_level`, `reasons`, `fraud_flag`, heatmap URLs, `payout_breakdown` or `recent_approved_claims` | none present | | |
| 3.10 | No claimant page shows risk, reasons or heatmaps | none shown | | |
| 3.11 | Illegal move: settle a rejected claim | 409 | | |
| 3.12 | Illegal move: start review on an `awaiting_assessment` claim | 409 | | |
| 3.13 | Illegal move: second quotation on an `assessed` claim | 409 | | |
| 3.14 | Illegal move: claimant reply when status is not `more_info_requested` | 409 | | |
| 3.15 | After a 409 the site shows `detail` and reloads the claim | | | |
| 3.16 | Every status change is in `status_history` with who, when, from, to and note | | | |
| 3.17 | All errors have the shape `{"detail": "..."}` | | | |

## 4. Formats (contract section 2.5)

| # | Check | Result | Note / fix owner |
|---|-------|--------|------------------|
| 4.1 | JSON field names are `snake_case` | | |
| 4.2 | Dates are `YYYY-MM-DD`; date-times are ISO UTC ending in `+00:00` | | |
| 4.3 | Money is whole rupees as a number; ids are whole numbers | | |
| 4.4 | Status keys and risk levels match the contract exactly | | |

## 5. Unchanged from v1

| # | Check | Result | Note / fix owner |
|---|-------|--------|------------------|
| 5.1 | Photo checks (ELA, noise, copy-move, JPEG ghosts, two AI detectors) are unchanged | | |
| 5.2 | Fusion model and thresholds (0.45 / 0.688) are unchanged | | |

## Summary

| Section | Pass | Fail | Open fixes |
|---------|------|------|------------|
| 0 Seed | | | |
| 1 Sign-in | | | |
| 2 Journeys | | | |
| 3 Access | | | |
| 4 Formats | | | |
| 5 Unchanged | | | |
