import json
import math
import threading
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from app.utils.config import Config


PROVIDERS = ("deepseek", "qwen")


class ApiQuotaExceeded(RuntimeError):
    """Raised before an external API call when its configured quota is exhausted."""

    def __init__(self, provider: str, reasons: list[str]):
        self.provider = provider
        self.reasons = reasons
        provider_name = {
            "deepseek": "DeepSeek",
            "qwen": "千问",
        }.get(provider, provider)
        super().__init__(
            f"{provider_name} 调用已被限额拦截：{'；'.join(reasons)}。"
            "请调整限额或清零用量后重试。"
        )


def estimate_tokens(text) -> int:
    """Estimate tokens when a provider does not expose usage metadata."""
    if not text:
        return 0
    return max(1, math.ceil(len(str(text)) / 3))


class ApiCostService:
    def __init__(self, config=None, usage_file=None):
        self._config = config or Config()
        configured_path = self._config.get("api_usage_file", "app/data/api_usage.json")
        self.usage_file = Path(usage_file or configured_path)
        self._lock = threading.RLock()
        self._data = self._load()

    @staticmethod
    def _empty_provider():
        return {
            "call_limit": None,
            "token_limit": None,
            "cost_limit": None,
            "calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "estimated_cost": 0.0,
            "currency": "USD",
            "total_duration_ms": 0,
            "failed_calls": 0,
            "blocked_calls": 0,
            "actual_token_calls": 0,
            "estimated_token_calls": 0,
            "last_called_at": None,
        }

    def _empty_data(self):
        providers = {}
        for provider in PROVIDERS:
            providers[provider] = self._empty_provider()
            providers[provider]["currency"] = self._pricing(provider).get("currency", "USD")
        return {
            "providers": providers,
            "recent_calls": [],
            "daily_usage": {provider: {} for provider in PROVIDERS},
        }

    def _load(self):
        data = self._empty_data()
        try:
            if self.usage_file.exists():
                loaded = json.loads(self.usage_file.read_text(encoding="utf-8"))
                for provider in PROVIDERS:
                    old_usage = loaded.get("providers", {}).get(provider, {})
                    if "cost_limit_usd" in old_usage:
                        old_usage["cost_limit"] = old_usage.pop("cost_limit_usd")
                    if "estimated_cost_usd" in old_usage:
                        old_usage["estimated_cost"] = old_usage.pop("estimated_cost_usd")
                    data["providers"][provider].update(old_usage)
                    data["providers"][provider]["currency"] = self._pricing(provider).get(
                        "currency", "USD"
                    )
                data["recent_calls"] = [
                    item for item in loaded.get("recent_calls", [])
                    if item.get("provider") in PROVIDERS
                ][-100:]
                for item in data["recent_calls"]:
                    item.setdefault("model", None)
                    item.setdefault("retry_count", 0)
                    item.setdefault("token_source", "estimated")
                    if "estimated_cost_usd" in item:
                        item["estimated_cost"] = item.pop("estimated_cost_usd")
                    item.setdefault("estimated_cost", 0)
                    item.setdefault("currency", self._pricing(item["provider"]).get("currency", "USD"))
                loaded_daily = loaded.get("daily_usage", {})
                for provider in PROVIDERS:
                    data["daily_usage"][provider] = loaded_daily.get(provider, {})
                if not loaded_daily:
                    for item in data["recent_calls"]:
                        provider = item["provider"]
                        day = str(item.get("called_at", ""))[:10]
                        if not day:
                            continue
                        currency = item.get("currency", data["providers"][provider]["currency"])
                        daily = data["daily_usage"][provider].setdefault(
                            day,
                            {
                                "calls": 0,
                                "input_tokens": 0,
                                "output_tokens": 0,
                                "total_tokens": 0,
                                "estimated_cost": 0.0,
                                "currency": currency,
                            },
                        )
                        input_tokens = int(item.get("input_tokens", 0))
                        output_tokens = int(item.get("output_tokens", 0))
                        daily["calls"] += 1
                        daily["input_tokens"] += input_tokens
                        daily["output_tokens"] += output_tokens
                        daily["total_tokens"] += input_tokens + output_tokens
                        daily["estimated_cost"] = round(
                            daily["estimated_cost"] + float(item.get("estimated_cost", 0)), 8
                        )
        except (OSError, json.JSONDecodeError):
            pass
        return data

    def _save(self):
        self.usage_file.parent.mkdir(parents=True, exist_ok=True)
        temp_file = self.usage_file.with_suffix(".tmp")
        temp_file.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temp_file.replace(self.usage_file)

    def _pricing(self, provider):
        pricing = self._config.get("api_cost_rates", {}) or {}
        return pricing.get(provider, {}) or {}

    def estimate_cost(self, provider, input_tokens=0, output_tokens=0, cache_hit_tokens=0, cache_miss_tokens=0):
        pricing = self._pricing(provider)
        for tier in pricing.get("tiers", []):
            if input_tokens <= int(tier.get("max_input_tokens", 0)):
                pricing = {**pricing, **tier}
                break
        input_rate = float(pricing.get("input_per_million", 0) or 0)
        cache_hit_rate = float(pricing.get("cache_hit_input_per_million", input_rate) or 0)
        cache_miss_rate = float(pricing.get("cache_miss_input_per_million", input_rate) or 0)
        output_rate = float(pricing.get("output_per_million", 0) or 0)
        priced_input = (
            cache_hit_tokens * cache_hit_rate
            + cache_miss_tokens * cache_miss_rate
            if cache_hit_tokens or cache_miss_tokens
            else input_tokens * input_rate
        )
        return (
            priced_input / 1_000_000
            + output_tokens * output_rate / 1_000_000
        )

    def check_quota(self, provider):
        if provider not in PROVIDERS:
            raise ValueError(f"Unsupported API provider: {provider}")
        with self._lock:
            usage = self._data["providers"][provider]
            reasons = []
            if usage["call_limit"] is not None and usage["calls"] >= usage["call_limit"]:
                reasons.append(
                    f"调用次数已达到上限（当前 {usage['calls']} 次 / 上限 {usage['call_limit']} 次）"
                )
            if usage["token_limit"] is not None and usage["total_tokens"] >= usage["token_limit"]:
                reasons.append(
                    f"Token 用量已达到上限（当前 {usage['total_tokens']} / 上限 {usage['token_limit']}）"
                )
            if (
                usage["cost_limit"] is not None
                and usage["estimated_cost"] >= usage["cost_limit"]
            ):
                currency = usage["currency"]
                reasons.append(
                    "预估成本已达到上限"
                    f"（当前 {usage['estimated_cost']:.6f} {currency} / "
                    f"上限 {usage['cost_limit']:.6f} {currency}）"
                )
            if reasons:
                usage["blocked_calls"] += 1
                self._save()
                raise ApiQuotaExceeded(provider, reasons)

    def record_call(
        self,
        provider,
        *,
        input_tokens=0,
        output_tokens=0,
        cache_hit_tokens=0,
        cache_miss_tokens=0,
        duration_ms=0,
        success=True,
        model=None,
        retry_count=0,
        token_source="estimated",
        error=None,
    ):
        with self._lock:
            usage = self._data["providers"][provider]
            pricing = self._pricing(provider)
            currency = pricing.get("currency", "USD")
            cost = self.estimate_cost(
                provider, input_tokens, output_tokens, cache_hit_tokens, cache_miss_tokens
            )
            usage["calls"] += 1
            usage["input_tokens"] += int(input_tokens)
            usage["output_tokens"] += int(output_tokens)
            usage["total_tokens"] += int(input_tokens + output_tokens)
            usage["estimated_cost"] = round(usage["estimated_cost"] + cost, 8)
            usage["currency"] = currency
            usage["total_duration_ms"] += int(duration_ms)
            usage["failed_calls"] += 0 if success else 1
            usage["actual_token_calls"] += 1 if token_source == "actual" else 0
            usage["estimated_token_calls"] += 1 if token_source != "actual" else 0
            now = datetime.now(timezone.utc).isoformat()
            day = datetime.now().astimezone().date().isoformat()
            usage["last_called_at"] = now
            daily = self._data["daily_usage"][provider].setdefault(
                day,
                {
                    "calls": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                    "estimated_cost": 0.0,
                    "currency": currency,
                },
            )
            daily["calls"] += 1
            daily["input_tokens"] += int(input_tokens)
            daily["output_tokens"] += int(output_tokens)
            daily["total_tokens"] += int(input_tokens + output_tokens)
            daily["estimated_cost"] = round(daily["estimated_cost"] + cost, 8)
            daily["currency"] = currency
            self._data["recent_calls"].append(
                {
                    "provider": provider,
                    "model": model,
                    "retry_count": int(retry_count),
                    "token_source": token_source,
                    "success": success,
                    "input_tokens": int(input_tokens),
                    "output_tokens": int(output_tokens),
                    "cache_hit_tokens": int(cache_hit_tokens),
                    "cache_miss_tokens": int(cache_miss_tokens),
                    "duration_ms": int(duration_ms),
                    "estimated_cost": round(cost, 8),
                    "currency": currency,
                    "error": str(error)[:300] if error else None,
                    "called_at": now,
                }
            )
            self._data["recent_calls"] = self._data["recent_calls"][-100:]
            self._save()

    def get_summary(self):
        with self._lock:
            result = deepcopy(self._data)
            for usage in result["providers"].values():
                calls = usage["calls"]
                usage["average_duration_ms"] = (
                    round(usage["total_duration_ms"] / calls) if calls else 0
                )
            return result

    def update_limits(
        self, provider, *, call_limit=None, token_limit=None, cost_limit=None
    ):
        if provider not in PROVIDERS:
            raise ValueError(f"Unsupported API provider: {provider}")
        with self._lock:
            usage = self._data["providers"][provider]
            usage["call_limit"] = call_limit
            usage["token_limit"] = token_limit
            usage["cost_limit"] = cost_limit
            self._save()
            return deepcopy(usage)

    def reset_usage(self, provider=None):
        if provider is not None and provider not in PROVIDERS:
            raise ValueError(f"Unsupported API provider: {provider}")
        with self._lock:
            targets = PROVIDERS if provider is None else (provider,)
            for name in targets:
                current = self._data["providers"][name]
                limits = {
                    key: current[key]
                    for key in ("call_limit", "token_limit", "cost_limit")
                }
                self._data["providers"][name] = self._empty_provider()
                self._data["providers"][name].update(limits)
                self._data["providers"][name]["currency"] = self._pricing(name).get(
                    "currency", "USD"
                )
                self._data["daily_usage"][name] = {}
            if provider is None:
                self._data["recent_calls"] = []
            else:
                self._data["recent_calls"] = [
                    item
                    for item in self._data["recent_calls"]
                    if item.get("provider") != provider
                ]
            self._save()


_shared_service = None
_shared_lock = threading.Lock()


def get_api_cost_service(config=None):
    global _shared_service
    with _shared_lock:
        if _shared_service is None:
            _shared_service = ApiCostService(config=config)
        return _shared_service
