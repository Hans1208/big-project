import json
import tempfile
import unittest
from pathlib import Path

from status_report import build_report


class StatusReportTests(unittest.TestCase):
    def test_reports_pending_labels_and_partition_positives(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            packets = root / "packets"; packets.mkdir()
            split = root / "split.json"
            split.write_text(json.dumps({"assignments": {"train": ["A"], "validation": ["B"], "test": ["C"]}}), encoding="utf-8")
            for case_id, label in (("A", False), ("B", True), ("C", None)):
                packet = {"case_id": case_id, "labeling_status": "completed_human_review" if label is not None else "pending_human_review", "claims": [{"is_hallucination": label}]}
                (packets / f"SYN-{case_id}.json").write_text(json.dumps(packet), encoding="utf-8")
            report = build_report(packets, split)
            self.assertIn("|validation|1|1|1|1|0|", report)
            self.assertIn("|test|1|0|0|0|1|", report)
            self.assertIn("평가 보류", report)
