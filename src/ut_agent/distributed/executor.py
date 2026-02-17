"""分布式执行器."""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set
import logging

from ut_agent.distributed.task_queue import TaskQueue, Task, TaskStatus

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """执行结果."""
    
    task_id: str
    success: bool
    output: Optional[str] = None
    error: Optional[str] = None
    execution_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典."""
        return {
            "task_id": self.task_id,
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "execution_time": self.execution_time,
            "metadata": self.metadata,
        }


class Worker:
    """工作节点."""
    
    def __init__(self, worker_id: str, max_concurrent: int = 5):
        """初始化工作节点.
        
        Args:
            worker_id: 工作节点 ID
            max_concurrent: 最大并发数
        """
        self.worker_id = worker_id
        self.max_concurrent = max_concurrent
        self._handlers: Dict[str, Callable[[Task], Any]] = {}
        self._is_running = False
        self._current_load = 0
        self._lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(max_concurrent)
    
    @property
    def is_running(self) -> bool:
        """是否正在运行."""
        return self._is_running
    
    @property
    def current_load(self) -> int:
        """当前负载."""
        return self._current_load
    
    async def start(self) -> None:
        """启动工作节点."""
        self._is_running = True
        logger.info(f"Worker {self.worker_id} started")
    
    async def stop(self) -> None:
        """停止工作节点."""
        self._is_running = False
        logger.info(f"Worker {self.worker_id} stopped")
    
    def register_handler(self, task_type: str, handler: Callable[[Task], Any]) -> None:
        """注册任务处理器.
        
        Args:
            task_type: 任务类型
            handler: 处理函数
        """
        self._handlers[task_type] = handler
        logger.debug(f"Worker {self.worker_id} registered handler for {task_type}")
    
    async def execute(self, task: Task) -> ExecutionResult:
        """执行任务.
        
        Args:
            task: 任务对象
            
        Returns:
            ExecutionResult: 执行结果
        """
        if not self._is_running:
            return ExecutionResult(
                task_id=task.id,
                success=False,
                error="Worker is not running"
            )
        
        handler = self._handlers.get(task.name)
        if not handler:
            return ExecutionResult(
                task_id=task.id,
                success=False,
                error=f"No handler registered for task type: {task.name}"
            )
        
        async with self._semaphore:
            async with self._lock:
                self._current_load += 1
            
            start_time = asyncio.get_event_loop().time()
            
            try:
                result = await handler(task)
                
                if isinstance(result, ExecutionResult):
                    return result
                else:
                    return ExecutionResult(
                        task_id=task.id,
                        success=True,
                        output=str(result),
                        execution_time=asyncio.get_event_loop().time() - start_time
                    )
            except Exception as e:
                logger.exception(f"Task {task.id} execution failed")
                return ExecutionResult(
                    task_id=task.id,
                    success=False,
                    error=str(e),
                    execution_time=asyncio.get_event_loop().time() - start_time
                )
            finally:
                async with self._lock:
                    self._current_load -= 1
    
    def health_check(self) -> Dict[str, Any]:
        """健康检查.
        
        Returns:
            Dict[str, Any]: 健康状态
        """
        return {
            "worker_id": self.worker_id,
            "is_running": self._is_running,
            "current_load": self._current_load,
            "max_concurrent": self.max_concurrent,
            "available_slots": self.max_concurrent - self._current_load,
            "registered_handlers": list(self._handlers.keys()),
        }


class DistributedExecutor:
    """分布式执行器."""
    
    def __init__(self, queue: TaskQueue, max_workers: int = 4, poll_interval: float = 1.0):
        """初始化分布式执行器.
        
        Args:
            queue: 任务队列
            max_workers: 最大工作节点数
            poll_interval: 轮询间隔（秒）
        """
        self.queue = queue
        self.max_workers = max_workers
        self.poll_interval = poll_interval
        self.workers: List[Worker] = []
        self._is_running = False
        self._worker_tasks: Set[asyncio.Task] = set()
        self._monitor_task: Optional[asyncio.Task] = None
    
    async def start(self) -> None:
        """启动执行器."""
        if self._is_running:
            return
        
        self._is_running = True
        
        # 创建工作节点
        for i in range(self.max_workers):
            worker = Worker(worker_id=f"worker-{i+1}")
            await worker.start()
            self.workers.append(worker)
            
            # 启动工作循环
            task = asyncio.create_task(self._worker_loop(worker))
            self._worker_tasks.add(task)
            task.add_done_callback(self._worker_tasks.discard)
        
        # 启动监控任务
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        
        logger.info(f"DistributedExecutor started with {self.max_workers} workers")
    
    async def stop(self, graceful: bool = True, timeout: float = 30.0) -> None:
        """停止执行器.
        
        Args:
            graceful: 是否优雅关闭
            timeout: 超时时间
        """
        if not self._is_running:
            return
        
        self._is_running = False
        
        # 取消监控任务
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        if graceful:
            # 等待工作节点完成任务
            await asyncio.gather(*self._worker_tasks, return_exceptions=True)
        else:
            # 立即取消所有任务
            for task in self._worker_tasks:
                task.cancel()
            await asyncio.gather(*self._worker_tasks, return_exceptions=True)
        
        # 停止所有工作节点
        for worker in self.workers:
            await worker.stop()
        
        self.workers.clear()
        self._worker_tasks.clear()
        
        logger.info("DistributedExecutor stopped")
    
    async def submit(
        self,
        name: str,
        payload: Dict[str, Any],
        task_type: Optional[str] = None,
        priority: int = 2,
        max_retries: int = 3,
        timeout: Optional[float] = None,
    ) -> str:
        """提交任务.
        
        Args:
            name: 任务名称
            payload: 任务数据
            task_type: 任务类型
            priority: 优先级
            max_retries: 最大重试次数
            timeout: 超时时间
            
        Returns:
            str: 任务 ID
        """
        from ut_agent.distributed.task_queue import TaskPriority
        
        task = Task(
            id=str(uuid.uuid4()),
            name=task_type or name,
            payload=payload,
            priority=TaskPriority(priority),
            max_retries=max_retries,
        )
        
        if timeout:
            from datetime import timedelta
            task.timeout = timedelta(seconds=timeout)
        
        task_id = await self.queue.submit(task)
        logger.debug(f"Task {task_id} submitted")
        return task_id
    
    async def _worker_loop(self, worker: Worker) -> None:
        """工作节点循环.
        
        Args:
            worker: 工作节点
        """
        while self._is_running:
            try:
                # 从队列获取任务
                task = await self.queue.consume(timeout=self.poll_interval)
                
                if task is None:
                    continue
                
                # 执行任务
                result = await worker.execute(task)
                
                # 更新任务状态
                if result.success:
                    await self.queue.complete(
                        task.id,
                        result={
                            "output": result.output,
                            "execution_time": result.execution_time,
                            "metadata": result.metadata,
                        }
                    )
                else:
                    await self.queue.fail(
                        task.id,
                        error=result.error or "Unknown error",
                        retry=task.retry_count < task.max_retries
                    )
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(f"Worker {worker.worker_id} error")
                await asyncio.sleep(1)
    
    async def _monitor_loop(self) -> None:
        """监控循环."""
        while self._is_running:
            try:
                await self.check_workers()
                await self.queue.check_timeouts()
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("Monitor loop error")
                await asyncio.sleep(5)
    
    async def check_workers(self) -> None:
        """检查工作节点健康状态."""
        # 检查是否有工作节点故障
        failed_workers = [w for w in self.workers if not w.is_running]
        
        for worker in failed_workers:
            logger.warning(f"Worker {worker.worker_id} is not running, replacing...")
            self.workers.remove(worker)
            
            # 创建新工作节点
            new_worker = Worker(worker_id=worker.worker_id)
            await new_worker.start()
            self.workers.append(new_worker)
            
            # 启动新工作循环
            task = asyncio.create_task(self._worker_loop(new_worker))
            self._worker_tasks.add(task)
            task.add_done_callback(self._worker_tasks.discard)
        
        # 确保工作节点数量
        while len(self.workers) < self.max_workers:
            worker_id = f"worker-{len(self.workers) + 1}"
            worker = Worker(worker_id=worker_id)
            await worker.start()
            self.workers.append(worker)
            
            task = asyncio.create_task(self._worker_loop(worker))
            self._worker_tasks.add(task)
            task.add_done_callback(self._worker_tasks.discard)
    
    async def get_stats(self) -> Dict[str, Any]:
        """获取统计信息.
        
        Returns:
            Dict[str, Any]: 统计信息
        """
        queue_stats = await self.queue.get_stats()
        
        worker_stats = []
        for worker in self.workers:
            worker_stats.append(worker.health_check())
        
        return {
            "total_workers": len(self.workers),
            "active_workers": sum(1 for w in self.workers if w.is_running),
            "total_load": sum(w.current_load for w in self.workers),
            "workers": worker_stats,
            "total_tasks": queue_stats.get("total", 0),
            "completed_tasks": queue_stats.get("completed", 0),
            **queue_stats,
        }
