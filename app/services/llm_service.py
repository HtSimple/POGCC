import json
import os
from abc import ABC, abstractmethod
from app.utils.config import Config
from app.services.deepseek_service import DeepSeekService
from app.services.qwen_service import QwenService


class BaseLLMService(ABC):
    @abstractmethod
    def generate(self, prompt, model=None, temperature=0.7, max_tokens=4096):
        pass


class LLMService:

    VALID_PROVIDERS = ["deepseek", "qwen"]

    def __init__(self, config=None):
        if config is None:
            config = Config()
        self._config = config

        self.provider = self._config.get('llm_provider', 'deepseek')
        self._service = self._create_service(self.provider)

    def _create_service(self, provider):
        if provider == 'qwen':
            return QwenService(config=self._config)
        else:
            return DeepSeekService(config=self._config)

    def switch_provider(self, provider):
        if provider not in self.VALID_PROVIDERS:
            raise ValueError(f"不支持的LLM提供者: {provider}，支持的提供者: {self.VALID_PROVIDERS}")

        if provider == self.provider:
            return self.provider

        self.provider = provider
        self._service = self._create_service(provider)

        self._config.set('llm_provider', provider)

        return self.provider

    def get_available_providers(self):
        return self.VALID_PROVIDERS.copy()

    def generate(self, prompt, model=None, temperature=0.7, max_tokens=4096):
        kwargs = {"temperature": temperature, "max_tokens": max_tokens}
        if model is not None:
            kwargs["model"] = model
        return self._service.generate(prompt, **kwargs)

    @property
    def provider_name(self):
        return self.provider
