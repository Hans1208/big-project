"""Retrieve similar consultation records from Chroma."""

from __future__ import annotations

import re

from functools import lru_cache
from typing import Any

from rag.config import (
    CHROMA_DB_DIR,
    LEGAL_CONSULTATIONS_COLLECTION_NAME,
)
from rag.embedding_service import (
    EmbeddingService,
)
from rag.vector_store import (
    ChromaVectorStore,
)


DEFAULT_TOP_K = 3
DEFAULT_CANDIDATE_COUNT = 24
MINIMUM_CANDIDATE_COUNT = 15

SOURCE_LIMITS = {
    "case": 2,
    "basic": 1,
}

CATEGORY_KEYWORDS = {
    "family_registration": (
        "가족관계등록",
        "가족관계증명",
        "등록부",
        "출생신고",
        "사망신고",
        "개명",
        "성과본",
        "성본",
        "국적",
    ),
    "inheritance": (
        "상속",
        "유언",
        "유증",
        "유류분",
        "한정승인",
        "상속포기",
        "상속재산",
    ),
    "family_litigation": (
        "이혼",
        "재산분할",
        "위자료",
        "양육비",
        "양육권",
        "면접교섭",
        "혼인무효",
        "혼인취소",
        "사실혼",
        "친권자지정",
        "친권자변경",
    ),
    "kinship": (
        "입양",
        "파양",
        "친생자",
        "친생부인",
        "인지청구",
        "인지신고",
        "친자인지",
        "성년후견",
        "한정후견",
        "미성년후견",
        "후견",
        "친권상실",
        "부양",
        "실종",
    ),
}

TOPIC_SIGNALS = (
    {
        "name": "visitation",
        "query_terms": (
            "\uc544\uc774\ub97c\ubcf4\uc9c0\ubabb",
            "\uc790\ub140\ub97c\ubcf4\uc9c0\ubabb",
            "\uc544\uc774\ub97c\ub9cc\ub098\uc9c0\ubabb",
            "\uc790\ub140\ub97c\ub9cc\ub098\uc9c0\ubabb",
            "\uc544\uc774\ub97c\ubabb\ub9cc\ub098",
            "\uc790\ub140\ub97c\ubabb\ub9cc\ub098",
            "\ub9cc\ub098\uc9c0\ubabb\ud558\uac8c",
            "\ubcf4\uc9c0\ubabb\ud558\uac8c",
            "\uba74\uc811\uad50\uc12d",
        ),
        "candidate_terms": (
            "\uba74\uc811\uad50\uc12d",
            "\uba74\uc811\uad50\uc12d\uad8c",
        ),
        "boost": 0.34,
    },
    {
        "name": "inheritance_debt",
        "query_terms": (
            "\ube5a",
            "\ucc44\ubb34",
            "\ubd80\ucc44",
            "\uc0c1\uc18d\uc744\ubc1b\uc9c0\uc54a",
            "\uc0c1\uc18d\uc7ac\uc0b0\uc744\ubc1b\uc9c0\uc54a",
            "\uc0c1\uc18d\uc744\ud3ec\uae30",
        ),
        "candidate_terms": (
            "\uc0c1\uc18d\ud3ec\uae30",
            "\ud55c\uc815\uc2b9\uc778",
            "\uc0c1\uc18d\ucc44\ubb34",
            "\ucc44\ubb34",
        ),
        "boost": 0.28,
    },
    {
        "name": "adult_guardianship",
        "query_terms": (
            "\uce58\ub9e4",
            "\uc131\ub144\ud6c4\uacac",
            "\ud310\ub2e8\ub2a5\ub825",
            "\uc758\uc0ac\ub2a5\ub825",
            "\uc815\uc2e0\uc801\uc81c\uc57d",
        ),
        "candidate_terms": (
            "\uc131\ub144\ud6c4\uacac",
            "\uc131\ub144\ud6c4\uacac\uac1c\uc2dc",
        ),
        "exclude_candidate_terms": (
            "\ubbf8\uc131\ub144\ud6c4\uacac",
        ),
        "boost": 0.30,
    },
)



def _normalize_text(
    value: object,
) -> str:
    return re.sub(
        r"[^0-9a-z가-힣]+",
        "",
        str(
            value or ""
        ).casefold(),
    )


def _character_ngrams(
    text: str,
    size: int = 2,
) -> set[str]:
    if not text:
        return set()

    if len(text) < size:
        return {text}

    return {
        text[index:index + size]
        for index in range(
            len(text) - size + 1
        )
    }


def infer_service_category(
    query: object,
) -> str | None:
    normalized_query = (
        _normalize_text(query)
    )

    if not normalized_query:
        return None

    category_scores: dict[
        str,
        int,
    ] = {}

    for (
        category,
        keywords,
    ) in CATEGORY_KEYWORDS.items():
        category_scores[category] = sum(
            len(
                _normalize_text(
                    keyword
                )
            )
            for keyword in keywords
            if _normalize_text(
                keyword
            ) in normalized_query
        )

    best_category = max(
        category_scores,
        key=category_scores.get,
    )

    if category_scores[
        best_category
    ] <= 0:
        return None

    return best_category


