# ClaimProof v2: how to run it

This guide covers every starting point: a fresh machine, a machine that already has some of the
packages, no dataset, and an existing database with old or different tables.

All commands are for **Windows PowerShell**, run from the `claim-checker` folder unless a step says
otherwise.

---

## 0. Pick how you want to run it

| Mode | What you get | Needs |
|---|---|---|
| **A. Frontend only (mock mode)** | All pages for all three roles, with built-in sample data. No server, no database, no dataset. | Node.js |
| **B. Backend tests only** | Checks every API journey and access rule on a temporary SQLite database. | Python + a few small packages |
| **C. Full app** | The real backend, PostgreSQL, the real photo checks and the seeded demo data. | Everything below |

If you only need to show the screens, mode A is enough. For the real demo, use mode C.

---

## 1. Check what you already have

Run these and compare with the "Needed" column.

```powershell
py -0                       # lists installed Python versions; you need 3.12
node -v                     # Node.js, needed v20 or newer
npm -v
psql --version              # PostgreSQL (only for mode C); "not recognized" means not installed or not on PATH
git --version
```

| Tool | Needed | Where to get it |
|---|---|---|
| Python | **3.12** (the pinned packages, including torch, are built for 3.12; 3.13/3.14 will fail) | python.org |
| Node.js | 20 or newer | nodejs.org (LTS) |
| PostgreSQL | 14 or newer (mode C only) | postgresql.org; remember the `postgres` password you set |

---

## 2. Backend (Python) packages

### 2.1 Check what is installed

```powershell
venv\Scripts\activate                     # if the venv already exists
python --version                          # must say 3.12.x
python -c "import fastapi, sqlalchemy, bcrypt, httpx, dotenv, joblib, sklearn; print('web packages OK')"
python -c "import torch, transformers, timm, clip, cv2; print('photo-check packages OK')"
python -m pip check                       # reports broken or conflicting packages
```

Then follow the case that matches.

### Case 1: no venv yet (nothing installed)

```powershell
py -3.12 -m venv venv
venv\Scripts\activate
python -m pip install -r requirements.txt       # includes CPU-only torch; takes a while
```

`requirements.txt` already points pip at the CPU build of PyTorch (first line), so you don't get the
large GPU build.

### Case 2: venv exists but was made with the wrong Python

Symptoms: `python --version` in the venv shows 3.13 or 3.14, or you see errors such as
`ArgsKwargs`, `DLL load failed` or `No module named 'pydantic_core._pydantic_core'`.
The packages cannot be repaired in place; rebuild the venv:

```powershell
deactivate                                      # only if the venv is active
Remove-Item -Recurse -Force venv
py -3.12 -m venv venv
venv\Scripts\activate
python -m pip install -r requirements.txt
```

### Case 3: venv is fine but some packages are missing

Running the install again only adds what is missing; packages that are already there are skipped:

```powershell
venv\Scripts\activate
python -m pip install -r requirements.txt
```

The v2 packages most often missing from an old v1 venv are `bcrypt`, `httpx`, `python-dotenv`,
`python-multipart` and `psycopg2-binary`. To add just those:

```powershell
python -m pip install bcrypt httpx python-dotenv python-multipart psycopg2-binary
```

### Case 4: you only want to run the backend tests (mode B)

The tests replace the photo checks with a stand-in, so they don't need torch or the model weights:

```powershell
python -m pip install fastapi uvicorn sqlalchemy bcrypt httpx python-multipart python-dotenv joblib scikit-learn
```

### 2.2 Model weights (mode C only)

The AI detectors need files that are **not** in Git (`weights/` and `third_party/` are git-ignored).
Check:

```powershell
Test-Path weights\BFREE_dino2reg4
Test-Path third_party\B-Free
Test-Path third_party\Community-Forensics
Test-Path backend\fusion\fusion_model.joblib
```

Any `False` means you need to download it: follow section 3 of
[DETECTORS_README.md](DETECTORS_README.md). Without them the backend still starts, but every photo
check reports "The AI check failed on this photo" and the seed results won't match the plan.

---

## 3. Frontend (Node) packages

From the `frontend` folder:

```powershell
cd frontend
Test-Path node_modules                     # False = nothing installed yet
npm ls --depth=0                           # lists installed packages; errors show missing ones
npm ls react-zoom-pan-pinch                # the newest package; should show 3.7.0
```

