import unittest

from second_review import build_blind_packet, cohen_kappa


class SecondReviewTests(unittest.TestCase):
    def test_blind_packet_excludes_primary_labels(self):
        source = {"case_id": "SYN-E-001", "candidate_output_path": "x", "answer_generator": "model", "claims": [{"claim_id": "SYN-E-001-C01", "text": "claim", "is_supported": True, "is_hallucination": False, "reviewer_rationale": "reason"}]}
        blind = build_blind_packet(source)
        self.assertIsNone(blind["claims"][0]["is_hallucination"])
        self.assertNotIn("reason", str(blind))

    def test_kappa_perfect_agreement(self):
        self.assertEqual(cohen_kappa([True, False], [True, False]), 1.0)
