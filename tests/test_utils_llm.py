"""LLM 模型管理模块单元测试."""

from unittest.mock import Mock, patch, MagicMock

import pytest

from ut_agent.utils.llm import (
    LLMProvider,
    OpenAIProvider,
    DeepSeekProvider,
    OllamaProvider,
    LLMProviderRegistry,
    register_provider,
    get_llm,
    list_available_providers,
)
from ut_agent.config import settings
from ut_agent.exceptions import ConfigurationError, LLMError


class TestLLMProvider:
    """LLMProvider 抽象基类测试."""

    def test_abstract_methods(self):
        """测试抽象方法必须被实现."""
        class TestProvider(LLMProvider):
            name = "test"
            
            def create_model(self, config):
                pass
            
            def is_available(self, config):
                pass

        provider = TestProvider()
        assert provider.name == "test"
        assert provider.requires_api_key is True

    def test_get_config(self):
        """测试 get_config 方法."""
        class TestProvider(LLMProvider):
            name = "test"
            api_key_setting = "test_api_key"
            model_setting = "test_model"
            base_url_setting = "test_base_url"
            
            def create_model(self, config):
                pass
            
            def is_available(self, config):
                pass

        mock_config = Mock(
            test_api_key="test_key",
            test_model="test_model",
            test_base_url="http://localhost",
        )

        provider = TestProvider()
        config = provider.get_config(mock_config)

        assert config["api_key"] == "test_key"
        assert config["model"] == "test_model"
        assert config["base_url"] == "http://localhost"

    def test_get_config_no_settings(self):
        """测试无设置时的 get_config 方法."""
        class TestProvider(LLMProvider):
            name = "test"
            api_key_setting = ""
            model_setting = ""
            base_url_setting = ""
            
            def create_model(self, config):
                pass
            
            def is_available(self, config):
                pass

        mock_config = Mock()
        provider = TestProvider()
        config = provider.get_config(mock_config)

        assert config["api_key"] is None
        assert config["model"] is None
        assert config["base_url"] is None


class TestOpenAIProvider:
    """OpenAIProvider 测试."""

    def test_openai_provider_initialization(self):
        """测试 OpenAIProvider 初始化."""
        provider = OpenAIProvider()

        assert provider.name == "openai"
        assert provider.requires_api_key is True
        assert provider.api_key_setting == "openai_api_key"
        assert provider.model_setting == "openai_model"
        assert provider.base_url_setting == "openai_base_url"

    def test_openai_is_available_true(self):
        """测试 OpenAI 可用."""
        provider = OpenAIProvider()
        mock_config = Mock(openai_api_key="test_key")

        assert provider.is_available(mock_config) is True

    def test_openai_is_available_false(self):
        """测试 OpenAI 不可用."""
        provider = OpenAIProvider()
        mock_config = Mock(openai_api_key=None)

        assert provider.is_available(mock_config) is False

    def test_openai_create_model(self):
        """测试创建 OpenAI 模型."""
        provider = OpenAIProvider()
        mock_config = Mock(
            openai_api_key="test_key",
            openai_model="gpt-3.5-turbo",
            openai_base_url="https://api.openai.com/v1",
            temperature=0.7,
            ca_cert_path=None,
        )

        with patch("ut_agent.utils.llm.ChatOpenAI") as mock_chat_openai:
            mock_model = Mock()
            mock_chat_openai.return_value = mock_model

            model = provider.create_model(mock_config)

            mock_chat_openai.assert_called_once_with(
                model="gpt-3.5-turbo",
                api_key="test_key",
                base_url="https://api.openai.com/v1",
                temperature=0.7,
                http_client=None,
            )
            assert model == mock_model

    def test_openai_create_model_no_api_key(self):
        """测试无 API Key 时创建 OpenAI 模型."""
        provider = OpenAIProvider()
        mock_config = Mock(
            openai_api_key=None,
            openai_model="gpt-3.5-turbo",
            openai_base_url="https://api.openai.com/v1",
            temperature=0.7,
        )

        with pytest.raises(ConfigurationError):
            provider.create_model(mock_config)


