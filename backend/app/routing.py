"""Claim routing rules for ClaimProof v2.

backend calls route_claim() once the photo checks have finished.
This module holds no database code: it only takes values and returns a
result, so it is easy to test (see tests/test_routing.py).
"""

RISK_LEVELS = ("low", "medium", "high")


def route_claim(risk_level: str, assessors: list[dict]) -> dict:
    """Decide the fraud flag and the assessor for a claim.

    assessors: [{"id": 3, "open_claims": 2}, ...]
    returns {"fraud_flag": bool, "assessor_id": int}

    - fraud_flag is True when risk_level is "high".
    - The assessor with the fewest open claims is chosen; on a tie,
      the lower id wins, so the result is predictable.

    Raises ValueError for an unknown risk level or an empty assessor list,
    so a setup mistake is reported instead of silently leaving a claim
    unassigned.
    """
    if risk_level not in RISK_LEVELS:
        raise ValueError(f"risk_level must be one of {RISK_LEVELS}, got {risk_level!r}")
    if not assessors:
        raise ValueError("No assessors available to assign the claim to")

    chosen = min(assessors, key=lambda a: (a["open_claims"], a["id"]))
    return {"fraud_flag": risk_level == "high", "assessor_id": chosen["id"]}
