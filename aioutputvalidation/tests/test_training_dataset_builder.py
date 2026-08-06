import unittest

from training_dataset_builder import build_training_rows, build_v2_training_rows


def make_packet(**overrides):
    packet = {
        "case_id": "SYN-E-001",
        "reviewer_id": "human",
        "labeling_status": "completed_human_review",
        "claims": [{"claim_id": "SYN-E-001-C01", "is_hallucination": False}],
    }
    packet.update(overrides)
    return packet


def make_observation(**overrides):
    observation = {
        "case_id": "SYN-E-001",
        "claim_scores": [{"claim_id": "SYN-E-001-C01", "evidence_score": 0.8, "evidence_margin": 0.3}],
        "schema_error": 0,
        "low_support_ratio": 0.0,
        "citation_missing_ratio": 0.0,
        "uncertainty_disclosed": True,
        "explicit_conflicts": [],
        "unsupported_assertions": [],
    }
    observation.update(overrides)
    return observation


class TrainingDatasetBuilderTests(unittest.TestCase):
    def test_rejects_mismatched_case_ids(self):
        with self.assertRaises(ValueError):
            build_training_rows(make_packet(), make_observation(case_id="SYN-E-002"))

    def test_rejects_packets_without_completed_human_review(self):
        with self.assertRaises(ValueError):
            build_training_rows(make_packet(labeling_status="pending_human_review"), make_observation())

    def test_rejects_non_boolean_is_hallucination(self):
        packet = make_packet(claims=[{"claim_id": "SYN-E-001-C01", "is_hallucination": None}])
        with self.assertRaises(ValueError):
            build_training_rows(packet, make_observation())

    def test_rejects_claim_missing_from_observation(self):
        packet = make_packet(claims=[{"claim_id": "SYN-E-001-C99", "is_hallucination": False}])
        with self.assertRaises(ValueError):
            build_training_rows(packet, make_observation())

    def test_builds_one_row_per_claim_with_labeler_and_case_id(self):
        rows = build_training_rows(make_packet(), make_observation())
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["case_id"], "SYN-E-001")
        self.assertEqual(row["claim_id"], "SYN-E-001-C01")
        self.assertEqual(row["labeler_id"], "human")
        self.assertEqual(row["is_hallucination"], False)
        self.assertEqual(set(row["features"]), {"schema_error", "evidence_gap", "low_support_ratio", "citation_missing_ratio", "uncertainty_absent"})

    def test_v2_rejects_claim_missing_evidence_margin(self):
        observation = make_observation(claim_scores=[{"claim_id": "SYN-E-001-C01", "evidence_score": 0.8}])
        with self.assertRaises(ValueError):
            build_v2_training_rows(make_packet(), observation)

    def test_v2_rows_keep_v1_features_and_add_conflict_flags(self):
        observation = make_observation(explicit_conflicts=["unmatched_specific_date"], unsupported_assertions=["책임을 부인"])
        row = build_v2_training_rows(make_packet(), observation)[0]
        self.assertEqual(row["feature_contract"], "claim_evidence_v2")
        self.assertEqual(row["features"]["explicit_conflict_present"], 1)
        self.assertEqual(row["features"]["unsupported_assertion_present"], 1)
        self.assertEqual(row["features"]["schema_error"], 0.0)
        self.assertEqual(row["features"]["low_support_ratio"], 0.0)


if __name__ == "__main__":
    unittest.main()
