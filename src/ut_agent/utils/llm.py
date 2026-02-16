"""LLM 模型管理模块 - 支持插件式提供商注册."""

import httpx
from abc import ABC, abstractmethod
from typing import Optional, Dict, Type, Callable, Any
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from ut_agent.config import settings
from ut_agent.exceptions import ConfigurationError, LLMError

__all__ = [
    "get_llm",
    "list_available_providers",
    "register_provider",
    "LLMProvider",
    "OpenAIProvider",
    "DeepSeekProvider",
    "OllamaProvider",
]


def _create_http_client(config: Any) -> Optional[httpx.Client]:
    """创建带有 CA 证书的 HTTP 客户端.

    Args:
        config: 配置对象

    Returns:
        配置了 CA 证书的 httpx.Client，如果未配置 CA 证书则返回 None
    """
    ca_cert_path = getattr(config, "ca_cert_path", None)
    if not ca_cert_path:
        return None
    return httpx.Client(verify=ca_cert_path)


class LLMProvider(ABC):
    """LLM 提供商抽象基类."""

    name: str = ""
    requires_api_key: bool = True
    api_key_setting: str = ""
    model_setting: str = ""
    base_url_setting: str = ""

    @abstractmethod
    def create_model(self, config: Any) -> BaseChatModel:
        """创建 LLM 模型实例."""
        pass

    @abstractmethod
    def is_available(self, config: Any) -> bool:
        """检查提供商是否可用."""
        pass

    def get_config(self, config: Any) -> Dict[str, Any]:
        """获取提供商配置."""
        return {
            "api_key": getattr(config, self.api_key_setting, None) if self.api_key_setting else None,
            "model": getattr(config, self.model_setting, None) if self.model_setting else None,
            "base_url": getattr(config, self.base_url_setting, None) if self.base_url_setting else None,
        }


class OpenAIProvider(LLMProvider):
    """OpenAI 提供商."""

    name = "openai"
    requires_api_key = True
    api_key_setting = "openai_api_key"
    model_setting = "openai_model"
    base_url_setting = "openai_base_url"

    def create_model(self, config: Any) -> BaseChatModel:
        api_key, model, base_url = self.get_config(config).values()
        if not api_key:
            raise ConfigurationError(
                "OpenAI API Key 未配置",
                config_key="openai_api_key"
            )
        http_client = _create_http_client(config)
        return ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=config.temperature,
            http_client=http_client,
        )

    def is_available(self, config: Any) -> bool:
        return bool(getattr(config, self.api_key_setting, None))


class DeepSeekProvider(LLMProvider):
    """DeepSeek 提供商."""

    name = "deepseek"
    requires_api_key = True
    api_key_setting = "deepseek_api_key"
    model_setting = "deepseek_model"
    base_url_setting = "deepseek_base_url"

    def create_model(self, config: Any) -> BaseChatModel:
        api_key, model, base_url = self.get_config(config).values()
        if not api_key:
            raise ConfigurationError(
                "DeepSeek API Key 未配置",
                config_key="deepseek_api_key"
            )
        http_client = _create_http_client(config)
        return ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=config.temperature,
            http_client=http_client,
        )

    def is_available(self, config: Any) -> bool:
        return bool(getattr(config, self.api_key_setting, None))


class OllamaProvider(LLMProvider):
    """Ollama 提供商."""

    name = "ollama"
    requires_api_key = False
    api_key_setting = ""
    model_setting = "ollama_model"
    base_url_setting = "ollama_base_url"

    def create_model(self, config: Any) -> BaseChatModel:
        _, model, base_url = self.get_config(config).values()
        return ChatOllama(
            model=model,
            base_url=base_url,
            temperature=config.temperature,
        )

    def is_available(self, config: Any) -> bool:
        return True


class LLMProviderRegistry:
    """LLM 提供商注册表."""

    _providers: Dict[str, LLMProvider] = {}

    @classmethod
    def register(cls, provider: LLMProvider) -> None:
        """注册提供商."""
        cls._providers[provider.name] = provider

    @classmethod
    def get(cls, name: str) -> Optional[LLMProvider]:
        """获取提供商."""
        return cls._providers.get(name)

    @classmethod
    def list_available(cls, config: Any) -> list[str]:
        """列出可用提供商."""
        return [
            name for name, provider in cls._providers.items()
            if provider.is_available(config)
        ]

    @classmethod
    def list_all(cls) -> list[str]:
        """列出所有已注册提供商."""
        return list(cls._providers.keys())


def register_provider(provider: LLMProvider) -> None:
    """注册自定义 LLM 提供商.

    Args:
        provider: LLM 提供商实例

    Example:
        ```python
        class MyCustomProvider(LLMProvider):
            name = "my_custom"
            requires_api_key = True
            api_key_setting = "my_custom_api_key"
            model_setting = "my_custom_model"

            def create_model(self, config):
                return ChatOpenAI(
                    model=getattr(config, self.model_setting),
                    api_key=getattr(config, self.api_key_setting),
                    temperature=config.temperature,
                )

            def is_available(self, config):
                return bool(getattr(config, self.api_key_setting, None))

        register_provider(MyCustomProvider())
        ```
    """
    LLMProviderRegistry.register(provider)


def get_llm(provider: Optional[str] = None) -> Any:
    """获取 LLM 模型实例.

    Args:
        provider: LLM 提供商名称 (openai/deepseek/ollama 或自定义)

    Returns:
        BaseChatModel: LangChain 聊天模型实例（带缓存和重试机制）

    Raises:
        ConfigurationError: 提供商未配置或不可用
        LLMError: 提供商不存在
    """
    from ut_agent.utils.llm_cache import get_cached_llm
    provider_name = provider or settings.default_llm_provider
    provider_instance = LLMProviderRegistry.get(provider_name)

    if not provider_instance:
        available = LLMProviderRegistry.list_all()
        raise LLMError(
            f"不支持的 LLM 提供商: {provider_name}. 可用提供商: {available}",
            provider=provider_name
        )

    if not provider_instance.is_available(settings):
        raise ConfigurationError(
            f"LLM 提供商 '{provider_name}' 不可用，请检查配置",
            config_key=provider_instance.api_key_setting
        )

    base_llm = provider_instance.create_model(settings)
    return get_cached_llm(base_llm)


def list_available_providers() -> list[str]:
    """列出可用的 LLM 提供商.

    Returns:
        list[str]: 可用提供商名称列表
    """
    return LLMProviderRegistry.list_available(settings)


LLMProviderRegistry.register(OpenAIProvider())
LLMProviderRegistry.register(DeepSeekProvider())
LLMProviderRegistry.register(OllamaProvider())
