"""RAG 문서를 일정 길이의 검색 청크로 분할한다."""

from __future__ import annotations

from typing import Any, Sequence


DEFAULT_CHUNK_SIZE = 800
DEFAULT_CHUNK_OVERLAP = 120


def _validate_chunk_options(
    chunk_size: int,
    chunk_overlap: int,
) -> None:
    if chunk_size < 1:
        raise ValueError(
            "chunk_size는 1 이상이어야 합니다."
        )

    if chunk_overlap < 0:
        raise ValueError(
            "chunk_overlap은 0 이상이어야 합니다."
        )

    if chunk_overlap >= chunk_size:
        raise ValueError(
            "chunk_overlap은 chunk_size보다 작아야 합니다."
        )


def _find_split_position(
    text: str,
    start: int,
    maximum_end: int,
    chunk_size: int,
) -> int:
    """가능하면 문단이나 문장 경계에서 청크를 끊는다."""
    minimum_end = start + max(
        1,
        chunk_size // 2,
    )

    separators = (
        "\n\n",
        "\n",
        ". ",
        " ",
    )

    for separator in separators:
        position = text.rfind(
            separator,
            minimum_end,
            maximum_end,
        )

        if position != -1:
            return position + len(separator)

    return maximum_end


def _build_embedding_text(
    document: dict[str, Any],
    chunk_content: str,
) -> str:
    """검색 성능을 위해 서식명과 분류를 본문 앞에 붙인다."""
    title = str(
        document.get("title", "")
    ).strip()

    case_type = str(
        document.get("case_type", "")
    ).strip()

    case_subtype = str(
        document.get("case_subtype", "")
    ).strip()

    header_parts: list[str] = []

    if title:
        header_parts.append(
            f"서식명: {title}"
        )

    if case_type or case_subtype:
        category = " > ".join(
            part
            for part in (
                case_type,
                case_subtype,
            )
            if part
        )
        header_parts.append(
            f"분류: {category}"
        )

    header_parts.append(
        chunk_content
    )

    return "\n".join(header_parts)


def chunk_document(
    document: dict[str, Any],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[dict[str, Any]]:
    """문서 하나를 여러 검색 청크로 분할한다."""
    _validate_chunk_options(
        chunk_size,
        chunk_overlap,
    )

    document_id = str(
        document.get("document_id", "")
    ).strip()

    if not document_id:
        raise ValueError(
            "document_id가 필요합니다."
        )

    content = str(
        document.get("content", "")
    ).replace(
        "\r\n",
        "\n",
    ).replace(
        "\r",
        "\n",
    ).strip()

    if not content:
        raise ValueError(
            f"{document_id} 문서의 content가 비어 있습니다."
        )

    chunks: list[dict[str, Any]] = []
    start = 0
    chunk_index = 0

    while start < len(content):
        maximum_end = min(
            start + chunk_size,
            len(content),
        )

        if maximum_end == len(content):
            end = maximum_end
        else:
            end = _find_split_position(
                text=content,
                start=start,
                maximum_end=maximum_end,
                chunk_size=chunk_size,
            )

        raw_chunk = content[start:end]
        chunk_content = raw_chunk.strip()

        trailing_whitespace_count = (
            len(raw_chunk) - len(raw_chunk.rstrip())
        )
        visible_end = end - trailing_whitespace_count

        if chunk_content:
            chunk = dict(document)

            chunk["chunk_id"] = (
                f"{document_id}::"
                f"chunk-{chunk_index:04d}"
            )
            chunk["chunk_index"] = chunk_index
            chunk["content"] = chunk_content
            chunk["embedding_text"] = (
                _build_embedding_text(
                    document,
                    chunk_content,
                )
            )

            chunks.append(chunk)
            chunk_index += 1

        if end >= len(content):
            break

        next_start = visible_end - chunk_overlap

        if next_start <= start:
            next_start = end

        start = next_start

    return chunks


def chunk_documents(
    documents: Sequence[dict[str, Any]],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[dict[str, Any]]:
    """여러 문서를 청킹하고 단일 목록으로 합친다."""
    chunks: list[dict[str, Any]] = []

    for document in documents:
        chunks.extend(
            chunk_document(
                document=document,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
        )

    return chunks

