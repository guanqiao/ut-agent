"""分布式任务队列测试."""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from ut_agent.distributed.task_queue import TaskQueue, Task, TaskStatus, TaskPriority


class TestTask:
    """任务模型测试."""

    def test_task_creation(self):
        """测试任务创建."""
        task = Task(
            id="test-123",
            name="generate_tests",
            payload={"file_path": "/path/to/file.py"},
            priority=TaskPriority.NORMAL
        )
        assert task.id == "test-123"
        assert task.name == "generate_tests"
        assert task.status == TaskStatus.PENDING
        assert task.priority == TaskPriority.NORMAL

    def test_task_priority_comparison(self):
        """测试任务优先级比较."""
        high_task = Task(id="1", name="test", payload={}, priority=TaskPriority.HIGH)
        normal_task = Task(id="2", name="test", payload={}, priority=TaskPriority.NORMAL)
        low_task = Task(id="3", name="test", payload={}, priority=TaskPriority.LOW)
        
        assert high_task.priority.value > normal_task.priority.value
        assert normal_task.priority.value > low_task.priority.value

    def test_task_to_dict(self):
        """测试任务序列化."""
        task = Task(
            id="test-123",
            name="generate_tests",
            payload={"key": "value"},
            priority=TaskPriority.HIGH
        )
        data = task.to_dict()
        
        assert data["id"] == "test-123"
        assert data["name"] == "generate_tests"
        assert data["payload"] == {"key": "value"}
        assert data["priority"] == "high"

    def test_task_from_dict(self):
        """测试任务反序列化."""
        data = {
            "id": "test-123",
            "name": "generate_tests",
            "payload": {"key": "value"},
            "priority": "high",
            "status": "pending",
            "created_at": datetime.now().isoformat()
        }
        task = Task.from_dict(data)
        
        assert task.id == "test-123"
        assert task.priority == TaskPriority.HIGH
        assert task.status == TaskStatus.PENDING


class TestTaskQueue:
    """任务队列测试."""

    @pytest.fixture
    async def queue(self):
        """创建任务队列实例."""
        queue = TaskQueue(backend="memory")
        await queue.connect()
        yield queue
        await queue.disconnect()

    @pytest.mark.asyncio
    async def test_connect_disconnect(self):
        """测试连接和断开."""
        queue = TaskQueue(backend="memory")
        await queue.connect()
        assert queue.is_connected is True
        
        await queue.disconnect()
        assert queue.is_connected is False

    @pytest.mark.asyncio
    async def test_submit_task(self, queue):
        """测试提交任务."""
        task = Task(
            id="test-123",
            name="generate_tests",
            payload={"file_path": "/path/to/file.py"}
        )
        
        task_id = await queue.submit(task)
        assert task_id == "test-123"
        
        # 验证任务已存储
        stored_task = await queue.get_task(task_id)
        assert stored_task is not None
        assert stored_task.status == TaskStatus.PENDING

    @pytest.mark.asyncio
    async def test_submit_with_priority(self, queue):
        """测试按优先级提交任务."""
        low_task = Task(id="low", name="test", payload={}, priority=TaskPriority.LOW)
        high_task = Task(id="high", name="test", payload={}, priority=TaskPriority.HIGH)
        normal_task = Task(id="normal", name="test", payload={}, priority=TaskPriority.NORMAL)
        
        await queue.submit(low_task)
        await queue.submit(high_task)
        await queue.submit(normal_task)
        
        # 获取任务应该按优先级排序
        tasks = await queue.list_pending_tasks()
        assert len(tasks) == 3
        assert tasks[0].id == "high"
        assert tasks[1].id == "normal"
        assert tasks[2].id == "low"

    @pytest.mark.asyncio
    async def test_consume_task(self, queue):
        """测试消费任务."""
        task = Task(id="test-123", name="generate_tests", payload={})
        await queue.submit(task)
        
        consumed_task = await queue.consume()
        assert consumed_task is not None
        assert consumed_task.id == "test-123"
        assert consumed_task.status == TaskStatus.PROCESSING

    @pytest.mark.asyncio
    async def test_consume_empty_queue(self, queue):
        """测试消费空队列."""
        task = await queue.consume(timeout=0.1)
        assert task is None

    @pytest.mark.asyncio
    async def test_complete_task(self, queue):
        """测试完成任务."""
        task = Task(id="test-123", name="generate_tests", payload={})
        await queue.submit(task)
        
        await queue.complete(task.id, result={"tests": ["test1", "test2"]})
        
        completed_task = await queue.get_task(task.id)
        assert completed_task.status == TaskStatus.COMPLETED
        assert completed_task.result == {"tests": ["test1", "test2"]}

    @pytest.mark.asyncio
    async def test_fail_task(self, queue):
        """测试失败任务."""
        task = Task(id="test-123", name="generate_tests", payload={})
        await queue.submit(task)
        
        await queue.fail(task.id, error="Test generation failed")
        
        failed_task = await queue.get_task(task.id)
        assert failed_task.status == TaskStatus.FAILED
        assert failed_task.error == "Test generation failed"

    @pytest.mark.asyncio
    async def test_retry_task(self, queue):
        """测试重试任务."""
        task = Task(id="test-123", name="generate_tests", payload={}, max_retries=3)
        await queue.submit(task)
        
        # 第一次失败
        await queue.fail(task.id, error="Temporary error", retry=True)
        
        retried_task = await queue.get_task(task.id)
        assert retried_task.status == TaskStatus.PENDING
        assert retried_task.retry_count == 1

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self, queue):
        """测试超过最大重试次数."""
        task = Task(id="test-123", name="generate_tests", payload={}, max_retries=2)
        await queue.submit(task)
        
        # 失败三次（每次都会增加 retry_count）
        for _ in range(3):
            await queue.fail(task.id, error="Error", retry=True)
        
        failed_task = await queue.get_task(task.id)
        assert failed_task.status == TaskStatus.FAILED
        # retry_count 会在每次 fail 时增加，所以是 3
        assert failed_task.retry_count >= 2

    @pytest.mark.asyncio
    async def test_cancel_task(self, queue):
        """测试取消任务."""
        task = Task(id="test-123", name="generate_tests", payload={})
        await queue.submit(task)
        
        await queue.cancel(task.id)
        
        cancelled_task = await queue.get_task(task.id)
        assert cancelled_task.status == TaskStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_get_task_status(self, queue):
        """测试获取任务状态."""
        task = Task(id="test-123", name="generate_tests", payload={})
        await queue.submit(task)
        
        status = await queue.get_status(task.id)
        assert status == TaskStatus.PENDING

    @pytest.mark.asyncio
    async def test_list_tasks_by_status(self, queue):
        """测试按状态列出任务."""
        # 创建不同状态的任务
        pending_task = Task(id="pending", name="test", payload={})
        completed_task = Task(id="completed", name="test", payload={})
        failed_task = Task(id="failed", name="test", payload={})
        
        await queue.submit(pending_task)
        await queue.submit(completed_task)
        await queue.submit(failed_task)
        
        await queue.complete(completed_task.id, result={})
        await queue.fail(failed_task.id, error="error")
        
        pending_tasks = await queue.list_tasks(status=TaskStatus.PENDING)
        assert len(pending_tasks) == 1
        assert pending_tasks[0].id == "pending"

    @pytest.mark.asyncio
    async def test_task_timeout(self, queue):
        """测试任务超时."""
        task = Task(
            id="test-123",
            name="generate_tests",
            payload={},
            timeout=timedelta(seconds=1)
        )
        await queue.submit(task)
        
        # 模拟任务处理超时
        await queue.consume()
        await asyncio.sleep(1.1)
        
        # 检查超时任务应该被重新放入队列或标记为失败
        await queue.check_timeouts()
        
        task_after_timeout = await queue.get_task(task.id)
        assert task_after_timeout.status in [TaskStatus.PENDING, TaskStatus.FAILED]

    @pytest.mark.asyncio
    async def test_queue_stats(self, queue):
        """测试队列统计信息."""
        # 添加一些任务
        await queue.submit(Task(id="1", name="test", payload={}))
        await queue.submit(Task(id="2", name="test", payload={}))
        await queue.complete("1", result={})
        
        stats = await queue.get_stats()
        
        assert stats["pending"] == 1
        assert stats["completed"] == 1
        assert stats["total"] == 2

    @pytest.mark.asyncio
    async def test_clear_completed_tasks(self, queue):
        """测试清理已完成任务."""
        # 添加并完成任务
        await queue.submit(Task(id="completed", name="test", payload={}))
        await queue.complete("completed", result={})
        
        # 添加待处理任务
        await queue.submit(Task(id="pending", name="test", payload={}))
        
        await queue.clear_completed(age=timedelta(seconds=0))
        
        # 已完成的任务应该被清理
        completed_task = await queue.get_task("completed")
        assert completed_task is None
        
        # 待处理任务应该保留
        pending_task = await queue.get_task("pending")
        assert pending_task is not None


