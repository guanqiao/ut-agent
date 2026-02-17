"""AST 缓存管理器 - 安全版本.

优化点：
1. 使用 JSON 替代 pickle 进行序列化，防止代码执行漏洞
2. 使用 SHA256 替代 MD5 进行哈希计算
3. 添加缓存压缩支持
"""

import gzip
import hashlib
import json
import os
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import tree_sitter_java as ts_java
import tree_sitter_typescript as ts_typescript
from tree_sitter import Language, Parser

from ut_agent.exceptions import ASTParseError


@dataclass
class CacheEntry:
    """缓存条目."""
    file_path: str
    content_hash: str
    language: str
    ast_data: Any
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    size_bytes: int = 0
    ttl_seconds: int = 86400

    def is_expired(self) -> bool:
        """检查缓存是否过期."""
        if self.ttl_seconds <= 0:
            return False
        expiry_time = self.created_at + timedelta(seconds=self.ttl_seconds)
        return datetime.now() > expiry_time


@dataclass
class CacheStats:
    """缓存统计信息."""
    total_entries: int = 0
    total_size_bytes: int = 0
    hit_count: int = 0
    miss_count: int = 0
    eviction_count: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hit_count + self.miss_count
        return self.hit_count / total if total > 0 else 0.0


class SecureASTCacheManager:
    """AST 缓存管理器 - 安全版本.
    
    安全改进：
    1. 使用 JSON 替代 pickle 进行序列化
    2. 使用 SHA256 替代 MD5 进行哈希计算
    3. 支持缓存压缩
    """

    _instance: Optional["SecureASTCacheManager"] = None

    def __new__(cls, cache_dir: Optional[Path] = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, cache_dir: Optional[Path] = None):
        if self._initialized:
            return

        from ut_agent.config import settings
        self._cache_dir = cache_dir or Path.cwd() / ".ut-agent" / "ast_cache"
        self._cache_dir.mkdir(parents=True, exist_ok=True)

        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._stats = CacheStats()
        self._max_cache_size = settings.ast_cache_max_size
        self._max_entries = settings.ast_cache_max_entries
        self._default_ttl = settings.ast_cache_ttl
        self._parsers: Dict[str, Parser] = {}
        self._compression_enabled = True

        self._load_cache_index()
        self._initialized = True

    @classmethod
    def get_instance(cls, cache_dir: Optional[Path] = None) -> "SecureASTCacheManager":
        """获取单例实例."""
        return cls(cache_dir)

    @classmethod
    def reset_instance(cls):
        """重置单例实例（用于测试）."""
        cls._instance = None

    def _get_parser(self, language: str) -> Parser:
        """获取或创建解析器."""
        if language not in self._parsers:
            parser = Parser()
            if language == "java":
                parser.language = Language(ts_java.language())
            elif language in ("typescript", "typescript tsx"):
                parser.language = Language(ts_typescript.language_typescript())
            elif language == "tsx":
                parser.language = Language(ts_typescript.language_tsx())
            else:
                raise ValueError(f"不支持的语言: {language}")
            self._parsers[language] = parser
        return self._parsers[language]

    def _compute_hash(self, content: str) -> str:
        """计算内容哈希 - 使用 SHA256 替代 MD5."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _get_cache_key(self, file_path: str, language: str) -> str:
        """生成缓存键."""
        abs_path = str(Path(file_path).resolve())
        return f"{language}:{abs_path}"

    def _get_cache_file_path(self, cache_key: str) -> Path:
        """获取缓存文件路径."""
        safe_key = hashlib.sha256(cache_key.encode()).hexdigest()
        return self._cache_dir / f"{safe_key}.json.gz"

    def _load_cache_index(self):
        """加载缓存索引."""
        index_file = self._cache_dir / "index.json"
        if not index_file.exists():
            return

        try:
            with open(index_file, "r", encoding="utf-8") as f:
                index_data = json.load(f)

            for entry_data in index_data.get("entries", []):
                cache_key = entry_data.get("cache_key")
                if not cache_key:
                    continue

                cache_file = self._get_cache_file_path(cache_key)
                if not cache_file.exists():
                    continue

                self._cache[cache_key] = CacheEntry(
                    file_path=entry_data.get("file_path", ""),
                    content_hash=entry_data.get("content_hash", ""),
                    language=entry_data.get("language", ""),
                    ast_data=None,
                    created_at=datetime.fromisoformat(entry_data.get("created_at", datetime.now().isoformat())),
                    last_accessed=datetime.fromisoformat(entry_data.get("last_accessed", datetime.now().isoformat())),
                    access_count=entry_data.get("access_count", 0),
                    size_bytes=entry_data.get("size_bytes", 0),
                )

            self._stats.total_entries = len(self._cache)
            self._stats.total_size_bytes = sum(e.size_bytes for e in self._cache.values())

        except Exception as e:
            print(f"加载缓存索引失败: {e}")

    def _save_cache_index(self):
        """保存缓存索引."""
        index_file = self._cache_dir / "index.json"

        entries = []
        for cache_key, entry in self._cache.items():
            entries.append({
                "cache_key": cache_key,
                "file_path": entry.file_path,
                "content_hash": entry.content_hash,
                "language": entry.language,
                "created_at": entry.created_at.isoformat(),
                "last_accessed": entry.last_accessed.isoformat(),
                "access_count": entry.access_count,
                "size_bytes": entry.size_bytes,
            })

        index_data = {
            "version": "2.0",
            "format": "json.gz",
            "entries": entries,
            "stats": {
                "hit_count": self._stats.hit_count,
                "miss_count": self._stats.miss_count,
                "eviction_count": self._stats.eviction_count,
            },
        }

        with open(index_file, "w", encoding="utf-8") as f:
            json.dump(index_data, f, indent=2, ensure_ascii=False)

    def _evict_if_needed(self, required_space: int = 0):
        """在需要时清理缓存 - 使用 LRU 策略."""
        self._evict_expired_entries()

        while (
            (self._stats.total_size_bytes + required_space > self._max_cache_size
             or len(self._cache) >= self._max_entries)
            and len(self._cache) > 0
        ):
            oldest_key = next(iter(self._cache))
            self._evict_entry(oldest_key)

    def _evict_expired_entries(self):
        """清理过期缓存条目."""
        expired_keys = [
            key for key, entry in self._cache.items()
            if entry.is_expired()
        ]
        for key in expired_keys:
            self._evict_entry(key)

    def _evict_entry(self, cache_key: str):
        """清理指定缓存条目."""
        if cache_key not in self._cache:
            return

        entry = self._cache[cache_key]
        cache_file = self._get_cache_file_path(cache_key)

        if cache_file.exists():
            cache_file.unlink()

        self._stats.total_size_bytes -= entry.size_bytes
        self._stats.total_entries -= 1
        self._stats.eviction_count += 1

        del self._cache[cache_key]

    def _serialize_ast(self, ast_data: Any) -> bytes:
        """序列化 AST 数据 - 使用 JSON + gzip 压缩.
        
        Args:
            ast_data: AST 数据
            
        Returns:
            bytes: 压缩后的 JSON 数据
        """
        json_data = json.dumps(ast_data, ensure_ascii=False).encode("utf-8")
        
        if self._compression_enabled:
            return gzip.compress(json_data, compresslevel=6)
        return json_data

    def _deserialize_ast(self, data: bytes) -> Any:
        """反序列化 AST 数据.
        
        Args:
            data: 压缩数据
            
        Returns:
            Any: AST 数据
        """
        try:
            # 尝试解压
            json_data = gzip.decompress(data)
        except gzip.BadGzipFile:
            # 如果不是压缩数据，直接使用
            json_data = data
        
        return json.loads(json_data.decode("utf-8"))

    def get_or_parse(
        self,
        file_path: str,
        language: str,
        content: Optional[str] = None,
    ) -> Tuple[Any, bool]:
        """获取或解析 AST.

        Args:
            file_path: 文件路径
            language: 语言类型
            content: 文件内容（可选，不提供则自动读取）

        Returns:
            Tuple[Any, bool]: (AST数据, 是否命中缓存)
        """
        from ut_agent.utils.metrics import record_cache_operation
        path = Path(file_path)
        if content is None:
            content = path.read_text(encoding="utf-8")

        content_hash = self._compute_hash(content)
        cache_key = self._get_cache_key(file_path, language)

        if cache_key in self._cache:
            entry = self._cache[cache_key]

            if entry.is_expired():
                self._evict_entry(cache_key)
                record_cache_operation("ast", "evict", hit=False)
            elif entry.content_hash == content_hash:
                self._cache.move_to_end(cache_key)
                entry.last_accessed = datetime.now()
                entry.access_count += 1
                self._stats.hit_count += 1
                record_cache_operation("ast", "get", hit=True)

                cache_file = self._get_cache_file_path(cache_key)
                if cache_file.exists() and entry.ast_data is None:
                    try:
                        with open(cache_file, "rb") as f:
                            entry.ast_data = self._deserialize_ast(f.read())
                    except Exception:
                        self._evict_entry(cache_key)
                        record_cache_operation("ast", "evict", hit=False)
                        return self._parse_and_cache(file_path, language, content, content_hash, cache_key), False

                return entry.ast_data, True

        self._stats.miss_count += 1
        record_cache_operation("ast", "get", hit=False)
        return self._parse_and_cache(file_path, language, content, content_hash, cache_key), False

    def _parse_and_cache(
        self,
        file_path: str,
        language: str,
        content: str,
        content_hash: str,
        cache_key: str,
    ) -> Any:
        """解析并缓存 AST."""
        from ut_agent.utils.metrics import ast_parse, record_cache_operation
        # 解析 AST 并记录性能
        with ast_parse(file_path, language):
            parser = self._get_parser(language)
            tree = parser.parse(bytes(content, "utf-8"))

            ast_data = self._serialize_tree(tree)

        cache_file = self._get_cache_file_path(cache_key)
        serialized = self._serialize_ast(ast_data)
        size_bytes = len(serialized)

        self._evict_if_needed(size_bytes)

        with open(cache_file, "wb") as f:
            f.write(serialized)

        entry = CacheEntry(
            file_path=file_path,
            content_hash=content_hash,
            language=language,
            ast_data=ast_data,
            size_bytes=size_bytes,
            ttl_seconds=self._default_ttl,
        )

        self._cache[cache_key] = entry
        self._stats.total_entries += 1
        self._stats.total_size_bytes += size_bytes

        record_cache_operation("ast", "set", hit=False)
        self._save_cache_index()

        return ast_data

    def _serialize_tree(self, tree) -> Dict[str, Any]:
        """序列化 AST 树."""
        root = tree.root_node

        def node_to_dict(node) -> Dict[str, Any]:
            result = {
                "type": node.type,
                "start_byte": node.start_byte,
                "end_byte": node.end_byte,
                "start_point": {"row": node.start_point.row, "column": node.start_point.column},
                "end_point": {"row": node.end_point.row, "column": node.end_point.column},
                "text": node.text.decode("utf-8") if len(node.text) < 10000 else None,
                "children": [],
            }

            for i in range(node.child_count):
                child = node.child(i)
                result["children"].append(node_to_dict(child))

            return result

        return node_to_dict(root)

    def invalidate(self, file_path: str, language: Optional[str] = None):
        """使指定文件的缓存失效."""
        if language:
            cache_key = self._get_cache_key(file_path, language)
            if cache_key in self._cache:
                self._evict_entry(cache_key)
        else:
            keys_to_remove = [
                k for k in self._cache
                if k.endswith(str(Path(file_path).resolve()))
            ]
            for key in keys_to_remove:
                self._evict_entry(key)

        self._save_cache_index()

    def clear(self):
        """清空所有缓存."""
        for cache_file in self._cache_dir.glob("*.json.gz"):
            cache_file.unlink()

        self._cache.clear()
        self._stats = CacheStats()

        index_file = self._cache_dir / "index.json"
        if index_file.exists():
            index_file.unlink()

    def get_cache_stats(self) -> CacheStats:
        """获取缓存统计信息."""
        return self._stats

    def get_cached_files(self) -> List[str]:
        """获取已缓存的文件列表."""
        return list(set(entry.file_path for entry in self._cache.values()))

    def get_size_info(self) -> Dict[str, Any]:
        """获取缓存大小信息."""
        return {
            "total_entries": self._stats.total_entries,
            "total_size_bytes": self._stats.total_size_bytes,
            "total_size_mb": self._stats.total_size_bytes / (1024 * 1024),
            "max_size_mb": self._max_cache_size / (1024 * 1024),
            "usage_percent": (self._stats.total_size_bytes / self._max_cache_size) * 100,
        }


def parse_java_ast_secure(file_path: str, use_cache: bool = True) -> Dict[str, Any]:
    """解析 Java 文件 AST - 安全版本.

    Args:
        file_path: Java 文件路径
        use_cache: 是否使用缓存

    Returns:
        Dict: AST 数据
    """
    if use_cache:
        cache_manager = SecureASTCacheManager.get_instance()
        ast_data, _ = cache_manager.get_or_parse(file_path, "java")
        return ast_data
    else:
        parser = Parser(Language(ts_java.language()))
        content = Path(file_path).read_text(encoding="utf-8")
        tree = parser.parse(bytes(content, "utf-8"))

        cache_manager = SecureASTCacheManager.get_instance()
        return cache_manager._serialize_tree(tree)


def parse_typescript_ast_secure(file_path: str, use_cache: bool = True) -> Dict[str, Any]:
    """解析 TypeScript 文件 AST - 安全版本.

    Args:
        file_path: TypeScript 文件路径
        use_cache: 是否使用缓存

    Returns:
        Dict: AST 数据
    """
    if use_cache:
        cache_manager = SecureASTCacheManager.get_instance()
        ast_data, _ = cache_manager.get_or_parse(file_path, "typescript")
        return ast_data
    else:
        parser = Parser(Language(ts_typescript.language_typescript()))
        content = Path(file_path).read_text(encoding="utf-8")
        tree = parser.parse(bytes(content, "utf-8"))

        cache_manager = SecureASTCacheManager.get_instance()
        return cache_manager._serialize_tree(tree)
