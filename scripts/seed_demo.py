"""Build the ClaimProof v2 demo on an empty claimproof_v2 database.

    python scripts/seed_demo.py           # empty database only
    python scripts/seed_demo.py --reset   # drop every v2 table first, then seed

Run it with the backend's Python environment (it runs the real photo checks,
so PyTorch and the AI detector weights must be installed). It reads
backend/.env: DATABASE_URL, TOKEN_SECRET and DEMO_PASSWORD.

Demo accounts: claimant1..30@demo.in, assessor1@demo.in, insurer1@demo.in,
all with DEMO_PASSWORD. Claimants 1-16 have recent approved claims, so the
insurer sees a claim-history deduction on their current claim.

Everything goes through M3's real functions (app.workflow and app.auth): the
claim checks, the photo checks, routing and the status engine. Nothing writes
a status straight into the tables, so the demo also tests the workflow.
"""
import argparse
import os
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
IMAGES = ROOT / "data" / "images"
sys.path.insert(0, str(BACKEND))

from fastapi import HTTPException  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from app import models, photo_checks, workflow  # noqa: E402
from app.auth import hash_password  # noqa: E402
from app.database import DATABASE_URL, Base, SessionLocal, engine  # noqa: E402

# ---------------------------------------------------------------- accounts

CLAIMANT_NAMES = [
    "Ravi Kumar", "Meena Iyer", "Arjun Reddy", "Lakshmi Narayanan", "Karthik Raja",
    "Divya Shankar", "Vignesh Murali", "Anitha Raman", "Prakash Rao", "Sangeetha Pillai",
    "Rahul Menon", "Deepa Krishnan", "Senthil Kumar", "Nandini Gopal", "Manoj Varma",
    "Revathi Sundar", "Ashok Natarajan", "Kavitha Ramesh", "Ganesh Iyer", "Preethi Balaji",
    "Harish Chandran", "Swathi Mohan", "Bala Subramanian", "Janani Venkat", "Mohan Das",
    "Pooja Hegde", "Sathish Kannan", "Uma Maheswari", "Vinod Nair", "Yamuna Devi",
]
USERS = ([(f"claimant{i}@demo.in", name, "claimant") for i, name in enumerate(CLAIMANT_NAMES, 1)]
         + [("assessor1@demo.in", "Suresh Babu", "assessor"),
            ("insurer1@demo.in", "Priya Menon", "insurer")])

CARS = [("Maruti", "Swift"), ("Hyundai", "i20"), ("Honda", "City"), ("Tata", "Nexon"), ("Kia", "Seltos"),
        ("Toyota", "Glanza"), ("Mahindra", "XUV300"), ("Maruti", "Baleno"), ("Hyundai", "Creta"), ("Renault", "Kwid")]
PLACES = ["Avinashi Road", "Gandhipuram", "Peelamedu", "RS Puram", "Saibaba Colony", "Town Hall",
          "Race Course", "Singanallur", "Ukkadam", "Vadavalli", "Saravanampatti", "Ganapathy"]

# Repairs used for the claims and quotations:
# (severity, incident description, quotation items (kind, description, quantity, unit price), assessor note)
REPAIRS = [
    ("moderate", "Rear bumper hit while parked at a signal",
     [("part", "Rear bumper (hatchback)", 1, 8500), ("labour", "Paint, per panel", 1, 3500),
      ("labour", "Fitting, per hour", 3, 800)], "Bumper cracked, needs replacement"),
    ("minor", "Side mirror broken by a passing two-wheeler",
     [("part", "Outer rear view mirror", 1, 2900), ("labour", "Fitting, per hour", 1, 800)],
     "Mirror replacement"),
    ("moderate", "Front fender and headlamp damaged while reversing",
     [("part", "Front fender", 1, 4200), ("part", "Headlamp assembly", 1, 6200),
      ("labour", "Fitting, per hour", 2, 800)], "Fender and headlamp need replacement"),
    ("minor", "Scratches and a dent on the left door",
     [("labour", "Denting, per panel", 1, 1500), ("labour", "Paint, per panel", 1, 3500)],
     "Door dent, repairable"),
    ("severe", "Front of the car damaged in a collision",
     [("part", "Front bumper (hatchback)", 1, 7800), ("part", "Headlamp assembly", 2, 6200),
      ("part", "Bonnet (hatchback)", 1, 9800), ("labour", "Paint, per panel", 2, 3500),
      ("labour", "Fitting, per hour", 6, 800)], "Bumper, bonnet and both headlamps"),
    ("moderate", "Windshield cracked by a stone on the highway",
     [("part", "Windshield glass", 1, 7500), ("labour", "Windshield fitting", 1, 1000)],
     "Windshield replacement"),
    ("moderate", "Tail lamp and boot dented in a rear-end bump",
     [("part", "Tail lamp assembly", 1, 3400), ("labour", "Denting, per panel", 1, 1500),
      ("labour", "Paint, per panel", 1, 3500)], "Tail lamp and boot panel"),
]

