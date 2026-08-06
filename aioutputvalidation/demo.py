import json

from audit import build_audit_record
from validator import validate

payload = {
    "summary": "별거 중인 신청인이 이혼과 위자료를 문의함.", "case_type": "친족", "case_subtype": "이혼 및 위자료",
    "urgency_level": "중", "eligibility": "확인필요",
    "extracted_json": {"당사자": [], "금액": None, "날짜": [], "사건개요": "이혼 상담"},
    "missing_info_json": ["혼인관계증명서"], "checklist_json": [], "timeline_json": []
}

result = validate(payload, [[0.98, 0.02, 0.0], [0.90, 0.1, 0.0]], [[1.0, 0.0, 0.0]], cited_claim_count=2)
print(json.dumps(build_audit_record(result), ensure_ascii=False, indent=2))
