import unittest

from pathlib import Path
import tempfile

from training import FEATURE_NAMES, FEATURE_NAMES_V2, load_jsonl, mlp_probability, train_mlp


class TrainingTests(unittest.TestCase):
    def test_trains_versioned_mlp(self):
        rows = [
            {"features": dict(zip(FEATURE_NAMES, [0, 0.0, 0.0, 0.0, 0])), "is_hallucination": False},
            {"features": dict(zip(FEATURE_NAMES, [1, 1.0, 1.0, 1.0, 1])), "is_hallucination": True},
        ]
        model = train_mlp(rows, epochs=10)
        self.assertEqual(model["architecture"], [5, 8, 1])
        self.assertEqual(len(model["weights_1"]), 8)
        self.assertEqual(len(model["weights_1"][0]), 5)

    def test_trains_v2_feature_contract(self):
        rows = [
            {"features": dict(zip(FEATURE_NAMES_V2, [0, 0, 0, 0, 0, 0, 0, 0])), "is_hallucination": False},
            {"features": dict(zip(FEATURE_NAMES_V2, [1, 1, 1, 1, 1, 1, 1, 1])), "is_hallucination": True},
        ]
        model = train_mlp(rows, epochs=10, feature_names=FEATURE_NAMES_V2)
        self.assertEqual(model["architecture"], [8, 8, 1])
        self.assertIn("evidence_ambiguity", model["feature_names"])
        self.assertGreaterEqual(mlp_probability(rows[1]["features"], model), 0.0)

    def test_load_jsonl_accepts_explicit_v2_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rows.jsonl"
            path.write_text('{"features": {"schema_error": 0, "evidence_gap": 0, "low_support_ratio": 0, "citation_missing_ratio": 0, "uncertainty_absent": 0, "evidence_ambiguity": 0, "explicit_conflict_present": 0, "unsupported_assertion_present": 0}, "is_hallucination": false}\n', encoding="utf-8")
            self.assertEqual(len(load_jsonl(path, FEATURE_NAMES_V2)), 1)


if __name__ == "__main__":
    unittest.main()
