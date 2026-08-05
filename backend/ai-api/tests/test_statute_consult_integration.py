import asyncio

from types import SimpleNamespace

from app.ai.consult.schemas import (
    ConsultAnalyzeResponse,
    RawInput,
)


class FakeAnalysis:
    summary = (
        "\uc774\ud63c \ud6c4 "
        "\uc7ac\uc0b0\ubd84\ud560 "
        "\uccad\uad6c \uc0ac\uac74"
    )
    case_type = "\uac00\uc0ac\uc18c\uc1a1"
    case_subtype = "\uc7ac\uc0b0\ubd84\ud560"
    extracted = {
        "\uccad\uad6c\ub0b4\uc6a9": (
            "\uc7ac\uc0b0\ubd84\ud560"
        ),
    }
    timeline = []

    def to_dict(self):
        return {
            "consult_summary": self.summary,
            "consult_case_type": self.case_type,
            "consult_case_subtype": (
                self.case_subtype
            ),
            "consult_extracted": self.extracted,
            "consult_timeline": self.timeline,
        }


def test_consult_response_schema_has_legal_sources():
    fields = (
        ConsultAnalyzeResponse.model_fields
    )

    assert "related_statutes" in fields
    assert "related_precedents" in fields

    assert (
        fields["related_statutes"]
        .default_factory
        is list
    )
    assert (
        fields["related_precedents"]
        .default_factory
        is list
    )


def test_analyze_consult_attaches_anonymized_legal_sources(
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

    analysis = FakeAnalysis()
    calls = {}

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
        lambda summary, details, extracted: (
            "COMBINED CONSULT TEXT"
        ),
    )
    monkeypatch.setattr(
        consult.analysis_service,
        "analyze",
        lambda consult_text: analysis,
    )

    async def fake_run_consult_analysis(state):
        return {
            "raw_input": state["content"],
        }

    monkeypatch.setattr(
        consult,
        "run_consult_analysis",
        fake_run_consult_analysis,
    )

    def fake_collect_related_legal_sources(
        *,
        content,
        top_n,
    ):
        calls["anonymized_text"] = (
            content.get("anonymized_text")
        )
        calls["top_n"] = top_n

        return {
            "related_statutes": [
                {
                    "citation": (
                        "\ubbfc\ubc95 "
                        "\uc81c839\uc870\uc7582"
                        "(\uc7ac\uc0b0\ubd84\ud560"
                        "\uccad\uad6c\uad8c)"
                    ),
                }
            ],
            "related_precedents": [
                {
                    "precedent_id": "100",
                    "case_name": (
                        "\uc774\ud63c\ubc0f"
                        "\uc7ac\uc0b0\ubd84\ud560"
                    ),
                }
            ],
        }

    monkeypatch.setattr(
        consult,
        "collect_related_legal_sources",
        fake_collect_related_legal_sources,
    )

    anonymized_text = (
        "[PERSON]\uacfc \uc774\ud63c\ud558\uba70 "
        "\uc7ac\uc0b0\ubd84\ud560\uc744 "
        "\uccad\uad6c\ud569\ub2c8\ub2e4."
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
        consult.analyze_consult(payload)
    )

    assert calls == {
        "anonymized_text": anonymized_text,
        "top_n": 5,
    }

    assert result["related_statutes"] == [
        {
            "citation": (
                "\ubbfc\ubc95 "
                "\uc81c839\uc870\uc7582"
                "(\uc7ac\uc0b0\ubd84\ud560"
                "\uccad\uad6c\uad8c)"
            ),
        }
    ]

    assert result["related_precedents"] == [
        {
            "precedent_id": "100",
            "case_name": (
                "\uc774\ud63c\ubc0f"
                "\uc7ac\uc0b0\ubd84\ud560"
            ),
        }
    ]