class TestTaskQueueWithRedis:
    """使用 Redis 后端的任务队列测试."""

    @pytest.fixture
    async def redis_queue(self):
        """创建 Redis 任务队列实例."""
        # 这些测试在没有 Redis 时跳过
        try:
            import redis.asyncio as aioredis
            client = aioredis.from_url("redis://localhost")
            await client.ping()
            
            queue = TaskQueue(backend="redis", redis_url="redis://localhost")
            await queue.connect()
            yield queue
            await queue.disconnect()
        except Exception:
            pytest.skip("Redis not available")

    @pytest.mark.asyncio
    async def test_redis_backend(self, redis_queue):
        """测试 Redis 后端."""
        task = Task(id="test-123", name="generate_tests", payload={"key": "value"})
        await redis_queue.submit(task)
        
        stored_task = await redis_queue.get_task("test-123")
        assert stored_task is not None
        assert stored_task.payload == {"key": "value"}


class TestTaskQueueIntegration:
    """任务队列集成测试."""

    @pytest.mark.asyncio
    async def test_producer_consumer_pattern(self):
        """测试生产者-消费者模式."""
        queue = TaskQueue(backend="memory")
        await queue.connect()
        
        try:
            # 生产者提交任务
            tasks = [
                Task(id=f"task-{i}", name="process", payload={"index": i})
                for i in range(5)
            ]
            for task in tasks:
                await queue.submit(task)
            
            # 消费者处理任务
            processed = []
            for _ in range(5):
                task = await queue.consume(timeout=1.0)
                if task:
                    processed.append(task.id)
                    await queue.complete(task.id, result={"processed": True})
            
            assert len(processed) == 5
        finally:
            await queue.disconnect()

    @pytest.mark.asyncio
    async def test_concurrent_consumers(self):
        """测试并发消费者."""
        queue = TaskQueue(backend="memory")
        await queue.connect()
        
        try:
            # 提交多个任务
            for i in range(10):
                await queue.submit(Task(id=f"task-{i}", name="process", payload={}))
            
            # 并发消费
            results = []
            
            async def consumer():
                while True:
                    task = await queue.consume(timeout=0.5)
                    if task is None:
                        break
                    await queue.complete(task.id, result={})
                    results.append(task.id)
            
            # 启动3个并发消费者
            await asyncio.gather(
                consumer(),
                consumer(),
                consumer()
            )
            
            assert len(results) == 10
        finally:
            await queue.disconnect()
