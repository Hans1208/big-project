from app.ai.forms.rag_candidates import (
    convert_rag_result_to_candidate,
    search_rag_candidates,
)


def test_convert_rag_result_to_candidate():
    rag_result = {
        "document_id": "I001002016",
        "chunk_id": "I001002016::chunk-0003",
        "title": (
            "이혼, 위자료, 재산분할, "
            "친권행사자지정, 양육비청구의 소"
        ),
        "case_type": "가사소송",
        "case_subtype": "가,나,다류 가사소송",
        "similarity": 0.8865,
        "content": "서식 본문",
        "source": "forms/test.hwpx",
    }

    candidate = convert_rag_result_to_candidate(
        rag_result
    )

    assert candidate == {
        "tmpltNo": "I001002016",
        "name": (
            "이혼, 위자료, 재산분할, "
            "친권행사자지정, 양육비청구의 소"
        ),
        "main": "가사소송",
        "sub": "가,나,다류 가사소송",
        "similarity": 0.8865,
        "chunk_id": "I001002016::chunk-0003",
        "source": "forms/test.hwpx",
    }


def test_convert_rag_results_removes_invalid_rows():
    from app.ai.forms.rag_candidates import (
        convert_rag_results_to_candidates,
    )

    results = [
        {
            "document_id": "FORM-001",
            "title": "유효한 서식",
            "case_type": "친족",
            "case_subtype": "양육비",
            "similarity": 0.9,
            "chunk_id": "FORM-001::chunk-0000",
            "source": "forms/one.hwpx",
        },
        {
            "document_id": "",
            "title": "ID 없는 서식",
        },
        {
            "document_id": "FORM-003",
            "title": "",
        },
    ]

    candidates = convert_rag_results_to_candidates(
        results
    )

    assert len(candidates) == 1
    assert candidates[0]["tmpltNo"] == "FORM-001"
    assert candidates[0]["name"] == "유효한 서식"


def test_search_rag_candidates_uses_local_retriever():
    from app.ai.forms.rag_candidates import (
        search_rag_candidates,
    )

    calls = {}

    def fake_retrieve(**kwargs):
        calls.update(kwargs)

        return [
            {
                "document_id": "FORM-001",
                "chunk_id": "FORM-001::chunk-0002",
                "title": "이혼 및 재산분할청구의 소",
                "case_type": "가사소송",
                "case_subtype": "가,나,다류 가사소송",
                "similarity": 0.91,
                "source": "forms/FORM-001.hwpx",
            },
            {
                "document_id": "FORM-002",
                "chunk_id": "FORM-002::chunk-0001",
                "title": "재산분할 심판청구서",
                "case_type": "가사소송",
                "case_subtype": "라,마류 가사비송",
                "similarity": 0.87,
                "source": "forms/FORM-002.hwpx",
            },
        ]

    candidates = search_rag_candidates(
        query_text="이혼 후 재산을 나누고 싶습니다.",
        top_n=2,
        retrieve=fake_retrieve,
    )

    assert calls == {
        "query": "이혼 후 재산을 나누고 싶습니다.",
        "top_k": 2,
    }

    assert [
        candidate["tmpltNo"]
        for candidate in candidates
    ] == [
        "FORM-001",
        "FORM-002",
    ]

    assert candidates[0]["name"] == (
        "이혼 및 재산분할청구의 소"
    )


