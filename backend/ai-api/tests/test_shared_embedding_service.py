from rag.consultation_retriever import (
    ConsultationRetriever,
)
from rag.embedding_service import (
    EmbeddingService,
    get_default_embedding_service,
)
from rag.precedent_retriever import (
    PrecedentRetriever,
)
from rag.statute_retriever import (
    StatuteRetriever,
)


def test_default_embedding_service_is_singleton():
    first = (
        get_default_embedding_service()
    )
    second = (
        get_default_embedding_service()
    )

    assert first is second
    assert isinstance(
        first,
        EmbeddingService,
    )


def test_default_retrievers_use_shared_embedding_service():
    shared = (
        get_default_embedding_service()
    )

    statute_retriever = StatuteRetriever(
        vector_store=object()
    )
    precedent_retriever = (
        PrecedentRetriever(
            vector_store=object()
        )
    )
    consultation_retriever = (
        ConsultationRetriever(
            vector_store=object()
        )
    )

    assert (
        statute_retriever
        .embedding_service
        is shared
    )
    assert (
        precedent_retriever
        .embedding_service
        is shared
    )
    assert (
        consultation_retriever
        .embedding_service
        is shared
    )


def test_injected_embedding_service_is_preserved():
    custom_service = object()

    statute_retriever = StatuteRetriever(
        embedding_service=custom_service,
        vector_store=object(),
    )
    precedent_retriever = (
        PrecedentRetriever(
            embedding_service=(
                custom_service
            ),
            vector_store=object(),
        )
    )
    consultation_retriever = (
        ConsultationRetriever(
            embedding_service=(
                custom_service
            ),
            vector_store=object(),
        )
    )

    assert (
        statute_retriever
        .embedding_service
        is custom_service
    )
    assert (
        precedent_retriever
        .embedding_service
        is custom_service
    )
    assert (
        consultation_retriever
        .embedding_service
        is custom_service
    )
