"""错误恢复机制单元测试."""

from unittest.mock import Mock, patch, MagicMock

import pytest

from ut_agent.utils.recovery import (
    RecoveryStrategy,
    RecoveryContext,
    RecoveryResult,
    ErrorRecoveryManager,
    with_recovery,
    CircuitBreaker,
    get_recovery_manager,
)
from ut_agent.exceptions import (
    RetryableError,
    LLMRateLimitError,
    LLMConnectionError,
    LLMError,
    UTAgentError,
)


class TestRecoveryStrategy:
    """恢复策略枚举测试."""

    def test_recovery_strategy_values(self):
        """测试恢复策略枚举值."""
        assert RecoveryStrategy.RETRY.value == "retry"
        assert RecoveryStrategy.FALLBACK.value == "fallback"
        assert RecoveryStrategy.SKIP.value == "skip"
        assert RecoveryStrategy.ABORT.value == "abort"


class TestRecoveryContext:
    """恢复上下文测试."""

    def test_recovery_context_creation(self):
        """测试创建恢复上下文."""
        error = ValueError("test error")
        context = RecoveryContext(
            error=error,
            attempt=1,
            max_attempts=3,
            operation_name="test_op",
            args=(1, 2),
            kwargs={"key": "value"},
        )

        assert context.error == error
        assert context.attempt == 1
        assert context.max_attempts == 3
        assert context.operation_name == "test_op"
        assert context.history == []

    def test_add_history(self):
        """测试添加历史记录."""
        context = RecoveryContext(
            error=ValueError("test"),
            attempt=0,
            max_attempts=3,
            operation_name="test",
            args=(),
            kwargs={},
        )

        context.add_history("action1", result="success")
        context.add_history("action2", error=ValueError("failed"))

        assert len(context.history) == 2
        assert context.history[0]["action"] == "action1"
        assert context.history[0]["result"] == "success"
        assert context.history[1]["action"] == "action2"
        assert context.history[1]["error"] == "failed"


class TestRecoveryResult:
    """恢复结果测试."""

    def test_recovery_result_creation(self):
        """测试创建恢复结果."""
        result = RecoveryResult(
            success=True,
            result="test_result",
            strategy_used=RecoveryStrategy.RETRY,
            attempts=2,
        )

        assert result.success is True
        assert result.result == "test_result"
        assert result.strategy_used == RecoveryStrategy.RETRY
        assert result.attempts == 2


class TestErrorRecoveryManager:
    """错误恢复管理器测试."""

    def test_manager_initialization(self):
        """测试管理器初始化."""
        manager = ErrorRecoveryManager(
            max_retries=5,
            retry_delay=2.0,
            exponential_backoff=False,
        )

        assert manager._max_retries == 5
        assert manager._retry_delay == 2.0
        assert manager._exponential_backoff is False

    def test_get_strategy_retry(self):
        """测试获取重试策略."""
        manager = ErrorRecoveryManager()

        error = LLMRateLimitError("rate limit")
        strategy = manager.get_strategy(error)

        assert strategy == RecoveryStrategy.RETRY

    def test_get_strategy_connection_error(self):
        """测试获取连接错误策略."""
        manager = ErrorRecoveryManager()

        error = LLMConnectionError("connection failed")
        strategy = manager.get_strategy(error)

        assert strategy == RecoveryStrategy.RETRY

    def test_get_strategy_unknown_error(self):
        """测试获取未知错误策略."""
        manager = ErrorRecoveryManager()

        error = ValueError("unknown error")
        strategy = manager.get_strategy(error)

        assert strategy == RecoveryStrategy.ABORT

    def test_register_fallback(self):
        """测试注册降级处理器."""
        manager = ErrorRecoveryManager()

        def fallback_handler(error, context):
            return "fallback_result"

        manager.register_fallback(LLMError, fallback_handler)

        assert LLMError in manager._fallback_handlers

    def test_register_strategy(self):
        """测试注册恢复策略."""
        manager = ErrorRecoveryManager()

        manager.register_strategy(ValueError, RecoveryStrategy.SKIP)

        assert manager._recovery_strategies[ValueError] == RecoveryStrategy.SKIP

    def test_handle_retry_success(self):
        """测试重试处理成功."""
        manager = ErrorRecoveryManager(max_retries=3, retry_delay=0.1)

        error = RetryableError("retryable error", max_retries=3, retry_count=0)
        context = RecoveryContext(
            error=error,
            attempt=0,
            max_attempts=3,
            operation_name="test",
            args=(),
            kwargs={},
        )

        result = manager.recover(error, context)

        assert result.success is True
        assert result.strategy_used == RecoveryStrategy.RETRY
        assert result.attempts == 1

    def test_handle_retry_max_exceeded(self):
        """测试重试次数超限."""
        manager = ErrorRecoveryManager(max_retries=3, retry_delay=0.1)

        error = RetryableError("retryable error", max_retries=3, retry_count=3)
        context = RecoveryContext(
            error=error,
            attempt=3,
            max_attempts=3,
            operation_name="test",
            args=(),
            kwargs={},
        )

        result = manager.recover(error, context)

        assert result.success is False
        assert result.strategy_used == RecoveryStrategy.RETRY

    def test_handle_skip(self):
        """测试跳过策略."""
        manager = ErrorRecoveryManager()

        error = UTAgentError("skip error")
        manager.register_strategy(UTAgentError, RecoveryStrategy.SKIP)

        context = RecoveryContext(
            error=error,
            attempt=0,
            max_attempts=3,
            operation_name="test",
            args=(),
            kwargs={},
        )

        result = manager.recover(error, context)

        assert result.success is True
        assert result.strategy_used == RecoveryStrategy.SKIP

    def test_calculate_delay_exponential(self):
        """测试指数退避延迟计算."""
        manager = ErrorRecoveryManager(
            retry_delay=1.0,
            exponential_backoff=True,
        )

        assert manager._calculate_delay(0) == 1.0
        assert manager._calculate_delay(1) == 2.0
        assert manager._calculate_delay(2) == 4.0

    def test_calculate_delay_fixed(self):
        """测试固定延迟计算."""
        manager = ErrorRecoveryManager(
            retry_delay=2.0,
            exponential_backoff=False,
        )

        assert manager._calculate_delay(0) == 2.0
        assert manager._calculate_delay(1) == 2.0
        assert manager._calculate_delay(2) == 2.0


