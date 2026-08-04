from rag.precedent_api import PrecedentSearchPage
from rag.precedent_collector import (
    PrecedentSearchJob,
    build_default_search_jobs,
    collect_precedent_summaries,
)


def _item(
    precedent_id,
    case_name,
    decision_date,
):
    return {
        "precedent_id": precedent_id,
        "case_name": case_name,
        "case_number": f"case-{precedent_id}",
        "decision_date": decision_date,
        "court_name": "테스트법원",
        "court_type_code": "400202",
        "case_type_name": "가사",
        "case_type_code": "400106",
        "decision_type": "판결",
        "decision": "선고",
        "data_source_name": "대법원",
        "detail_link": (
            "/DRF/lawService.do"
            f"?target=prec&ID={precedent_id}"
        ),
    }


def test_default_jobs_include_keyword_and_law_searches():
    jobs = build_default_search_jobs()

    signatures = {
        (
            job.query,
            job.search_scope,
            job.court_type_code,
            job.referenced_law,
        )
        for job in jobs
    }

    assert (
        "재산분할",
        1,
        "400201",
        "",
    ) in signatures

    assert (
        "재산분할",
        2,
        "400202",
        "",
    ) in signatures

    assert (
        "",
        1,
        "400201",
        "가사소송법",
    ) in signatures

    assert (
        "이혼",
        2,
        "400202",
        "민법",
    ) in signatures

    assert len(signatures) == len(jobs)


def test_collector_paginates_and_deduplicates_by_id():
    calls = []

    class FakeClient:
        def search_precedents(self, **kwargs):
            calls.append(kwargs)

            query = kwargs["query"]
            page = kwargs["page"]

            if query == "재산분할" and page == 1:
                return PrecedentSearchPage(
                    total_count=3,
                    page=1,
                    items=[
                        _item(
                            "100",
                            "재산분할",
                            "20230101",
                        ),
                        _item(
                            "200",
                            "이혼 및 재산분할",
                            "20240101",
                        ),
                    ],
                )

            if query == "재산분할" and page == 2:
                return PrecedentSearchPage(
                    total_count=3,
                    page=2,
                    items=[
                        _item(
                            "300",
                            "재산분할 청구",
                            "20220101",
                        ),
                    ],
                )

            if query == "양육비" and page == 1:
                return PrecedentSearchPage(
                    total_count=1,
                    page=1,
                    items=[
                        _item(
                            "200",
                            "이혼 및 재산분할",
                            "20240101",
                        ),
                    ],
                )

            return PrecedentSearchPage(
                total_count=0,
                page=page,
                items=[],
            )

    jobs = [
        PrecedentSearchJob(
            query="재산분할",
            search_scope=1,
            court_type_code="400202",
            referenced_law="",
            label="keyword:title:재산분할:lower",
        ),
        PrecedentSearchJob(
            query="양육비",
            search_scope=2,
            court_type_code="400202",
            referenced_law="민법",
            label="law:민법:양육비:lower",
        ),
    ]

    results = collect_precedent_summaries(
        client=FakeClient(),
        jobs=jobs,
        decision_date_from="20160101",
        decision_date_to="20260804",
        display=2,
    )

    assert [
        result["precedent_id"]
        for result in results
    ] == [
        "200",
        "100",
        "300",
    ]

    duplicated = results[0]

    assert duplicated["matched_searches"] == [
        "keyword:title:재산분할:lower",
        "law:민법:양육비:lower",
    ]

    assert [
        call["page"]
        for call in calls
        if call["query"] == "재산분할"
    ] == [1, 2]

    assert all(
        call["decision_date_from"] == "20160101"
        and call["decision_date_to"] == "20260804"
        and call["display"] == 2
        for call in calls
    )


def test_collector_respects_page_limit():
    calls = []

    class FakeClient:
        def search_precedents(self, **kwargs):
            calls.append(kwargs)

            return PrecedentSearchPage(
                total_count=100,
                page=kwargs["page"],
                items=[
                    _item(
                        str(kwargs["page"]),
                        "이혼",
                        "20240101",
                    )
                ],
            )

    jobs = [
        PrecedentSearchJob(
            query="이혼",
            search_scope=1,
            court_type_code="400201",
            referenced_law="",
            label="smoke",
        )
    ]

    results = collect_precedent_summaries(
        client=FakeClient(),
        jobs=jobs,
        decision_date_from="20160101",
        decision_date_to="20260804",
        display=1,
        max_pages_per_job=2,
    )

    assert len(results) == 2
    assert len(calls) == 2


def test_default_jobs_limit_body_searches():
    jobs = build_default_search_jobs()

    signatures = {
        (
            job.query,
            job.search_scope,
            job.court_type_code,
            job.referenced_law,
        )
        for job in jobs
    }

    assert (
        "\uc7ac\uc0b0\ubd84\ud560",
        2,
        "400202",
        "",
    ) in signatures

    assert (
        "\ud611\uc758\uc774\ud63c",
        2,
        "400202",
        "",
    ) not in signatures

    assert len(jobs) == 108


def test_collector_filters_unrelated_tax_cases():
    tax_case = _item(
        "901",
        (
            "\ubc95\uc778\uc138\ubd80\uacfc\ucc98\ubd84"
            "\ub4f1\ucde8\uc18c\uccad\uad6c"
        ),
        "20250101",
    )
    tax_case["case_type_name"] = (
        "\ud589\uc815"
    )

    inheritance_case = _item(
        "900",
        "\uc0c1\uc18d\uc7ac\uc0b0\ubd84\ud560",
        "20240101",
    )
    inheritance_case["case_type_name"] = (
        "\ubbfc\uc0ac"
    )

    class FakeClient:
        def search_precedents(self, **kwargs):
            return PrecedentSearchPage(
                total_count=2,
                page=1,
                items=[
                    tax_case,
                    inheritance_case,
                ],
            )

    results = collect_precedent_summaries(
        client=FakeClient(),
        jobs=[
            PrecedentSearchJob(
                query="\uc0c1\uc18d",
                search_scope=2,
                court_type_code="400202",
                referenced_law="\ubbfc\ubc95",
                label=(
                    "law:"
                    "\ubbfc\ubc95:"
                    "\uc0c1\uc18d:"
                    "lower"
                ),
            )
        ],
        decision_date_from="20160101",
        decision_date_to="20260804",
        display=100,
    )

    assert [
        result["precedent_id"]
        for result in results
    ] == [
        "900",
    ]


def test_collector_keeps_generic_family_case():
    family_case = _item(
        "902",
        "\uc0ac\uac74\uba85\ube44\uacf5\uac1c",
        "20240201",
    )
    family_case["case_type_name"] = (
        "\uac00\uc0ac"
    )

    class FakeClient:
        def search_precedents(self, **kwargs):
            return PrecedentSearchPage(
                total_count=1,
                page=1,
                items=[family_case],
            )

    results = collect_precedent_summaries(
        client=FakeClient(),
        jobs=[
            PrecedentSearchJob(
                query="\uc7ac\uc0b0\ubd84\ud560",
                search_scope=2,
                court_type_code="400202",
                referenced_law="",
                label=(
                    "keyword:body:"
                    "\uc7ac\uc0b0\ubd84\ud560:"
                    "lower"
                ),
            )
        ],
        decision_date_from="20160101",
        decision_date_to="20260804",
        display=100,
    )

    assert [
        result["precedent_id"]
        for result in results
    ] == [
        "902",
    ]
