"""
只测新接入的本地 RAG：入库 →（模拟）规划关键词 → 按关键词在已上传文档里检索 → 校验命中片段。
示例文档：app/rag/test_text.pdf（与 demo 里用的同类查询）。
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# 与 demo 一致：规划后用于在库里搜的关键词（这里不调用 LLM，只模拟规划结果）
PLANNED_QUERIES = ["PMLC Model", "RBS creation"]

TEST_PDF = _ROOT / "app" / "rag" / "test_text.pdf"


@pytest.fixture(scope="module")
def _st():
    pytest.importorskip("sentence_transformers")


def _embedding_model():
    from app.utils.config import config

    m = config.get("rag_embedding_model") or "app/rag/bge-small-en-v1.5"
    p = Path(m)
    return str(p if p.is_absolute() else (_ROOT / p).resolve())


def test_rag_ingest_test_text_pdf_then_search(_st):
    """入库 test_text.pdf 后，用单个关键词 search，应能返回片段。"""
    from app.rag.service import RetrievalService

    assert TEST_PDF.is_file(), f"缺少示例 PDF: {TEST_PDF}"

    with tempfile.TemporaryDirectory() as tmp:
        rs = RetrievalService(persist_dir=tmp, embedding_model=_embedding_model())
        report = rs.batch_ingest([str(TEST_PDF.resolve())])[0]
        assert report.status in ("success", "skipped")
        assert report.num_chunks >= 1

        resp = rs.search("PMLC Model", top_k=5)
        assert len(resp.results) >= 1
        blob = " ".join(r.text for r in resp.results)
        assert len(blob.strip()) > 20


def test_rag_planned_keywords_search_uploaded_pdf(_st):
    """
    模拟「规划搜索关键词」之后：对每个关键词在已入库文档里检索（与 SearchAgent 里逻辑一致），
    不跑 Tavily、不跑评估/整理/生成回答。
    """
    from app.core.knowledge_agent.search_agent import SearchAgent
    from app.rag.service import RetrievalService

    assert TEST_PDF.is_file(), f"缺少示例 PDF: {TEST_PDF}"

    with tempfile.TemporaryDirectory() as tmp:
        rs = RetrievalService(persist_dir=tmp, embedding_model=_embedding_model())
        rs.batch_ingest([str(TEST_PDF.resolve())])

        class EmptyWebSearch:
            def search(self, query, max_results=5, search_depth="advanced"):
                return []

        sa = SearchAgent(
            llm_service=MagicMock(),
            web_search_service=EmptyWebSearch(),
            retrieval_service=rs,
        )
        state = {
            "topic": "local-rag-test",
            "search_queries": list(PLANNED_QUERIES),
            "search_results": [],
            "search_round": 0,
            "collected_knowledge": "",
            "max_tokens": 4096,
        }
        out = sa._execute_search_node(state)
        merged = out["search_results"]

        local_rows = [r for r in merged if str(r.get("title", "")).startswith("[本地]")]
        assert local_rows, "应有本地库命中行"
        contents = " ".join(r.get("content", "") for r in local_rows)
        assert len(contents.strip()) > 20


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
