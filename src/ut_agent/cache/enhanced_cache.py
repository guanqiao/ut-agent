"""增强型缓存系统.

优化点：
1. 使用 SHA256 替代 MD5 进行哈希计算
2. 添加缓存压缩支持（gzip）
3. 实现多级缓存策略（L1内存/L2磁盘）
4. 添加缓存持久化功能
"""

import gzip
import hashlib
import json
import os
import pickle
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from collections import OrderedDict
import threading
import logging

logger = logging.getLogger(__name__)


@dataclass
class CacheMetadata:
    """缓存元数据."""
    key: str
    created_at: datetime
    expires_at: Optional[datetime]
    size_bytes: int
    compressed: bool = False
    checksum: str = ""  # SHA256 checksum
    access_count: int = 0
    last_accessed: Optional[datetime] = None


class CompressionStrategy:
    """压缩策略."""
    
    @staticmethod
    def compress(data: bytes, level: int = 6) -> bytes:
        """压缩数据.
        
        Args:
            data: 原始数据
            level: 压缩级别 (1-9)
            
        Returns:
            bytes: 压缩后的数据
        """
        return gzip.compress(data, compresslevel=level)
    
    @staticmethod
    def decompress(data: bytes) -> bytes:
        """解压数据.
        
        Args:
            data: 压缩数据
            
        Returns:
            bytes: 解压后的数据
        """
        return gzip.decompress(data)
    
    @staticmethod
    def should_compress(data: bytes, threshold: int = 1024) -> bool:
        """判断是否应该压缩.
        
        Args:
            data: 数据
            threshold: 压缩阈值（字节）
            
        Returns:
            bool: 是否应该压缩
        """
        return len(data) > threshold


class HashStrategy:
    """哈希策略."""
    
    @staticmethod
    def compute_sha256(data: Union[str, bytes]) -> str:
        """计算 SHA256 哈希.
        
        Args:
            data: 数据
            
        Returns:
            str: SHA256 哈希值（64字符十六进制）
        """
        if isinstance(data, str):
            data = data.encode('utf-8')
        return hashlib.sha256(data).hexdigest()
    
    @staticmethod
    def compute_md5(data: Union[str, bytes]) -> str:
        """计算 MD5 哈希（兼容旧版本）.
        
        Args:
            data: 数据
            
        Returns:
            str: MD5 哈希值（32字符十六进制）
        """
        if isinstance(data, str):
            data = data.encode('utf-8')
        return hashlib.md5(data).hexdigest()


