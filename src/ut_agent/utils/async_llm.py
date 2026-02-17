"""异步 LLM 调用器模块 - 统一管理 LLM 异步调用."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from ut_agent.exceptions import LLMError, LLMRateLimitError, LLMResponseError
from ut_agent.utils import get_logger

logger = get_logger("async_llm")


class LLMCallStatus(Enum):
    """LLM 调用状态枚举."""

    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    CANCELLED = "cancelled"


@dataclass
class LLMCallConfig:
    """LLM 调用配置."""

    max_retries: int = 3
    retry_delay: float = 1.0
    timeout: int = 60
    exponential_backoff: bool = True
    max_retry_delay: float = 30.0
    max_concurrent_calls: int = 5
    history_limit: int = 100

    def __post_init__(self):
        """验证配置."""
        if self.max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        if self.timeout < 0:
            raise ValueError("timeout must be non-negative")
        if self.retry_delay < 0:
            raise ValueError("retry_delay must be non-negative")


@dataclass
class LLMCallResult:
    """LLM 调用结果."""

    status: LLMCallStatus
    content: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    retry_after: Optional[int] = None
    timestamp: datetime = field(default_factory=datetime.now)
    duration_ms: int = 0
    attempt: int = 1

    @property
    def success(self) -> bool:
        """是否成功."""
        return self.status == LLMCallStatus.SUCCESS

    @property
    def total_tokens(self) -> int:
        """总 token 数."""
        return self.prompt_tokens + self.completion_tokens


class AsyncLLMCaller:
    """异步 LLM 调用器 - 统一管理 LLM 异步调用.

    功能:
    - 异步调用 LLM
    - 超时控制
    - 重试机制（指数退避）
    - 速率限制处理
    - 批量调用
    - 调用历史记录
    - 统计信息
    """

    def __init__(
        self,
        llm: BaseChatModel,
        config: Optional[LLMCallConfig] = None,
    ):
        """初始化调用器.

        Args:
            llm: LangChain Chat Model 实例
            config: 调用配置
        """
        self._llm = llm
        self._config = config or LLMCallConfig()
        self._call_history: List[LLMCallResult] = []
        self._semaphore = asyncio.Semaphore(self._config.max_concurrent_calls)

    async def call(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        **kwargs: Any,
    ) -> LLMCallResult:
        """异步调用 LLM.

        Args:
            prompt: 用户提示
            system_prompt: 系统提示
            temperature: 温度参数
            **kwargs: 其他参数

        Returns:
            LLMCallResult: 调用结果
        """
        messages: List[BaseMessage] = []

        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))

        messages.append(HumanMessage(content=prompt))

        return await self._call_with_retry(messages, temperature, **kwargs)

    async def call_with_messages(
        self,
        messages: List[BaseMessage],
        temperature: Optional[float] = None,
        **kwargs: Any,
    ) -> LLMCallResult:
        """使用消息列表调用 LLM.

        Args:
            messages: 消息列表
            temperature: 温度参数
            **kwargs: 其他参数

        Returns:
            LLMCallResult: 调用结果
        """
        return await self._call_with_retry(messages, temperature, **kwargs)

    async def _call_with_retry(
        self,
        messages: List[BaseMessage],
        temperature: Optional[float] = None,
        **kwargs: Any,
    ) -> LLMCallResult:
        """带重试机制的调用.

        Args:
            messages: 消息列表
            temperature: 温度参数
            **kwargs: 其他参数

        Returns:
            LLMCallResult: 调用结果
        """
        last_result: Optional[LLMCallResult] = None
        start_time = datetime.now()

        for attempt in range(self._config.max_retries + 1):
            try:
                async with self._semaphore:
                    result = await asyncio.wait_for(
                        self._invoke_llm(messages, temperature, **kwargs),
                        timeout=self._config.timeout,
                    )

                    duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
                    result.duration_ms = duration_ms
                    result.attempt = attempt + 1

                    if result.success:
                        self._record_call(result)
                        return result

                    last_result = result
                    logger.warning(
                        f"LLM call failed (attempt {attempt + 1}/{self._config.max_retries + 1}): {result.errors}"
                    )

            except asyncio.TimeoutError:
                duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
                last_result = LLMCallResult(
                    status=LLMCallStatus.TIMEOUT,
                    errors=[f"Call timed out after {self._config.timeout} seconds"],
                    duration_ms=duration_ms,
                    attempt=attempt + 1,
                )
                logger.warning(f"LLM call timed out (attempt {attempt + 1})")

            except LLMRateLimitError as e:
                duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
                retry_after = e.details.get("retry_after", 60)
                last_result = LLMCallResult(
                    status=LLMCallStatus.RATE_LIMITED,
                    errors=[str(e)],
                    retry_after=retry_after,
                    duration_ms=duration_ms,
                    attempt=attempt + 1,
                )
                logger.warning(f"LLM rate limited, retry after {retry_after}s")

            except Exception as e:
                duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
                error_msg = str(e)

                if "rate limit" in error_msg.lower():
                    last_result = LLMCallResult(
                        status=LLMCallStatus.RATE_LIMITED,
                        errors=[error_msg],
                        retry_after=60,
                        duration_ms=duration_ms,
                        attempt=attempt + 1,
                    )
                else:
                    last_result = LLMCallResult(
                        status=LLMCallStatus.FAILED,
                        errors=[error_msg],
                        duration_ms=duration_ms,
                        attempt=attempt + 1,
                    )
                logger.error(f"LLM call error: {e}")

            if attempt < self._config.max_retries:
                delay = self._calculate_retry_delay(attempt)
                if last_result and last_result.status == LLMCallStatus.RATE_LIMITED:
                    delay = max(delay, last_result.retry_after or 60)
                await asyncio.sleep(delay)

        if last_result:
            self._record_call(last_result)
            return last_result

        return LLMCallResult(
            status=LLMCallStatus.FAILED,
            errors=["Unknown error"],
            attempt=self._config.max_retries + 1,
        )

    async def _invoke_llm(
        self,
        messages: List[BaseMessage],
        temperature: Optional[float] = None,
        **kwargs: Any,
    ) -> LLMCallResult:
        """调用 LLM.

        Args:
            messages: 消息列表
            temperature: 温度参数
            **kwargs: 其他参数

        Returns:
            LLMCallResult: 调用结果
        """
        try:
            invoke_kwargs = kwargs.copy()
            if temperature is not None:
                invoke_kwargs["temperature"] = temperature

            response = await self._llm.ainvoke(messages, **invoke_kwargs)

            content = ""
            prompt_tokens = 0
            completion_tokens = 0

            if hasattr(response, "content"):
                content = str(response.content)

            if hasattr(response, "usage_metadata"):
                usage = response.usage_metadata
                if usage:
                    prompt_tokens = usage.get("input_tokens", 0)
                    completion_tokens = usage.get("output_tokens", 0)

            return LLMCallResult(
                status=LLMCallStatus.SUCCESS,
                content=content,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )

        except Exception as e:
            error_msg = str(e)
            if "rate limit" in error_msg.lower():
                return LLMCallResult(
                    status=LLMCallStatus.RATE_LIMITED,
                    errors=[error_msg],
                    retry_after=60,
                )
            return LLMCallResult(
                status=LLMCallStatus.FAILED,
                errors=[error_msg],
            )

    def _calculate_retry_delay(self, attempt: int) -> float:
        """计算重试延迟.

        Args:
            attempt: 当前尝试次数

        Returns:
            float: 延迟秒数
        """
        if self._config.exponential_backoff:
            delay = self._config.retry_delay * (2**attempt)
            return min(delay, self._config.max_retry_delay)
        return self._config.retry_delay

    async def batch_call(
        self,
        prompts: List[str],
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        **kwargs: Any,
    ) -> List[LLMCallResult]:
        """批量调用 LLM.

        Args:
            prompts: 提示列表
            system_prompt: 系统提示
            temperature: 温度参数
            **kwargs: 其他参数

        Returns:
            List[LLMCallResult]: 调用结果列表
        """
        results = await asyncio.gather(
            *[
                self.call(prompt, system_prompt, temperature, **kwargs)
                for prompt in prompts
            ],
            return_exceptions=True,
        )

        return [
            r if isinstance(r, LLMCallResult) else LLMCallResult(
                status=LLMCallStatus.FAILED,
                errors=[str(r)],
            )
            for r in results
        ]

    def _record_call(self, result: LLMCallResult) -> None:
        """记录调用结果.

        Args:
            result: 调用结果
        """
        self._call_history.append(result)

        if len(self._call_history) > self._config.history_limit:
            self._call_history = self._call_history[-self._config.history_limit :]

    def get_call_history(self, limit: int = 100) -> List[LLMCallResult]:
        """获取调用历史.

        Args:
            limit: 返回数量限制

        Returns:
            List[LLMCallResult]: 调用历史列表
        """
        return self._call_history[-limit:]

    def clear_history(self) -> None:
        """清除调用历史."""
        self._call_history = []

    def get_stats(self) -> Dict[str, Any]:
        """获取调用统计信息.

        Returns:
            Dict[str, Any]: 统计信息
        """
        if not self._call_history:
            return {
                "total_calls": 0,
                "success_count": 0,
                "failed_count": 0,
                "success_rate": 0.0,
                "total_tokens": 0,
                "avg_duration_ms": 0.0,
            }

        success_count = sum(1 for r in self._call_history if r.success)
        failed_count = len(self._call_history) - success_count
        total_tokens = sum(r.total_tokens for r in self._call_history)
        total_duration = sum(r.duration_ms for r in self._call_history)

        return {
            "total_calls": len(self._call_history),
            "success_count": success_count,
            "failed_count": failed_count,
            "success_rate": success_count / len(self._call_history),
            "total_tokens": total_tokens,
            "avg_duration_ms": total_duration / len(self._call_history),
        }
