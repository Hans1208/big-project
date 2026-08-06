import unittest

from output_review_feedback import build_feedback_packet


class OutputReviewFeedbackTests(unittest.TestCase):
    def test_feedback_packet_hides_model_decision(self):
        packet = build_feedback_packet({"case_id": "SYN-E-001", "decision": "high_risk"})
        self.assertNotIn("high_risk", str(packet))
        self.assertEqual(packet["review_status"], "pending_human_output_review")
