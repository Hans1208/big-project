from app.ai.consult.rag_service import (
    collect_related_legal_sources,
)
from app.ai.consult.schemas import (
    ConsultAnalyzeResponse,
    RawInputContent,
)


def test_consult_schema_exposes_anonymized_rag_fields():
    assert (
        "anonymized_text"
        in RawInputContent.model_fields
    )

    for field_name in (
        "related_statutes",
        "related_precedents",
        "related_consultations",
    ):
        assert (
            field_name
            in ConsultAnalyzeResponse.model_fields
        )


def test_consult_rag_reads_only_anonymized_text():
    calls = {
        "statutes": [],
        "precedents": [],
        "consultations": [],
    }

    content = {
        "summary": "RAW-SUMMARY-SECRET",
        "details": "RAW-DETAIL-SECRET",
        "anonymized_text": (
            "[PERSON]\uacfc "
            "\uc774\ud63c\ud558\uba70 "
            "\uc7ac\uc0b0\ubd84\ud560\uc744 "
            "\uccad\uad6c\ud569\ub2c8\ub2e4."
        ),
    }

    def fake_statutes(
        *,
        anonymized_text,
        top_n,
    ):
        calls["statutes"].append(
            (
                anonymized_text,
                top_n,
            )
        )

        return [
            {
                "citation": "statute"
            }
        ]

    def fake_precedents(
        *,
        anonymized_text,
        top_n,
    ):
        calls["precedents"].append(
            (
                anonymized_text,
                top_n,
            )
        )

        return [
            {
                "precedent_id": "100"
            }
        ]

    def fake_consultations(
        *,
        anonymized_text,
        top_n,
    ):
        calls[
            "consultations"
        ].append(
            (
                anonymized_text,
                top_n,
            )
        )

        return [
            {
                "consultation_id": (
                    "consultation-1"
                )
            }
        ]

    results = (
        collect_related_legal_sources(
            content=content,
            top_n=5,
            statute_search=fake_statutes,
            precedent_search=(
                fake_precedents
            ),
            consultation_search=(
                fake_consultations
            ),
        )
    )

    expected_text = (
        content["anonymized_text"]
    )

    assert calls == {
        "statutes": [
            (
                expected_text,
                5,
            )
        ],
        "precedents": [
            (
                expected_text,
                5,
            )
        ],
        "consultations": [
            (
                expected_text,
                3,
            )
        ],
    }

    assert (
        "RAW-SUMMARY-SECRET"
        not in str(calls)
    )

    assert (
        "RAW-DETAIL-SECRET"
        not in str(calls)
    )

    assert results == {
        "related_statutes": [
            {
                "citation": "statute"
            }
        ],
        "related_precedents": [
            {
                "precedent_id": "100"
            }
        ],
        "related_consultations": [
            {
                "consultation_id": (
                    "consultation-1"
                )
            }
        ],
    }


def test_consult_rag_returns_empty_without_anonymized_text():
    called = False

    def must_not_run(**_kwargs):
        nonlocal called
        called = True
        return []

    results = (
        collect_related_legal_sources(
            content={
                "summary": "RAW",
                "details": "RAW",
            },
            statute_search=must_not_run,
            precedent_search=must_not_run,
            consultation_search=(
                must_not_run
            ),
        )
    )

    assert results == {
        "related_statutes": [],
        "related_precedents": [],
        "related_consultations": [],
    }

    assert called is False
