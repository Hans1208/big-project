import unittest

from evidence_diagnostics import rank_claim_evidence


class EvidenceDiagnosticsTests(unittest.TestCase):
    def test_reports_top_two_scores_margin_and_chunk_position(self):
        result = rank_claim_evidence([1, 0], [[0, 1], [0.8, 0.2], [1, 0]])
        self.assertEqual(result["top_evidence_chunk_index"], 2)
        self.assertEqual(result["evidence_score"], 1.0)
        self.assertGreater(result["evidence_margin"], 0.0)

    def test_empty_evidence_is_safe_to_serialize(self):
        result = rank_claim_evidence([1, 0], [])
        self.assertEqual(result["evidence_score"], 0.0)
        self.assertIsNone(result["top_evidence_chunk_index"])

    def test_single_candidate_has_no_margin_signal(self):
        result = rank_claim_evidence([1, 0], [[1, 0]])
        self.assertEqual(result["evidence_candidate_count"], 1)
        self.assertEqual(result["evidence_margin"], 0.0)
