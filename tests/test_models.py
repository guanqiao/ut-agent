"""LLM 模型管理模块单元测试."""

from unittest.mock import Mock, patch

import pytest
from langchain_core.language_models.chat_models import BaseChatModel

from ut_agent.config import settings
from ut_agent.models import get_llm, list_available_providers


class TestGetLLM:
    """get_llm 函数测试."""

    @patch("ut_agent.models.llm.settings")
    @patch("ut_agent.models.llm.ChatOpenAI")
    def test_get_openai_llm(self, mock_chat_openai, mock_settings):
        """测试获取 OpenAI LLM."""
        mock_settings.openai_api_key = "test-key"
        mock_settings.openai_model = "gpt-4o"
        mock_settings.openai_base_url = None
        mock_settings.temperature = 0.2

        mock_instance = Mock(spec=BaseChatModel)
        mock_chat_openai.return_value = mock_instance

        result = get_llm("openai")

        assert result is mock_instance
        mock_chat_openai.assert_called_once_with(
            model="gpt-4o",
            api_key="test-key",
            base_url=None,
            temperature=0.2,
        )

    @patch("ut_agent.models.llm.settings")
    @patch("ut_agent.models.llm.ChatOpenAI")
    def test_get_openai_llm_with_base_url(self, mock_chat_openai, mock_settings):
        """测试获取带自定义 base_url 的 OpenAI LLM."""
        mock_settings.openai_api_key = "test-key"
        mock_settings.openai_model = "gpt-4"
        mock_settings.openai_base_url = "https://custom.api.com"
        mock_settings.temperature = 0.5

        mock_instance = Mock(spec=BaseChatModel)
        mock_chat_openai.return_value = mock_instance

        result = get_llm("openai")

        mock_chat_openai.assert_called_once_with(
            model="gpt-4",
            api_key="test-key",
            base_url="https://custom.api.com",
            temperature=0.5,
        )

    @patch("ut_agent.models.llm.settings")
    def test_get_openai_llm_without_api_key(self, mock_settings):
        """测试未配置 API Key 时获取 OpenAI LLM."""
        mock_settings.openai_api_key = None

        with pytest.raises(ValueError, match="OpenAI API Key 未配置"):
            get_llm("openai")

    @patch("ut_agent.models.llm.settings")
    @patch("ut_agent.models.llm.ChatOpenAI")
    def test_get_deepseek_llm(self, mock_chat_openai, mock_settings):
        """测试获取 DeepSeek LLM."""
        mock_settings.deepseek_api_key = "deepseek-key"
        mock_settings.deepseek_model = "deepseek-chat"
        mock_settings.deepseek_base_url = "https://api.deepseek.com"
        mock_settings.temperature = 0.2

        mock_instance = Mock(spec=BaseChatModel)
        mock_chat_openai.return_value = mock_instance

        result = get_llm("deepseek")

        assert result is mock_instance
        mock_chat_openai.assert_called_once_with(
            model="deepseek-chat",
            api_key="deepseek-key",
            base_url="https://api.deepseek.com",
            temperature=0.2,
        )

    @patch("ut_agent.models.llm.settings")
    def test_get_deepseek_llm_without_api_key(self, mock_settings):
        """测试未配置 API Key 时获取 DeepSeek LLM."""
        mock_settings.deepseek_api_key = None

        with pytest.raises(ValueError, match="DeepSeek API Key 未配置"):
            get_llm("deepseek")

    @patch("ut_agent.models.llm.settings")
    @patch("ut_agent.models.llm.ChatOllama")
    def test_get_ollama_llm(self, mock_chat_ollama, mock_settings):
        """测试获取 Ollama LLM."""
        mock_settings.ollama_model = "qwen2.5-coder:14b"
        mock_settings.ollama_base_url = "http://localhost:11434"
        mock_settings.temperature = 0.2

        mock_instance = Mock(spec=BaseChatModel)
        mock_chat_ollama.return_value = mock_instance

        result = get_llm("ollama")

        assert result is mock_instance
        mock_chat_ollama.assert_called_once_with(
            model="qwen2.5-coder:14b",
            base_url="http://localhost:11434",
            temperature=0.2,
        )

    @patch("ut_agent.models.llm.settings")
    @patch("ut_agent.models.llm.ChatOllama")
    def test_get_ollama_llm_with_custom_config(self, mock_chat_ollama, mock_settings):
        """测试获取带自定义配置的 Ollama LLM."""
        mock_settings.ollama_model = "llama2"
        mock_settings.ollama_base_url = "http://192.168.1.100:11434"
        mock_settings.temperature = 0.8

        mock_instance = Mock(spec=BaseChatModel)
        mock_chat_ollama.return_value = mock_instance

        result = get_llm("ollama")

        mock_chat_ollama.assert_called_once_with(
            model="llama2",
            base_url="http://192.168.1.100:11434",
            temperature=0.8,
        )

    @patch("ut_agent.models.llm.settings")
    def test_get_unsupported_provider(self, mock_settings):
        """测试获取不支持的 LLM 提供商."""
        with pytest.raises(ValueError, match="不支持的 LLM 提供商"):
            get_llm("unsupported")

    @patch("ut_agent.models.llm.settings")
    @patch("ut_agent.models.llm.ChatOpenAI")
    def test_get_default_llm(self, mock_chat_openai, mock_settings):
        """测试获取默认 LLM."""
        mock_settings.default_llm_provider = "openai"
        mock_settings.openai_api_key = "test-key"
        mock_settings.openai_model = "gpt-4o"
        mock_settings.openai_base_url = None
        mock_settings.temperature = 0.2

        mock_instance = Mock(spec=BaseChatModel)
        mock_chat_openai.return_value = mock_instance

        result = get_llm()

        assert result is mock_instance
        mock_chat_openai.assert_called_once()

    @patch("ut_agent.models.llm.settings")
    @patch("ut_agent.models.llm.ChatOpenAI")
    def test_get_llm_provider_override(self, mock_chat_openai, mock_settings):
        """测试覆盖默认 LLM 提供商."""
        mock_settings.default_llm_provider = "ollama"
        mock_settings.openai_api_key = "test-key"
        mock_settings.openai_model = "gpt-4o"
        mock_settings.openai_base_url = None
        mock_settings.temperature = 0.2

        mock_instance = Mock(spec=BaseChatModel)
        mock_chat_openai.return_value = mock_instance

        result = get_llm("openai")

        assert result is mock_instance


