"""LLM 调用批处理优化.

提供批量请求合并、请求队列管理和并发控制功能。
"""

import asyncio
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Generic, List, Optional, TypeVar

from ut_agent.utils import get_logger

logger = get_logger("batch_processor")

T = TypeVar('T')
R = TypeVar('R')


@dataclass
class BatchRequest(Generic[T, R]):
    """批处理请求."""
    id: str
    data: T
    callback: Optional[Callable[[R], None]] = None
    result: Optional[R] = None
    error: Optional[Exception] = None
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None

    def complete(self, result: R) -> None:
        """完成请求."""
        self.result = result
        self.completed_at = time.time()
        if self.callback:
            self.callback(result)

    def fail(self, error: Exception) -> None:
        """请求失败."""
        self.error = error
        self.completed_at = time.time()


@dataclass
class BatchResult(Generic[R]):
    """批处理结果."""
    results: List[R] = field(default_factory=list)
    errors: List[Exception] = field(default_factory=list)
    total_time: float = 0.0
    batch_size: int = 0

    @property
    def success_count(self) -> int:
        return len(self.results)

    @property
    def error_count(self) -> int:
        return len(self.errors)


class RequestQueue(Generic[T, R]):
    """请求队列."""

    def __init__(self, max_size: int = 1000):
        self._queue: deque[BatchRequest[T, R]] = deque(maxlen=max_size)
        self._lock = threading.Lock()
        self._not_empty = threading.Condition(self._lock)

    def put(self, request: BatchRequest[T, R]) -> bool:
        """添加请求到队列."""
        with self._lock:
            if len(self._queue) >= self._queue.maxlen:
                return False
            self._queue.append(request)
            self._not_empty.notify()
            return True

    def get(self, timeout: Optional[float] = None) -> Optional[BatchRequest[T, R]]:
        """从队列获取请求."""
        with self._not_empty:
            if not self._queue:
                if not self._not_empty.wait(timeout or 0.1):
                    return None
            if self._queue:
                return self._queue.popleft()
            return None

    def get_batch(self, batch_size: int, timeout: float = 0.1) -> List[BatchRequest[T, R]]:
        """获取一批请求."""
        batch = []
        deadline = time.time() + timeout

        while len(batch) < batch_size:
            remaining = deadline - time.time()
            if remaining <= 0:
                break

            request = self.get(timeout=min(remaining, 0.01))
            if request:
                batch.append(request)
            elif batch:
                break

        return batch

    def size(self) -> int:
        """获取队列大小."""
        with self._lock:
            return len(self._queue)

    def clear(self) -> None:
        """清空队列."""
        with self._lock:
            self._queue.clear()


class BatchProcessor(Generic[T, R]):
    """批处理器."""

    def __init__(
        self,
        process_func: Callable[[List[T]], List[R]],
        batch_size: int = 10,
        max_concurrency: int = 4,
        flush_interval: float = 0.5,
        queue_size: int = 1000,
    ):
        self._process_func = process_func
        self._batch_size = batch_size
        self._max_concurrency = max_concurrency
        self._flush_interval = flush_interval

        self._queue: RequestQueue[T, R] = RequestQueue(max_size=queue_size)
        self._running = False
        self._workers: List[threading.Thread] = []
        self._semaphore = threading.Semaphore(max_concurrency)

    def start(self) -> None:
        """启动批处理器."""
        if self._running:
            return

        self._running = True

        for i in range(self._max_concurrency):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"batch-worker-{i}",
                daemon=True,
            )
            worker.start()
            self._workers.append(worker)

        logger.info(f"Batch processor started with {self._max_concurrency} workers")

    def stop(self) -> None:
        """停止批处理器."""
        self._running = False

        for worker in self._workers:
            worker.join(timeout=5)

        self._workers.clear()
        logger.info("Batch processor stopped")

    def submit(
        self,
        data: T,
        callback: Optional[Callable[[R], None]] = None,
    ) -> BatchRequest[T, R]:
        """提交请求."""
        request = BatchRequest(
            id=f"req-{time.time()}-{id(data)}",
            data=data,
            callback=callback,
        )

        if not self._queue.put(request):
            request.fail(Exception("Queue is full"))
            return request

        return request

    def submit_batch(
        self,
        data_list: List[T],
        callback: Optional[Callable[[R], None]] = None,
    ) -> List[BatchRequest[T, R]]:
        """批量提交请求."""
        return [self.submit(data, callback) for data in data_list]

    def _worker_loop(self) -> None:
        """工作线程循环."""
        while self._running:
            with self._semaphore:
                batch = self._queue.get_batch(
                    self._batch_size,
                    timeout=self._flush_interval,
                )

                if not batch:
                    continue

                self._process_batch(batch)

    def _process_batch(self, batch: List[BatchRequest[T, R]]) -> None:
        """处理一批请求."""
        start_time = time.time()

        try:
            data_list = [req.data for req in batch]
            results = self._process_func(data_list)

            for i, request in enumerate(batch):
                if i < len(results):
                    request.complete(results[i])
                else:
                    request.fail(Exception("Missing result"))

        except Exception as error:
            logger.error(f"Batch processing error: {error}")
            for request in batch:
                request.fail(error)

        elapsed = time.time() - start_time
        logger.debug(f"Processed batch of {len(batch)} in {elapsed:.3f}s")


