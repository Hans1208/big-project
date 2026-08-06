import json
import tempfile
import unittest
from pathlib import Path

from output_feedback_calibration import collect


class OutputFeedbackCalibrationTests(unittest.TestCase):
    def test_collects_blind_feedback_without_duplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); results = root / "results"; feedback = root / "feedback"; results.mkdir(); feedback.mkdir()
            (results / "SYN-A.json").write_text(json.dumps({"hallucination_probability": 0.8}), encoding="utf-8")
            (feedback / "SYN-A.json").write_text(json.dumps({"review_status": "completed_human_output_review", "reviewer_decision": "high_risk"}), encoding="utf-8")
            self.assertEqual(collect(results, [feedback]), ([True], [0.8]))
