"""安全 AST 缓存测试."""

import gzip
import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from ut_agent.tools.ast_cache_secure import (
    SecureASTCacheManager,
    CacheEntry,
    CacheStats,
    parse_java_ast_secure,
    parse_typescript_ast_secure,
)


class TestCacheEntry:
    """缓存条目测试."""

    def test_cache_entry_creation(self):
        """测试缓存条目创建."""
        entry = CacheEntry(
            file_path="/test/Test.java",
            content_hash="abc123",
            language="java",
            ast_data={"type": "program"},
        )
        
        assert entry.file_path == "/test/Test.java"
        assert entry.content_hash == "abc123"
        assert entry.language == "java"
        assert entry.access_count == 0

    def test_cache_entry_not_expired(self):
        """测试未过期."""
        entry = CacheEntry(
            file_path="/test/Test.java",
            content_hash="abc123",
            language="java",
            ast_data={},
            ttl_seconds=3600,
        )
        
        assert entry.is_expired() is False

    def test_cache_entry_expired(self):
        """测试已过期."""
        from datetime import datetime, timedelta
        
        entry = CacheEntry(
            file_path="/test/Test.java",
            content_hash="abc123",
            language="java",
            ast_data={},
            created_at=datetime.now() - timedelta(hours=2),
            ttl_seconds=3600,
        )
        
        assert entry.is_expired() is True


class TestCacheStats:
    """缓存统计测试."""

    def test_hit_rate_zero(self):
        """测试命中率为 0."""
        stats = CacheStats()
        assert stats.hit_rate == 0.0

    def test_hit_rate_calculation(self):
        """测试命中率计算."""
        stats = CacheStats(hit_count=80, miss_count=20)
        assert stats.hit_rate == 0.8


