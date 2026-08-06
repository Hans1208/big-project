import unittest

from contrastive_evaluation import attach_multi_positive_labels, evaluate_packets


def embed_claims(texts):
    return [[1.0, 0.0] if text == "claim" else [0.0, 1.0] for text in texts]


def embed_evidence(texts):
    return [[1.0, 0.0] if text == "positive" else [0.8, 0.2] for text in texts]


class ContrastiveEvaluationTests(unittest.TestCase):
    def test_reports_recall_and_hard_negative_margin(self):
        packet = {
            "reviewer_id": "human", "labeling_status": "completed_human_review",
            "evidence_chunks": [{"evidence_id": "E1", "text": "positive"}, {"evidence_id": "E2", "text": "negative"}],
            "claims": [
                {"text": "claim", "support_status": "supported", "supporting_evidence_id": "E1", "hard_negative_evidence_id": "E2"},
                {"text": "unsupported", "support_status": "unsupported", "supporting_evidence_id": None, "hard_negative_evidence_id": None},
            ],
        }
        report = evaluate_packets([packet], embed_claims, embed_evidence)
        self.assertEqual(report["recall_at_1"], 1.0)
        self.assertEqual(report["hard_negative_pairs"], 1)
        self.assertGreater(report["hard_negative_mean_margin"], 0)

    def test_multi_positive_label_makes_any_direct_support_a_hit(self):
        source = {"case_id": "A", "reviewer_id": "human", "labeling_status": "completed_human_review", "evidence_chunks": [{"evidence_id": "E1", "text": "positive"}, {"evidence_id": "E2", "text": "negative"}], "claims": [{"claim_id": "C1", "text": "claim", "support_status": "supported", "supporting_evidence_id": "E2", "hard_negative_evidence_id": None}]}
        multi = {"case_id": "A", "reviewer_id": "human", "labeling_status": "completed_human_review", "evidence_chunks": [{"evidence_id": "E1"}, {"evidence_id": "E2"}], "claims": [{"claim_id": "C1", "supporting_evidence_ids": ["E1", "E2"]}]}
        report = evaluate_packets(attach_multi_positive_labels([source], [multi]), embed_claims, embed_evidence)
        self.assertEqual(report["recall_at_1"], 1.0)
