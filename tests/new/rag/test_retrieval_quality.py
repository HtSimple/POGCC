from __future__ import annotations

import sys
from pathlib import Path

import pytest

CURRENT = Path(__file__).resolve()
TESTING_DIR = CURRENT.parents[1]
if str(TESTING_DIR) not in sys.path:
    sys.path.insert(0, str(TESTING_DIR))

from _test_utils import add_project_root_to_path

ROOT = add_project_root_to_path(CURRENT)


@pytest.mark.rag
def test_retrieval_service_ingest_and_search_txt(tmp_path: Path):
    """
    RAG recall smoke test.

    This requires the embedding model path configured in the repository.
    If the local embedding model is not available, the test is skipped rather than failed.
    """
    from app.rag.service import RetrievalService

    doc = tmp_path / "rag_sample.txt"
    doc.write_text(
        "项目章程要求系统支持结构化PPT大纲、页面内容补全、演讲备注生成。"
        "同时，系统需要通过RAG降低事实幻觉，并进行事实准确率评测。"
        "性能目标是万字长文档端到端处理时间不超过五分钟。",
        encoding="utf-8",
    )

    persist_dir = tmp_path / "index"

    try:
        service = RetrievalService(persist_dir=str(persist_dir))
    except Exception as exc:
        pytest.skip(f"RetrievalService cannot start, probably missing embedding model: {exc}")

    report = service.ingest(str(doc))
    assert report.status in {"success", "skipped"}
    assert report.num_chunks >= 1

    resp = service.search("系统如何降低事实幻觉？", top_k=3)
    assert resp.results
    joined = "\n".join(item.text for item in resp.results)
    assert "RAG" in joined or "事实" in joined or "幻觉" in joined


@pytest.mark.rag
def test_retrieval_service_duplicate_ingest_skips(tmp_path: Path):
    from app.rag.service import RetrievalService

    doc = tmp_path / "dup_sample.txt"
    doc.write_text("重复入库测试：同一个文件不应该重复写入向量库。", encoding="utf-8")
    try:
        service = RetrievalService(persist_dir=str(tmp_path / "index"))
    except Exception as exc:
        pytest.skip(f"RetrievalService cannot start: {exc}")

    first = service.ingest(str(doc))
    second = service.ingest(str(doc))
    assert first.status in {"success", "skipped"}
    assert second.status == "skipped"
