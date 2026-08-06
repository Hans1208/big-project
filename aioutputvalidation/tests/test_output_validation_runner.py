import tempfile
import unittest
from pathlib import Path

from output_validation_runner import validate_observation, write_review_queue


class OutputValidationRunnerTests(unittest.TestCase):
    def test_schema_error_is_high_risk(self):
        model = {"weights_1": [[0, 0, 0, 0, 0]] * 8, "bias_1": [0] * 8, "weights_2": [0] * 8, "bias_2": 0}
        observation = {"case_id": "SYN-E-001", "schema_error": 1, "claim_scores": [], "low_support_ratio": 1.0, "citation_missing_ratio": 1.0, "uncertainty_disclosed": False}
        self.assertEqual(validate_observation(observation, model, 0.5, "test")["decision"], "high_risk")

    def test_review_queue_contains_only_flagged_results(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "queue.md"
            write_review_queue([{"case_id": "A", "decision": "safe", "hallucination_probability": 0.1, "evidence_score": 0.9}, {"case_id": "B", "decision": "high_risk", "hallucination_probability": 0.9, "evidence_score": 0.1}], path)
            self.assertIn("B", path.read_text(encoding="utf-8"))
            self.assertNotIn("|A|", path.read_text(encoding="utf-8"))
