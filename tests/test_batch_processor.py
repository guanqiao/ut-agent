"""LLM 调用批处理优化单元测试."""

import time
from unittest.mock import Mock, patch, MagicMock

import pytest

from ut_agent.utils.batch_processor import (
    BatchRequest,
    BatchResult,
    RequestQueue,
    BatchProcessor,
    ConcurrentExecutor,
    RateLimiter,
    LLMBatchClient,
)


class TestBatchRequest:
    """批处理请求测试."""

    def test_batch_request_creation(self):
        """测试创建批处理请求."""
        request = BatchRequest(id="test-1", data="test_data")

        assert request.id == "test-1"
        assert request.data == "test_data"
        assert request.result is None
        assert request.error is None

    def test_batch_request_complete(self):
        """测试完成请求."""
        request = BatchRequest(id="test-1", data="test_data")
        request.complete("result")

        assert request.result == "result"
        assert request.completed_at is not None

    def test_batch_request_complete_with_callback(self):
        """测试带回调的完成请求."""
        callback_result = []

        def callback(result):
            callback_result.append(result)

        request = BatchRequest(id="test-1", data="test_data", callback=callback)
        request.complete("result")

        assert callback_result == ["result"]

    def test_batch_request_fail(self):
        """测试请求失败."""
        request = BatchRequest(id="test-1", data="test_data")
        error = ValueError("test error")
        request.fail(error)

        assert request.error == error
        assert request.completed_at is not None


class TestBatchResult:
    """批处理结果测试."""

    def test_batch_result_creation(self):
        """测试创建批处理结果."""
        result = BatchResult(
            results=["r1", "r2"],
            errors=[ValueError("e1")],
            total_time=1.5,
            batch_size=3,
        )

        assert result.success_count == 2
        assert result.error_count == 1
        assert result.total_time == 1.5


class TestRequestQueue:
    """请求队列测试."""

    def test_queue_put_get(self):
        """测试队列放入和获取."""
        queue = RequestQueue[str, str]()
        request = BatchRequest(id="test-1", data="data")

        queue.put(request)
        result = queue.get(timeout=0.1)

        assert result == request

    def test_queue_get_batch(self):
        """测试获取一批请求."""
        queue = RequestQueue[str, str]()

        for i in range(5):
            queue.put(BatchRequest(id=f"test-{i}", data=f"data-{i}"))

        batch = queue.get_batch(batch_size=3, timeout=0.1)

        assert len(batch) == 3

    def test_queue_size(self):
        """测试队列大小."""
        queue = RequestQueue[str, str]()

        queue.put(BatchRequest(id="test-1", data="data"))
        queue.put(BatchRequest(id="test-2", data="data"))

        assert queue.size() == 2

    def test_queue_clear(self):
        """测试清空队列."""
        queue = RequestQueue[str, str]()

        queue.put(BatchRequest(id="test-1", data="data"))
        queue.clear()

        assert queue.size() == 0

    def test_queue_max_size(self):
        """测试队列最大大小."""
        queue = RequestQueue[str, str](max_size=2)

        assert queue.put(BatchRequest(id="test-1", data="data")) is True
        assert queue.put(BatchRequest(id="test-2", data="data")) is True
        assert queue.put(BatchRequest(id="test-3", data="data")) is False


class TestBatchProcessor:
    """批处理器测试."""

    def test_batch_processor_creation(self):
        """测试创建批处理器."""
        def process_func(items):
            return [item.upper() for item in items]

        processor = BatchProcessor(
            process_func=process_func,
            batch_size=5,
            max_concurrency=2,
        )

        assert processor._batch_size == 5
        assert processor._max_concurrency == 2

    def test_batch_processor_submit(self):
        """测试提交请求."""
        def process_func(items):
            return [item.upper() for item in items]

        processor = BatchProcessor(
            process_func=process_func,
            batch_size=5,
            max_concurrency=1,
            flush_interval=0.1,
        )

        request = processor.submit("test")

        assert request.id is not None
        assert request.data == "test"

    def test_batch_processor_start_stop(self):
        """测试启动和停止."""
        def process_func(items):
            return items

        processor = BatchProcessor(
            process_func=process_func,
            batch_size=5,
            max_concurrency=1,
        )

        processor.start()
        assert processor._running is True

        processor.stop()
        assert processor._running is False


class TestConcurrentExecutor:
    """并发执行器测试."""

    def test_execute_single(self):
        """测试执行单个任务."""
        executor = ConcurrentExecutor(max_workers=2)

        result = executor.execute(lambda x: x * 2, 5)

        assert result == 10

    def test_execute_batch(self):
        """测试批量执行."""
        executor = ConcurrentExecutor(max_workers=4)

        results = executor.execute_batch(lambda x: x * 2, [1, 2, 3, 4])

        assert sorted(results) == [2, 4, 6, 8]

    def test_max_workers_limit(self):
        """测试最大工作线程限制."""
        executor = ConcurrentExecutor(max_workers=2)

        active_counts = []

        def track_active(x):
            active_counts.append(executor.active_count)
            time.sleep(0.1)
            return x

        executor.execute_batch(track_active, [1, 2, 3, 4])

        assert max(active_counts) <= 2


class TestRateLimiter:
    """速率限制器测试."""

    def test_rate_limiter_basic(self):
        """测试基本速率限制."""
        limiter = RateLimiter(requests_per_second=10.0)

        start = time.time()
        for _ in range(3):
            limiter.acquire()
        elapsed = time.time() - start

        assert elapsed >= 0.2

    def test_rate_limiter_set_rate(self):
        """测试设置速率."""
        limiter = RateLimiter(requests_per_second=10.0)

        limiter.set_rate(100.0)

        assert limiter._rate == 100.0


class TestLLMBatchClient:
    """LLM 批处理客户端测试."""

    def test_client_creation(self):
        """测试创建客户端."""
        mock_llm = Mock()
        client = LLMBatchClient(
            llm_client=mock_llm,
            batch_size=5,
            max_concurrency=2,
        )

        assert client._batch_size == 5

    def test_client_start_stop(self):
        """测试启动和停止客户端."""
        mock_llm = Mock()
        client = LLMBatchClient(llm_client=mock_llm)

        client.start()
        assert client._processor is not None

        client.stop()

    def test_client_submit_without_start(self):
        """测试未启动时提交请求."""
        mock_llm = Mock()
        client = LLMBatchClient(llm_client=mock_llm)

        with pytest.raises(RuntimeError):
            client.submit("test prompt")

    def test_process_llm_batch(self):
        """测试处理 LLM 批量请求."""
        mock_llm = Mock()
        mock_llm.invoke.return_value = "response"

        client = LLMBatchClient(
            llm_client=mock_llm,
            batch_size=2,
            rate_limit=100.0,
        )

        results = client._process_llm_batch(["prompt1", "prompt2"])

        assert len(results) == 2
        assert results == ["response", "response"]
