import asyncio
import threading

from types import SimpleNamespace

from app.ai.consult.schemas import RawInput
from app.routers import consult as consult_router


def make_payload():
    return RawInput(
        content={
            "summary": "summary",
            "details": "details",
            "anonymized_text": (
                "anonymized consultation"
            ),
            "summited_file_link": [],
        }
    )


class FakeAnalysis:
    output = {
        "summary": "analysis summary",
    }

    def to_dict(self):
        return {
            "analysis_result": "ok",
        }


def patch_lightweight_pipeline(
    monkeypatch,
    *,
    extract_all,
    analyze,
    run_graph,
    search_rag,
    validate_output,
):
    monkeypatch.setattr(
        consult_router.stt_extract,
        "normalize_file_links",
        lambda value: [],
    )
    monkeypatch.setattr(
        consult_router.stt_extract,
        "extract_all",
        extract_all,
    )
    monkeypatch.setattr(
        consult_router.analysis_service,
        "build_consult_text",
        lambda summary, details, text: (
            "consult text"
        ),
    )
    monkeypatch.setattr(
        consult_router.analysis_service,
        "analyze",
        analyze,
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
    monkeypatch.setattr(
        consult_router,
        "run_consult_analysis",
        run_graph,
    )
    monkeypatch.setattr(
        consult_router,
        "collect_related_legal_sources",
        search_rag,
    )
    monkeypatch.setattr(
        consult_router,
        "validate_consultation_output",
        validate_output,
    )


def legal_sources():
    return {
        "related_statutes": [],
        "related_precedents": [],
        "related_consultations": [],
    }


def test_blocking_pipeline_steps_run_outside_event_loop(
    monkeypatch,
):
    event_loop_thread = threading.get_ident()
    called_threads = {}

    def record(
        name,
        result,
    ):
        called_threads[name] = (
            threading.get_ident()
        )
        return result

    def extract_all(file_links):
        return record(
            "extract_all",
            SimpleNamespace(
                text="",
                texts=[],
                details=[],
            ),
        )

    def analyze(text):
        return record(
            "analyze",
            FakeAnalysis(),
        )

    async def run_graph(state):
        called_threads["graph"] = (
            threading.get_ident()
        )
        return {
            "graph_result": "ok",
        }

    def search_rag(
        *,
        content,
        top_n,
    ):
        return record(
            "rag",
            legal_sources(),
        )

    def validate_output(
        *,
        analysis_output,
        legal_sources,
    ):
        return record(
            "validation",
            {
                "decision": "safe",
            },
        )

    patch_lightweight_pipeline(
        monkeypatch,
        extract_all=extract_all,
        analyze=analyze,
        run_graph=run_graph,
        search_rag=search_rag,
        validate_output=validate_output,
    )

    result = asyncio.run(
        consult_router.analyze_consult(
            make_payload()
        )
    )

    assert result["graph_result"] == "ok"
    assert result["output_validation"] == {
        "decision": "safe",
    }

    for name in (
        "extract_all",
        "analyze",
        "rag",
        "validation",
    ):
        assert (
            called_threads[name]
            != event_loop_thread
        ), (
            f"{name} ran on "
            "event-loop thread"
        )

    assert (
        called_threads["graph"]
        == event_loop_thread
    )


def test_graph_and_rag_search_run_concurrently(
    monkeypatch,
):
    graph_started = threading.Event()
    rag_started = threading.Event()

    def extract_all(file_links):
        return SimpleNamespace(
            text="",
            texts=[],
            details=[],
        )

    def analyze(text):
        return FakeAnalysis()

    async def run_graph(state):
        graph_started.set()

        for _ in range(100):
            if rag_started.is_set():
                break

            await asyncio.sleep(0.01)

        assert rag_started.is_set(), (
            "RAG did not start while "
            "graph was running"
        )

        return {
            "graph_result": "ok",
        }

    def search_rag(
        *,
        content,
        top_n,
    ):
        rag_started.set()

        assert graph_started.wait(
            timeout=1.0
        ), (
            "Graph did not start while "
            "RAG was running"
        )

        return legal_sources()

    def validate_output(
        *,
        analysis_output,
        legal_sources,
    ):
        return {
            "decision": "safe",
        }

    patch_lightweight_pipeline(
        monkeypatch,
        extract_all=extract_all,
        analyze=analyze,
        run_graph=run_graph,
        search_rag=search_rag,
        validate_output=validate_output,
    )

    result = asyncio.run(
        consult_router.analyze_consult(
            make_payload()
        )
    )

    assert result["graph_result"] == "ok"
