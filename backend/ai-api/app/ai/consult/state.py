"""
app/agents/consult/state.py

기존에 case_analysis/graph.py, rescue_check/modal.py, missing_check/modal.py에
각각 나눠져 있던 ConsultState / MissingDataState를 하나로 합친 것.

주의: extracted_content(파일별 추출 결과 배열)와 extracted_content_text(rescue_check/
missing_check 단계가 프롬프트에 바로 쓰는 합쳐진 문자열)를 분리해서 갖고 있는데,
이는 새 필드를 "추가"한 게 아니라 기존에 각 모듈이 각자 다시 계산하던 것
(rescue_check.EligibilityCheckRequest.to_consult_fields, missing_check도 동일 로직 재구현)을
한 곳(build_extracted_text_node)에서 한 번만 계산해 중복 구현을 없앤 것.
"""

from typing import List, TypedDict


class ConsultState(TypedDict, total=False):
    # --- 입력 ---
    raw_input: dict

    # --- parse_input (기존 case_analysis) ---
    summary: str
    details: str
    submitted_file_link: List[str]
    consult_day: str

    # --- process_multimodal_content (기존 case_analysis) ---
    extracted_content: List[str]  # 파일별 추출 텍스트 배열. extracted_content_detail과 동일 인덱스
    extracted_content_detail: list

    # rescue_check/missing_check가 프롬프트에 바로 쓰는, "내용없음"/"파일 오류"를 걸러
    # 이어붙인 문자열. (기존에는 EligibilityCheckRequest.to_consult_fields()가 매번
    # 다시 계산하던 것을 그래프 내부에서 한 번만 계산해 재사용)
    extracted_content_text: str

    # --- classify_case_type / classify_emergency (기존 case_analysis) ---
    case_list: list  # [{"case_ratio": float, "case_type": str, "case_type_reason": str}, ...]
    case_emergency_ratio: float
    case_emergency_level: str
    case_emergency_reason: str

    # --- combine_case_analysis (기존 case_analysis.combine_output_node) ---
    case_analysis: dict

    # --- extract_all_signals / eligibility_rule / build_checklist (기존 rescue_check) ---
    income_property_signal: dict
    special_status_signal: dict
    eligibility_result: dict
    winnability_signal: dict
    executability_signal: dict
    appropriateness_signal: dict
    relief_review_checklist: dict

    # --- candidate_generation / validation / document_mapping (기존 missing_check) ---
    candidate_missing_items: List[dict]
    validated_missing_items: List[dict]
    missing_items: List[dict]
