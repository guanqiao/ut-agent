"""Anthropic Claude LLM 提供商测试."""

import pytest
import os
from unittest.mock import Mock, patch, AsyncMock
from typing import AsyncGenerator

from ut_agent.utils.llm_providers.claude import ClaudeProvider, ClaudeConfig


class TestClaudeConfig:
    """Claude 配置测试."""

    def test_default_config(self):
        """测试默认配置."""
        config = ClaudeConfig()
        assert config.model == "claude-3-sonnet-20240229"
        assert config.max_tokens == 4096
        assert config.temperature == 0.7

    def test_custom_config(self):
        """测试自定义配置."""
        config = ClaudeConfig(
            model="claude-3-opus-20240229",
            max_tokens=8192,
            temperature=0.5
        )
        assert config.model == "claude-3-opus-20240229"
        assert config.max_tokens == 8192
        assert config.temperature == 0.5

    def test_config_from_env(self, monkeypatch):
        """测试从环境变量读取配置."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-api-key")
        monkeypatch.setenv("CLAUDE_MODEL", "claude-3-haiku-20240307")
        
        config = ClaudeConfig.from_env()
        assert config.api_key == "test-api-key"
        assert config.model == "claude-3-haiku-20240307"


class TestClaudeProvider:
    """Claude 提供商测试."""

    @pytest.fixture
    def provider(self):
        """创建提供商实例."""
        config = ClaudeConfig(api_key="test-key")
        return ClaudeProvider(config)

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
        assert provider.config.model == "claude-3-sonnet-20240229"

    def test_provider_name(self, provider):
        """测试提供商名称."""
        assert provider.name == "claude"

    def test_format_messages(self, provider, sample_messages):
        """测试消息格式化."""
        formatted = provider._format_messages(sample_messages)
        
        # Claude 使用不同的消息格式
        assert "system" in formatted or any(m.get("role") == "system" for m in formatted)

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
        # 创建一个模拟的异常类
        class MockRateLimitError(Exception):
            pass
        
        with patch.object(provider, '_call_api', new_callable=AsyncMock) as mock_call:
            # 第一次调用失败，第二次成功
            mock_call.side_effect = [
                MockRateLimitError("Rate limit exceeded"),
                "Success after retry"
            ]
            
            result = await provider.generate(sample_messages, max_retries=2)
            assert result == "Success after retry"
            assert mock_call.call_count == 2

    @pytest.mark.asyncio
    async def test_handle_api_error(self, provider, sample_messages):
        """测试处理 API 错误."""
        # 创建一个模拟的异常类
        class MockAPIError(Exception):
            pass
        
        with patch.object(provider, '_call_api', new_callable=AsyncMock) as mock_call:
            mock_call.side_effect = MockAPIError("API Error")
            
            with pytest.raises(Exception):
                await provider.generate(sample_messages, max_retries=1)

    def test_count_tokens(self, provider):
        """测试 Token 计数."""
        text = "Hello, world!"
        tokens = provider.count_tokens(text)
        
        # 应该返回一个正整数
        assert isinstance(tokens, int)
        assert tokens > 0

    def test_estimate_cost(self, provider):
        """测试成本估算."""
        input_tokens = 100
        output_tokens = 50
        
        cost = provider.estimate_cost(input_tokens, output_tokens)
        
        # 应该返回一个非负数
        assert isinstance(cost, float)
        assert cost >= 0

    def test_validate_config(self):
        """测试配置验证."""
        # 有效配置
        valid_config = ClaudeConfig(api_key="valid-key")
        assert ClaudeProvider.validate_config(valid_config) is True
        
        # 无效配置（空 API key）
        invalid_config = ClaudeConfig(api_key="")
        assert ClaudeProvider.validate_config(invalid_config) is False

    @pytest.mark.asyncio
    async def test_generate_with_tools(self, provider):
        """测试使用工具/函数调用生成."""
        messages = [{"role": "user", "content": "What's the weather?"}]
        tools = [
            {
                "name": "get_weather",
                "description": "Get weather for a location",
                "parameters": {
                    "location": {"type": "string"}
                }
            }
        ]
        
        with patch.object(provider, '_call_api', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = {
                "content": "I'll check the weather for you.",
                "tool_calls": [{"name": "get_weather", "arguments": {"location": "Beijing"}}]
            }
            
            result = await provider.generate(messages, tools=tools)
            
            assert "tool_calls" in result or isinstance(result, dict)


class TestClaudeProviderIntegration:
    """Claude 提供商集成测试."""

    @pytest.mark.skipif(
        not os.getenv("ANTHROPIC_API_KEY"),
        reason="ANTHROPIC_API_KEY not set"
    )
    @pytest.mark.asyncio
    async def test_real_api_call(self):
        """测试真实 API 调用（需要 API key）."""
        config = ClaudeConfig.from_env()
        provider = ClaudeProvider(config)
        
        messages = [{"role": "user", "content": "Say 'Hello, World!'"}]
        result = await provider.generate(messages)
        
        assert isinstance(result, str)
        assert len(result) > 0
        assert "Hello" in result or "World" in result

    @pytest.mark.skipif(
        not os.getenv("ANTHROPIC_API_KEY"),
        reason="ANTHROPIC_API_KEY not set"
    )
    @pytest.mark.asyncio
    async def test_real_streaming(self):
        """测试真实流式 API 调用."""
        config = ClaudeConfig.from_env()
        provider = ClaudeProvider(config)
        
        messages = [{"role": "user", "content": "Count from 1 to 3"}]
        
        chunks = []
        async for chunk in provider.generate_stream(messages):
            chunks.append(chunk)
        
        assert len(chunks) > 0
        full_text = "".join(chunks)
        assert len(full_text) > 0
