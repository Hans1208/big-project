"""검색 결과 한 장에 대응하는 '문서 전체'를 되살린다.

색인은 조문·판례를 청크로 쪼개 담는다. 검색은 질의와 가까운 청크 하나만
돌려주므로, 화면 카드에 실리는 본문은 그 문서의 한 조각이다.

실측 두 건:

  · 가사소송법 제2조(가정법원의 관장 사항) - 797자에서 끊겨,
    "5) 「민법」 제909조제4항 및 제6항(...)에" 로 문장 중간에서 멈춘다.
  · 판례 2022느단5199 - chunk-0002만 걸려 본문이 "비율에 따라"로 시작한다.
    끝은 "판사 남성우"로 제대로 끝나서, 전체를 다 본 것처럼 읽힌다.

앞뒤가 잘렸다는 표시가 화면 어디에도 없다. 변호사가 이걸 근거로 담으면
판단의 전제가 된 부분을 못 본 채 담게 된다.

여기서는 청크 id로부터 문서 id를 되짚어, 그 문서의 청크를 순서대로 모아
하나로 잇는다. 유사도가 아니라 document_id 일치로 가져오므로 다른 사건의
본문이 섞일 수 없다.
"""

from typing import Any

# 청크 id는 chunking.py가 "{document_id}::chunk-0000" 꼴로 만든다.
CHUNK_ID_SEPARATOR = "::chunk-"


def to_document_id(chunk_id: str) -> str:
    """청크 id에서 문서 id를 떼어낸다.

    이미 문서 id면 그대로 돌려준다 - 청크가 하나뿐이라 쪼개지지 않은 문서는
    청크 id 없이 문서 id가 그대로 레코드 id가 된다(vector_store.upsert 참고).
    """
    value = (chunk_id or "").strip()

    if not value:
        return ""

    head, separator, _ = value.partition(CHUNK_ID_SEPARATOR)

    return head if separator else value


def _join_chunks(chunks: list[dict[str, Any]]) -> str:
    """청크 본문을 원래 순서대로 잇는다.

    청크를 자를 때 겹치는 부분(chunk_overlap)을 두므로, 앞 조각의 끝과 뒤
    조각의 앞이 겹칠 수 있다. 겹친 만큼을 걷어내고 붙인다 - 안 그러면 같은
    문단이 두 번 나와서, 읽는 사람은 판결이 같은 말을 반복한 것으로 읽는다.
    """
    joined = ""

    for chunk in chunks:
        content = (chunk.get("content") or "").strip()

        if not content:
            continue

        if not joined:
            joined = content
            continue

        # 겹침은 chunk_overlap(기본 100자) 안쪽이다. 넉넉히 400자까지 보되
        # 긴 겹침부터 찾아야 짧은 우연의 일치로 본문을 깎지 않는다.
        overlap = 0
        maximum = min(len(joined), len(content), 400)

        for size in range(maximum, 20, -1):
            if joined[-size:] == content[:size]:
                overlap = size
                break

        joined = f"{joined}\n{content[overlap:].lstrip()}"

    return joined.strip()


def build_full_text(store: Any, chunk_id: str) -> dict[str, Any]:
    """청크 id로 그 문서의 전체 본문을 만든다.

    돌려주는 chunk_count/truncated로 화면이 '조각 하나였는지'를 알 수 있다.
    """
    document_id = to_document_id(chunk_id)

    if not document_id:
        raise ValueError("chunk_id가 필요합니다.")

    chunks = store.fetch_document_chunks(document_id)

    if not chunks:
        return {
            "document_id": document_id,
            "content": "",
            "chunk_count": 0,
            "found": False,
        }

    metadata = chunks[0].get("metadata") or {}

    return {
        "document_id": document_id,
        "title": metadata.get("title") or "",
        "source": metadata.get("source") or "",
        "content": _join_chunks(chunks),
        "chunk_count": len(chunks),
        "found": True,
    }
