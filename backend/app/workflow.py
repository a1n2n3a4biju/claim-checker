"""Claim status engine and workflow actions (owner: M3).

Every status change goes through change_status(): it allows only the moves in
contract section 2.3 (anything else is 409), checks the role (403) and writes
one status_history row (who, when, from, to, note).

The API endpoints in main.py and scripts/seed_demo.py both call the action
functions below, so the demo data goes through the real workflow.
"""
import hashlib
from datetime import date, timedelta
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy.orm import Session

from . import models, photo_checks
from .routing import route_claim

BACKEND_DIR = Path(__file__).resolve().parents[1]
UPLOAD_DIR = BACKEND_DIR / "uploads"

# ---------------------------------------------------------------- statuses (contract 2.2)

# key: (shown to staff, shown to claimant)
STATUSES = {
    "submitted":           ("Submitted", "Received"),
    "photos_checked":      ("Photos checked", "Received"),
    "awaiting_assessment": ("Awaiting assessment", "Being assessed"),
    "assessed":            ("Assessed", "Being assessed"),
    "under_review":        ("Under insurer review", "Under review"),
    "more_info_requested": ("More info requested", "We need more information"),
    "decided":             ("Decided", "Decision made"),
    "settled":             ("Settled", "Settled"),
}


def staff_label(status: str) -> str:
    return STATUSES[status][0]


def claimant_label(status: str) -> str:
    return STATUSES[status][1]


# ---------------------------------------------------------------- allowed moves (contract 2.3)

SYSTEM = "system"
TRANSITIONS = {
    (None, "submitted"): "claimant",
    ("submitted", "photos_checked"): SYSTEM,
    ("photos_checked", "awaiting_assessment"): SYSTEM,
    ("awaiting_assessment", "assessed"): "assessor",
    ("assessed", "under_review"): "insurer",
    ("under_review", "more_info_requested"): "insurer",
    ("more_info_requested", "under_review"): "claimant",
    ("under_review", "decided"): "insurer",
    ("decided", "settled"): "insurer",
}

OUTCOMES = ("approved", "rejected", "further_review")
SEVERITIES = ("minor", "moderate", "severe")
ITEM_KINDS = ("part", "labour")


def change_status(db: Session, claim: models.Claim, to: str,
                  actor: models.User | None, note: str = "") -> None:
    """Move a claim to a new status. actor=None means the system did it."""
    frm = claim.status if claim.id else None
    who = TRANSITIONS.get((frm, to))
    if who is None:
        frm_label = staff_label(frm) if frm else "new"
        raise HTTPException(409, f"A claim can't move from '{frm_label}' to "
                                 f"'{staff_label(to)}'. It is currently '{frm_label}'.")
    actor_role = actor.role if actor else SYSTEM
    if actor_role != who:
        raise HTTPException(403, "You don't have access to this")
    claim.status = to
    if claim.id is None:
        db.add(claim)                                  # a new claim
    db.flush()                                         # gives a new claim its id
    db.add(models.StatusHistory(claim_id=claim.id, from_status=frm, to_status=to,
                                user_id=actor.id if actor else None, note=note or ""))


# ---------------------------------------------------------------- helpers

def own_claim(claim: models.Claim | None, user: models.User) -> models.Claim:
    """The claim must exist (404) and belong to this claimant (403)."""
    if not claim:
        raise HTTPException(404, "Not found")
    if claim.claimant_id != user.id:
        raise HTTPException(403, "You don't have access to this")
    return claim


def assigned_claim(claim: models.Claim | None, user: models.User) -> models.Claim:
    """The claim must exist (404) and be assigned to this assessor (403)."""
    if not claim:
        raise HTTPException(404, "Not found")
    if claim.assessor_id != user.id:
        raise HTTPException(403, "You don't have access to this")
    return claim


def get_claim(db: Session, claim_id: int) -> models.Claim:
    claim = db.get(models.Claim, claim_id)
    if not claim:
        raise HTTPException(404, "Not found")
    return claim


# Claim-history deduction (team choice, see docs/CONTRACT.md "Payout breakdown").
# Each approved claim by the same claimant in the 12 months before this
# incident takes HISTORY_RATE_PER_CLAIM off the amount left after the
# deductible, up to HISTORY_RATE_MAX in total.
RECENT_DAYS = 365
HISTORY_RATE_PER_CLAIM = 0.05
HISTORY_RATE_MAX = 0.20