class TestWithRecovery:
    """恢复装饰器测试."""

    def test_with_recovery_success(self):
        """测试装饰器成功执行."""
        @with_recovery(max_retries=3, retry_delay=0.1)
        def successful_func():
            return "success"

        result = successful_func()

        assert result == "success"

    def test_with_recovery_retry_success(self):
        """测试装饰器重试后成功."""
        call_count = 0

        @with_recovery(max_retries=3, retry_delay=0.1)
        def retry_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RetryableError("retry", max_retries=3, retry_count=call_count)
            return "success"

        result = retry_func()

        assert result == "success"
        assert call_count == 2

    def test_with_recovery_skip(self):
        """测试装饰器跳过策略."""
        from ut_agent.exceptions import CodeAnalysisError

        @with_recovery(max_retries=3, retry_delay=0.1)
        def skip_func():
            raise CodeAnalysisError("skip this")

        result = skip_func()

        assert result is None


class TestCircuitBreaker:
    """熔断器测试."""

    def test_circuit_breaker_initial_state(self):
        """测试熔断器初始状态."""
        cb = CircuitBreaker()

        assert cb.state == "closed"
        assert cb.is_available() is True

    def test_circuit_breaker_record_success(self):
        """测试记录成功."""
        cb = CircuitBreaker()

        cb.record_success()

        assert cb.state == "closed"
        assert cb._failure_count == 0

    def test_circuit_breaker_open_after_failures(self):
        """测试失败后熔断器打开."""
        cb = CircuitBreaker(failure_threshold=3)

        for _ in range(3):
            cb.record_failure()

        assert cb.state == "open"
        assert cb.is_available() is False

    def test_circuit_breaker_execute_success(self):
        """测试熔断器执行成功."""
        cb = CircuitBreaker()

        result = cb.execute(lambda: "success")

        assert result == "success"
        assert cb.state == "closed"

    def test_circuit_breaker_execute_failure(self):
        """测试熔断器执行失败."""
        cb = CircuitBreaker(failure_threshold=2)

        with pytest.raises(ValueError):
            cb.execute(lambda: int("invalid"))

        assert cb._failure_count == 1

    def test_circuit_breaker_open_rejects_requests(self):
        """测试熔断器打开时拒绝请求."""
        cb = CircuitBreaker(failure_threshold=1)

        cb.record_failure()
        cb.record_failure()

        assert cb.state == "open"

        with pytest.raises(UTAgentError) as exc_info:
            cb.execute(lambda: "should fail")

        assert "Circuit breaker is open" in str(exc_info.value)

    def test_circuit_breaker_half_open_recovery(self):
        """测试熔断器半开状态恢复."""
        cb = CircuitBreaker(
            failure_threshold=1,
            recovery_timeout=0.1,
            half_open_requests=1,
        )

        cb.record_failure()
        cb.record_failure()
        assert cb.state == "open"

        import time
        time.sleep(0.15)

        assert cb.state == "half_open"

        cb.record_success()
        assert cb.state == "closed"


class TestGetRecoveryManager:
    """获取恢复管理器测试."""

    def test_get_recovery_manager_singleton(self):
        """测试获取单例."""
        manager1 = get_recovery_manager()
        manager2 = get_recovery_manager()

        assert manager1 is manager2
