"""自适应线程池.

根据系统负载动态调整线程池大小，优化并发性能。
"""

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, TypeVar, Generic
from queue import Queue
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class ThreadPoolMetrics:
    """线程池指标."""
    current_workers: int = 0
    min_workers: int = 0
    max_workers: int = 0
    queue_size: int = 0
    active_tasks: int = 0
    completed_tasks: int = 0
    rejected_tasks: int = 0
    avg_task_duration: float = 0.0
    cpu_usage: float = 0.0
    adjustment_count: int = 0
    last_adjustment_time: Optional[float] = None


@dataclass
class AdaptiveThreadPoolConfig:
    """自适应线程池配置."""
    min_workers: int = 2
    max_workers: int = 32
    adjustment_interval: float = 5.0  # 调整间隔（秒）
    cpu_threshold_high: float = 80.0  # CPU 高阈值
    cpu_threshold_low: float = 50.0   # CPU 低阈值
    queue_threshold_high: int = 10    # 队列高阈值
    queue_threshold_low: int = 2      # 队列低阈值
    scale_up_factor: float = 1.5      # 扩容因子
    scale_down_factor: float = 0.8    # 缩容因子
    enable_backpressure: bool = True  # 启用背压
    max_queue_size: int = 100         # 最大队列大小


class CPUMonitor:
    """CPU 监控器."""
    
    def __init__(self):
        self._last_cpu_times = None
        self._last_check_time = 0
        self._lock = threading.Lock()
    
    def get_cpu_usage(self) -> float:
        """获取 CPU 使用率.
        
        Returns:
            float: CPU 使用率（0-100）
        """
        try:
            import psutil
            return psutil.cpu_percent(interval=0.1)
        except ImportError:
            # 如果没有 psutil，使用简单估算
            return self._estimate_cpu_usage()
    
    def _estimate_cpu_usage(self) -> float:
        """估算 CPU 使用率（简化版）."""
        # 基于活跃线程数估算
        active_threads = threading.active_count()
        cpu_count = os.cpu_count() or 4
        
        # 简单估算：每个 CPU 核心 4 个线程为 100%
        estimated = min(100.0, (active_threads / (cpu_count * 4)) * 100)
        return estimated


