"""
测试「检索摘要与来源」一步（SearchAgent 快路径：规划 → 本地 RAG + 网络检索 → 拼接来源）。

与前端「补充知识」写入的 knowledge 字段格式一致（【RAG本地库】/【网络搜索】+ 来源行）。
POST /api/search/knowledge 与批量 /api/search/knowledge/batch 均走 SearchAgent 快路径（检索+来源拼接）。

在项目根目录执行：
    python tests/test_knowledge_retrieval.py
    python tests/test_knowledge_retrieval.py deepseek
    python tests/test_knowledge_retrieval.py --full      # 含评估+整理 LLM
    python tests/test_knowledge_retrieval.py deepseek --compare # 多页串行 vs 批量并行耗时

或：
    pytest tests/test_knowledge_retrieval.py -v -s
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.core.knowledge_agent.batch_retrieval import retrieve_knowledge_batch
from app.core.knowledge_agent.search_agent import SearchAgent
from app.services.llm_service import LLMService
from app.services.web_search_service import WebSearchService

# 与前端 fillKnowledge 拼 query 方式一致
SAMPLE_SLIDE_QUERY = "\n".join(
    [
        "人工智能在教育中的应用",
        "概述",
        "背景介绍",
        "背景介绍",
    ]
)

DEFAULT_PROVIDER: str | None = None
SOURCE_MARKERS = ("来源:", "【RAG本地库】", "【网络搜索】")


def build_slide_query(
    topic: str,
    section_title: str,
    title: str,
    bullets: list[str] | None = None,
) -> str:
    """复现 App.vue fillKnowledge 中的 query 拼接。"""
    lines = [topic, section_title, title, *(bullets or [])]
    return "\n".join(line for line in lines if line)


def is_llm_error_text(text: str | None) -> bool:
    if not text:
        return True
    return text.startswith("[") and "]" in text[:40]


def has_source_structure(text: str) -> bool:
    return any(marker in text for marker in SOURCE_MARKERS)


def _try_load_retrieval_service():
    try:
        from app.rag.service import RetrievalService
        from app.utils.config import config

        persist_dir = config.get("rag_persist_dir") or "app/rag/data_index"
        embedding_model = config.get("rag_embedding_model") or "app/rag/bge-small-en-v1.5"
        return RetrievalService(
            persist_dir=persist_dir,
            embedding_model=embedding_model,
        )
    except Exception as exc:
        print(f"[跳过本地 RAG] {exc}")
        return None


def run_knowledge_retrieval(
    query: str = SAMPLE_SLIDE_QUERY,
    provider: str | None = None,
    refine_knowledge: bool = False,
    retrieval_service=None,
) -> dict[str, Any]:
    llm = LLMService()
    use = provider if provider is not None else DEFAULT_PROVIDER
    if use is not None:
        llm.switch_provider(use)

    if retrieval_service is None:
        retrieval_service = _try_load_retrieval_service()

    agent = SearchAgent(
        llm_service=llm,
        web_search_service=WebSearchService(),
        retrieval_service=retrieval_service,
    )

    mode = "完整整理" if refine_knowledge else "快路径（检索+来源拼接）"
    print(f"\n查询:\n{query}\n")
    print(f"模式: {mode} | provider: {llm.provider_name} | 本地RAG: {'有' if retrieval_service else '无'}")

    t0 = time.perf_counter()
    knowledge = agent.search(query, refine_knowledge=refine_knowledge)
    elapsed = time.perf_counter() - t0

    ok = bool(knowledge.strip()) and not is_llm_error_text(knowledge)
    has_sources = has_source_structure(knowledge)
    n_blocks = knowledge.count("\n[") + (1 if knowledge.strip().startswith("[") else 0)

    return {
        "query": query,
        "provider": llm.provider_name,
        "refine_knowledge": refine_knowledge,
        "elapsed_sec": elapsed,
        "ok": ok,
        "has_sources": has_sources,
        "char_len": len(knowledge),
        "n_result_blocks": n_blocks,
        "knowledge_preview": knowledge[:800],
        "knowledge": knowledge,
    }


def print_retrieval_report(report: dict[str, Any]) -> None:
    print(f"\n{'=' * 56}")
    print("检索摘要与来源 — 耗时与结构检查")
    print(f"{'=' * 56}")
    print(f"模型:           {report['provider']}")
    print(f"模式:           {'完整整理' if report['refine_knowledge'] else '快路径'}")
    print(f"耗时:           {report['elapsed_sec']:.2f} 秒")
    print(f"成功:           {report['ok']}")
    print(f"含来源结构:     {report['has_sources']}")
    print(f"字符数:         {report['char_len']}")
    print(f"结果块约计:     {report['n_result_blocks']}")
    print(f"{'=' * 56}")
    print("预览（前 800 字）:")
    print(report["knowledge_preview"])
    if report["char_len"] > 800:
        print("...")
    print(f"{'=' * 56}\n")


SAMPLE_QUERIES = [
    build_slide_query("人工智能在教育中的应用", "概述", "背景介绍", ["背景介绍"]),
    build_slide_query("人工智能在教育中的应用", "概述", "研究意义", ["研究意义"]),
    build_slide_query("人工智能在教育中的应用", "主要内容", "核心概念", ["核心概念"]),
]


def run_batch_serial(queries: list[str], retrieval_service=None) -> dict[str, Any]:
    t0 = time.perf_counter()
    results = []
    for i, q in enumerate(queries):
        report = run_knowledge_retrieval(query=q, retrieval_service=retrieval_service)
        results.append({"index": i, "ok": report["ok"], "elapsed_sec": report["elapsed_sec"]})
    return {
        "mode": "serial",
        "elapsed_sec": time.perf_counter() - t0,
        "ok_count": sum(1 for r in results if r["ok"]),
        "pages": results,
    }


def run_batch_parallel(
    queries: list[str],
    max_workers: int = 3,
    retrieval_service=None,
) -> dict[str, Any]:
    items = [{"index": i, "query": q} for i, q in enumerate(queries)]
    report = retrieve_knowledge_batch(items, max_workers=max_workers, retrieval_service=retrieval_service)
    return {
        "mode": "parallel",
        "elapsed_sec": report["elapsed_sec"],
        "ok_count": sum(1 for r in report["results"] if r["success"]),
        "pages": report["results"],
    }


def test_knowledge_retrieval_fast_path():
    """集成测试：快路径检索，检查返回非空且带来源标记。"""
    report = run_knowledge_retrieval(refine_knowledge=False)
    print_retrieval_report(report)
    assert report["elapsed_sec"] > 0
    assert report["ok"], f"检索失败或 LLM 报错: {report['knowledge_preview'][:200]}"
    assert report["has_sources"], "输出中未找到「来源」或【RAG本地库】/【网络搜索】标记"


def main() -> None:
    refine = "--full" in sys.argv
    compare = "--compare" in sys.argv
    provider: str | None = None
    query = SAMPLE_SLIDE_QUERY
    for arg in sys.argv[1:]:
        if arg in ("--full", "--compare"):
            continue
        if arg in LLMService.VALID_PROVIDERS:
            provider = arg
        else:
            query = arg

    if provider:
        llm = LLMService()
        llm.switch_provider(provider)

    retrieval_service = _try_load_retrieval_service()

    if compare:
        print(f"\n对比 {len(SAMPLE_QUERIES)} 页：串行 vs 批量并行\n")
        serial = run_batch_serial(SAMPLE_QUERIES, retrieval_service=retrieval_service)
        parallel = run_batch_parallel(SAMPLE_QUERIES, retrieval_service=retrieval_service)
        speedup = serial["elapsed_sec"] / parallel["elapsed_sec"] if parallel["elapsed_sec"] else 0
        print(f"串行总耗时: {serial['elapsed_sec']:.2f}s (成功 {serial['ok_count']})")
        print(f"并行总耗时: {parallel['elapsed_sec']:.2f}s (成功 {parallel['ok_count']})")
        print(f"加速比: {speedup:.2f}x\n")
        return

    report = run_knowledge_retrieval(
        query=query,
        provider=provider,
        refine_knowledge=refine,
        retrieval_service=retrieval_service,
    )
    print_retrieval_report(report)
    if not report["ok"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
