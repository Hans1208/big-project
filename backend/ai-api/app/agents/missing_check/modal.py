"""
agents/missing_data/modal.py

누락자료/추가조사 필요항목 감지에 쓰이는 모든 pydantic 스키마, LangGraph State,
FastAPI 요청/응답 모델을 모아둔 모듈.

- 이 노드는 사건유형 후보(case_list)에 상관없이 범용 로직으로 동작한다 (사건유형별 분기 없음).
- candidate_generation 단계는 자유 판단으로 후보를 뽑고, validation 단계가
  confidence 점수를 매겨 최종 채택 여부를 코드 레벨(threshold)에서 결정한다.
  -> 어느 쪽도 "~이다" 식 확정적 법률판단을 내리지 않음 (HITL 원칙 유지).
"""

from typing import TypedDict, List, Literal, Optional

from pydantic import BaseModel, Field

from app.agents.rescue_check.modal import (
    LLMSignalBase,
    RawInput,
    CaseAnalysisPayload,
    EligibilityCheckRequest,
    ConsultState,
)


# ---------------------------------------------------------------------------
# 누락 항목 스키마
# ---------------------------------------------------------------------------

MissingItemType = Literal["증빙", "사실관계"]

# 서류를 확보하는 방식 - document_mapping 단계에서 상담원/변호사 안내 문구 분기용으로 사용.
# - 본인발급: 정부24/홈택스 등에서 당사자가 즉시 발급 가능
# - 제3자발급: 상대방/기관이 보유 또는 신고한 내역을 당사자가 열람·요청해야 하는 경우
# - 절차확보: 진정/소송 등 공식 절차(법원 조회명령, 근로감독관 조사 등)를 거쳐야만 확보되는 경우
AcquisitionType = Literal["본인발급", "제3자발급", "절차확보"]


class ReferenceDocument(BaseModel):
    """missing_item 하나에 대응하는, 한국 내 실제 확인 가능 서류 1건.

    LLM이 자유 생성하되 doc_name/issuing_authority는 실존 서류명·기관명 그대로 쓰도록
    프롬프트에서 강제한다 (없는 서류를 지어내지 않도록 - 할루시네이션 방지 대상).
    """
    doc_name: str = Field(description="서류의 정식 명칭 (예: 폐업사실증명원)")
    issuing_authority: str = Field(description="발급/작성 기관 (예: 관할 세무서, 근로복지공단)")
    acquisition_type: AcquisitionType = Field(
        description="본인발급 / 제3자발급 / 절차확보 중 하나"
    )
    acquisition_type_desc: str = Field(
        description="acquisition_type에 대한 1문장 부연 설명 (누가, 어떤 방식으로 확보하는지)"
    )
    online_issuance: bool = Field(description="온라인으로 즉시 발급 가능한지 여부")
    online_issuance_channel: Optional[str] = Field(
        default=None, description="온라인 발급 채널명 (예: 정부24, 홈택스). 불가 시 null"
    )
    related_law: Optional[str] = Field(
        default=None, description="근거 법령명 (해당되는 경우만, 없으면 null)"
    )
    notes: Optional[str] = Field(
        default=None, description="발급 제한사항, 소요기간, 대체 서류 등 실무 유의사항"
    )


class MissingItemCandidate(LLMSignalBase):
    """후보 생성(candidate_generation) 단계 출력 - 아직 검증 전"""
    item: str = Field(description="누락된 것으로 보이는 구체적 항목명")
    type: MissingItemType = Field(description="증빙자료 부족인지, 사실관계 미확정인지")
    reason: str = Field(description="왜 이 항목이 필요한지, 어떤 판단/서식 작성에 영향을 주는지")


class MissingItemValidated(MissingItemCandidate):
    """검증(validation) 단계 출력 - 신뢰도 점수 포함"""
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="이 항목이 '실제로 원본 자료에 없다'는 판단에 대한 확신도 (0~1)",
    )
    evidence_check_note: str = Field(
        description="원본 텍스트를 재확인한 근거 요약 (왜 이 confidence를 매겼는지)"
    )


class MissingItemWithDocuments(MissingItemValidated):
    """서류 매핑(document_mapping) 단계 출력 - 실제 확인 가능 서류 목록 포함.

    최종 API 응답(MissingDataCheckResponse.missing_items)은 이 스키마 기준."""
    reference_documents: List[ReferenceDocument] = Field(
        default_factory=list,
        description="이 누락 항목을 확인/보완할 수 있는 한국 내 실제 서류 목록 (1~3개 권장)",
    )


class CandidateList(BaseModel):
    candidates: List[MissingItemCandidate] = Field(default_factory=list)


class ValidatedList(BaseModel):
    validated: List[MissingItemValidated] = Field(default_factory=list)


class DocumentMappedList(BaseModel):
    items: List[MissingItemWithDocuments] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# LangGraph State (rescue_check.ConsultState 확장)
# ---------------------------------------------------------------------------

class MissingDataState(ConsultState, total=False):
    # relief_review_checklist 등 어제/오늘 단계 필드는 ConsultState에 이미 포함되어 있음.
    candidate_missing_items: List[dict]
    validated_missing_items: List[dict]  # validation 단계 출력 (threshold 통과분, 서류 매핑 전)
    missing_items: List[dict]  # 최종 산출물 (reference_documents 포함, 화면 노출 + 다음 노드 공용)


# ---------------------------------------------------------------------------
# FastAPI 요청/응답 모델
# ---------------------------------------------------------------------------

class MissingDataCheckRequest(BaseModel):
    """/eligibility/analyze 까지의 응답을 그대로 이 스키마로 받아서 넘기는 구조."""
    raw_input: RawInput
    case_analysis: CaseAnalysisPayload
    relief_review_checklist: dict  # /eligibility/analyze 응답의 relief_review_checklist 그대로

    def to_consult_fields(self) -> dict:
        """EligibilityCheckRequest의 텍스트 조합 로직을 그대로 재사용하고,
        여기에 relief_review_checklist만 얹는다 (중복 로직 방지)."""
        base_fields = EligibilityCheckRequest(
            raw_input=self.raw_input,
            case_analysis=self.case_analysis,
        ).to_consult_fields()
        return {**base_fields, "relief_review_checklist": self.relief_review_checklist}


class MissingDataCheckResponse(BaseModel):
    missing_items: List[MissingItemWithDocuments]
