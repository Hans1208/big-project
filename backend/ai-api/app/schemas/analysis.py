from typing import List, Literal, Optional
from pydantic import BaseModel, Field, model_validator

CaseType = Literal["친족", "상속", "가사소송", "가족관계등록"]

CaseSubtype = Literal[
    "약혼", "혼인의 성립, 무효, 취소", "협의이혼", "재판상이혼 등",
    "이혼 및 위자료", "이혼 및 재산분할청구권", "양육비", "면접교섭권",
    "입양, 파양, 친양자", "친권", "후견인", "부양",
    "상속일반", "상속분", "상속재산분할", "유언", "유류분",
    "가사소송일반", "가,나,다류 가사소송", "라,마류 가사비송",
    "양육비직접지급명령", "이행명령", "과태료와 감치", "기타",
    "신고", "국적의 취득과 상실", "성본창설과 개명",
    "가족관계등록창설", "가족관계등록부정정",
]

CASE_TYPE_SUBTYPE_MAP = {
    "친족": [
        "약혼", "혼인의 성립, 무효, 취소", "협의이혼", "재판상이혼 등",
        "이혼 및 위자료", "이혼 및 재산분할청구권", "양육비", "면접교섭권",
        "입양, 파양, 친양자", "친권", "후견인", "부양",
    ],
    "상속": ["상속일반", "상속분", "상속재산분할", "유언", "유류분"],
    "가사소송": [
        "가사소송일반", "가,나,다류 가사소송", "라,마류 가사비송",
        "양육비직접지급명령", "이행명령", "과태료와 감치", "기타",
    ],
    "가족관계등록": [
        "신고", "국적의 취득과 상실", "성본창설과 개명",
        "가족관계등록창설", "가족관계등록부정정",
    ],
}


class Party(BaseModel):
    역할: str = Field(description="당사자의 역할 (예: 청구인, 상대방, 신청인, 피상속인 등)")
    이름: str = Field(description="당사자 성명. 상담에서 확인 불가능하면 '미상'")
    model_config = {"extra": "forbid"}


class DateEntry(BaseModel):
    항목: str = Field(description="날짜의 의미 (예: '혼인', '별거_시작', '사망')")
    값: str = Field(description="날짜 또는 시점 (예: '2020-03', '약 3년 전')")
    model_config = {"extra": "forbid"}


class ExtractedInfo(BaseModel):
    당사자: List[Party]
    금액: Optional[int] = Field(description="재산분할·양육비·위자료 등 금액(원). 없으면 null")
    날짜: List[DateEntry] = Field(description="주요 날짜 목록. 없으면 빈 배열")
    사건개요: str = Field(description="상담 내용 기반 1~2문장 핵심 사건 요약")
    # 아래 셋은 서식 초안에 그대로 들어가는 값이다. 법원 서식의 당사자 주소는 송달을
    # 위한 법정 필수 기재사항이라, 비어 있으면 상담원이 초안을 받아 손으로 채워야 한다.
    #
    # extra="forbid"라서 프롬프트에만 적으면 모델이 만들어도 버려진다 — 여기에 필드를
    # 두어야 실제로 넘어온다.
    #
    # 주민등록번호는 여기에 두지 않는다. 개인정보 보호법 제24조의2가 동의가 아니라
    # 법령 근거를 요구해서, 상담에서 말했더라도 이 시스템은 보관하지 않는다.
    # default를 주면 안 된다. 기본값이 있으면 JSON 스키마에서 required가 빠지고,
    # Gemini는 필수가 아닌 필드를 아예 안 내보낸다 — 실측에서 이 셋만 응답에서
    # 통째로 사라졌다(당사자·금액·날짜·사건개요는 그대로 왔다).
    # 위 '금액'이 같은 방식이다. default 없는 Optional이라 필수이면서 null을 허용해서,
    # 모르는 사건에서는 "금액": null로 온다.
    주소: Optional[str] = Field(
        description="상담자 본인의 주소. 상대방·사망자의 주소나 등록기준지는 제외. "
                    "들은 만큼만 적고 없으면 null",
    )
    전화번호: Optional[str] = Field(
        description="상담자 본인의 연락처. 자릿수가 안 맞거나 중간이 끊겼으면 null "
                    "— 틀린 번호는 송달 실패로 이어지므로 비워 두는 편이 낫다",
    )
    개인정보동의: Optional[bool] = Field(
        description="상담원이 주소·전화번호 수집을 안내하고 상담자가 동의했으면 true. "
                    "안내가 없었거나 거절했으면 false, 애매하면 false",
    )
    model_config = {"extra": "forbid"}


class ChecklistItem(BaseModel):
    항목: str
    결과: Literal["충족", "미충족", "확인필요"]
    model_config = {"extra": "forbid"}


class TimelineItem(BaseModel):
    날짜: str
    내용: str
    model_config = {"extra": "forbid"}


class AIAnalysisSchema(BaseModel):
    # 분량을 못 박지 않는다. 이 요약은 변호사 검토와 법률구조 대상 판단에 함께 쓰이는데,
    # 문장 수를 정해두면 소득·신분·증빙 같은 판단 재료가 먼저 잘려나간다.
    # 무엇을 담아야 하는지는 prompts.py의 summary 규칙에 적어둔다.
    summary: str = Field(
        description="상담 내용 요약. 사실관계·쟁점·내담자 요구, 그리고 소득·재산·신분·증빙 등 "
                    "법률구조 대상 판단에 필요한 언급을 빠뜨리지 말 것"
    )
    case_type: CaseType
    case_subtype: CaseSubtype
    urgency_level: Literal["상", "중", "하"]
    eligibility: Literal["대상후보", "비대상후보", "확인필요"]
    extracted_json: ExtractedInfo
    missing_info_json: List[str] = Field(description="누락 자료 목록. 없으면 빈 배열")
    checklist_json: List[ChecklistItem]
    timeline_json: List[TimelineItem] = Field(description="사실관계 타임라인. 없으면 빈 배열")

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def validate_subtype_matches_type(self):
        allowed = CASE_TYPE_SUBTYPE_MAP.get(self.case_type, [])
        if self.case_subtype not in allowed:
            raise ValueError(
                f"case_subtype '{self.case_subtype}'은(는) case_type '{self.case_type}'에 속하지 않습니다."
            )
        return self