class TestDeepSeekProvider:
    """DeepSeekProvider 测试."""

    def test_deepseek_provider_initialization(self):
        """测试 DeepSeekProvider 初始化."""
        provider = DeepSeekProvider()

        assert provider.name == "deepseek"
        assert provider.requires_api_key is True
        assert provider.api_key_setting == "deepseek_api_key"
        assert provider.model_setting == "deepseek_model"
        assert provider.base_url_setting == "deepseek_base_url"

    def test_deepseek_is_available_true(self):
        """测试 DeepSeek 可用."""
        provider = DeepSeekProvider()
        mock_config = Mock(deepseek_api_key="test_key")

        assert provider.is_available(mock_config) is True

    def test_deepseek_is_available_false(self):
        """测试 DeepSeek 不可用."""
        provider = DeepSeekProvider()
        mock_config = Mock(deepseek_api_key=None)

        assert provider.is_available(mock_config) is False

    def test_deepseek_create_model(self):
        """测试创建 DeepSeek 模型."""
        provider = DeepSeekProvider()
        mock_config = Mock(
            deepseek_api_key="test_key",
            deepseek_model="deepseek-chat",
            deepseek_base_url="https://api.deepseek.com/v1",
            temperature=0.7,
            ca_cert_path=None,
        )

        with patch("ut_agent.utils.llm.ChatOpenAI") as mock_chat_openai:
            mock_model = Mock()
            mock_chat_openai.return_value = mock_model

            model = provider.create_model(mock_config)

            mock_chat_openai.assert_called_once_with(
                model="deepseek-chat",
                api_key="test_key",
                base_url="https://api.deepseek.com/v1",
                temperature=0.7,
                http_client=None,
            )

    def test_deepseek_create_model_no_api_key(self):
        """测试无 API Key 时创建 DeepSeek 模型."""
        provider = DeepSeekProvider()
        mock_config = Mock(
            deepseek_api_key=None,
            deepseek_model="deepseek-chat",
            deepseek_base_url="https://api.deepseek.com/v1",
            temperature=0.7,
        )

        with pytest.raises(ConfigurationError):
            provider.create_model(mock_config)


class TestOllamaProvider:
    """OllamaProvider 测试."""

    def test_ollama_provider_initialization(self):
        """测试 OllamaProvider 初始化."""
        provider = OllamaProvider()

        assert provider.name == "ollama"
        assert provider.requires_api_key is False
        assert provider.api_key_setting == ""
        assert provider.model_setting == "ollama_model"
        assert provider.base_url_setting == "ollama_base_url"

    def test_ollama_is_available(self):
        """测试 Ollama 总是可用."""
        provider = OllamaProvider()
        mock_config = Mock()

        assert provider.is_available(mock_config) is True

    def test_ollama_create_model(self):
        """测试创建 Ollama 模型."""
        provider = OllamaProvider()
        mock_config = Mock(
            ollama_model="llama3",
            ollama_base_url="http://localhost:11434",
            temperature=0.7,
        )

        with patch("ut_agent.utils.llm.ChatOllama") as mock_chat_ollama:
            mock_model = Mock()
            mock_chat_ollama.return_value = mock_model

            model = provider.create_model(mock_config)

            mock_chat_ollama.assert_called_once_with(
                model="llama3",
                base_url="http://localhost:11434",
                temperature=0.7,
            )


