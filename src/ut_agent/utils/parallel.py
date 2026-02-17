"""异步并行处理器模块 - 统一管理并行任务执行."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, Generic, List, Optional, TypeVar

from ut_agent.utils import get_logger

logger = get_logger("parallel")

T = TypeVar("T")
R = TypeVar("R")


class TaskStatus(Enum):
    """任务状态枚举."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class ParallelConfig:
    """并行处理配置."""

    max_concurrency: int = 4
    timeout: int = 300
    fail_fast: bool = False
    retry_count: int = 0
    retry_delay: float = 1.0

    def __post_init__(self):
        """验证配置."""
        if self.max_concurrency < 1:
            raise ValueError("max_concurrency must be at least 1")
        if self.timeout < 0:
            raise ValueError("timeout must be non-negative")
        if self.retry_count < 0:
            raise ValueError("retry_count must be non-negative")


@dataclass
class ParallelResult(Generic[R]):
    """并行处理结果."""

    task_id: str
    status: TaskStatus
    result: Optional[R] = None
    errors: List[str] = field(default_factory=list)
    duration_ms: int = 0
    attempt: int = 1

    @property
    def success(self) -> bool:
        """是否成功."""
        return self.status == TaskStatus.SUCCESS


@dataclass
class ProcessorStats:
    """处理器统计信息."""

    total_tasks: int = 0
    successful: int = 0
    failed: int = 0
    total_duration_ms: int = 0

    @property
    def success_rate(self) -> float:
        """成功率."""
        if self.total_tasks == 0:
            return 0.0
        return self.successful / self.total_tasks


