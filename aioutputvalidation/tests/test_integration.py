import unittest

from integration import extract_claims, has_uncertainty_disclosure, validate_rag_output, validate_rag_output_with_service


PAYLOAD = {
    "summary": "별거 중인 신청인이 이혼과 위자료를 문의함.", "case_type": "친족", "case_subtype": "이혼 및 위자료",
    "urgency_level": "중", "eligibility": "확인필요",
    "extracted_json": {"당사자": [], "금액": None, "날짜": [], "사건개요": "이혼 상담"},
    "missing_info_json": [], "checklist_json": [], "timeline_json": [{"날짜": "2025-01", "내용": "별거 시작"}]
}


def fake_embed(texts):
    return [[1.0, 0.0] if "이혼" in text or "별거" in text else [0.0, 1.0] for text in texts]


class FakeEmbeddingService:
    def embed_query(self, text):
        return fake_embed([text])[0]

    def embed_documents(self, texts):
        return fake_embed(texts)


class IntegrationTests(unittest.TestCase):
    def test_extracts_deduplicated_claims(self):
        self.assertEqual(len(extract_claims(PAYLOAD)), 3)

    def test_existing_rag_shape_is_accepted(self):
        rag_results = [{"content": "별거와 이혼에 관한 법률상담 근거", "citation": "민법 제840조"}]
        result = validate_rag_output(PAYLOAD, rag_results, fake_embed)
        self.assertTrue(result.valid)
        self.assertIn(result.decision, {"safe", "review_required"})

    def test_missing_evidence_escalates(self):
        result = validate_rag_output(PAYLOAD, [], fake_embed)
        self.assertEqual(result.decision, "high_risk")

    def test_existing_service_shape_is_accepted(self):
        sources = {
            "related_statutes": [{"content": "이혼과 별거에 대한 법률 근거", "citation": "민법 제840조"}],
            "related_precedents": [],
        }
        result = validate_rag_output_with_service(PAYLOAD, sources, FakeEmbeddingService())
        self.assertTrue(result.valid)

    def test_detects_korean_uncertainty_cue(self):
        self.assertTrue(has_uncertainty_disclosure(["대상 여부는 추가 확인이 필요합니다."]))
        self.assertFalse(has_uncertainty_disclosure(["이혼 상담입니다."]))


if __name__ == "__main__":
    unittest.main()