def _question_lexical_boost(
    query: str,
    candidate_question: object,
) -> float:
    normalized_query = (
        _normalize_text(query)
    )
    normalized_question = (
        _normalize_text(
            candidate_question
        )
    )

    if (
        not normalized_query
        or not normalized_question
    ):
        return 0.0

    if (
        normalized_question
        in normalized_query
        or normalized_query
        in normalized_question
    ):
        return 0.22

    query_ngrams = _character_ngrams(
        normalized_query
    )
    question_ngrams = (
        _character_ngrams(
            normalized_question
        )
    )

    if (
        not query_ngrams
        or not question_ngrams
    ):
        return 0.0

    intersection = len(
        query_ngrams
        & question_ngrams
    )

    union = len(
        query_ngrams
        | question_ngrams
    )

    ratio = (
        intersection / union
        if union
        else 0.0
    )

    return min(
        0.20,
        ratio * 0.35,
    )


def _keyword_boost(
    query: str,
    candidate: dict[str, Any],
) -> float:
    normalized_query = (
        _normalize_text(query)
    )

    candidate_text = (
        _normalize_text(
            " ".join(
                (
                    str(
                        candidate.get(
                            "question",
                            "",
                        )
                    ),
                    str(
                        candidate.get(
                            "legal_path",
                            "",
                        )
                    ),
                    str(
                        candidate.get(
                            "answer",
                            "",
                        )
                    )[:1000],
                )
            )
        )
    )

    if (
        not normalized_query
        or not candidate_text
    ):
        return 0.0

    matched_length = 0

    for keywords in (
        CATEGORY_KEYWORDS.values()
    ):
        for keyword in keywords:
            normalized_keyword = (
                _normalize_text(
                    keyword
                )
            )

            if (
                normalized_keyword
                and normalized_keyword
                in normalized_query
                and normalized_keyword
                in candidate_text
            ):
                matched_length += len(
                    normalized_keyword
                )

    return min(
        0.14,
        matched_length * 0.012,
    )


def _topic_boost(
    query: str,
    candidate: dict[str, Any],
) -> float:
    normalized_query = (
        _normalize_text(query)
    )

    candidate_text = (
        _normalize_text(
            " ".join(
                (
                    str(
                        candidate.get(
                            "question",
                            "",
                        )
                    ),
                    str(
                        candidate.get(
                            "legal_path",
                            "",
                        )
                    ),
                    str(
                        candidate.get(
                            "answer",
                            "",
                        )
                    )[:1000],
                )
            )
        )
    )

    best_boost = 0.0

    for signal in TOPIC_SIGNALS:
        query_matched = any(
            _normalize_text(term)
            in normalized_query
            for term
            in signal["query_terms"]
        )

        if not query_matched:
            continue

        excluded_candidate = any(
            _normalize_text(term)
            in candidate_text
            for term
            in signal.get(
                "exclude_candidate_terms",
                (),
            )
        )

        if excluded_candidate:
            continue

        candidate_matched = any(
            _normalize_text(term)
            in candidate_text
            for term
            in signal[
                "candidate_terms"
            ]
        )

        if candidate_matched:
            best_boost = max(
                best_boost,
                float(
                    signal["boost"]
                ),
            )

    return best_boost



def rerank_consultation_candidates(
    query: str,
    candidates: list[
        dict[str, Any]
    ],
) -> list[dict[str, Any]]:
    inferred_category = (
        infer_service_category(
            query
        )
    )

    reranked: list[
        dict[str, Any]
    ] = []

    for original_rank, candidate in enumerate(
        candidates
    ):
        normalized = dict(
            candidate
        )

        similarity = float(
            normalized.get(
                "similarity",
                0.0,
            )
            or 0.0
        )

        category_boost = 0.0

        if (
            inferred_category
            and normalized.get(
                "service_category"
            )
            == inferred_category
        ):
            category_boost = 0.10

        question_boost = (
            _question_lexical_boost(
                query,
                normalized.get(
                    "question",
                    "",
                ),
            )
        )

        keyword_boost = (
            _keyword_boost(
                query,
                normalized,
            )
        )

        topic_boost = (
            _topic_boost(
                query,
                normalized,
            )
        )

        normalized[
            "rerank_score"
        ] = (
            similarity
            + category_boost
            + question_boost
            + keyword_boost
            + topic_boost
        )

        normalized[
            "inferred_category"
        ] = (
            inferred_category or ""
        )

        normalized[
            "_original_rank"
        ] = original_rank

        reranked.append(
            normalized
        )

    reranked.sort(
        key=lambda item: (
            float(
                item.get(
                    "rerank_score",
                    0.0,
                )
            ),
            float(
                item.get(
                    "similarity",
                    0.0,
                )
            ),
            -int(
                item.get(
                    "_original_rank",
                    0,
                )
            ),
        ),
        reverse=True,
    )

    for candidate in reranked:
        candidate.pop(
            "_original_rank",
            None,
        )

    return reranked


