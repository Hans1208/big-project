"""Collect family-law precedent summaries."""

from __future__ import annotations

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
    "상속",
    "상속재산분할",
    "유류분",
    "상속포기",
    "한정승인",
    "상속회복",
    "기여분",
    "특별수익",
    "친생자",
    "인지청구",
    "친생부인",
    "가족관계등록",
    "부양료",
    "성년후견",
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
)


@dataclass(frozen=True)
class PrecedentSearchJob:
    query: str
    search_scope: int
    court_type_code: str
    referenced_law: str
    label: str


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

            add_job(
                query=clean_keyword,
                search_scope=2,
                court_type_code=court_code,
                referenced_law="",
                label=(
                    f"keyword:body:{clean_keyword}:"
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

    for record in records.values():
        record["matched_searches"].sort()

    return sorted(
        records.values(),
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