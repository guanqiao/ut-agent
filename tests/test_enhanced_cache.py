"""增强型缓存测试."""

import gzip
import pytest
from pathlib import Path
from datetime import datetime, timedelta

from ut_agent.cache.enhanced_cache import (
    EnhancedCache,
    CompressionStrategy,
    HashStrategy,
    CacheMetadata,
)


class TestCompressionStrategy:
    """压缩策略测试."""

    def test_compress_decompress(self):
        """测试压缩和解压."""
        # 使用更大的数据来确保压缩有效
        original = b"x" * 1000 + b"This is test data that will be compressed and decompressed."
        compressed = CompressionStrategy.compress(original)
        decompressed = CompressionStrategy.decompress(compressed)
        
        assert decompressed == original
        assert len(compressed) < len(original)

    def test_should_compress_large_data(self):
        """测试大数据应该压缩."""
        data = b"x" * 2000
        assert CompressionStrategy.should_compress(data, threshold=1024) is True

    def test_should_not_compress_small_data(self):
        """测试小数据不应该压缩."""
        data = b"small"
        assert CompressionStrategy.should_compress(data, threshold=1024) is False


class TestHashStrategy:
    """哈希策略测试."""

    def test_compute_sha256_string(self):
        """测试字符串 SHA256 哈希."""
        hash_value = HashStrategy.compute_sha256("test")
        assert len(hash_value) == 64
        assert all(c in '0123456789abcdef' for c in hash_value)

    def test_compute_sha256_bytes(self):
        """测试字节 SHA256 哈希."""
        hash_value = HashStrategy.compute_sha256(b"test")
        assert len(hash_value) == 64

    def test_sha256_consistency(self):
        """测试 SHA256 一致性."""
        hash1 = HashStrategy.compute_sha256("test")
        hash2 = HashStrategy.compute_sha256("test")
        assert hash1 == hash2

    def test_sha256_different_inputs(self):
        """测试不同输入产生不同哈希."""
        hash1 = HashStrategy.compute_sha256("test1")
        hash2 = HashStrategy.compute_sha256("test2")
        assert hash1 != hash2

    def test_compute_md5(self):
        """测试 MD5 哈希."""
        hash_value = HashStrategy.compute_md5("test")
        assert len(hash_value) == 32


class TestCacheMetadata:
    """缓存元数据测试."""

    def test_metadata_creation(self):
        """测试元数据创建."""
        meta = CacheMetadata(
            key="test_key",
            created_at=datetime.now(),
            expires_at=None,
            size_bytes=100,
        )
        
        assert meta.key == "test_key"
        assert meta.size_bytes == 100
        assert meta.compressed is False