| Case | What to do |
|---|---|
| No `node_modules` folder | `npm install` |
| `node_modules` exists from before the zoom viewer was added (`npm ls react-zoom-pan-pinch` shows `(empty)` or an error) | `npm install` (adds only what is missing) |
| You want exactly the versions in `package-lock.json` (e.g. on the demo machine) | `npm ci` (deletes `node_modules` and reinstalls from the lock file) |
| Strange build errors after switching branches | `Remove-Item -Recurse -Force node_modules`, then `npm install` |
| `node -v` is below 20 | Install Node.js 20+ first; Vite 8 will not run on older versions |

Check that it builds:

```powershell
npm run build          # should end with "built in ..."
npm run lint           # 0 errors expected (3 old warnings are known)
```

---

## 4. Settings files

### 4.1 Backend: `backend/.env`

```powershell
Copy-Item backend\.env.example backend\.env      # skip if backend\.env already exists
python -c "import secrets; print(secrets.token_hex(32))"   # copy the output into TOKEN_SECRET
notepad backend\.env
```

| Setting | Example | Meaning |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg2://postgres:YOUR_PASSWORD@localhost:5432/claimproof_v2` | Which database to use (see section 6) |
| `TOKEN_SECRET` | 64 random hex characters | Signs the sign-in tokens. Changing it signs everyone out. |
| `DEMO_PASSWORD` | anything you choose | Password for every seeded demo account |

Never commit `backend/.env`; it is in `.gitignore`.

### 4.2 Frontend: `frontend/.env`

```powershell
cd frontend
Copy-Item .env.example .env                      # skip if .env already exists
```

| Setting | Value for mode A | Value for mode C |
|---|---|---|
| `VITE_API_URL` | (ignored) | `http://localhost:8000` |
| `VITE_USE_MOCK` | `true` | `false` |

If a `.env.local` file also exists in `frontend`, **it wins over `.env`**. Either edit both or delete
`.env.local`. Restart `npm run dev` after any change.

---

## 5. The dataset (demo photos)

The seed script uploads real photos from `data/images/` and runs the real photo checks on them.
The dataset is **not** in Git; it is in the team's shared Google Drive folder.

### 5.1 Check whether you have the photos the seed needs

With the venv active, from `claim-checker`:

```powershell
python -c "import sys; sys.path[:0]=['scripts']; import seed_demo as s; need=s.LOW_PHOTOS+s.MEDIUM_PHOTOS+[s.PHOTO_AI,s.PHOTO_AI_2,s.PHOTO_COPY_MOVE]; miss=[p for p in need if not (s.IMAGES/p).exists()]; print(len(need)-len(miss),'of',len(need),'demo photos found'); print(*miss, sep='\n')"
```

It prints `49 of 49 demo photos found` when everything is there, otherwise the list of missing files.
(It reads `backend/.env`, so do section 4.1 first.)

The seed needs:

| Folder | Files |
|---|---|
| `data/images/genuine/` | `P_001.jpg` to `P_048.jpg` (46 of them are used) |
| `data/images/ai/` | `AI_SD_001.jpg`, `AI_SD_002.jpg` |
| `data/images/Scripted_edits/` | `CM_P_005.jpg` |
| `data/images/scores.csv` | Saved scores; only used to explain the expected risk, not required to run |

### Case 1: you have the dataset

Nothing to do. Make sure the folder names match exactly (`genuine`, `ai`, `Scripted_edits`, with
that capitalisation) and there is no extra folder level such as `data/images/images/genuine`.

### Case 2: you don't have the dataset yet

1. Download the dataset zip file(s) from the team's Google Drive folder.
2. Extract them so the folders sit directly in `data/images/`:
   ```powershell
   Expand-Archive "$HOME\Downloads\drive-download-XXXX.zip" -DestinationPath data\images -Force
   ```
   If Google Drive split the download into several zips, extract all of them into the same place.
3. Run the check in 5.1 again.

### Case 3: you can't get the dataset

You still have three options:

- **Mode A (mock mode)** shows every page with sample data and needs no photos.
- **Mode B (tests)** needs no photos.
- **Use your own photos** for a real backend: put any 49 *different* JPEG files at the paths the
  check in 5.1 lists (for example, car photos renamed to `P_001.jpg` and so on). The seed will run,
  but the risk levels will come from your photos, so some lines of its summary will be marked
  `CHECK` (for example, the "AI photo" claim may come out low risk). The photos must all be
  different files: the same photo uploaded twice is flagged as a duplicate.

You can also skip the seed entirely and create a customer account from the **Create an account**
page, but sign-up only makes customer accounts with no policy, so you cannot submit a claim or see
the assessor and insurer pages that way. The seed is the only way to create staff accounts.

---

## 6. The database

v2 uses its **own** PostgreSQL database, `claimproof_v2`. The tables are:
`users`, `policies`, `vehicles`, `claims`, `images`, `analysis_results`, `quotations`,
`quotation_items`, `status_history`.