class ConcurrentExecutor:
    """并发执行器."""

    def __init__(self, max_workers: int = 4):
        self._max_workers = max_workers
        self._semaphore = threading.Semaphore(max_workers)
        self._active_count = 0
        self._lock = threading.Lock()

    def execute(
        self,
        func: Callable[..., R],
        *args: Any,
        **kwargs: Any,
    ) -> R:
        """执行函数（带并发限制）."""
        with self._semaphore:
            with self._lock:
                self._active_count += 1

            try:
                return func(*args, **kwargs)
            finally:
                with self._lock:
                    self._active_count -= 1

    def execute_batch(
        self,
        func: Callable[[T], R],
        items: List[T],
    ) -> List[R]:
        """批量执行函数."""
        results: List[Optional[R]] = [None] * len(items)
        errors: List[Optional[Exception]] = [None] * len(items)

        def worker(index: int, item: T) -> None:
            try:
                results[index] = self.execute(func, item)
            except Exception as e:
                errors[index] = e

        threads = []
        for i, item in enumerate(items):
            thread = threading.Thread(target=worker, args=(i, item))
            thread.start()
            threads.append(thread)

        for thread in threads:
            thread.join()

        for i, error in enumerate(errors):
            if error:
                raise error

        return [r for r in results if r is not None]

    @property
    def active_count(self) -> int:
        """获取活跃任务数."""
        with self._lock:
            return self._active_count


class RateLimiter:
    """速率限制器."""

    def __init__(self, requests_per_second: float = 10.0):
        self._rate = requests_per_second
        self._interval = 1.0 / requests_per_second
        self._last_request_time = 0.0
        self._lock = threading.Lock()

    def acquire(self) -> None:
        """获取执行许可."""
        with self._lock:
            now = time.time()
            elapsed = now - self._last_request_time

            if elapsed < self._interval:
                sleep_time = self._interval - elapsed
                time.sleep(sleep_time)

            self._last_request_time = time.time()

    def set_rate(self, requests_per_second: float) -> None:
        """设置速率."""
        self._rate = requests_per_second
        self._interval = 1.0 / requests_per_second


class LLMBatchClient:
    """LLM 批处理客户端."""

    def __init__(
        self,
        llm_client: Any,
        batch_size: int = 5,
        max_concurrency: int = 2,
        rate_limit: float = 10.0,
    ):
        self._llm = llm_client
        self._batch_size = batch_size
        self._rate_limiter = RateLimiter(requests_per_second=rate_limit)

        self._processor: Optional[BatchProcessor] = None
        self._max_concurrency = max_concurrency

    def start(self) -> None:
        """启动批处理客户端."""
        self._processor = BatchProcessor(
            process_func=self._process_llm_batch,
            batch_size=self._batch_size,
            max_concurrency=self._max_concurrency,
        )
        self._processor.start()

    def stop(self) -> None:
        """停止批处理客户端."""
        if self._processor:
            self._processor.stop()

    def _process_llm_batch(self, prompts: List[str]) -> List[Any]:
        """处理 LLM 批量请求."""
        results = []

        for prompt in prompts:
            self._rate_limiter.acquire()
            try:
                result = self._llm.invoke(prompt)
                results.append(result)
            except Exception as e:
                logger.error(f"LLM batch request failed: {e}")
                results.append(None)

        return results

    def submit(self, prompt: str, callback: Optional[Callable] = None) -> BatchRequest:
        """提交 LLM 请求."""
        if not self._processor:
            raise RuntimeError("Batch processor not started")

        return self._processor.submit(prompt, callback)

    def submit_batch(
        self,
        prompts: List[str],
        callback: Optional[Callable] = None,
    ) -> List[BatchRequest]:
        """批量提交 LLM 请求."""
        if not self._processor:
            raise RuntimeError("Batch processor not started")

        return self._processor.submit_batch(prompts, callback)
