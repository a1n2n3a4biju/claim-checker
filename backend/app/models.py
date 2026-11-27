"""Database tables for ClaimProof v2 (owner: M3).

When this file changes, announce it in the group: everyone pulls and recreates
their database with  python scripts/seed_demo.py --reset
"""
from datetime import datetime, timezone

from sqlalchemy import (JSON, Boolean, Column, Date, DateTime, Float, ForeignKey,
                        Integer, String, Text)
from sqlalchemy.orm import relationship

from .database import Base


def now():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    role = Column(String, nullable=False)              # claimant | assessor | insurer
    password_hash = Column(String, nullable=False)     # bcrypt only, never the password


class Policy(Base):
    __tablename__ = "policies"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    policy_number = Column(String, unique=True, nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    premium = Column(Integer, nullable=False)           # whole rupees
    deductible = Column(Integer, nullable=False)
    sum_insured = Column(Integer, nullable=False)
    vehicles = relationship("Vehicle", back_populates="policy", order_by="Vehicle.id")


class Vehicle(Base):
    __tablename__ = "vehicles"
    id = Column(Integer, primary_key=True)
    policy_id = Column(Integer, ForeignKey("policies.id"), nullable=False)
    registration = Column(String, nullable=False)
    make = Column(String, nullable=False)
    model = Column(String, nullable=False)
    year = Column(Integer, nullable=False)
    policy = relationship("Policy", back_populates="vehicles")


class Claim(Base):
    __tablename__ = "claims"
    id = Column(Integer, primary_key=True)
    claimant_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False)
    policy_id = Column(Integer, ForeignKey("policies.id"), nullable=False)
    incident_date = Column(Date, nullable=False)
    incident_time = Column(String, nullable=False)      # "HH:MM"
    location = Column(String, nullable=False)
    severity = Column(String, nullable=False)           # minor | moderate | severe
    description = Column(Text, nullable=False)
    status = Column(String, nullable=False, default="submitted")
    created_at = Column(DateTime(timezone=True), default=now)

    # filled in after the photo checks and routing
    risk_level = Column(String, nullable=True)          # low | medium | high
    risk_score = Column(Float, nullable=True)
    reasons = Column(JSON, default=list)
    fraud_flag = Column(Boolean, default=False)
    assessor_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # filled in by the insurer
    info_request = Column(Text, nullable=True)          # latest "more info" message
    decision = Column(String, nullable=True)            # approved | rejected | further_review
    approved_amount = Column(Integer, nullable=True)
    decision_note = Column(Text, nullable=True)

    claimant = relationship("User", foreign_keys=[claimant_id])
    assessor = relationship("User", foreign_keys=[assessor_id])
    vehicle = relationship("Vehicle")
    policy = relationship("Policy")


class ImageRecord(Base):
    __tablename__ = "images"
    id = Column(Integer, primary_key=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False)
    file_path = Column(String, nullable=False)
    sha256_hash = Column(String, index=True, nullable=False)
    duplicate_of = Column(Integer, nullable=True)
    uploaded_at = Column(DateTime(timezone=True), default=now)
    checked = Column(Boolean, default=False)            # photo checks finished
    risk_score = Column(Float, nullable=True)
    risk_level = Column(String, nullable=True)


class AnalysisResult(Base):
    __tablename__ = "analysis_results"
    id = Column(Integer, primary_key=True)
    image_id = Column(Integer, ForeignKey("images.id"), nullable=False)
    module = Column(String, nullable=False)
    score = Column(Float, nullable=False)
    flags = Column(JSON, default=list)
    artifact_paths = Column(JSON, default=dict)


class Quotation(Base):
    __tablename__ = "quotations"
    id = Column(Integer, primary_key=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), unique=True, nullable=False)
    assessor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    total = Column(Integer, nullable=False)             # calculated by the backend
    note = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), default=now)
    items = relationship("QuotationItem", order_by="QuotationItem.id")
    assessor = relationship("User")


class QuotationItem(Base):
    __tablename__ = "quotation_items"
    id = Column(Integer, primary_key=True)
    quotation_id = Column(Integer, ForeignKey("quotations.id"), nullable=False)
    kind = Column(String, nullable=False)               # part | labour
    description = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Integer, nullable=False)


class StatusHistory(Base):
    __tablename__ = "status_history"
    id = Column(Integer, primary_key=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False, index=True)
    from_status = Column(String, nullable=True)         # None for a new claim
    to_status = Column(String, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)   # None = system
    note = Column(Text, default="")
    at = Column(DateTime(timezone=True), default=now)
    user = relationship("User")