# ---------------------------------------------------------------- photos

# From our dataset (data/images). Each photo is used once: a re-used photo would be
# flagged as a duplicate. The expected risk comes from the saved scores (scores.csv).
LOW_PHOTOS = [f"genuine/{n}.jpg" for n in (
    "P_012 P_021 P_016 P_001 P_046 P_032 P_018 P_003 P_015 P_024 P_035 P_004 P_034 P_013 P_037 P_040 "
    "P_026 P_007 P_023 P_036 P_025 P_045 P_029 P_030 P_009 P_044 P_033 P_019 P_006 P_039 P_028 P_022 "
    "P_047 P_038 P_048 P_043 P_002 P_008").split()]
MEDIUM_PHOTOS = [f"genuine/{n}.jpg" for n in "P_017 P_027 P_042 P_014 P_020 P_041 P_011 P_031".split()]
PHOTO_AI = "ai/AI_SD_001.jpg"
PHOTO_AI_2 = "ai/AI_SD_002.jpg"
PHOTO_COPY_MOVE = "Scripted_edits/CM_P_005.jpg"

# Claim history: claimants 1-10 have one recent approved claim, 11-14 two, 15-16 four
HISTORY_COUNT = {**{i: 1 for i in range(1, 11)}, **{i: 2 for i in range(11, 15)}, 15: 4, 16: 4}
HISTORY_DATES = [date(2026, 2, 12), date(2026, 4, 20), date(2026, 6, 8), date(2026, 8, 17)]


