from datetime import date
from app import models
from app.auth import hash_password
from app.database import SessionLocal

db = SessionLocal()
users = {"ravi@demo.in": ("Ravi Kumar", "claimant"),
         "suresh@demo.in": ("Suresh", "assessor"),
         "priya@demo.in": ("Priya", "insurer")}
for email, (name, role) in users.items():
    if not db.query(models.User).filter_by(email=email).first():
        db.add(models.User(email=email, name=name, role=role, password_hash=hash_password("test1234")))
db.commit()
ravi = db.query(models.User).filter_by(email="ravi@demo.in").first()
policy = models.Policy(policy_number="POL-TEST-1", holder_id=ravi.id, start_date=date(2026, 1, 1),
                       end_date=date(2026, 12, 31), premium=12500, deductible=2000, sum_insured=400000)
db.add(policy); db.flush()
db.add(models.Vehicle(policy_id=policy.id, registration="TN 37 AB 1234", make="Maruti", model="Swift", year=2021))
db.commit()
print("Test users, policy and vehicle created")