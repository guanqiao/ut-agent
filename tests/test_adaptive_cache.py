"""自适应缓存策略测试."""

import pytest
import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from ut_agent.cache.adaptive_cache import (
    CacheEntry,
    AccessPattern,
    AdaptiveCache,
    CacheStrategy,
)


class TestCacheEntry:
    """缓存项测试."""

    def test_entry_creation(self):
        """测试缓存项创建."""
        entry = CacheEntry(
            key="test_key",
            value="test_value",
            ttl=300,
        )
        
        assert entry.key == "test_key"
        assert entry.value == "test_value"
        assert entry.ttl == 300
        assert entry.access_count == 0
        assert entry.priority == 1.0
        
    def test_entry_access(self):
        """测试缓存项访问."""
        entry = CacheEntry(
            key="test_key",
            value="test_value",
            ttl=300,
        )
        
        # 第一次访问
        entry.record_access()
        assert entry.access_count == 1
        assert entry.last_access_time is not None
        
        # 多次访问
        for _ in range(5):
            entry.record_access()
        assert entry.access_count == 6
        
    def test_entry_score_calculation(self):
        """测试缓存项分数计算."""
        entry = CacheEntry(
            key="test_key",
            value="test_value",
            ttl=300,
        )
        
        # 初始分数
        initial_score = entry.calculate_score()
        assert initial_score > 0
        
        # 访问后分数应提高
        entry.record_access()
        entry.record_access()
        entry.record_access()
        
        accessed_score = entry.calculate_score()
        assert accessed_score > initial_score
        
    def test_entry_is_expired(self):
        """测试缓存项过期检查."""
        # 未过期项
        entry = CacheEntry(
            key="test_key",
            value="test_value",
            ttl=300,
        )
        assert not entry.is_expired()
        
        # 已过期项
        expired_entry = CacheEntry(
            key="expired_key",
            value="expired_value",
            ttl=-1,  # 已过期
        )
        assert expired_entry.is_expired()
        
    def test_entry_to_dict(self):
        """测试缓存项序列化."""
        entry = CacheEntry(
            key="test_key",
            value={"data": "test"},
            ttl=300,
        )
        entry.record_access()
        
        data = entry.to_dict()
        
        assert data["key"] == "test_key"
        assert data["value"] == {"data": "test"}
        assert data["access_count"] == 1
        assert "created_at" in data
        assert "last_access_time" in data


class TestAccessPattern:
    """访问模式测试."""

    def test_pattern_creation(self):
        """测试访问模式创建."""
        pattern = AccessPattern(key="test_key")
        
        assert pattern.key == "test_key"
        assert pattern.access_times == []
        assert pattern.access_count == 0
        
    def test_record_access(self):
        """测试记录访问."""
        pattern = AccessPattern(key="test_key")
        
        # 记录多次访问
        for _ in range(5):
            pattern.record_access()
            
        assert pattern.access_count == 5
        assert len(pattern.access_times) == 5
        
    def test_get_access_frequency(self):
        """测试获取访问频率."""
        pattern = AccessPattern(key="test_key")
        
        # 无访问记录
        assert pattern.get_access_frequency() == 0.0
        
        # 记录访问
        for _ in range(10):
            pattern.record_access()
            
        frequency = pattern.get_access_frequency()
        assert frequency > 0
        
    def test_is_hot_key(self):
        """测试热键检测."""
        pattern = AccessPattern(key="test_key")
        
        # 非热键
        assert not pattern.is_hot_key(threshold=5)
        
        # 成为热键
        for _ in range(10):
            pattern.record_access()
            
        assert pattern.is_hot_key(threshold=5)
        
    def test_predict_next_access(self):
        """测试预测下次访问时间."""
        pattern = AccessPattern(key="test_key")
        
        # 无足够数据
        prediction = pattern.predict_next_access()
        assert prediction is None
        
        # 记录规律访问
        now = datetime.now()
        for i in range(5):
            pattern.access_times.append(now - timedelta(seconds=(5-i) * 10))
        pattern.access_count = 5
        
        prediction = pattern.predict_next_access()
        assert prediction is not None