class TestLLMProviderRegistry:
    """LLMProviderRegistry 测试."""

    def setup_method(self):
        """设置测试环境."""
        # 保存原始提供商
        self.original_providers = LLMProviderRegistry._providers.copy()
        # 清空注册表
        LLMProviderRegistry._providers.clear()

    def teardown_method(self):
        """清理测试环境."""
        # 恢复原始提供商
        LLMProviderRegistry._providers.clear()
        LLMProviderRegistry._providers.update(self.original_providers)

    def test_register(self):
        """测试注册提供商."""
        class TestProvider(LLMProvider):
            name = "test"
            
            def create_model(self, config):
                pass
            
            def is_available(self, config):
                pass

        provider = TestProvider()
        LLMProviderRegistry.register(provider)

        assert "test" in LLMProviderRegistry._providers
        assert LLMProviderRegistry._providers["test"] == provider

    def test_get_existing(self):
        """测试获取已注册的提供商."""
        class TestProvider(LLMProvider):
            name = "test"
            
            def create_model(self, config):
                pass
            
            def is_available(self, config):
                pass

        provider = TestProvider()
        LLMProviderRegistry.register(provider)

        retrieved = LLMProviderRegistry.get("test")
        assert retrieved == provider

    def test_get_nonexistent(self):
        """测试获取不存在的提供商."""
        assert LLMProviderRegistry.get("nonexistent") is None

    def test_list_available(self):
        """测试列出可用提供商."""
        class AvailableProvider(LLMProvider):
            name = "available"
            
            def create_model(self, config):
                pass
            
            def is_available(self, config):
                return True

        class UnavailableProvider(LLMProvider):
            name = "unavailable"
            
            def create_model(self, config):
                pass
            
            def is_available(self, config):
                return False

        LLMProviderRegistry.register(AvailableProvider())
        LLMProviderRegistry.register(UnavailableProvider())

        mock_config = Mock()
        available = LLMProviderRegistry.list_available(mock_config)

        assert "available" in available
        assert "unavailable" not in available

    def test_list_all(self):
        """测试列出所有提供商."""
        class TestProvider1(LLMProvider):
            name = "test1"
            
            def create_model(self, config):
                pass
            
            def is_available(self, config):
                pass

        class TestProvider2(LLMProvider):
            name = "test2"
            
            def create_model(self, config):
                pass
            
            def is_available(self, config):
                pass

        LLMProviderRegistry.register(TestProvider1())
        LLMProviderRegistry.register(TestProvider2())

        all_providers = LLMProviderRegistry.list_all()

        assert "test1" in all_providers
        assert "test2" in all_providers
        assert len(all_providers) == 2


class TestRegisterProvider:
    """register_provider 函数测试."""

    def setup_method(self):
        """设置测试环境."""
        self.original_providers = LLMProviderRegistry._providers.copy()

    def teardown_method(self):
        """清理测试环境."""
        LLMProviderRegistry._providers.clear()
        LLMProviderRegistry._providers.update(self.original_providers)

    def test_register_provider(self):
        """测试注册提供商."""
        class TestProvider(LLMProvider):
            name = "custom"
            
            def create_model(self, config):
                pass
            
            def is_available(self, config):
                return True

        provider = TestProvider()
        register_provider(provider)

        assert "custom" in LLMProviderRegistry._providers
        assert LLMProviderRegistry._providers["custom"] == provider


class TestGetLLM:
    """get_llm 函数测试."""

    @patch("ut_agent.utils.llm_cache.get_cached_llm")
    def test_get_llm_default_provider(self, mock_get_cached):
        """测试获取默认提供商的 LLM."""
        mock_model = Mock()
        mock_get_cached.return_value = mock_model

        # 保存原始默认提供商
        original_default = settings.default_llm_provider
        settings.default_llm_provider = "ollama"  # Ollama 不需要 API Key

        try:
            model = get_llm()
            assert model == mock_model
            mock_get_cached.assert_called_once()
        finally:
            settings.default_llm_provider = original_default

    @patch("ut_agent.utils.llm_cache.get_cached_llm")
    def test_get_llm_specific_provider(self, mock_get_cached):
        """测试获取指定提供商的 LLM."""
        mock_model = Mock()
        mock_get_cached.return_value = mock_model

        model = get_llm(provider="ollama")
        assert model == mock_model
        mock_get_cached.assert_called_once()

    def test_get_llm_nonexistent_provider(self):
        """测试获取不存在的提供商."""
        with pytest.raises(LLMError, match="不支持的 LLM 提供商"):
            get_llm(provider="nonexistent")

    def test_get_llm_unavailable_provider(self):
        """测试获取不可用的提供商."""
        # 保存原始 API Key
        original_key = settings.openai_api_key
        settings.openai_api_key = None  # 使 OpenAI 不可用

        try:
            with pytest.raises(ConfigurationError, match="不可用，请检查配置"):
                get_llm(provider="openai")
        finally:
            settings.openai_api_key = original_key


class TestListAvailableProviders:
    """list_available_providers 函数测试."""

    def test_list_available_providers(self):
        """测试列出可用提供商."""
        providers = list_available_providers()
        assert isinstance(providers, list)
        # 至少应该包含 ollama
        assert "ollama" in providers
