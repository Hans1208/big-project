"""텍스트 -> AI_ANALYSIS 구조화 (파이프라인 2단계).

이 층이 파이프라인의 허브다. 뒤의 consult(판정) / forms(서식) / RAG는
서로를 모른 채 각자 이 결과만 읽는다.

입력은 텍스트뿐이다 — S3도 파일도 모른다(그건 ai/stt/의 일).
그래서 실시간 STT로 바뀌어도 이 층은 손댈 필요가 없고,
테스트할 때도 AWS 자격증명 없이 문자열만 넣으면 된다.
"""

import re
from typing import Optional

from app.ai.analysis.llm_client import analyze_consultation

# 주민등록번호·전화번호는 분석 입력에서 지운다.
#
# 분석은 마스킹본이 아니라 원문을 받는다(core-api buildCombinedInputText). 그래서
# 상담에서 불러준 주민등록번호가 그대로 외부 LLM으로 나가고, 요약에도 실려 DB에
# 저장된다 - 실측에서 요약이 "남편 백승현(870521-1284222)이"로 나왔다.
#
# 더 나쁜 것은 그 번호가 지어낸 값이었다는 점이다. STT가 뭉갠 소리
# ("팔치유공산 2.1을 2글팔 4.2.2")에서 모델이 형식만 완벽한 가짜 주민번호를
# 만들어냈다. 실제로 말한 번호와도 다르다. 법률 서류에 없는 주민번호가 올라가는
# 것은 빈칸보다 위험하고, 형식이 그럴듯해서 사람 눈으로는 걸러지지 않는다.
#
# 마스킹본을 통째로 쓰지 않는 이유: 이름까지 [PRIVATE_PERSON]이 되면 분석이
# 당사자를 못 뽑고, 그러면 서식 초안의 이름칸이 전부 빈다. 서식은 주민번호를
# AI가 채우지 않도록 이미 막혀 있으므로(FIELD_PROMPT 2번), 번호만 지우면
# 잃는 기능이 없다.
#
# 금액은 지우지 않는다. "2억", "200000000"까지 지우면 재산분할·양육비 분석이
# 통째로 무력해진다 - 자릿수만 보고 지우면 안 되는 이유다.
_RRN_RE = re.compile(r"\d{6}\s*[-~]\s*\d{7}")
_PHONE_RE = re.compile(r"0\d{1,2}\s*[-)]\s*\d{3,4}\s*[-]\s*\d{4}")


def scrub_sensitive_numbers(text: str) -> str:
    """분석 입력에서 주민등록번호·전화번호를 지운다.

    구분자가 있는 형태만 지운다. 구분자 없는 긴 숫자를 지우면 금액과 사건번호가
    함께 사라진다."""
    if not text:
        return text
    text = _RRN_RE.sub("[주민등록번호]", text)
    return _PHONE_RE.sub("[전화번호]", text)


class ConsultAnalysis:
    """AI_ANALYSIS 계약 형태의 구조화 결과.

    case_type은 이 층 것을 쓴다. 대상 사건 범위가 "서식이 실제로 있는 대분류"로
    확정됐고, 그 목록이 이 모델의 분류체계와 같기 때문이다.

        app/schemas/analysis.py  CaseType     = 친족/상속/가사소송/가족관계등록
        app/ai/forms/recommender MVP_CATEGORIES = 친족/상속/가사소송/가족관계등록

    consult 층 classify_case_type의 8개 유형(임금체불·개인회생 등)은 서식이 없어
    초안 생성까지 이어지지 못한다. 또 대분류와 소분류를 서로 다른 모델이 만들면
    둘이 어긋날 수 있는데(예: 대분류 임금체불 + 소분류 상속재산분할), 한 모델이
    같이 만들면 그 문제가 없다.

    consult 층 노드는 그대로 둔다 — case_list(프론트 표시)와 소멸시효 계산이
    아직 그 8개 유형 이름에 묶여 있다.
    """

    def __init__(
        self,
        summary: Optional[str] = None,
        case_type: Optional[str] = None,
        case_subtype: Optional[str] = None,
        extracted: Optional[dict] = None,
        timeline: Optional[list] = None,
    ):
        self.summary = summary
        self.case_type = case_type
        self.case_subtype = case_subtype
        self.extracted = extracted
        self.timeline = timeline

    def to_dict(self) -> dict:
        return {
            "consult_summary": self.summary,
            "consult_case_type": self.case_type,
            "consult_case_subtype": self.case_subtype,
            "consult_extracted": self.extracted,
            "consult_timeline": self.timeline,
        }


def build_consult_text(summary: str, details: str, extracted_text: str) -> str:
    """구조화 분석에 넣을 입력 텍스트 조합.

    상담원이 입력한 요약·상세에 첨부파일에서 뽑은 텍스트를 이어 붙인다.
    녹취록을 올린 경우 그 내용까지 요약·추출 대상이 되어야 하므로
    stt 단계 결과(extracted_text)가 반드시 포함되어야 한다.
    """
    return scrub_sensitive_numbers(
        f"[요약]\n{summary or ''}\n\n"
        f"[상세]\n{details or ''}\n\n"
        f"[추출된 첨부내용]\n{extracted_text or ''}"
    )


def analyze(consult_text: str) -> ConsultAnalysis:
    """상담 텍스트를 AI_ANALYSIS 형태로 구조화한다.

    실패해도 예외를 올리지 않고 빈 결과를 돌려준다.
    이 단계가 실패했다고 뒤의 판정까지 막히면 안 되기 때문 —
    실제로 모델 과부하(503)나 스키마 검증 실패가 종종 발생한다.
    """
    if not consult_text or not consult_text.strip():
        return ConsultAnalysis()

    try:
        result = analyze_consultation(consult_text)
    except Exception as e:  # noqa: BLE001 - 이 단계 실패가 전체 파이프라인을 막지 않게 한다
        print(f"[ai.analysis] 구조화 분석 실패, 이 단계 없이 진행: {e}")
        return ConsultAnalysis()

    # 하위 필드가 Pydantic 모델이라 그대로 응답에 실으면 직렬화에서 막힌다.
    # model_dump()로 중첩까지 한 번에 dict/list로 바꾼다.
    data = result.model_dump()
    return ConsultAnalysis(
        summary=(data.get("summary") or "").strip() or None,
        case_type=data.get("case_type"),
        case_subtype=data.get("case_subtype"),
        extracted=data.get("extracted_json"),
        timeline=data.get("timeline_json"),
    )
