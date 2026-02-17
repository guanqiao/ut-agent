"""错误处理器测试模块."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ut_agent.exceptions import (
    UTAgentError,
    LLMError,
    LLMRateLimitError,
    CodeAnalysisError,
    TestGenerationError,
    RetryableError,
)
from ut_agent.utils.error_handler import (
    ErrorHandler,
    ErrorContext,
    ErrorRecord,
    ErrorSeverity,
    RecoveryAction,
    RecoveryStrategy,
)


class TestErrorContext:
    """ErrorContext 测试."""

    def test_context_creation(self):
        """测试上下文创建."""
        context = ErrorContext(
            node_name="test_node",
            operation="test_operation",
            input_data={"key": "value"},
        )
        assert context.node_name == "test_node"
        assert context.operation == "test_operation"
        assert context.input_data == {"key": "value"}
        assert context.trace_id is not None

    def test_context_with_parent(self):
        """测试带父上下文的创建."""
        parent = ErrorContext(node_name="parent", operation="parent_op")
        child = ErrorContext(
            node_name="child",
            operation="child_op",
            parent_trace_id=parent.trace_id,
        )
        assert child.parent_trace_id == parent.trace_id

    def test_context_to_dict(self):
        """测试上下文转换为字典."""
        context = ErrorContext(
            node_name="test_node",
            operation="test_operation",
            extra={"extra_key": "extra_value"},
        )
        result = context.to_dict()

        assert result["node_name"] == "test_node"
        assert result["operation"] == "test_operation"
        assert result["extra"]["extra_key"] == "extra_value"


class TestErrorRecord:
    """ErrorRecord 测试."""

    def test_record_creation(self):
        """测试记录创建."""
        error = UTAgentError("Test error", details={"key": "value"})
        context = ErrorContext(node_name="test", operation="op")

        record = ErrorRecord(
            error=error,
            context=context,
            severity=ErrorSeverity.HIGH,
        )

        assert record.error == error
        assert record.context == context
        assert record.severity == ErrorSeverity.HIGH
        assert record.timestamp is not None

    def test_record_to_dict(self):
        """测试记录转换为字典."""
        error = UTAgentError("Test error")
        context = ErrorContext(node_name="test", operation="op")

        record = ErrorRecord(
            error=error,
            context=context,
            severity=ErrorSeverity.MEDIUM,
        )

        result = record.to_dict()

        assert result["error"]["message"] == "Test error"
        assert result["context"]["node_name"] == "test"
        assert result["severity"] == "medium"


class TestRecoveryStrategy:
    """RecoveryStrategy 测试."""

    @pytest.mark.asyncio
    async def test_retry_strategy(self):
        """测试重试策略."""
        call_count = 0

        async def operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary error")
            return "success"

        strategy = RecoveryStrategy(
            action=RecoveryAction.RETRY,
            max_retries=3,
            retry_delay=0.1,
        )

        result = await strategy.execute(operation)

        assert result.success
        assert result.result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_skip_strategy(self):
        """测试跳过策略."""
        async def operation():
            raise ValueError("Error")

        strategy = RecoveryStrategy(action=RecoveryAction.SKIP)

        result = await strategy.execute(operation)

        assert result.success
        assert result.skipped

    @pytest.mark.asyncio
    async def test_fail_strategy(self):
        """测试失败策略."""
        async def operation():
            raise ValueError("Error")

        strategy = RecoveryStrategy(action=RecoveryAction.FAIL)

        result = await strategy.execute(operation)

        assert not result.success
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_fallback_strategy(self):
        """测试降级策略."""
        async def operation():
            raise ValueError("Error")

        async def fallback():
            return "fallback_result"

        strategy = RecoveryStrategy(
            action=RecoveryAction.FALLBACK,
            fallback_func=fallback,
        )

        result = await strategy.execute(operation)

        assert result.success
        assert result.result == "fallback_result"


class TestErrorHandler:
    """ErrorHandler 测试."""

    @pytest.fixture
    def handler(self):
        """创建处理器实例."""
        return ErrorHandler()

    @pytest.fixture
    def context(self):
        """创建测试上下文."""
        return ErrorContext(node_name="test_node", operation="test_op")

    def test_handler_initialization(self, handler):
        """测试处理器初始化."""
        assert handler._error_records == []
        assert handler._strategies != {}

    def test_register_strategy(self, handler):
        """测试注册策略."""
        strategy = RecoveryStrategy(action=RecoveryAction.SKIP)

        handler.register_strategy(ValueError, strategy)

        assert ValueError in handler._strategies
        assert handler._strategies[ValueError] == strategy

    @pytest.mark.asyncio
    async def test_handle_error_with_retry(self, handler, context):
        """测试处理错误并重试."""
        call_count = 0

        async def operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary error")
            return "success"

        strategy = RecoveryStrategy(
            action=RecoveryAction.RETRY,
            max_retries=3,
            retry_delay=0.1,
        )
        handler.register_strategy(ValueError, strategy)

        result = await handler.handle(operation, context)

        assert result.success
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_handle_error_with_skip(self, handler, context):
        """测试处理错误并跳过."""
        async def operation():
            raise ValueError("Skip this")

        strategy = RecoveryStrategy(action=RecoveryAction.SKIP)
        handler.register_strategy(ValueError, strategy)

        result = await handler.handle(operation, context)

        assert result.success
        assert result.skipped

    @pytest.mark.asyncio
    async def test_handle_error_with_fallback(self, handler, context):
        """测试处理错误并降级."""
        async def operation():
            raise ValueError("Use fallback")

        async def fallback():
            return "fallback_result"

        strategy = RecoveryStrategy(
            action=RecoveryAction.FALLBACK,
            fallback_func=fallback,
        )
        handler.register_strategy(ValueError, strategy)

        result = await handler.handle(operation, context)

        assert result.success
        assert result.result == "fallback_result"

    @pytest.mark.asyncio
    async def test_handle_unexpected_error(self, handler, context):
        """测试处理未预期的错误."""
        async def operation():
            raise RuntimeError("Unexpected error")

        result = await handler.handle(operation, context)

        assert not result.success
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_handle_with_default_strategy(self, handler, context):
        """测试使用默认策略."""
        handler.set_default_strategy(RecoveryAction.SKIP)

        async def operation():
            raise ValueError("Error")

        result = await handler.handle(operation, context)

        assert result.success

    def test_record_error(self, handler, context):
        """测试记录错误."""
        error = UTAgentError("Test error")

        handler.record_error(error, context, ErrorSeverity.HIGH)

        assert len(handler._error_records) == 1
        assert handler._error_records[0].error == error

    def test_get_error_records(self, handler, context):
        """测试获取错误记录."""
        for i in range(5):
            error = UTAgentError(f"Error {i}")
            handler.record_error(error, context, ErrorSeverity.LOW)

        records = handler.get_error_records()

        assert len(records) == 5

    def test_get_error_records_by_severity(self, handler, context):
        """测试按严重程度获取错误记录."""
        handler.record_error(UTAgentError("Low"), context, ErrorSeverity.LOW)
        handler.record_error(UTAgentError("High"), context, ErrorSeverity.HIGH)
        handler.record_error(UTAgentError("Critical"), context, ErrorSeverity.CRITICAL)

        high_records = handler.get_error_records(severity=ErrorSeverity.HIGH)
        critical_records = handler.get_error_records(severity=ErrorSeverity.CRITICAL)

        assert len(high_records) == 1
        assert len(critical_records) == 1

    def test_clear_records(self, handler, context):
        """测试清除记录."""
        handler.record_error(UTAgentError("Error"), context, ErrorSeverity.LOW)

        handler.clear_records()

        assert len(handler._error_records) == 0

    @pytest.mark.asyncio
    async def test_handle_with_context_propagation(self, handler):
        """测试上下文传播."""
        results = []

        async def operation():
            results.append(handler._current_context)
            return "success"

        context = ErrorContext(node_name="propagated", operation="test")
        await handler.handle(operation, context)

        assert results[0] == context

    def test_get_error_summary(self, handler, context):
        """测试获取错误摘要."""
        handler.record_error(UTAgentError("Error 1"), context, ErrorSeverity.LOW)
        handler.record_error(UTAgentError("Error 2"), context, ErrorSeverity.HIGH)
        handler.record_error(UTAgentError("Error 3"), context, ErrorSeverity.CRITICAL)

        summary = handler.get_error_summary()

        assert summary["total_errors"] == 3
        assert summary["by_severity"]["low"] == 1
        assert summary["by_severity"]["high"] == 1
        assert summary["by_severity"]["critical"] == 1


class TestErrorHandlerIntegration:
    """ErrorHandler 集成测试."""

    @pytest.mark.asyncio
    async def test_full_error_handling_workflow(self):
        """测试完整错误处理工作流."""
        handler = ErrorHandler()

        handler.register_strategy(
            LLMRateLimitError,
            RecoveryStrategy(
                action=RecoveryAction.RETRY,
                max_retries=3,
                retry_delay=0.1,
            ),
        )

        handler.register_strategy(
            CodeAnalysisError,
            RecoveryStrategy(action=RecoveryAction.SKIP),
        )

        handler.register_strategy(
            TestGenerationError,
            RecoveryStrategy(action=RecoveryAction.FAIL),
        )

        call_count = 0

        async def llm_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise LLMRateLimitError("Rate limited")
            return "llm_success"

        context = ErrorContext(node_name="llm_node", operation="generate")
        result = await handler.handle(llm_operation, context)

        assert result.success
        assert call_count == 2

        async def analysis_operation():
            raise CodeAnalysisError("Parse error")

        context = ErrorContext(node_name="analysis_node", operation="analyze")
        result = await handler.handle(analysis_operation, context)

        assert result.success
        assert result.skipped

        async def generation_operation():
            raise TestGenerationError("Generation failed")

        context = ErrorContext(node_name="generation_node", operation="generate")
        result = await handler.handle(generation_operation, context)

        assert not result.success

        summary = handler.get_error_summary()
        assert summary["total_errors"] >= 1
