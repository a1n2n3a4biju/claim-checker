from datetime import datetime, timezone

from sqlalchemy import (Boolean, Column, Date, DateTime, Float, ForeignKey,
                        Integer, JSON, String, Text)

from .database import Base


def now():
    return datetime.now(timezone.utc)


# ---------- people, policies, vehicles ----------

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    role = Column(String, nullable=False)              # claimant, assessor or insurer
    password_hash = Column(String, nullable=False)     # never the real password
    created_at = Column(DateTime, default=now)


class Policy(Base):
    __tablename__ = "policies"
    id = Column(Integer, primary_key=True)
    policy_number = Column(String, unique=True, nullable=False)
    holder_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    premium = Column(Integer, nullable=False)          # whole rupees
    deductible = Column(Integer, nullable=False)
    sum_insured = Column(Integer, nullable=False)


class Vehicle(Base):
    __tablename__ = "vehicles"
    id = Column(Integer, primary_key=True)
    policy_id = Column(Integer, ForeignKey("policies.id"), nullable=False)
    registration = Column(String, nullable=False)
    make = Column(String)
    model = Column(String)
    year = Column(Integer)


# ---------- claims and photos ----------

class Claim(Base):
    __tablename__ = "claims"
    id = Column(Integer, primary_key=True)
    claimant_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False)
    incident_date = Column(Date, nullable=False)
    incident_time = Column(String)
    location = Column(String)
    severity = Column(String)                          # minor, moderate or severe
    description = Column(Text, default="")
    status = Column(String, default="submitted")
    assessor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    fraud_flag = Column(Boolean, default=False)
    info_request = Column(Text, nullable=True)         # the insurer's question, if any
    created_at = Column(DateTime, default=now)


class ImageRecord(Base):
    __tablename__ = "images"
    id = Column(Integer, primary_key=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False)
    file_path = Column(String)
    sha256_hash = Column(String)
    duplicate_of = Column(Integer, nullable=True)
    uploaded_at = Column(DateTime, default=now)


class AnalysisResult(Base):
    __tablename__ = "analysis_results"
    id = Column(Integer, primary_key=True)
    image_id = Column(Integer, ForeignKey("images.id"), nullable=False)
    module = Column(String)
    score = Column(Float)
    flags = Column(JSON)
    artifact_paths = Column(JSON)


class Verdict(Base):
    __tablename__ = "verdicts"
    id = Column(Integer, primary_key=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False)
    overall_risk = Column(String)
    risk_score = Column(Float)
    reasons = Column(JSON)
    created_at = Column(DateTime, default=now)


# ---------- assessment, decisions, history ----------

class Quotation(Base):
    __tablename__ = "quotations"
    id = Column(Integer, primary_key=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False)
    assessor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    total = Column(Integer, nullable=False)
    note = Column(Text, default="")
    created_at = Column(DateTime, default=now)


class QuotationItem(Base):
    __tablename__ = "quotation_items"
    id = Column(Integer, primary_key=True)
    quotation_id = Column(Integer, ForeignKey("quotations.id"), nullable=False)
    kind = Column(String)                              # part or labour
    description = Column(String)
    quantity = Column(Integer)
    unit_price = Column(Integer)
    line_total = Column(Integer)


class Decision(Base):
    __tablename__ = "decisions"
    id = Column(Integer, primary_key=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False)
    insurer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    outcome = Column(String)                           # approved, rejected or fraud_review
    amount = Column(Integer, nullable=True)
    note = Column(Text, default="")
    decided_at = Column(DateTime, default=now)


class StatusHistory(Base):
    __tablename__ = "status_history"
    id = Column(Integer, primary_key=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False)
    from_status = Column(String, nullable=True)
    to_status = Column(String, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)   # empty = the system
    note = Column(Text, default="")
    at = Column(DateTime, default=now)