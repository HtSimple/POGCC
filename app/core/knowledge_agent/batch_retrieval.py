"""批量知识检索：ThreadPoolExecutor + 每线程独立 LLMService / SearchAgent。"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from app.core.knowledge_agent.search_agent import SearchAgent
from app.services.llm_service import LLMService
from app.services.web_search_service import WebSearchService
from app.utils.config import config

SOURCE_MARKERS = ("来源:", "【RAG本地库】", "【网络搜索】")


def is_retrieval_error(text: str | None) -> bool:
    """判断检索返回文本是否代表失败，空结果和错误前缀都视为失败。"""
    if not text:
        return True
    if text.strip() == "暂无收集到的知识":
        return False
    return text.startswith("[") and "]" in text[:40]


def has_source_structure(text: str) -> bool:
    """检查知识文本中是否包含可追踪来源标记。"""
    return any(m in text for m in SOURCE_MARKERS)


def _retrieve_one(
    index: int,
    query: str,
    item_id: str | None,
    refine_knowledge: bool,
    retrieval_service,
) -> dict[str, Any]:
    """在线程中检索单个查询，返回统一的批量结果项。"""
    # 每个线程独立持有 LLM 和搜索 Agent，避免共享客户端状态导致并发串扰。
    llm = LLMService()
    agent = SearchAgent(
        llm_service=llm,
        web_search_service=WebSearchService(),
        retrieval_service=retrieval_service,
    )
    knowledge = agent.search(query, refine_knowledge=refine_knowledge)
    success = bool(knowledge.strip()) and not is_retrieval_error(knowledge)
    message = None if success else (knowledge[:200] if knowledge else "未返回内容")
    return {
        "index": index,
        "id": item_id,
        "success": success,
        "knowledge": knowledge or "",
        "has_sources": has_source_structure(knowledge or ""),
        "message": message,
    }


def retrieve_knowledge_batch(
    items: list[dict[str, Any]],
    refine_knowledge: bool = False,
    max_workers: int | None = None,
    retrieval_service=None,
) -> dict[str, Any]:
    """
    并行检索多页知识。

    items 每项: index, query, id(可选)
    """
    if not items:
        return {
            "success": True,
            "results": [],
            "message": "无待检索页面",
            "elapsed_sec": 0.0,
        }

    default_workers = int(config.get("knowledge_batch_max_workers", 3) or 3)
    workers = max_workers if max_workers is not None else default_workers
    workers = max(1, min(workers, len(items), 8))

    t0 = time.perf_counter()
    results: list[dict[str, Any]] = []

    # 用线程池并发处理多个页面/主题，返回后再按原始 index 排序。
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                _retrieve_one,
                int(item.get("index", i)),
                str(item["query"]),
                item.get("id"),
                refine_knowledge,
                retrieval_service,
            ): int(item.get("index", i))
            for i, item in enumerate(items)
        }
        for fut in as_completed(futures):
            results.append(fut.result())

    elapsed = time.perf_counter() - t0
    results.sort(key=lambda r: r["index"])
    ok_count = sum(1 for r in results if r["success"])

    return {
        "success": ok_count > 0,
        "results": results,
        "message": f"批量检索完成：成功 {ok_count}/{len(items)} 页",
        "elapsed_sec": round(elapsed, 2),
    }
