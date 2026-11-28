"""ClaimProof v2 API (owner: M3). Endpoints follow docs/CONTRACT.md section 3.

Run from the backend folder:  uvicorn app.main:app --reload
"""
import json
import os
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import (BackgroundTasks, Depends, FastAPI, File, Form, HTTPException,
                     Request, UploadFile)
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from . import auth, models, photo_checks, workflow
from .auth import current_user, require_role
from .database import BACKEND_DIR, Base, engine, get_db
from .workflow import claimant_label, staff_label

PRICE_LIST_PATH = BACKEND_DIR.parent / "data" / "price_list.json"

(BACKEND_DIR / "uploads").mkdir(exist_ok=True)
(BACKEND_DIR / "results").mkdir(exist_ok=True)
Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app):
    if os.getenv("SKIP_PHOTO_MODELS") != "1":     # tests can skip loading the AI models
        photo_checks.load()
    yield


app = FastAPI(title="ClaimProof v2", lifespan=lifespan)
app.add_middleware(CORSMiddleware,
                   allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])
app.mount("/uploads", StaticFiles(directory=BACKEND_DIR / "uploads"), name="uploads")
app.mount("/results", StaticFiles(directory=BACKEND_DIR / "results"), name="results")


@app.exception_handler(RequestValidationError)
async def readable_422(request: Request, exc: RequestValidationError):
    """Contract 2.7: every error is {"detail": "a readable message"}; 422 names the field."""
    parts = []
    for e in exc.errors():
        field = ".".join(str(x) for x in e.get("loc", []) if x not in ("body", "query", "path", "form"))
        parts.append(f"{field}: {e.get('msg', 'invalid')}" if field else e.get("msg", "invalid"))
    return JSONResponse(status_code=422, content={"detail": "; ".join(parts) or "Invalid input"})


# ---------------------------------------------------------------- formatting (contract 2.5)

