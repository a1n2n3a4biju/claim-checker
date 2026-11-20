import hashlib
import os
from fastapi import FastAPI, Depends, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session
from .database import Base, engine, get_db
from . import models
from .modules import forensics, jpeg_artifacts, ai_detector

os.makedirs("uploads", exist_ok=True)
os.makedirs("results", exist_ok=True)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Claim Checker")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"],
                   allow_methods=["*"], allow_headers=["*"])
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.mount("/results", StaticFiles(directory="results"), name="results")


class ClaimIn(BaseModel):
    claimant_name: str
    incident_date: str
    description: str = ""


@app.post("/claims")
def create_claim(data: ClaimIn, db: Session = Depends(get_db)):
    claim = models.Claim(**data.model_dump())
    db.add(claim)
    db.commit()
    db.refresh(claim)
    return {"id": claim.id, **data.model_dump()}


@app.get("/claims")
def list_claims(db: Session = Depends(get_db)):
    claims = db.query(models.Claim).order_by(models.Claim.id.desc()).all()
    return [{"id": c.id, "claimant_name": c.claimant_name,
             "incident_date": c.incident_date,
             "created_at": c.created_at.isoformat()} for c in claims]


@app.post("/claims/{claim_id}/images")
async def upload_images(claim_id: int, files: list[UploadFile] = File(...),
                        db: Session = Depends(get_db)):
    if not db.get(models.Claim, claim_id):
        raise HTTPException(404, "Claim not found")
    saved = []
    for f in files:
        data = await f.read()
        if not data.startswith(b"\xff\xd8"):
            raise HTTPException(400, f"{f.filename} is not a JPEG")
        h = hashlib.sha256(data).hexdigest()
        dup = db.query(models.ImageRecord).filter_by(sha256_hash=h).first()
        img = models.ImageRecord(claim_id=claim_id, file_path="", sha256_hash=h,
                                 duplicate_of=dup.id if dup else None)
        db.add(img)
        db.flush()
        path = f"uploads/{img.id}.jpg"
        with open(path, "wb") as out:
            out.write(data)
        img.file_path = path
        saved.append({"image_id": img.id, "url": f"/{path}",
                      "duplicate_of": img.duplicate_of})
    db.commit()
    return saved


@app.get("/claims/{claim_id}/results")
def get_results(claim_id: int, db: Session = Depends(get_db)):
    claim = db.get(models.Claim, claim_id)
    if not claim:
        raise HTTPException(404, "Claim not found")

    verdict = (db.query(models.Verdict)
                 .filter_by(claim_id=claim_id)
                 .order_by(models.Verdict.id.desc())
                 .first())

    images = []
    for img in db.query(models.ImageRecord).filter_by(claim_id=claim_id).all():
        modules = []
        for r in db.query(models.AnalysisResult).filter_by(image_id=img.id).all():
            artifacts = {}
            if r.artifact_paths and r.artifact_paths.get("heatmap_path"):
                artifacts["heatmap_url"] = "/" + r.artifact_paths["heatmap_path"]
            modules.append({"module": r.module, "score": r.score,
                            "flags": r.flags or [], "artifacts": artifacts})
        images.append({
            "image_id": img.id,
            "url": "/" + img.file_path,
            "duplicate_of": img.duplicate_of,
            "risk_score": fuse([m["score"] for m in modules]),         # filled in once analysis exists
            "modules": modules,
        })

    return {
        "claim_id": claim.id,
        "claimant_name": claim.claimant_name,
        "incident_date": claim.incident_date,
        "status": "analyzed" if verdict else "not_analyzed",
        "overall_risk": verdict.overall_risk if verdict else None,
        "risk_score": verdict.risk_score if verdict else None,
        "reasons": verdict.reasons if verdict else [],
        "reviewer_decision": verdict.reviewer_decision if verdict else None,
        "images": images,
    }

# Placeholder thresholds until M2's fusion model is ready
LOW_THRESHOLD, HIGH_THRESHOLD = 0.4, 0.7


def run_all_modules(image_path: str, out_dir: str = "results") -> list[dict]:
    results = []
    for module in (forensics, jpeg_artifacts, ai_detector):
        r = module.analyze(image_path, out_dir)
        results.extend(r if isinstance(r, list) else [r])
    return results


def risk_level(score: float) -> str:
    if score < LOW_THRESHOLD:
        return "low"
    return "medium" if score < HIGH_THRESHOLD else "high"
def fuse(scores: list[float]) -> float:
    """Placeholder fusion: average of module scores. M2's model replaces this."""
    return round(sum(scores) / len(scores), 2) if scores else None


@app.post("/claims/{claim_id}/analyze")
def analyze_claim(claim_id: int, db: Session = Depends(get_db)):
    if not db.get(models.Claim, claim_id):
        raise HTTPException(404, "Claim not found")
    images = db.query(models.ImageRecord).filter_by(claim_id=claim_id).all()
    if not images:
        raise HTTPException(400, "Upload at least one photo before analyzing")

    claim_score, reasons = 0.0, []
    for img in images:
        if img.duplicate_of:
            reasons.append(f"Photo {img.id} is identical to an earlier upload (photo {img.duplicate_of})")
        # remove old results so analyzing twice doesn't duplicate rows
        db.query(models.AnalysisResult).filter_by(image_id=img.id).delete()
        results = run_all_modules(img.file_path)
        for r in results:
            db.add(models.AnalysisResult(image_id=img.id, module=r["module"],
                                         score=r["score"], flags=r["flags"],
                                         artifact_paths=r["artifacts"]))
            reasons.extend(r["flags"])
        # placeholder fusion: average of module scores (replaced by M2's model)
        image_score = fuse([r["score"] for r in results])
        claim_score = max(claim_score, image_score)   # claim = riskiest photo

    verdict = models.Verdict(claim_id=claim_id,
                             overall_risk=risk_level(claim_score),
                             risk_score=round(claim_score, 2),
                             reasons=reasons[:5])
    db.add(verdict)
    db.commit()
    return {"claim_id": claim_id, "overall_risk": verdict.overall_risk,
            "risk_score": verdict.risk_score}
