from rag.build_precedent_index import (
    build_precedent_index,
)
from rag.precedent_api import PrecedentSearchPage
from rag.precedent_collector import (
    PrecedentSearchJob,
)


class FakeApiClient:
    def search_precedents(self, **kwargs):
        return PrecedentSearchPage(
            total_count=1,
            page=1,
            items=[
                {
                    "precedent_id": "300001",
                    "case_name": "재산분할 등",
                    "case_number": "2023드합12345",
                    "decision_date": "20240115",
                    "court_name": "서울가정법원",
                    "court_type_code": "400202",
                    "case_type_name": "가사",
                    "case_type_code": "400106",
                    "decision_type": "판결",
                    "decision": "선고",
                    "data_source_name": "대법원",
                    "detail_link": "",
                }
            ],
        )

    def get_precedent(self, precedent_id):
        assert precedent_id == "300001"

        return {
            "PrecService": {
                "판례정보일련번호": "300001",
                "사건명": "재산분할 등",
                "사건번호": "2023드합12345",
                "선고일자": "20240115",
                "법원명": "서울가정법원",
                "법원종류코드": "400202",
                "사건종류명": "가사",
                "판시사항": "재산분할 대상의 판단",
                "판결요지": (
                    "혼인 중 형성한 재산을 분할한다."
                ),
                "판례내용": (
                    "원고와 피고가 함께 재산을 형성하였다."
                ),
                "참조조문": "민법 제839조의2",
            }
        }


class FakeEmbeddingService:
    def __init__(self):
        self.texts = []

    def embed_documents(self, texts):
        self.texts.extend(texts)

        return [
            [1.0, 0.0]
            for _ in texts
        ]


class FakeVectorStore:
    def __init__(self):
        self.documents = []
        self.embeddings = []

    def upsert_documents(
        self,
        documents,
        embeddings,
    ):
        self.documents.extend(documents)
        self.embeddings.extend(embeddings)

    def count(self):
        return len(self.documents)


def test_build_precedent_index_collects_and_stores():
    embedding_service = FakeEmbeddingService()
    vector_store = FakeVectorStore()

    result = build_precedent_index(
        jobs=[
            PrecedentSearchJob(
                query="재산분할",
                search_scope=1,
                court_type_code="400202",
                referenced_law="",
                label="test:lower",
            )
        ],
        decision_date_from="20160101",
        decision_date_to="20260804",
        display=10,
        batch_size=2,
        api_client=FakeApiClient(),
        embedding_service=embedding_service,
        vector_store=vector_store,
    )

    assert result == {
        "jobs": 1,
        "summaries": 1,
        "precedents": 1,
        "failed": 0,
        "chunks": 3,
        "stored": 3,
    }

    assert len(vector_store.documents) == 3
    assert len(vector_store.embeddings) == 3

    assert {
        document["section_type"]
        for document in vector_store.documents
    } == {
        "holding",
        "summary",
        "full_text",
    }

    assert all(
        text
        for text in embedding_service.texts
    )