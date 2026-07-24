"""
agents/missing_data/graph.py

누락자료 / 추가조사 필요항목 감지 LangGraph 파이프라인.

- candidate_generation : 사건유형 후보(case_list)와 무관하게 범용 프롬프트로 "누락 후보"를 자유롭게 생성.
  eligibility/analyze 결과(relief_review_checklist)를 최소 기준선(힌트)으로 삼되,
  원본 텍스트를 다시 훑어 그 외 누락도 함께 찾는다.
- validation           : 각 후보를 원본 텍스트와 재대조하여 confidence(0~1)를 매긴다
  (할루시네이션/오탐 체크). 최종 채택 여부는 config.CONFIDENCE_THRESHOLD로 코드에서 결정.
- document_mapping     : threshold를 통과한 각 누락 항목에 대해, 한국 내에서 실제로
  확인/발급 가능한 서류(ReferenceDocument)를 1~3개씩 매핑한다. 서류명·발급기관은
  실존하는 것만 쓰도록 프롬프트에서 강제 (할루시네이션 방지).
- 세 단계 모두 확정적 법률판단을 내리지 않으며, 결과는 참고자료임을 전제로 한다 (HITL 원칙).

main.py에서는 이 모듈의 `missing_data_graph`만 가져다 쓰면 된다:
    from app.agents.missing_data.graph import missing_data_graph
    result_state = await missing_data_graph.ainvoke(initial_state)
"""

from typing import List

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END

from . import config
from .modal import (
    MissingDataState,
    CandidateList,
    ValidatedList,
    MissingItemValidated,
    DocumentMappedList,
)


# ---------------------------------------------------------------------------
# 1. LLM 클라이언트 (모듈 로드 시 1회만 생성)
# ---------------------------------------------------------------------------

llm = ChatOpenAI(model=config.MODEL_NAME, temperature=0)

candidate_llm = llm.with_structured_output(CandidateList, method=config.STRUCTURED_METHOD)
validation_llm = llm.with_structured_output(ValidatedList, method=config.STRUCTURED_METHOD)
document_mapping_llm = llm.with_structured_output(DocumentMappedList, method=config.STRUCTURED_METHOD)


# ---------------------------------------------------------------------------
# 2. 프롬프트
# ---------------------------------------------------------------------------

COMMON_PRINCIPLE = """
[공통 원칙]
- 당신은 대한법률구조공단 내부 상담 지원 도구의 정보 추출 보조 역할만 수행합니다.
- 사건유형 후보(case_list)와 무관하게 동일한 기준으로 판단하세요 (유형별 특칙 적용 금지).
- "~에 해당한다", "~이다" 같은 단정적 법률판단 표현을 쓰지 말고 참고용 표현만 사용하세요.
- 이 결과는 참고자료이며, 최종 판단은 담당 변호사/공익법무관이 수행합니다 (HITL).
"""

CANDIDATE_PROMPT = COMMON_PRINCIPLE + """
[추출 목적]
아래 사건 정보를 보고, 이후 단계(서식 작성, 구조검토 4대 기준 판단)에 필요하지만
아직 확보되지 않았거나 확정되지 않은 항목의 후보를 찾으세요.

- 구조검토 4대 기준: 구조대상자 여부 / 승소가능성 / 집행가능성 / 구조타당성
- relief_review_checklist에 이미 드러난 미비 사항(evidence_status, required_evidence,
  각 항목의 review_note)은 최소 기준선으로 삼되, 원본 텍스트를 다시 훑어 그 외에
  빠진 것도 찾으세요.
- 각 후보에는 항목명(item), 종류(증빙/사실관계), 이유(reason)를 함께 답하세요.

[사건유형 후보 (참고용, case_analysis 결과 — 비율 순)]
{case_list_text}

[사건 자료 (요약 + 상세 + 추출된 첨부내용)]
{consult_text}

[구조검토 체크리스트 결과]
{relief_review_checklist}
"""

VALIDATION_PROMPT = COMMON_PRINCIPLE + """
[검증 목적]
아래는 "누락되었다"고 제시된 후보 항목 목록과, 그 사건의 원본 자료입니다.
각 후보에 대해 원본 자료를 다시 확인하여:

1. 정말로 원본 자료 어디에도 해당 정보/자료가 없는지 재검토하세요.
   (이미 원문에 있는데 후보 생성 단계에서 놓친 경우 confidence를 낮게 주세요)
2. confidence(0~1)를 매기세요.
   - 1.0에 가까움: 원본을 다시 봐도 확실히 없음 / 명백히 필요한 정보
   - 0.5 근처: 애매함 (일부 암시는 있으나 확정 자료는 없음)
   - 0에 가까움: 사실 원본에 이미 있거나, 이 사건에 꼭 필요한 항목이 아님
3. evidence_check_note에 재확인 근거를 간단히 남기세요.

[원본 사건 자료]
{consult_text}

[누락 후보 목록]
{candidates}
"""

