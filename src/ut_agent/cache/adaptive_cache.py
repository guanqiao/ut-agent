"""自适应缓存策略.

提供智能缓存管理，支持多种淘汰策略：
- LRU (Least Recently Used): 最近最少使用
- LFU (Least Frequently Used): 最少频繁使用
- ADAPTIVE: 自适应策略，结合访问频率和时间
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
from collections import OrderedDict
import heapq

logger = logging.getLogger(__name__)


class CacheStrategy(Enum):
    """缓存策略枚举."""
    LRU = "lru"           # 最近最少使用
    LFU = "lfu"           # 最少频繁使用
    ADAPTIVE = "adaptive" # 自适应策略


@dataclass
class CacheEntry:
    """缓存项.
    
    Attributes:
        key: 缓存键
        value: 缓存值
        ttl: 生存时间（秒）
        created_at: 创建时间
        last_access_time: 最后访问时间
        access_count: 访问次数
        priority: 优先级（用于自适应策略）
    """
    key: str
    value: Any
    ttl: int = 300
    created_at: datetime = field(default_factory=datetime.now)
    last_access_time: Optional[datetime] = None
    access_count: int = 0
    priority: float = 1.0
    
    def record_access(self) -> None:
        """记录访问."""
        self.access_count += 1
        self.last_access_time = datetime.now()
        
    def is_expired(self) -> bool:
        """检查是否过期."""
        if self.ttl <= 0:
            return True  # TTL <= 0 表示已过期
        elapsed = (datetime.now() - self.created_at).total_seconds()
        return elapsed > self.ttl
        
    def calculate_score(self) -> float:
        """计算缓存项分数（用于淘汰决策）.
        
        分数越高，越不应该被淘汰。
        
        Returns:
            float: 分数
        """
        # 基于访问频率和最近访问时间计算分数
        frequency_score = min(self.access_count / 100.0, 1.0)
        
        if self.last_access_time:
            time_since_access = (datetime.now() - self.last_access_time).total_seconds()
            recency_score = max(0, 1.0 - time_since_access / 3600)  # 1小时内衰减
        else:
            recency_score = 0.5  # 从未访问过给中等分数
            
        # 综合分数（即使没有访问记录也有基础分数）
        base_score = 0.1  # 基础分数
        score = (base_score + frequency_score * 0.6 + recency_score * 0.3) * self.priority
        return score
        
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "key": self.key,
            "value": self.value,
            "ttl": self.ttl,
            "created_at": self.created_at.isoformat(),
            "last_access_time": self.last_access_time.isoformat() if self.last_access_time else None,
            "access_count": self.access_count,
            "priority": self.priority,
        }


@dataclass
class AccessPattern:
    """访问模式分析.
    
    用于分析缓存项的访问模式，预测未来访问。
    """
    key: str
    access_times: List[datetime] = field(default_factory=list)
    access_count: int = 0
    
    def record_access(self) -> None:
        """记录访问时间."""
        self.access_count += 1
        self.access_times.append(datetime.now())
        
        # 只保留最近100次访问记录
        if len(self.access_times) > 100:
            self.access_times = self.access_times[-100:]
            
    def get_access_frequency(self) -> float:
        """获取访问频率（每秒访问次数）.
        
        Returns:
            float: 访问频率
        """
        if len(self.access_times) < 2:
            return 0.0
            
        time_span = (self.access_times[-1] - self.access_times[0]).total_seconds()
        if time_span == 0:
            return float(self.access_count)
            
        return self.access_count / time_span
        
    def is_hot_key(self, threshold: int = 10) -> bool:
        """检查是否为热键.
        
        Args:
            threshold: 热键访问次数阈值
            
        Returns:
            bool: 是否为热键
        """
        return self.access_count >= threshold
        
    def predict_next_access(self) -> Optional[datetime]:
        """预测下次访问时间.
        
        Returns:
            Optional[datetime]: 预测的下次访问时间
        """
        if len(self.access_times) < 3:
            return None
            
        # 计算平均访问间隔
        intervals = []
        for i in range(1, len(self.access_times)):
            interval = (self.access_times[i] - self.access_times[i-1]).total_seconds()
            intervals.append(interval)
            
        avg_interval = sum(intervals) / len(intervals)
        return datetime.now() + timedelta(seconds=avg_interval)


class AdaptiveCache:
    """自适应缓存.
    
    支持多种淘汰策略的智能缓存系统。
    
    Attributes:
        max_size: 最大缓存大小
        default_ttl: 默认TTL（秒）
        strategy: 缓存策略
    """
    
    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: int = 300,
        strategy: CacheStrategy = CacheStrategy.ADAPTIVE,
    ):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.strategy = strategy
        
        # 缓存存储
        self._cache: Dict[str, CacheEntry] = {}
        self._access_patterns: Dict[str, AccessPattern] = {}
        
        # LRU 专用：OrderedDict 保持访问顺序
        self._lru_order: OrderedDict[str, None] = OrderedDict()
        
        # LFU 专用：访问频率字典
        self._frequency: Dict[str, int] = {}
        
        # 统计信息
        self._hit_count = 0
        self._miss_count = 0
        self._eviction_count = 0
        
        # 锁
        self._lock = asyncio.Lock()
        
        # 后台清理任务
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False
        
        logger.info(f"AdaptiveCache initialized with strategy={strategy.value}, max_size={max_size}")
        
    async def start(self) -> None:
        """启动缓存（启动后台清理任务）."""
        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("AdaptiveCache started")
        
    async def stop(self) -> None:
        """停止缓存."""
        self._running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        logger.info("AdaptiveCache stopped")
        
    async def _cleanup_loop(self) -> None:
        """后台清理循环."""
        while self._running:
            try:
                await self._remove_expired()
                await asyncio.sleep(60)  # 每分钟清理一次
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("Cleanup loop error")
                await asyncio.sleep(60)
                
    async def _remove_expired(self) -> int:
        """移除过期缓存项.
        
        Returns:
            int: 移除的项数
        """
        expired_keys = []
        
        async with self._lock:
            for key, entry in self._cache.items():
                if entry.is_expired():
                    expired_keys.append(key)
                    
            for key in expired_keys:
                await self._remove_entry(key)
                
        if expired_keys:
            logger.debug(f"Removed {len(expired_keys)} expired entries")
            
        return len(expired_keys)
        
    async def _remove_entry(self, key: str) -> None:
        """移除缓存项."""
        if key in self._cache:
            del self._cache[key]
            
        if key in self._lru_order:
            del self._lru_order[key]
            
        if key in self._frequency:
            del self._frequency[key]
            
        if key in self._access_patterns:
            del self._access_patterns[key]
            
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存值.
        
        Args:
            key: 缓存键
            
        Returns:
            Optional[Any]: 缓存值，不存在则返回None
        """
        async with self._lock:
            entry = self._cache.get(key)
            
            if entry is None:
                self._miss_count += 1
                return None
                
            if entry.is_expired():
                await self._remove_entry(key)
                self._miss_count += 1
                return None
                
            # 更新访问信息
            entry.record_access()
            self._hit_count += 1
            
            # 更新LRU顺序
            if self.strategy == CacheStrategy.LRU:
                self._lru_order.move_to_end(key)
                
            # 更新频率
            if key in self._frequency:
                self._frequency[key] += 1
            else:
                self._frequency[key] = 1
                
            # 更新访问模式
            if key not in self._access_patterns:
                self._access_patterns[key] = AccessPattern(key=key)
            self._access_patterns[key].record_access()
            
            return entry.value
            
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        priority: float = 1.0,
    ) -> None:
        """设置缓存值.
        
        Args:
            key: 缓存键
            value: 缓存值
            ttl: 生存时间（秒），默认使用default_ttl
            priority: 优先级
        """
        ttl = ttl if ttl is not None else self.default_ttl
        
        async with self._lock:
            # 检查是否需要淘汰
            if len(self._cache) >= self.max_size and key not in self._cache:
                await self._evict_entry()
                
            # 创建或更新缓存项
            entry = CacheEntry(
                key=key,
                value=value,
                ttl=ttl,
                priority=priority,
            )
            
            self._cache[key] = entry
            
            # 更新LRU顺序
            if self.strategy == CacheStrategy.LRU:
                self._lru_order[key] = None
                self._lru_order.move_to_end(key)
                
            # 初始化频率
            if key not in self._frequency:
                self._frequency[key] = 0
                
        logger.debug(f"Cache set: {key}")
        
    async def _evict_entry(self) -> None:
        """执行缓存淘汰."""
        if not self._cache:
            return
            
        key_to_evict = None
        
        if self.strategy == CacheStrategy.LRU:
            # 淘汰最久未使用的
            key_to_evict = next(iter(self._lru_order))
            
        elif self.strategy == CacheStrategy.LFU:
            # 淘汰最少使用的
            min_freq = min(self._frequency.values())
            candidates = [k for k, v in self._frequency.items() if v == min_freq]
            key_to_evict = candidates[0] if candidates else None
            
        else:  # ADAPTIVE
            # 自适应策略：综合考虑访问频率、时间和优先级
            min_score = float('inf')
            for key, entry in self._cache.items():
                # 热键保护
                pattern = self._access_patterns.get(key)
                if pattern and pattern.is_hot_key(threshold=20):
                    continue
                    
                score = entry.calculate_score()
                if score < min_score:
                    min_score = score
                    key_to_evict = key
                    
        if key_to_evict:
            await self._remove_entry(key_to_evict)
            self._eviction_count += 1
            logger.debug(f"Evicted cache entry: {key_to_evict}")
            
    async def delete(self, key: str) -> bool:
        """删除缓存项.
        
        Args:
            key: 缓存键
            
        Returns:
            bool: 是否成功删除
        """
        async with self._lock:
            if key in self._cache:
                await self._remove_entry(key)
                logger.debug(f"Cache deleted: {key}")
                return True
            return False
            
    async def clear(self) -> None:
        """清空缓存."""
        async with self._lock:
            self._cache.clear()
            self._lru_order.clear()
            self._frequency.clear()
            self._access_patterns.clear()
            
        logger.info("Cache cleared")
        
    async def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """批量获取缓存值.
        
        Args:
            keys: 缓存键列表
            
        Returns:
            Dict[str, Any]: 存在的缓存值字典
        """
        results = {}
        for key in keys:
            value = await self.get(key)
            if value is not None:
                results[key] = value
        return results
        
    async def set_many(self, items: Dict[str, Any], ttl: Optional[int] = None) -> None:
        """批量设置缓存值.
        
        Args:
            items: 键值对字典
            ttl: 生存时间（秒）
        """
        for key, value in items.items():
            await self.set(key, value, ttl)
            
    async def delete_many(self, keys: List[str]) -> int:
        """批量删除缓存项.
        
        Args:
            keys: 缓存键列表
            
        Returns:
            int: 成功删除的数量
        """
        count = 0
        for key in keys:
            if await self.delete(key):
                count += 1
        return count
        
    @property
    def size(self) -> int:
        """获取当前缓存大小."""
        return len(self._cache)
        
    async def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息.
        
        Returns:
            Dict[str, Any]: 统计信息
        """
        total_requests = self._hit_count + self._miss_count
        hit_rate = self._hit_count / total_requests if total_requests > 0 else 0.0
        
        # 热键统计
        hot_keys = [k for k, p in self._access_patterns.items() if p.is_hot_key()]
        
        return {
            "size": self.size,
            "max_size": self.max_size,
            "strategy": self.strategy.value,
            "hit_count": self._hit_count,
            "miss_count": self._miss_count,
            "hit_rate": round(hit_rate, 4),
            "eviction_count": self._eviction_count,
            "hot_key_count": len(hot_keys),
        }
        
    async def get_access_pattern(self, key: str) -> Optional[AccessPattern]:
        """获取访问模式.
        
        Args:
            key: 缓存键
            
        Returns:
            Optional[AccessPattern]: 访问模式
        """
        return self._access_patterns.get(key)
        
    async def get_hot_keys(self, threshold: int = 10) -> List[str]:
        """获取热键列表.
        
        Args:
            threshold: 热键阈值
            
        Returns:
            List[str]: 热键列表
        """
        return [
            key for key, pattern in self._access_patterns.items()
            if pattern.is_hot_key(threshold)
        ]
