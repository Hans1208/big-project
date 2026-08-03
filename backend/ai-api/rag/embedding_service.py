"""로컬 Sentence Transformer 기반 임베딩 서비스."""

from __future__ import annotations

from typing import Any, Sequence

from sentence_transformers import SentenceTransformer

from rag.config import EMBEDDING_MODEL_NAME


class EmbeddingService:
    """E5 모델로 문서와 검색 질의를 임베딩한다.

    모델은 실제 임베딩이 처음 요청될 때 로딩한다.
    테스트에서는 model 인자로 가짜 모델을 주입할 수 있다.
    """

    def __init__(
        self,
        model_name: str = EMBEDDING_MODEL_NAME,
        model: Any | None = None,
    ) -> None:
        self.model_name = model_name
        self._model = model

    def _get_model(self) -> Any:
        """Sentence Transformer 모델을 한 번만 로딩한다."""
        if self._model is None:
            self._model = SentenceTransformer(
                self.model_name
            )

        return self._model

    def embed_documents(
        self,
        texts: Sequence[str],
    ) -> list[list[float]]:
        """검색 대상 문서들을 passage 임베딩으로 변환한다."""
        prefixed_texts = [
            f"passage: {text.strip()}"
            for text in texts
        ]

        if not prefixed_texts:
            return []

        vectors = self._get_model().encode(
            prefixed_texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

        return vectors.tolist()

    def embed_query(
        self,
        text: str,
    ) -> list[float]:
        """사용자 검색문 하나를 query 임베딩으로 변환한다."""
        prefixed_text = f"query: {text.strip()}"

        vectors = self._get_model().encode(
            [prefixed_text],
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

        return vectors[0].tolist()
