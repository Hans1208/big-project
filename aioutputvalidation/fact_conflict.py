"""Detect explicit claim facts absent from the source transcript."""

from __future__ import annotations

import re


DATE_RE = re.compile(r"20\d{2}[-./]\d{1,2}[-./]\d{1,2}")
AMOUNT_RE = re.compile(r"\b\d[\d,]{2,}원")
FINALITY_TERMS = (
    "기각", "서면으로 인정", "확정되었다", "완료했다",
    "정정이 완료", "이전이 완료", "검인되어", "등록까지 마쳤",
    "법원이 허가", "허가가 확정", "절차가 완료", "개명을 허가",
    "등록 절차도 완료", "친권이 법원에서 확정", "면접교섭을 허가",
)
RELATIONSHIP_FACT_TERMS = ("상대방을 대리", "합의서를 작성", "대리하여", "법정대리인", "법정 보호자", "화해계약을 체결", "후견인", "친권자", "보호자", "보호책임자", "보호책임자로", "대리권", "대리 권한", "조정을 성립", "조정이 성립", "조정이 완료", "조정 절차가 마무리", "조정 조서를 확정", "조정조서", "조정 결과를 확정", "법원이 승인한 조정 결과", "조정 합의가 확정", "조정 합의를 승인", "조정 합의의 효력", "조정의 효력", "상속재산 분할 합의", "분할 합의가 확정", "분할 협의가 성립", "분할 협의가 확정", "법원이 분할 합의를 승인")
UNCERTAINTY_CUES = ("가능성", "수 있", "확인 필요", "확인이 필요", "확인해야", "불분명", "미정", "예정", "추정", "사실상", "일 수")
# Contextual allegations require human review when the source does not support them.
UNSUPPORTED_ASSERTION_TERMS = ("책임을 부인", "연락을 회피", "자료 제출을 미루", "절차를 진행 중")
LEGAL_AUTHORITY_TERMS = ("권한", "위임", "후견", "유언집행", "송달", "효력", "대리")
UNCONFIRMED_TERMS = ("확인하지 못", "알 수 없", "모릅니다", "언급된 적이 없", "보지 못")
# A term match immediately followed by one of these means the claim is denying the
# fact, not asserting it (e.g. "정정이 완료되지 않았다"). Checked against the text
# right after the match so unrelated negation elsewhere in the sentence doesn't count.
NEGATION_MARKERS = ("지 않", "지 못", "이 아니", "가 아니", "되지 않", "되지 못", "안 되", "않았", "못했", "아니었", "아니다", "아닙니다", "없습니다", "없었다", "된 바 없", "된 적 없")


def _has_unnegated_term(claim: str, term: str, window: int = 12) -> bool:
    """True only if some occurrence of term in claim is not immediately negated."""
    start = 0
    while True:
        index = claim.find(term, start)
        if index == -1:
            return False
        tail = claim[index + len(term): index + len(term) + window]
        if not any(marker in tail for marker in NEGATION_MARKERS):
            return True
        start = index + len(term)


def explicit_conflicts(claims: list[str], transcript: str) -> list[str]:
    conflicts: list[str] = []
    transcript_amounts = {value.replace(",", "") for value in AMOUNT_RE.findall(transcript)}
    # Normalize separators the same way amounts are normalized above: a claim written
    # "2025.1.3" must match a transcript written "2025-1-3" instead of being flagged
    # as an unsupported date purely because of formatting.
    transcript_dates = {re.sub(r"[-./]", "-", value) for value in DATE_RE.findall(transcript)}
    for claim in claims:
        if any(re.sub(r"[-./]", "-", date) not in transcript_dates for date in DATE_RE.findall(claim)):
            conflicts.append("unmatched_specific_date")
        if any(amount.replace(",", "") not in transcript_amounts for amount in AMOUNT_RE.findall(claim)):
            conflicts.append("unmatched_specific_amount")
        if any(_has_unnegated_term(claim, term) and term not in transcript for term in FINALITY_TERMS):
            conflicts.append("unmatched_finality_statement")
        if any(_has_unnegated_term(claim, term) and term not in transcript for term in RELATIONSHIP_FACT_TERMS) and not any(cue in claim for cue in UNCERTAINTY_CUES):
            conflicts.append("unmatched_relationship_or_representation_fact")
    return sorted(set(conflicts))


def unsupported_assertions(claims: list[str], transcript: str) -> list[str]:
    """Return non-specific allegations absent from the source for human review."""
    unsupported = {term for claim in claims for term in UNSUPPORTED_ASSERTION_TERMS if _has_unnegated_term(claim, term) and term not in transcript}
    for claim in claims:
        has_unmatched_relation_or_finality = any(_has_unnegated_term(claim, term) and term not in transcript for term in RELATIONSHIP_FACT_TERMS)
        if has_unmatched_relation_or_finality and any(cue in claim for cue in UNCERTAINTY_CUES):
            unsupported.add("unmatched_uncertain_relation_or_finality_claim")
    return sorted(unsupported)


def legal_authority_ambiguities(claims: list[str], transcript: str) -> list[str]:
    """Escalate supported but legally sensitive authority/document unknowns."""
    if not any(term in transcript for term in UNCONFIRMED_TERMS):
        return []
    return [claim for claim in claims if any(term in claim for term in LEGAL_AUTHORITY_TERMS)]
