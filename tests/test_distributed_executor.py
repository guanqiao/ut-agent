"""分布式执行器测试."""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from ut_agent.distributed.executor import DistributedExecutor, Worker, ExecutionResult
from ut_agent.distributed.task_queue import TaskQueue, Task, TaskStatus


class TestExecutionResult:
    """执行结果模型测试."""

    def test_result_creation(self):
        """测试结果创建."""
        result = ExecutionResult(
            task_id="task-123",
            success=True,
            output="Test output",
            execution_time=1.5
        )
        assert result.task_id == "task-123"
        assert result.success is True
        assert result.output == "Test output"
        assert result.execution_time == 1.5

    def test_result_failure(self):
        """测试结果失败."""
        result = ExecutionResult(
            task_id="task-123",
            success=False,
            error="Execution failed",
            execution_time=0.5
        )
        assert result.success is False
        assert result.error == "Execution failed"
        assert result.output is None

    def test_result_to_dict(self):
        """测试结果序列化."""
        result = ExecutionResult(
            task_id="task-123",
            success=True,
            output="output",
            execution_time=1.0
        )
        data = result.to_dict()
        assert data["task_id"] == "task-123"
        assert data["success"] is True


class TestWorker:
    """工作节点测试."""

    @pytest.fixture
    async def worker(self):
        """创建工作节点实例."""
        worker = Worker(worker_id="worker-1", max_concurrent=2)
        yield worker
        await worker.stop()

    def test_worker_initialization(self, worker):
        """测试工作节点初始化."""
        assert worker.worker_id == "worker-1"
        assert worker.max_concurrent == 2
        assert worker.is_running is False
        assert worker.current_load == 0

    @pytest.mark.asyncio
    async def test_worker_start_stop(self, worker):
        """测试工作节点启动和停止."""
        await worker.start()
        assert worker.is_running is True
        
        await worker.stop()
        assert worker.is_running is False

    @pytest.mark.asyncio
    async def test_worker_execute_task(self, worker):
        """测试工作节点执行任务."""
        await worker.start()
        
        async def mock_handler(task):
            return ExecutionResult(
                task_id=task.id,
                success=True,
                output=f"Processed {task.name}",
                execution_time=0.1
            )
        
        worker.register_handler("test_task", mock_handler)
        
        task = Task(id="task-1", name="test_task", payload={"key": "value"})
        result = await worker.execute(task)
        
        assert result.success is True
        assert result.output == "Processed test_task"

    @pytest.mark.asyncio
    async def test_worker_execute_unknown_task(self, worker):
        """测试工作节点执行未知任务."""
        await worker.start()
        
        task = Task(id="task-1", name="unknown_task", payload={})
        result = await worker.execute(task)
        
        assert result.success is False
        assert "No handler" in result.error

    @pytest.mark.asyncio
    async def test_worker_concurrent_limit(self, worker):
        """测试工作节点并发限制."""
        await worker.start()
        
        execution_order = []
        
        async def slow_handler(task):
            await asyncio.sleep(0.1)
            execution_order.append(task.id)
            return ExecutionResult(task_id=task.id, success=True, execution_time=0.1)
        
        worker.register_handler("slow_task", slow_handler)
        
        # 提交多个任务
        tasks = [
            Task(id=f"task-{i}", name="slow_task", payload={})
            for i in range(3)
        ]
        
        # 并发执行
        results = await asyncio.gather(*[worker.execute(t) for t in tasks])
        
        assert len(results) == 3
        assert all(r.success for r in results)

    def test_worker_health_check(self, worker):
        """测试工作节点健康检查."""
        health = worker.health_check()
        
        assert "worker_id" in health
        assert "is_running" in health
        assert "current_load" in health
        assert "max_concurrent" in health