Two things to know first:

- The backend and the seed create any **missing** tables automatically, but they **never change a
  table that already exists**. If an existing table has a different layout, you must remove it (or use a
  new database). Otherwise you get errors such as `column claims.fraud_flag does not exist`.
- `python scripts\seed_demo.py --reset` drops **only the nine tables above** (with all their data,
  including accounts people registered) and rebuilds them. Tables with other names are left alone.

Pick the case that matches.

### Case 1: no database yet

Make sure PostgreSQL is running and `DATABASE_URL` has the right user and password. The seed creates
`claimproof_v2` for you:

```powershell
python scripts\seed_demo.py
```

If you get `permission denied to create database`, create it yourself in psql or pgAdmin, then run
the seed again:

```sql
CREATE DATABASE claimproof_v2;
```

### Case 2: you have the old v1 database (`claimproof`)

Nothing to change in it. v2 uses `claimproof_v2`, so v1's data is kept. Just make sure `DATABASE_URL`
ends in `/claimproof_v2`, not `/claimproof`, and follow Case 1.

### Case 3: `claimproof_v2` exists from an earlier version of v2

For example, seeded before this update (accounts like `ravi@demo.in`, or decisions saved as
`fraud_review`). The seed refuses to run on a database that already has users
("The database already has data. Run with --reset ..."). Reset it:

```powershell
python scripts\seed_demo.py --reset
```

This deletes all v2 data and rebuilds the demo (several minutes).

**Keeping your existing data instead:** the table layout has not changed in this update, only one
value has. Run this once in psql or pgAdmin on `claimproof_v2`, and the old data works with the new code:

```sql
UPDATE claims SET decision = 'further_review' WHERE decision = 'fraud_review';
```

The old seed accounts (`ravi@demo.in` and so on) will still be there instead of `claimant1` to
`claimant30`.

### Case 4: the database has tables with a different layout, or other tables you don't need

Typical errors: `column ... does not exist`, `relation ... does not exist` on a column you know
exists, or `--reset` failing with `cannot drop table users because other objects depend on it` (another
table, e.g. from v1, points at `users`).

Choose one:

