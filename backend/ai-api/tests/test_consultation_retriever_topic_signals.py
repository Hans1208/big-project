from __future__ import annotations

import pytest

from rag.consultation_retriever import (
    rerank_consultation_candidates,
)


def _candidate(
    consultation_id,
    *,
    question,
    answer,
    legal_path,
    service_category,
    similarity,
):
    return {
        "id": (
            f"{consultation_id}"
            "::chunk-0000"
        ),
        "consultation_id": (
            consultation_id
        ),
        "source_type": "case",
        "service_category": (
            service_category
        ),
        "question": question,
        "answer": answer,
        "legal_path": legal_path,
        "source_file": "test.csv",
        "source_row": "2",
        "source_date": "2024-07-31",
        "content": answer,
        "similarity": similarity,
    }


@pytest.mark.parametrize(
    (
        "query",
        "generic_candidate",
        "specific_candidate",
        "expected_id",
    ),
    (
        (
            (
                "\uc774\ud63c \ud6c4 "
                "\uc0c1\ub300\ubc29\uc774 "
                "\uc544\uc774\ub97c \ubcf4\uc9c0 "
                "\ubabb\ud558\uac8c \ud569\ub2c8\ub2e4."
            ),
            _candidate(
                "generic-divorce",
                question=(
                    "\uc774\ud63c \uc808\ucc28\uc640 "
                    "\uc2e0\uace0 \ubc29\ubc95"
                ),
                answer=(
                    "\uc7ac\ud310\uc0c1 \uc774\ud63c "
                    "\uc808\ucc28\ub97c "
                    "\uc548\ub0b4\ud569\ub2c8\ub2e4."
                ),
                legal_path=(
                    "\uce5c\uc871>\uc774\ud63c>"
                    "\uc7ac\ud310\uc0c1\uc774\ud63c"
                ),
                service_category=(
                    "family_litigation"
                ),
                similarity=0.93,
            ),
            _candidate(
                "specific-visitation",
                question=(
                    "\ube44\uc591\uc721 \ubd80\ubaa8\uc758 "
                    "\uba74\uc811\uad50\uc12d\uad8c "
                    "\ud589\uc0ac"
                ),
                answer=(
                    "\uba74\uc811\uad50\uc12d\uc744 "
                    "\uccad\uad6c\ud560 \uc218 "
                    "\uc788\uc2b5\ub2c8\ub2e4."
                ),
                legal_path=(
                    "\uce5c\uc871>"
                    "\uc591\uc721\uad8c\uc790\uc591\uc721\ube44"
                    "\uba74\uc811\uad50\uc12d\uad8c\ub4f1>"
                    "\uba74\uc811\uad50\uc12d\uad8c"
                ),
                service_category=(
                    "family_litigation"
                ),
                similarity=0.75,
            ),
            "specific-visitation",
        ),
        (
            (
                "\ubd80\ubaa8\ub2d8\uc774 "
                "\ube5a\uc744 \ub0a8\uae30\uace0 "
                "\ub3cc\uc544\uac00\uc154\uc11c "
                "\uc0c1\uc18d\uc7ac\uc0b0\uc744 "
                "\ubc1b\uc9c0 \uc54a\uc73c\ub824 "
                "\ud569\ub2c8\ub2e4."
            ),
            _candidate(
                "generic-inheritance",
                question=(
                    "\ubc95\uc815\uc0c1\uc18d\ubd84\uc744 "
                    "\uacc4\uc0b0\ud558\ub294 \ubc29\ubc95"
                ),
                answer=(
                    "\uc0c1\uc18d\uc778\ubcc4 "
                    "\uc0c1\uc18d\ubd84\uc744 "
                    "\uacc4\uc0b0\ud569\ub2c8\ub2e4."
                ),
                legal_path=(
                    "\uc0c1\uc18d\uacfc\uc720\uc5b8>"
                    "\uc0c1\uc18d\uc77c\ubc18>"
                    "\uc0c1\uc18d\ubd84"
                ),
                service_category=(
                    "inheritance"
                ),
                similarity=0.91,
            ),
            _candidate(
                "specific-renunciation",
                question=(
                    "\uc0c1\uc18d\ucc44\ubb34\ub85c "
                    "\uc0c1\uc18d\uc744 "
                    "\ud3ec\uae30\ud558\uace0 "
                    "\uc2f6\uc2b5\ub2c8\ub2e4."
                ),
                answer=(
                    "\uc0c1\uc18d\ud3ec\uae30 \ub610\ub294 "
                    "\ud55c\uc815\uc2b9\uc778\uc744 "
                    "\uac80\ud1a0\ud569\ub2c8\ub2e4."
                ),
                legal_path=(
                    "\uc0c1\uc18d\uacfc\uc720\uc5b8>"
                    "\uc0c1\uc18d\uc77c\ubc18>"
                    "\uc0c1\uc18d\ud3ec\uae30"
                ),
                service_category=(
                    "inheritance"
                ),
                similarity=0.80,
            ),
            "specific-renunciation",
        ),
        (
            (
                "\uce58\ub9e4\uac00 \uc2ec\ud55c "
                "\ubd80\ubaa8\ub2d8\uc744 \uc704\ud574 "
                "\ud6c4\uacac\uc744 "
                "\uc2e0\uccad\ud558\uace0 "
                "\uc2f6\uc2b5\ub2c8\ub2e4."
            ),
            _candidate(
                "generic-minor-guardianship",
                question=(
                    "\ubbf8\uc131\ub144\ud6c4\uacac\uc778\uc758 "
                    "\uc7ac\uc0b0 \uad00\ub9ac"
                ),
                answer=(
                    "\ubbf8\uc131\ub144\ud6c4\uacac\uc778\uc758 "
                    "\uad8c\ud55c\uc744 "
                    "\uc548\ub0b4\ud569\ub2c8\ub2e4."
                ),
                legal_path=(
                    "\uce5c\uc871>\uae30\ud0c0\uce5c\uc871>"
                    "\ud6c4\uacac\uc0ac\uac74>"
                    "\ubbf8\uc131\ub144\ud6c4\uacac"
                ),
                service_category="kinship",
                similarity=0.92,
            ),
            _candidate(
                "specific-adult-guardianship",
                question=(
                    "\uce58\ub9e4 \ud658\uc790\uc758 "
                    "\uc131\ub144\ud6c4\uacac "
                    "\uac1c\uc2dc \uc2e0\uccad"
                ),
                answer=(
                    "\uc131\ub144\ud6c4\uacac "
                    "\uac1c\uc2dc\uc2ec\ud310\uc744 "
                    "\uccad\uad6c\ud569\ub2c8\ub2e4."
                ),
                legal_path=(
                    "\uce5c\uc871>\uae30\ud0c0\uce5c\uc871>"
                    "\ud6c4\uacac\uc0ac\uac74>"
                    "\uc131\ub144\ud6c4\uacac"
                ),
                service_category="kinship",
                similarity=0.78,
            ),
            "specific-adult-guardianship",
        ),
    ),
)
def test_topic_signals_promote_specific_subtopics(
    query,
    generic_candidate,
    specific_candidate,
    expected_id,
):
    reranked = (
        rerank_consultation_candidates(
            query,
            [
                generic_candidate,
                specific_candidate,
            ],
        )
    )

    assert reranked[0][
        "consultation_id"
    ] == expected_id
