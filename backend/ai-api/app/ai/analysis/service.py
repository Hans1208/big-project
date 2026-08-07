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
    """주민등록번호·전화번호를 둘 다 지운다. 판정 계층(consult)이 쓴다.

    구조대상 판단과 누락자료 목록에는 어느 쪽 번호도 실릴 이유가 없다.

    구분자가 있는 형태만 지운다. 구분자 없는 긴 숫자를 지우면 금액과 사건번호가
    함께 사라진다."""
    if not text:
        return text
    return _PHONE_RE.sub("[전화번호]", scrub_resident_number(text))


def scrub_resident_number(text: str) -> str:
    """주민등록번호만 지운다. 구조화 분석 입력이 쓴다.

    전화번호는 남긴다 — 서식의 당사자 연락처칸에 들어가야 하는 값이라, 지우면
    분석이 뽑을 수가 없고 상담원이 초안을 받아 손으로 채워야 한다.

    주민등록번호는 계속 지운다. 이유가 전화번호와 다르다:
      · 개인정보 보호법 제24조의2 — 동의가 아니라 법령 근거가 있어야 처리할 수 있어
        애초에 보관하지 않기로 한 값이다. 서식에서도 [직접 기재]로 남긴다.
      · 지어낼 위험이 훨씬 크다. 실측에서 STT가 뭉갠 소리("팔치유공산 2.1을 2글팔
        4.2.2")를 모델이 형식만 완벽한 가짜 주민번호로 채웠고, 그게 요약에 실려
        DB까지 갔다. 형식이 그럴듯해서 사람 눈으로는 걸러지지 않는다.

    전화번호도 같은 위험이 있지만 두 가지가 다르다 — 상담원이 화면에서 눈으로
    확인·수정하는 단계를 거치고, 분석 프롬프트에도 "자릿수가 안 맞으면 null"이라고
    적어 두었다."""
    if not text:
        return text
    return _RRN_RE.sub("[주민등록번호]", text)


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
        output: Optional[dict] = None,
    ):
        self.summary = summary
        self.case_type = case_type
        self.case_subtype = case_subtype
        self.extracted = extracted
        self.timeline = timeline
        self.output = output

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
    # 주민등록번호만 지운다. 전화번호는 서식의 연락처칸에 들어가야 해서 남긴다
    # (scrub_resident_number 주석 참고).
    return scrub_resident_number(
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
    extracted = data.get("extracted_json")
    return ConsultAnalysis(
        summary=strip_contact_from_summary(data.get("summary"), extracted) or None,
        case_type=data.get("case_type"),
        case_subtype=data.get("case_subtype"),
        extracted=extracted,
        timeline=data.get("timeline_json"),
        output=data,
    )


# 서식 작성용으로 뽑는 키들.
#
# 계약(contracts/README_ai_analysis_contract.md 4절)은 extracted_json을 '유연
# key-value'로 두고 당사자·금액·날짜·사건개요를 '권장' 키로만 적어 두었는데,
# 출력 검증 스키마(aioutputvalidation/schema/ai_analysis.schema.json)는 그 넷을
# required + additionalProperties:false로 못박아 두었다. 그래서 아래 셋을 그대로
# 넘기면 "Additional properties are not allowed"로 모든 분석이 형식 오류가 된다
# (실측 1건). 스키마를 계약대로 완화하는 게 맞지만 그건 검증 모델 쪽 결정이라,
# 그때까지 검증기에 넘기는 사본에서만 뺀다.
#
# 저장·화면에 쓰는 원본은 건드리지 않는다 — 동의 화면이 이 값으로 주소·전화칸을
# 미리 채운다(DraftContactConsent).
DRAFT_CONTACT_KEYS = ("주소", "전화번호", "개인정보동의")


def without_draft_contact(output: dict) -> dict:
    """출력 검증에 넘길 사본에서 서식용 연락처 키를 뺀다. 원본은 그대로 둔다."""
    if not isinstance(output, dict):
        return output
    extracted = output.get("extracted_json")
    if not isinstance(extracted, dict):
        return output
    if not any(k in extracted for k in DRAFT_CONTACT_KEYS):
        return output
    return {
        **output,
        "extracted_json": {k: v for k, v in extracted.items()
                           if k not in DRAFT_CONTACT_KEYS},
    }


# "주소(서울시 …)"처럼 괄호로 덧붙인 모양. 값을 지우면 빈 괄호가 남으므로 괄호째 지운다.
_CONTACT_PAREN_RE = "[(（][^)）]*{}[^)）]*[)）]"


def strip_contact_from_summary(summary: str, extracted: dict | None) -> str:
    """요약에서 주소·전화번호를 지운다.

    이 값들은 extracted_json의 전용 칸에 이미 들어가 있다. 요약에까지 실리면 같은
    개인정보가 두 군데에 쌓이고, 그 요약은 변호사 검토 화면에 그대로 뜬다. 연락처는
    사실관계도 쟁점도 아니라 검토에 쓸모도 없다.

    프롬프트에도 "요약에 쓰지 말라"고 적어 두었지만 지켜지지 않는다(실측: 두 번 연속
    "청구인은 본인의 주소(서울특별시 …)와 연락처(010-…)를 제공하였습니다"가 나왔다).
    이 파일이 여러 번 택한 방식대로, 프롬프트로 못 막는 것은 코드로 막는다.

    지우는 것은 값 자체다. "주소를 제공하였습니다" 같은 서술은 남긴다 — 상담원이
    연락처를 받았다는 사실은 검토에 의미가 있고, 값이 없으면 개인정보도 아니다."""
    text = (summary or "").strip()
    if not text or not isinstance(extracted, dict):
        return text

    for key in ("주소", "전화번호"):
        value = str(extracted.get(key) or "").strip()
        if len(value) < 4 or value not in text:
            continue
        # 괄호로 덧붙인 모양을 먼저 지운다. 값만 지우면 "주소()와"가 남는다.
        text = re.sub(_CONTACT_PAREN_RE.format(re.escape(value)), "", text)
        text = text.replace(value, "")

    # 값을 들어낸 자리에 남는 군더더기를 정리한다.
    text = re.sub(r"\s*[(（][\s,·]*[)）]", "", text)   # 빈 괄호
    text = re.sub(r"\s{2,}", " ", text)
    return re.sub(r"\s+([,.·])", r"\1", text).strip()
