"""AWS Bedrock LLM 提供商测试."""

import pytest
import os
from unittest.mock import Mock, patch, AsyncMock
from typing import AsyncGenerator

from ut_agent.utils.llm_providers.bedrock import BedrockProvider, BedrockConfig


class TestBedrockConfig:
    """Bedrock 配置测试."""

    def test_default_config(self):
        """测试默认配置."""
        config = BedrockConfig(
            aws_access_key_id="test-key",
            aws_secret_access_key="test-secret"
        )
        assert config.model_id == "anthropic.claude-3-sonnet-20240229-v1:0"
        assert config.region == "us-east-1"
        assert config.max_tokens == 4096

    def test_custom_config(self):
        """测试自定义配置."""
        config = BedrockConfig(
            aws_access_key_id="test-key",
            aws_secret_access_key="test-secret",
            model_id="anthropic.claude-3-opus-20240229-v1:0",
            region="us-west-2",
            max_tokens=8192
        )
        assert config.model_id == "anthropic.claude-3-opus-20240229-v1:0"
        assert config.region == "us-west-2"
        assert config.max_tokens == 8192

    def test_config_from_env(self, monkeypatch):
        """测试从环境变量读取配置."""
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test-key")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test-secret")
        monkeypatch.setenv("AWS_REGION", "eu-west-1")
        monkeypatch.setenv("BEDROCK_MODEL_ID", "meta.llama3-70b-instruct-v1:0")
        
        config = BedrockConfig.from_env()
        assert config.aws_access_key_id == "test-key"
        assert config.region == "eu-west-1"
        assert config.model_id == "meta.llama3-70b-instruct-v1:0"

    def test_iam_role_config(self):
        """测试 IAM 角色配置."""
        config = BedrockConfig(
            use_iam_role=True,
            region="us-east-1"
        )
        assert config.use_iam_role is True
        assert config.aws_access_key_id is None


class TestBedrockProvider:
    """Bedrock 提供商测试."""

    @pytest.fixture
    def provider(self):
        """创建提供商实例."""
        config = BedrockConfig(
            aws_access_key_id="test-key",
            aws_secret_access_key="test-secret",
            region="us-east-1"
        )
        return BedrockProvider(config)

    @pytest.fixture
    def sample_messages(self):
        """示例消息."""
        return [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello!"}
        ]

    def test_provider_initialization(self, provider):
        """测试提供商初始化."""
        assert provider.config.aws_access_key_id == "test-key"
        assert provider.config.region == "us-east-1"

    def test_provider_name(self, provider):
        """测试提供商名称."""
        assert provider.name == "bedrock"

    def test_get_model_family(self, provider):
        """测试获取模型家族."""
        # Claude 模型
        provider.config.model_id = "anthropic.claude-3-sonnet-20240229-v1:0"
        assert provider._get_model_family() == "claude"
        
        # Llama 模型
        provider.config.model_id = "meta.llama3-70b-instruct-v1:0"
        assert provider._get_model_family() == "llama"
        
        # Mistral 模型
        provider.config.model_id = "mistral.mistral-large-2402-v1:0"
        assert provider._get_model_family() == "mistral"

    def test_format_messages_for_claude(self, provider, sample_messages):
        """测试为 Claude 格式化消息."""
        provider.config.model_id = "anthropic.claude-3-sonnet-20240229-v1:0"
        formatted = provider._format_messages(sample_messages)
        
        assert "anthropic_version" in formatted
        assert "messages" in formatted

    def test_format_messages_for_llama(self, provider, sample_messages):
        """测试为 Llama 格式化消息."""
        provider.config.model_id = "meta.llama3-70b-instruct-v1:0"
        formatted = provider._format_messages(sample_messages)
        
        assert "prompt" in formatted or "messages" in formatted

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
    async def test_handle_throttling(self, provider, sample_messages):
        """测试处理限流."""
        class MockThrottlingError(Exception):
            pass
        
        with patch.object(provider, '_call_api', new_callable=AsyncMock) as mock_call:
            mock_call.side_effect = [
                MockThrottlingError("ThrottlingException"),
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
            mock_call.side_effect = MockAuthError("AccessDeniedException")
            
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

    def test_validate_config_with_keys(self):
        """测试使用密钥验证配置."""
        valid_config = BedrockConfig(
            aws_access_key_id="valid-key",
            aws_secret_access_key="valid-secret",
            region="us-east-1"
        )
        assert BedrockProvider.validate_config(valid_config) is True

    def test_validate_config_with_iam_role(self):
        """测试使用 IAM 角色验证配置."""
        valid_config = BedrockConfig(
            use_iam_role=True,
            region="us-east-1"
        )
        assert BedrockProvider.validate_config(valid_config) is True

    def test_validate_config_invalid(self):
        """测试无效配置."""
        # 没有密钥也没有 IAM 角色
        invalid_config = BedrockConfig(region="us-east-1")
        assert BedrockProvider.validate_config(invalid_config) is False

    def test_supported_models(self, provider):
        """测试支持的模型列表."""
        models = provider.get_supported_models()
        
        assert isinstance(models, list)
        assert len(models) > 0
        # 应该包含 Claude 模型
        assert any("claude" in m for m in models)

    def test_model_pricing(self, provider):
        """测试模型定价."""
        # Claude 定价
        provider.config.model_id = "anthropic.claude-3-sonnet-20240229-v1:0"
        cost = provider.estimate_cost(1000, 500)
        assert cost > 0


class TestBedrockProviderIntegration:
    """Bedrock 提供商集成测试."""

    @pytest.mark.skipif(
        not os.getenv("AWS_ACCESS_KEY_ID") or not os.getenv("AWS_SECRET_ACCESS_KEY"),
        reason="AWS credentials not set"
    )
    @pytest.mark.asyncio
    async def test_real_api_call(self):
        """测试真实 API 调用（需要 AWS 凭证）."""
        config = BedrockConfig.from_env()
        provider = BedrockProvider(config)
        
        messages = [{"role": "user", "content": "Say 'Hello, World!'"}]
        result = await provider.generate(messages)
        
        assert isinstance(result, str)
        assert len(result) > 0
        assert "Hello" in result or "World" in result

    @pytest.mark.skipif(
        not os.getenv("AWS_ACCESS_KEY_ID") or not os.getenv("AWS_SECRET_ACCESS_KEY"),
        reason="AWS credentials not set"
    )
    @pytest.mark.asyncio
    async def test_real_streaming(self):
        """测试真实流式 API 调用."""
        config = BedrockConfig.from_env()
        provider = BedrockProvider(config)
        
        messages = [{"role": "user", "content": "Count from 1 to 3"}]
        
        chunks = []
        async for chunk in provider.generate_stream(messages):
            chunks.append(chunk)
        
        assert len(chunks) > 0
        full_text = "".join(chunks)
        assert len(full_text) > 0
