import pytest

from app.retrieval.fts import PostgresFTSRetriever


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows


class _FakeSession:
    async def execute(self, statement, params=None):
        _ = (statement, params)
        return _FakeResult(
            [
                {
                    "id": "chunk-1",
                    "source_id": "source-1",
                    "doc_path": "tax-law/vat-basics.md",
                    "title": "VAT Basics",
                    "section_ref": "Input tax credits",
                    "page_ref": None,
                    "chunk_text": "Input VAT can be credited when supported by valid invoices.",
                    "rank": 0.82,
                }
            ]
        )


@pytest.mark.asyncio
async def test_fts_retrieval_returns_expected_chunk():
    retriever = PostgresFTSRetriever()
    rows = await retriever.retrieve(_FakeSession(), query="input vat invoice", top_k=3)
    assert len(rows) == 1
    assert rows[0].title == "VAT Basics"
    assert "credited" in rows[0].chunk_text
