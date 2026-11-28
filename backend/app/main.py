import hashlib
import json
import os
from contextlib import asynccontextmanager
from datetime import date, timedelta, timezone
from pathlib import Path
from typing import Literal

from fastapi import BackgroundTasks, Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from . import models
from .auth import check_password, current_user, make_token, require_role
from .database import Base, engine, get_db
from .modules import ai_detector
from .pipeline import analyze_and_route
from .scoring import load_fusion
from .workflow import CLAIMANT_LABELS, STAFF_LABELS, change_status, log_new_claim

os.makedirs("uploads", exist_ok=True)
os.makedirs("results", exist_ok=True)
Base.metadata.create_all(bind=engine)
PRICE_LIST = Path(__file__).resolve().parents[2] / "data" / "price_list.json"
HISTORY_WINDOW_DAYS = 365        # "last year" = 12 months before the new incident
HISTORY_RATE_PER_CLAIM = 0.10    # 10% per earlier approved claim (draft; confirm with sir)
HISTORY_RATE_CAP = 0.30          # never more than 30%

@asynccontextmanager
async def lifespan(app):
    ai_detector.warm_up()
    load_fusion()
    yield

app = FastAPI(title="ClaimProof v2", lifespan=lifespan)
app.add_middleware(CORSMiddleware,
                   allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.mount("/results", StaticFiles(directory="results"), name="results")


# ---------- request shapes ----------

class LoginIn(BaseModel):
    email: str
    password: str

class ClaimIn(BaseModel):
    vehicle_id: int
    incident_date: date
    incident_time: str = ""
    location: str = ""
    severity: Literal["minor", "moderate", "severe"]
    description: str = ""

class ReplyIn(BaseModel):
    note: str

class QuoteItem(BaseModel):
    kind: Literal["part", "labour"]
    description: str
    quantity: int = Field(gt=0)
    unit_price: int = Field(ge=0)

class QuotationIn(BaseModel):
    items: list[QuoteItem] = Field(min_length=1)
    note: str = ""

class InfoIn(BaseModel):
    message: str

class DecisionIn(BaseModel):
    outcome: Literal["approved", "rejected", "fraud_review"]
    amount: int | None = None
    note: str = ""


# ---------- sign-in ----------

@app.post("/auth/login")
def login(data: LoginIn, db: Session = Depends(get_db)):
    user = db.query(models.User).filter_by(email=data.email.strip().lower()).first()
    if not user or not check_password(data.password, user.password_hash):
        raise HTTPException(401, "Wrong email or password")
    return {"token": make_token(user),
            "user": {"id": user.id, "name": user.name, "role": user.role}}


@app.get("/me")
def me(user: models.User = Depends(current_user)):
    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role}

# ---------- helpers ----------

def utc(dt):
    return dt.replace(tzinfo=timezone.utc).isoformat() if dt else None


def latest(db, model, claim_id):
    return db.query(model).filter_by(claim_id=claim_id).order_by(model.id.desc()).first()


def get_claim(db, claim_id):
    claim = db.get(models.Claim, claim_id)
    if not claim:
        raise HTTPException(404, "Claim not found")
    return claim


def image_results(db, claim):
    images = []
    for img in db.query(models.ImageRecord).filter_by(claim_id=claim.id).all():
        modules = []
        for r in db.query(models.AnalysisResult).filter_by(image_id=img.id).all():
            artifacts = {}
            if r.artifact_paths and r.artifact_paths.get("heatmap_path"):
                artifacts["heatmap_url"] = "/" + r.artifact_paths["heatmap_path"]
            modules.append({"module": r.module, "score": r.score,
                            "flags": r.flags or [], "artifacts": artifacts})
        images.append({"image_id": img.id, "url": "/" + img.file_path,
                       "duplicate_of": img.duplicate_of, "modules": modules})
    return images


