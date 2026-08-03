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


def test_consult_response_schema_has_related_statutes():
    assert "related_statutes" in (
        ConsultAnalyzeResponse.model_fields
    )

    field = (
        ConsultAnalyzeResponse
        .model_fields["related_statutes"]
    )

    assert field.default_factory is list


def test_analyze_consult_attaches_related_statutes(
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

    def fake_find_related_statutes(
        *,
        analysis,
        fallback_text,
        top_n,
    ):
        calls["analysis"] = analysis
        calls["fallback_text"] = fallback_text
        calls["top_n"] = top_n

        return [
            {
                "citation": (
                    "\ubbfc\ubc95 "
                    "\uc81c839\uc870\uc7582"
                    "(\uc7ac\uc0b0\ubd84\ud560"
                    "\uccad\uad6c\uad8c)"
                ),
            }
        ]

    monkeypatch.setattr(
        consult,
        "find_related_statutes",
        fake_find_related_statutes,
    )

    payload = RawInput(
        content={
            "summary": (
                "\uc774\ud63c \ud6c4 "
                "\uc7ac\uc0b0\ubd84\ud560"
            ),
            "details": (
                "\uc0c1\ub300\ubc29\uacfc "
                "\ud611\uc758\uac00 \ub418\uc9c0 "
                "\uc54a\uc2b5\ub2c8\ub2e4."
            ),
            "summited_file_link": [],
        }
    )

    result = asyncio.run(
        consult.analyze_consult(payload)
    )

    assert calls == {
        "analysis": analysis,
        "fallback_text": (
            "COMBINED CONSULT TEXT"
        ),
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
