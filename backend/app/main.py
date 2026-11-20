import hashlib
import os
from fastapi import FastAPI, Depends, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session
from .database import Base, engine, get_db
from . import models

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