def test_search_rag_candidates_deduplicates_same_source():
    from app.ai.forms.rag_candidates import (
        search_rag_candidates,
    )

    def fake_retrieve(**kwargs):
        return [
            {
                "document_id": "I001000051",
                "title": "개명허가신청서",
                "case_type": "가족관계등록",
                "case_subtype": "성본창설과 개명",
                "similarity": 0.91,
                "chunk_id": (
                    "I001000051::chunk-0000"
                ),
                "source": (
                    "서식_hwpx/가족관계등록/"
                    "성본창설과 개명/"
                    "개명허가신청서.hwpx"
                ),
            },
            {
                "document_id": "I001000052",
                "title": "개명허가신청서",
                "case_type": "가족관계등록",
                "case_subtype": "성본창설과 개명",
                "similarity": 0.90,
                "chunk_id": (
                    "I001000052::chunk-0000"
                ),
                "source": (
                    "서식_hwpx/가족관계등록/"
                    "성본창설과 개명/"
                    "개명허가신청서.hwpx"
                ),
            },
            {
                "document_id": "I001001181",
                "title": "성 및 본의 창설허가신청서",
                "case_type": "가족관계등록",
                "case_subtype": "성본창설과 개명",
                "similarity": 0.89,
                "chunk_id": (
                    "I001001181::chunk-0000"
                ),
                "source": (
                    "서식_hwpx/가족관계등록/"
                    "성본창설과 개명/"
                    "성및본창설허가신청서.hwpx"
                ),
            },
        ]

    candidates = search_rag_candidates(
        query_text="이름을 개명하고 싶습니다.",
        top_n=3,
        retrieve=fake_retrieve,
    )

    assert [
        candidate["tmpltNo"]
        for candidate in candidates
    ] == [
        "I001000051",
        "I001001181",
    ]



def test_search_rag_candidates_promotes_primary_inheritance_form():
    def fake_retrieve(**kwargs):
        return [
            {
                "document_id": "DEATH",
                "title": (
                    "\uc0ac\ub9dd\uc2e0\uace0\uc11c"
                    "(\uc2dc\uad6c\uc74d\uba74\ub3d9"
                    "\uc0ac\ubb34\uc18c \uc81c\ucd9c\uc6a9)"
                ),
                "case_type": "\uac00\uc871\uad00\uacc4\ub4f1\ub85d",
                "case_subtype": "\uc2e0\uace0",
                "similarity": 0.901586,
                "chunk_id": "DEATH::chunk-0001",
                "source": "forms/death-report.hwpx",
            },
            {
                "document_id": "CORRECTION",
                "title": (
                    "[\uc0c1\uc18d\uc7ac\uc0b0\ubaa9\ub85d "
                    "\uacbd\uc815\uc2e0\uccad\uc11c"
                    "(\ud55c\uc815\uc2b9\uc778)]"
                ),
                "case_type": "\uac00\uc0ac\uc18c\uc1a1",
                "case_subtype": (
                    "\ub77c,\ub9c8\ub958 \uac00\uc0ac\ube44\uc1a1"
                ),
                "similarity": 0.897686,
                "chunk_id": "CORRECTION::chunk-0001",
                "source": (
                    "forms/inheritance-correction.hwpx"
                ),
            },
            {
                "document_id": "LIMITED",
                "title": (
                    "\uc0c1\uc18d\ud55c\uc815\uc2b9\uc778 "
                    "\uc2ec\ud310\uccad\uad6c\uc11c"
                ),
                "case_type": "\uac00\uc0ac\uc18c\uc1a1",
                "case_subtype": (
                    "\ub77c,\ub9c8\ub958 \uac00\uc0ac\ube44\uc1a1"
                ),
                "similarity": 0.895744,
                "chunk_id": "LIMITED::chunk-0001",
                "source": (
                    "forms/limited-acceptance.hwpx"
                ),
            },
        ]

    candidates = search_rag_candidates(
        query_text=(
            "\ubd80\ubaa8\ub2d8\uc774 \ub0a8\uae34 "
            "\ube5a\uc774 \ub9ce\uc544\uc11c "
            "\uc0c1\uc18d\uc744 \ud3ec\uae30\ud558\uac70\ub098 "
            "\ud55c\uc815\uc2b9\uc778\uc744 "
            "\uc2e0\uccad\ud558\uace0 \uc2f6\uc2b5\ub2c8\ub2e4."
        ),
        top_n=3,
        retrieve=fake_retrieve,
    )

    assert candidates[0]["name"] == (
        "\uc0c1\uc18d\ud55c\uc815\uc2b9\uc778 "
        "\uc2ec\ud310\uccad\uad6c\uc11c"
    )
