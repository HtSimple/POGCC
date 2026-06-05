import json

import pytest

from app.core.generator import batch_content
from app.services.api_cost_service import (
    ApiCostService,
    ApiQuotaExceeded,
    estimate_tokens,
)
from app.services.llm_service import LLMService


class TestConfig:
    def get(self, key, default=None):
        if key == "api_cost_rates":
            return {
                "deepseek": {
                    "currency": "USD",
                    "input_per_million": 1,
                    "output_per_million": 2,
                },
                "qwen": {"currency": "CNY", "input_per_million": 2, "output_per_million": 12},
            }
        return default


def test_records_usage_and_estimated_cost(tmp_path):
    usage_file = tmp_path / "usage.json"
    service = ApiCostService(config=TestConfig(), usage_file=usage_file)

    service.record_call(
        "deepseek",
        input_tokens=1_000_000,
        output_tokens=500_000,
        duration_ms=120,
    )

    usage = service.get_summary()["providers"]["deepseek"]
    assert usage["calls"] == 1
    assert usage["total_tokens"] == 1_500_000
    assert usage["estimated_cost"] == 2
    assert usage["average_duration_ms"] == 120
    assert json.loads(usage_file.read_text(encoding="utf-8"))["providers"]["deepseek"]["calls"] == 1


def test_blocks_llm_call_after_limit_is_reached(tmp_path):
    service = ApiCostService(config=TestConfig(), usage_file=tmp_path / "usage.json")
    service.update_limits("qwen", call_limit=1)
    service.record_call("qwen")

    with pytest.raises(
        ApiQuotaExceeded,
        match=r"千问 调用已被限额拦截：调用次数已达到上限（当前 1 次 / 上限 1 次）",
    ):
        service.check_quota("qwen")

    assert service.get_summary()["providers"]["qwen"]["blocked_calls"] == 1


def test_quota_error_lists_token_and_cost_limits_with_current_usage(tmp_path):
    service = ApiCostService(config=TestConfig(), usage_file=tmp_path / "usage.json")
    service.update_limits("qwen", token_limit=20, cost_limit=0.00004)
    service.record_call("qwen", input_tokens=10, output_tokens=10)

    with pytest.raises(ApiQuotaExceeded) as exc_info:
        service.check_quota("qwen")

    message = str(exc_info.value)
    assert "Token 用量已达到上限（当前 20 / 上限 20）" in message
    assert "预估成本已达到上限（当前 0.000140 CNY / 上限 0.000040 CNY）" in message
    assert "请调整限额或清零用量后重试" in message


def test_batch_content_does_not_retry_quota_failures(monkeypatch):
    calls = 0

    class QuotaBlockedExpander:
        def __init__(self, llm_service):
            pass

        def expand_page_content(self, outline_node, context=None):
            nonlocal calls
            calls += 1
            raise ApiQuotaExceeded("deepseek", ["调用次数已达到上限（当前 3 次 / 上限 3 次）"])

    monkeypatch.setattr(batch_content, "ContentExpander", QuotaBlockedExpander)
    result = batch_content._expand_one(0, {"title": "测试"}, None, "slide-001", object())

    assert calls == 1
    assert result["success"] is False
    assert result["quota_exceeded"] is True
    assert "调用次数已达到上限" in result["message"]


def test_reset_keeps_limits_and_token_estimation_is_available(tmp_path):
    service = ApiCostService(config=TestConfig(), usage_file=tmp_path / "usage.json")
    service.update_limits("qwen", token_limit=100)
    service.record_call("qwen", input_tokens=10, output_tokens=20)

    service.reset_usage("qwen")

    usage = service.get_summary()["providers"]["qwen"]
    assert usage["total_tokens"] == 0
    assert usage["token_limit"] == 100
    assert estimate_tokens("用于估算 Token 的文本") > 0


def test_deepseek_cache_tokens_use_separate_prices(tmp_path):
    class CachePriceConfig:
        def get(self, key, default=None):
            if key == "api_cost_rates":
                return {
                    "deepseek": {
                        "currency": "USD",
                        "cache_hit_input_per_million": 0.1,
                        "cache_miss_input_per_million": 1,
                        "output_per_million": 2,
                    }
                }
            return default

    service = ApiCostService(config=CachePriceConfig(), usage_file=tmp_path / "usage.json")
    service.record_call(
        "deepseek",
        input_tokens=2_000_000,
        output_tokens=500_000,
        cache_hit_tokens=1_000_000,
        cache_miss_tokens=1_000_000,
        token_source="actual",
    )

    usage = service.get_summary()["providers"]["deepseek"]
    assert usage["estimated_cost"] == 2.1
    assert usage["actual_token_calls"] == 1


def test_llm_service_prefers_provider_actual_usage():
    recorded = {}

    class FakeProvider:
        def generate_with_usage(self, prompt, **kwargs):
            return "answer", {
                "input_tokens": 12,
                "output_tokens": 4,
                "cache_hit_tokens": 8,
                "cache_miss_tokens": 4,
            }

    class FakeCostService:
        def check_quota(self, provider):
            pass

        def record_call(self, provider, **kwargs):
            recorded.update(kwargs)

    service = LLMService.__new__(LLMService)
    service.provider = "deepseek"
    service._service = FakeProvider()
    service.cost_service = FakeCostService()

    assert service.generate("hello") == "answer"
    assert recorded["input_tokens"] == 12
    assert recorded["output_tokens"] == 4
    assert recorded["token_source"] == "actual"


def test_qwen_uses_input_length_pricing_tier(tmp_path):
    class TierConfig:
        def get(self, key, default=None):
            if key == "api_cost_rates":
                return {
                    "qwen": {
                        "currency": "CNY",
                        "tiers": [
                            {"max_input_tokens": 10, "input_per_million": 1, "output_per_million": 2},
                            {"max_input_tokens": 100, "input_per_million": 10, "output_per_million": 20},
                        ],
                    }
                }
            return default

    service = ApiCostService(config=TierConfig(), usage_file=tmp_path / "usage.json")
    assert service.estimate_cost("qwen", input_tokens=20, output_tokens=10) == pytest.approx(0.0004)


def test_records_daily_usage(tmp_path):
    service = ApiCostService(config=TestConfig(), usage_file=tmp_path / "usage.json")
    service.record_call("qwen", input_tokens=10, output_tokens=5, token_source="actual")

    daily = service.get_summary()["daily_usage"]["qwen"]
    assert len(daily) == 1
    today = next(iter(daily.values()))
    assert today["calls"] == 1
    assert today["total_tokens"] == 15