class AsyncParallelProcessor(Generic[T, R]):
    """异步并行处理器 - 统一管理并行任务执行.

    功能:
    - 并发控制（信号量）
    - 超时控制
    - 重试机制
    - 快速失败模式
    - 进度回调
    - 结果回调
    - 统计信息
    """

    def __init__(
        self,
        process_func: Callable[[T], R],
        config: Optional[ParallelConfig] = None,
    ):
        """初始化处理器.

        Args:
            process_func: 处理函数（同步或异步）
            config: 并行配置
        """
        self._process_func = process_func
        self._config = config or ParallelConfig()
        self._stats = ProcessorStats()
        self._semaphore = asyncio.Semaphore(self._config.max_concurrency)

    async def process_one(
        self,
        task: T,
        task_id: Optional[str] = None,
    ) -> ParallelResult[R]:
        """处理单个任务.

        Args:
            task: 任务
            task_id: 任务 ID

        Returns:
            ParallelResult: 处理结果
        """
        task_id = task_id or getattr(task, "id", str(id(task)))
        start_time = datetime.now()
        last_error: Optional[str] = None

        for attempt in range(self._config.retry_count + 1):
            try:
                async with self._semaphore:
                    result = await asyncio.wait_for(
                        self._invoke_process_func(task),
                        timeout=self._config.timeout,
                    )

                    duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

                    return ParallelResult(
                        task_id=task_id,
                        status=TaskStatus.SUCCESS,
                        result=result,
                        duration_ms=duration_ms,
                        attempt=attempt + 1,
                    )

            except asyncio.TimeoutError:
                duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
                return ParallelResult(
                    task_id=task_id,
                    status=TaskStatus.TIMEOUT,
                    errors=[f"Task timed out after {self._config.timeout} seconds"],
                    duration_ms=duration_ms,
                    attempt=attempt + 1,
                )

            except Exception as e:
                last_error = str(e)
                logger.warning(
                    f"Task {task_id} failed (attempt {attempt + 1}/{self._config.retry_count + 1}): {e}"
                )

                if attempt < self._config.retry_count:
                    await asyncio.sleep(self._config.retry_delay * (attempt + 1))

        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        return ParallelResult(
            task_id=task_id,
            status=TaskStatus.FAILED,
            errors=[last_error or "Unknown error"],
            duration_ms=duration_ms,
            attempt=self._config.retry_count + 1,
        )

    async def _invoke_process_func(self, task: T) -> R:
        """调用处理函数.

        Args:
            task: 任务

        Returns:
            R: 处理结果
        """
        if asyncio.iscoroutinefunction(self._process_func):
            return await self._process_func(task)
        else:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._process_func, task)

    async def process_all(
        self,
        tasks: List[T],
        on_progress: Optional[Callable[[int, int], None]] = None,
        on_result: Optional[Callable[[ParallelResult[R]], None]] = None,
    ) -> List[ParallelResult[R]]:
        """处理所有任务.

        Args:
            tasks: 任务列表
            on_progress: 进度回调
            on_result: 结果回调

        Returns:
            List[ParallelResult]: 处理结果列表
        """
        if not tasks:
            return []

        self._stats = ProcessorStats()
        completed = 0
        total = len(tasks)
        results: List[ParallelResult[R]] = []

        async def process_with_callback(task: T) -> ParallelResult[R]:
            nonlocal completed

            result = await self.process_one(task)
            completed += 1

            self._update_stats(result)

            if on_progress:
                on_progress(completed, total)

            if on_result:
                await self._invoke_callback(on_result, result)

            return result

        if self._config.fail_fast:
            for task in tasks:
                result = await process_with_callback(task)
                results.append(result)

                if not result.success:
                    break
        else:
            results = await asyncio.gather(
                *[process_with_callback(task) for task in tasks],
                return_exceptions=True,
            )

            results = [
                r if isinstance(r, ParallelResult) else ParallelResult(
                    task_id=str(i),
                    status=TaskStatus.FAILED,
                    errors=[str(r)],
                )
                for i, r in enumerate(results)
            ]

        return results

    async def _invoke_callback(
        self,
        callback: Callable,
        *args: Any,
    ) -> None:
        """调用回调函数.

        Args:
            callback: 回调函数
            *args: 参数
        """
        if asyncio.iscoroutinefunction(callback):
            await callback(*args)
        else:
            callback(*args)

    async def process_batches(
        self,
        batches: List[List[T]],
        on_batch_complete: Optional[Callable[[int, List[ParallelResult[R]]], None]] = None,
    ) -> List[List[ParallelResult[R]]]:
        """批量处理任务.

        Args:
            batches: 任务批次列表
            on_batch_complete: 批次完成回调

        Returns:
            List[List[ParallelResult]]: 批次处理结果列表
        """
        all_results = []

        for batch_index, batch in enumerate(batches):
            batch_results = await self.process_all(batch)
            all_results.append(batch_results)

            if on_batch_complete:
                await self._invoke_callback(on_batch_complete, batch_index, batch_results)

        return all_results

    def _update_stats(self, result: ParallelResult[R]) -> None:
        """更新统计信息.

        Args:
            result: 处理结果
        """
        self._stats.total_tasks += 1
        self._stats.total_duration_ms += result.duration_ms

        if result.success:
            self._stats.successful += 1
        else:
            self._stats.failed += 1

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息.

        Returns:
            Dict[str, Any]: 统计信息
        """
        return {
            "total_tasks": self._stats.total_tasks,
            "successful": self._stats.successful,
            "failed": self._stats.failed,
            "success_rate": self._stats.success_rate,
            "total_duration_ms": self._stats.total_duration_ms,
            "avg_duration_ms": (
                self._stats.total_duration_ms / self._stats.total_tasks
                if self._stats.total_tasks > 0
                else 0
            ),
        }

    def clear_stats(self) -> None:
        """清除统计信息."""
        self._stats = ProcessorStats()

    async def map(
        self,
        tasks: List[T],
    ) -> List[Optional[R]]:
        """映射处理任务，返回结果列表.

        Args:
            tasks: 任务列表

        Returns:
            List[Optional[R]]: 结果列表（失败的任务返回 None）
        """
        results = await self.process_all(tasks)
        return [r.result if r.success else None for r in results]

    async def filter_success(
        self,
        tasks: List[T],
    ) -> List[R]:
        """过滤成功的任务结果.

        Args:
            tasks: 任务列表

        Returns:
            List[R]: 成功的结果列表
        """
        results = await self.process_all(tasks)
        return [r.result for r in results if r.success and r.result is not None]
