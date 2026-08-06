import unittest

from validator import cosine_similarity, load_model_weights, validate


PAYLOAD = {
    "summary": "요약", "case_type": "친족", "case_subtype": "이혼 및 위자료", "urgency_level": "중", "eligibility": "확인필요",
    "extracted_json": {"당사자": [], "금액": None, "날짜": [], "사건개요": "개요"}, "missing_info_json": [], "checklist_json": [], "timeline_json": []
}


class ValidatorTests(unittest.TestCase):
    def test_cosine_similarity(self):
        self.assertAlmostEqual(cosine_similarity([1, 0], [1, 0]), 1.0)

    def test_versioned_model_is_loaded(self):
        self.assertEqual(load_model_weights()["architecture"], [5, 8, 1])

    def test_supported_result_is_safe(self):
        result = validate(PAYLOAD, [[1, 0], [0.99, 0.01]], [[1, 0]], cited_claim_count=2)
        self.assertTrue(result.valid)
        self.assertEqual(result.decision, "safe")
        self.assertEqual(len(result.claim_evidence_scores), 2)
        self.assertEqual(result.to_dict()["decision"], "safe")

    def test_schema_error_is_high_risk(self):
        invalid = dict(PAYLOAD)
        invalid.pop("summary")
        result = validate(invalid, [[1, 0]], [[1, 0]], cited_claim_count=1)
        self.assertFalse(result.valid)
        self.assertEqual(result.decision, "high_risk")

    def test_case_type_and_subtype_mismatch_is_blocked(self):
        mismatched = dict(PAYLOAD)
        mismatched["case_subtype"] = "상속분"
        result = validate(mismatched, [[1, 0]], [[1, 0]], cited_claim_count=1)
        self.assertFalse(result.valid)
        self.assertEqual(result.decision, "high_risk")

    def test_unsupported_result_requires_review(self):
        result = validate(PAYLOAD, [[0, 1]], [[1, 0]], cited_claim_count=0)
        self.assertEqual(result.decision, "high_risk")


if __name__ == "__main__":
    unittest.main()