class AdaptiveThreadPool(Generic[T]):
    """自适应线程池.
    
    根据系统负载动态调整线程池大小。
    """
    
    def __init__(self, config: Optional[AdaptiveThreadPoolConfig] = None):
        """初始化自适应线程池.
        
        Args:
            config: 配置
        """
        self.config = config or AdaptiveThreadPoolConfig()
        self.metrics = ThreadPoolMetrics(
            current_workers=self.config.min_workers,
            min_workers=self.config.min_workers,
            max_workers=self.config.max_workers,
        )
        
        self._executor: Optional[ThreadPoolExecutor] = None
        self._task_queue: Queue = Queue(maxsize=self.config.max_queue_size)
        self._cpu_monitor = CPUMonitor()
        self._shutdown = False
        self._lock = threading.RLock()
        self._task_durations: List[float] = []
        
        # 初始化线程池
        self._create_executor(self.config.min_workers)
        
        # 启动调整线程
        self._adjustment_thread = threading.Thread(
            target=self._adjustment_loop,
            daemon=True,
        )
        self._adjustment_thread.start()
        
        logger.info(
            f"AdaptiveThreadPool initialized: "
            f"min={self.config.min_workers}, max={self.config.max_workers}"
        )
    
    def _create_executor(self, num_workers: int) -> None:
        """创建线程池执行器.
        
        Args:
            num_workers: 工作线程数
        """
        with self._lock:
            if self._executor is not None:
                self._executor.shutdown(wait=False)
            
            self._executor = ThreadPoolExecutor(
                max_workers=num_workers,
                thread_name_prefix="adaptive_pool_",
            )
            self.metrics.current_workers = num_workers
            logger.debug(f"ThreadPool resized to {num_workers}")
    
    def _adjustment_loop(self) -> None:
        """调整循环."""
        while not self._shutdown:
            try:
                time.sleep(self.config.adjustment_interval)
                
                if not self._shutdown:
                    self._adjust_pool_size()
                    
            except Exception as e:
                logger.error(f"Adjustment loop error: {e}")
    
    def _adjust_pool_size(self) -> None:
        """调整线程池大小."""
        with self._lock:
            current = self.metrics.current_workers
            cpu_usage = self._cpu_monitor.get_cpu_usage()
            queue_size = self._task_queue.qsize()
            
            self.metrics.cpu_usage = cpu_usage
            self.metrics.queue_size = queue_size
            
            new_size = current
            
            # 扩容条件
            if cpu_usage < self.config.cpu_threshold_high and queue_size > self.config.queue_threshold_high:
                if current < self.config.max_workers:
                    new_size = min(
                        int(current * self.config.scale_up_factor),
                        self.config.max_workers
                    )
                    logger.info(
                        f"Scaling up: {current} -> {new_size} "
                        f"(cpu={cpu_usage:.1f}%, queue={queue_size})"
                    )
            
            # 缩容条件
            elif cpu_usage > self.config.cpu_threshold_high or queue_size < self.config.queue_threshold_low:
                if current > self.config.min_workers:
                    new_size = max(
                        int(current * self.config.scale_down_factor),
                        self.config.min_workers
                    )
                    logger.info(
                        f"Scaling down: {current} -> {new_size} "
                        f"(cpu={cpu_usage:.1f}%, queue={queue_size})"
                    )
            
            # 应用调整
            if new_size != current:
                self._create_executor(new_size)
                self.metrics.adjustment_count += 1
                self.metrics.last_adjustment_time = time.time()
    
    def submit(self, fn: Callable[..., T], *args, **kwargs) -> Optional[Any]:
        """提交任务.
        
        Args:
            fn: 函数
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            Optional[Future]: Future 对象，如果背压则返回 None
        """
        if self._shutdown:
            raise RuntimeError("ThreadPool is shutdown")
        
        # 背压检查
        if self.config.enable_backpressure:
            if self._task_queue.full():
                self.metrics.rejected_tasks += 1
                logger.warning("Task rejected due to backpressure")
                return None
        
        with self._lock:
            if self._executor is None:
                raise RuntimeError("ThreadPool is not initialized")
            
            future = self._executor.submit(self._wrap_task(fn), *args, **kwargs)
            self.metrics.active_tasks += 1
            
            return future
    
    def _wrap_task(self, fn: Callable[..., T]) -> Callable[..., T]:
        """包装任务函数.
        
        Args:
            fn: 原始函数
            
        Returns:
            Callable: 包装后的函数
        """
        def wrapper(*args, **kwargs) -> T:
            start_time = time.time()
            try:
                return fn(*args, **kwargs)
            finally:
                duration = time.time() - start_time
                self._record_task_duration(duration)
                self.metrics.active_tasks -= 1
                self.metrics.completed_tasks += 1
        
        return wrapper
    
    def _record_task_duration(self, duration: float) -> None:
        """记录任务执行时间.
        
        Args:
            duration: 执行时间（秒）
        """
        self._task_durations.append(duration)
        
        # 只保留最近 100 个记录
        if len(self._task_durations) > 100:
            self._task_durations = self._task_durations[-100:]
        
        # 更新平均执行时间
        if self._task_durations:
            self.metrics.avg_task_duration = sum(self._task_durations) / len(self._task_durations)
    
    def map(
        self,
        fn: Callable[[Any], T],
        iterable: List[Any],
        timeout: Optional[float] = None,
    ) -> List[T]:
        """映射执行.
        
        Args:
            fn: 函数
            iterable: 可迭代对象
            timeout: 超时时间
            
        Returns:
            List[T]: 结果列表
        """
        if self._shutdown:
            raise RuntimeError("ThreadPool is shutdown")
        
        with self._lock:
            if self._executor is None:
                raise RuntimeError("ThreadPool is not initialized")
            
            results = list(self._executor.map(fn, iterable, timeout=timeout))
            self.metrics.completed_tasks += len(results)
            
            return results
    
    def shutdown(self, wait: bool = True) -> None:
        """关闭线程池.
        
        Args:
            wait: 是否等待所有任务完成
        """
        self._shutdown = True
        
        with self._lock:
            if self._executor is not None:
                self._executor.shutdown(wait=wait)
                self._executor = None
        
        logger.info("AdaptiveThreadPool shutdown")
    
    def get_metrics(self) -> ThreadPoolMetrics:
        """获取指标.
        
        Returns:
            ThreadPoolMetrics: 线程池指标
        """
        with self._lock:
            return ThreadPoolMetrics(
                current_workers=self.metrics.current_workers,
                min_workers=self.metrics.min_workers,
                max_workers=self.metrics.max_workers,
                queue_size=self._task_queue.qsize(),
                active_tasks=self.metrics.active_tasks,
                completed_tasks=self.metrics.completed_tasks,
                rejected_tasks=self.metrics.rejected_tasks,
                avg_task_duration=self.metrics.avg_task_duration,
                cpu_usage=self.metrics.cpu_usage,
                adjustment_count=self.metrics.adjustment_count,
                last_adjustment_time=self.metrics.last_adjustment_time,
            )
    
    def __enter__(self):
        """上下文管理器入口."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口."""
        self.shutdown(wait=True)


