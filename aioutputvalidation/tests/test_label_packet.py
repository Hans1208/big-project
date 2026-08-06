import unittest
from pathlib import Path

from label_packet import build_label_packet


class LabelPacketTests(unittest.TestCase):
    def test_packet_has_blank_human_labels(self):
        bundle = {"case_id": "SYN-E-001", "answer_generator": "gemini", "ai_output": {"summary": "요약", "extracted_json": {"사건개요": "개요"}, "timeline_json": [{"내용": "사실"}]}}
        packet = build_label_packet(bundle, Path("generated/SYN-E-001.json"))
        self.assertEqual(packet["labeling_status"], "pending_human_review")
        self.assertTrue(all(claim["is_hallucination"] is None for claim in packet["claims"]))


if __name__ == "__main__":
    unittest.main()