class TestAdaptiveCache:
    """自适应缓存测试."""

    @pytest.fixture
    async def cache(self):
        """创建缓存实例."""
        cache = AdaptiveCache(
            max_size=100,
            default_ttl=300,
            strategy=CacheStrategy.LRU,
        )
        await cache.start()
        yield cache
        await cache.stop()
        
    @pytest.mark.asyncio
    async def test_cache_initialization(self):
        """测试缓存初始化."""
        cache = AdaptiveCache(
            max_size=100,
            default_ttl=300,
        )
        
        assert cache.max_size == 100
        assert cache.default_ttl == 300
        assert cache.strategy == CacheStrategy.ADAPTIVE
        assert cache.size == 0
        
    @pytest.mark.asyncio
    async def test_set_and_get(self, cache):
        """测试设置和获取缓存."""
        # 设置缓存
        await cache.set("key1", "value1")
        
        # 获取缓存
        value = await cache.get("key1")
        assert value == "value1"
        
    @pytest.mark.asyncio
    async def test_get_nonexistent(self, cache):
        """测试获取不存在的缓存."""
        value = await cache.get("nonexistent")
        assert value is None
        
    @pytest.mark.asyncio
    async def test_delete(self, cache):
        """测试删除缓存."""
        await cache.set("key1", "value1")
        
        # 删除
        result = await cache.delete("key1")
        assert result is True
        
        # 确认已删除
        value = await cache.get("key1")
        assert value is None
        
    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, cache):
        """测试删除不存在的缓存."""
        result = await cache.delete("nonexistent")
        assert result is False
        
    @pytest.mark.asyncio
    async def test_clear(self, cache):
        """测试清空缓存."""
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        
        await cache.clear()
        
        assert cache.size == 0
        assert await cache.get("key1") is None
        assert await cache.get("key2") is None
        
    @pytest.mark.asyncio
    async def test_expired_entry(self, cache):
        """测试过期缓存项."""
        # 设置短TTL的缓存
        await cache.set("key1", "value1", ttl=0.1)
        
        # 立即获取应成功
        value = await cache.get("key1")
        assert value == "value1"
        
        # 等待过期
        await asyncio.sleep(0.2)
        
        # 过期后获取应失败
        value = await cache.get("key1")
        assert value is None
        
    @pytest.mark.asyncio
    async def test_lru_eviction(self):
        """测试LRU淘汰策略."""
        cache = AdaptiveCache(
            max_size=3,
            strategy=CacheStrategy.LRU,
        )
        await cache.start()
        
        # 填满缓存
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.set("key3", "value3")
        
        # 访问key1，使其成为最近使用
        await cache.get("key1")
        
        # 添加新项，应淘汰key2（最久未使用）
        await cache.set("key4", "value4")
        
        assert await cache.get("key1") is not None
        assert await cache.get("key2") is None  # 被淘汰
        assert await cache.get("key3") is not None
        assert await cache.get("key4") is not None
        
        await cache.stop()
        
    @pytest.mark.asyncio
    async def test_lfu_eviction(self):
        """测试LFU淘汰策略."""
        cache = AdaptiveCache(
            max_size=3,
            strategy=CacheStrategy.LFU,
        )
        await cache.start()
        
        # 填满缓存
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.set("key3", "value3")
        
        # 多次访问key1和key2
        for _ in range(5):
            await cache.get("key1")
            await cache.get("key2")
            
        # key3只访问一次
        await cache.get("key3")
        
        # 添加新项，应淘汰key3（最少使用）
        await cache.set("key4", "value4")
        
        assert await cache.get("key1") is not None
        assert await cache.get("key2") is not None
        assert await cache.get("key3") is None  # 被淘汰
        assert await cache.get("key4") is not None
        
        await cache.stop()
        
    @pytest.mark.asyncio
    async def test_adaptive_strategy(self):
        """测试自适应策略."""
        cache = AdaptiveCache(
            max_size=5,
            strategy=CacheStrategy.ADAPTIVE,
        )
        await cache.start()
        
        # 添加缓存项
        for i in range(5):
            await cache.set(f"key{i}", f"value{i}")
            
        # 模拟不同访问模式
        # key0: 高频访问（热键）
        for _ in range(20):
            await cache.get("key0")
            
        # key1: 中频访问
        for _ in range(5):
            await cache.get("key1")
            
        # key2, key3, key4: 低频访问
        await cache.get("key2")
        await cache.get("key3")
        
        # 添加新项触发淘汰
        await cache.set("key5", "value5")
        
        # 热键应保留
        assert await cache.get("key0") is not None
        
        await cache.stop()
        
    @pytest.mark.asyncio
    async def test_hot_key_promotion(self, cache):
        """测试热键提升."""
        await cache.set("key1", "value1")
        
        # 多次访问使其成为热键
        for _ in range(15):
            await cache.get("key1")
            
        # 检查是否被识别为热键
        pattern = cache._access_patterns.get("key1")
        if pattern:
            assert pattern.is_hot_key()
            
    @pytest.mark.asyncio
    async def test_cache_stats(self, cache):
        """测试缓存统计."""
        # 添加一些缓存
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        
        # 访问缓存
        await cache.get("key1")
        await cache.get("key1")
        await cache.get("nonexistent")
        
        stats = await cache.get_stats()
        
        assert "size" in stats
        assert "max_size" in stats
        assert "hit_count" in stats
        assert "miss_count" in stats
        assert "eviction_count" in stats
        assert stats["size"] == 2
        
    @pytest.mark.asyncio
    async def test_get_many(self, cache):
        """测试批量获取."""
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.set("key3", "value3")
        
        values = await cache.get_many(["key1", "key2", "nonexistent"])
        
        assert values["key1"] == "value1"
        assert values["key2"] == "value2"
        assert "nonexistent" not in values
        
    @pytest.mark.asyncio
    async def test_set_many(self, cache):
        """测试批量设置."""
        items = {
            "key1": "value1",
            "key2": "value2",
            "key3": "value3",
        }
        
        await cache.set_many(items)
        
        assert await cache.get("key1") == "value1"
        assert await cache.get("key2") == "value2"
        assert await cache.get("key3") == "value3"
        
    @pytest.mark.asyncio
    async def test_delete_many(self, cache):
        """测试批量删除."""
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.set("key3", "value3")
        
        deleted = await cache.delete_many(["key1", "key2", "nonexistent"])
        
        assert deleted == 2
        assert await cache.get("key1") is None
        assert await cache.get("key2") is None
        assert await cache.get("key3") == "value3"


