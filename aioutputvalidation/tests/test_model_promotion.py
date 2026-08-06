import tempfile
import unittest
from pathlib import Path

from model_promotion import promote


class ModelPromotionTests(unittest.TestCase):
    def test_promotes_candidate_passing_validation_recall_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = root / "candidate.json"
            candidate.write_text('{"architecture":[5,8,1]}', encoding="utf-8")
            manifest = promote(candidate, {"evaluation_version": "v1", "selected_threshold": 0.2, "validation": {"recall": 1.0, "f1": 0.5}}, root)
            self.assertTrue(manifest.exists())

    def test_blocks_candidate_below_recall_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "candidate.json"
            candidate.write_text('{"architecture":[5,8,1]}', encoding="utf-8")
            with self.assertRaises(ValueError):
                promote(candidate, {"evaluation_version": "v1", "selected_threshold": 0.2, "validation": {"recall": 0.1, "f1": 0.5}}, Path(directory))
