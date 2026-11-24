# Claim Checker: frontend (E7)

React web app for the claim photo manipulation checker. Owner: M1.

Anyone can **create a claim and upload photos**. Each photo is run through the edit forensics
and AI-detection checks by the backend, and the app shows the claim's **risk level, the reasons,
visual evidence (heatmaps) and AI scores**. A reviewer then **approves or escalates** the claim.
The tool never rejects a claim on its own.

## Pages

| Page | Address | What it does |
|---|---|---|
| Review queue | `/claims` | All claims, highest risk first, with a risk-level filter (All / High / Medium / Low / Not analyzed). The filter is kept in the address, e.g. `/claims?risk=high` |
| New claim | `/claims/new` | Claim form (claimant, incident date, description) and multi-photo upload with previews. JPEG only, up to 10 photos, 10 MB each. Shows progress: creating, uploading, running checks |
| Results | `/claims/:id` | Risk score and level, what happens next, reasons, reviewer decision panel, photo picker (riskiest photo first), evidence viewer (heatmap over original with a slider) and every check's score |

## Requirements

- **Node.js 20 or newer** (`node -v` to check)
- The **backend** running for real data (see the main README). The frontend also has a mock mode that needs no backend.

## Setup

From the `frontend` folder:

```powershell
npm install
Copy-Item .env.example .env.local
```

`.env.local` holds your local settings and is not committed:

| Setting | Default | Meaning |
|---|---|---|
| `VITE_API_URL` | `http://localhost:8000` | Address of the FastAPI backend |
| `VITE_USE_MOCK` | `false` | `true` uses built-in sample claims instead of the backend |

Restart `npm run dev` after changing `.env.local`; Vite only reads it at startup.

## Run

**1. Start the backend** (separate terminal, from the project root, venv active):

```powershell
cd backend
python -m uvicorn app.main:app --reload
```

Start it from the `backend` folder, so it finds its database, `uploads` and `results` folders.
Wait for `Application startup complete`.

**2. Start the frontend:**

```powershell
cd frontend
npm run dev
```

Open **http://localhost:5173**.

The first analysis after the backend starts takes up to a minute while the AI models load.
After that, each photo takes about 8–9 seconds on CPU.

## Mock mode

Set `VITE_USE_MOCK=true` in `.env.local` and restart `npm run dev`. The app then shows five
sample claims covering every case (high, medium, low, escalated, not analyzed, duplicate photo,
several photos). The navigation rail shows "Showing sample data". The placeholder photo is a
drawing (`public/mock/claim_photo.svg`), not a dataset image.

## Backend endpoints used

| Endpoint | Used by |
|---|---|
| `POST /claims` | New claim |
| `POST /claims/{id}/images` (multipart field `files`) | New claim |
| `POST /claims/{id}/analyze` | New claim, and "Run checks" on the results page |
| `GET /claims?risk=low\|medium\|high` | Review queue and its filter |
| `GET /claims/{id}/results` | Results page |
| `PATCH /claims/{id}/decision` with `{"decision": "approved"\|"escalated", "note": "..."}` | Reviewer decision panel |

Images and heatmaps are loaded from the backend (`VITE_API_URL` + the path it returns).

## Project structure

```
src/
├── api/claims.js              all backend calls; switches between real API and mock data
├── mocks/mockData.js          sample claims for mock mode, in the backend's format
├── pages/
│   ├── ClaimsList.jsx         review queue with risk filter (E7.4)
│   ├── NewClaim.jsx           claim form and photo upload (E7.2)
│   └── Results.jsx            results page (E7.3)
├── components/
│   ├── EvidenceViewer.jsx     heatmap-over-photo viewer with slider
│   ├── ReviewPanel.jsx        approve / escalate with a note (E7.5)
│   └── SafeImage.jsx          image with a message instead of a broken icon
├── utils/
│   ├── risk.js                risk thresholds (fallback only) and status wording
│   └── modules.js             plain-language labels for each check
├── theme.js                   colours, type and component styles
├── App.jsx                    layout and routing
└── main.jsx                   entry point
```

**Risk levels come from the backend.** `utils/risk.js` keeps a copy of the fusion thresholds
(0.45 / 0.688) only as a fallback for colouring scores; update it if the fusion model is retrained.

## Design notes

- Colours: red, amber and green are used **only** for risk, so colour always carries meaning.
  Brand colour is teal (`#0E5E6F`). Type: Public Sans.
- Every page has loading and error states; a failed request shows a message with **Try again**.
- Missing photos or heatmaps show a short message instead of a broken image.
- The upload page accepts JPEG only, matching the backend and the detection modules.

## Troubleshooting

| Problem | Fix |
|---|---|
| Blank page | Press F12, open the Console tab, read the first red error |
| "Network Error" | The backend isn't running, or `VITE_API_URL` is wrong |
| Changes to `.env.local` ignored | Stop and restart `npm run dev` |
| No heatmaps | Check the backend terminal for errors during analysis |