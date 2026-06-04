from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

CURRENT = Path(__file__).resolve()
TESTING_DIR = CURRENT.parents[1]
if str(TESTING_DIR) not in sys.path:
    sys.path.insert(0, str(TESTING_DIR))

from _test_utils import add_project_root_to_path

ROOT = add_project_root_to_path(CURRENT)


def test_llm_service_has_provider_metadata():
    """
    Basic compatibility check for the existing LLMService.
    If API keys are missing in local dev, initialization may fail and the test is skipped.
    """
    try:
        from app.services.llm_service import LLMService
        service = LLMService()
    except Exception as exc:
        pytest.skip(f"LLMService cannot initialize in this environment: {exc}")

    assert hasattr(service, "provider_name")
    assert service.provider_name in {"deepseek", "qwen"}


class SimpleFallbackGateway:
    """
    A tiny test double that documents the expected fallback behavior.
    Use this test as a target when you later implement app/services/model_gateway.py.
    """

    def __init__(self, primary, backup, max_retries: int = 1):
        self.primary = primary
        self.backup = backup
        self.max_retries = max_retries

    def generate(self, prompt: str) -> str:
        last_error = None
        for _ in range(self.max_retries + 1):
            try:
                return self.primary.generate(prompt)
            except Exception as exc:
                last_error = exc
        try:
            return self.backup.generate(prompt)
        except Exception as backup_exc:
            raise RuntimeError(f"both primary and backup failed: {last_error}; {backup_exc}") from backup_exc


def test_expected_model_fallback_behavior():
    primary = Mock()
    primary.generate.side_effect = [TimeoutError("timeout"), RuntimeError("still failing")]
    backup = Mock()
    backup.generate.return_value = "backup-ok"

    gateway = SimpleFallbackGateway(primary=primary, backup=backup, max_retries=1)
    result = gateway.generate("hello")

    assert result == "backup-ok"
    assert primary.generate.call_count == 2
    assert backup.generate.call_count == 1


def test_expected_model_fallback_raises_when_all_failed():
    primary = Mock()
    primary.generate.side_effect = RuntimeError("primary down")
    backup = Mock()
    backup.generate.side_effect = RuntimeError("backup down")

    gateway = SimpleFallbackGateway(primary=primary, backup=backup, max_retries=1)
    with pytest.raises(RuntimeError):
        gateway.generate("hello")
