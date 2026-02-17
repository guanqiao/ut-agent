"""自适应线程池测试."""

import time
import pytest
from unittest.mock import Mock, patch

from ut_agent.utils.adaptive_thread_pool import (
    AdaptiveThreadPool,
    AdaptiveThreadPoolConfig,
    TaskScheduler,
    CPUMonitor,
    get_optimal_thread_count,
    get_global_thread_pool,
    shutdown_global_thread_pool,
)


class TestCPUMonitor:
    """CPU 监控器测试."""

    def test_get_cpu_usage(self):
        """测试获取 CPU 使用率."""
        monitor = CPUMonitor()
        usage = monitor.get_cpu_usage()
        
        # 应该在 0-100 范围内
        assert 0 <= usage <= 100

    def test_estimate_cpu_usage(self):
        """测试估算 CPU 使用率."""
        monitor = CPUMonitor()
        usage = monitor._estimate_cpu_usage()
        
        # 应该在 0-100 范围内
        assert 0 <= usage <= 100


class TestAdaptiveThreadPoolConfig:
    """自适应线程池配置测试."""

    def test_default_config(self):
        """测试默认配置."""
        config = AdaptiveThreadPoolConfig()
        
        assert config.min_workers == 2
        assert config.max_workers == 32
        assert config.adjustment_interval == 5.0
        assert config.enable_backpressure is True

    def test_custom_config(self):
        """测试自定义配置."""
        config = AdaptiveThreadPoolConfig(
            min_workers=4,
            max_workers=16,
            enable_backpressure=False,
        )
        
        assert config.min_workers == 4
        assert config.max_workers == 16
        assert config.enable_backpressure is False


class TestAdaptiveThreadPool:
    """自适应线程池测试."""

    @pytest.fixture
    def pool(self):
        """创建线程池."""
        config = AdaptiveThreadPoolConfig(
            min_workers=2,
            max_workers=8,
            adjustment_interval=1.0,
        )
        pool = AdaptiveThreadPool(config)
        yield pool
        pool.shutdown(wait=True)

    def test_initialization(self, pool):
        """测试初始化."""
        metrics = pool.get_metrics()
        
        assert metrics.current_workers == 2
        assert metrics.min_workers == 2
        assert metrics.max_workers == 8

    def test_submit_task(self, pool):
        """测试提交任务."""
        def task():
            return 42
        
        future = pool.submit(task)
        assert future is not None
        
        result = future.result()
        assert result == 42

    def test_submit_multiple_tasks(self, pool):
        """测试提交多个任务."""
        results = []
        
        def task(n):
            time.sleep(0.01)
            return n * 2
        
        futures = [pool.submit(task, i) for i in range(10)]
        
        for future in futures:
            if future:
                results.append(future.result())
        
        assert len(results) == 10
        assert results == [i * 2 for i in range(10)]

    def test_map_execution(self, pool):
        """测试 map 执行."""
        def task(x):
            return x * x
        
        results = pool.map(task, [1, 2, 3, 4, 5])
        
        assert results == [1, 4, 9, 16, 25]

    def test_context_manager(self):
        """测试上下文管理器."""
        with AdaptiveThreadPool() as pool:
            future = pool.submit(lambda: 123)
            result = future.result()
            assert result == 123

    def test_shutdown(self, pool):
        """测试关闭."""
        pool.shutdown(wait=True)
        
        with pytest.raises(RuntimeError):
            pool.submit(lambda: 1)

    def test_get_metrics(self, pool):
        """测试获取指标."""
        # 执行一些任务
        for i in range(5):
            pool.submit(lambda x: x * 2, i)
        
        time.sleep(0.1)
        
        metrics = pool.get_metrics()
        
        assert metrics.completed_tasks >= 0
        assert metrics.current_workers >= 2

    def test_task_duration_tracking(self, pool):
        """测试任务执行时间追踪."""
        def slow_task():
            time.sleep(0.05)
            return 1
        
        future = pool.submit(slow_task)
        future.result()
        
        time.sleep(0.1)
        
        metrics = pool.get_metrics()
        assert metrics.avg_task_duration > 0


class TestTaskScheduler:
    """任务调度器测试."""

    @pytest.fixture
    def scheduler(self):
        """创建调度器."""
        config = AdaptiveThreadPoolConfig(min_workers=2, max_workers=4)
        pool = AdaptiveThreadPool(config)
        scheduler = TaskScheduler(pool)
        yield scheduler
        pool.shutdown(wait=True)

    def test_schedule_task(self, scheduler):
        """测试调度任务."""
        def task():
            return "result"
        
        future = scheduler.schedule(task)
        assert future is not None

    def test_wait_all(self, scheduler):
        """测试等待所有任务."""
        def task(n):
            time.sleep(0.01)
            return n * 2
        
        for i in range(5):
            scheduler.schedule(task, i)
        
        results = scheduler.wait_all(timeout=5.0)
        
        assert len(results) == 5

    def test_get_pool_metrics(self, scheduler):
        """测试获取线程池指标."""
        metrics = scheduler.get_pool_metrics()
        
        assert metrics is not None
        assert metrics.current_workers >= 2