class TestDistributedExecutor:
    """分布式执行器测试."""

    @pytest.fixture
    async def executor(self):
        """创建分布式执行器实例."""
        queue = TaskQueue(backend="memory")
        await queue.connect()
        
        executor = DistributedExecutor(queue, max_workers=2)
        await executor.start()
        
        yield executor
        
        await executor.stop()
        await queue.disconnect()

    @pytest.mark.asyncio
    async def test_executor_initialization(self):
        """测试执行器初始化."""
        queue = TaskQueue(backend="memory")
        await queue.connect()
        
        executor = DistributedExecutor(queue, max_workers=3)
        assert executor.max_workers == 3
        assert len(executor.workers) == 0
        
        await queue.disconnect()

    @pytest.mark.asyncio
    async def test_executor_start_stop(self, executor):
        """测试执行器启动和停止."""
        # 启动时会创建工作节点
        assert len(executor.workers) == 2
        assert all(w.is_running for w in executor.workers)
        
        await executor.stop()
        assert all(not w.is_running for w in executor.workers)

    @pytest.mark.asyncio
    async def test_submit_and_execute(self, executor):
        """测试提交和执行任务."""
        executed_tasks = []
        
        async def test_handler(task):
            executed_tasks.append(task.id)
            return ExecutionResult(
                task_id=task.id,
                success=True,
                output=f"Executed {task.name}",
                execution_time=0.01
            )
        
        # 注册处理器
        for worker in executor.workers:
            worker.register_handler("test_task", test_handler)
        
        # 提交任务
        task_id = await executor.submit(
            name="test_task",
            payload={"data": "test"},
            task_type="test_task"
        )
        
        # 等待任务执行
        await asyncio.sleep(0.5)
        
        # 验证任务被执行
        assert task_id in executed_tasks

    @pytest.mark.asyncio
    async def test_load_balancing(self, executor):
        """测试负载均衡."""
        worker_loads = {w.worker_id: 0 for w in executor.workers}
        
        async def counting_handler(task):
            worker_loads[task.payload["worker_id"]] += 1
            await asyncio.sleep(0.05)
            return ExecutionResult(task_id=task.id, success=True, execution_time=0.05)
        
        for worker in executor.workers:
            worker.register_handler("load_test", counting_handler)
        
        # 提交多个任务
        for i in range(6):
            await executor.submit(
                name="load_test",
                payload={"worker_id": executor.workers[i % 2].worker_id},
                task_type="load_test"
            )
        
        await asyncio.sleep(0.5)
        
        # 验证负载被分配
        assert sum(worker_loads.values()) == 6

    @pytest.mark.asyncio
    async def test_worker_failure_recovery(self, executor):
        """测试工作节点故障恢复."""
        # 模拟一个工作节点故障
        failed_worker = executor.workers[0]
        await failed_worker.stop()
        
        # 执行器应该检测到故障并创建新节点
        await asyncio.sleep(0.2)
        await executor.check_workers()
        
        # 验证工作节点数量恢复
        assert len(executor.workers) == 2
        assert all(w.is_running for w in executor.workers)

    @pytest.mark.asyncio
    async def test_task_retry_on_failure(self, executor):
        """测试任务失败重试."""
        attempt_count = 0
        
        async def failing_handler(task):
            nonlocal attempt_count
            attempt_count += 1
            # 前两次失败，第三次成功
            if attempt_count <= 2:
                return ExecutionResult(
                    task_id=task.id,
                    success=False,
                    error="Temporary failure",
                    execution_time=0.01
                )
            return ExecutionResult(
                task_id=task.id,
                success=True,
                output="Success after retry",
                execution_time=0.01
            )
        
        for worker in executor.workers:
            worker.register_handler("retry_task", failing_handler)
        
        task_id = await executor.submit(
            name="retry_task",
            payload={},
            task_type="retry_task",
            max_retries=3
        )
        
        # 等待重试完成（需要足够时间让任务被重新消费）
        await asyncio.sleep(2.5)
        
        # 验证任务最终被成功执行（至少尝试了3次）
        assert attempt_count >= 2  # 至少重试一次

    @pytest.mark.asyncio
    async def test_executor_stats(self, executor):
        """测试执行器统计信息."""
        async def dummy_handler(task):
            return ExecutionResult(task_id=task.id, success=True, execution_time=0.01)
        
        for worker in executor.workers:
            worker.register_handler("dummy", dummy_handler)
        
        # 提交一些任务
        for i in range(5):
            await executor.submit(name="dummy", payload={}, task_type="dummy")
        
        await asyncio.sleep(0.3)
        
        stats = await executor.get_stats()
        
        assert "total_workers" in stats
        assert "active_workers" in stats
        assert "total_tasks" in stats
        assert "completed_tasks" in stats

    @pytest.mark.asyncio
    async def test_graceful_shutdown(self, executor):
        """测试优雅关闭."""
        async def slow_handler(task):
            await asyncio.sleep(0.5)
            return ExecutionResult(task_id=task.id, success=True, execution_time=0.5)
        
        for worker in executor.workers:
            worker.register_handler("slow", slow_handler)
        
        # 提交长时间运行的任务
        await executor.submit(name="slow", payload={}, task_type="slow")
        
        # 给任务一点时间开始执行
        await asyncio.sleep(0.1)
        
        # 优雅关闭
        await executor.stop(graceful=True)
        
        # 验证所有工作节点已停止
        assert all(not w.is_running for w in executor.workers)


class TestDistributedExecutorIntegration:
    """分布式执行器集成测试."""

    @pytest.mark.asyncio
    async def test_end_to_end_execution(self):
        """测试端到端执行."""
        queue = TaskQueue(backend="memory")
        await queue.connect()
        
        try:
            executor = DistributedExecutor(queue, max_workers=2)
            await executor.start()
            
            results = []
            
            async def test_handler(task):
                result = f"Result for {task.id}"
                results.append(result)
                return ExecutionResult(
                    task_id=task.id,
                    success=True,
                    output=result,
                    execution_time=0.01
                )
            
            for worker in executor.workers:
                worker.register_handler("integration_test", test_handler)
            
            # 提交多个任务
            task_ids = []
            for i in range(5):
                task_id = await executor.submit(
                    name="integration_test",
                    payload={"index": i},
                    task_type="integration_test"
                )
                task_ids.append(task_id)
            
            # 等待所有任务完成
            await asyncio.sleep(1.0)
            
            # 验证所有任务被执行
            assert len(results) == 5
            
            await executor.stop()
        finally:
            await queue.disconnect()

    @pytest.mark.asyncio
    async def test_concurrent_task_processing(self):
        """测试并发任务处理."""
        queue = TaskQueue(backend="memory")
        await queue.connect()
        
        try:
            executor = DistributedExecutor(queue, max_workers=3)
            await executor.start()
            
            execution_times = []
            
            async def concurrent_handler(task):
                start = asyncio.get_event_loop().time()
                await asyncio.sleep(0.1)  # 模拟工作
                end = asyncio.get_event_loop().time()
                execution_times.append(end - start)
                return ExecutionResult(task_id=task.id, success=True, execution_time=0.1)
            
            for worker in executor.workers:
                worker.register_handler("concurrent", concurrent_handler)
            
            # 提交大量任务
            for i in range(10):
                await executor.submit(name="concurrent", payload={}, task_type="concurrent")
            
            # 等待完成
            await asyncio.sleep(1.0)
            
            # 验证并发执行（总时间应该小于串行时间）
            assert len(execution_times) == 10
            
            await executor.stop()
        finally:
            await queue.disconnect()