def history(db, claim, labels):
    rows = db.query(models.StatusHistory).filter_by(claim_id=claim.id).order_by(models.StatusHistory.id).all()
    out = []
    for h in rows:
        who = db.get(models.User, h.user_id) if h.user_id else None
        out.append({"from": h.from_status, "to": h.to_status, "label": labels[h.to_status],
                    "by": f"{who.name} ({who.role})" if who else "System",
                    "at": utc(h.at), "note": h.note})
    return out


CLAIMANT_OUTCOME = {"approved": "approved", "rejected": "rejected",
                    "fraud_review": "further_review"}      # never say "fraud" to a claimant


def claimant_view(db, claim):
    vehicle = db.get(models.Vehicle, claim.vehicle_id)
    quote = latest(db, models.Quotation, claim.id)
    decision = latest(db, models.Decision, claim.id)
    return {
        "id": claim.id, "status": claim.status, "status_label": CLAIMANT_LABELS[claim.status],
        "vehicle": {"registration": vehicle.registration},
        "incident_date": claim.incident_date.isoformat(),
        "quotation_total": quote.total if quote else None,
        "decision": CLAIMANT_OUTCOME[decision.outcome] if decision else None,
        "approved_amount": decision.amount if decision and decision.outcome == "approved" else None,
        "info_request": claim.info_request,
        "timeline": [{"status": h["to"], "label": h["label"], "at": h["at"]}
                     for h in history(db, claim, CLAIMANT_LABELS)],
    }

def recent_approved_claims(db, claim):
    """Same claimant, approved, incident in the 12 months before this claim's incident."""
    start = claim.incident_date - timedelta(days=HISTORY_WINDOW_DAYS)
    earlier = db.query(models.Claim).filter(
        models.Claim.claimant_id == claim.claimant_id,
        models.Claim.id != claim.id,
        models.Claim.incident_date >= start,
        models.Claim.incident_date < claim.incident_date,
    ).all()
    result = []
    for c in earlier:
        d = latest(db, models.Decision, c.id)
        if d and d.outcome == "approved":
            result.append({"id": c.id, "incident_date": c.incident_date.isoformat(),
                           "approved_amount": d.amount, "status": c.status})
    return result


def payout_breakdown(db, claim, policy, quote, verdict):
    if not quote:
        return None
    base = max(0, quote.total - policy.deductible)
    recent = recent_approved_claims(db, claim)
    low_risk = verdict is not None and verdict.overall_risk == "low"
    rate = min(HISTORY_RATE_PER_CLAIM * len(recent), HISTORY_RATE_CAP) if low_risk else 0.0
    history_deduction = round(base * rate)
    suggested = max(0, min(base - history_deduction, policy.sum_insured))
    return {
        "quotation_total": quote.total, "deductible": policy.deductible,
        "after_deductible": base, "recent_approved_claims": len(recent),
        "history_rate": rate, "history_deduction": history_deduction,
        "sum_insured_cap": policy.sum_insured, "suggested_payout": suggested,
        "explanation": (f"{round(rate * 100)}% deducted for {len(recent)} approved claim(s) "
                        f"in the previous 12 months" if rate else "No claim-history deduction"),
    }
