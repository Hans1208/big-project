"""ChromaDB 기반 로컬 벡터 저장소."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

import chromadb


STATUTE_METADATA_FIELDS: tuple[str, ...] = (
    "law_id",
    "mst",
    "law_key",
    "law_name",
    "law_type",
    "ministry",
    "effective_date",
    "promulgation_date",
    "promulgation_number",
    "article_key",
    "article_number",
    "article_branch_number",
    "article_label",
    "article_title",
    "article_effective_date",
)

PRECEDENT_METADATA_FIELDS: tuple[str, ...] = (
    "precedent_id",
    "case_name",
    "case_number",
    "decision_date",
    "decision",
    "court_name",
    "court_type_code",
    "court_level",
    "case_type_name",
    "case_type_code",
    "decision_type",
    "holding",
    "summary",
    "referenced_statutes",
    "referenced_precedents",
    "matched_searches",
    "section_type",
    "section_label",
)

SEARCH_METADATA_FIELDS = (
    STATUTE_METADATA_FIELDS
    + PRECEDENT_METADATA_FIELDS
)


def _metadata_value(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(
        value,
        (list, tuple, set),
    ):
        return " | ".join(
            str(item).strip()
            for item in value
            if str(item).strip()
        )

    return str(value)


class ChromaVectorStore:
    """직접 계산한 임베딩을 ChromaDB에 저장하고 검색한다."""

    def __init__(
        self,
        persist_directory: str | Path,
        collection_name: str,
        client: Any | None = None,
    ) -> None:
        """로컬 ChromaDB 클라이언트와 컬렉션을 준비한다.

        Args:
            persist_directory:
                ChromaDB 데이터를 저장할 로컬 폴더.
            collection_name:
                사용할 ChromaDB 컬렉션 이름.
            client:
                테스트나 외부 주입에 사용할 Chroma 클라이언트.
        """
        self.persist_directory = Path(
            persist_directory
        )
        self.collection_name = collection_name

        if client is None:
            self.persist_directory.mkdir(
                parents=True,
                exist_ok=True,
            )

            self.client = chromadb.PersistentClient(
                path=str(self.persist_directory)
            )
        else:
            self.client = client

        self.collection = (
            self.client.get_or_create_collection(
                name=self.collection_name,
                embedding_function=None,
                configuration={
                    "hnsw": {
                        "space": "cosine",
                        "batch_size": 100,
                        "sync_threshold": 100_000,
                    }
                },
            )
        )

    def count(self) -> int:
        """현재 컬렉션에 저장된 레코드 수를 반환한다."""
        return self.collection.count()

    def upsert_documents(
        self,
        documents: Sequence[dict[str, Any]],
        embeddings: Sequence[Sequence[float]],
    ) -> None:
        """문서와 임베딩을 ChromaDB에 저장하거나 갱신한다."""
        if len(documents) != len(embeddings):
            raise ValueError(
                "문서 수와 임베딩 수가 일치해야 합니다."
            )

        if not documents:
            return

        ids: list[str] = []
        contents: list[str] = []
        metadatas: list[dict[str, Any]] = []
        normalized_embeddings: list[list[float]] = []

        for index, document in enumerate(documents):
            record_id = document.get(
                "chunk_id"
            ) or document.get(
                "document_id"
            )

            if not record_id:
                raise ValueError(
                    f"{index}번째 문서에 document_id가 없습니다."
                )

            content = str(
                document.get("content", "")
            ).strip()

            if not content:
                raise ValueError(
                    f"{index}번째 문서의 content가 비어 있습니다."
                )

            document_id = str(
                document.get("document_id", record_id)
            )

            metadata: dict[str, Any] = {
                "document_id": document_id,
                "document_type": str(
                    document.get("document_type", "")
                ),
                "title": str(
                    document.get("title", "")
                ),
                "case_type": str(
                    document.get("case_type", "")
                ),
                "case_subtype": str(
                    document.get("case_subtype", "")
                ),
                "source": str(
                    document.get("source", "")
                ),
            }

            for field_name in SEARCH_METADATA_FIELDS:
                if field_name not in document:
                    continue

                field_value = document[field_name]

                metadata[field_name] = (
                    _metadata_value(field_value)
                )

            if "chunk_index" in document:
                metadata["chunk_index"] = int(
                    document["chunk_index"]
                )

            ids.append(str(record_id))
            contents.append(content)
            metadatas.append(metadata)
            normalized_embeddings.append(
                [
                    float(value)
                    for value in embeddings[index]
                ]
            )

        self.collection.upsert(
            ids=ids,
            documents=contents,
            metadatas=metadatas,
            embeddings=normalized_embeddings,
        )

    def search(
        self,
        query_embedding: Sequence[float],
        top_k: int = 3,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """질의 벡터와 유사한 문서를 검색한다."""
        if top_k < 1:
            raise ValueError(
                "top_k는 1 이상이어야 합니다."
            )

        collection_count = self.count()

        if collection_count == 0:
            return []

        query_arguments: dict[str, Any] = {
            "query_embeddings": [
                [
                    float(value)
                    for value in query_embedding
                ]
            ],
            "n_results": min(
                top_k,
                collection_count,
            ),
            "include": [
                "documents",
                "metadatas",
                "distances",
            ],
        }

        if where:
            query_arguments["where"] = where

        raw_results = self.collection.query(
            **query_arguments
        )

        ids = (raw_results.get("ids") or [[]])[0]
        documents = (
            raw_results.get("documents") or [[]]
        )[0]
        metadatas = (
            raw_results.get("metadatas") or [[]]
        )[0]
        distances = (
            raw_results.get("distances") or [[]]
        )[0]

        results: list[dict[str, Any]] = []

        for (
            record_id,
            content,
            metadata,
            distance,
        ) in zip(
            ids,
            documents,
            metadatas,
            distances,
        ):
            safe_metadata = metadata or {}
            numeric_distance = float(distance)

            results.append(
                {
                    "id": record_id,
                    "document_id": safe_metadata.get(
                        "document_id",
                        record_id,
                    ),
                    "document_type": safe_metadata.get(
                        "document_type",
                        "",
                    ),
                    "title": safe_metadata.get(
                        "title",
                        "",
                    ),
                    "case_type": safe_metadata.get(
                        "case_type",
                        "",
                    ),
                    "case_subtype": safe_metadata.get(
                        "case_subtype",
                        "",
                    ),
                    "content": content,
                    "source": safe_metadata.get(
                        "source",
                        "",
                    ),
                    "distance": numeric_distance,
                    "similarity": 1.0 - numeric_distance,
                    **{
                        field_name: safe_metadata.get(
                            field_name,
                            "",
                        )
                        for field_name
                        in SEARCH_METADATA_FIELDS
                    },
                    "metadata": safe_metadata,
                }
            )

        return results


