import unittest

from multi_evidence_label_packet import build_multi_evidence_packet, validate_completed_packet


class MultiEvidenceLabelPacketTests(unittest.TestCase):
    def test_excludes_unsupported_claims_and_prior_choice(self):
        source = {"case_id": "A", "claims": [{"claim_id": "C1", "text": "keep", "support_status": "supported", "supporting_evidence_id": "E1"}, {"claim_id": "C2", "text": "skip", "support_status": "unsupported"}], "evidence_chunks": [{"evidence_id": "E1", "text": "one"}]}
        packet = build_multi_evidence_packet(source)
        self.assertEqual([claim["claim_id"] for claim in packet["claims"]], ["C1"])
        self.assertEqual(packet["claims"][0]["supporting_evidence_ids"], [])

    def test_completed_packet_requires_at_least_one_valid_choice(self):
        packet = {"reviewer_id": "human", "labeling_status": "completed_human_review", "evidence_chunks": [{"evidence_id": "E1"}], "claims": [{"supporting_evidence_ids": ["E1"]}]}
        validate_completed_packet(packet)
        packet["claims"][0]["supporting_evidence_ids"] = []
        with self.assertRaises(ValueError):
            validate_completed_packet(packet)
