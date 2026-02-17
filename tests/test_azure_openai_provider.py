"""Azure OpenAI LLM 提供商测试."""

import pytest
import os
from unittest.mock import Mock, patch, AsyncMock
from typing import AsyncGenerator

from ut_agent.utils.llm_providers.azure_openai import AzureOpenAIProvider, AzureOpenAIConfig


class TestAzureOpenAIConfig:
    """Azure OpenAI 配置测试."""

    def test_default_config(self):
        """测试默认配置."""
        config = AzureOpenAIConfig(
            api_key="test-key",
            endpoint="https://test.openai.azure.com"
        )
        assert config.model == "gpt-4"
        assert config.api_version == "2024-02-01"
        assert config.max_tokens == 4096

    def test_custom_config(self):
        """测试自定义配置."""
        config = AzureOpenAIConfig(
            api_key="test-key",
            endpoint="https://custom.openai.azure.com",
            model="gpt-4-turbo",
            api_version="2024-05-01-preview",
            max_tokens=8192
        )
        assert config.model == "gpt-4-turbo"
        assert config.api_version == "2024-05-01-preview"
        assert config.max_tokens == 8192

    def test_config_from_env(self, monkeypatch):
        """测试从环境变量读取配置."""
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-api-key")
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com")
        monkeypatch.setenv("AZURE_OPENAI_MODEL", "gpt-4")
        
        config = AzureOpenAIConfig.from_env()
        assert config.api_key == "test-api-key"
        assert config.endpoint == "https://test.openai.azure.com"
        assert config.model == "gpt-4"

    def test_deployment_config(self):
        """测试部署配置."""
        config = AzureOpenAIConfig(
            api_key="test-key",
            endpoint="https://test.openai.azure.com",
            deployment_name="my-gpt4-deployment"
        )
        assert config.deployment_name == "my-gpt4-deployment"