def rupees(n: int) -> str:
    """45000 -> '₹45,000', 1234567 -> '₹12,34,567' (Indian grouping)."""
    s = str(abs(int(n)))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        head = ",".join([head[max(0, i - 2):i] for i in range(len(head), 0, -2)][::-1])
        s = f"{head},{tail}"
    return ("-" if n < 0 else "") + "₹" + s


def recent_approved_claims(db: Session, claim: models.Claim) -> list[models.Claim]:
    """Approved claims by the same claimant with an incident in the RECENT_DAYS
    before this claim's incident (this claim itself not counted)."""
    since = claim.incident_date - timedelta(days=RECENT_DAYS)
    return (db.query(models.Claim)
              .filter(models.Claim.claimant_id == claim.claimant_id, models.Claim.id != claim.id,
                      models.Claim.decision == "approved",
                      models.Claim.incident_date >= since, models.Claim.incident_date <= claim.incident_date)
              .order_by(models.Claim.incident_date.desc(), models.Claim.id.desc()).all())


def payout_breakdown(db: Session, claim: models.Claim, quotation: models.Quotation | None) -> dict | None:
    """How the suggested payout is worked out. None until there is a quotation.

    after deductible = max(0, quotation total - deductible)
    history rate     = min(recent approved claims x 5%, 20%)
    suggested payout = min(after deductible - history deduction, sum insured)
    Only a suggestion: the insurer decides the final amount.
    """
    if not quotation:
        return None
    p = claim.policy
    after = max(0, quotation.total - p.deductible)
    recent = len(recent_approved_claims(db, claim))
    rate = round(min(recent * HISTORY_RATE_PER_CLAIM, HISTORY_RATE_MAX), 2)
    deduction = round(after * rate)
    suggested = max(0, min(after - deduction, p.sum_insured))

    text = (f"Quotation {rupees(quotation.total)} minus the {rupees(p.deductible)} deductible "
            f"leaves {rupees(after)}. ")
    if recent:
        text += (f"The claimant had {recent} approved claim{'s' if recent != 1 else ''} in the last 12 months, "
                 f"so {round(rate * 100)}% ({rupees(deduction)}) is taken off. ")
    else:
        text += "No approved claims in the last 12 months, so nothing is taken off for claim history. "
    if after - deduction > p.sum_insured:
        text += f"This is more than the sum insured, so it is capped at {rupees(p.sum_insured)}. "
    text += f"Suggested payout: {rupees(suggested)}."

    return {"quotation_total": quotation.total, "deductible": p.deductible, "after_deductible": after,
            "recent_approved_claims": recent, "history_rate": rate, "history_deduction": deduction,
            "sum_insured": p.sum_insured, "suggested_payout": suggested, "explanation": text}


def suggested_payout(db: Session, claim: models.Claim, quotation: models.Quotation | None) -> int | None:
    """The breakdown's suggested payout, or None without a quotation. Only a suggestion."""
    b = payout_breakdown(db, claim, quotation)
    return b["suggested_payout"] if b else None


def policy_valid_on(policy: models.Policy, day: date) -> bool:
    return policy.start_date <= day <= policy.end_date


# ---------------------------------------------------------------- claimant actions

def create_claim(db: Session, claimant: models.User, data: dict) -> models.Claim:
    """data: vehicle_id, incident_date (date), incident_time, location, severity, description."""
    vehicle = db.get(models.Vehicle, data["vehicle_id"])
    if not vehicle or vehicle.policy.user_id != claimant.id:
        raise HTTPException(400, "This vehicle is not on any of your policies")
    policy = vehicle.policy
    incident = data["incident_date"]
    if incident > date.today():
        raise HTTPException(400, "The incident date can't be in the future")
    if not policy_valid_on(policy, incident):
        raise HTTPException(400, f"Policy {policy.policy_number} was not valid on {incident.isoformat()} "
                                 f"(valid {policy.start_date.isoformat()} to {policy.end_date.isoformat()})")
    if data["severity"] not in SEVERITIES:
        raise HTTPException(400, f"severity must be one of {', '.join(SEVERITIES)}")

    claim = models.Claim(claimant_id=claimant.id, vehicle_id=vehicle.id, policy_id=policy.id,
                         incident_date=incident, incident_time=data["incident_time"],
                         location=data["location"], severity=data["severity"],
                         description=data["description"])
    change_status(db, claim, "submitted", claimant, "Claim submitted")   # (new) -> submitted
    return claim


