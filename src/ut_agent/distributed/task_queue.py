"""分布式任务队列."""

import json
import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Union
from pathlib import Path


class TaskStatus(Enum):
    """任务状态."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class TaskPriority(Enum):
    """任务优先级."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class Task:
    """任务模型."""
    
    id: str
    name: str
    payload: Dict[str, Any]
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    timeout: Optional[timedelta] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    worker_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典."""
        return {
            "id": self.id,
            "name": self.name,
            "payload": self.payload,
            "priority": self.priority.name.lower(),
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "timeout": self.timeout.total_seconds() if self.timeout else None,
            "result": self.result,
            "error": self.error,
            "worker_id": self.worker_id,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        """从字典反序列化."""
        return cls(
            id=data["id"],
            name=data["name"],
            payload=data["payload"],
            priority=TaskPriority[data["priority"].upper()],
            status=TaskStatus(data["status"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            retry_count=data.get("retry_count", 0),
            max_retries=data.get("max_retries", 3),
            timeout=timedelta(seconds=data["timeout"]) if data.get("timeout") else None,
            result=data.get("result"),
            error=data.get("error"),
            worker_id=data.get("worker_id"),
        )


class TaskQueue:
    """任务队列."""
    
    def __init__(self, backend: str = "memory", redis_url: Optional[str] = None, **kwargs):
        """初始化任务队列.
        
        Args:
            backend: 后端类型 (memory, redis)
            redis_url: Redis URL
            **kwargs: 其他配置
        """
        self.backend = backend
        self.redis_url = redis_url
        self._storage: Dict[str, Task] = {}
        self._pending_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._is_connected = False
        self._redis_client = None
        self._lock = asyncio.Lock()
    
    async def connect(self) -> None:
        """连接到队列后端."""
        if self.backend == "redis" and self.redis_url:
            try:
                import redis.asyncio as aioredis
                self._redis_client = aioredis.from_url(self.redis_url)
                await self._redis_client.ping()
            except ImportError:
                raise ImportError("redis package is required. Install with: pip install redis")
        
        self._is_connected = True
    
    async def disconnect(self) -> None:
        """断开队列后端连接."""
        if self._redis_client:
            await self._redis_client.close()
            self._redis_client = None
        
        self._is_connected = False
    
    @property
    def is_connected(self) -> bool:
        """是否已连接."""
        return self._is_connected
    
    async def submit(self, task: Task) -> str:
        """提交任务.
        
        Args:
            task: 任务对象
            
        Returns:
            str: 任务 ID
        """
        async with self._lock:
            if not task.id:
                task.id = str(uuid.uuid4())
            
            task.status = TaskStatus.PENDING
            task.created_at = datetime.now()
            
            if self.backend == "redis" and self._redis_client:
                await self._redis_client.hset(
                    f"task:{task.id}",
                    mapping={k: json.dumps(v) if isinstance(v, (dict, list)) else str(v) 
                            for k, v in task.to_dict().items()}
                )
                await self._redis_client.zadd(
                    "queue:pending",
                    {task.id: -task.priority.value}
                )
            else:
                self._storage[task.id] = task
                await self._pending_queue.put((-task.priority.value, task.created_at.timestamp(), task.id))
            
            return task.id
    
    async def consume(self, timeout: Optional[float] = None) -> Optional[Task]:
        """消费任务.
        
        Args:
            timeout: 超时时间（秒）
            
        Returns:
            Optional[Task]: 任务对象，如果超时返回 None
        """
        async with self._lock:
            if self.backend == "redis" and self._redis_client:
                # 从 Redis 获取优先级最高的任务
                result = await self._redis_client.zpopmax("queue:pending")
                if not result:
                    return None
                
                task_id = result[0][0]
                task_data = await self._redis_client.hgetall(f"task:{task_id}")
                
                if not task_data:
                    return None
                
                task = Task.from_dict({k: json.loads(v) if v.startswith("{") else v 
                                      for k, v in task_data.items()})
            else:
                # 从内存队列获取
                try:
                    priority, created_at, task_id = await asyncio.wait_for(
                        self._pending_queue.get(), timeout=timeout
                    )
                    task = self._storage.get(task_id)
                    if not task:
                        return None
                except asyncio.TimeoutError:
                    return None
            
            # 更新任务状态
            task.status = TaskStatus.PROCESSING
            task.started_at = datetime.now()
            
            if self.backend == "redis" and self._redis_client:
                await self._redis_client.hset(f"task:{task.id}", "status", task.status.value)
                await self._redis_client.hset(f"task:{task.id}", "started_at", task.started_at.isoformat())
                await self._redis_client.sadd("queue:processing", task.id)
            
            return task
    
    async def complete(self, task_id: str, result: Any) -> None:
        """完成任务.
        
        Args:
            task_id: 任务 ID
            result: 任务结果
        """
        async with self._lock:
            task = await self._get_task_internal(task_id)
            if not task:
                return
            
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            task.result = result
            
            if self.backend == "redis" and self._redis_client:
                await self._redis_client.hset(f"task:{task_id}", "status", task.status.value)
                await self._redis_client.hset(f"task:{task_id}", "completed_at", task.completed_at.isoformat())
                await self._redis_client.hset(f"task:{task_id}", "result", json.dumps(result))
                await self._redis_client.srem("queue:processing", task_id)
                await self._redis_client.zadd("queue:completed", {task_id: datetime.now().timestamp()})
            else:
                self._storage[task_id] = task
    
    async def fail(self, task_id: str, error: str, retry: bool = False) -> None:
        """标记任务失败.
        
        Args:
            task_id: 任务 ID
            error: 错误信息
            retry: 是否重试
        """
        async with self._lock:
            task = await self._get_task_internal(task_id)
            if not task:
                return
            
            task.error = error
            task.retry_count += 1
            
            if retry and task.retry_count < task.max_retries:
                # 重新放入队列
                task.status = TaskStatus.PENDING
                task.started_at = None
                
                if self.backend == "redis" and self._redis_client:
                    await self._redis_client.hset(f"task:{task_id}", "status", task.status.value)
                    await self._redis_client.hset(f"task:{task_id}", "retry_count", str(task.retry_count))
                    await self._redis_client.hset(f"task:{task_id}", "error", error)
                    await self._redis_client.srem("queue:processing", task_id)
                    await self._redis_client.zadd("queue:pending", {task_id: -task.priority.value})
                else:
                    await self._pending_queue.put((-task.priority.value, datetime.now().timestamp(), task_id))
            else:
                # 标记为失败
                task.status = TaskStatus.FAILED
                task.completed_at = datetime.now()
                
                if self.backend == "redis" and self._redis_client:
                    await self._redis_client.hset(f"task:{task_id}", "status", task.status.value)
                    await self._redis_client.hset(f"task:{task_id}", "completed_at", task.completed_at.isoformat())
                    await self._redis_client.hset(f"task:{task_id}", "error", error)
                    await self._redis_client.srem("queue:processing", task_id)
                    await self._redis_client.zadd("queue:failed", {task_id: datetime.now().timestamp()})
            
            if self.backend == "memory":
                self._storage[task_id] = task
    
    async def cancel(self, task_id: str) -> None:
        """取消任务.
        
        Args:
            task_id: 任务 ID
        """
        async with self._lock:
            task = await self._get_task_internal(task_id)
            if not task or task.status not in [TaskStatus.PENDING, TaskStatus.PROCESSING]:
                return
            
            task.status = TaskStatus.CANCELLED
            task.completed_at = datetime.now()
            
            if self.backend == "redis" and self._redis_client:
                await self._redis_client.hset(f"task:{task_id}", "status", task.status.value)
                await self._redis_client.hset(f"task:{task_id}", "completed_at", task.completed_at.isoformat())
                await self._redis_client.zrem("queue:pending", task_id)
                await self._redis_client.srem("queue:processing", task_id)
            else:
                self._storage[task_id] = task
    
    async def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务.
        
        Args:
            task_id: 任务 ID
            
        Returns:
            Optional[Task]: 任务对象
        """
        return await self._get_task_internal(task_id)
    
    async def _get_task_internal(self, task_id: str) -> Optional[Task]:
        """内部获取任务方法."""
        if self.backend == "redis" and self._redis_client:
            task_data = await self._redis_client.hgetall(f"task:{task_id}")
            if not task_data:
                return None
            
            # 解析数据
            parsed_data = {}
            for k, v in task_data.items():
                try:
                    parsed_data[k] = json.loads(v)
                except (json.JSONDecodeError, TypeError):
                    parsed_data[k] = v.decode() if isinstance(v, bytes) else v
            
            return Task.from_dict(parsed_data)
        else:
            return self._storage.get(task_id)
    
    async def get_status(self, task_id: str) -> Optional[TaskStatus]:
        """获取任务状态.
        
        Args:
            task_id: 任务 ID
            
        Returns:
            Optional[TaskStatus]: 任务状态
        """
        task = await self.get_task(task_id)
        return task.status if task else None
    
    async def list_pending_tasks(self) -> List[Task]:
        """列出待处理任务（按优先级排序）."""
        if self.backend == "redis" and self._redis_client:
            task_ids = await self._redis_client.zrange("queue:pending", 0, -1)
            tasks = []
            for task_id in task_ids:
                task = await self.get_task(task_id.decode() if isinstance(task_id, bytes) else task_id)
                if task:
                    tasks.append(task)
            return tasks
        else:
            # 从内存获取所有 PENDING 状态的任务并排序
            pending = [t for t in self._storage.values() if t.status == TaskStatus.PENDING]
            return sorted(pending, key=lambda t: (-t.priority.value, t.created_at))
    
    async def list_tasks(self, status: Optional[TaskStatus] = None) -> List[Task]:
        """列出任务.
        
        Args:
            status: 任务状态过滤器
            
        Returns:
            List[Task]: 任务列表
        """
        if self.backend == "redis" and self._redis_client:
            # 从 Redis 获取
            pattern = "task:*"
            keys = await self._redis_client.keys(pattern)
            tasks = []
            for key in keys:
                task_data = await self._redis_client.hgetall(key)
                if task_data:
                    parsed_data = {k: json.loads(v) if v.startswith("{") else v 
                                  for k, v in task_data.items()}
                    task = Task.from_dict(parsed_data)
                    if status is None or task.status == status:
                        tasks.append(task)
            return tasks
        else:
            # 从内存获取
            if status:
                return [t for t in self._storage.values() if t.status == status]
            return list(self._storage.values())
    
    async def check_timeouts(self) -> List[str]:
        """检查超时任务.
        
        Returns:
            List[str]: 超时任务 ID 列表
        """
        timeout_tasks = []
        now = datetime.now()
        
        processing_tasks = await self.list_tasks(status=TaskStatus.PROCESSING)
        
        for task in processing_tasks:
            if task.timeout and task.started_at:
                elapsed = now - task.started_at
                if elapsed > task.timeout:
                    # 任务超时
                    await self.fail(task.id, "Task timeout", retry=True)
                    timeout_tasks.append(task.id)
        
        return timeout_tasks
    
    async def get_stats(self) -> Dict[str, int]:
        """获取队列统计信息.
        
        Returns:
            Dict[str, int]: 统计信息
        """
        all_tasks = await self.list_tasks()
        
        stats = {
            "total": len(all_tasks),
            "pending": 0,
            "processing": 0,
            "completed": 0,
            "failed": 0,
            "cancelled": 0,
        }
        
        for task in all_tasks:
            if task.status.value in stats:
                stats[task.status.value] += 1
        
        return stats
    
    async def clear_completed(self, age: Optional[timedelta] = None) -> int:
        """清理已完成任务.
        
        Args:
            age: 清理超过该时间的任务
            
        Returns:
            int: 清理的任务数量
        """
        async with self._lock:
            completed_tasks = await self.list_tasks(status=TaskStatus.COMPLETED)
            cleared = 0
            now = datetime.now()
            
            for task in completed_tasks:
                if age and task.completed_at:
                    if now - task.completed_at < age:
                        continue
                
                if self.backend == "redis" and self._redis_client:
                    await self._redis_client.delete(f"task:{task.id}")
                    await self._redis_client.zrem("queue:completed", task.id)
                else:
                    self._storage.pop(task.id, None)
                
                cleared += 1
            
            return cleared
