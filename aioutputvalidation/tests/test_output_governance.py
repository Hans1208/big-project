import unittest

from output_governance import validate_output_bundle


MANIFEST = {"case_id": "SYN-E-001", "scenario_author": "author_a", "answer_generator": "generator_b", "gold_labeler": "labeler_c"}
OUTPUT = {"summary": "요약", "case_type": "친족", "case_subtype": "이혼 및 위자료", "urgency_level": "중", "eligibility": "확인필요", "extracted_json": {"당사자": [], "금액": None, "날짜": [], "사건개요": "개요"}, "missing_info_json": [], "checklist_json": [], "timeline_json": []}


class OutputGovernanceTests(unittest.TestCase):
    def test_independent_complete_bundle_passes(self):
        bundle = {"case_id": "SYN-E-001", "answer_generator": "generator_b", "ai_output": OUTPUT, "rag_results": []}
        self.assertEqual(validate_output_bundle(bundle, MANIFEST), [])

    def test_gold_label_leak_and_role_overlap_are_blocked(self):
        bundle = {"case_id": "SYN-E-001", "answer_generator": "author_a", "ai_output": OUTPUT, "rag_results": [], "is_hallucination": False}
        errors = validate_output_bundle(bundle, MANIFEST)
        self.assertTrue(any("distinct" in error for error in errors))
        self.assertTrue(any("gold-label" in error for error in errors))

    def test_empty_required_content_is_blocked(self):
        incomplete = dict(OUTPUT)
        incomplete["summary"] = ""
        bundle = {"case_id": "SYN-E-001", "answer_generator": "generator_b", "ai_output": incomplete, "rag_results": []}
        self.assertTrue(any("AI output schema" in error for error in validate_output_bundle(bundle, MANIFEST)))


if __name__ == "__main__":
    unittest.main()