def staff_view(db, claim, for_insurer=False):
    vehicle = db.get(models.Vehicle, claim.vehicle_id)
    policy = db.get(models.Policy, vehicle.policy_id)
    claimant = db.get(models.User, claim.claimant_id)
    verdict = latest(db, models.Verdict, claim.id)
    quote = latest(db, models.Quotation, claim.id)
    previous = db.query(models.Claim).filter(models.Claim.claimant_id == claim.claimant_id,
                                             models.Claim.id != claim.id).all()
    previous_list = []                                                    # NEW
    for c in previous:
        d = latest(db, models.Decision, c.id)
        previous_list.append({"id": c.id, "incident_date": c.incident_date.isoformat(),
                              "status": c.status,
                              "approved_amount": d.amount if d and d.outcome == "approved" else None})
    out = {
        "id": claim.id, "status": claim.status, "status_label": STAFF_LABELS[claim.status],
        "claimant": {"id": claimant.id, "name": claimant.name},
        "vehicle": {"registration": vehicle.registration, "make": vehicle.make,
                    "model": vehicle.model, "year": vehicle.year},
        "incident_date": claim.incident_date.isoformat(), "incident_time": claim.incident_time,
        "location": claim.location, "severity": claim.severity, "description": claim.description,
        "risk_level": verdict.overall_risk if verdict else None,
        "risk_score": verdict.risk_score if verdict else None,
        "reasons": verdict.reasons if verdict else [],
        "fraud_flag": claim.fraud_flag,
        "images": image_results(db, claim),
        "previous_claims": previous_list,                                 # NEW: with amounts
        "recent_approved_claims": recent_approved_claims(db, claim),      # NEW
        "history": history(db, claim, STAFF_LABELS),
        "quotation": None,
    }
    if quote:
        items = db.query(models.QuotationItem).filter_by(quotation_id=quote.id).all()
        assessor = db.get(models.User, quote.assessor_id)
        out["quotation"] = {"total": quote.total, "note": quote.note,
                            "assessor": f"{assessor.name} (assessor)",
                            "items": [{"kind": i.kind, "description": i.description,
                                       "quantity": i.quantity, "unit_price": i.unit_price,
                                       "line_total": i.line_total} for i in items]}
    if for_insurer:
        out["policy"] = {"policy_number": policy.policy_number, "premium": policy.premium,
                         "deductible": policy.deductible, "sum_insured": policy.sum_insured,
                         "start_date": policy.start_date.isoformat(),
                         "end_date": policy.end_date.isoformat()}
        out["policy_valid_on_incident_date"] = policy.start_date <= claim.incident_date <= policy.end_date
        breakdown = payout_breakdown(db, claim, policy, quote, verdict)  # NEW
        out["payout_breakdown"] = breakdown                               # NEW
        out["suggested_payout"] = breakdown["suggested_payout"] if breakdown else None
        out["decisions"] = [{"outcome": d.outcome, "amount": d.amount, "note": d.note,
                             "at": utc(d.decided_at)}
                            for d in db.query(models.Decision).filter_by(claim_id=claim.id).all()]
    return out

# ---------- claimant ----------

@app.get("/me/policies")
def my_policies(user=Depends(require_role("claimant")), db: Session = Depends(get_db)):
    out = []
    for p in db.query(models.Policy).filter_by(holder_id=user.id).all():
        vehicles = db.query(models.Vehicle).filter_by(policy_id=p.id).all()
        out.append({"id": p.id, "policy_number": p.policy_number,
                    "start_date": p.start_date.isoformat(), "end_date": p.end_date.isoformat(),
                    "premium": p.premium, "deductible": p.deductible, "sum_insured": p.sum_insured,
                    "vehicles": [{"id": v.id, "registration": v.registration, "make": v.make,
                                  "model": v.model, "year": v.year} for v in vehicles]})
    return out


@app.post("/claims")
def submit_claim(data: ClaimIn, user=Depends(require_role("claimant")),
                 db: Session = Depends(get_db)):
    vehicle = db.get(models.Vehicle, data.vehicle_id)
    policy = db.get(models.Policy, vehicle.policy_id) if vehicle else None
    if not vehicle or policy.holder_id != user.id:
        raise HTTPException(400, "This vehicle is not on any of your policies")
    if not (policy.start_date <= data.incident_date <= policy.end_date):
        raise HTTPException(400, "Your policy was not valid on the incident date")
    claim = models.Claim(claimant_id=user.id, **data.model_dump())
    db.add(claim)
    db.flush()                         # gives the claim its id
    log_new_claim(db, claim, user)
    db.commit()
    db.refresh(claim)
    return {"id": claim.id, "status": claim.status}


