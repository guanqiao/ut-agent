"""异步 LLM 调用器测试模块."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage

from ut_agent.exceptions import LLMError, LLMRateLimitError, LLMResponseError
from ut_agent.utils.async_llm import (
    AsyncLLMCaller,
    LLMCallConfig,
    LLMCallResult,
    LLMCallStatus,
)


class MockChatModel(BaseChatModel):
    """测试用 Mock Chat Model."""

    @property
    def _llm_type(self) -> str:
        return "mock"

    def __init__(
        self,
        should_fail: bool = False,
        should_rate_limit: bool = False,
        response_delay: float = 0.1,
        response_content: str = "Test response",
    ):
        super().__init__()
        self._should_fail = should_fail
        self._should_rate_limit = should_rate_limit
        self._response_delay = response_delay
        self._response_content = response_content
        self._call_count = 0
        self._last_prompt: Optional[str] = None

    def _generate(
        self,
        messages: List[Any],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> Any:
        from langchain_core.outputs import ChatResult, ChatGeneration

        self._call_count += 1
        if messages:
            self._last_prompt = str(messages[-1].content) if hasattr(messages[-1], "content") else str(messages[-1])

        if self._should_rate_limit:
            raise Exception("Rate limit exceeded")

        if self._should_fail:
            raise Exception("Mock LLM error")

        return ChatResult(
            generations=[
                ChatGeneration(message=AIMessage(content=self._response_content))
            ]
        )

    async def _agenerate(
        self,
        messages: List[Any],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> Any:
        if self._response_delay > 0:
            await asyncio.sleep(self._response_delay)

        return self._generate(messages, stop, run_manager, **kwargs)


class TestLLMCallConfig:
    """LLMCallConfig 测试."""

    def test_default_config(self):
        """测试默认配置."""
        config = LLMCallConfig()
        assert config.max_retries == 3
        assert config.retry_delay == 1.0
        assert config.timeout == 60
        assert config.exponential_backoff is True
        assert config.max_retry_delay == 30.0

    def test_custom_config(self):
        """测试自定义配置."""
        config = LLMCallConfig(
            max_retries=5,
            retry_delay=2.0,
            timeout=120,
            exponential_backoff=False,
            max_retry_delay=60.0,
        )
        assert config.max_retries == 5
        assert config.retry_delay == 2.0
        assert config.timeout == 120
        assert config.exponential_backoff is False
        assert config.max_retry_delay == 60.0

    def test_validate_config(self):
        """测试配置验证."""
        with pytest.raises(ValueError):
            LLMCallConfig(max_retries=-1)

        with pytest.raises(ValueError):
            LLMCallConfig(timeout=-1)


class TestLLMCallResult:
    """LLMCallResult 测试."""

    def test_success_result(self):
        """测试成功结果."""
        result = LLMCallResult(
            status=LLMCallStatus.SUCCESS,
            content="Test response",
            prompt_tokens=100,
            completion_tokens=50,
        )
        assert result.status == LLMCallStatus.SUCCESS
        assert result.content == "Test response"
        assert result.success is True
        assert result.total_tokens == 150

    def test_failed_result(self):
        """测试失败结果."""
        result = LLMCallResult(
            status=LLMCallStatus.FAILED,
            errors=["Error message"],
        )
        assert result.status == LLMCallStatus.FAILED
        assert result.success is False
        assert len(result.errors) == 1

    def test_timeout_result(self):
        """测试超时结果."""
        result = LLMCallResult(
            status=LLMCallStatus.TIMEOUT,
        )
        assert result.status == LLMCallStatus.TIMEOUT
        assert result.success is False

    def test_rate_limited_result(self):
        """测试速率限制结果."""
        result = LLMCallResult(
            status=LLMCallStatus.RATE_LIMITED,
            retry_after=60,
        )
        assert result.status == LLMCallStatus.RATE_LIMITED
        assert result.retry_after == 60


class TestAsyncLLMCaller:
    """AsyncLLMCaller 测试."""

    @pytest.fixture
    def mock_llm(self):
        """创建 Mock LLM."""
        return MockChatModel()

    @pytest.fixture
    def caller(self, mock_llm):
        """创建调用器实例."""
        return AsyncLLMCaller(mock_llm)

    def test_caller_initialization(self, mock_llm):
        """测试调用器初始化."""
        caller = AsyncLLMCaller(mock_llm)
        assert caller._llm == mock_llm
        assert caller._config is not None
        assert caller._call_history == []

    @pytest.mark.asyncio
    async def test_call_success(self, caller, mock_llm):
        """测试成功调用."""
        result = await caller.call("Test prompt")

        assert result.status == LLMCallStatus.SUCCESS
        assert result.content == "Test response"
        assert result.success is True
        assert mock_llm._call_count == 1

    @pytest.mark.asyncio
    async def test_call_with_messages(self, caller, mock_llm):
        """测试使用消息列表调用."""
        messages = [
            HumanMessage(content="Hello"),
            AIMessage(content="Hi there!"),
            HumanMessage(content="How are you?"),
        ]

        result = await caller.call_with_messages(messages)

        assert result.status == LLMCallStatus.SUCCESS
        assert result.content == "Test response"

    @pytest.mark.asyncio
    async def test_call_with_failure(self, mock_llm):
        """测试调用失败."""
        mock_llm._should_fail = True
        caller = AsyncLLMCaller(mock_llm, config=LLMCallConfig(max_retries=1))

        result = await caller.call("Test prompt")

        assert result.status == LLMCallStatus.FAILED
        assert result.success is False
        assert len(result.errors) > 0

    @pytest.mark.asyncio
    async def test_call_with_timeout(self, mock_llm):
        """测试调用超时."""
        mock_llm._response_delay = 5.0
        caller = AsyncLLMCaller(
            mock_llm,
            config=LLMCallConfig(timeout=0.1, max_retries=1),
        )

        result = await caller.call("Test prompt")

        assert result.status == LLMCallStatus.TIMEOUT

    @pytest.mark.asyncio
    async def test_call_with_retry(self, mock_llm):
        """测试重试机制."""
        fail_count = 0

        class FlakeyLLM(MockChatModel):
            async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
                nonlocal fail_count
                fail_count += 1
                if fail_count < 3:
                    raise Exception("Temporary error")
                return await super()._agenerate(messages, stop, run_manager, **kwargs)

        flakey_llm = FlakeyLLM()
        caller = AsyncLLMCaller(
            flakey_llm,
            config=LLMCallConfig(max_retries=3, retry_delay=0.1),
        )

        result = await caller.call("Test prompt")

        assert result.status == LLMCallStatus.SUCCESS
        assert fail_count == 3

    @pytest.mark.asyncio
    async def test_call_with_exponential_backoff(self, mock_llm):
        """测试指数退避."""
        mock_llm._should_fail = True
        caller = AsyncLLMCaller(
            mock_llm,
            config=LLMCallConfig(
                max_retries=3,
                retry_delay=0.1,
                exponential_backoff=True,
                max_retry_delay=1.0,
            ),
        )

        start_time = datetime.now()
        await caller.call("Test prompt")
        end_time = datetime.now()

        elapsed = (end_time - start_time).total_seconds()
        assert elapsed >= 0.1 + 0.2 + 0.4

    @pytest.mark.asyncio
    async def test_call_with_rate_limit(self, mock_llm):
        """测试速率限制处理."""
        mock_llm._should_rate_limit = True
        caller = AsyncLLMCaller(
            mock_llm,
            config=LLMCallConfig(max_retries=1),
        )

        result = await caller.call("Test prompt")

        assert result.status == LLMCallStatus.RATE_LIMITED

    @pytest.mark.asyncio
    async def test_call_history(self, caller, mock_llm):
        """测试调用历史记录."""
        await caller.call("Prompt 1")
        await caller.call("Prompt 2")

        history = caller.get_call_history()
        assert len(history) == 2

    @pytest.mark.asyncio
    async def test_call_history_limit(self, mock_llm):
        """测试调用历史记录限制."""
        caller = AsyncLLMCaller(mock_llm)

        for i in range(150):
            await caller.call(f"Prompt {i}")

        history = caller.get_call_history()
        assert len(history) == 100

    def test_clear_history(self, caller):
        """测试清除历史记录."""
        caller._call_history = [
            LLMCallResult(status=LLMCallStatus.SUCCESS, content="test")
        ]

        caller.clear_history()
        assert len(caller._call_history) == 0

    @pytest.mark.asyncio
    async def test_batch_call(self, caller, mock_llm):
        """测试批量调用."""
        prompts = ["Prompt 1", "Prompt 2", "Prompt 3"]

        results = await caller.batch_call(prompts)

        assert len(results) == 3
        assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_batch_call_with_concurrency_limit(self, mock_llm):
        """测试批量调用并发限制."""
        mock_llm._response_delay = 0.1
        caller = AsyncLLMCaller(
            mock_llm,
            config=LLMCallConfig(max_concurrent_calls=2),
        )

        prompts = ["Prompt 1", "Prompt 2", "Prompt 3", "Prompt 4"]

        start_time = datetime.now()
        results = await caller.batch_call(prompts)
        end_time = datetime.now()

        elapsed = (end_time - start_time).total_seconds()
        assert elapsed >= 0.2
        assert len(results) == 4

    @pytest.mark.asyncio
    async def test_call_with_system_prompt(self, caller, mock_llm):
        """测试带系统提示的调用."""
        result = await caller.call(
            "Test prompt",
            system_prompt="You are a helpful assistant.",
        )

        assert result.status == LLMCallStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_call_with_temperature(self, caller, mock_llm):
        """测试带温度参数的调用."""
        result = await caller.call(
            "Test prompt",
            temperature=0.5,
        )

        assert result.status == LLMCallStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_get_stats(self, caller, mock_llm):
        """测试获取统计信息."""
        await caller.call("Prompt 1")
        await caller.call("Prompt 2")
        mock_llm._should_fail = True
        await caller.call("Prompt 3")

        stats = caller.get_stats()

        assert stats["total_calls"] == 3
        assert stats["success_count"] == 2
        assert stats["failed_count"] == 1
        assert stats["success_rate"] == 2 / 3


class TestAsyncLLMCallerIntegration:
    """AsyncLLMCaller 集成测试."""

    @pytest.mark.asyncio
    async def test_full_workflow(self):
        """测试完整工作流."""
        mock_llm = MockChatModel()
        caller = AsyncLLMCaller(
            mock_llm,
            config=LLMCallConfig(
                max_retries=3,
                retry_delay=0.1,
                timeout=30,
            ),
        )

        result1 = await caller.call("Generate a test for class A")
        assert result1.success

        result2 = await caller.call("Generate a test for class B")
        assert result2.success

        history = caller.get_call_history()
        assert len(history) == 2

        stats = caller.get_stats()
        assert stats["success_rate"] == 1.0

    @pytest.mark.asyncio
    async def test_error_recovery(self):
        """测试错误恢复."""
        fail_count = 0

        class RecoveringLLM(MockChatModel):
            async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
                nonlocal fail_count
                fail_count += 1
                if fail_count <= 2:
                    raise Exception("Temporary failure")
                return await super()._agenerate(messages, stop, run_manager, **kwargs)

        mock_llm = RecoveringLLM()
        caller = AsyncLLMCaller(
            mock_llm,
            config=LLMCallConfig(max_retries=5, retry_delay=0.1),
        )

        result = await caller.call("Test prompt")

        assert result.success
        assert fail_count == 3
