"""Backend API test for ClaimProof v2: journeys, access rules, 409s and "no risk for claimants".

Runs on a temporary SQLite database with the photo checks replaced by a stand-in,
so it needs neither PostgreSQL nor the AI models. From the repository root:

    python tests/test_backend.py

Needs: fastapi, sqlalchemy, bcrypt, httpx, python-multipart, python-dotenv, joblib, scikit-learn.
The real photo checks are tested by backend/test_contract.py; the full demo by scripts/seed_demo.py.
"""
import os
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TMP = Path(tempfile.mkdtemp(prefix="claimproof_test_"))
os.environ.update(DATABASE_URL=f"sqlite:///{(TMP / 'test.db').as_posix()}", TOKEN_SECRET="test-secret-" + "x" * 20,
                  SKIP_PHOTO_MODELS="1")
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient  # noqa: E402

from app import models, photo_checks, workflow  # noqa: E402
from app.auth import hash_password  # noqa: E402
from app.database import SessionLocal  # noqa: E402

workflow.UPLOAD_DIR = TMP / "uploads"            # keep test photos out of backend/uploads
FEATURES = ["ela", "noise", "copy_move", "jpeg", "ai_detector_1", "ai_detector_2"]


def fake_checks(image_path, out_dir=None):
    """Stand-in photo checks: a photo containing b'FAKE' scores high, anything else low."""
    data = (workflow.UPLOAD_DIR / Path(image_path).name).read_bytes()
    s = 0.95 if b"FAKE" in data else 0.05
    return [{"module": m, "score": s, "flags": [f"{m} found something"] if s > 0.5 else [],
             "artifacts": {"heatmap_path": f"results/x_{m}.png"}} for m in FEATURES], []


photo_checks.run_all_modules = fake_checks

from app.main import app  # noqa: E402

JPEG = b"\xff\xd8\xff\xe0 genuine photo"
FAKE_JPEG = b"\xff\xd8\xff\xe0 FAKE photo"
PASSWORD = "test-pass"
fails = 0


def check(name, cond, extra=""):
    global fails
    print(("PASS  " if cond else "FAIL  ") + name + ("" if cond else f"\n      -> {extra}"))
    fails += not cond


def setup_data():
    db = SessionLocal()
    for email, name, role in [("ravi@demo.in", "Ravi Kumar", "claimant"), ("meena@demo.in", "Meena Iyer", "claimant"),
                              ("suresh@demo.in", "Suresh Babu", "assessor"), ("kavya@demo.in", "Kavya Nair", "assessor"),
                              ("priya@demo.in", "Priya Menon", "insurer")]:
        db.add(models.User(email=email, name=name, role=role, password_hash=hash_password(PASSWORD)))
    db.flush()
    ravi = db.query(models.User).filter_by(email="ravi@demo.in").one()
    meena = db.query(models.User).filter_by(email="meena@demo.in").one()
    p1 = models.Policy(user_id=ravi.id, policy_number="POL-1", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31),
                       premium=12500, deductible=2000, sum_insured=400000)
    p2 = models.Policy(user_id=meena.id, policy_number="POL-2", start_date=date(2025, 11, 1), end_date=date(2026, 10, 31),
                       premium=9800, deductible=1500, sum_insured=300000)
    db.add_all([p1, p2])
    db.flush()
    db.add_all([models.Vehicle(policy_id=p1.id, registration="TN 37 AB 1234", make="Maruti", model="Swift", year=2021),
                models.Vehicle(policy_id=p2.id, registration="TN 66 EF 9012", make="Honda", model="City", year=2019)])
    db.commit()
    db.close()


