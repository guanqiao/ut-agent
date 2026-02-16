"""AST 缓存管理器单元测试."""

import os
import tempfile
from pathlib import Path
from datetime import datetime

import pytest

from ut_agent.tools.ast_cache import (
    CacheEntry,
    CacheStats,
    ASTCacheManager,
    parse_java_ast,
    parse_typescript_ast,
)


class TestCacheEntry:
    """CacheEntry 测试."""

    def test_cache_entry_creation(self):
        """测试缓存条目创建."""
        entry = CacheEntry(
            file_path="/path/to/file.java",
            content_hash="abc123",
            language="java",
            ast_data={"type": "program"},
        )

        assert entry.file_path == "/path/to/file.java"
        assert entry.content_hash == "abc123"
        assert entry.language == "java"
        assert entry.ast_data == {"type": "program"}
        assert entry.access_count == 0

    def test_cache_entry_default_values(self):
        """测试缓存条目默认值."""
        entry = CacheEntry(
            file_path="/path/to/file.java",
            content_hash="abc123",
            language="java",
            ast_data=None,
        )

        assert isinstance(entry.created_at, datetime)
        assert isinstance(entry.last_accessed, datetime)
        assert entry.access_count == 0
        assert entry.size_bytes == 0


class TestCacheStats:
    """CacheStats 测试."""

    def test_cache_stats_creation(self):
        """测试缓存统计创建."""
        stats = CacheStats()

        assert stats.total_entries == 0
        assert stats.total_size_bytes == 0
        assert stats.hit_count == 0
        assert stats.miss_count == 0
        assert stats.eviction_count == 0

    def test_cache_stats_hit_rate_zero(self):
        """测试命中率为零."""
        stats = CacheStats()
        assert stats.hit_rate == 0.0

    def test_cache_stats_hit_rate_calculation(self):
        """测试命中率计算."""
        stats = CacheStats(hit_count=3, miss_count=1)
        assert stats.hit_rate == 0.75

    def test_cache_stats_hit_rate_all_hits(self):
        """测试全部命中."""
        stats = CacheStats(hit_count=10, miss_count=0)
        assert stats.hit_rate == 1.0


class TestASTCacheManager:
    """ASTCacheManager 测试."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        """每个测试前重置单例."""
        ASTCacheManager.reset_instance()
        self.cache_dir = tmp_path / ".ut-agent" / "ast_cache"
        self.cache_manager = ASTCacheManager(self.cache_dir)

    def test_singleton_pattern(self):
        """测试单例模式."""
        manager1 = ASTCacheManager.get_instance()
        manager2 = ASTCacheManager.get_instance()

        assert manager1 is manager2

    def test_cache_dir_creation(self):
        """测试缓存目录创建."""
        assert self.cache_dir.exists()

    def test_get_cache_stats(self):
        """测试获取缓存统计."""
        stats = self.cache_manager.get_cache_stats()

        assert isinstance(stats, CacheStats)
        assert stats.total_entries == 0

    def test_clear_cache(self):
        """测试清空缓存."""
        self.cache_manager.clear()

        stats = self.cache_manager.get_cache_stats()
        assert stats.total_entries == 0
        assert stats.total_size_bytes == 0

    def test_get_cached_files_empty(self):
        """测试获取空缓存文件列表."""
        files = self.cache_manager.get_cached_files()
        assert files == []

    def test_get_size_info(self):
        """测试获取缓存大小信息."""
        size_info = self.cache_manager.get_size_info()

        assert "total_entries" in size_info
        assert "total_size_bytes" in size_info
        assert "total_size_mb" in size_info
        assert "max_size_mb" in size_info
        assert "usage_percent" in size_info

    def test_compute_hash(self):
        """测试哈希计算."""
        content1 = "public class Test {}"
        content2 = "public class Test {}"
        content3 = "public class Other {}"

        hash1 = self.cache_manager._compute_hash(content1)
        hash2 = self.cache_manager._compute_hash(content2)
        hash3 = self.cache_manager._compute_hash(content3)

        assert hash1 == hash2
        assert hash1 != hash3

    def test_get_cache_key(self):
        """测试缓存键生成."""
        key1 = self.cache_manager._get_cache_key("/path/to/file.java", "java")
        key2 = self.cache_manager._get_cache_key("/path/to/file.java", "java")
        key3 = self.cache_manager._get_cache_key("/path/to/file.ts", "typescript")

        assert key1 == key2
        assert key1 != key3
        assert "java:" in key1
        assert "typescript:" in key3


class TestASTCacheManagerWithFiles:
    """ASTCacheManager 文件操作测试."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        """每个测试前设置."""
        ASTCacheManager.reset_instance()
        self.cache_dir = tmp_path / ".ut-agent" / "ast_cache"
        self.cache_manager = ASTCacheManager(self.cache_dir)
        self.test_dir = tmp_path / "test_files"
        self.test_dir.mkdir()

    def test_parse_java_file(self):
        """测试解析 Java 文件."""
        java_file = self.test_dir / "Test.java"
        java_file.write_text("""
