import json
import os
from abc import ABC, abstractmethod
from app.utils.config import Config
from app.services.deepseek_service import DeepSeekService
from app.services.qwen_service import QwenService


class BaseLLMService(ABC):
    """LLM 服务的最小接口，约束具体模型适配器都要实现文本生成。"""

    @abstractmethod
    def generate(self, prompt, model=None, temperature=0.7, max_tokens=4096):
        """根据提示词调用模型生成文本，由具体提供方实现。"""
        pass


class LLMService:
    """统一的 LLM 门面，负责在 DeepSeek 与 Qwen 适配器之间切换。"""

    VALID_PROVIDERS = ["deepseek", "qwen"]

    def __init__(self, config=None):
        """读取配置中的默认提供方，并创建对应的底层模型服务。"""
        if config is None:
            config = Config()
        self._config = config

        self.provider = self._config.get('llm_provider', 'deepseek')
        self._service = self._create_service(self.provider)

    def _create_service(self, provider):
        """按提供方名称实例化具体 LLM 服务，未知值回退到 DeepSeek。"""
        if provider == 'qwen':
            return QwenService(config=self._config)
        else:
            return DeepSeekService(config=self._config)

    def switch_provider(self, provider):
        """运行时切换 LLM 提供方，并把选择写回配置供后续调用复用。"""
        if provider not in self.VALID_PROVIDERS:
            raise ValueError(f"不支持的LLM提供者: {provider}，支持的提供者: {self.VALID_PROVIDERS}")

        if provider == self.provider:
            return self.provider

        self.provider = provider
        self._service = self._create_service(provider)

        self._config.set('llm_provider', provider)

        return self.provider

    def get_available_providers(self):
        """返回当前系统支持切换的 LLM 提供方列表。"""
        return self.VALID_PROVIDERS.copy()

    def generate(self, prompt, model=None, temperature=0.7, max_tokens=4096):
        """透传普通文本生成请求到当前提供方，允许临时覆盖模型名。"""
        kwargs = {"temperature": temperature, "max_tokens": max_tokens}
        if model is not None:
            kwargs["model"] = model
        return self._service.generate(prompt, **kwargs)

    def generate_json_schema(self, prompt, schema_name, schema, model=None, temperature=0.2, max_tokens=4096):
        """请求模型按指定 JSON Schema 输出，供结构化协议生成场景使用。"""
        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": schema_name,
                "strict": True,
                "schema": schema,
            },
        }
        kwargs = {
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": response_format,
        }
        if model is not None:
            kwargs["model"] = model
        return self._service.generate(prompt, **kwargs)

    def generate_json_object(self, prompt, model=None, temperature=0.2, max_tokens=4096):
        """请求模型返回 JSON 对象格式，适合搜索规划、评估等轻量结构化输出。"""
        kwargs = {
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }
        if model is not None:
            kwargs["model"] = model
        return self._service.generate(prompt, **kwargs)

    @property
    def provider_name(self):
        """暴露当前正在使用的 LLM 提供方名称。"""
        return self.provider
