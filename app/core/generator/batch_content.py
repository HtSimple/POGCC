from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from app.core.generator.content_expander import ContentExpander
from app.services.api_cost_service import ApiQuotaExceeded
from app.services.llm_service import LLMService
from app.utils.config import config

logger = logging.getLogger(__name__)

_RETRY_ATTEMPTS = 2
_RETRY_BACKOFF_SEC = 1.5


def is_llm_error_content(content: str | None) -> bool:
    if not content:
        return True
    return content.startswith("[") and "]" in content[:40]


def _result_from_expanded(
    index: int,
    item_id: str | None,
    expanded: dict[str, Any],
) -> dict[str, Any]:
    content = expanded.get("content") or ""
    page_content = expanded.get("page_content")
    success = page_content is not None and bool(content) and not is_llm_error_content(content)
    message = (
        expanded.get("message")
        if success
        else (expanded.get("message") or content[:200] if content else "no content returned")
    )
    return {
        "index": index,
        "id": item_id,
        "success": success,
        "content": content,
        "page_content": expanded.get("page_content"),
        "message": message,
    }


def _expand_one(
    index: int,
    outline_node: dict[str, Any],
    context: str | None,
    item_id: str | None,
    llm_service: LLMService | None = None,
) -> dict[str, Any]:
    llm = llm_service or LLMService()
    expander = ContentExpander(llm_service=llm)
    last_result: dict[str, Any] | None = None

    for attempt in range(_RETRY_ATTEMPTS + 1):
        try:
            expanded = expander.expand_page_content(outline_node, context=context)
            result = _result_from_expanded(index, item_id, expanded)
            last_result = result
            if result["success"]:
                return result

            if attempt < _RETRY_ATTEMPTS:
                wait = _RETRY_BACKOFF_SEC * (attempt + 1)
                logger.warning(
                    "batch content attempt %s/%s failed for index=%s id=%s: %s; retry in %.1fs",
                    attempt + 1,
                    _RETRY_ATTEMPTS + 1,
                    index,
                    item_id,
                    result.get("message"),
                    wait,
                )
                time.sleep(wait)
        except ApiQuotaExceeded as exc:
            return {
                "index": index,
                "id": item_id,
                "success": False,
                "content": "",
                "page_content": None,
                "message": str(exc),
                "quota_exceeded": True,
            }
        except Exception as exc:
            last_result = {
                "index": index,
                "id": item_id,
                "success": False,
                "content": "",
                "page_content": None,
                "message": str(exc),
            }
            if attempt < _RETRY_ATTEMPTS:
                wait = _RETRY_BACKOFF_SEC * (attempt + 1)
                logger.warning(
                    "batch content attempt %s/%s raised for index=%s id=%s: %s; retry in %.1fs",
                    attempt + 1,
                    _RETRY_ATTEMPTS + 1,
                    index,
                    item_id,
                    exc,
                    wait,
                )
                time.sleep(wait)

    return last_result or {
        "index": index,
        "id": item_id,
        "success": False,
        "content": "",
        "page_content": None,
        "message": "no content returned",
    }


def _run_batch(
    items: list[dict[str, Any]],
    context: str | None,
    max_workers: int,
    llm_service: LLMService | None,
) -> list[dict[str, Any]]:
    if max_workers <= 1 or len(items) <= 1:
        return [
            _expand_one(
                int(item.get("index", i)),
                item["outline_node"],
                item.get("context") if item.get("context") is not None else context,
                item.get("id"),
                llm_service,
            )
            for i, item in enumerate(items)
        ]

    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                _expand_one,
                int(item.get("index", i)),
                item["outline_node"],
                item.get("context") if item.get("context") is not None else context,
                item.get("id"),
                llm_service,
            ): int(item.get("index", i))
            for i, item in enumerate(items)
        }
        for fut in as_completed(futures):
            results.append(fut.result())
    return results


def expand_content_batch(
    items: list[dict[str, Any]],
    context: str | None = None,
    max_workers: int | None = None,
    llm_service: LLMService | None = None,
) -> dict[str, Any]:
    if not items:
        return {
            "success": True,
            "results": [],
            "message": "no content items",
            "elapsed_sec": 0.0,
        }

    default_workers = int(config.get("content_batch_max_workers", 2) or 2)
    workers = max_workers if max_workers is not None else default_workers
    workers = max(1, min(workers, len(items), 8))

    t0 = time.perf_counter()
    results = _run_batch(items, context, workers, llm_service)
    results.sort(key=lambda row: row["index"])

    failed_indices = {
        row["index"]
        for row in results
        if not row["success"] and not row.get("quota_exceeded")
    }
    if failed_indices and workers > 1:
        failed_items = [
            item
            for i, item in enumerate(items)
            if int(item.get("index", i)) in failed_indices
        ]
        logger.info("batch content retrying %s failed item(s) sequentially", len(failed_items))
        retry_results = _run_batch(failed_items, context, max_workers=1, llm_service=llm_service)
        retry_by_index = {row["index"]: row for row in retry_results}
        results = [retry_by_index.get(row["index"], row) for row in results]

    elapsed = time.perf_counter() - t0
    ok_count = sum(1 for row in results if row["success"])

    return {
        "success": ok_count > 0,
        "results": results,
        "message": f"batch content generated: {ok_count}/{len(items)}",
        "elapsed_sec": round(elapsed, 2),
    }
