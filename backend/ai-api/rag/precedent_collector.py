"""Collect relevant family-law precedent summaries."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable

from rag.precedent_api import PrecedentApiClient


SUPREME_COURT_CODE = "400201"
LOWER_COURT_CODE = "400202"

COURT_LEVELS = {
    SUPREME_COURT_CODE: "supreme",
    LOWER_COURT_CODE: "lower",
}

DOMAIN_KEYWORDS = (
    "이혼",
    "재판상이혼",
    "협의이혼",
    "재산분할",
    "위자료",
    "양육비",
    "양육권",
    "친권",
    "면접교섭",
    "혼인무효",
    "혼인취소",
    "사실혼",
    "가족관계등록",
    "가족관계등록부",
    "가족관계등록부정정",
    "등록부정정",
    "출생신고",
    "혼인신고",
    "이혼신고",
    "사망신고",
    "인지신고",
    "성본변경",
    "성과본변경",
    "상속",
    "상속재산분할",
    "유류분",
    "상속포기",
    "한정승인",
    "상속회복",
    "기여분",
    "특별수익",
    "상속승인",
    "상속결격",
    "상속재산관리인",
    "특별연고자",
    "유언",
    "유언효력",
    "유언집행",
    "유증",
    "친생자",
    "인지청구",
    "친생부인",
    "부양료",
    "성년후견",
    "입양",
    "파양",
    "친생관계존부확인",
    "친생자관계존부확인",
    "친생자관계부존재확인",
    "친권자지정",
    "친권상실",
    "미성년후견",
    "후견개시",
    "부양청구",
    "실종선고",
    "부재자재산관리",
)

BODY_SEARCH_KEYWORDS = (
    "이혼",
    "재산분할",
    "양육비",
    "친권",
    "면접교섭",
    "상속",
    "유류분",
    "후견",
    "가족관계등록부정정",
    "출생신고",
    "입양",
    "파양",
    "친생자관계",
    "인지청구",
    "성년후견",
    "미성년후견",
    "유언",
    "상속포기",
    "한정승인",
)

SPECIALIZED_REFERENCE_LAWS = (
    "가사소송법",
    "가족관계의 등록 등에 관한 법률",
)

GENERAL_REFERENCE_LAWS = (
    "민법",
    "민사소송법",
    "민사집행법",
)

REFERENCE_ANCHORS = (
    "이혼",
    "재산분할",
    "양육비",
    "친권",
    "상속",
    "유류분",
    "후견",
    "가족관계등록부정정",
    "입양",
    "친생자관계",
    "인지청구",
    "유언",
)

EXCLUDED_CASE_NAME_TERMS = (
    "법인세",
    "상속세",
    "증여세",
    "부가가치세",
    "소득세",
    "양도소득세",
    "종합소득세",
    "관세",
    "조세",
    "세금",
    "과세",
    "부과처분",
    "과징금",
    "특허",
    "산업재해",
    "산재",
    "마약",
    "뇌물",
)


@dataclass(frozen=True)
class PrecedentSearchJob:
    query: str
    search_scope: int
    court_type_code: str
    referenced_law: str
    label: str


def _normalize_text(
    value: object,
) -> str:
    return re.sub(
        r"[^0-9a-z가-힣]+",
        "",
        str(value).casefold(),
    )


def is_relevant_precedent_summary(
    item: dict[str, Any],
) -> bool:
    """Decide relevance before fetching the full precedent."""
    case_name = _normalize_text(
        item.get("case_name", "")
    )
    case_type_name = _normalize_text(
        item.get("case_type_name", "")
    )

    if any(
        _normalize_text(term) in case_name
        for term in EXCLUDED_CASE_NAME_TERMS
    ):
        return False

    if "가사" in case_type_name:
        return True

    return any(
        _normalize_text(keyword) in case_name
        for keyword in DOMAIN_KEYWORDS
    )


def build_default_search_jobs(
    keywords: Iterable[str] = DOMAIN_KEYWORDS,
) -> list[PrecedentSearchJob]:
    jobs: list[PrecedentSearchJob] = []
    signatures: set[
        tuple[str, int, str, str]
    ] = set()

    def add_job(
        *,
        query: str,
        search_scope: int,
        court_type_code: str,
        referenced_law: str,
        label: str,
    ) -> None:
        signature = (
            query,
            search_scope,
            court_type_code,
            referenced_law,
        )

        if signature in signatures:
            return

        signatures.add(signature)

        jobs.append(
            PrecedentSearchJob(
                query=query,
                search_scope=search_scope,
                court_type_code=court_type_code,
                referenced_law=referenced_law,
                label=label,
            )
        )

    for keyword in keywords:
        clean_keyword = keyword.strip()

        if not clean_keyword:
            continue

        for court_code, court_level in (
            COURT_LEVELS.items()
        ):
            add_job(
                query=clean_keyword,
                search_scope=1,
                court_type_code=court_code,
                referenced_law="",
                label=(
                    f"keyword:title:{clean_keyword}:"
                    f"{court_level}"
                ),
            )

    for keyword in BODY_SEARCH_KEYWORDS:
        for court_code, court_level in (
            COURT_LEVELS.items()
        ):
            add_job(
                query=keyword,
                search_scope=2,
                court_type_code=court_code,
                referenced_law="",
                label=(
                    f"keyword:body:{keyword}:"
                    f"{court_level}"
                ),
            )

    for law_name in SPECIALIZED_REFERENCE_LAWS:
        for court_code, court_level in (
            COURT_LEVELS.items()
        ):
            add_job(
                query="",
                search_scope=1,
                court_type_code=court_code,
                referenced_law=law_name,
                label=(
                    f"law:{law_name}:all:"
                    f"{court_level}"
                ),
            )

    for law_name in GENERAL_REFERENCE_LAWS:
        for anchor in REFERENCE_ANCHORS:
            for court_code, court_level in (
                COURT_LEVELS.items()
            ):
                add_job(
                    query=anchor,
                    search_scope=2,
                    court_type_code=court_code,
                    referenced_law=law_name,
                    label=(
                        f"law:{law_name}:{anchor}:"
                        f"{court_level}"
                    ),
                )

    return jobs


def collect_precedent_summaries(
    *,
    client: PrecedentApiClient,
    jobs: Iterable[PrecedentSearchJob],
    decision_date_from: str,
    decision_date_to: str,
    display: int = 100,
    max_pages_per_job: int | None = None,
) -> list[dict[str, Any]]:
    if not 1 <= display <= 100:
        raise ValueError(
            "display must be between 1 and 100."
        )

    if (
        max_pages_per_job is not None
        and max_pages_per_job < 1
    ):
        raise ValueError(
            "max_pages_per_job must be positive."
        )

    records: dict[str, dict[str, Any]] = {}

    for job in jobs:
        page_number = 1
        fetched_for_job = 0
        pages_fetched = 0

        while True:
            result = client.search_precedents(
                query=job.query,
                search_scope=job.search_scope,
                display=display,
                page=page_number,
                court_type_code=(
                    job.court_type_code
                ),
                referenced_law=(
                    job.referenced_law
                ),
                decision_date_from=(
                    decision_date_from
                ),
                decision_date_to=(
                    decision_date_to
                ),
            )

            pages_fetched += 1
            fetched_for_job += len(result.items)

            for item in result.items:
                precedent_id = str(
                    item.get(
                        "precedent_id",
                        "",
                    )
                ).strip()

                if not precedent_id:
                    continue

                if precedent_id not in records:
                    record = dict(item)
                    record["matched_searches"] = []
                    records[precedent_id] = record

                matched_searches = records[
                    precedent_id
                ]["matched_searches"]

                if job.label not in matched_searches:
                    matched_searches.append(
                        job.label
                    )

            if (
                max_pages_per_job is not None
                and pages_fetched
                >= max_pages_per_job
            ):
                break

            if not result.items:
                break

            if (
                result.total_count > 0
                and fetched_for_job
                >= result.total_count
            ):
                break

            if len(result.items) < display:
                break

            page_number += 1

    relevant_records: list[dict[str, Any]] = []

    for record in records.values():
        record["matched_searches"].sort()

        if is_relevant_precedent_summary(
            record
        ):
            relevant_records.append(record)

    return sorted(
        relevant_records,
        key=lambda item: (
            str(
                item.get(
                    "decision_date",
                    "",
                )
            ),
            str(
                item.get(
                    "precedent_id",
                    "",
                )
            ),
        ),
        reverse=True,
    )