from __future__ import annotations

import json
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
LATENCY_LIMIT_SEC = float(os.environ.get("POGCC_LATENCY_LIMIT_SEC", "300"))


pytestmark = pytest.mark.performance


def require_server():
    if not is_server_reachable(BASE_URL):
        pytest.skip(f"POGCC server is not reachable at {BASE_URL}.")


def test_outline_latency_under_limit():
    """
    Tests response latency for outline generation.
    Default threshold follows the charter: <= 300 seconds for long document flow.
    For CI you can set POGCC_LATENCY_LIMIT_SEC=60.
    """
    require_server()
    payload = {
        "topic": "PPT大纲智能生成与内容补全系统性能测试",
        "requirements": (
            "请生成10页课程汇报PPT。包含项目背景、需求分析、系统架构、RAG链路、"
            "内容生成、测试验证、风险与总结。"
        ),
    }
    start = time.perf_counter()
    resp = requests.post(f"{BASE_URL}/api/generator/outline", json=payload, timeout=LATENCY_LIMIT_SEC + 30)
    elapsed = time.perf_counter() - start
    assert resp.status_code == 200, resp.text[:1000]
    assert elapsed <= LATENCY_LIMIT_SEC
    data = resp.json()
    assert "success" in data


def test_long_requirement_latency_smoke():
    """
    Smoke test for a long input. It does not create a real 10k-word file,
    but pushes a long requirement string through the current outline endpoint.
    """
    require_server()
    long_text = "这是用于性能测试的长文本。系统需要提取主题、组织逻辑、生成大纲并控制输出结构。" * 250
    start = time.perf_counter()
    resp = requests.post(
        f"{BASE_URL}/api/generator/outline",
        json={"topic": "长文档PPT生成测试", "requirements": long_text},
        timeout=LATENCY_LIMIT_SEC + 30,
    )
    elapsed = time.perf_counter() - start
    assert resp.status_code == 200, resp.text[:1000]
    assert elapsed <= LATENCY_LIMIT_SEC