def iso(dt: datetime | None) -> str | None:
    """ISO date-time in UTC ending in +00:00."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def day(d: date | None) -> str | None:
    return d.isoformat() if d else None


def person(user: models.User | None) -> str:
    return f"{user.name} ({user.role})" if user else "System"


def quotation_of(db: Session, claim: models.Claim) -> models.Quotation | None:
    return db.query(models.Quotation).filter_by(claim_id=claim.id).first()


def history_rows(db: Session, claim: models.Claim) -> list[models.StatusHistory]:
    return (db.query(models.StatusHistory).filter_by(claim_id=claim.id)
              .order_by(models.StatusHistory.at, models.StatusHistory.id).all())


def vehicle_out(v: models.Vehicle) -> dict:
    return {"id": v.id, "registration": v.registration, "make": v.make, "model": v.model, "year": v.year}


def policy_out(p: models.Policy) -> dict:
    return {"id": p.id, "policy_number": p.policy_number, "start_date": day(p.start_date),
            "end_date": day(p.end_date), "premium": p.premium, "deductible": p.deductible,
            "sum_insured": p.sum_insured}


# ---------------------------------------------------------------- claimant view: never any risk fields

def claimant_claim(db: Session, claim: models.Claim) -> dict:
    q = quotation_of(db, claim)
    return {
        "id": claim.id,
        "status": claim.status,
        "status_label": claimant_label(claim.status),
        "vehicle": {"registration": claim.vehicle.registration, "make": claim.vehicle.make,
                    "model": claim.vehicle.model},
        "incident_date": day(claim.incident_date),
        "incident_time": claim.incident_time,
        "location": claim.location,
        "severity": claim.severity,
        "description": claim.description,
        "created_at": iso(claim.created_at),
        "quotation_total": q.total if q else None,
        "decision": claim.decision,
        "approved_amount": claim.approved_amount,
        "info_request": claim.info_request if claim.status == "more_info_requested" else None,
        "timeline": [{"status": h.to_status, "label": claimant_label(h.to_status), "at": iso(h.at)}
                     for h in history_rows(db, claim)],
    }


def claimant_summary(claim: models.Claim) -> dict:
    return {"id": claim.id, "status": claim.status, "status_label": claimant_label(claim.status),
            "vehicle": {"registration": claim.vehicle.registration, "make": claim.vehicle.make,
                        "model": claim.vehicle.model},
            "incident_date": day(claim.incident_date), "created_at": iso(claim.created_at)}


# ---------------------------------------------------------------- staff views

def images_out(db: Session, claim: models.Claim) -> list[dict]:
    out = []
    for img in db.query(models.ImageRecord).filter_by(claim_id=claim.id).order_by(models.ImageRecord.id):
        modules = []
        for r in db.query(models.AnalysisResult).filter_by(image_id=img.id).order_by(models.AnalysisResult.id):
            artifacts = {}
            if r.artifact_paths and r.artifact_paths.get("heatmap_path"):
                artifacts["heatmap_url"] = "/" + r.artifact_paths["heatmap_path"].lstrip("/")
            modules.append({"module": r.module, "score": round(r.score, 3),
                            "flags": r.flags or [], "artifacts": artifacts})
        out.append({"image_id": img.id, "url": "/" + img.file_path, "uploaded_at": iso(img.uploaded_at),
                    "duplicate_of": img.duplicate_of, "checked": bool(img.checked),
                    "risk_score": img.risk_score, "risk_level": img.risk_level, "modules": modules})
    return out


def staff_summary(db: Session, claim: models.Claim) -> dict:
    q = quotation_of(db, claim)
    return {"id": claim.id, "status": claim.status, "status_label": staff_label(claim.status),
            "claimant": claim.claimant.name,
            "vehicle": {"registration": claim.vehicle.registration, "make": claim.vehicle.make,
                        "model": claim.vehicle.model},
            "incident_date": day(claim.incident_date), "severity": claim.severity,
            "created_at": iso(claim.created_at),
            "risk_level": claim.risk_level, "risk_score": claim.risk_score,
            "fraud_flag": bool(claim.fraud_flag),
            "assessor": claim.assessor.name if claim.assessor else None,
            "quotation_total": q.total if q else None}


def past_claims(db: Session, claim: models.Claim) -> list[dict]:
    """Other claims by the same claimant or on the same vehicle."""
    others = (db.query(models.Claim)
                .filter(models.Claim.id != claim.id)
                .filter((models.Claim.claimant_id == claim.claimant_id) |
                        (models.Claim.vehicle_id == claim.vehicle_id))
                .order_by(models.Claim.created_at.desc()).all())
    return [{"id": c.id, "incident_date": day(c.incident_date), "status": c.status,
             "status_label": staff_label(c.status), "registration": c.vehicle.registration,
             "same_vehicle": c.vehicle_id == claim.vehicle_id, "decision": c.decision,
             "approved_amount": c.approved_amount} for c in others]


def recent_approved(db: Session, claim: models.Claim) -> list[dict]:
    """Approved claims by this claimant in the 12 months before this incident."""
    return [{"id": c.id, "incident_date": day(c.incident_date), "registration": c.vehicle.registration,
             "approved_amount": c.approved_amount, "status": c.status, "status_label": staff_label(c.status)}
            for c in workflow.recent_approved_claims(db, claim)]


def staff_claim(db: Session, claim: models.Claim) -> dict:
    q = quotation_of(db, claim)
    data = claimant_claim(db, claim)
    data.update({
        "status_label": staff_label(claim.status),
        "claimant": {"id": claim.claimant.id, "name": claim.claimant.name, "email": claim.claimant.email},
        "vehicle": vehicle_out(claim.vehicle),
        "info_request": claim.info_request,
        "decision_note": claim.decision_note,
        "risk_level": claim.risk_level,
        "risk_score": claim.risk_score,
        "fraud_flag": bool(claim.fraud_flag),
        "reasons": claim.reasons or [],
        "images": images_out(db, claim),
        "assessor": person(claim.assessor) if claim.assessor else None,
        "quotation": ({"total": q.total, "note": q.note, "assessor": person(q.assessor), "created_at": iso(q.created_at),
                       "items": [{"kind": i.kind, "description": i.description, "quantity": i.quantity,
                                  "unit_price": i.unit_price, "amount": i.quantity * i.unit_price}
                                 for i in q.items]} if q else None),
        "previous_claims": past_claims(db, claim),
        "recent_approved_claims": recent_approved(db, claim),
        "history": [{"from": h.from_status, "to": h.to_status, "by": person(h.user), "at": iso(h.at),
                     "note": h.note or ""} for h in history_rows(db, claim)],
    })
    data["timeline"] = [{"status": h["to"], "label": staff_label(h["to"]), "at": h["at"]} for h in data["history"]]
    return data


def insurer_claim(db: Session, claim: models.Claim) -> dict:
    data = staff_claim(db, claim)
    breakdown = workflow.payout_breakdown(db, claim, quotation_of(db, claim))
    data.update({
        "policy": policy_out(claim.policy),
        "payout_breakdown": breakdown,
        "suggested_payout": breakdown["suggested_payout"] if breakdown else None,
        "policy_valid_on_incident_date": workflow.policy_valid_on(claim.policy, claim.incident_date),
    })
    return data


# ---------------------------------------------------------------- request bodies

class LoginIn(BaseModel):
    email: str
    password: str


class RegisterIn(BaseModel):
    name: str
    email: str
    password: str


class ClaimIn(BaseModel):
    vehicle_id: int
    incident_date: date
    incident_time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$", examples=["14:30"])
    location: str = Field(min_length=1)
    severity: Literal["minor", "moderate", "severe"]
    description: str = Field(min_length=1)


class ItemIn(BaseModel):
    kind: Literal["part", "labour"]
    description: str = Field(min_length=1)
    quantity: int = Field(ge=1)
    unit_price: int = Field(ge=0)


class QuotationIn(BaseModel):
    items: list[ItemIn] = Field(min_length=1)
    note: str = ""


class InfoRequestIn(BaseModel):
    message: str = Field(min_length=1)


class DecisionIn(BaseModel):
    outcome: Literal["approved", "rejected", "further_review"]
    amount: int | None = None
    note: str = ""


async def read_files(files: list[UploadFile] | None) -> list[tuple[str, bytes]]:
    return [(f.filename or "photo", await f.read()) for f in (files or []) if f.filename]


# ---------------------------------------------------------------- endpoints: anyone

@app.get("/")
def home():
    return {"status": "ok", "app": "ClaimProof v2", "docs": "/docs"}


@app.post("/auth/login")
def login(data: LoginIn, db: Session = Depends(get_db)):
    return auth.login(db, data.email, data.password)


@app.post("/auth/register", status_code=201)
def register(data: RegisterIn, db: Session = Depends(get_db)):
    """New customer account (always a claimant); returns token and user, like /auth/login."""
    return auth.register(db, data.name, data.email, data.password)


@app.get("/me")
def me(user: models.User = Depends(current_user)):
    return auth.user_out(user)


# ---------------------------------------------------------------- endpoints: claimant

claimant_only = require_role("claimant")
assessor_only = require_role("assessor")
insurer_only = require_role("insurer")


@app.get("/me/policies")
def my_policies(user: models.User = Depends(claimant_only), db: Session = Depends(get_db)):
    policies = db.query(models.Policy).filter_by(user_id=user.id).order_by(models.Policy.id).all()
    return [{**policy_out(p), "vehicles": [vehicle_out(v) for v in p.vehicles]} for p in policies]


@app.post("/claims", status_code=201)
def create_claim(data: ClaimIn, user: models.User = Depends(claimant_only), db: Session = Depends(get_db)):
    claim = workflow.create_claim(db, user, data.model_dump())
    db.commit()
    return claimant_claim(db, claim)


@app.post("/claims/{claim_id}/images", status_code=201)
async def upload_images(claim_id: int, background: BackgroundTasks, files: list[UploadFile] = File(...),
                        user: models.User = Depends(claimant_only), db: Session = Depends(get_db)):
    claim = db.get(models.Claim, claim_id)
    images = workflow.upload_photos(db, claim, user, await read_files(files))
    db.commit()
    background.add_task(workflow.run_photo_checks_in_background, claim_id)   # checks start after the upload
    return [{"image_id": i.id, "url": "/" + i.file_path} for i in images]


@app.get("/me/claims")
def my_claims(user: models.User = Depends(claimant_only), db: Session = Depends(get_db)):
    claims = (db.query(models.Claim).filter_by(claimant_id=user.id)
                .order_by(models.Claim.created_at.desc(), models.Claim.id.desc()).all())
    return [claimant_summary(c) for c in claims]


@app.get("/me/claims/{claim_id}")
def my_claim(claim_id: int, user: models.User = Depends(claimant_only), db: Session = Depends(get_db)):
    return claimant_claim(db, workflow.own_claim(db.get(models.Claim, claim_id), user))


@app.post("/claims/{claim_id}/reply")
async def reply(claim_id: int, background: BackgroundTasks, note: str = Form(""),
                files: list[UploadFile] | None = File(None),
                user: models.User = Depends(claimant_only), db: Session = Depends(get_db)):
    claim = db.get(models.Claim, claim_id)
    images = workflow.reply_to_info_request(db, claim, user, note, await read_files(files))
    db.commit()
    if images:
        background.add_task(workflow.run_photo_checks_in_background, claim_id)
    return claimant_claim(db, claim)


# ---------------------------------------------------------------- endpoints: assessor

@app.get("/assessor/claims")
def assessor_claims(user: models.User = Depends(assessor_only), db: Session = Depends(get_db)):
    claims = (db.query(models.Claim).filter_by(assessor_id=user.id)
                .order_by(models.Claim.created_at.desc(), models.Claim.id.desc()).all())
    return [staff_summary(db, c) for c in claims]


@app.get("/assessor/claims/{claim_id}")
def assessor_claim(claim_id: int, user: models.User = Depends(assessor_only), db: Session = Depends(get_db)):
    return staff_claim(db, workflow.assigned_claim(db.get(models.Claim, claim_id), user))


@app.post("/claims/{claim_id}/quotation")
def submit_quotation(claim_id: int, data: QuotationIn, user: models.User = Depends(assessor_only),
                     db: Session = Depends(get_db)):
    claim = db.get(models.Claim, claim_id)
    workflow.submit_quotation(db, claim, user, [i.model_dump() for i in data.items], data.note)
    db.commit()
    return staff_claim(db, claim)


@app.get("/price-list")
def price_list(user: models.User = Depends(require_role("assessor", "insurer"))):
    if not PRICE_LIST_PATH.exists():
        raise HTTPException(404, "Not found: data/price_list.json is missing")
    return json.loads(PRICE_LIST_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- endpoints: insurer

RISK_ORDER = {"high": 0, "medium": 1, "low": 2, None: 3}


@app.get("/insurer/claims")
def insurer_claims(status: str | None = None, risk: Literal["low", "medium", "high"] | None = None,
                   user: models.User = Depends(insurer_only), db: Session = Depends(get_db)):
    if status and status not in workflow.STATUSES:
        raise HTTPException(400, f"Unknown status '{status}'")
    query = db.query(models.Claim)
    if status:
        query = query.filter_by(status=status)
    if risk:
        query = query.filter_by(risk_level=risk)
    claims = query.all()
    # fraud flags first, then high risk, then newest
    claims.sort(key=lambda c: (c.created_at or datetime.min.replace(tzinfo=timezone.utc)), reverse=True)
    claims.sort(key=lambda c: (not c.fraud_flag, RISK_ORDER.get(c.risk_level, 3)))
    return [staff_summary(db, c) for c in claims]


@app.get("/insurer/claims/{claim_id}")
def insurer_claim_view(claim_id: int, user: models.User = Depends(insurer_only), db: Session = Depends(get_db)):
    return insurer_claim(db, workflow.get_claim(db, claim_id))


@app.post("/claims/{claim_id}/start-review")
def start_review(claim_id: int, user: models.User = Depends(insurer_only), db: Session = Depends(get_db)):
    claim = workflow.get_claim(db, claim_id)
    workflow.start_review(db, claim, user)
    db.commit()
    return insurer_claim(db, claim)


@app.post("/claims/{claim_id}/request-info")
def request_info(claim_id: int, data: InfoRequestIn, user: models.User = Depends(insurer_only),
                 db: Session = Depends(get_db)):
    claim = workflow.get_claim(db, claim_id)
    workflow.request_info(db, claim, user, data.message)
    db.commit()
    return insurer_claim(db, claim)


@app.post("/claims/{claim_id}/decision")
def decision(claim_id: int, data: DecisionIn, user: models.User = Depends(insurer_only),
             db: Session = Depends(get_db)):
    claim = workflow.get_claim(db, claim_id)
    workflow.decide(db, claim, user, data.outcome, data.amount, data.note)
    db.commit()
    return insurer_claim(db, claim)


@app.post("/claims/{claim_id}/settle")
def settle(claim_id: int, user: models.User = Depends(insurer_only), db: Session = Depends(get_db)):
    claim = workflow.get_claim(db, claim_id)
    workflow.settle(db, claim, user)
    db.commit()
    return insurer_claim(db, claim)