@app.post("/claims/{claim_id}/images")
async def upload_images(claim_id: int, background: BackgroundTasks,
                        files: list[UploadFile] = File(...),
                        user=Depends(require_role("claimant")), db: Session = Depends(get_db)):
    claim = get_claim(db, claim_id)
    if claim.claimant_id != user.id:
        raise HTTPException(403, "You don't have access to this")
    if claim.status not in ("submitted", "more_info_requested"):
        raise HTTPException(409, "Photos can't be added at this stage")
    saved = []
    for f in files:
        data = await f.read()
        if not data.startswith(b"\xff\xd8"):
            raise HTTPException(400, f"{f.filename} is not a JPEG")
        h = hashlib.sha256(data).hexdigest()
        dup = db.query(models.ImageRecord).filter_by(sha256_hash=h).first()
        img = models.ImageRecord(claim_id=claim.id, file_path="", sha256_hash=h,
                                 duplicate_of=dup.id if dup else None)
        db.add(img)
        db.flush()
        path = f"uploads/{img.id}.jpg"
        with open(path, "wb") as out:
            out.write(data)
        img.file_path = path
        saved.append({"image_id": img.id, "duplicate_of": img.duplicate_of})
    db.commit()
    if claim.status == "submitted":
        background.add_task(analyze_and_route, claim.id)   # checks run after we reply
    return saved


@app.get("/me/claims")
def my_claims(user=Depends(require_role("claimant")), db: Session = Depends(get_db)):
    claims = db.query(models.Claim).filter_by(claimant_id=user.id).order_by(models.Claim.id.desc()).all()
    return [claimant_view(db, c) for c in claims]


@app.get("/me/claims/{claim_id}")
def my_claim(claim_id: int, user=Depends(require_role("claimant")), db: Session = Depends(get_db)):
    claim = get_claim(db, claim_id)
    if claim.claimant_id != user.id:
        raise HTTPException(403, "You don't have access to this")
    return claimant_view(db, claim)


@app.post("/claims/{claim_id}/reply")
def reply(claim_id: int, data: ReplyIn, user=Depends(require_role("claimant")),
          db: Session = Depends(get_db)):
    claim = get_claim(db, claim_id)
    if claim.claimant_id != user.id:
        raise HTTPException(403, "You don't have access to this")
    change_status(db, claim, "under_review", user, note=data.note)
    claim.info_request = None
    db.commit()
    return claimant_view(db, claim)

# ---------- assessor ----------

def my_assigned_claim(db, claim_id, user):
    claim = get_claim(db, claim_id)
    if claim.assessor_id != user.id:
        raise HTTPException(403, "This claim isn't assigned to you")
    return claim


@app.get("/assessor/claims")
def assessor_claims(user=Depends(require_role("assessor")), db: Session = Depends(get_db)):
    claims = db.query(models.Claim).filter_by(assessor_id=user.id).order_by(models.Claim.id.desc()).all()
    return [{"id": c.id, "status": c.status, "status_label": STAFF_LABELS[c.status],
             "incident_date": c.incident_date.isoformat(), "severity": c.severity} for c in claims]


@app.get("/assessor/claims/{claim_id}")
def assessor_claim(claim_id: int, user=Depends(require_role("assessor")),
                   db: Session = Depends(get_db)):
    return staff_view(db, my_assigned_claim(db, claim_id, user))


@app.get("/price-list")
def price_list(user=Depends(require_role("assessor", "insurer"))):
    return json.loads(PRICE_LIST.read_text()) if PRICE_LIST.exists() else []


