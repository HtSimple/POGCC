from __future__ import annotations

import concurrent.futures
import os
import sys
import time
from pathlib import Path

import pytest
import requests

CURRENT = Path(__file__).resolve()
TESTING_DIR = CURRENT.parents[1]
if str(TESTING_DIR) not in sys.path:
    sys.path.insert(0, str(TESTING_DIR))

from _test_utils import get_base_url, is_server_reachable

BASE_URL = get_base_url()
CONCURRENCY = int(os.environ.get("POGCC_CONCURRENCY", "3"))
TIMEOUT = int(os.environ.get("POGCC_CONCURRENCY_TIMEOUT", "240"))


pytestmark = pytest.mark.performance


def _call_outline(index: int) -> dict:
    start = time.perf_counter()
    try:
        resp = requests.post(
            f"{BASE_URL}/api/generator/outline",
            json={
                "topic": f"并发测试主题 {index}",
                "requirements": "生成5页PPT，测试后端在并发请求下是否稳定。",
            },
            timeout=TIMEOUT,
        )
        return {
            "index": index,
            "status_code": resp.status_code,
            "elapsed": time.perf_counter() - start,
            "ok": resp.status_code == 200 and isinstance(resp.json(), dict),
            "error": "",
        }
    except Exception as exc:
        return {
            "index": index,
            "status_code": None,
            "elapsed": time.perf_counter() - start,
            "ok": False,
            "error": str(exc),
        }


def test_three_concurrent_outline_requests():
    """
    Project charter requires the backend prototype to support at least 3 concurrent requests.
    """
    if not is_server_reachable(BASE_URL):
        pytest.skip(f"POGCC server is not reachable at {BASE_URL}.")

    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
        results = list(executor.map(_call_outline, range(1, CONCURRENCY + 1)))

    failed = [r for r in results if not r["ok"]]
    assert not failed, f"failed concurrent calls: {failed}; all results: {results}"