class TestAzureOpenAIProvider:
    """Azure OpenAI 提供商测试."""

    @pytest.fixture
    def provider(self):
        """创建提供商实例."""
        config = AzureOpenAIConfig(
            api_key="test-key",
            endpoint="https://test.openai.azure.com"
        )
        return AzureOpenAIProvider(config)

    @pytest.fixture
    def sample_messages(self):
        """示例消息."""
        return [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello!"}
        ]

    def test_provider_initialization(self, provider):
        """测试提供商初始化."""
        assert provider.config.api_key == "test-key"
        assert provider.config.endpoint == "https://test.openai.azure.com"
        assert provider.config.model == "gpt-4"

    def test_provider_name(self, provider):
        """测试提供商名称."""
        assert provider.name == "azure_openai"

    def test_get_deployment_name(self, provider):
        """测试获取部署名称."""
        # 如果没有指定 deployment_name，应该使用 model 名称
        assert provider._get_deployment_name() == "gpt-4"
        
        # 如果指定了 deployment_name
        provider.config.deployment_name = "custom-deployment"
        assert provider._get_deployment_name() == "custom-deployment"

    def test_build_url(self, provider):
        """测试构建 API URL."""
        url = provider._build_url()
        assert "https://test.openai.azure.com" in url
        assert "openai/deployments/gpt-4" in url
        assert "api-version=2024-02-01" in url

    @pytest.mark.asyncio
    async def test_generate(self, provider, sample_messages):
        """测试生成文本."""
        with patch.object(provider, '_call_api', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = "Hello! How can I help you today?"
            
            result = await provider.generate(sample_messages)
            
            assert result == "Hello! How can I help you today?"
            mock_call.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_stream(self, provider, sample_messages):
        """测试流式生成."""
        async def mock_stream():
            chunks = ["Hello", "! ", "How", " can", " I", " help", " you?"]
            for chunk in chunks:
                yield chunk
        
        with patch.object(provider, '_call_api_stream', return_value=mock_stream()):
            chunks = []
            async for chunk in provider.generate_stream(sample_messages):
                chunks.append(chunk)
            
            assert len(chunks) > 0
            assert "".join(chunks) == "Hello! How can I help you?"

    @pytest.mark.asyncio
    async def test_handle_rate_limit(self, provider, sample_messages):
        """测试处理速率限制."""
        class MockRateLimitError(Exception):
            pass
        
        with patch.object(provider, '_call_api', new_callable=AsyncMock) as mock_call:
            mock_call.side_effect = [
                MockRateLimitError("Rate limit exceeded"),
                "Success after retry"
            ]
            
            result = await provider.generate(sample_messages, max_retries=2)
            assert result == "Success after retry"
            assert mock_call.call_count == 2

    @pytest.mark.asyncio
    async def test_handle_auth_error(self, provider, sample_messages):
        """测试处理认证错误."""
        class MockAuthError(Exception):
            pass
        
        with patch.object(provider, '_call_api', new_callable=AsyncMock) as mock_call:
            mock_call.side_effect = MockAuthError("Authentication failed")
            
            with pytest.raises(Exception):
                await provider.generate(sample_messages, max_retries=1)

    def test_count_tokens(self, provider):
        """测试 Token 计数."""
        text = "Hello, world!"
        tokens = provider.count_tokens(text)
        
        assert isinstance(tokens, int)
        assert tokens > 0

    def test_estimate_cost(self, provider):
        """测试成本估算."""
        input_tokens = 100
        output_tokens = 50
        
        cost = provider.estimate_cost(input_tokens, output_tokens)
        
        assert isinstance(cost, float)
        assert cost >= 0

    def test_validate_config(self):
        """测试配置验证."""
        # 有效配置
        valid_config = AzureOpenAIConfig(
            api_key="valid-key",
            endpoint="https://test.openai.azure.com"
        )
        assert AzureOpenAIProvider.validate_config(valid_config) is True
        
        # 无效配置（空 API key）
        invalid_config = AzureOpenAIConfig(
            api_key="",
            endpoint="https://test.openai.azure.com"
        )
        assert AzureOpenAIProvider.validate_config(invalid_config) is False
        
        # 无效配置（空 endpoint）
        invalid_config2 = AzureOpenAIConfig(
            api_key="valid-key",
            endpoint=""
        )
        assert AzureOpenAIProvider.validate_config(invalid_config2) is False

    @pytest.mark.asyncio
    async def test_generate_with_functions(self, provider):
        """测试使用函数调用生成."""
        messages = [{"role": "user", "content": "What's the weather?"}]
        functions = [
            {
                "name": "get_weather",
                "description": "Get weather for a location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string"}
                    }
                }
            }
        ]
        
        with patch.object(provider, '_call_api', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = {
                "content": "I'll check the weather for you.",
                "function_call": {"name": "get_weather", "arguments": '{"location": "Beijing"}'}
            }
            
            result = await provider.generate(messages, functions=functions)
            
            assert "function_call" in result or isinstance(result, dict)

    def test_region_selection(self):
        """测试区域选择."""
        config = AzureOpenAIConfig(
            api_key="test-key",
            endpoint="https://test.openai.azure.com",
            region="eastus"
        )
        provider = AzureOpenAIProvider(config)
        
        # 区域应该影响端点选择
        assert provider.config.region == "eastus"


class TestAzureOpenAIProviderIntegration:
    """Azure OpenAI 提供商集成测试."""

    @pytest.mark.skipif(
        not os.getenv("AZURE_OPENAI_API_KEY") or not os.getenv("AZURE_OPENAI_ENDPOINT"),
        reason="AZURE_OPENAI_API_KEY or AZURE_OPENAI_ENDPOINT not set"
    )
    @pytest.mark.asyncio
    async def test_real_api_call(self):
        """测试真实 API 调用（需要 API key）."""
        config = AzureOpenAIConfig.from_env()
        provider = AzureOpenAIProvider(config)
        
        messages = [{"role": "user", "content": "Say 'Hello, World!'"}]
        result = await provider.generate(messages)
        
        assert isinstance(result, str)
        assert len(result) > 0
        assert "Hello" in result or "World" in result

    @pytest.mark.skipif(
        not os.getenv("AZURE_OPENAI_API_KEY") or not os.getenv("AZURE_OPENAI_ENDPOINT"),
        reason="AZURE_OPENAI_API_KEY or AZURE_OPENAI_ENDPOINT not set"
    )
    @pytest.mark.asyncio
    async def test_real_streaming(self):
        """测试真实流式 API 调用."""
        config = AzureOpenAIConfig.from_env()
        provider = AzureOpenAIProvider(config)
        
        messages = [{"role": "user", "content": "Count from 1 to 3"}]
        
        chunks = []
        async for chunk in provider.generate_stream(messages):
            chunks.append(chunk)
        
        assert len(chunks) > 0
        full_text = "".join(chunks)
        assert len(full_text) > 0
