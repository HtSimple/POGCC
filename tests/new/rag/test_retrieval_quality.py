from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest

CURRENT = Path(__file__).resolve()
RAG_DIR = CURRENT.parent
FIXTURES_DIR = RAG_DIR / "fixtures"
TESTING_DIR = RAG_DIR.parent
CORPUS_PATH = FIXTURES_DIR / "rag_corpus.txt"

if str(TESTING_DIR) not in sys.path:
    sys.path.insert(0, str(TESTING_DIR))

from _test_utils import add_project_root_to_path  # noqa: E402
from conftest import embedding_model_path  # noqa: E402
from rag_metrics import (  # noqa: E402
    build_quality_summary,
    set_rag_quality_summary,
)

add_project_root_to_path(CURRENT)

MIN_TOP_K_HIT_RATE = 0.85


def _joined_result_text(results) -> str:
    return "\n".join(item.text or "" for item in results)


def _build_reference_context(results) -> str:
    """Mirror generator._build_outline_reference_context block format (content only)."""
    blocks: List[str] = []
    for index, item in enumerate(results, start=1):
        text = (item.text or "").strip()
        if len(text) > 1200:
            text = text[:1200] + "..."
        if text:
            blocks.append(f"[参考资料 {index}]\n{text}")
    return "\n\n".join(blocks)


def _corpus_chunk_count(service) -> int:
    docs = service.list_documents()
    corpus_docs = [d for d in docs if d.get("file_name") == CORPUS_PATH.name]
    return int(corpus_docs[0].get("num_chunks", 0)) if corpus_docs else 0


@pytest.mark.rag
def test_retrieval_service_ingest_and_search_txt(tmp_path: Path):
    pytest.importorskip("sentence_transformers")
    from app.rag.service import RetrievalService

    doc = tmp_path / "rag_sample.txt"
    doc.write_text(
        "项目章程要求系统支持结构化PPT大纲、页面内容补全、演讲备注生成。"
        "同时，系统需要通过RAG降低事实幻觉，并进行事实准确率评测。"
        "性能目标是万字长文档端到端处理时间不超过五分钟。",
        encoding="utf-8",
    )

    try:
        service = RetrievalService(
            persist_dir=str(tmp_path / "index"),
            embedding_model=embedding_model_path(),
        )
    except Exception as exc:
        pytest.skip(f"RetrievalService cannot start, probably missing embedding model: {exc}")

    report = service.ingest(str(doc))
    assert report.status in {"success", "skipped"}
    assert report.num_chunks >= 1

    resp = service.search("系统如何降低事实幻觉？", top_k=3)
    assert resp.results
    joined = _joined_result_text(resp.results)
    assert "RAG" in joined or "事实" in joined or "幻觉" in joined


@pytest.mark.rag
def test_retrieval_service_duplicate_ingest_skips(tmp_path: Path):
    pytest.importorskip("sentence_transformers")
    from app.rag.service import RetrievalService

    doc = tmp_path / "dup_sample.txt"
    doc.write_text("重复入库测试：同一个文件不应该重复写入向量库。", encoding="utf-8")
    try:
        service = RetrievalService(
            persist_dir=str(tmp_path / "index"),
            embedding_model=embedding_model_path(),
        )
    except Exception as exc:
        pytest.skip(f"RetrievalService cannot start: {exc}")

    first = service.ingest(str(doc))
    second = service.ingest(str(doc))
    assert first.status in {"success", "skipped"}
    assert second.status == "skipped"


@pytest.mark.rag
def test_fixture_corpus_top_k_hit_rate(ingested_corpus, rag_query_cases: List[Dict[str, Any]]):
    assert len(rag_query_cases) >= 30, "rag_queries.json should contain at least 30 cases"
    ingest_report = getattr(ingested_corpus, "_ingest_report", None)
    summary = build_quality_summary(
        ingested_corpus,
        rag_query_cases,
        CORPUS_PATH,
        embedding_model=embedding_model_path(),
        ingest_status=getattr(ingest_report, "status", "unknown"),
        num_chunks=_corpus_chunk_count(ingested_corpus),
        min_hit_rate=MIN_TOP_K_HIT_RATE,
    )
    set_rag_quality_summary(summary)

    assert summary.hit_rate >= MIN_TOP_K_HIT_RATE, (
        f"Top-K hit rate {summary.hit_rate:.2%} below threshold {MIN_TOP_K_HIT_RATE:.0%} "
        f"({summary.hit_count}/{summary.case_count} cases passed)"
    )


@pytest.mark.rag
def test_retrieval_results_include_source_metadata(ingested_corpus):
    resp = ingested_corpus.search("RAG 检索来源字段", top_k=3)
    assert resp.results, "Expected non-empty retrieval results"

    for item in resp.results:
        assert item.source_file, "Each chunk should expose source_file"
        assert item.chunk_id, "Each chunk should expose chunk_id"
        assert item.text.strip(), "Each chunk should include text"
        assert item.score is not None


@pytest.mark.rag
def test_corpus_splits_into_multiple_chunks(tmp_path: Path):
    """Verify DocumentProcessor splits long txt; fixture corpus may stay as one chunk if under max_chars."""
    from app.rag.document_processor import DocumentProcessor, ProcessorConfig

    doc = tmp_path / "long_split.txt"
    doc.write_text(
        "第一部分：" + "结构化PPT大纲与RAG检索质量验证。" * 40 + "\n\n"
        "第二部分：" + "演讲备注生成与Markdown导出测试语料。" * 40,
        encoding="utf-8",
    )
    processor = DocumentProcessor(ProcessorConfig(max_chars=500, min_chunk_chars=80))
    _, chunks = processor.process_file(str(doc))
    assert len(chunks) >= 2, f"Expected >=2 chunks, got {len(chunks)}"


@pytest.mark.rag
def test_reference_context_contains_corpus_evidence(ingested_corpus):
    query = "\n".join(
        [
            "POGCC PPT 大纲智能生成",
            "生成5页课程汇报PPT，包含 RAG、JSON Schema、质量验证。",
        ]
    )
    resp = ingested_corpus.search(query=query, top_k=5)
    assert resp.results

    context = _build_reference_context(resp.results)
    assert "[参考资料 1]" in context
    assert any(keyword in context for keyword in ("RAG", "JSON", "Schema", "大纲"))


@pytest.mark.rag
def test_update_file_refreshes_index_content(rag_service, tmp_path: Path):
    doc = tmp_path / "versioned.txt"
    doc.write_text("第一版内容：系统不支持 RAG 检索。", encoding="utf-8")

    first = rag_service.ingest(str(doc))
    assert first.status == "success"

    doc.write_text("第二版内容：系统已支持 RAG 检索与事实幻觉控制。", encoding="utf-8")
    updated = rag_service.update_file(str(doc))
    assert updated.status == "success"

    resp = rag_service.search("RAG 检索", top_k=3)
    joined = _joined_result_text(resp.results)
    assert "第二版" in joined or "事实幻觉控制" in joined
    assert "不支持 RAG" not in joined