package com.example;

public class Test {
    public void doSomething() {
        System.out.println("Hello");
    }
}
""")

        ast_data, cache_hit = self.cache_manager.get_or_parse(
            str(java_file), "java"
        )

        assert ast_data is not None
        assert cache_hit is False
        assert "type" in ast_data

    def test_parse_java_file_cache_hit(self):
        """测试 Java 文件缓存命中."""
        java_file = self.test_dir / "Test.java"
        java_file.write_text("public class Test { }")

        self.cache_manager.get_or_parse(str(java_file), "java")
        ast_data, cache_hit = self.cache_manager.get_or_parse(
            str(java_file), "java"
        )

        assert cache_hit is True
        assert ast_data is not None

    def test_parse_typescript_file(self):
        """测试解析 TypeScript 文件."""
        ts_file = self.test_dir / "test.ts"
        ts_file.write_text("""
export function add(a: number, b: number): number {
    return a + b;
}
""")

        ast_data, cache_hit = self.cache_manager.get_or_parse(
            str(ts_file), "typescript"
        )

        assert ast_data is not None
        assert cache_hit is False

    def test_invalidate_cache(self):
        """测试缓存失效."""
        java_file = self.test_dir / "Test.java"
        java_file.write_text("public class Test { }")

        self.cache_manager.get_or_parse(str(java_file), "java")

        self.cache_manager.invalidate(str(java_file), "java")

        stats = self.cache_manager.get_cache_stats()
        assert stats.total_entries == 0

    def test_invalidate_cache_all_languages(self):
        """测试缓存失效（所有语言）."""
        java_file = self.test_dir / "Test.java"
        java_file.write_text("public class Test { }")

        self.cache_manager.get_or_parse(str(java_file), "java")

        self.cache_manager.invalidate(str(java_file))

        stats = self.cache_manager.get_cache_stats()
        assert stats.total_entries == 0

    def test_warmup(self):
        """测试缓存预热."""
        files = []
        for i in range(3):
            java_file = self.test_dir / f"Test{i}.java"
            java_file.write_text(f"public class Test{i} {{ }}")
            files.append(str(java_file))

        self.cache_manager.warmup(files, "java")

        stats = self.cache_manager.get_cache_stats()
        assert stats.total_entries == 3

    def test_cache_miss_count(self):
        """测试缓存未命中计数."""
        java_file = self.test_dir / "Test.java"
        java_file.write_text("public class Test { }")

        initial_miss = self.cache_manager.get_cache_stats().miss_count

        self.cache_manager.get_or_parse(str(java_file), "java")

        new_stats = self.cache_manager.get_cache_stats()
        assert new_stats.miss_count >= initial_miss + 1

    def test_cache_hit_count(self):
        """测试缓存命中计数."""
        java_file = self.test_dir / "Test.java"
        java_file.write_text("public class Test { }")

        self.cache_manager.get_or_parse(str(java_file), "java")
        initial_hit = self.cache_manager.get_cache_stats().hit_count

        self.cache_manager.get_or_parse(str(java_file), "java")

        new_stats = self.cache_manager.get_cache_stats()
        assert new_stats.hit_count >= initial_hit + 1

    def test_file_modification_invalidates_cache(self):
        """测试文件修改使缓存失效."""
        java_file = self.test_dir / "Test.java"
        java_file.write_text("public class Test { }")

        self.cache_manager.get_or_parse(str(java_file), "java")

        java_file.write_text("public class Modified { }")

        ast_data, cache_hit = self.cache_manager.get_or_parse(
            str(java_file), "java"
        )

        assert cache_hit is False


class TestSerializeTree:
    """AST 序列化测试."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        """每个测试前设置."""
        ASTCacheManager.reset_instance()
        self.cache_dir = tmp_path / ".ut-agent" / "ast_cache"
        self.cache_manager = ASTCacheManager(self.cache_dir)
        self.test_dir = tmp_path / "test_files"
        self.test_dir.mkdir()

    def test_serialize_tree_structure(self):
        """测试 AST 序列化结构."""
        java_file = self.test_dir / "Test.java"
        java_file.write_text("public class Test { }")

        ast_data, _ = self.cache_manager.get_or_parse(str(java_file), "java")

        assert "type" in ast_data
        assert "children" in ast_data
        assert "start_byte" in ast_data
        assert "end_byte" in ast_data
        assert "start_point" in ast_data
        assert "end_point" in ast_data

    def test_serialize_tree_has_class_declaration(self):
        """测试 AST 包含类声明."""
        java_file = self.test_dir / "Test.java"
        java_file.write_text("public class Test { }")

        ast_data, _ = self.cache_manager.get_or_parse(str(java_file), "java")

        def find_class_node(node):
            if node.get("type") == "class_declaration":
                return node
            for child in node.get("children", []):
                result = find_class_node(child)
                if result:
                    return result
            return None

        class_node = find_class_node(ast_data)
        assert class_node is not None


class TestParseFunctions:
    """便捷解析函数测试."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        """每个测试前设置."""
        ASTCacheManager.reset_instance()
        self.test_dir = tmp_path / "test_files"
        self.test_dir.mkdir()

    def test_parse_java_ast_function(self):
        """测试 parse_java_ast 函数."""
        java_file = self.test_dir / "Test.java"
        java_file.write_text("public class Test { }")

        ast_data = parse_java_ast(str(java_file), use_cache=False)

        assert ast_data is not None
        assert "type" in ast_data

    def test_parse_typescript_ast_function(self):
        """测试 parse_typescript_ast 函数."""
        ts_file = self.test_dir / "test.ts"
        ts_file.write_text("export const x = 1;")

        ast_data = parse_typescript_ast(str(ts_file), use_cache=False)

        assert ast_data is not None
        assert "type" in ast_data

    def test_parse_java_ast_with_cache(self):
        """测试带缓存的 parse_java_ast 函数."""
        java_file = self.test_dir / "Test.java"
        java_file.write_text("public class Test { }")

        ast_data1 = parse_java_ast(str(java_file), use_cache=True)
        ast_data2 = parse_java_ast(str(java_file), use_cache=True)

        assert ast_data1 is not None
        assert ast_data2 is not None


class TestCacheEviction:
    """缓存清理测试."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        """每个测试前设置."""
        ASTCacheManager.reset_instance()
        self.cache_dir = tmp_path / ".ut-agent" / "ast_cache"
        self.cache_manager = ASTCacheManager(self.cache_dir)
        self.cache_manager._max_cache_size = 1000
        self.test_dir = tmp_path / "test_files"
        self.test_dir.mkdir()

    def test_evict_entry(self):
        """测试清理单个条目."""
        java_file = self.test_dir / "Test.java"
        java_file.write_text("public class Test { }")

        self.cache_manager.get_or_parse(str(java_file), "java")

        cache_key = self.cache_manager._get_cache_key(str(java_file), "java")
        self.cache_manager._evict_entry(cache_key)

        stats = self.cache_manager.get_cache_stats()
        assert stats.total_entries == 0
