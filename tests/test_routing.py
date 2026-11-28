"""Tests for backend/app/routing.py.

Run from the repository root:
    python -m unittest tests/test_routing.py
(pytest also works: python -m pytest tests/test_routing.py)
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.routing import route_claim  # noqa: E402

ASSESSORS = [{"id": 3, "open_claims": 2}, {"id": 4, "open_claims": 1}]


class FraudFlagTests(unittest.TestCase):
    def test_high_risk_sets_fraud_flag(self):
        self.assertTrue(route_claim("high", ASSESSORS)["fraud_flag"])

    def test_low_risk_has_no_fraud_flag(self):
        self.assertFalse(route_claim("low", ASSESSORS)["fraud_flag"])

    def test_medium_risk_has_no_fraud_flag(self):
        self.assertFalse(route_claim("medium", ASSESSORS)["fraud_flag"])


class AssessorTests(unittest.TestCase):
    def test_least_busy_assessor_is_chosen(self):
        self.assertEqual(route_claim("low", ASSESSORS)["assessor_id"], 4)

    def test_tie_picks_lower_id(self):
        tied = [{"id": 9, "open_claims": 1}, {"id": 5, "open_claims": 1}]
        self.assertEqual(route_claim("low", tied)["assessor_id"], 5)

    def test_single_assessor(self):
        self.assertEqual(route_claim("high", [{"id": 7, "open_claims": 10}])["assessor_id"], 7)

    def test_result_shape(self):
        self.assertEqual(route_claim("medium", ASSESSORS), {"fraud_flag": False, "assessor_id": 4})


class BadInputTests(unittest.TestCase):
    def test_unknown_risk_level(self):
        with self.assertRaises(ValueError):
            route_claim("HIGH", ASSESSORS)

    def test_no_assessors(self):
        with self.assertRaises(ValueError):
            route_claim("low", [])


if __name__ == "__main__":
    unittest.main()
