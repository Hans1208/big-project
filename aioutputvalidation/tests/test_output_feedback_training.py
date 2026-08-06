import unittest

from output_feedback_training import build_row


class OutputFeedbackTrainingTests(unittest.TestCase):
    def test_builds_binary_row_from_completed_output_review(self):
        row = build_row(
            {"case_id": "SYN-R9-E-001", "review_status": "completed_human_output_review", "reviewer_decision": "review_required", "reviewer_id": "reviewer-a"},
            {"case_id": "SYN-R9-E-001", "schema_error": 0, "low_support_ratio": 0.2, "citation_missing_ratio": 0, "uncertainty_disclosed": True, "claim_scores": [{"evidence_score": 0.8}]},
        )
        self.assertTrue(row["is_hallucination"])
        self.assertEqual(row["features"]["evidence_gap"], 0.2)
