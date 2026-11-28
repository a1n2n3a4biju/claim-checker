# ClaimProof v2: how the new code works

An explanation of the code added for v2, file by file, for anyone who has to read, change or present
it. For setup, see [SETUP_GUIDE.md](SETUP_GUIDE.md); for the list of changes, see
[CHANGES.md](CHANGES.md); for the exact names and response shapes, see [CONTRACT.md](CONTRACT.md).

---

## 1. The big picture

```
 Browser (React, port 5173)                     Backend (FastAPI, port 8000)               PostgreSQL
 ┌──────────────────────────┐   HTTP + token   ┌────────────────────────────────┐        ┌───────────────┐
 │ pages/ (per role)        │ ───────────────> │ main.py      endpoints, shapes │ ─────> │ claimproof_v2 │
 │ api/index.js  one fn per │ <─────────────── │ auth.py      sign-in, roles    │        │ 9 tables      │
 │               endpoint   │      JSON        │ workflow.py  statuses, actions │        └───────────────┘
 │ mocks/ (no-backend mode) │                  │ routing.py   pick assessor     │
 └──────────────────────────┘                  │ photo_checks.py  v1 checks     │ ─────> backend/uploads, results
                                               └────────────────────────────────┘
```

Three rules hold the design together:

1. **Every status change goes through one function** (`workflow.change_status`). It knows the
   allowed moves and who may make each one, and it writes a history row. Nothing else sets
   `claim.status`.
2. **The endpoints are thin.** `main.py` checks the input and the role, calls a function in
   `workflow.py`, and turns the result into JSON. The rules live in `workflow.py`, so the seed script
   and the tests use exactly the same code as the website.
3. **Claimants never receive risk data.** Claimant responses are built by a separate function that
   doesn't include those fields, and the frontend strips them again as a second safety net.

### The life of a claim

```
submitted -> photos_checked -> awaiting_assessment -> assessed -> under_review -> decided -> settled
 claimant      system            system (routing)      assessor     insurer          insurer    insurer
                                                                     |    ^
                                                       insurer asks  v    |  claimant replies
                                                              more_info_requested
```

---

## 2. Backend

### 2.1 `backend/app/database.py`: connection

- Loads `backend/.env` with `python-dotenv`, wherever the program is started from.
- Builds the SQLAlchemy `engine` from `DATABASE_URL`. For SQLite it adds `check_same_thread=False`,
  which SQLite needs when FastAPI uses the connection from different threads.
- `get_db()` is a FastAPI dependency: each request gets its own session, which is closed afterwards.

### 2.2 `backend/app/models.py`: the tables

| Table | One row is | Key columns |
|---|---|---|
| `users` | an account | `email` (unique), `role` (claimant / assessor / insurer), `password_hash` (bcrypt, never the password) |
| `policies` | an insurance policy of a claimant | `start_date`, `end_date`, `premium`, `deductible`, `sum_insured` (whole rupees) |
| `vehicles` | a car on a policy | `registration`, `make`, `model`, `year` |
| `claims` | a claim | status, incident details, `risk_level`, `risk_score`, `reasons`, `fraud_flag`, `assessor_id`, `decision`, `approved_amount`, `decision_note`, `info_request` |
| `images` | an uploaded photo | `file_path`, `sha256_hash` (to spot duplicates), `duplicate_of`, `checked`, `risk_score`, `risk_level` |
| `analysis_results` | one check's result on one photo | `module` (e.g. `ela`), `score`, `flags`, `artifact_paths` (heatmap) |
| `quotations` | the assessor's estimate | `total` (calculated by the backend), `note` |
| `quotation_items` | one line of it | `kind` (part / labour), `description`, `quantity`, `unit_price` |
| `status_history` | one status change | `from_status`, `to_status`, `user_id` (empty = the system), `note`, `at` |

Money is always whole rupees (integers), never decimals.

### 2.3 `backend/app/auth.py`: passwords, tokens and roles

**Passwords.** `hash_password()` uses bcrypt with a random salt. Only the hash is stored, so even
someone who reads the database can't recover a password. `verify_password()` checks a typed password
against the hash.