class TestAdaptiveCacheIntegration:
    """自适应缓存集成测试."""

    @pytest.mark.asyncio
    async def test_real_world_scenario(self):
        """测试真实场景."""
        cache = AdaptiveCache(
            max_size=50,
            default_ttl=600,
            strategy=CacheStrategy.ADAPTIVE,
        )
        await cache.start()
        
        # 模拟真实访问模式
        # 1. 添加一些数据
        for i in range(30):
            await cache.set(f"data_{i}", f"value_{i}")
            
        # 2. 模拟热点数据访问
        hot_keys = [f"data_{i}" for i in range(5)]
        for _ in range(50):
            for key in hot_keys:
                await cache.get(key)
                
        # 3. 模拟普通访问
        for i in range(10, 20):
            await cache.get(f"data_{i}")
            
        # 4. 添加新数据触发淘汰
        for i in range(30, 40):
            await cache.set(f"data_{i}", f"value_{i}")
            
        # 5. 验证热点数据仍在缓存中
        for key in hot_keys:
            assert await cache.get(key) is not None, f"Hot key {key} should not be evicted"
            
        # 6. 检查统计
        stats = await cache.get_stats()
        assert stats["hit_count"] > 0
        assert stats["miss_count"] >= 0
        
        await cache.stop()
        
    @pytest.mark.asyncio
    async def test_concurrent_access(self):
        """测试并发访问."""
        cache = AdaptiveCache(
            max_size=100,
            strategy=CacheStrategy.ADAPTIVE,
        )
        await cache.start()
        
        # 并发写入
        async def writer(start, count):
            for i in range(count):
                await cache.set(f"key_{start}_{i}", f"value_{start}_{i}")
                
        # 并发读取
        async def reader(keys):
            for key in keys:
                await cache.get(key)
                
        # 启动多个写入任务
        write_tasks = [
            asyncio.create_task(writer(i * 10, 10))
            for i in range(5)
        ]
        
        await asyncio.gather(*write_tasks)
        
        # 启动多个读取任务
        all_keys = [f"key_{i}_{j}" for i in range(5) for j in range(10)]
        read_tasks = [
            asyncio.create_task(reader(all_keys[i::3]))
            for i in range(3)
        ]
        
        await asyncio.gather(*read_tasks)
        
        stats = await cache.get_stats()
        assert stats["size"] <= 100  # 不超过最大容量
        
        await cache.stop()