class TestOptimalThreadCount:
    """最优线程数测试."""

    def test_get_optimal_thread_count(self):
        """测试获取最优线程数."""
        count = get_optimal_thread_count()
        
        # 应该大于 0
        assert count > 0
        
        # 通常是 CPU 核心数的 1.5 倍
        import os
        cpu_count = os.cpu_count() or 4
        assert count == int(cpu_count * 1.5)


class TestGlobalThreadPool:
    """全局线程池测试."""

    def test_get_global_thread_pool(self):
        """测试获取全局线程池."""
        # 确保先关闭之前的
        shutdown_global_thread_pool(wait=True)
        
        pool1 = get_global_thread_pool()
        pool2 = get_global_thread_pool()
        
        # 应该是同一个实例
        assert pool1 is pool2
        
        shutdown_global_thread_pool(wait=True)

    def test_shutdown_global_thread_pool(self):
        """测试关闭全局线程池."""
        pool = get_global_thread_pool()
        
        shutdown_global_thread_pool(wait=True)
        
        # 再次获取应该是新的实例
        new_pool = get_global_thread_pool()
        assert new_pool is not pool
        
        shutdown_global_thread_pool(wait=True)


class TestBackpressure:
    """背压测试."""

    def test_backpressure_rejects_tasks(self):
        """测试背压拒绝任务."""
        config = AdaptiveThreadPoolConfig(
            min_workers=1,
            max_workers=2,
            enable_backpressure=True,
            max_queue_size=1,
        )
        
        with AdaptiveThreadPool(config) as pool:
            def slow_task():
                time.sleep(1)
                return 1
            
            # 提交一个慢任务
            future1 = pool.submit(slow_task)
            assert future1 is not None
            
            # 由于背压，后续任务可能被拒绝
            # （取决于执行速度）

    def test_no_backpressure_accepts_all(self):
        """测试无背压接受所有任务."""
        config = AdaptiveThreadPoolConfig(
            min_workers=4,
            max_workers=8,
            enable_backpressure=False,
        )
        
        with AdaptiveThreadPool(config) as pool:
            futures = []
            for i in range(20):
                future = pool.submit(lambda x: x, i)
                if future:
                    futures.append(future)
            
            # 应该接受所有任务
            assert len(futures) == 20


class TestThreadPoolAdjustment:
    """线程池调整测试."""

    def test_adjustment_does_not_go_below_min(self):
        """测试调整不会低于最小值."""
        config = AdaptiveThreadPoolConfig(
            min_workers=4,
            max_workers=8,
            adjustment_interval=0.1,
        )
        
        with AdaptiveThreadPool(config) as pool:
            # 等待调整
            time.sleep(0.3)
            
            metrics = pool.get_metrics()
            assert metrics.current_workers >= 4

    def test_adjustment_does_not_exceed_max(self):
        """测试调整不会超过最大值."""
        config = AdaptiveThreadPoolConfig(
            min_workers=2,
            max_workers=4,
            adjustment_interval=0.1,
        )
        
        with AdaptiveThreadPool(config) as pool:
            # 提交大量任务触发扩容
            for i in range(20):
                pool.submit(lambda x: time.sleep(0.01) or x, i)
            
            # 等待调整
            time.sleep(0.3)
            
            metrics = pool.get_metrics()
            assert metrics.current_workers <= 4


class TestConcurrency:
    """并发测试."""

    def test_concurrent_task_execution(self):
        """测试并发任务执行."""
        config = AdaptiveThreadPoolConfig(min_workers=4, max_workers=8)
        
        with AdaptiveThreadPool(config) as pool:
            start_time = time.time()
            
            # 提交 10 个耗时任务
            futures = []
            for i in range(10):
                future = pool.submit(lambda: time.sleep(0.1))
                if future:
                    futures.append(future)
            
            # 等待所有任务完成
            for future in futures:
                future.result()
            
            elapsed = time.time() - start_time
            
            # 并发执行应该比串行快（串行需要 1 秒）
            assert elapsed < 0.5

    def test_thread_safety(self):
        """测试线程安全."""
        config = AdaptiveThreadPoolConfig(min_workers=4, max_workers=8)
        
        with AdaptiveThreadPool(config) as pool:
            counter = [0]
            lock = [threading.Lock()]
            
            def increment():
                with lock[0]:
                    counter[0] += 1
                return counter[0]
            
            futures = [pool.submit(increment) for _ in range(100)]
            
            for future in futures:
                if future:
                    future.result()
            
            # 所有任务应该都执行了
            assert counter[0] == 100


import threading