@app.post("/claims/{claim_id}/quotation")
def submit_quotation(claim_id: int, data: QuotationIn, user=Depends(require_role("assessor")),
                     db: Session = Depends(get_db)):
    claim = my_assigned_claim(db, claim_id, user)
    total = sum(i.quantity * i.unit_price for i in data.items)      # the backend calculates
    change_status(db, claim, "assessed", user, note=f"Quotation total {total}")
    quote = models.Quotation(claim_id=claim.id, assessor_id=user.id, total=total, note=data.note)
    db.add(quote)
    db.flush()
    for i in data.items:
        db.add(models.QuotationItem(quotation_id=quote.id, kind=i.kind, description=i.description,
                                    quantity=i.quantity, unit_price=i.unit_price,
                                    line_total=i.quantity * i.unit_price))
    db.commit()
    return {"claim_id": claim.id, "total": total, "status": claim.status}


# ---------- insurer ----------

@app.get("/insurer/claims")
def insurer_claims(status: str | None = None, risk: Literal["low", "medium", "high"] | None = None,
                   user=Depends(require_role("insurer")), db: Session = Depends(get_db)):
    rows = []
    for c in db.query(models.Claim).all():
        v = latest(db, models.Verdict, c.id)
        item = {"id": c.id, "status": c.status, "status_label": STAFF_LABELS[c.status],
                "claimant": db.get(models.User, c.claimant_id).name,
                "incident_date": c.incident_date.isoformat(), "fraud_flag": c.fraud_flag,
                "risk_level": v.overall_risk if v else None,
                "risk_score": v.risk_score if v else None}
        if (status is None or c.status == status) and (risk is None or item["risk_level"] == risk):
            rows.append(item)
    # fraud flags first, then highest risk, then newest
    return sorted(rows, key=lambda r: (not r["fraud_flag"], -(r["risk_score"] or 0), -r["id"]))


@app.get("/insurer/claims/{claim_id}")
def insurer_claim(claim_id: int, user=Depends(require_role("insurer")),
                  db: Session = Depends(get_db)):
    return staff_view(db, get_claim(db, claim_id), for_insurer=True)


@app.post("/claims/{claim_id}/start-review")
def start_review(claim_id: int, user=Depends(require_role("insurer")),
                 db: Session = Depends(get_db)):
    claim = get_claim(db, claim_id)
    change_status(db, claim, "under_review", user)
    db.commit()
    return {"claim_id": claim.id, "status": claim.status}


@app.post("/claims/{claim_id}/request-info")
def request_info(claim_id: int, data: InfoIn, user=Depends(require_role("insurer")),
                 db: Session = Depends(get_db)):
    claim = get_claim(db, claim_id)
    change_status(db, claim, "more_info_requested", user, note=data.message)
    claim.info_request = data.message
    db.commit()
    return {"claim_id": claim.id, "status": claim.status}


@app.post("/claims/{claim_id}/decision")
def decide(claim_id: int, data: DecisionIn, user=Depends(require_role("insurer")),
           db: Session = Depends(get_db)):
    claim = get_claim(db, claim_id)
    if data.outcome == "approved" and not (data.amount and data.amount > 0):
        raise HTTPException(400, "Enter the approved amount")
    if data.outcome != "approved" and not data.note.strip():
        raise HTTPException(400, "A note is required to reject or send to fraud review")
    change_status(db, claim, "decided", user, note=data.note)
    db.add(models.Decision(claim_id=claim.id, insurer_id=user.id, outcome=data.outcome,
                           amount=data.amount if data.outcome == "approved" else None,
                           note=data.note))
    db.commit()
    return {"claim_id": claim.id, "status": claim.status, "outcome": data.outcome}


@app.post("/claims/{claim_id}/settle")
def settle(claim_id: int, user=Depends(require_role("insurer")), db: Session = Depends(get_db)):
    claim = get_claim(db, claim_id)
    decision = latest(db, models.Decision, claim.id)
    if not decision or decision.outcome != "approved":
        raise HTTPException(409, "Only approved claims can be settled")
    change_status(db, claim, "settled", user, note=f"Paid {decision.amount}")
    db.commit()
    return {"claim_id": claim.id, "status": claim.status}