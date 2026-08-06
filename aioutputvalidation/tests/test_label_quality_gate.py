import unittest

from label_quality_gate import packet_errors, summarize_packets


PACKET = {"case_id": "SYN-E-001", "answer_generator": "gemini", "reviewer_id": "reviewer", "labeling_status": "completed_human_review", "claims": [{"claim_id": "C1", "is_supported": True, "is_hallucination": False}]}


class LabelQualityGateTests(unittest.TestCase):
    def test_completed_independent_packet_passes(self):
        self.assertEqual(packet_errors(PACKET, "scenario_author"), [])

    def test_pending_packet_is_blocked(self):
        pending = dict(PACKET, reviewer_id=None, labeling_status="pending_human_review")
        self.assertTrue(packet_errors(pending))

    def test_summary_reports_difficulty_and_labels(self):
        result = summarize_packets([PACKET], {"SYN-E-001": "easy"})
        self.assertEqual(result["packets_by_difficulty"], {"easy": 1})
        self.assertEqual(result["hallucination_labels"], {"False": 1})


if __name__ == "__main__":
    unittest.main()
