"""错误处理器模块 - 统一管理错误处理和恢复."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type, Union
from uuid import uuid4

from ut_agent.exceptions import UTAgentError, RetryableError
from ut_agent.utils import get_logger

logger = get_logger("error_handler")


class ErrorSeverity(Enum):
    """错误严重程度枚举."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RecoveryAction(Enum):
    """恢复动作枚举."""

    RETRY = "retry"
    SKIP = "skip"
    FAIL = "fail"
    FALLBACK = "fallback"
    ABORT = "abort"


@dataclass
class ErrorContext:
    """错误上下文."""

    node_name: str
    operation: str
    input_data: Optional[Dict[str, Any]] = None
    extra: Dict[str, Any] = field(default_factory=dict)
    trace_id: str = field(default_factory=lambda: str(uuid4())[:8])
    parent_trace_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "node_name": self.node_name,
            "operation": self.operation,
            "input_data": self.input_data,
            "extra": self.extra,
            "trace_id": self.trace_id,
            "parent_trace_id": self.parent_trace_id,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ErrorRecord:
    """错误记录."""

    error: UTAgentError
    context: ErrorContext
    severity: ErrorSeverity
    timestamp: datetime = field(default_factory=datetime.now)
    recovery_attempted: bool = False
    recovery_success: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "error": self.error.to_dict(),
            "context": self.context.to_dict(),
            "severity": self.severity.value,
            "timestamp": self.timestamp.isoformat(),
            "recovery_attempted": self.recovery_attempted,
            "recovery_success": self.recovery_success,
        }


@dataclass
class RecoveryResult:
    """恢复结果."""

    success: bool
    result: Any = None
    error: Optional[Exception] = None
    skipped: bool = False
    attempts: int = 1
    duration_ms: int = 0


