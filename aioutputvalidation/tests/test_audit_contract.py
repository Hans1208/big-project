import unittest

from audit import build_audit_record
from audit_contract import output_validation_contract_errors
from validator import validate


class AuditContractTests(unittest.TestCase):
    def test_generated_audit_obeys_api_contract(self):
        result = validate({}, [[1, 0]], [[1, 0]], cited_claim_count=1)
        self.assertEqual(output_validation_contract_errors(build_audit_record(result)), [])

    def test_contract_rejects_sensitive_extra_field(self):
        result = validate({}, [[1, 0]], [[1, 0]], cited_claim_count=1)
        record = build_audit_record(result)
        record["consultation_text"] = "must not be here"
        self.assertTrue(output_validation_contract_errors(record))


if __name__ == "__main__":
    unittest.main()
