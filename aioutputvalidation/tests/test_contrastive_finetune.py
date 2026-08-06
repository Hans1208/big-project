import unittest

from contrastive_finetune import build_triplets


class ContrastiveFinetuneTests(unittest.TestCase):
    def test_uses_only_supported_claims_with_hard_negatives(self):
        packet = {"reviewer_id": "human", "labeling_status": "completed_human_review", "evidence_chunks": [{"evidence_id": "P", "text": "positive"}, {"evidence_id": "N", "text": "negative"}], "claims": [{"text": "keep", "support_status": "supported", "supporting_evidence_id": "P", "hard_negative_evidence_id": "N"}, {"text": "skip", "support_status": "unsupported", "supporting_evidence_id": None, "hard_negative_evidence_id": None}]}
        self.assertEqual(build_triplets([packet]), [("keep", "positive", "negative")])
