from fastapi import HTTPException

from . import models

STAFF_LABELS = {
    "submitted": "Submitted", "photos_checked": "Photos checked",
    "awaiting_assessment": "Awaiting assessment", "assessed": "Assessed",
    "under_review": "Under insurer review", "more_info_requested": "More info requested",
    "decided": "Decided", "settled": "Settled",
}

CLAIMANT_LABELS = {
    "submitted": "Received", "photos_checked": "Received",
    "awaiting_assessment": "Being assessed", "assessed": "Being assessed",
    "under_review": "Under review", "more_info_requested": "We need more information",
    "decided": "Decision made", "settled": "Settled",
}

# (from, to): who may make this move
ALLOWED = {
    ("submitted", "photos_checked"): "system",
    ("photos_checked", "awaiting_assessment"): "system",
    ("awaiting_assessment", "assessed"): "assessor",
    ("assessed", "under_review"): "insurer",
    ("under_review", "more_info_requested"): "insurer",
    ("more_info_requested", "under_review"): "claimant",
    ("under_review", "decided"): "insurer",
    ("decided", "settled"): "insurer",
}


def log_new_claim(db, claim: models.Claim, user: models.User):
    db.add(models.StatusHistory(claim_id=claim.id, from_status=None,
                                to_status="submitted", user_id=user.id,
                                note="Claim submitted"))


def change_status(db, claim: models.Claim, to_status: str,
                  user: models.User | None = None, note: str = ""):
    """user=None means the system made the change."""
    role = user.role if user else "system"
    if ALLOWED.get((claim.status, to_status)) != role:
        raise HTTPException(409, f"A claim can't move from '{claim.status}' to '{to_status}' now")
    db.add(models.StatusHistory(claim_id=claim.id, from_status=claim.status,
                                to_status=to_status, user_id=user.id if user else None,
                                note=note))
    claim.status = to_status