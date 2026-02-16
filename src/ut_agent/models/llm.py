"""LLM 模型管理模块."""

from typing import Optional
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from ut_agent.config import settings


def get_llm(provider: Optional[str] = None) -> BaseChatModel:
    """获取 LLM 模型实例.

    Args:
        provider: LLM 提供商 (openai/deepseek/ollama)

    Returns:
        BaseChatModel: LangChain 聊天模型实例
    """
    provider = provider or settings.default_llm_provider

    if provider == "openai":
        if not settings.openai_api_key:
            raise ValueError("OpenAI API Key 未配置")
        return ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            temperature=settings.temperature,
        )

    elif provider == "deepseek":
        if not settings.deepseek_api_key:
            raise ValueError("DeepSeek API Key 未配置")
        return ChatOpenAI(
            model=settings.deepseek_model,
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            temperature=settings.temperature,
        )

    elif provider == "ollama":
        return ChatOllama(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
            temperature=settings.temperature,
        )

    else:
        raise ValueError(f"不支持的 LLM 提供商: {provider}")


def list_available_providers() -> list[str]:
    """列出可用的 LLM 提供商."""
    providers = []

    if settings.openai_api_key:
        providers.append("openai")
    if settings.deepseek_api_key:
        providers.append("deepseek")
    providers.append("ollama")

    return providers