def save_images(db: Session, claim: models.Claim, files: list[tuple[str, bytes]]) -> list[models.ImageRecord]:
    """Store JPEG photos for a claim. files: [(filename, bytes)]. Checks run separately."""
    if not files:
        raise HTTPException(400, "Choose at least one JPEG photo")
    UPLOAD_DIR.mkdir(exist_ok=True)
    saved = []
    for filename, data in files:
        if not data.startswith(b"\xff\xd8"):          # every JPEG starts with these bytes
            raise HTTPException(400, f"{filename} is not a JPEG photo")
    for filename, data in files:
        h = hashlib.sha256(data).hexdigest()
        dup = db.query(models.ImageRecord).filter_by(sha256_hash=h).first()
        img = models.ImageRecord(claim_id=claim.id, file_path="", sha256_hash=h,
                                 duplicate_of=dup.id if dup else None)
        db.add(img)
        db.flush()                                    # gives img an id
        (UPLOAD_DIR / f"{img.id}.jpg").write_bytes(data)
        img.file_path = f"uploads/{img.id}.jpg"
        saved.append(img)
    return saved


def upload_photos(db: Session, claim: models.Claim, claimant: models.User,
                  files: list[tuple[str, bytes]]) -> list[models.ImageRecord]:
    own_claim(claim, claimant)
    if claim.status != "submitted":
        raise HTTPException(409, "Photos can only be added while the claim is 'Submitted'. "
                                 "To send more photos later, reply to an info request.")
    return save_images(db, claim, files)


def reply_to_info_request(db: Session, claim: models.Claim, claimant: models.User,
                          note: str, files: list[tuple[str, bytes]]) -> list[models.ImageRecord]:
    own_claim(claim, claimant)
    if claim.status != "more_info_requested":
        raise HTTPException(409, "You can only reply when we have asked for more information")
    if not note.strip() and not files:
        raise HTTPException(422, "note: write a reply or add photos")
    images = save_images(db, claim, files) if files else []
    extra = f" ({len(images)} photo{'s' if len(images) != 1 else ''} added)" if images else ""
    change_status(db, claim, "under_review", claimant, (note.strip() + extra).strip())
    return images


# ---------------------------------------------------------------- photo checks + routing (system)

def open_claims_per_assessor(db: Session) -> list[dict]:
    """Open claims = assigned and still waiting for a quotation."""
    assessors = db.query(models.User).filter_by(role="assessor").order_by(models.User.id).all()
    return [{"id": a.id,
             "open_claims": db.query(models.Claim).filter_by(assessor_id=a.id,
                                                             status="awaiting_assessment").count()}
            for a in assessors]


def run_photo_checks(db: Session, claim_id: int) -> models.Claim:
    """Check every photo not yet checked, update the claim's risk, and, if the
    claim is still 'submitted', move it on and assign an assessor."""
    claim = get_claim(db, claim_id)
    images = db.query(models.ImageRecord).filter_by(claim_id=claim.id).order_by(models.ImageRecord.id).all()
    if not images:
        raise HTTPException(400, "Upload at least one photo first")

    reasons = list(claim.reasons or [])
    for img in images:
        if img.checked:
            continue
        if img.duplicate_of:
            reasons.append(f"Photo {img.id} is identical to an earlier upload (photo {img.duplicate_of})")
        db.query(models.AnalysisResult).filter_by(image_id=img.id).delete()
        results, problems = photo_checks.run_all_modules(str(BACKEND_DIR / img.file_path))
        reasons.extend(problems)
        for r in results:
            artifacts = dict(r.get("artifacts") or {})
            # module paths may be absolute or relative; keep them relative to backend/
            if artifacts.get("heatmap_path"):
                hp = Path(artifacts["heatmap_path"])
                artifacts["heatmap_path"] = (hp.relative_to(BACKEND_DIR) if hp.is_absolute() else hp).as_posix()
            db.add(models.AnalysisResult(image_id=img.id, module=r["module"], score=r["score"],
                                         flags=r.get("flags") or [], artifact_paths=artifacts))
            reasons.extend(r.get("flags") or [])
        score = photo_checks.fuse({r["module"]: r["score"] for r in results})
        img.risk_score = score
        img.risk_level = photo_checks.risk_level(score) if score is not None else None
        img.checked = True

    scores = [i.risk_score for i in images if i.risk_score is not None]
    claim_score = max(scores) if scores else 0.0            # claim = riskiest photo
    claim.risk_score = round(claim_score, 2)
    claim.risk_level = photo_checks.risk_level(claim_score)
    claim.reasons = list(dict.fromkeys(reasons))[:5]         # no repeats, keep order
    if claim.risk_level == "high":
        claim.fraud_flag = True

    if claim.status == "submitted":
        change_status(db, claim, "photos_checked", None,
                      f"{len(images)} photo{'s' if len(images) != 1 else ''} checked")
        route = route_claim(claim.risk_level, open_claims_per_assessor(db))
        claim.fraud_flag = route["fraud_flag"]
        claim.assessor_id = route["assessor_id"]
        assessor = db.get(models.User, route["assessor_id"])
        change_status(db, claim, "awaiting_assessment", None, f"Assigned to {assessor.name}")
    db.commit()
    return claim