1. **Use a fresh database (safest, keeps everything that's there).** Change the name at the end of
   `DATABASE_URL`, for example `/claimproof_v2_demo`, and run `python scripts\seed_demo.py`. The seed
   creates the new database.
2. **Reset the v2 tables:** `python scripts\seed_demo.py --reset`. This works when no other table
   depends on them.
3. **Empty the whole database (deletes every table in it, including ones v2 doesn't use).** Only if
   this database is just for v2. In psql connected to that database:
   ```sql
   DROP SCHEMA public CASCADE;
   CREATE SCHEMA public;
   ```
   Then run `python scripts\seed_demo.py`.

To see what is in a database before deciding:

```powershell
psql -U postgres -d claimproof_v2 -c "\dt"           # list tables
psql -U postgres -d claimproof_v2 -c "\d claims"     # columns of one table
```

### Case 5: different server, port, user or password

Only `DATABASE_URL` changes:

```
postgresql+psycopg2://USER:PASSWORD@HOST:PORT/DATABASE_NAME
```

If the password contains `@`, `:` or `/`, write it URL-encoded (`@` is `%40`).

### Case 6: no PostgreSQL at all

The backend also runs on SQLite (the tests use it). It's fine for trying the app on one laptop, but
use PostgreSQL for the real demo. Use an absolute path:

```
DATABASE_URL=sqlite:///C:/Users/YOU/claimproof_v2.db
```

The seed works the same way. To start again, delete the `.db` file or use `--reset`.

---

## 7. Seed the demo data (mode C)

With the venv active, from `claim-checker`:

```powershell
python scripts\seed_demo.py            # empty database
python scripts\seed_demo.py --reset    # anything already there is deleted first
```

- It loads the photo models, then runs the real checks on every demo photo, so expect **several
  minutes**.
- It prints one line per claim, then a summary with each claim's risk, status, payout and history
  deduction. Lines marked `CHECK` didn't come out as planned (usually missing weights or different
  photos).
- It saves the uploaded photos as `backend/uploads/1.jpg`, `2.jpg` and so on, **overwriting** any
  files with those names. Copy `backend/uploads` elsewhere first if you need the old ones.

### Demo accounts

All use the password in `DEMO_PASSWORD`.

| Email | Role | What it shows |
|---|---|---|
| `claimant1` … `claimant8@demo.in` | claimant | Past approved claims + a current claim **under review** (the insurer can decide right away) |
| `claimant9` … `claimant16@demo.in` | claimant | Past approved claims + a current claim **assessed** (the insurer starts the review) |
| `claimant17@demo.in` | claimant | AI-generated photo: high risk, fraud flag |
| `claimant18@demo.in` | claimant | Copy-move edited photo |
| `claimant19@demo.in` | claimant | Awaiting assessment (the assessor can write the quotation) |
| `claimant20@demo.in` | claimant | More information requested (the claimant can reply) |
| `claimant21@demo.in` | claimant | Decided: further review |
| `claimant22@demo.in` | claimant | Approved and settled |
| `claimant23@demo.in` | claimant | Policy ended 31 Oct 2026; a later claim is refused |
| `claimant24` … `claimant30@demo.in` | claimant | No claims: use them to submit a claim live |
| `assessor1@demo.in` | assessor | Suresh Babu; every claim is assigned to him |
| `insurer1@demo.in` | insurer | Priya Menon |

Claim history: claimants 1–10 have one earlier approved claim (5% deduction), 11–14 have two (10%),
15–16 have four (20%, the maximum).

---

## 8. Start the app

### Mode A: frontend only

```powershell
cd frontend
# in frontend\.env (and .env.local if present): VITE_USE_MOCK=true
npm run dev
```

Open http://localhost:5173 and sign in with any demo email and **any non-empty password**. Data lives
in the browser's memory and resets when you refresh the page.

### Mode B: backend tests

```powershell
python -m unittest tests/test_routing.py      # routing rules
python tests/test_backend.py                  # ends with "ALL PASSED"
```

Run them as **two separate commands**. `test_backend.py` is a plain script, not a unittest module.

### Mode C: full app (two terminals)

Terminal 1, backend:

```powershell
venv\Scripts\activate
cd backend
python -m uvicorn app.main:app --reload
```

Wait for `Application startup complete` (loading the AI models takes up to a minute).
API documentation: http://localhost:8000/docs

Terminal 2, frontend:

```powershell
cd frontend
# in frontend\.env: VITE_USE_MOCK=false, VITE_API_URL=http://localhost:8000
npm run dev
```

Open http://localhost:5173. Then work through [tests/e2e_checklist.md](../tests/e2e_checklist.md).

### A short demo path

1. Sign in as `insurer1@demo.in` and open a claim from claimant 15 or 16. The **Payout** box shows the
   20% history deduction, and the approve amount is already filled in.
2. Open the photo: zoom, drag, switch on a heatmap and move the transparency slider.
3. Open claimant 17's claim: high risk with the fraud flag.
4. Sign in as `claimant24@demo.in` and submit a new claim with a photo, then as `assessor1@demo.in`
   write its quotation.

---

## 9. Troubleshooting

| Problem | Cause and fix |
|---|---|
| `DATABASE_URL is not set` | `backend/.env` is missing or in the wrong folder. It must be `claim-checker/backend/.env`. |
| `password authentication failed for user "postgres"` | Wrong password in `DATABASE_URL`. |
| `could not connect to server` / `Connection refused` | PostgreSQL isn't running. Start it from Services (`postgresql-x64-NN`). |
| `The database already has data` | Use `--reset`, or see section 6, case 3. |
| `column ... does not exist` | Old table layout. See section 6, case 4. |
| `Missing dataset photo: ...` | See section 5. |
| `No module named 'sqlalchemy'` (or similar) | The venv isn't active (`venv\Scripts\activate`), or see section 2. |
| `ArgsKwargs` or `DLL load failed` | venv made with the wrong Python. See section 2, case 2. |
| Activation blocked in PowerShell | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| pip says it can't read `requirements.txt` | The file is saved as UTF-16. Open it in VS Code, choose "Save with Encoding", then UTF-8. |
| `TOKEN_SECRET is not set on the server` | Add it to `backend/.env` and restart the backend. |
| Frontend says "Can't reach the server" | The backend isn't running, or `VITE_API_URL` is wrong, or `.env.local` overrides `.env`. |
| Signed out after a while | Tokens last 8 hours, and changing `TOKEN_SECRET` signs everyone out. Sign in again. |
| Photos or heatmaps don't show | Photos load from `backend/uploads` and `backend/results`. If you reset the database but kept old files, or deleted the folders, run the seed again. |
| `Failed to resolve import "react-zoom-pan-pinch"` | Run `npm install` in `frontend`. |
| Mock mode: `claimant2` gets "Policy ... was not valid" | On purpose: that mock claimant's policy ended on 31 Oct 2026, to show the refusal (like `claimant23` in the real seed). Use another claimant for a normal claim. |
| Every photo check says "The AI check failed" | Model weights missing. See section 2.2. |
