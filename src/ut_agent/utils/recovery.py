"""错误恢复机制.

提供自动错误检测、诊断和恢复功能。
"""

import functools
import time
import traceback
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Union

from ut_agent.exceptions import (
    UTAgentError,
    RetryableError,
    LLMError,
    LLMRateLimitError,
    LLMConnectionError,
    CodeAnalysisError,
    TestGenerationError,
)
from ut_agent.utils import get_logger

logger = get_logger("recovery")

T = TypeVar('T')


class RecoveryStrategy(Enum):
    """恢复策略."""
    RETRY = "retry"
    FALLBACK = "fallback"
    SKIP = "skip"
    ABORT = "abort"


@dataclass
class RecoveryContext:
    """恢复上下文."""
    error: Exception
    attempt: int
    max_attempts: int
    operation_name: str
    args: tuple
    kwargs: Dict[str, Any]
    history: List[Dict[str, Any]] = field(default_factory=list)

    def add_history(self, action: str, result: Any = None, error: Optional[Exception] = None) -> None:
        self.history.append({
            "action": action,
            "result": result,
            "error": str(error) if error else None,
            "timestamp": time.time(),
        })


@dataclass
class RecoveryResult:
    """恢复结果."""
    success: bool
    result: Any = None
    error: Optional[Exception] = None
    strategy_used: Optional[RecoveryStrategy] = None
    attempts: int = 0
    history: List[Dict[str, Any]] = field(default_factory=list)


class ErrorRecoveryManager:
    """错误恢复管理器."""

    def __init__(
        self,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        exponential_backoff: bool = True,
    ):
        self._max_retries = max_retries
        self._retry_delay = retry_delay
        self._exponential_backoff = exponential_backoff
        self._fallback_handlers: Dict[Type[Exception], Callable] = {}
        self._recovery_strategies: Dict[Type[Exception], RecoveryStrategy] = {}

        self._register_default_strategies()
        self._register_default_fallbacks()

    def _register_default_strategies(self) -> None:
        """注册默认恢复策略."""
        self._recovery_strategies = {
            LLMRateLimitError: RecoveryStrategy.RETRY,
            LLMConnectionError: RecoveryStrategy.RETRY,
            RetryableError: RecoveryStrategy.RETRY,
            LLMError: RecoveryStrategy.FALLBACK,
            CodeAnalysisError: RecoveryStrategy.SKIP,
            TestGenerationError: RecoveryStrategy.FALLBACK,
        }

    def _register_default_fallbacks(self) -> None:
        """注册默认降级处理器."""
        pass

    def register_fallback(
        self,
        error_type: Type[Exception],
        handler: Callable,
    ) -> None:
        """注册降级处理器.

        Args:
            error_type: 错误类型
            handler: 降级处理函数
        """
        self._fallback_handlers[error_type] = handler

    def register_strategy(
        self,
        error_type: Type[Exception],
        strategy: RecoveryStrategy,
    ) -> None:
        """注册恢复策略.

        Args:
            error_type: 错误类型
            strategy: 恢复策略
        """
        self._recovery_strategies[error_type] = strategy

    def get_strategy(self, error: Exception) -> RecoveryStrategy:
        """获取错误对应的恢复策略."""
        for error_type, strategy in self._recovery_strategies.items():
            if isinstance(error, error_type):
                return strategy
        return RecoveryStrategy.ABORT

    def recover(
        self,
        error: Exception,
        context: RecoveryContext,
    ) -> RecoveryResult:
        """执行错误恢复.

        Args:
            error: 发生的错误
            context: 恢复上下文

        Returns:
            恢复结果
        """
        strategy = self.get_strategy(error)
        context.add_history(f"strategy_selected", result=strategy.value)

        logger.info(
            f"Recovery strategy selected: {strategy.value} for error: {type(error).__name__}"
        )

        if strategy == RecoveryStrategy.RETRY:
            return self._handle_retry(error, context)
        elif strategy == RecoveryStrategy.FALLBACK:
            return self._handle_fallback(error, context)
        elif strategy == RecoveryStrategy.SKIP:
            return self._handle_skip(error, context)
        else:
            return RecoveryResult(
                success=False,
                error=error,
                strategy_used=strategy,
                attempts=context.attempt,
                history=context.history,
            )

    def _handle_retry(
        self,
        error: Exception,
        context: RecoveryContext,
    ) -> RecoveryResult:
        """处理重试策略."""
        if context.attempt >= context.max_attempts:
            logger.warning(f"Max retries ({context.max_attempts}) exceeded")
            return RecoveryResult(
                success=False,
                error=error,
                strategy_used=RecoveryStrategy.RETRY,
                attempts=context.attempt,
                history=context.history,
            )

        delay = self._calculate_delay(context.attempt)
        context.add_history("retry_wait", result=delay)

        logger.info(f"Waiting {delay:.2f}s before retry {context.attempt + 1}")
        time.sleep(delay)

        return RecoveryResult(
            success=True,
            strategy_used=RecoveryStrategy.RETRY,
            attempts=context.attempt + 1,
            history=context.history,
        )

    def _handle_fallback(
        self,
        error: Exception,
        context: RecoveryContext,
    ) -> RecoveryResult:
        """处理降级策略."""
        for error_type, handler in self._fallback_handlers.items():
            if isinstance(error, error_type):
                try:
                    result = handler(error, context)
                    context.add_history("fallback_executed", result=result)
                    return RecoveryResult(
                        success=True,
                        result=result,
                        strategy_used=RecoveryStrategy.FALLBACK,
                        attempts=context.attempt,
                        history=context.history,
                    )
                except Exception as fallback_error:
                    context.add_history("fallback_failed", error=fallback_error)
                    logger.error(f"Fallback handler failed: {fallback_error}")

        return RecoveryResult(
            success=False,
            error=error,
            strategy_used=RecoveryStrategy.FALLBACK,
            attempts=context.attempt,
            history=context.history,
        )

    def _handle_skip(
        self,
        error: Exception,
        context: RecoveryContext,
    ) -> RecoveryResult:
        """处理跳过策略."""
        logger.warning(f"Skipping operation due to error: {error}")
        context.add_history("skipped")

        return RecoveryResult(
            success=True,
            result=None,
            strategy_used=RecoveryStrategy.SKIP,
            attempts=context.attempt,
            history=context.history,
        )

    def _calculate_delay(self, attempt: int) -> float:
        """计算重试延迟."""
        if self._exponential_backoff:
            return self._retry_delay * (2 ** attempt)
        return self._retry_delay


