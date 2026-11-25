from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey, JSON
from .database import Base


def now():
    return datetime.now(timezone.utc)


class Claim(Base):
    __tablename__ = "claims"
    id = Column(Integer, primary_key=True)
    claimant_name = Column(String, nullable=False)
    incident_date = Column(String, nullable=False)
    description = Column(Text, default="")
    created_at = Column(DateTime, default=now)


class ImageRecord(Base):
    __tablename__ = "images"
    id = Column(Integer, primary_key=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False)
    file_path = Column(String, nullable=False)
    sha256_hash = Column(String, index=True, nullable=False)
    duplicate_of = Column(Integer, nullable=True)
    uploaded_at = Column(DateTime, default=now)


class AnalysisResult(Base):
    __tablename__ = "analysis_results"
    id = Column(Integer, primary_key=True)
    image_id = Column(Integer, ForeignKey("images.id"), nullable=False)
    module = Column(String, nullable=False)
    score = Column(Float, nullable=False)
    flags = Column(JSON, default=list)
    artifact_paths = Column(JSON, default=dict)


class Verdict(Base):
    __tablename__ = "verdicts"
    id = Column(Integer, primary_key=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False)
    overall_risk = Column(String)
    risk_score = Column(Float)
    reasons = Column(JSON, default=list)
    reviewer_decision = Column(String, nullable=True)
    reviewer_note = Column(Text, nullable=True)
    reviewer_name = Column(String, nullable=True)
    decided_at = Column(DateTime, nullable=True)