class TestSecureASTCacheManager:
    """安全 AST 缓存管理器测试."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """重置单例."""
        SecureASTCacheManager.reset_instance()
        yield
        SecureASTCacheManager.reset_instance()

    @pytest.fixture
    def cache_manager(self, tmp_path):
        """创建缓存管理器."""
        return SecureASTCacheManager.get_instance(cache_dir=tmp_path / "ast_cache")

    def test_singleton_pattern(self, tmp_path):
        """测试单例模式."""
        cm1 = SecureASTCacheManager.get_instance(cache_dir=tmp_path / "cache1")
        cm2 = SecureASTCacheManager.get_instance(cache_dir=tmp_path / "cache2")
        
        # 应该是同一个实例
        assert cm1 is cm2

    def test_compute_hash_sha256(self, cache_manager):
        """测试 SHA256 哈希计算."""
        hash1 = cache_manager._compute_hash("test content")
        hash2 = cache_manager._compute_hash("test content")
        hash3 = cache_manager._compute_hash("different content")
        
        # 相同内容应该产生相同哈希
        assert hash1 == hash2
        # 不同内容应该产生不同哈希
        assert hash1 != hash3
        # SHA256 哈希长度应该是 64
        assert len(hash1) == 64

    def test_get_cache_key(self, cache_manager):
        """测试缓存键生成."""
        key = cache_manager._get_cache_key("/test/File.java", "java")
        
        assert "java" in key
        assert "File.java" in key

    def test_get_cache_file_path(self, cache_manager):
        """测试缓存文件路径."""
        cache_key = "java:/test/File.java"
        path = cache_manager._get_cache_file_path(cache_key)
        
        # 应该是 .json.gz 扩展名
        assert path.suffixes == [".json", ".gz"]

    def test_serialize_ast_with_compression(self, cache_manager):
        """测试 AST 序列化（带压缩）."""
        ast_data = {"type": "program", "children": []}
        
        serialized = cache_manager._serialize_ast(ast_data)
        
        # 应该是 gzip 压缩的数据
        assert isinstance(serialized, bytes)
        # 解压后应该能还原
        decompressed = gzip.decompress(serialized)
        assert json.loads(decompressed) == ast_data

    def test_deserialize_ast(self, cache_manager):
        """测试 AST 反序列化."""
        ast_data = {"type": "program", "children": []}
        serialized = cache_manager._serialize_ast(ast_data)
        
        deserialized = cache_manager._deserialize_ast(serialized)
        
        assert deserialized == ast_data

    def test_deserialize_ast_uncompressed(self, cache_manager):
        """测试反序列化未压缩数据."""
        ast_data = {"type": "program"}
        json_data = json.dumps(ast_data).encode("utf-8")
        
        deserialized = cache_manager._deserialize_ast(json_data)
        
        assert deserialized == ast_data

    def test_evict_entry(self, cache_manager, tmp_path):
        """测试清理缓存条目."""
        # 创建测试缓存文件
        cache_key = "java:/test/File.java"
        cache_file = cache_manager._get_cache_file_path(cache_key)
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_bytes(b"test data")
        
        # 添加缓存条目
        cache_manager._cache[cache_key] = CacheEntry(
            file_path="/test/File.java",
            content_hash="abc",
            language="java",
            ast_data={},
            size_bytes=100,
        )
        cache_manager._stats.total_entries = 1
        cache_manager._stats.total_size_bytes = 100
        
        # 清理条目
        cache_manager._evict_entry(cache_key)
        
        assert cache_key not in cache_manager._cache
        assert not cache_file.exists()
        assert cache_manager._stats.eviction_count == 1

    def test_clear_cache(self, cache_manager, tmp_path):
        """测试清空缓存."""
        # 创建测试文件
        cache_manager._cache_dir.mkdir(parents=True, exist_ok=True)
        test_file = cache_manager._cache_dir / "test.json.gz"
        test_file.write_bytes(b"test")
        
        # 添加条目
        cache_manager._cache["test"] = CacheEntry(
            file_path="/test.java",
            content_hash="abc",
            language="java",
            ast_data={},
        )
        
        # 清空
        cache_manager.clear()
        
        assert len(cache_manager._cache) == 0
        assert not test_file.exists()

    def test_get_size_info(self, cache_manager):
        """测试获取大小信息."""
        cache_manager._stats.total_entries = 10
        cache_manager._stats.total_size_bytes = 1024 * 1024  # 1MB
        
        info = cache_manager.get_size_info()
        
        assert info["total_entries"] == 10
        assert info["total_size_mb"] == 1.0


class TestParseJavaAstSecure:
    """安全 Java AST 解析测试."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """重置单例."""
        SecureASTCacheManager.reset_instance()
        yield
        SecureASTCacheManager.reset_instance()

    def test_parse_java_without_cache(self, tmp_path):
        """测试不使用缓存解析."""
        java_file = tmp_path / "Test.java"
        java_file.write_text("public class Test {}", encoding="utf-8")
        
        result = parse_java_ast_secure(str(java_file), use_cache=False)
        
        assert result["type"] == "program"

    def test_parse_typescript_without_cache(self, tmp_path):
        """测试不使用缓存解析 TypeScript."""
        ts_file = tmp_path / "Test.ts"
        ts_file.write_text("function test() {}", encoding="utf-8")
        
        result = parse_typescript_ast_secure(str(ts_file), use_cache=False)
        
        assert result["type"] == "program"


class TestSecurityImprovements:
    """安全改进测试."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """重置单例."""
        SecureASTCacheManager.reset_instance()
        yield
        SecureASTCacheManager.reset_instance()

    @pytest.fixture
    def cache_manager(self, tmp_path):
        """创建缓存管理器."""
        return SecureASTCacheManager.get_instance(cache_dir=tmp_path / "ast_cache")

    def test_no_pickle_usage(self, cache_manager):
        """测试不使用 pickle."""
        import pickle
        
        ast_data = {"type": "program", "children": []}
        serialized = cache_manager._serialize_ast(ast_data)
        
        # 尝试用 pickle 加载应该失败
        with pytest.raises(Exception):
            pickle.loads(serialized)

    def test_json_format(self, cache_manager):
        """测试使用 JSON 格式."""
        ast_data = {"type": "program", "children": []}
        serialized = cache_manager._serialize_ast(ast_data)
        
        # 解压后应该是有效的 JSON
        decompressed = gzip.decompress(serialized)
        parsed = json.loads(decompressed)
        
        assert parsed == ast_data

    def test_sha256_not_md5(self, cache_manager):
        """测试使用 SHA256 而非 MD5."""
        hash_value = cache_manager._compute_hash("test")
        
        # SHA256 长度是 64，MD5 长度是 32
        assert len(hash_value) == 64

    def test_compression_reduces_size(self, cache_manager):
        """测试压缩减少大小."""
        # 创建大 AST 数据
        ast_data = {
            "type": "program",
            "children": [{"type": "class", "name": f"Class{i}"} for i in range(100)]
        }
        
        json_data = json.dumps(ast_data).encode("utf-8")
        compressed = cache_manager._serialize_ast(ast_data)
        
        # 压缩后应该更小
        assert len(compressed) < len(json_data) * 1.1  # 允许一点开销