def with_recovery(
    max_retries: int = 3,
    retry_delay: float = 1.0,
    exponential_backoff: bool = True,
    on_error: Optional[Callable[[Exception, RecoveryContext], Any]] = None,
) -> Callable:
    """错误恢复装饰器.

    Args:
        max_retries: 最大重试次数
        retry_delay: 基础重试延迟
        exponential_backoff: 是否使用指数退避
        on_error: 错误处理回调

    Returns:
        装饰器函数
    """
    manager = ErrorRecoveryManager(
        max_retries=max_retries,
        retry_delay=retry_delay,
        exponential_backoff=exponential_backoff,
    )

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            attempt = 0

            while attempt <= max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as error:
                    context = RecoveryContext(
                        error=error,
                        attempt=attempt,
                        max_attempts=max_retries,
                        operation_name=func.__name__,
                        args=args,
                        kwargs=kwargs,
                    )

                    if on_error:
                        try:
                            on_error(error, context)
                        except Exception as callback_error:
                            logger.error(f"Error callback failed: {callback_error}")

                    result = manager.recover(error, context)

                    if not result.success:
                        raise error

                    if result.strategy_used == RecoveryStrategy.SKIP:
                        return None

                    attempt = result.attempts

            raise RuntimeError(f"Unexpected state in recovery wrapper for {func.__name__}")

        return wrapper

    return decorator


class CircuitBreaker:
    """熔断器."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_requests: int = 3,
    ):
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._half_open_requests = half_open_requests

        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._state = "closed"
        self._half_open_successes = 0

    @property
    def state(self) -> str:
        """获取当前状态."""
        if self._state == "open":
            if self._should_attempt_recovery():
                self._state = "half_open"
                self._half_open_successes = 0
        return self._state

    def _should_attempt_recovery(self) -> bool:
        """检查是否应该尝试恢复."""
        if self._last_failure_time is None:
            return True
        return time.time() - self._last_failure_time >= self._recovery_timeout

    def record_success(self) -> None:
        """记录成功."""
        if self._state == "half_open":
            self._half_open_successes += 1
            if self._half_open_successes >= self._half_open_requests:
                self._reset()
        else:
            self._failure_count = 0

    def record_failure(self) -> None:
        """记录失败."""
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._state == "half_open":
            self._state = "open"
        elif self._failure_count >= self._failure_threshold:
            self._state = "open"

    def _reset(self) -> None:
        """重置熔断器."""
        self._failure_count = 0
        self._last_failure_time = None
        self._state = "closed"
        self._half_open_successes = 0

    def is_available(self) -> bool:
        """检查是否可用."""
        return self.state != "open"

    def execute(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """执行函数（带熔断保护）."""
        if not self.is_available():
            raise UTAgentError(
                "Circuit breaker is open",
                details={
                    "state": self.state,
                    "failure_count": self._failure_count,
                }
            )

        try:
            result = func(*args, **kwargs)
            self.record_success()
            return result
        except Exception as error:
            self.record_failure()
            raise


_recovery_manager: Optional[ErrorRecoveryManager] = None


def get_recovery_manager() -> ErrorRecoveryManager:
    """获取全局恢复管理器."""
    global _recovery_manager
    if _recovery_manager is None:
        _recovery_manager = ErrorRecoveryManager()
    return _recovery_manager
