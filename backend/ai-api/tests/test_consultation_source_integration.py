from __future__ import annotations

import asyncio

from pathlib import Path
from types import SimpleNamespace

from app.ai.consult.rag_service import (
    collect_related_legal_sources,
)
from app.ai.consult.schemas import (
    ConsultAnalyzeResponse,
    RawInput,
)


BACKEND_DIR = (
    Path(__file__).resolve().parents[2]
)

JAVA_RESPONSE_PATH = (
    BACKEND_DIR
    / "core-api"
    / "src"
    / "main"
    / "java"
    / "com"
    / "aivle"
    / "bigproject"
    / "analysis"
    / "client"
    / "ConsultAnalyzeApiResponse.java"
)


def test_python_and_java_contracts_expose_consultations():
    assert (
        "related_consultations"
        in ConsultAnalyzeResponse.model_fields
    )

    field = (
        ConsultAnalyzeResponse
        .model_fields[
            "related_consultations"
        ]
    )

    assert field.default_factory is list

    java_source = (
        JAVA_RESPONSE_PATH.read_text(
            encoding="utf-8-sig"
        )
    )

    assert (
        "JsonNode relatedConsultations"
        in java_source
    )


def test_aggregation_uses_only_anonymized_text():
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
            "\uc591\uc721\ube44\ub97c "
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
        calls["consultations"].append(
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

    result = (
        collect_related_legal_sources(
            content=content,
            top_n=5,
            consultation_search=(
                fake_consultations
            ),
            statute_search=fake_statutes,
            precedent_search=(
                fake_precedents
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

    assert list(result) == [
        "related_statutes",
        "related_precedents",
        "related_consultations",
    ]

    assert (
        "RAW-SUMMARY-SECRET"
        not in str(calls)
    )
    assert (
        "RAW-DETAIL-SECRET"
        not in str(calls)
    )


def test_aggregation_returns_all_empty_without_anonymized_text():
    called = False

    def must_not_run(**_kwargs):
        nonlocal called
        called = True
        return []

    result = (
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

    assert result == {
        "related_statutes": [],
        "related_precedents": [],
        "related_consultations": [],
    }

    assert called is False


def test_consultation_failure_does_not_remove_other_sources():
    def broken_consultations(
        **_kwargs,
    ):
        raise RuntimeError(
            "consultation failure"
        )

    result = (
        collect_related_legal_sources(
            content={
                "anonymized_text": (
                    "\uc0c1\uc18d\ud3ec\uae30 "
                    "\ubb38\uc758"
                )
            },
            statute_search=(
                lambda **_kwargs: [
                    {
                        "citation": (
                            "statute"
                        )
                    }
                ]
            ),
            precedent_search=(
                lambda **_kwargs: [
                    {
                        "precedent_id": (
                            "100"
                        )
                    }
                ]
            ),
            consultation_search=(
                broken_consultations
            ),
        )
    )

    assert result == {
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
        "related_consultations": [],
    }


def test_router_returns_related_consultations(
    monkeypatch,
):
    monkeypatch.setenv(
        "OPENAI_API_KEY",
        "test-key",
    )
    monkeypatch.setenv(
        "S3_BUCKET_NAME",
        "test-bucket",
    )

    from app.routers import consult

    monkeypatch.setattr(
        consult.stt_extract,
        "normalize_file_links",
        lambda links: [],
    )

    monkeypatch.setattr(
        consult.stt_extract,
        "extract_all",
        lambda links: SimpleNamespace(
            texts=[],
            details=[],
            text="",
        ),
    )

    monkeypatch.setattr(
        consult.analysis_service,
        "build_consult_text",
        lambda *_args: (
            "RAW ANALYSIS TEXT"
        ),
    )

    class FakeAnalysis:
        def to_dict(self):
            return {
                "consult_summary": (
                    "\uc0c1\ub2f4 \uc694\uc57d"
                ),
                "consult_case_type": (
                    "\uce5c\uc871"
                ),
                "consult_case_subtype": (
                    "\uc591\uc721\ube44"
                ),
                "consult_extracted": {},
                "consult_timeline": [],
            }

    monkeypatch.setattr(
        consult.analysis_service,
        "analyze",
        lambda _text: FakeAnalysis(),
    )

    async def fake_graph(state):
        return {
            "raw_input": (
                state["content"]
            )
        }

    monkeypatch.setattr(
        consult,
        "run_consult_analysis",
        fake_graph,
    )

    anonymized_text = (
        "[PERSON]\uc774 "
        "\uc591\uc721\ube44\ub97c "
        "\uc9c0\uae09\ud558\uc9c0 "
        "\uc54a\uc2b5\ub2c8\ub2e4."
    )

    def fake_collect(
        *,
        content,
        top_n,
    ):
        assert (
            content[
                "anonymized_text"
            ]
            == anonymized_text
        )
        assert top_n == 5

        return {
            "related_statutes": [],
            "related_precedents": [],
            "related_consultations": [
                {
                    "consultation_id": (
                        "consultation-1"
                    )
                }
            ],
        }

    monkeypatch.setattr(
        consult,
        "collect_related_legal_sources",
        fake_collect,
    )

    payload = RawInput(
        content={
            "summary": (
                "RAW-SUMMARY-SECRET"
            ),
            "details": (
                "RAW-DETAIL-SECRET"
            ),
            "anonymized_text": (
                anonymized_text
            ),
            "summited_file_link": [],
        }
    )

    result = asyncio.run(
        consult.analyze_consult(
            payload
        )
    )

    assert result[
        "related_consultations"
    ] == [
        {
            "consultation_id": (
                "consultation-1"
            )
        }
    ]
