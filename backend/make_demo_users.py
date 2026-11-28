"""Demo data for ClaimProof v2:
30 claimants (policies, vehicles, claim history), 3 assessors, 2 insurers.
Password for everyone: DEMO_PASSWORD in backend/.env
Run from the backend folder:  python make_demo_users.py
"""
import csv
import os
import random
from datetime import date

from dotenv import load_dotenv

from app import models
from app.auth import hash_password
from app.database import Base, SessionLocal, engine

load_dotenv()
PASSWORD = os.getenv("DEMO_PASSWORD")
if not PASSWORD:
    raise SystemExit("Set DEMO_PASSWORD in backend/.env first")

random.seed(42)
Base.metadata.create_all(bind=engine)

FIRST = ["Ravi", "Meena", "Arjun", "Divya", "Karthik", "Lakshmi", "Vikram", "Anjali", "Suresh",
         "Priya", "Rahul", "Kavitha", "Naveen", "Deepa", "Ganesh", "Swathi", "Manoj", "Revathi",
         "Ajay", "Nithya", "Prakash", "Sneha", "Harish", "Keerthana", "Sanjay", "Pooja", "Vijay",
         "Aishwarya", "Rohit", "Janani"]
LAST = ["Kumar", "Nair", "Iyer", "Menon", "Reddy", "Pillai", "Sharma", "Raj", "Krishnan",
        "Subramanian"]
CARS = [("Maruti", "Swift"), ("Hyundai", "i20"), ("Tata", "Nexon"), ("Honda", "City"),
        ("Toyota", "Innova"), ("Mahindra", "XUV300"), ("Kia", "Seltos"), ("Renault", "Kwid")]
DISTRICTS = ["37", "38", "39", "66", "01", "09"]


# ---- the history plan for each claimant ----
# each entry: (outcome, when)  -  "recent" = Jan-Aug 2026, "old" = 2024
def history_plan(n):
    if 1 <= n <= 10:
        return [("approved", "recent")]
    if 11 <= n <= 14:
        return [("approved", "recent")] * 2
    if 15 <= n <= 16:
        return [("approved", "recent")] * 3
    if 17 <= n <= 20:
        return [("approved", "old")]
    if 21 <= n <= 23:
        return [("rejected", "recent")]
    return []                                         # 24-30: no history


def registration():
    letters = "".join(random.choice("ABCDEFGHJKLMNPRSTUVWXYZ") for _ in range(2))
    return f"TN {random.choice(DISTRICTS)} {letters} {random.randint(1000, 9999)}"


db = SessionLocal()
hashed = hash_password(PASSWORD)
rows = []


def add_user(email, name, role):
    user = db.query(models.User).filter_by(email=email).first()
    if not user:
        user = models.User(email=email, name=name, role=role, password_hash=hashed)
        db.add(user)
        db.flush()
    return user


def add_policy(number, holder, year, template=None):
    p = models.Policy(policy_number=number, holder_id=holder.id,
                      start_date=date(year, 1, 1), end_date=date(year, 12, 31),
                      premium=template.premium if template else random.choice([8500, 10500, 12500, 15000, 18000]),
                      deductible=template.deductible if template else random.choice([1000, 2000, 2500, 5000]),
                      sum_insured=template.sum_insured if template else random.choice([300000, 400000, 600000, 800000]))
    db.add(p)
    db.flush()
    return p


def add_history_claim(user, vehicle, when, outcome, insurer):
    claim = models.Claim(claimant_id=user.id, vehicle_id=vehicle.id, incident_date=when,
                         incident_time="10:00", location="Coimbatore", severity="moderate",
                         description="Earlier claim (demo history)",
                         status="settled" if outcome == "approved" else "decided")
    db.add(claim)
    db.flush()
    db.add(models.Decision(claim_id=claim.id, insurer_id=insurer.id, outcome=outcome,
                           amount=random.choice([12000, 18500, 25000, 32000]) if outcome == "approved" else None,
                           note="Demo history"))
    db.add(models.StatusHistory(claim_id=claim.id, from_status=None, to_status=claim.status,
                                user_id=insurer.id, note="Imported history (demo data)"))


# ---- staff ----
for i, name in enumerate(["Suresh Babu", "Kavya Ramesh", "Anand Rao"], start=1):
    rows.append({"email": f"assessor{i}@demo.in", "name": name, "role": "assessor", "history": ""})
    add_user(f"assessor{i}@demo.in", name, "assessor")
insurer = None
for i, name in enumerate(["Priya Shankar", "Mohan Das"], start=1):
    rows.append({"email": f"insurer{i}@demo.in", "name": name, "role": "insurer", "history": ""})
    u = add_user(f"insurer{i}@demo.in", name, "insurer")
    insurer = insurer or u

# ---- claimants ----
for n in range(1, 31):
    email = f"claimant{n}@demo.in"
    name = f"{FIRST[n - 1]} {random.choice(LAST)}"
    user = add_user(email, name, "claimant")
    plan = history_plan(n)
    rows.append({"email": email, "name": name, "role": "claimant",
                 "history": ", ".join(f"{o} ({w})" for o, w in plan) or "none"})

    number = f"POL-2026-{n:04d}"
    if db.query(models.Policy).filter_by(policy_number=number).first():
        continue                                      # already created earlier

    year = 2025 if n >= 28 else 2026                  # claimants 28-30: policy ended in 2025
    policy = add_policy(number, user, year)
    cars = []
    for _ in range(random.choice([1, 1, 2])):
        make, model = random.choice(CARS)
        car = models.Vehicle(policy_id=policy.id, registration=registration(),
                             make=make, model=model, year=random.randint(2016, 2025))
        db.add(car)
        cars.append(car)
    db.flush()

    old_car = None
    for outcome, when in plan:
        if when == "recent":                          # on the current 2026 policy
            add_history_claim(user, cars[0], date(2026, random.randint(1, 8), random.randint(1, 28)),
                              outcome, insurer)
        else:                                         # on a 2024 policy, same car
            if old_car is None:
                old_policy = add_policy(f"POL-2024-{n:04d}", user, 2024, template=policy)
                old_car = models.Vehicle(policy_id=old_policy.id, registration=cars[0].registration,
                                         make=cars[0].make, model=cars[0].model, year=cars[0].year)
                db.add(old_car)
                db.flush()
            add_history_claim(user, old_car, date(2024, random.randint(3, 10), random.randint(1, 28)),
                              outcome, insurer)

db.commit()
db.close()

with open("demo_accounts.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["email", "name", "role", "history"])
    writer.writeheader()
    writer.writerows(rows)

print(f"{len(rows)} accounts ready (30 claimants, 3 assessors, 2 insurers).")
print("Password: DEMO_PASSWORD from .env. Account list with each claimant's history: demo_accounts.csv")