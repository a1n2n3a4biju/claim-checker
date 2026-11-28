from . import models
from .database import SessionLocal
from .scoring import fuse, risk_level, run_all_modules
from .workflow import change_status

try:
    from .routing import route_claim              # M2's function
except ImportError:                                # until M2's file is merged
    def route_claim(risk_level, assessors):
        best = min(assessors, key=lambda a: (a["open_claims"], a["id"]))
        return {"fraud_flag": risk_level == "high", "assessor_id": best["id"]}


def score_claim(db, claim: models.Claim) -> models.Verdict:
    """Your v1 analysis: six checks per photo, fusion, riskiest photo."""
    images = db.query(models.ImageRecord).filter_by(claim_id=claim.id).all()
    claim_score, reasons = 0.0, []
    for img in images:
        if img.duplicate_of:
            reasons.append(f"Photo {img.id} is identical to an earlier upload (photo {img.duplicate_of})")
        db.query(models.AnalysisResult).filter_by(image_id=img.id).delete()
        results, problems = run_all_modules(img.file_path)
        reasons.extend(problems)
        for r in results:
            r["score"] = float(r["score"])
            db.add(models.AnalysisResult(image_id=img.id, module=r["module"], score=r["score"],
                                         flags=r["flags"], artifact_paths=r["artifacts"]))
            reasons.extend(r["flags"])
        image_score = fuse({r["module"]: r["score"] for r in results})
        if image_score is not None:
            claim_score = max(claim_score, image_score)
    verdict = models.Verdict(claim_id=claim.id, overall_risk=risk_level(claim_score),
                             risk_score=round(claim_score, 2),
                             reasons=list(dict.fromkeys(reasons))[:5])
    db.add(verdict)
    return verdict


def analyze_and_route(claim_id: int):
    """Runs in the background after the claimant uploads photos."""
    db = SessionLocal()
    try:
        claim = db.get(models.Claim, claim_id)
        if not claim or claim.status != "submitted":
            return
        verdict = score_claim(db, claim)
        change_status(db, claim, "photos_checked", note=f"Risk: {verdict.overall_risk}")

        assessors = [{"id": a.id,
                      "open_claims": db.query(models.Claim).filter_by(
                          assessor_id=a.id, status="awaiting_assessment").count()}
                     for a in db.query(models.User).filter_by(role="assessor").all()]
        if assessors:
            route = route_claim(verdict.overall_risk, assessors)
            claim.fraud_flag = route["fraud_flag"]
            claim.assessor_id = route["assessor_id"]
            change_status(db, claim, "awaiting_assessment", note="Assigned to an assessor")
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[pipeline] claim {claim_id} failed: {e}")
    finally:
        db.close()