DOCUMENT_MAPPING_PROMPT = COMMON_PRINCIPLE + """
[매핑 목적]
아래는 검증을 통과한 "누락 항목" 목록입니다. 각 항목에 대해, 대한민국에서
실제로 발급/확인 가능한 서류를 1~3개씩 찾아 reference_documents로 제시하세요.

[매핑 규칙]
- doc_name / issuing_authority는 실존하는 서류명·기관명만 사용하세요.
  존재를 확신할 수 없는 서류는 만들어내지 말고, 확실한 것만 제시하세요 (할루시네이션 금지).
- acquisition_type을 반드시 아래 세 가지 중 하나로 분류하세요.
  - "본인발급": 당사자가 정부24/홈택스 등에서 스스로 즉시 발급 가능
  - "제3자발급": 상대방·기관이 보유/신고한 내역을 당사자가 열람·요청해야 함
  - "절차확보": 진정/소송 등 공식 절차(법원 조회명령, 근로감독관 조사 등)를 거쳐야만 확보됨
- online_issuance/online_issuance_channel은 실제 온라인 발급 가능 여부에 맞게 정확히 표기하세요.
  (모르면 online_issuance=false, channel=null)
- 이 서류 목록은 상담원/변호사가 다음 행동을 정하는 데 참고하는 자료이며,
  "반드시 이 서류가 있어야 한다"는 단정적 표현은 피하세요 (참고용 안내).

[검증 통과 누락 항목 목록]
{validated_items}
"""


# ---------------------------------------------------------------------------
# 3. 헬퍼
# ---------------------------------------------------------------------------

def _consult_text(state: MissingDataState) -> str:
    """rescue_check.graph._consult_text와 동일 로직.
    모듈 간 결합을 피하기 위해 의도적으로 중복 구현함 (3줄 수준이라 재사용 이득이 적음)."""
    summary = state.get("summary", "")
    details = state.get("details", "")
    extracted = state.get("extracted_content", "")
    return f"[요약]\n{summary}\n\n[상세]\n{details}\n\n[추출된 첨부내용]\n{extracted}"


def _case_list_text(state: MissingDataState) -> str:
    """case_list(비율이 매겨진 사건유형 후보 목록)를 프롬프트용 문자열로 펼친다.

    rescue_check.graph._primary_case_type처럼 "대표 1개"를 고르는 게 아니라, 후보 전체를
    참고자료로 그대로 보여주는 용도라 로직이 달라 별도로 둔다 (모듈 간 결합 회피 이유는
    _consult_text와 동일)."""
    case_list = state.get("case_list") or []
    if not case_list:
        return "(사건유형 후보 정보 없음)"
    return ", ".join(
        f"{c.get('case_type')}({c.get('case_ratio', 0):.0%})" for c in case_list
    )


# ---------------------------------------------------------------------------
# 4. LangGraph 노드
# ---------------------------------------------------------------------------

async def candidate_generation_node(state: MissingDataState) -> dict:
    text = _consult_text(state)
    prompt = CANDIDATE_PROMPT.format(
        case_list_text=_case_list_text(state),
        consult_text=text,
        relief_review_checklist=state.get("relief_review_checklist", {}),
    )
    result: CandidateList = await candidate_llm.ainvoke(
        [SystemMessage(content=prompt), HumanMessage(content=text)]
    )
    return {"candidate_missing_items": [c.model_dump() for c in result.candidates]}


async def validation_node(state: MissingDataState) -> dict:
    text = _consult_text(state)
    prompt = VALIDATION_PROMPT.format(
        consult_text=text,
        candidates=state.get("candidate_missing_items", []),
    )
    result: ValidatedList = await validation_llm.ainvoke(
        [SystemMessage(content=prompt), HumanMessage(content=text)]
    )

    # 코드 레벨 threshold 적용 -- 실질적인 "임계치 조정" 지점 (config.CONFIDENCE_THRESHOLD)
    final_items: List[dict] = [
        v.model_dump()
        for v in result.validated
        if v.confidence >= config.CONFIDENCE_THRESHOLD
    ]
    return {"validated_missing_items": final_items}


async def document_mapping_node(state: MissingDataState) -> dict:
    validated_items = state.get("validated_missing_items", [])

    # threshold 통과 항목이 없으면 LLM 호출 없이 빈 리스트로 종료 (불필요한 API 호출 방지)
    if not validated_items:
        return {"missing_items": []}

    prompt = DOCUMENT_MAPPING_PROMPT.format(validated_items=validated_items)
    result: DocumentMappedList = await document_mapping_llm.ainvoke(
        [SystemMessage(content=prompt), HumanMessage(content=str(validated_items))]
    )

    # LLM이 순서를 바꾸거나 일부를 누락시킬 가능성에 대비해 item명 기준으로 매핑,
    # 매핑 실패 항목은 reference_documents=[] 상태로 원본 검증 결과를 그대로 보존.
    mapped_by_item = {m.item: m for m in result.items}
    final_items: List[dict] = []
    for validated in validated_items:
        mapped = mapped_by_item.get(validated.get("item"))
        if mapped is not None:
            final_items.append(mapped.model_dump())
        else:
            final_items.append({**validated, "reference_documents": []})

    return {"missing_items": final_items}


# ---------------------------------------------------------------------------
# 5. 그래프 조립 (순차 구조 — rescue_check와 동일 패턴, 안정성 우선)
# ---------------------------------------------------------------------------

_graph_builder = StateGraph(MissingDataState)

_graph_builder.add_node("candidate_generation", candidate_generation_node)
_graph_builder.add_node("validation", validation_node)
_graph_builder.add_node("document_mapping", document_mapping_node)

_graph_builder.add_edge(START, "candidate_generation")
_graph_builder.add_edge("candidate_generation", "validation")
_graph_builder.add_edge("validation", "document_mapping")
_graph_builder.add_edge("document_mapping", END)

missing_data_graph = _graph_builder.compile()