**Tokens.** After sign-in the browser gets a token like `<data>.<signature>`:

- `<data>` is base64 of `{"sub": user id, "role": ..., "exp": expiry time}`, valid for 8 hours.
- `<signature>` is an HMAC-SHA256 of `<data>`, made with `TOKEN_SECRET`.

If anyone changes the data (for example the role), the signature no longer matches and the token is
refused with 401. `hmac.compare_digest` is used so the comparison takes the same time whether it
matches or not.

**Access checks** are FastAPI dependencies:

- `current_user`: reads the `Authorization: Bearer ...` header, checks the token, loads the user
  (401 if any of that fails, including when the user's role has changed since the token was made).
- `require_role("insurer")`: also requires one of the given roles (otherwise 403).

**Sign-up** (`register`): tidies the name and lower-cases the email, checks the email format, that
the password has at least 8 characters, and that the email isn't already used (400). It always
creates a **claimant**: staff accounts can see every claim and approve money, so they only come
from the seed script.

### 2.4 `backend/app/workflow.py`: the status engine and all actions

**Statuses and labels.** `STATUSES` maps each status to two labels: one for staff and a friendlier
one for claimants (for example `under_review` is "Under insurer review" for staff, "Under review" for
the claimant).

**Allowed moves.** `TRANSITIONS` is a table of `(from, to) → who may do it`:

```python
("awaiting_assessment", "assessed"): "assessor",
("under_review", "decided"): "insurer",
("submitted", "photos_checked"): SYSTEM,
...
```

`change_status(db, claim, to, actor, note)`:

1. Looks up the move. Not in the table: **409**, with a message saying what the status is now.
2. Compares the actor's role with the one allowed (`actor=None` means the system). Wrong role: **403**.
3. Sets the status and adds a `status_history` row.

That's why, for example, an insurer can't approve a claim that hasn't been assessed: the move
`assessed → decided` simply isn't in the table.

**Ownership checks.** `own_claim()` (the claim must belong to this claimant) and `assigned_claim()`
(it must be assigned to this assessor) return 404 for a missing claim and 403 for someone else's.

**Claimant actions.**

- `create_claim`: the vehicle must be on one of the claimant's own policies, the incident date can't
  be in the future and must be inside the policy dates (otherwise 400 with the policy's dates).
- `save_images` / `upload_photos`: accepts only JPEGs (checks the first two bytes, `FF D8`, not just
  the file name), stores each as `uploads/<image id>.jpg`, and records its SHA-256 hash. If the same
  hash already exists, the photo is marked `duplicate_of` that earlier one. Photos can only be added
  while the claim is `submitted`.
- `reply_to_info_request`: a note and/or photos, then the claim goes back to `under_review`.

**Photo checks and routing** (`run_photo_checks`), done by the system:

1. For every photo not checked yet: run all checks (`photo_checks.run_all_modules`), save each
   module's result, fuse the scores into the photo's risk score and level. A duplicate photo adds a
   reason.
2. The claim's risk = its **riskiest photo**. Reasons are the modules' flags, without repeats, at most 5.
   High risk sets the fraud flag.
3. If the claim is still `submitted`: move it to `photos_checked`, ask `routing.route_claim` for an
   assessor (giving it each assessor's number of open claims), assign them, and move to
   `awaiting_assessment`.

After an upload, the API runs this in the background (`run_photo_checks_in_background`, with its own
database session) so the upload request returns at once. Photos added in a reply are checked too:
they can raise the risk, but don't change the status.

**Assessor action.** `submit_quotation` checks every line (kind, description, quantity ≥ 1, price ≥ 0),
moves the claim to `assessed` and **calculates the total itself** from the lines. A total sent by the
browser would be ignored.

**Insurer actions.** `start_review`, `request_info` (a message is required), `decide` and `settle`:

- `decide`: outcome `approved`, `rejected` or `further_review`. Approving needs an amount above 0;
  rejecting or further review needs a note.
- `settle`: only an approved claim can be settled. A rejected or further-review claim gets 409.

### 2.5 Claim history and the payout breakdown (in `workflow.py`)

The rule's numbers are constants, so changing the rule means changing three lines:

```python
RECENT_DAYS = 365              # what "recent" means
HISTORY_RATE_PER_CLAIM = 0.05  # taken off per recent approved claim
HISTORY_RATE_MAX = 0.20        # never more than this in total
```

**`recent_approved_claims(db, claim)`** finds the claimant's *other* claims that were **approved**
and whose **incident date** is within 365 days **before this claim's incident date**. It counts from
the incident rather than from today, so the answer doesn't change depending on when the insurer opens
the claim. Rejected and further-review claims don't count.

**`payout_breakdown(db, claim, quotation)`** returns `None` until there is a quotation, then:

```python
after     = max(0, quotation.total - policy.deductible)
recent    = len(recent_approved_claims(db, claim))
rate      = round(min(recent * 0.05, 0.20), 2)
deduction = round(after * rate)
suggested = max(0, min(after - deduction, policy.sum_insured))
```

It also writes an `explanation` sentence for the insurer, using `rupees()`, which formats amounts the
Indian way (`₹12,34,567`). The sentence mentions the cap when the sum insured limits the payout.

`suggested_payout()` just returns the breakdown's last number, so there's only one place where the
payout is calculated.

### 2.6 `backend/app/routing.py`: choosing an assessor

`route_claim(risk_level, assessors)` gets the risk level and a list such as
`[{"id": 3, "open_claims": 2}, {"id": 4, "open_claims": 1}]` and returns
`{"fraud_flag": risk_level == "high", "assessor_id": ...}`.

The assessor is chosen with `min(assessors, key=lambda a: (a["open_claims"], a["id"]))`: fewest open
claims first, and on a tie the lower id, so the result is always predictable. It has no database code,
which makes it easy to test (`tests/test_routing.py`). "Open claims" are the assessor's claims still
`awaiting_assessment` (counted in `workflow.open_claims_per_assessor`).

### 2.7 `backend/app/photo_checks.py`: the v1 checks, unchanged

- `load()`: loads the fusion model and warms up the AI detectors once, at startup.
- `run_all_modules()`: runs forensics (ELA, noise, copy-move), JPEG ghosts and the two AI detectors.
  If one fails, it's reported as a reason instead of stopping the claim.
- `fuse()`: combines the six scores with the saved logistic regression model.
- `risk_level()`: low below 0.45, high from 0.688, medium in between.

The detection modules are imported only when first used, so the tests can run without PyTorch.

### 2.8 `backend/app/main.py`: the endpoints

On startup it creates `backend/uploads` and `backend/results`, creates any missing tables, loads the
photo models (skipped when `SKIP_PHOTO_MODELS=1`, as in the tests), allows the frontend's address
(CORS), and serves the two folders at `/uploads` and `/results`.

Every error comes back as `{"detail": "a readable message"}`. A custom handler turns FastAPI's
validation errors (422) into one sentence naming the field, e.g. `amount: Input should be greater than 0`.

**Building responses.** The same claim is shown differently depending on who asks:

| Function | Used for | Contains |
|---|---|---|
| `claimant_claim` | `GET /me/claims/{id}` | Claim details, claimant status labels, timeline, decision. **No** risk, photos' results, history or payout. |
| `staff_claim` | `GET /assessor/claims/{id}` | Everything above plus risk, reasons, fraud flag, photos with each module's score and heatmap, quotation, `previous_claims` (with `approved_amount`), `recent_approved_claims`, full history |
| `insurer_claim` | `GET /insurer/claims/{id}` | `staff_claim` plus policy, `payout_breakdown`, `suggested_payout`, and whether the policy was valid on the incident date |

`past_claims` lists other claims by the same claimant **or on the same vehicle** (marked
`same_vehicle`), which helps spot a car claimed under different names.

The request bodies (`LoginIn`, `RegisterIn`, `ClaimIn`, `QuotationIn`, `DecisionIn`, ...) are Pydantic
models, so wrong types or missing fields are refused before any code runs. `DecisionIn.outcome` only
accepts `approved`, `rejected` or `further_review`, which is why the old `fraud_review` now gets 422.

---

## 3. Demo data: `scripts/seed_demo.py`

**How it works.** It calls the same `workflow` and `auth` functions the website uses, never writing a
status straight into a table. A claim that ends `under_review` really went through submission, photo
checks, routing, quotation and the insurer's "start review". If the workflow has a bug, the seed fails
too.

**Steps in `main()`:**

1. Read `DEMO_PASSWORD`. Create the PostgreSQL database if missing (`create_database_if_missing`
   connects to the built-in `postgres` database and runs `CREATE DATABASE`).
2. With `--reset`, drop the nine v2 tables; then create them. Stop if users already exist, so the
   demo is never added twice by accident.
3. Load the photo models.
4. Create 32 users with **one** bcrypt hash of the demo password (hashing is deliberately slow, and
   doing it 32 times would only slow the seed down; the hashes are still bcrypt).
5. One policy and vehicle per claimant. Deductibles and sums insured rotate through a few values;
   claimant 23's policy ends on 31 Oct 2026.
6. For claimants 1–16: create the earlier claims (dated Feb, Apr, Jun and Aug 2026), take each through
   to approved at its suggested payout and settled. Then create the current claim, so the later
   claims' payouts already include the deduction for the earlier ones.
7. Claimants 17–23: one claim each for the special cases (see [SETUP_GUIDE.md](SETUP_GUIDE.md),
   section 7). Claimant 23's claim is expected to be refused with 400, and the script checks that it
   was.
8. Print a summary and mark with `CHECK` any claim whose risk or status isn't what was planned.

**Helpers.**

- `new_claim()`: submits, uploads one photo and runs the checks.
- `quote()`: the assessor submits one of the seven `REPAIRS` quotations.
- `photo()`: reads a dataset file and stops with a clear message if it's missing.

**Why each photo is used once.** The same file uploaded twice has the same SHA-256 hash and is
flagged as a duplicate, which would add a reason and could change the result. So the photos are
split into `LOW_PHOTOS` (38 genuine photos the saved scores rate low), `MEDIUM_PHOTOS` (8 that rate
medium) and three fakes (`AI_SD_001`, `AI_SD_002`, `CM_P_005`).

---

## 4. Frontend

### 4.1 Structure

| Folder | What's in it |
|---|---|
| `src/api/client.js` | The axios instance: adds the token to every request, turns every error into an `ApiError(status, detail)`, and on a 401 clears the token and signs the user out |
| `src/api/index.js` | One small function per endpoint. Pages never call axios directly, so a contract change touches only this file. Each function goes to the mock instead when `VITE_USE_MOCK=true`. |
| `src/auth/` | `AuthContext` keeps the signed-in user; `storage.js` keeps the token in `sessionStorage` |
| `src/components/` | Pieces shared by several pages |
| `src/pages/` | One folder per role |
| `src/mocks/mockServer.js` | A complete stand-in backend |
| `src/utils/` | Labels, money/date formatting, the `useLoad` hook |

### 4.2 Sign-in and page protection

- **`AuthContext`** holds the user. On a page refresh it finds the saved token and calls `GET /me` to
  restore the user. It also listens for the "signed out" event that `client.js` sends on any 401.
- **`sessionStorage`** (not `localStorage`) means closing the tab signs you out. Every access is
  wrapped in `try/catch`, so a browser that blocks storage still works.
- **`RequireRole`** wraps each role's pages: not signed in sends you to `/login` (remembering where
  you wanted to go); wrong role shows "You don't have access to this".
- `HOME` gives each role's home page, used after sign-in and by the header logo.

The backend checks access on every request anyway. The frontend checks are only for a good
experience, not for security.

### 4.3 Claimant protection in the browser

`stripRisk()` in `api/index.js` removes keys such as `risk_score`, `risk_level`, `reasons`,
`fraud_flag`, `images`, `heatmap_url` and `suggested_payout` from every claimant response, at any depth.
The backend already leaves them out; this is a second guard in case one is ever added by mistake.

### 4.4 Loading data: `utils/useLoad.js`

`useLoad(loadFunction)` returns `{ data, error, loading, reload, setData }`. Pages use it like this:

```jsx
const { data: claim, error, loading, reload, setData } =
  useLoad(useCallback(() => getInsurerClaim(id), [id]));
```

`setData` lets an action put the updated claim (returned by the backend) straight on the page without
loading it again. `reload` is used after a 409, when the claim changed in the meantime.

### 4.5 Staff claim pages

**`components/StaffClaim.jsx`** has the pieces both assessor and insurer pages use:

- `RiskSummary`: risk level, score, fraud flag and the reasons.
- `PhotoEvidence`: each photo in a `PhotoViewer`, with each check's score and flags.
- `ClaimFacts`: incident details.
- `QuotationTable`: the quotation lines and total.
- `PreviousClaims({ claims, recent, linkBase })`: the table of other claims. Approved amounts are in
  their own column, claims in `recent` are highlighted, and a summary line above shows how many
  approved claims fall in the 12 months before this incident and how much was paid.

**`pages/insurer/InsurerClaim.jsx`** lays out the insurer's page: risk and photos on the left; on the
right, the actions and the **Payout** box (`PayoutBreakdown`), then the policy, quotation, previous
claims and full history.

`PayoutBreakdown` shows the backend's numbers as rows (quotation total, minus deductible, after
deductible, claim-history deduction, suggested payout in bold) and the explanation sentence. It doesn't
calculate anything itself, so it can never disagree with the backend.

**`pages/insurer/ClaimActions.jsx`** shows only the actions allowed for the current status:

| Status | What the insurer sees |
|---|---|
| `assessed` | "Start review" |
| `under_review` | Decide (Approve / Reject / Further review) and "Ask for more info" |
| `decided` | Approved: "Mark settled". Rejected or further review: the decision, no further action |
| `more_info_requested` | The question, while waiting for the claimant's reply |
| `settled` | The amount paid |
| earlier statuses | "Waiting for the photo checks and the assessor's quotation" |

The approve amount starts at `claim.suggested_payout`. The form checks the obvious mistakes before
sending (whole rupees above 0, a note for reject and further review), but the backend checks again.
If the backend answers 409 (for example, someone else already decided), the page shows the message and
reloads the claim. The parent gives the component `key={claim.status}`, so the forms reset whenever
the status changes.

### 4.6 The photo viewer: `components/PhotoViewer.jsx`

Built on `react-zoom-pan-pinch`:

```jsx
<TransformWrapper ref={zoom} minScale={1} maxScale={8} ... onTransformed={(_, s) => setScale(s.scale)}>
  <TransformComponent>
    <Box sx={{ position: 'relative' }}>
      <img src={photo} />                                   {/* the photo */}
      <img src={heatmap} style={{ position: 'absolute', inset: 0, opacity }} />   {/* the overlay */}
    </Box>
  </TransformComponent>
</TransformWrapper>
```

- **Photo and heatmap move together.** Both images are inside the same zoomed box, and the heatmap is
  stretched over the photo (`inset: 0`, full width and height). Zooming or panning keeps them lined up.
- **Buttons.** The `ref` gives access to `zoomIn()`, `zoomOut()` and `resetTransform()`.
  `onTransformed` reports the current scale, which is shown as a percentage and used to disable
  "Zoom out" and "Reset" at 100% and "Zoom in" at 800%.
- **Choosing the overlay.** Only modules that produced a heatmap are offered (ELA, noise, copy-move,
  JPEG; the AI detectors make none). "Photo only" hides the overlay. The first heatmap is shown by
  default.
- **Transparency.** A slider from 0 to 100% sets the overlay's `opacity`. `pointerEvents: 'none'` on
  the overlay lets drags reach the zoom area underneath.
- **Open full size / Heatmap.** Plain links that open the original files in a new tab.
- **Failures.** If the photo can't load, a message replaces the viewer. If one heatmap can't load,
  its URL is remembered in `badMaps` and a note says so, while the score and flags still apply.

The viewer shows heatmaps, so it is only used on assessor and insurer pages.

### 4.7 Other new pages

- **`pages/Landing.jsx`**: the v1 home page with two cards, "Create a new account" and "Sign in". A
  signed-in user sees a "Welcome back" box with a link to their home page instead. `CoverArt.jsx` is
  the drawing at the top.
- **`pages/Register.jsx`**: the sign-up form. It checks the fields in the browser first (including that
  both passwords match), then shows the backend's 400/422 messages next to the right field.
- **`pages/Login.jsx`**: sign-in, a link to sign-up, and the list of demo accounts.
- **`pages/claimant/`**: `MyClaims` (list), `SubmitClaim` (details, then photos with an upload progress
  bar), `ClaimDetails` (timeline, decision shown as "Approved", "Rejected" or "Needs further review",
  and the reply form when more information is asked for), `Dashboard` (policies).
- **`pages/assessor/`**: `AssignedClaims` and `AssessorClaim` with `QuotationForm`. The form picks items
  from the price list, lets you edit them, and adds up the total as you type (the backend
  recalculates it).

### 4.8 Mock mode: `mocks/mockServer.js`

A small backend inside the browser, used when `VITE_USE_MOCK=true`. It exists so the frontend can be
built and shown without the server.

- It has the same accounts as the seed (claimants 1–30, assessor 31, insurer 32). Any non-empty
  password works.
- It applies the same rules: the same transitions (409), role checks (403), ownership (403/404), and
  the same response shapes, including `payout_breakdown`, worked out with the same formula
  (`recentApproved` and `payoutBreakdown`).
- Data is kept in memory and resets on refresh.

**If you change the payout rule, change it in both places:** `backend/app/workflow.py` and
`payoutBreakdown` in `mockServer.js`.

---

## 5. Tests

### `tests/test_routing.py`

Unit tests for `route_claim`: the fraud flag only for high risk, the least busy assessor, the tie
going to the lower id, and errors for a bad risk level or no assessors.

### `tests/test_backend.py`

Runs the real FastAPI app with FastAPI's `TestClient` (no server needed) on a new temporary SQLite
database. The photo checks are replaced by `fake_checks`: a photo containing the bytes `FAKE` scores
high and anything else low, so the tests are fast and predictable.

It covers:

- sign-in and sign-up (including that passwords are stored as bcrypt hashes);
- each role's full journey;
- every 403 (wrong role, someone else's claim) and 409 (wrong status);
- formats (dates, whole rupees);
- the payout breakdown (exact numbers and explanation), the 12-month window, the 20% cap, and
  `further_review` / `fraud_review`;
- that **no claimant response** contains risk, fraud, payout or history fields, checked by searching
  the raw JSON text.

It prints one line per check and ends with `ALL PASSED` or the number that failed.

### `tests/e2e_checklist.md`

A manual checklist for the running app, role by role, with a column for notes and who fixes what.

---

## 6. Where to change things

| To change | Edit |
|---|---|
| The history deduction numbers | `RECENT_DAYS`, `HISTORY_RATE_PER_CLAIM`, `HISTORY_RATE_MAX` in `backend/app/workflow.py`, **and** `payoutBreakdown` in `frontend/src/mocks/mockServer.js`; then the expected numbers in `tests/test_backend.py` and the example in `docs/CONTRACT.md` |
| An allowed status move | `TRANSITIONS` in `workflow.py`, `ClaimActions.jsx`, the mock's transitions, `CONTRACT.md` section 2.3 |
| A status label | `STATUSES` in `workflow.py` and `frontend/src/utils/status.js` |
| How assessors are chosen | `backend/app/routing.py` and `tests/test_routing.py` |
| Risk thresholds | Don't: they come from the trained fusion model and the evaluation depends on them |
| Demo accounts or claims | `scripts/seed_demo.py`, the mock's users, the `DEMO` text in `Login.jsx`, the tables in `README.md` and `SETUP_GUIDE.md` |
| Token lifetime | `TOKEN_HOURS` in `backend/app/auth.py` |
| Minimum password length | `MIN_PASSWORD` in `auth.py` and the check in `Register.jsx` |
| Prices for the quotation form | `data/price_list.json` |
