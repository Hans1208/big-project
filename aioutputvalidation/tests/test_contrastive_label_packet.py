import unittest
from pathlib import Path

from contrastive_label_packet import build_contrastive_packet, validate_completed_packet


class ContrastiveLabelPacketTests(unittest.TestCase):
    def test_packet_is_blind_and_contains_sentence_chunks(self):
        bundle = {"case_id": "SYN-E-001", "ai_output": {"summary": "요약", "extracted_json": {"사건개요": "개요"}, "timeline_json": []}}
        packet = build_contrastive_packet(bundle, "내담자: 첫 근거입니다. 두 번째 근거입니다.", Path("generated/SYN-E-001.json"))
        self.assertEqual(packet["labeling_status"], "pending_human_review")
        self.assertEqual(len(packet["evidence_chunks"]), 2)
        self.assertTrue(all(claim["support_status"] is None for claim in packet["claims"]))

    def test_completed_packet_requires_distinct_valid_evidence(self):
        packet = {"reviewer_id": "human", "labeling_status": "completed_human_review", "evidence_chunks": [{"evidence_id": "E1"}, {"evidence_id": "E2"}], "claims": [{"support_status": "supported", "supporting_evidence_id": "E1", "hard_negative_evidence_id": "E2"}]}
        validate_completed_packet(packet)
        packet["claims"][0]["hard_negative_evidence_id"] = "E1"
        with self.assertRaises(ValueError):
            validate_completed_packet(packet)
