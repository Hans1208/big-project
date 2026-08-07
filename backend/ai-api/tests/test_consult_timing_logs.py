import asyncio
import logging

from types import SimpleNamespace

from app.ai.consult.schemas import RawInput
from app.routers import consult as consult_router


PRIVATE_MARKER = "PRIVATE-CONSULT-CONTENT-12345"


class FakeAnalysis:
    output = {
        "summary": "safe analysis",
    }

    def to_dict(self):
        return {
            "analysis_result": "ok",
        }


def make_payload():
    return RawInput(
        content={
            "summary": PRIVATE_MARKER,
            "details": PRIVATE_MARKER,
            "anonymized_text": (
                "anonymized consultation"
            ),
            "summited_file_link": [],
        }
    )


def test_analyze_consult_logs_stage_times_without_content(
    monkeypatch,
    caplog,
):
    monkeypatch.setattr(
        consult_router.stt_extract,
        "normalize_file_links",
        lambda value: [],
    )

    monkeypatch.setattr(
        consult_router.stt_extract,
        "extract_all",
        lambda links: SimpleNamespace(
            text=PRIVATE_MARKER,
            texts=[PRIVATE_MARKER],
            details=[],
        ),
    )

    monkeypatch.setattr(
        consult_router.analysis_service,
        "build_consult_text",
        lambda summary, details, text: (
            PRIVATE_MARKER
        ),
    )

    monkeypatch.setattr(
        consult_router.analysis_service,
        "analyze",
        lambda text: FakeAnalysis(),
    )

    monkeypatch.setattr(
        consult_router.analysis_service,
        "scrub_sensitive_numbers",
        lambda value: value,
    )

    monkeypatch.setattr(
        consult_router.analysis_service,
        "without_draft_contact",
        lambda value: value,
    )

    async def fake_graph(state):
        return {
            "graph_result": "ok",
        }

    monkeypatch.setattr(
        consult_router,
        "run_consult_analysis",
        fake_graph,
    )

    monkeypatch.setattr(
        consult_router,
        "collect_related_legal_sources",
        lambda **kwargs: {
            "related_statutes": [
                {"id": "statute-1"},
            ],
            "related_precedents": [
                {"id": "precedent-1"},
                {"id": "precedent-2"},
            ],
            "related_consultations": [
                {"id": "consultation-1"},
            ],
        },
    )

    monkeypatch.setattr(
        consult_router,
        "validate_consultation_output",
        lambda **kwargs: {
            "decision": "safe",
        },
    )

    caplog.set_level(
        logging.INFO,
        logger=consult_router.__name__,
    )

    result = asyncio.run(
        consult_router.analyze_consult(
            make_payload()
        )
    )

    assert result["graph_result"] == "ok"

    messages = "\n".join(
        record.getMessage()
        for record in caplog.records
        if record.name
        == consult_router.__name__
    )

    for stage in (
        "extract",
        "analysis",
        "consult_graph",
        "rag",
        "output_validation",
    ):
        assert (
            f"stage={stage}"
            in messages
        )
        assert "elapsed_ms=" in messages

    assert (
        "consult_analyze_completed"
        in messages
    )
    assert "total_ms=" in messages
    assert "statutes=1" in messages
    assert "precedents=2" in messages
    assert "consultations=1" in messages

    assert PRIVATE_MARKER not in messages
