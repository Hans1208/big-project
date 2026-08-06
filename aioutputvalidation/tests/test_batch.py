import unittest

from batch import validate_records


OUTPUT = {"summary": "요약", "case_type": "친족", "case_subtype": "이혼 및 위자료", "urgency_level": "중", "eligibility": "확인필요", "extracted_json": {"당사자": [], "금액": None, "날짜": [], "사건개요": "개요"}, "missing_info_json": [], "checklist_json": [], "timeline_json": []}


class BatchTests(unittest.TestCase):
    def test_aggregates_decisions_and_privacy_safe_audits(self):
        report = validate_records([{"record_id": "ANON-001", "ai_output": OUTPUT, "claim_embeddings": [[1, 0]], "evidence_embeddings": [[1, 0]], "cited_claim_count": 1}])
        self.assertEqual(report["total_records"], 1)
        self.assertEqual(report["decision_counts"]["safe"], 1)
        self.assertEqual(report["audits"][0]["record_id"], "ANON-001")


if __name__ == "__main__":
    unittest.main()