class TaskScheduler:
    """任务调度器.
    
    基于自适应线程池的任务调度。
    """
    
    def __init__(self, pool: Optional[AdaptiveThreadPool] = None):
        """初始化任务调度器.
        
        Args:
            pool: 线程池
        """
        self.pool = pool or AdaptiveThreadPool()
        self._futures: List[Any] = []
    
    def schedule(self, fn: Callable[..., T], *args, **kwargs) -> Optional[Any]:
        """调度任务.
        
        Args:
            fn: 函数
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            Optional[Future]: Future 对象
        """
        future = self.pool.submit(fn, *args, **kwargs)
        if future:
            self._futures.append(future)
        return future
    
    def wait_all(self, timeout: Optional[float] = None) -> List[T]:
        """等待所有任务完成.
        
        Args:
            timeout: 超时时间
            
        Returns:
            List[T]: 结果列表
        """
        results = []
        
        for future in as_completed(self._futures, timeout=timeout):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                logger.error(f"Task failed: {e}")
                results.append(e)
        
        self._futures.clear()
        return results
    
    def get_pool_metrics(self) -> ThreadPoolMetrics:
        """获取线程池指标.
        
        Returns:
            ThreadPoolMetrics: 指标
        """
        return self.pool.get_metrics()


def get_optimal_thread_count() -> int:
    """获取最优线程数.
    
    Returns:
        int: 最优线程数
    """
    cpu_count = os.cpu_count() or 4
    
    # IO 密集型任务：线程数 = CPU 核心数 * 2
    # CPU 密集型任务：线程数 = CPU 核心数 + 1
    # 混合任务：线程数 = CPU 核心数 * 1.5
    
    return int(cpu_count * 1.5)


# 全局线程池实例
_global_pool: Optional[AdaptiveThreadPool] = None
_global_pool_lock = threading.Lock()


def get_global_thread_pool() -> AdaptiveThreadPool:
    """获取全局线程池.
    
    Returns:
        AdaptiveThreadPool: 全局线程池
    """
    global _global_pool
    
    with _global_pool_lock:
        if _global_pool is None:
            config = AdaptiveThreadPoolConfig(
                min_workers=2,
                max_workers=get_optimal_thread_count(),
            )
            _global_pool = AdaptiveThreadPool(config)
        
        return _global_pool


def shutdown_global_thread_pool(wait: bool = True) -> None:
    """关闭全局线程池.
    
    Args:
        wait: 是否等待所有任务完成
    """
    global _global_pool
    
    with _global_pool_lock:
        if _global_pool is not None:
            _global_pool.shutdown(wait=wait)
            _global_pool = None
