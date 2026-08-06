import unittest

from audit import build_audit_record
from validator import validate


class AuditTests(unittest.TestCase):
    def test_high_risk_record_explains_weak_evidence(self):
        result = validate({}, [[0, 1]], [[1, 0]], cited_claim_count=0)
        record = build_audit_record(result)
        self.assertEqual(record["decision"], "high_risk")
        self.assertTrue(record["review_reasons"])
        self.assertNotIn("summary", record)


if __name__ == "__main__":
    unittest.main()