def create_database_if_missing():
    """PostgreSQL only: create claimproof_v2 if it doesn't exist yet."""
    url = make_url(DATABASE_URL)
    if not url.drivername.startswith("postgresql"):
        return
    from sqlalchemy import create_engine
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.execute(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": url.database}).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{url.database}"'))
            print(f"Created database {url.database}")
    admin.dispose()


def photo(rel: str) -> tuple[str, bytes]:
    path = IMAGES / rel
    if not path.exists():
        sys.exit(f"Missing dataset photo: {path}\nCopy the dataset into data/images/ first.")
    return path.name, path.read_bytes()


def new_claim(db, claimant, vehicle, n, incident_date, photo_rel, repair=None):
    """Claimant submits (with the n-th place and repair), uploads one photo,
    then the photo checks and routing run."""
    repair = repair or REPAIRS[n % len(REPAIRS)]
    claim = workflow.create_claim(db, claimant, dict(
        vehicle_id=vehicle.id, incident_date=incident_date,
        incident_time=f"{8 + n % 12:02d}:{(n * 13) % 60:02d}",
        location=f"{PLACES[n % len(PLACES)]}, Coimbatore", severity=repair[0], description=repair[1]))
    db.commit()
    workflow.upload_photos(db, claim, claimant, [photo(photo_rel)])
    db.commit()
    print(f"  claim {claim.id:>2} ({claimant.email}): photo checks on {photo_rel} ...", flush=True)
    workflow.run_photo_checks(db, claim.id)       # commits
    return claim, repair


def quote(db, claim, repair):
    _, _, items, note = repair
    workflow.submit_quotation(db, claim, claim.assessor,
                              [{"kind": k, "description": d, "quantity": q, "unit_price": u}
                               for k, d, q, u in items], note)
    db.commit()


def quotation(db, claim):
    return db.query(models.Quotation).filter_by(claim_id=claim.id).first()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reset", action="store_true", help="drop all v2 tables first (deletes all data)")
    args = parser.parse_args()

    demo_password = os.getenv("DEMO_PASSWORD")
    if not demo_password:
        sys.exit("DEMO_PASSWORD is not set in backend/.env")

    create_database_if_missing()
    if args.reset:
        Base.metadata.drop_all(bind=engine)
        print("Dropped all tables")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    if db.query(models.User).count():
        sys.exit("The database already has data. Run with --reset to start again from an empty database.")

    print("Loading photo checks (this can take a minute) ...")
    photo_checks.load()

    # 1. Users (one bcrypt hash, reused: hashing 32 times would only slow the seed down)
    pw_hash = hash_password(demo_password)
    users = {}
    for email, name, role in USERS:
        users[email] = models.User(email=email, name=name, role=role, password_hash=pw_hash)
        db.add(users[email])
    db.commit()
    claimant = {i: users[f"claimant{i}@demo.in"] for i in range(1, 31)}
    insurer = users["insurer1@demo.in"]

    # 2. One policy and one vehicle per claimant. Every policy runs for 2026,
    #    except claimant 23's, which ended on 31 Oct 2026 (for the refused claim).
    vehicles = {}
    for i in range(1, 31):
        start, end = (date(2025, 11, 1), date(2026, 10, 31)) if i == 23 else (date(2026, 1, 1), date(2026, 12, 31))
        policy = models.Policy(user_id=claimant[i].id, policy_number=f"POL-2026-{i:04d}",
                               start_date=start, end_date=end, premium=8000 + 250 * i,
                               deductible=(1000, 1500, 2000, 2500)[i % 4],
                               sum_insured=(250000, 300000, 400000, 500000)[i % 4])
        db.add(policy)
        db.flush()
        make, model = CARS[i % len(CARS)]
        v = models.Vehicle(policy_id=policy.id, registration=f"TN 37 A{chr(64 + i % 26 + 1)} {1000 + 37 * i}",
                           make=make, model=model, year=2018 + i % 7)
        db.add(v)
        db.flush()
        vehicles[i] = v
    db.commit()

    low, medium = iter(LOW_PHOTOS), iter(MEDIUM_PHOTOS)
    created, expected = [], []
    n = 0

    # 3. Claim history for claimants 1-16: earlier claims, approved and settled.
    #    Each is approved at its own suggested payout, so later ones already carry a deduction.
    total_history = sum(HISTORY_COUNT.values())
    print(f"Creating {total_history} past claims for claimants 1-16 (real photo checks; this takes a while) ...")
    for i, count in HISTORY_COUNT.items():
        for k in range(count):
            n += 1
            c, repair = new_claim(db, claimant[i], vehicles[i], n, HISTORY_DATES[k], next(low))
            quote(db, c, repair)
            workflow.start_review(db, c, insurer)
            workflow.decide(db, c, insurer, "approved",
                            workflow.suggested_payout(db, c, quotation(db, c)), "Matches quotation")
            workflow.settle(db, c, insurer)
            db.commit()

    # 4. A current claim for each of claimants 1-16, with a quotation, so the insurer
    #    sees the payout breakdown with the history deduction.
    #    Claimants 1-8: under review (ready to decide). 9-16: assessed (start review first).
    print("Creating current claims for claimants 1-16 ...")
    photos_now = [next(low) for _ in range(11)] + [next(medium) for _ in range(5)]
    for i in range(1, 17):
        n += 1
        c, repair = new_claim(db, claimant[i], vehicles[i], n, date(2026, 10, 5) + timedelta(days=2 * i),
                              photos_now[i - 1])
        quote(db, c, repair)
        want = "under_review" if i <= 8 else "assessed"
        if want == "under_review":
            workflow.start_review(db, c, insurer)
            db.commit()
        created.append(c)
        expected.append((f"claimant{i}, {HISTORY_COUNT[i]} past approved", "low" if i <= 11 else "medium", want))

    # 5. Other journeys (claimants 17-23, no claim history). Claimants 24-30 start empty.
    print("Creating the other demo claims ...")
    c, r = new_claim(db, claimant[17], vehicles[17], 4, date(2026, 11, 15), PHOTO_AI, REPAIRS[4])
    quote(db, c, r)
    workflow.start_review(db, c, insurer)
    db.commit()
    created.append(c); expected.append(("claimant17, AI-generated photo", "high", "under_review"))

    c, r = new_claim(db, claimant[18], vehicles[18], 3, date(2026, 11, 20), PHOTO_COPY_MOVE, REPAIRS[3])
    quote(db, c, r)
    created.append(c); expected.append(("claimant18, copy-move edit", "medium or high", "assessed"))

    c, r = new_claim(db, claimant[19], vehicles[19], 1, date(2026, 11, 3), next(medium), REPAIRS[1])
    created.append(c); expected.append(("claimant19, waiting for assessor", "medium", "awaiting_assessment"))

    c, r = new_claim(db, claimant[20], vehicles[20], 2, date(2026, 9, 14), next(medium), REPAIRS[2])
    quote(db, c, r)
    workflow.start_review(db, c, insurer)
    workflow.request_info(db, c, insurer,
                          "Please upload a photo of the other side of the car and the repair estimate.")
    db.commit()
    created.append(c); expected.append(("claimant20, info requested", "medium", "more_info_requested"))

    c, r = new_claim(db, claimant[21], vehicles[21], 4, date(2026, 10, 28), PHOTO_AI_2, REPAIRS[4])
    quote(db, c, r)
    workflow.start_review(db, c, insurer)
    workflow.decide(db, c, insurer, "further_review", None, "Photo needs a closer look before we decide")
    db.commit()
    created.append(c); expected.append(("claimant21, further review", "high", "decided"))

    c, r = new_claim(db, claimant[22], vehicles[22], 0, date(2026, 11, 2), next(medium), REPAIRS[0])
    quote(db, c, r)
    workflow.start_review(db, c, insurer)
    workflow.decide(db, c, insurer, "approved", workflow.suggested_payout(db, c, quotation(db, c)),
                    "Matches quotation")
    workflow.settle(db, c, insurer)
    db.commit()
    created.append(c); expected.append(("claimant22, settled", "medium", "settled"))

    # claimant 23: incident after the policy ended -> refused with 400, not created
    try:
        workflow.create_claim(db, claimant[23], dict(
            vehicle_id=vehicles[23].id, incident_date=date(2026, 11, 10), incident_time="10:00",
            location="Town Hall, Coimbatore", severity="minor", description="Dent on the rear door"))
        db.commit()
        refused = "NOT refused (check the policy date rule!)"
    except HTTPException as e:
        db.rollback()
        refused = f"refused with {e.status_code}: {e.detail}"

    # Summary
    print("\nDone.")
    print(f"  Users:    {db.query(models.User).count()}  (claimant1-30, assessor1, insurer1 @demo.in)")
    print(f"  Policies: {db.query(models.Policy).count()}  Vehicles: {db.query(models.Vehicle).count()}")
    print(f"  Claims:   {db.query(models.Claim).count()}  ({total_history} of them past claims, approved and settled)")
    problems = 0
    for claim, (label, want_risk, want_status) in zip(created, expected):
        db.refresh(claim)
        ok_status = claim.status == want_status
        ok_risk = claim.risk_level in want_risk.replace(" or ", " ").split()
        problems += (not ok_status) + (not ok_risk)
        b = workflow.payout_breakdown(db, claim, quotation(db, claim))
        pay = f"payout {b['suggested_payout']:>6} (-{round(b['history_rate'] * 100):>2}%)" if b else " " * 20
        print(f"    #{claim.id:<3} {label:<32} risk {claim.risk_level:<6} (expected {want_risk:<14}) "
              f"fraud {'yes' if claim.fraud_flag else 'no ':<3} {pay}  status {claim.status}"
              f"{'' if ok_status else '   <-- CHECK status'}{'' if ok_risk else '   <-- CHECK risk'}")
    print(f"    claimant23, outside policy dates: {refused}")
    print("\nSign in as claimant1-30, assessor1 or insurer1 @demo.in with the password in DEMO_PASSWORD.")
    print("Claimants 1-16 have recent approved claims, so their current claim shows a history deduction.")
    if problems:
        print(f"WARNING: {problems} result(s) differ from the plan; see the lines marked CHECK. "
              "A risk level a little off the saved scores is not by itself a bug.")
    db.close()


if __name__ == "__main__":
    main()