class TestListAvailableProviders:
    """list_available_providers 函数测试."""

    @patch("ut_agent.models.llm.settings")
    def test_list_with_all_providers(self, mock_settings):
        """测试列出所有可用的提供商."""
        mock_settings.openai_api_key = "openai-key"
        mock_settings.deepseek_api_key = "deepseek-key"

        providers = list_available_providers()

        assert "openai" in providers
        assert "deepseek" in providers
        assert "ollama" in providers

    @patch("ut_agent.models.llm.settings")
    def test_list_without_api_keys(self, mock_settings):
        """测试没有 API Key 时的提供商列表."""
        mock_settings.openai_api_key = None
        mock_settings.deepseek_api_key = None

        providers = list_available_providers()

        assert "openai" not in providers
        assert "deepseek" not in providers
        assert "ollama" in providers

    @patch("ut_agent.models.llm.settings")
    def test_list_with_only_openai(self, mock_settings):
        """测试只有 OpenAI 配置时."""
        mock_settings.openai_api_key = "openai-key"
        mock_settings.deepseek_api_key = None

        providers = list_available_providers()

        assert "openai" in providers
        assert "deepseek" not in providers
        assert "ollama" in providers

    @patch("ut_agent.models.llm.settings")
    def test_list_with_only_deepseek(self, mock_settings):
        """测试只有 DeepSeek 配置时."""
        mock_settings.openai_api_key = None
        mock_settings.deepseek_api_key = "deepseek-key"

        providers = list_available_providers()

        assert "openai" not in providers
        assert "deepseek" in providers
        assert "ollama" in providers

    @patch("ut_agent.models.llm.settings")
    def test_list_order(self, mock_settings):
        """测试提供商列表顺序."""
        mock_settings.openai_api_key = "key"
        mock_settings.deepseek_api_key = "key"

        providers = list_available_providers()

        assert providers[-1] == "ollama"

    @patch("ut_agent.models.llm.settings")
    def test_list_empty_api_keys(self, mock_settings):
        """测试空字符串 API Key."""
        mock_settings.openai_api_key = ""
        mock_settings.deepseek_api_key = ""

        providers = list_available_providers()

        assert "openai" not in providers
        assert "deepseek" not in providers