def run_photo_checks_in_background(claim_id: int) -> None:
    """For FastAPI BackgroundTasks: uses its own database session."""
    from .database import SessionLocal
    db = SessionLocal()
    try:
        run_photo_checks(db, claim_id)
    except Exception as e:
        db.rollback()
        print(f"[photo checks] claim {claim_id} failed: {type(e).__name__}: {e}")
    finally:
        db.close()


# ---------------------------------------------------------------- assessor actions

def submit_quotation(db: Session, claim: models.Claim, assessor: models.User,
                     items: list[dict], note: str) -> models.Quotation:
    assigned_claim(claim, assessor)
    if not items:
        raise HTTPException(422, "items: add at least one part or labour row")
    for i, it in enumerate(items, 1):
        if it["kind"] not in ITEM_KINDS:
            raise HTTPException(422, f"items[{i}].kind must be 'part' or 'labour'")
        if not str(it["description"]).strip():
            raise HTTPException(422, f"items[{i}].description is required")
        if it["quantity"] < 1 or it["unit_price"] < 0:
            raise HTTPException(422, f"items[{i}]: quantity must be at least 1 and unit_price not negative")
    change_status(db, claim, "assessed", assessor, note)      # 409 if not awaiting_assessment
    total = sum(int(it["quantity"]) * int(it["unit_price"]) for it in items)   # backend calculates
    q = models.Quotation(claim_id=claim.id, assessor_id=assessor.id, total=total, note=note or "")
    db.add(q)
    db.flush()
    for it in items:
        db.add(models.QuotationItem(quotation_id=q.id, kind=it["kind"], description=it["description"].strip(),
                                    quantity=int(it["quantity"]), unit_price=int(it["unit_price"])))
    return q


# ---------------------------------------------------------------- insurer actions

def start_review(db: Session, claim: models.Claim, insurer: models.User) -> None:
    change_status(db, claim, "under_review", insurer, "Review started")


def request_info(db: Session, claim: models.Claim, insurer: models.User, message: str) -> None:
    if not message.strip():
        raise HTTPException(422, "message: write what you need from the claimant")
    change_status(db, claim, "more_info_requested", insurer, message.strip())
    claim.info_request = message.strip()


def decide(db: Session, claim: models.Claim, insurer: models.User,
           outcome: str, amount: int | None, note: str) -> None:
    if outcome not in OUTCOMES:
        raise HTTPException(422, f"outcome must be one of {', '.join(OUTCOMES)}")
    if outcome == "approved" and (amount is None or amount <= 0):
        raise HTTPException(422, "amount: enter the approved amount in whole rupees")
    if outcome != "approved" and not (note or "").strip():
        raise HTTPException(422, "note: a note is required to reject or send for further review")
    change_status(db, claim, "decided", insurer, f"{outcome}" + (f": {note.strip()}" if note and note.strip() else ""))
    claim.decision = outcome
    claim.approved_amount = int(amount) if outcome == "approved" else None
    claim.decision_note = (note or "").strip()


def settle(db: Session, claim: models.Claim, insurer: models.User) -> None:
    if claim.status == "decided" and claim.decision != "approved":
        raise HTTPException(409, "Only an approved claim can be marked as settled")
    change_status(db, claim, "settled", insurer, f"Paid {claim.approved_amount}" if claim.approved_amount else "")