class TestEnhancedCache:
    """增强型缓存测试."""

    @pytest.fixture
    def cache(self, tmp_path):
        """创建缓存实例."""
        return EnhancedCache(
            max_memory_size=10,
            max_disk_size=20,
            disk_cache_dir=tmp_path / "cache",
            compression_enabled=True,
            compression_threshold=100,
        )

    def test_get_set_memory(self, cache):
        """测试内存缓存的 get/set."""
        cache.set("key1", "value1")
        
        result = cache.get("key1")
        
        assert result == "value1"

    def test_get_nonexistent(self, cache):
        """测试获取不存在的键."""
        result = cache.get("nonexistent")
        
        assert result is None

    def test_update_existing_key(self, cache):
        """测试更新已存在的键."""
        cache.set("key1", "value1")
        cache.set("key1", "value2")
        
        result = cache.get("key1")
        
        assert result == "value2"

    def test_memory_cache_hit_rate(self, cache):
        """测试内存缓存命中率."""
        cache.set("key1", "value1")
        
        # 多次获取
        for _ in range(5):
            cache.get("key1")
        
        stats = cache.get_stats()
        assert stats["memory"]["hits"] == 5
        assert stats["memory"]["hit_rate"] == 1.0

    def test_disk_cache(self, tmp_path):
        """测试磁盘缓存."""
        cache = EnhancedCache(
            max_memory_size=10,
            max_disk_size=20,
            disk_cache_dir=tmp_path / "cache",
        )
        
        # 存储到磁盘
        cache.set("disk_key", "disk_value", store_on_disk=True)
        
        # 从磁盘读取
        result = cache.get("disk_key")
        
        assert result == "disk_value"

    def test_memory_eviction(self, cache):
        """测试内存缓存淘汰."""
        # 填充缓存到上限
        for i in range(15):  # 超过 max_memory_size=10
            cache.set(f"key{i}", f"value{i}")
        
        # 检查大小没有超过限制
        stats = cache.get_stats()
        assert stats["memory"]["size"] <= 10

    def test_delete(self, cache):
        """测试删除."""
        cache.set("key1", "value1")
        
        deleted = cache.delete("key1")
        
        assert deleted is True
        assert cache.get("key1") is None

    def test_delete_nonexistent(self, cache):
        """测试删除不存在的键."""
        deleted = cache.delete("nonexistent")
        
        assert deleted is False

    def test_clear(self, cache):
        """测试清空."""
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        
        cache.clear()
        
        assert cache.get("key1") is None
        assert cache.get("key2") is None
        stats = cache.get_stats()
        assert stats["memory"]["size"] == 0

    def test_ttl_expiration(self, cache):
        """测试 TTL 过期."""
        # 设置非常短的 TTL
        cache.set("key1", "value1", ttl=1)
        
        # 应该能获取到
        result1 = cache.get("key1")
        assert result1 == "value1"
        
        # 修改过期时间到过去，模拟过期
        import time
        time.sleep(1.1)
        
        # 现在应该过期了
        result2 = cache.get("key1")
        assert result2 is None

    def test_cleanup_expired(self, cache):
        """测试清理过期缓存."""
        import time
        
        cache.set("key1", "value1", ttl=1)
        cache.set("key2", "value2", ttl=3600)
        
        # 等待 key1 过期
        time.sleep(1.1)
        
        count = cache.cleanup_expired()
        
        assert count >= 1
        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"

    def test_compression(self, tmp_path):
        """测试压缩功能."""
        cache = EnhancedCache(
            max_memory_size=10,
            max_disk_size=20,
            disk_cache_dir=tmp_path / "cache",
            compression_enabled=True,
            compression_threshold=50,
        )
        
        # 存储大数据到磁盘
        large_data = "x" * 1000
        cache.set("large_key", large_data, store_on_disk=True)
        
        # 验证能正确读取
        result = cache.get("large_key")
        assert result == large_data

    def test_checksum_verification(self, tmp_path):
        """测试校验和验证."""
        cache = EnhancedCache(
            max_memory_size=10,
            max_disk_size=20,
            disk_cache_dir=tmp_path / "cache",
        )
        
        cache.set("key1", "value1", store_on_disk=True)
        
        # 篡改缓存文件
        cache_path = cache._get_disk_cache_path("key1")
        if cache_path.exists():
            with open(cache_path, 'wb') as f:
                f.write(b"corrupted data")
        
        # 清除内存缓存，强制从磁盘读取
        cache._remove_from_memory("key1")
        
        # 应该检测到校验和不匹配
        result = cache.get("key1")
        assert result is None

    def test_stats(self, cache):
        """测试统计信息."""
        cache.set("key1", "value1")
        cache.get("key1")
        cache.get("nonexistent")
        
        stats = cache.get_stats()
        
        assert "memory" in stats
        assert "disk" in stats
        assert "compression" in stats
        assert stats["memory"]["size"] == 1
        assert stats["memory"]["hits"] == 1
        assert stats["memory"]["misses"] == 1

    def test_persistence(self, tmp_path):
        """测试持久化."""
        cache_dir = tmp_path / "cache"
        
        # 创建缓存并存储数据
        cache1 = EnhancedCache(
            max_memory_size=10,
            max_disk_size=20,
            disk_cache_dir=cache_dir,
        )
        cache1.set("persist_key", "persist_value", store_on_disk=True)
        
        # 创建新缓存实例（应该加载索引）
        cache2 = EnhancedCache(
            max_memory_size=10,
            max_disk_size=20,
            disk_cache_dir=cache_dir,
        )
        
        # 应该能从磁盘读取
        result = cache2.get("persist_key")
        assert result == "persist_value"

    def test_complex_data_types(self, cache):
        """测试复杂数据类型."""
        data = {
            "list": [1, 2, 3],
            "dict": {"a": 1, "b": 2},
            "tuple": (1, 2, 3),
        }
        
        cache.set("complex", data)
        result = cache.get("complex")
        
        assert result == data

    def test_thread_safety(self, cache):
        """测试线程安全."""
        import threading
        
        results = []
        
        def worker():
            for i in range(10):
                cache.set(f"key{i}", f"value{i}")
                result = cache.get(f"key{i}")
                results.append(result)
        
        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # 所有操作都应该成功
        assert len(results) == 50
        assert all(r is not None for r in results)


class TestSHA256Advantage:
    """SHA256 优势测试."""

    def test_sha256_longer_than_md5(self):
        """测试 SHA256 比 MD5 长."""
        data = "test"
        sha256_hash = HashStrategy.compute_sha256(data)
        md5_hash = HashStrategy.compute_md5(data)
        
        assert len(sha256_hash) == 64
        assert len(md5_hash) == 32
        assert len(sha256_hash) > len(md5_hash)

    def test_sha256_collision_resistance(self):
        """测试 SHA256 抗碰撞性."""
        # 生成大量哈希，检查是否有碰撞
        hashes = set()
        for i in range(1000):
            hash_value = HashStrategy.compute_sha256(f"data{i}")
            hashes.add(hash_value)
        
        # 应该没有碰撞
        assert len(hashes) == 1000


class TestCompressionBenefits:
    """压缩优势测试."""

    def test_compression_reduces_size(self):
        """测试压缩减少大小."""
        data = b"x" * 10000
        compressed = CompressionStrategy.compress(data)
        
        # 压缩后应该更小
        assert len(compressed) < len(data)
        
        # 解压后应该还原
        decompressed = CompressionStrategy.decompress(compressed)
        assert decompressed == data

    def test_compression_ratio(self):
        """测试压缩率."""
        # 重复数据应该有高压缩率
        data = b"ABCD" * 1000
        compressed = CompressionStrategy.compress(data)
        
        ratio = len(compressed) / len(data)
        assert ratio < 0.1  # 压缩率应该小于 10%
