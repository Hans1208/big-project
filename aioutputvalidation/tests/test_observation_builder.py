import unittest

from observation_builder import build_observation, split_evidence_chunks
from training_dataset_builder import build_training_rows, build_v2_training_rows


def fake_embed(texts):
    return [[1.0, 0.0] if "사실" in text else [0.0, 1.0] for text in texts]


class ObservationBuilderTests(unittest.TestCase):
    def test_builds_label_independent_observation(self):
        bundle = {"case_id": "SYN-E-001", "ai_output": {"summary": "사실 요약", "extracted_json": {"사건개요": "사실 개요"}, "timeline_json": []}}
        observation = build_observation(bundle, "사실 상담 전사", fake_embed)
        self.assertEqual(observation["schema_error"], 1)
        self.assertGreater(observation["schema_error_count"], 0)
        self.assertIn("evidence_margin", observation["claim_scores"][0])
        self.assertNotIn("is_hallucination", observation)

    def test_completed_labels_join_with_observations(self):
        packet = {"case_id": "SYN-E-001", "reviewer_id": "human", "labeling_status": "completed_human_review", "claims": [{"claim_id": "SYN-E-001-C01", "is_hallucination": False}]}
        observation = {"case_id": "SYN-E-001", "claim_scores": [{"claim_id": "SYN-E-001-C01", "evidence_score": 0.8}], "schema_error": 0, "low_support_ratio": 0.0, "citation_missing_ratio": 0.0, "uncertainty_disclosed": True}
        rows = build_training_rows(packet, observation)
        self.assertEqual(rows[0]["features"]["evidence_gap"], 0.2)

    def test_v2_rows_include_claim_evidence_and_conflict_features(self):
        packet = {"case_id": "SYN-E-001", "reviewer_id": "human", "labeling_status": "completed_human_review", "claims": [{"claim_id": "SYN-E-001-C01", "is_hallucination": True}]}
        observation = {"case_id": "SYN-E-001", "claim_scores": [{"claim_id": "SYN-E-001-C01", "evidence_score": 0.8, "evidence_margin": 0.3}], "schema_error": 0, "low_support_ratio": 0.0, "citation_missing_ratio": 0.0, "uncertainty_disclosed": True, "explicit_conflicts": ["unmatched_specific_date"], "unsupported_assertions": []}
        row = build_v2_training_rows(packet, observation)[0]
        self.assertEqual(row["features"]["evidence_ambiguity"], 0.7)
        self.assertEqual(row["features"]["explicit_conflict_present"], 1)

    def test_splits_transcript_into_speaker_evidence_chunks(self):
        chunks = split_evidence_chunks("[header]\n상담자: 질문\n내담자: 답변")
        self.assertEqual(chunks, ["상담자: 질문", "내담자: 답변"])

    def test_splits_a_single_turn_into_sentence_evidence_chunks(self):
        chunks = split_evidence_chunks("내담자: 2025. 1. 3.부터 별거했습니다. 위자료를 청구하고 싶습니다.")
        self.assertEqual(chunks, ["내담자: 2025. 1. 3.부터 별거했습니다.", "위자료를 청구하고 싶습니다."])


if __name__ == "__main__":
    unittest.main()