def _candidate_result(
    candidate: dict[str, Any],
) -> dict[str, Any]:
    result = dict(
        candidate
    )

    result["chunk_id"] = str(
        candidate.get(
            "id",
            "",
        )
        or ""
    )

    result["consultation_id"] = str(
        candidate.get(
            "consultation_id",
            "",
        )
        or ""
    ).strip()

    result["source_type"] = str(
        candidate.get(
            "source_type",
            "",
        )
        or ""
    ).strip()

    result["service_category"] = str(
        candidate.get(
            "service_category",
            "",
        )
        or ""
    ).strip()

    result["question"] = str(
        candidate.get(
            "question",
            "",
        )
        or ""
    ).strip()

    result["answer"] = str(
        candidate.get(
            "answer",
            "",
        )
        or ""
    ).strip()

    result["legal_path"] = str(
        candidate.get(
            "legal_path",
            "",
        )
        or ""
    ).strip()

    result["source_file"] = str(
        candidate.get(
            "source_file",
            "",
        )
        or ""
    ).strip()

    result["source_row"] = str(
        candidate.get(
            "source_row",
            "",
        )
        or ""
    ).strip()

    result["source_date"] = str(
        candidate.get(
            "source_date",
            "",
        )
        or ""
    ).strip()

    return result


def _select_balanced_results(
    candidates: list[
        dict[str, Any]
    ],
    *,
    top_k: int,
) -> list[dict[str, Any]]:
    selected: list[
        dict[str, Any]
    ] = []

    selected_ids: set[str] = set()

    source_counts = {
        "case": 0,
        "basic": 0,
    }

    def add_candidate(
        candidate: dict[str, Any],
    ) -> bool:
        consultation_id = str(
            candidate.get(
                "consultation_id",
                "",
            )
            or ""
        ).strip()

        if (
            not consultation_id
            or consultation_id
            in selected_ids
        ):
            return False

        selected.append(
            _candidate_result(
                candidate
            )
        )

        selected_ids.add(
            consultation_id
        )

        source_type = str(
            candidate.get(
                "source_type",
                "",
            )
            or ""
        ).strip()

        if source_type in source_counts:
            source_counts[
                source_type
            ] += 1

        return True

    for candidate in candidates:
        source_type = str(
            candidate.get(
                "source_type",
                "",
            )
            or ""
        ).strip()

        limit = SOURCE_LIMITS.get(
            source_type
        )

        if limit is None:
            continue

        if (
            source_counts[
                source_type
            ]
            >= limit
        ):
            continue

        add_candidate(
            candidate
        )

        if len(selected) >= top_k:
            return selected

    for candidate in candidates:
        add_candidate(
            candidate
        )

        if len(selected) >= top_k:
            break

    return selected


class ConsultationRetriever:
    """Search chunks and return one result per consultation."""

    def __init__(
        self,
        embedding_service: Any | None = None,
        vector_store: Any | None = None,
    ) -> None:
        if embedding_service is None:
            embedding_service = (
                EmbeddingService()
            )

        if vector_store is None:
            vector_store = (
                ChromaVectorStore(
                    persist_directory=(
                        CHROMA_DB_DIR
                    ),
                    collection_name=(
                        LEGAL_CONSULTATIONS_COLLECTION_NAME
                    ),
                )
            )

        self.embedding_service = (
            embedding_service
        )
        self.vector_store = vector_store

    def retrieve(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        candidate_k: int = (
            DEFAULT_CANDIDATE_COUNT
        ),
    ) -> list[dict[str, Any]]:
        clean_query = str(
            query or ""
        ).strip()

        if not clean_query:
            return []

        if top_k < 1:
            raise ValueError(
                "top_k must be at least 1."
            )

        effective_candidate_count = max(
            MINIMUM_CANDIDATE_COUNT,
            top_k,
            candidate_k,
        )

        try:
            query_embedding = (
                self.embedding_service
                .embed_query(
                    clean_query
                )
            )

            candidates = (
                self.vector_store.search(
                    query_embedding=(
                        query_embedding
                    ),
                    top_k=(
                        effective_candidate_count
                    ),
                )
            )
        except Exception:
            return []

        reranked = (
            rerank_consultation_candidates(
                clean_query,
                candidates,
            )
        )

        return _select_balanced_results(
            reranked,
            top_k=top_k,
        )


@lru_cache(maxsize=1)
def get_default_consultation_retriever() -> (
    ConsultationRetriever
):
    return ConsultationRetriever()


def retrieve_consultations(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    candidate_k: int = (
        DEFAULT_CANDIDATE_COUNT
    ),
) -> list[dict[str, Any]]:
    return (
        get_default_consultation_retriever()
        .retrieve(
            query=query,
            top_k=top_k,
            candidate_k=candidate_k,
        )
    )
