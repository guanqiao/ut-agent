"""异步并行处理器测试模块."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, TypeVar
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ut_agent.utils.parallel import (
    AsyncParallelProcessor,
    ParallelConfig,
    ParallelResult,
    TaskStatus,
)

T = TypeVar("T")


@dataclass
class MockTask:
    """测试用任务."""

    id: str
    value: int
    should_fail: bool = False
    delay: float = 0.1


async def mock_processor(task: MockTask) -> int:
    """Mock 处理函数."""
    if task.delay > 0:
        await asyncio.sleep(task.delay)

    if task.should_fail:
        raise ValueError(f"Task {task.id} failed")

    return task.value * 2


class TestParallelConfig:
    """ParallelConfig 测试."""

    def test_default_config(self):
        """测试默认配置."""
        config = ParallelConfig()
        assert config.max_concurrency == 4
        assert config.timeout == 300
        assert config.fail_fast is False
        assert config.retry_count == 0
        assert config.retry_delay == 1.0

    def test_custom_config(self):
        """测试自定义配置."""
        config = ParallelConfig(
            max_concurrency=8,
            timeout=600,
            fail_fast=True,
            retry_count=3,
            retry_delay=2.0,
        )
        assert config.max_concurrency == 8
        assert config.timeout == 600
        assert config.fail_fast is True
        assert config.retry_count == 3
        assert config.retry_delay == 2.0

    def test_validate_config(self):
        """测试配置验证."""
        with pytest.raises(ValueError):
            ParallelConfig(max_concurrency=0)

        with pytest.raises(ValueError):
            ParallelConfig(timeout=-1)


class TestParallelResult:
    """ParallelResult 测试."""

    def test_success_result(self):
        """测试成功结果."""
        result = ParallelResult(
            task_id="task-1",
            status=TaskStatus.SUCCESS,
            result=42,
        )
        assert result.status == TaskStatus.SUCCESS
        assert result.success is True
        assert result.result == 42

    def test_failed_result(self):
        """测试失败结果."""
        result = ParallelResult(
            task_id="task-1",
            status=TaskStatus.FAILED,
            errors=["Error message"],
        )
        assert result.status == TaskStatus.FAILED
        assert result.success is False
        assert len(result.errors) == 1

    def test_timeout_result(self):
        """测试超时结果."""
        result = ParallelResult(
            task_id="task-1",
            status=TaskStatus.TIMEOUT,
        )
        assert result.status == TaskStatus.TIMEOUT
        assert result.success is False


class TestAsyncParallelProcessor:
    """AsyncParallelProcessor 测试."""

    @pytest.fixture
    def processor(self):
        """创建处理器实例."""
        return AsyncParallelProcessor(mock_processor)

    @pytest.fixture
    def tasks(self):
        """创建测试任务."""
        return [
            MockTask(id="task-1", value=1),
            MockTask(id="task-2", value=2),
            MockTask(id="task-3", value=3),
        ]

    def test_processor_initialization(self):
        """测试处理器初始化."""
        processor = AsyncParallelProcessor(mock_processor)
        assert processor._process_func == mock_processor
        assert processor._config is not None

    @pytest.mark.asyncio
    async def test_process_single_task(self, processor):
        """测试处理单个任务."""
        task = MockTask(id="task-1", value=5)

        result = await processor.process_one(task)

        assert result.success
        assert result.result == 10

    @pytest.mark.asyncio
    async def test_process_multiple_tasks(self, processor, tasks):
        """测试处理多个任务."""
        results = await processor.process_all(tasks)

        assert len(results) == 3
        assert all(r.success for r in results)
        assert [r.result for r in results] == [2, 4, 6]

    @pytest.mark.asyncio
    async def test_process_with_concurrency_limit(self):
        """测试并发限制."""
        config = ParallelConfig(max_concurrency=2)
        processor = AsyncParallelProcessor(mock_processor, config)

        tasks = [
            MockTask(id=f"task-{i}", value=i, delay=0.1)
            for i in range(4)
        ]

        start_time = datetime.now()
        results = await processor.process_all(tasks)
        end_time = datetime.now()

        elapsed = (end_time - start_time).total_seconds()
        assert elapsed >= 0.2
        assert len(results) == 4

    @pytest.mark.asyncio
    async def test_process_with_failure(self, processor):
        """测试处理失败的任务."""
        tasks = [
            MockTask(id="task-1", value=1),
            MockTask(id="task-2", value=2, should_fail=True),
            MockTask(id="task-3", value=3),
        ]

        results = await processor.process_all(tasks)

        assert len(results) == 3
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]

        assert len(successful) == 2
        assert len(failed) == 1
        assert "failed" in failed[0].errors[0].lower()

    @pytest.mark.asyncio
    async def test_process_with_fail_fast(self):
        """测试快速失败模式."""
        config = ParallelConfig(fail_fast=True, max_concurrency=1)
        processor = AsyncParallelProcessor(mock_processor, config)

        tasks = [
            MockTask(id="task-1", value=1),
            MockTask(id="task-2", value=2, should_fail=True),
            MockTask(id="task-3", value=3),
        ]

        results = await processor.process_all(tasks)

        assert any(not r.success for r in results)

    @pytest.mark.asyncio
    async def test_process_with_timeout(self):
        """测试处理超时."""
        config = ParallelConfig(timeout=0.05)
        processor = AsyncParallelProcessor(mock_processor, config)

        task = MockTask(id="task-1", value=1, delay=1.0)

        result = await processor.process_one(task)

        assert result.status == TaskStatus.TIMEOUT

    @pytest.mark.asyncio
    async def test_process_with_retry(self):
        """测试重试机制."""
        call_count = 0

        async def flakey_processor(task: MockTask) -> int:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary error")
            return task.value * 2

        config = ParallelConfig(retry_count=3, retry_delay=0.1)
        processor = AsyncParallelProcessor(flakey_processor, config)

        task = MockTask(id="task-1", value=5)
        result = await processor.process_one(task)

        assert result.success
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_process_batch(self, processor):
        """测试批量处理."""
        batches = [
            [MockTask(id="batch-1-task-1", value=1), MockTask(id="batch-1-task-2", value=2)],
            [MockTask(id="batch-2-task-1", value=3), MockTask(id="batch-2-task-2", value=4)],
        ]

        results = await processor.process_batches(batches)

        assert len(results) == 2
        assert all(len(batch_results) == 2 for batch_results in results)

    @pytest.mark.asyncio
    async def test_process_with_progress_callback(self, processor, tasks):
        """测试进度回调."""
        progress_events = []

        def on_progress(completed: int, total: int):
            progress_events.append((completed, total))

        await processor.process_all(tasks, on_progress=on_progress)

        assert len(progress_events) == 3
        assert progress_events[-1] == (3, 3)

    @pytest.mark.asyncio
    async def test_process_with_result_callback(self, processor, tasks):
        """测试结果回调."""
        results_collected = []

        async def on_result(result: ParallelResult):
            results_collected.append(result)

        await processor.process_all(tasks, on_result=on_result)

        assert len(results_collected) == 3

    @pytest.mark.asyncio
    async def test_get_stats(self, processor, tasks):
        """测试获取统计信息."""
        await processor.process_all(tasks)

        stats = processor.get_stats()

        assert stats["total_tasks"] == 3
        assert stats["successful"] == 3
        assert stats["failed"] == 0
        assert stats["success_rate"] == 1.0

    @pytest.mark.asyncio
    async def test_clear_stats(self, processor, tasks):
        """测试清除统计信息."""
        await processor.process_all(tasks)

        processor.clear_stats()

        stats = processor.get_stats()
        assert stats["total_tasks"] == 0

    @pytest.mark.asyncio
    async def test_process_empty_list(self, processor):
        """测试处理空列表."""
        results = await processor.process_all([])

        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_process_with_semaphore(self):
        """测试信号量控制."""
        config = ParallelConfig(max_concurrency=2)
        processor = AsyncParallelProcessor(mock_processor, config)

        concurrent_count = 0
        max_concurrent = 0

        async def counting_processor(task: MockTask) -> int:
            nonlocal concurrent_count, max_concurrent
            concurrent_count += 1
            max_concurrent = max(max_concurrent, concurrent_count)
            await asyncio.sleep(0.1)
            concurrent_count -= 1
            return task.value * 2

        processor._process_func = counting_processor

        tasks = [MockTask(id=f"task-{i}", value=i, delay=0.1) for i in range(5)]
        await processor.process_all(tasks)

        assert max_concurrent <= 2


class TestAsyncParallelProcessorIntegration:
    """AsyncParallelProcessor 集成测试."""

    @pytest.mark.asyncio
    async def test_full_workflow(self):
        """测试完整工作流."""
        processor = AsyncParallelProcessor(
            mock_processor,
            config=ParallelConfig(
                max_concurrency=4,
                timeout=30,
                retry_count=2,
            ),
        )

        tasks = [
            MockTask(id=f"task-{i}", value=i, delay=0.05)
            for i in range(10)
        ]

        results = await processor.process_all(tasks)

        assert len(results) == 10
        assert all(r.success for r in results)

        stats = processor.get_stats()
        assert stats["success_rate"] == 1.0

    @pytest.mark.asyncio
    async def test_mixed_success_failure(self):
        """测试混合成功失败场景."""
        processor = AsyncParallelProcessor(mock_processor)

        tasks = [
            MockTask(id="success-1", value=1),
            MockTask(id="fail-1", value=2, should_fail=True),
            MockTask(id="success-2", value=3),
            MockTask(id="fail-2", value=4, should_fail=True),
            MockTask(id="success-3", value=5),
        ]

        results = await processor.process_all(tasks)

        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]

        assert len(successful) == 3
        assert len(failed) == 2

        stats = processor.get_stats()
        assert stats["success_rate"] == 0.6
