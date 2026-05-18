from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from app.core.generator.content_expander import ContentExpander
from app.services.llm_service import LLMService
from app.utils.config import config


def is_llm_error_content(content: str | None) -> bool:
    if not content:
        return True
    return content.startswith("[") and "]" in content[:40]


def _expand_one(
    index: int,
    outline_node: dict[str, Any],
    context: str | None,
    item_id: str | None,
) -> dict[str, Any]:
    llm = LLMService()
    expander = ContentExpander(llm_service=llm)
    expanded = expander.expand_page_content(outline_node, context=context)
    content = expanded.get("content") or ""
    success = bool(content) and not is_llm_error_content(content)
    message = expanded.get("message") if success else (content[:200] if content else "no content returned")

    return {
        "index": index,
        "id": item_id,
        "success": success,
        "content": content,
        "page_content": expanded.get("page_content"),
        "message": message,
    }


def expand_content_batch(
    items: list[dict[str, Any]],
    context: str | None = None,
    max_workers: int | None = None,
) -> dict[str, Any]:
    if not items:
        return {
            "success": True,
            "results": [],
            "message": "no content items",
            "elapsed_sec": 0.0,
        }

    default_workers = int(config.get("content_batch_max_workers", 3) or 3)
    workers = max_workers if max_workers is not None else default_workers
    workers = max(1, min(workers, len(items), 8))

    t0 = time.perf_counter()
    results: list[dict[str, Any]] = []

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                _expand_one,
                int(item.get("index", i)),
                item["outline_node"],
                item.get("context") if item.get("context") is not None else context,
                item.get("id"),
            ): int(item.get("index", i))
            for i, item in enumerate(items)
        }
        for fut in as_completed(futures):
            results.append(fut.result())

    elapsed = time.perf_counter() - t0
    results.sort(key=lambda row: row["index"])
    ok_count = sum(1 for row in results if row["success"])

    return {
        "success": ok_count > 0,
        "results": results,
        "message": f"batch content generated: {ok_count}/{len(items)}",
        "elapsed_sec": round(elapsed, 2),
    }