class EnhancedCache:
    """增强型缓存.
    
    特性：
    - SHA256 哈希计算
    - 数据压缩支持
    - 多级缓存（内存 + 磁盘）
    - 数据完整性校验
    """
    
    def __init__(
        self,
        max_memory_size: int = 1000,
        max_disk_size: int = 10000,
        disk_cache_dir: Optional[Path] = None,
        compression_enabled: bool = True,
        compression_threshold: int = 1024,
        default_ttl: int = 3600,
    ):
        """初始化增强型缓存.
        
        Args:
            max_memory_size: 内存缓存最大条目数
            max_disk_size: 磁盘缓存最大条目数
            disk_cache_dir: 磁盘缓存目录
            compression_enabled: 是否启用压缩
            compression_threshold: 压缩阈值（字节）
            default_ttl: 默认 TTL（秒）
        """
        self.max_memory_size = max_memory_size
        self.max_disk_size = max_disk_size
        self.compression_enabled = compression_enabled
        self.compression_threshold = compression_threshold
        self.default_ttl = default_ttl
        
        # L1: 内存缓存
        self._memory_cache: OrderedDict[str, Any] = OrderedDict()
        self._memory_metadata: Dict[str, CacheMetadata] = {}
        
        # L2: 磁盘缓存
        self._disk_cache_dir = disk_cache_dir or Path.cwd() / ".cache" / "enhanced"
        self._disk_cache_dir.mkdir(parents=True, exist_ok=True)
        self._disk_metadata: Dict[str, CacheMetadata] = {}
        
        # 统计信息
        self._memory_hits = 0
        self._memory_misses = 0
        self._disk_hits = 0
        self._disk_misses = 0
        
        # 锁
        self._lock = threading.RLock()
        
        # 加载磁盘缓存索引
        self._load_disk_index()
        
        logger.info(f"EnhancedCache initialized: memory={max_memory_size}, disk={max_disk_size}")
    
    def _load_disk_index(self) -> None:
        """加载磁盘缓存索引."""
        index_file = self._disk_cache_dir / "index.json"
        if not index_file.exists():
            return
        
        try:
            with open(index_file, 'r', encoding='utf-8') as f:
                index_data = json.load(f)
            
            for key, meta_dict in index_data.items():
                self._disk_metadata[key] = CacheMetadata(
                    key=key,
                    created_at=datetime.fromisoformat(meta_dict['created_at']),
                    expires_at=datetime.fromisoformat(meta_dict['expires_at']) if meta_dict.get('expires_at') else None,
                    size_bytes=meta_dict['size_bytes'],
                    compressed=meta_dict.get('compressed', False),
                    checksum=meta_dict.get('checksum', ''),
                    access_count=meta_dict.get('access_count', 0),
                    last_accessed=datetime.fromisoformat(meta_dict['last_accessed']) if meta_dict.get('last_accessed') else None,
                )
        except Exception as e:
            logger.warning(f"Failed to load disk cache index: {e}")
    
    def _save_disk_index(self) -> None:
        """保存磁盘缓存索引."""
        index_file = self._disk_cache_dir / "index.json"
        
        index_data = {}
        for key, meta in self._disk_metadata.items():
            index_data[key] = {
                'created_at': meta.created_at.isoformat(),
                'expires_at': meta.expires_at.isoformat() if meta.expires_at else None,
                'size_bytes': meta.size_bytes,
                'compressed': meta.compressed,
                'checksum': meta.checksum,
                'access_count': meta.access_count,
                'last_accessed': meta.last_accessed.isoformat() if meta.last_accessed else None,
            }
        
        with open(index_file, 'w', encoding='utf-8') as f:
            json.dump(index_data, f, indent=2)
    
    def _get_disk_cache_path(self, key: str) -> Path:
        """获取磁盘缓存文件路径.
        
        Args:
            key: 缓存键
            
        Returns:
            Path: 缓存文件路径
        """
        # 使用 SHA256 生成安全的文件名
        safe_name = HashStrategy.compute_sha256(key)
        return self._disk_cache_dir / f"{safe_name}.cache"
    
    def _serialize(self, value: Any) -> bytes:
        """序列化值.
        
        Args:
            value: 值
            
        Returns:
            bytes: 序列化后的数据
        """
        return pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)
    
    def _deserialize(self, data: bytes) -> Any:
        """反序列化数据.
        
        Args:
            data: 数据
            
        Returns:
            Any: 反序列化后的值
        """
        return pickle.loads(data)
    
    def _compress_if_needed(self, data: bytes) -> Tuple[bytes, bool]:
        """根据需要压缩数据.
        
        Args:
            data: 原始数据
            
        Returns:
            Tuple[bytes, bool]: (处理后的数据, 是否压缩)
        """
        if self.compression_enabled and CompressionStrategy.should_compress(data, self.compression_threshold):
            compressed = CompressionStrategy.compress(data)
            if len(compressed) < len(data):
                return compressed, True
        return data, False
    
    def _decompress_if_needed(self, data: bytes, compressed: bool) -> bytes:
        """根据需要解压数据.
        
        Args:
            data: 数据
            compressed: 是否压缩
            
        Returns:
            bytes: 解压后的数据
        """
        if compressed:
            return CompressionStrategy.decompress(data)
        return data
    
    def _compute_checksum(self, data: bytes) -> str:
        """计算数据校验和.
        
        Args:
            data: 数据
            
        Returns:
            str: SHA256 校验和
        """
        return HashStrategy.compute_sha256(data)
    
    def _verify_checksum(self, data: bytes, expected_checksum: str) -> bool:
        """验证数据校验和.
        
        Args:
            data: 数据
            expected_checksum: 期望的校验和
            
        Returns:
            bool: 校验是否通过
        """
        if not expected_checksum:
            return True
        actual_checksum = self._compute_checksum(data)
        return actual_checksum == expected_checksum
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存值.
        
        Args:
            key: 缓存键
            
        Returns:
            Optional[Any]: 缓存值
        """
        with self._lock:
            # 先检查内存缓存
            if key in self._memory_cache:
                meta = self._memory_metadata[key]
                
                # 检查是否过期
                if meta.expires_at and datetime.now() > meta.expires_at:
                    self._remove_from_memory(key)
                    self._memory_misses += 1
                    return None
                
                # 更新访问信息
                meta.access_count += 1
                meta.last_accessed = datetime.now()
                self._memory_cache.move_to_end(key)
                self._memory_hits += 1
                
                logger.debug(f"Memory cache hit: {key}")
                return self._memory_cache[key]
            
            # 再检查磁盘缓存
            if key in self._disk_metadata:
                meta = self._disk_metadata[key]
                
                # 检查是否过期
                if meta.expires_at and datetime.now() > meta.expires_at:
                    self._remove_from_disk(key)
                    self._disk_misses += 1
                    return None
                
                # 从磁盘加载
                cache_path = self._get_disk_cache_path(key)
                if cache_path.exists():
                    try:
                        with open(cache_path, 'rb') as f:
                            data = f.read()
                        
                        # 验证校验和
                        if not self._verify_checksum(data, meta.checksum):
                            logger.warning(f"Checksum mismatch for key: {key}")
                            self._remove_from_disk(key)
                            self._disk_misses += 1
                            return None
                        
                        # 解压
                        data = self._decompress_if_needed(data, meta.compressed)
                        
                        # 反序列化
                        value = self._deserialize(data)
                        
                        # 更新访问信息
                        meta.access_count += 1
                        meta.last_accessed = datetime.now()
                        self._disk_hits += 1
                        
                        # 提升到内存缓存
                        self._promote_to_memory(key, value, meta)
                        
                        logger.debug(f"Disk cache hit: {key}")
                        return value
                        
                    except Exception as e:
                        logger.warning(f"Failed to load from disk cache: {e}")
                        self._remove_from_disk(key)
            
            self._memory_misses += 1
            self._disk_misses += 1
            return None
    
    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        store_on_disk: bool = False,
    ) -> None:
        """设置缓存值.
        
        Args:
            key: 缓存键
            value: 缓存值
            ttl: TTL（秒）
            store_on_disk: 是否存储到磁盘
        """
        ttl = ttl if ttl is not None else self.default_ttl
        expires_at = datetime.now() + timedelta(seconds=ttl) if ttl > 0 else None
        
        with self._lock:
            # 存入内存缓存
            self._add_to_memory(key, value, expires_at)
            
            # 如果需要，存入磁盘缓存
            if store_on_disk:
                self._add_to_disk(key, value, expires_at)
    
    def _add_to_memory(self, key: str, value: Any, expires_at: Optional[datetime]) -> None:
        """添加到内存缓存."""
        # 检查是否需要淘汰
        if len(self._memory_cache) >= self.max_memory_size and key not in self._memory_cache:
            self._evict_from_memory()
        
        # 序列化计算大小
        data = self._serialize(value)
        
        self._memory_cache[key] = value
        self._memory_metadata[key] = CacheMetadata(
            key=key,
            created_at=datetime.now(),
            expires_at=expires_at,
            size_bytes=len(data),
        )
        self._memory_cache.move_to_end(key)
    
    def _add_to_disk(self, key: str, value: Any, expires_at: Optional[datetime]) -> None:
        """添加到磁盘缓存."""
        # 检查是否需要淘汰
        if len(self._disk_metadata) >= self.max_disk_size and key not in self._disk_metadata:
            self._evict_from_disk()
        
        try:
            # 序列化
            data = self._serialize(value)
            
            # 压缩
            data, compressed = self._compress_if_needed(data)
            
            # 计算校验和
            checksum = self._compute_checksum(data)
            
            # 保存到磁盘
            cache_path = self._get_disk_cache_path(key)
            with open(cache_path, 'wb') as f:
                f.write(data)
            
            # 更新元数据
            self._disk_metadata[key] = CacheMetadata(
                key=key,
                created_at=datetime.now(),
                expires_at=expires_at,
                size_bytes=len(data),
                compressed=compressed,
                checksum=checksum,
            )
            
            # 保存索引
            self._save_disk_index()
            
        except Exception as e:
            logger.warning(f"Failed to save to disk cache: {e}")
    
    def _promote_to_memory(self, key: str, value: Any, disk_meta: CacheMetadata) -> None:
        """将磁盘缓存提升到内存缓存."""
        self._add_to_memory(key, value, disk_meta.expires_at)
    
    def _remove_from_memory(self, key: str) -> None:
        """从内存缓存移除."""
        if key in self._memory_cache:
            del self._memory_cache[key]
        if key in self._memory_metadata:
            del self._memory_metadata[key]
    
    def _remove_from_disk(self, key: str) -> None:
        """从磁盘缓存移除."""
        cache_path = self._get_disk_cache_path(key)
        if cache_path.exists():
            cache_path.unlink()
        if key in self._disk_metadata:
            del self._disk_metadata[key]
        self._save_disk_index()
    
    def _evict_from_memory(self) -> None:
        """从内存缓存淘汰."""
        if not self._memory_cache:
            return
        
        # LRU 淘汰
        oldest_key = next(iter(self._memory_cache))
        self._remove_from_memory(oldest_key)
        logger.debug(f"Evicted from memory: {oldest_key}")
    
    def _evict_from_disk(self) -> None:
        """从磁盘缓存淘汰."""
        if not self._disk_metadata:
            return
        
        # 淘汰最少访问的
        lru_key = min(
            self._disk_metadata.keys(),
            key=lambda k: (self._disk_metadata[k].last_accessed or datetime.min, self._disk_metadata[k].access_count)
        )
        self._remove_from_disk(lru_key)
        logger.debug(f"Evicted from disk: {lru_key}")
    
    def delete(self, key: str) -> bool:
        """删除缓存.
        
        Args:
            key: 缓存键
            
        Returns:
            bool: 是否成功删除
        """
        with self._lock:
            removed = False
            
            if key in self._memory_cache:
                self._remove_from_memory(key)
                removed = True
            
            if key in self._disk_metadata:
                self._remove_from_disk(key)
                removed = True
            
            return removed
    
    def clear(self) -> None:
        """清空所有缓存."""
        with self._lock:
            # 清空内存
            self._memory_cache.clear()
            self._memory_metadata.clear()
            
            # 清空磁盘
            for key in list(self._disk_metadata.keys()):
                self._remove_from_disk(key)
            
            # 重置统计
            self._memory_hits = 0
            self._memory_misses = 0
            self._disk_hits = 0
            self._disk_misses = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息.
        
        Returns:
            Dict[str, Any]: 统计信息
        """
        with self._lock:
            memory_total = self._memory_hits + self._memory_misses
            disk_total = self._disk_hits + self._disk_misses
            
            return {
                "memory": {
                    "size": len(self._memory_cache),
                    "max_size": self.max_memory_size,
                    "hits": self._memory_hits,
                    "misses": self._memory_misses,
                    "hit_rate": self._memory_hits / memory_total if memory_total > 0 else 0.0,
                },
                "disk": {
                    "size": len(self._disk_metadata),
                    "max_size": self.max_disk_size,
                    "hits": self._disk_hits,
                    "misses": self._disk_misses,
                    "hit_rate": self._disk_hits / disk_total if disk_total > 0 else 0.0,
                },
                "compression": {
                    "enabled": self.compression_enabled,
                    "threshold": self.compression_threshold,
                },
            }
    
    def cleanup_expired(self) -> int:
        """清理过期缓存.
        
        Returns:
            int: 清理的条目数
        """
        count = 0
        now = datetime.now()
        
        with self._lock:
            # 清理内存
            expired_memory = [
                key for key, meta in self._memory_metadata.items()
                if meta.expires_at and now > meta.expires_at
            ]
            for key in expired_memory:
                self._remove_from_memory(key)
                count += 1
            
            # 清理磁盘
            expired_disk = [
                key for key, meta in self._disk_metadata.items()
                if meta.expires_at and now > meta.expires_at
            ]
            for key in expired_disk:
                self._remove_from_disk(key)
                count += 1
        
        return count