@dataclass
class RecoveryStrategy:
    """恢复策略."""

    action: RecoveryAction
    max_retries: int = 3
    retry_delay: float = 1.0
    exponential_backoff: bool = True
    fallback_func: Optional[Callable] = None

    async def execute(
        self,
        operation: Callable,
        *args: Any,
        **kwargs: Any,
    ) -> RecoveryResult:
        """执行恢复策略.

        Args:
            operation: 操作函数
            *args: 参数
            **kwargs: 关键字参数

        Returns:
            RecoveryResult: 恢复结果
        """
        start_time = datetime.now()

        if self.action == RecoveryAction.RETRY:
            return await self._execute_with_retry(operation, *args, **kwargs)

        elif self.action == RecoveryAction.SKIP:
            return RecoveryResult(success=True, skipped=True)

        elif self.action == RecoveryAction.FALLBACK:
            return await self._execute_fallback(*args, **kwargs)

        elif self.action == RecoveryAction.FAIL:
            try:
                await self._call_operation(operation, *args, **kwargs)
            except Exception as e:
                return RecoveryResult(success=False, error=e)

        elif self.action == RecoveryAction.ABORT:
            try:
                await self._call_operation(operation, *args, **kwargs)
            except Exception as e:
                raise e

        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        return RecoveryResult(success=True, duration_ms=duration_ms)

    async def _execute_with_retry(
        self,
        operation: Callable,
        *args: Any,
        **kwargs: Any,
    ) -> RecoveryResult:
        """带重试的执行."""
        start_time = datetime.now()
        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries + 1):
            try:
                result = await self._call_operation(operation, *args, **kwargs)
                duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
                return RecoveryResult(
                    success=True,
                    result=result,
                    attempts=attempt + 1,
                    duration_ms=duration_ms,
                )

            except Exception as e:
                last_error = e
                logger.warning(
                    f"Operation failed (attempt {attempt + 1}/{self.max_retries + 1}): {e}"
                )

                if attempt < self.max_retries:
                    delay = self._calculate_delay(attempt)
                    await asyncio.sleep(delay)

        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        return RecoveryResult(
            success=False,
            error=last_error,
            attempts=self.max_retries + 1,
            duration_ms=duration_ms,
        )

    async def _execute_fallback(self, *args: Any, **kwargs: Any) -> RecoveryResult:
        """执行降级函数."""
        start_time = datetime.now()

        if self.fallback_func is None:
            return RecoveryResult(success=False, error=ValueError("No fallback function"))

        try:
            if asyncio.iscoroutinefunction(self.fallback_func):
                result = await self.fallback_func(*args, **kwargs)
            else:
                result = self.fallback_func(*args, **kwargs)

            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            return RecoveryResult(success=True, result=result, duration_ms=duration_ms)

        except Exception as e:
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            return RecoveryResult(success=False, error=e, duration_ms=duration_ms)

    async def _call_operation(
        self,
        operation: Callable,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """调用操作函数."""
        if asyncio.iscoroutinefunction(operation):
            return await operation(*args, **kwargs)
        else:
            return operation(*args, **kwargs)

    def _calculate_delay(self, attempt: int) -> float:
        """计算延迟时间."""
        if self.exponential_backoff:
            return self.retry_delay * (2**attempt)
        return self.retry_delay


class ErrorHandler:
    """错误处理器 - 统一管理错误处理和恢复.

    功能:
    - 错误捕获和记录
    - 恢复策略管理
    - 上下文传播
    - 错误摘要和统计
    """

    def __init__(self):
        """初始化错误处理器."""
        self._error_records: List[ErrorRecord] = []
        self._strategies: Dict[Type[Exception], RecoveryStrategy] = {}
        self._default_strategy: RecoveryStrategy = RecoveryStrategy(action=RecoveryAction.FAIL)
        self._current_context: Optional[ErrorContext] = None
        self._max_records: int = 1000

        self._register_default_strategies()

    def _register_default_strategies(self) -> None:
        """注册默认策略."""
        from ut_agent.exceptions import (
            LLMRateLimitError,
            LLMConnectionError,
            ASTParseError,
            FileReadError,
            TestCompilationError,
            TestExecutionError,
        )

        self.register_strategy(
            LLMRateLimitError,
            RecoveryStrategy(
                action=RecoveryAction.RETRY,
                max_retries=3,
                retry_delay=2.0,
                exponential_backoff=True,
            ),
        )

        self.register_strategy(
            LLMConnectionError,
            RecoveryStrategy(
                action=RecoveryAction.RETRY,
                max_retries=3,
                retry_delay=1.0,
            ),
        )

        self.register_strategy(
            ASTParseError,
            RecoveryStrategy(action=RecoveryAction.SKIP),
        )

        self.register_strategy(
            FileReadError,
            RecoveryStrategy(action=RecoveryAction.SKIP),
        )

        self.register_strategy(
            TestCompilationError,
            RecoveryStrategy(action=RecoveryAction.FAIL),
        )

        self.register_strategy(
            TestExecutionError,
            RecoveryStrategy(action=RecoveryAction.FAIL),
        )

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
        self._strategies[error_type] = strategy
        logger.debug(f"Registered recovery strategy for {error_type.__name__}")

    def set_default_strategy(self, action: RecoveryAction) -> None:
        """设置默认策略.

        Args:
            action: 恢复动作
        """
        self._default_strategy = RecoveryStrategy(action=action)

    async def handle(
        self,
        operation: Callable,
        context: ErrorContext,
        *args: Any,
        **kwargs: Any,
    ) -> RecoveryResult:
        """处理操作并捕获错误.

        Args:
            operation: 操作函数
            context: 错误上下文
            *args: 参数
            **kwargs: 关键字参数

        Returns:
            RecoveryResult: 恢复结果
        """
        self._current_context = context

        try:
            result = await self._call_operation(operation, *args, **kwargs)
            return RecoveryResult(success=True, result=result)

        except Exception as e:
            logger.error(f"Error in {context.node_name}.{context.operation}: {e}")

            strategy = self._get_strategy(e)

            record = ErrorRecord(
                error=self._wrap_error(e),
                context=context,
                severity=self._determine_severity(e),
                recovery_attempted=True,
            )

            recovery_result = await strategy.execute(operation, *args, **kwargs)
            record.recovery_success = recovery_result.success

            self._record_error(record)

            return recovery_result

    async def _call_operation(
        self,
        operation: Callable,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """调用操作函数."""
        if asyncio.iscoroutinefunction(operation):
            return await operation(*args, **kwargs)
        else:
            return operation(*args, **kwargs)

    def _get_strategy(self, error: Exception) -> RecoveryStrategy:
        """获取恢复策略."""
        for error_type, strategy in self._strategies.items():
            if isinstance(error, error_type):
                return strategy

        if isinstance(error, RetryableError):
            return RecoveryStrategy(
                action=RecoveryAction.RETRY,
                max_retries=error.max_retries,
            )

        return self._default_strategy

    def _wrap_error(self, error: Exception) -> UTAgentError:
        """包装错误为 UTAgentError."""
        if isinstance(error, UTAgentError):
            return error

        return UTAgentError(str(error), details={"original_type": type(error).__name__})

    def _determine_severity(self, error: Exception) -> ErrorSeverity:
        """确定错误严重程度."""
        from ut_agent.exceptions import (
            LLMRateLimitError,
            LLMConnectionError,
            LLMError,
            CodeAnalysisError,
            TestGenerationError,
            TestCompilationError,
            TestExecutionError,
        )

        if isinstance(error, (TestCompilationError, TestExecutionError)):
            return ErrorSeverity.HIGH

        if isinstance(error, TestGenerationError):
            return ErrorSeverity.HIGH

        if isinstance(error, LLMRateLimitError):
            return ErrorSeverity.MEDIUM

        if isinstance(error, LLMConnectionError):
            return ErrorSeverity.MEDIUM

        if isinstance(error, LLMError):
            return ErrorSeverity.HIGH

        if isinstance(error, CodeAnalysisError):
            return ErrorSeverity.LOW

        return ErrorSeverity.MEDIUM

    def record_error(
        self,
        error: Union[Exception, UTAgentError],
        context: ErrorContext,
        severity: ErrorSeverity,
    ) -> None:
        """记录错误.

        Args:
            error: 错误
            context: 上下文
            severity: 严重程度
        """
        wrapped_error = self._wrap_error(error) if not isinstance(error, UTAgentError) else error

        record = ErrorRecord(
            error=wrapped_error,
            context=context,
            severity=severity,
        )

        self._error_records.append(record)

        if len(self._error_records) > self._max_records:
            self._error_records = self._error_records[-self._max_records :]

    def _record_error(self, record: ErrorRecord) -> None:
        """内部记录错误."""
        self._error_records.append(record)

        if len(self._error_records) > self._max_records:
            self._error_records = self._error_records[-self._max_records :]

    def get_error_records(
        self,
        severity: Optional[ErrorSeverity] = None,
        node_name: Optional[str] = None,
        limit: int = 100,
    ) -> List[ErrorRecord]:
        """获取错误记录.

        Args:
            severity: 严重程度过滤
            node_name: 节点名称过滤
            limit: 返回数量限制

        Returns:
            List[ErrorRecord]: 错误记录列表
        """
        records = self._error_records

        if severity:
            records = [r for r in records if r.severity == severity]

        if node_name:
            records = [r for r in records if r.context.node_name == node_name]

        return records[-limit:]

    def clear_records(self) -> None:
        """清除错误记录."""
        self._error_records = []

    def get_error_summary(self) -> Dict[str, Any]:
        """获取错误摘要.

        Returns:
            Dict[str, Any]: 错误摘要
        """
        if not self._error_records:
            return {
                "total_errors": 0,
                "by_severity": {},
                "by_node": {},
            }

        by_severity: Dict[str, int] = {}
        by_node: Dict[str, int] = {}

        for record in self._error_records:
            severity_key = record.severity.value
            by_severity[severity_key] = by_severity.get(severity_key, 0) + 1

            node_key = record.context.node_name
            by_node[node_key] = by_node.get(node_key, 0) + 1

        return {
            "total_errors": len(self._error_records),
            "by_severity": by_severity,
            "by_node": by_node,
        }