def main():
    setup_data()
    c = TestClient(app)

    def login(email):
        r = c.post("/auth/login", json={"email": email, "password": PASSWORD})
        return {"Authorization": f"Bearer {r.json()['token']}"}

    ravi, meena, suresh, kavya, priya = map(login, ["ravi@demo.in", "meena@demo.in", "suresh@demo.in",
                                                    "kavya@demo.in", "priya@demo.in"])

    print("\n-- sign-in")
    r = c.post("/auth/login", json={"email": "ravi@demo.in", "password": PASSWORD})
    check("login returns token and user", set(r.json()) == {"token", "user"} and r.json()["user"]["role"] == "claimant", r.text)
    r = c.post("/auth/login", json={"email": "ravi@demo.in", "password": "wrong"})
    check("wrong password -> 401 with detail", r.status_code == 401 and isinstance(r.json()["detail"], str), r.text)
    check("GET /me", c.get("/me", headers=ravi).json()["name"] == "Ravi Kumar")
    check("no token -> 401", c.get("/me").status_code == 401)
    check("changed token -> 401", c.get("/me", headers={"Authorization": ravi["Authorization"][:-3] + "abc"}).status_code == 401)

    print("\n-- sign-up (new customer)")
    new = {"name": "Anita Raj", "email": "Anita@Example.com", "password": "secret-pass-1"}
    r = c.post("/auth/register", json={**new, "role": "insurer"})
    check("register -> 201 claimant (role in body ignored)",
          r.status_code == 201 and r.json()["user"]["role"] == "claimant" and r.json()["token"], r.text)
    db = SessionLocal()
    stored = db.query(models.User).filter_by(email="anita@example.com").one().password_hash
    db.close()
    check("password stored only as a bcrypt hash", stored.startswith("$2") and new["password"] not in stored, stored)
    r = c.post("/auth/login", json={"email": "anita@example.com", "password": new["password"]})
    check("new user can sign in", r.status_code == 200 and r.json()["user"]["name"] == "Anita Raj", r.text)
    check("duplicate email -> 400", c.post("/auth/register", json=new).status_code == 400)
    r = c.post("/auth/register", json={**new, "email": "x@y.in", "password": "short"})
    check("short password -> 422 naming the field", r.status_code == 422 and r.json()["detail"].startswith("password"), r.text)
    r = c.post("/auth/register", json={**new, "email": "not-an-email"})
    check("bad email -> 422", r.status_code == 422 and r.json()["detail"].startswith("email"), r.text)
    anita = {"Authorization": f"Bearer {c.post('/auth/login', json={'email': 'anita@example.com', 'password': new['password']}).json()['token']}"}
    check("new user has no policies yet", c.get("/me/policies", headers=anita).json() == [])
    check("new user cannot open insurer pages -> 403", c.get("/insurer/claims", headers=anita).status_code == 403)

    print("\n-- claimant submits")
    pol = c.get("/me/policies", headers=ravi).json()
    vid = pol[0]["vehicles"][0]["id"]
    body = {"vehicle_id": vid, "incident_date": "2026-11-15", "incident_time": "14:30",
            "location": "Avinashi Road, Coimbatore", "severity": "moderate", "description": "Rear bumper hit while parked"}
    r = c.post("/claims", json=body, headers=ravi)
    check("POST /claims -> submitted", r.status_code == 201 and r.json()["status"] == "submitted", r.text)
    cid = r.json()["id"]
    check("vehicle not on policy -> 400", c.post("/claims", json={**body, "vehicle_id": 999}, headers=ravi).status_code == 400)
    meena_vid = c.get("/me/policies", headers=meena).json()[0]["vehicles"][0]["id"]
    r = c.post("/claims", json={**body, "vehicle_id": meena_vid, "incident_date": "2026-11-10"}, headers=meena)
    check("outside policy dates -> 400", r.status_code == 400 and "not valid" in r.json()["detail"], r.text)
    r = c.post("/claims", json={k: v for k, v in body.items() if k != "location"}, headers=ravi)
    check("missing field -> 422 naming it", r.status_code == 422 and "location" in r.json()["detail"], r.text)
    r = c.post(f"/claims/{cid}/images", files=[("files", ("a.png", b"\x89PNG", "image/png"))], headers=ravi)
    check("not a JPEG -> 400", r.status_code == 400, r.text)
    r = c.post(f"/claims/{cid}/images", files=[("files", ("a.jpg", JPEG, "image/jpeg"))], headers=ravi)
    check("upload JPEG", r.status_code == 201, r.text)
    mine = c.get(f"/me/claims/{cid}", headers=ravi).json()
    check("after checks: awaiting_assessment, claimant label 'Being assessed'",
          mine["status"] == "awaiting_assessment" and mine["status_label"] == "Being assessed", mine)
    check("timeline labels for claimant", [t["label"] for t in mine["timeline"]] == ["Received", "Received", "Being assessed"], mine["timeline"])

    print("\n-- routing")
    staff = c.get(f"/insurer/claims/{cid}", headers=priya).json()
    check("least busy assessor, tie -> lower id (Suresh)", staff["assessor"] == "Suresh Babu (assessor)", staff["assessor"])
    check("low risk -> no fraud flag", staff["risk_level"] == "low" and staff["fraud_flag"] is False, staff)
    r = c.post("/claims", json={**body, "incident_date": "2026-11-16"}, headers=ravi)
    cid2 = r.json()["id"]
    c.post(f"/claims/{cid2}/images", files=[("files", ("b.jpg", FAKE_JPEG, "image/jpeg"))], headers=ravi)
    staff2 = c.get(f"/insurer/claims/{cid2}", headers=priya).json()
    check("second claim goes to the less busy assessor (Kavya)", staff2["assessor"] == "Kavya Nair (assessor)", staff2["assessor"])
    check("high risk -> fraud flag", staff2["risk_level"] == "high" and staff2["fraud_flag"] is True, staff2)

    print("\n-- assessor")
    check("assigned list", [x["id"] for x in c.get("/assessor/claims", headers=suresh).json()] == [cid])
    check("other assessor cannot open -> 403", c.get(f"/assessor/claims/{cid}", headers=kavya).status_code == 403)
    check("price list", len(c.get("/price-list", headers=suresh).json()) >= 15)
    q = {"items": [{"kind": "part", "description": "Rear bumper", "quantity": 1, "unit_price": 8500},
                   {"kind": "labour", "description": "Paint and fitting", "quantity": 3, "unit_price": 800}],
         "note": "Bumper cracked, needs replacement"}
    check("other assessor quotation -> 403", c.post(f"/claims/{cid}/quotation", json=q, headers=kavya).status_code == 403)
    check("start review too early -> 409", c.post(f"/claims/{cid}/start-review", headers=priya).status_code == 409)
    r = c.post(f"/claims/{cid}/quotation", json=q, headers=suresh)
    check("quotation: backend total 10900, status assessed",
          r.status_code == 200 and r.json()["quotation"]["total"] == 10900 and r.json()["status"] == "assessed", r.text)
    check("second quotation -> 409", c.post(f"/claims/{cid}/quotation", json=q, headers=suresh).status_code == 409)

    print("\n-- insurer")
    r = c.post(f"/claims/{cid}/start-review", headers=priya)
    check("start review -> under_review", r.json()["status"] == "under_review", r.text)
    check("suggested payout = 10900 - 2000", r.json()["suggested_payout"] == 8900, r.json().get("suggested_payout"))
    check("claimant reply when not asked -> 409", c.post(f"/claims/{cid}/reply", data={"note": "x"}, headers=ravi).status_code == 409)
    r = c.post(f"/claims/{cid}/request-info", json={"message": "Please send a photo of the other side"}, headers=priya)
    check("request info -> more_info_requested", r.json()["status"] == "more_info_requested", r.text)
    mine = c.get(f"/me/claims/{cid}", headers=ravi).json()
    check("claimant sees the request", mine["status_label"] == "We need more information" and mine["info_request"], mine)
    check("Meena cannot reply on Ravi's claim -> 403", c.post(f"/claims/{cid}/reply", data={"note": "x"}, headers=meena).status_code == 403)
    r = c.post(f"/claims/{cid}/reply", data={"note": "Here it is"},
               files=[("files", ("c.jpg", JPEG + b"2", "image/jpeg"))], headers=ravi)
    check("reply -> back to under_review", r.status_code == 200 and r.json()["status"] == "under_review", r.text)
    check("approve without amount -> 422", c.post(f"/claims/{cid}/decision", json={"outcome": "approved"}, headers=priya).status_code == 422)
    check("reject without note -> 422", c.post(f"/claims/{cid}/decision", json={"outcome": "rejected"}, headers=priya).status_code == 422)
    r = c.post(f"/claims/{cid}/decision", json={"outcome": "approved", "amount": 8500, "note": "Agreed"}, headers=priya)
    check("approve own amount -> decided", r.json()["status"] == "decided" and r.json()["approved_amount"] == 8500, r.text)
    check("settle -> settled", c.post(f"/claims/{cid}/settle", headers=priya).json()["status"] == "settled")
    check("settle again -> 409", c.post(f"/claims/{cid}/settle", headers=priya).status_code == 409)
    hist = c.get(f"/insurer/claims/{cid}", headers=priya).json()["history"]
    check("every move in history with who and when (9 rows)",
          len(hist) == 9 and all(h["by"] and h["at"].endswith("+00:00") for h in hist), hist)

    print("\n-- claim history and payout breakdown")
    check("suggested payout before any history = 8900 (no deduction)",
          c.get(f"/insurer/claims/{cid}", headers=priya).json()["payout_breakdown"]["history_rate"] == 0)
    c.post(f"/claims/{cid2}/quotation", json=q, headers=kavya)
    v = c.post(f"/claims/{cid2}/start-review", headers=priya).json()
    b = v["payout_breakdown"]
    check("breakdown fields", b and set(b) >= {"quotation_total", "deductible", "after_deductible", "recent_approved_claims",
                                             "history_rate", "history_deduction", "suggested_payout", "explanation"}, b)
    check("1 recent approved claim -> 5% of 8900 = 445 off, suggested 8455",
          (b["quotation_total"], b["deductible"], b["after_deductible"], b["recent_approved_claims"],
           b["history_rate"], b["history_deduction"], b["suggested_payout"]) == (10900, 2000, 8900, 1, 0.05, 445, 8455), b)
    check("suggested_payout matches the breakdown", v["suggested_payout"] == 8455, v["suggested_payout"])
    check("explanation sentence", "₹8,900" in b["explanation"] and "5%" in b["explanation"]
          and b["explanation"].endswith("Suggested payout: ₹8,455."), b["explanation"])
    check("recent_approved_claims lists the earlier claim",
          [(x["id"], x["approved_amount"]) for x in v["recent_approved_claims"]] == [(cid, 8500)], v["recent_approved_claims"])
    check("previous_claims carry approved_amount",
          [(x["id"], x["approved_amount"]) for x in v["previous_claims"]] == [(cid, 8500)], v["previous_claims"])
    va = c.get(f"/assessor/claims/{cid2}", headers=kavya).json()
    check("assessor view has the history but no payout breakdown",
          va["recent_approved_claims"] and "payout_breakdown" not in va and "suggested_payout" not in va, list(va))
    db = SessionLocal()
    for n, (approved, day_) in enumerate([(True, "2026-03-01"), (True, "2026-04-01"), (True, "2026-05-01"),
                                          (True, "2026-06-01"), (True, "2025-06-01"), (False, "2026-07-01")]):
        db.add(models.Claim(claimant_id=1, vehicle_id=1, policy_id=1, incident_date=date.fromisoformat(day_),
                            incident_time="10:00", location="x", severity="minor", description=f"old {n}",
                            status="decided", decision="approved" if approved else "rejected",
                            approved_amount=1000 if approved else None))
    db.commit()
    db.close()
    b = c.get(f"/insurer/claims/{cid2}", headers=priya).json()["payout_breakdown"]
    check("only approved claims in the last 12 months count; rate capped at 20%",
          (b["recent_approved_claims"], b["history_rate"], b["history_deduction"], b["suggested_payout"]) == (5, 0.2, 1780, 7120), b)

    # a claim sent for further review cannot be settled
    check("old outcome fraud_review -> 422", c.post(f"/claims/{cid2}/decision", json={"outcome": "fraud_review", "note": "x"},
                                                   headers=priya).status_code == 422)
    r = c.post(f"/claims/{cid2}/decision", json={"outcome": "further_review", "note": "AI-generated photo"}, headers=priya)
    check("further_review -> decided", r.status_code == 200 and r.json()["decision"] == "further_review", r.text)
    check("settle a further_review claim -> 409", c.post(f"/claims/{cid2}/settle", headers=priya).status_code == 409)
    check("claimant sees decision further_review", c.get(f"/me/claims/{cid2}", headers=ravi).json()["decision"] == "further_review")
    queue = c.get("/insurer/claims", headers=priya).json()
    check("queue: fraud flag first", queue[0]["id"] == cid2, [(x["id"], x["fraud_flag"]) for x in queue])
    check("filter ?status=", [x["id"] for x in c.get("/insurer/claims?status=settled", headers=priya).json()] == [cid])
    check("filter ?risk=", [x["id"] for x in c.get("/insurer/claims?risk=high", headers=priya).json()] == [cid2])

    print("\n-- access rules")
    r = c.post("/claims", json={**body, "vehicle_id": meena_vid, "incident_date": "2026-10-01"}, headers=meena)
    meena_claim = r.json()["id"]
    check("Ravi opens Meena's claim -> 403", c.get(f"/me/claims/{meena_claim}", headers=ravi).status_code == 403)
    check("Ravi uploads to Meena's claim -> 403", c.post(f"/claims/{meena_claim}/images",
          files=[("files", ("d.jpg", JPEG, "image/jpeg"))], headers=ravi).status_code == 403)
    check("unknown claim -> 404", c.get("/me/claims/9999", headers=ravi).status_code == 404)
    for path in ["/assessor/claims", f"/assessor/claims/{cid}", "/price-list", "/insurer/claims", f"/insurer/claims/{cid}"]:
        check(f"claimant GET {path} -> 403", c.get(path, headers=ravi).status_code == 403)
    for action in ["quotation", "start-review", "request-info", "decision", "settle"]:
        check(f"claimant POST /claims/id/{action} -> 403", c.post(f"/claims/{cid}/{action}", json={}, headers=ravi).status_code == 403)
    check("assessor -> insurer endpoint 403", c.get("/insurer/claims", headers=suresh).status_code == 403)
    check("insurer -> POST /claims 403", c.post("/claims", json=body, headers=priya).status_code == 403)

    print("\n-- no risk information for claimants")
    words = ["risk_score", "risk_level", "reasons", "fraud", "heatmap", "modules", "suggested_payout",
             "payout_breakdown", "history_deduction", "recent_approved_claims", "previous_claims"]
    texts = [c.get("/me/claims", headers=h).text for h in (ravi, meena)]
    texts += [c.get(f"/me/claims/{x['id']}", headers=h).text for h in (ravi, meena) for x in c.get("/me/claims", headers=h).json()]
    leaks = [w for t in texts for w in words if w in t]
    check("claimant responses contain no risk fields", not leaks, leaks)

    print(f"\n{'ALL PASSED' if not fails else f'{fails} FAILED'}")
    return fails


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
