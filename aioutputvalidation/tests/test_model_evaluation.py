import unittest

from dataset_split import build_case_split
from model_evaluation import evaluate_fixed_split
from training import FEATURE_NAMES


class ModelEvaluationTests(unittest.TestCase):
    def test_reports_held_out_accuracy(self):
        catalog = [{"case_id": f"SYN-{difficulty[0].upper()}-{index}", "difficulty": difficulty} for difficulty in ("easy", "medium", "hard") for index in range(6)]
        split = build_case_split(catalog)
        rows = []
        for index, item in enumerate(catalog):
            for label in (False, True):
                rows.append({"case_id": item["case_id"], "claim_id": f"{item['case_id']}-{label}", "features": dict(zip(FEATURE_NAMES, [int(label), float(label), float(label), float(label), int(label)])), "is_hallucination": label})
        _, report = evaluate_fixed_split(rows, split)
        self.assertIn("accuracy", report["test"])
        self.assertEqual(report["split_counts"], {"train": 22, "validation": 8, "test": 6})
