"""语义缓存.

基于语义相似度的智能缓存系统，支持通过向量相似度匹配语义相近的查询。
"""

import asyncio
import hashlib
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Set
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class SimilarityConfig:
    """相似度配置.
    
    Attributes:
        threshold: 相似度阈值（0-1）
        top_k: 返回的最大结果数
        use_faiss: 是否使用FAISS加速（如果可用）
    """
    threshold: float = 0.85
    top_k: int = 5
    use_faiss: bool = False


@dataclass
class SemanticCacheEntry:
    """语义缓存项.
    
    Attributes:
        query: 查询文本
        response: 响应内容
        embedding: 查询的向量嵌入
        metadata: 元数据
        created_at: 创建时间
        last_access_time: 最后访问时间
        access_count: 访问次数
    """
    query: str
    response: str
    embedding: np.ndarray
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    last_access_time: Optional[datetime] = None
    access_count: int = 0
    
    def record_access(self) -> None:
        """记录访问."""
        self.access_count += 1
        self.last_access_time = datetime.now()
        
    def calculate_similarity(self, embedding: np.ndarray) -> float:
        """计算与给定嵌入的相似度.
        
        Args:
            embedding: 要比较的嵌入向量
            
        Returns:
            float: 余弦相似度（-1 到 1）
        """
        # 归一化向量
        norm1 = np.linalg.norm(self.embedding)
        norm2 = np.linalg.norm(embedding)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
            
        # 计算余弦相似度
        similarity = np.dot(self.embedding, embedding) / (norm1 * norm2)
        return float(similarity)
        
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "query": self.query,
            "response": self.response,
            "embedding": self.embedding.tolist(),
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "last_access_time": self.last_access_time.isoformat() if self.last_access_time else None,
            "access_count": self.access_count,
        }


class EmbeddingProvider(ABC):
    """嵌入提供者抽象基类."""
    
    @abstractmethod
    async def get_embedding(self, text: str) -> np.ndarray:
        """获取文本的嵌入向量.
        
        Args:
            text: 输入文本
            
        Returns:
            np.ndarray: 嵌入向量
        """
        pass
        
    @abstractmethod
    async def get_embeddings_batch(self, texts: List[str]) -> List[np.ndarray]:
        """批量获取嵌入向量.
        
        Args:
            texts: 输入文本列表
            
        Returns:
            List[np.ndarray]: 嵌入向量列表
        """
        pass


class SimpleEmbeddingProvider(EmbeddingProvider):
    """简单嵌入提供者.
    
    使用哈希和随机投影生成固定维度的嵌入向量。
    适用于测试和轻量级场景，不保证语义相似性。
    """
    
    def __init__(self, dimension: int = 384, seed: int = 42):
        self.dimension = dimension
        self.seed = seed
        self._projection_matrix: Optional[np.ndarray] = None
        self._cache: Dict[str, np.ndarray] = {}
        
    def _get_projection_matrix(self) -> np.ndarray:
        """获取投影矩阵（延迟初始化）."""
        if self._projection_matrix is None:
            np.random.seed(self.seed)
            self._projection_matrix = np.random.randn(768, self.dimension)
        return self._projection_matrix
        
    def _text_to_vector(self, text: str) -> np.ndarray:
        """将文本转换为向量."""
        # 使用字符n-gram特征
        features = np.zeros(768)
        text = text.lower().strip()
        
        # 字符级特征
        for i, char in enumerate(text):
            idx = ord(char) % 256
            features[idx] += 1
            
        # 词级特征
        words = text.split()
        for word in words:
            # 使用单词哈希
            hash_val = int(hashlib.md5(word.encode()).hexdigest(), 16)
            idx = (hash_val % 512) + 256
            features[idx] += 1
            
        return features
        
    async def get_embedding(self, text: str) -> np.ndarray:
        """获取文本的嵌入向量."""
        # 检查缓存
        cache_key = hashlib.md5(text.encode()).hexdigest()
        if cache_key in self._cache:
            return self._cache[cache_key]
            
        # 生成嵌入
        features = self._text_to_vector(text)
        projection = self._get_projection_matrix()
        embedding = np.dot(features, projection)
        
        # 归一化
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm
            
        # 缓存结果
        self._cache[cache_key] = embedding
        return embedding
        
    async def get_embeddings_batch(self, texts: List[str]) -> List[np.ndarray]:
        """批量获取嵌入向量."""
        embeddings = []
        for text in texts:
            embedding = await self.get_embedding(text)
            embeddings.append(embedding)
        return embeddings


class SemanticCache:
    """语义缓存.
    
    基于向量相似度的智能缓存系统。
    
    Attributes:
        embedding_provider: 嵌入提供者
        max_size: 最大缓存大小
        similarity_threshold: 相似度阈值
        config: 相似度配置
    """
    
    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        max_size: int = 1000,
        similarity_threshold: float = 0.85,
        config: Optional[SimilarityConfig] = None,
    ):
        self.embedding_provider = embedding_provider
        self.max_size = max_size
        self.similarity_threshold = similarity_threshold
        self.config = config or SimilarityConfig()
        
        # 缓存存储
        self._cache: Dict[str, SemanticCacheEntry] = {}
        self._query_to_key: Dict[str, str] = {}  # 查询文本到缓存键的映射
        
        # 统计信息
        self._hit_count = 0
        self._miss_count = 0
        self._eviction_count = 0
        
        # 锁
        self._lock = asyncio.Lock()
        
        # 后台任务
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False
        
        logger.info(f"SemanticCache initialized with max_size={max_size}, threshold={similarity_threshold}")
        
    async def start(self) -> None:
        """启动缓存."""
        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("SemanticCache started")
        
    async def stop(self) -> None:
        """停止缓存."""
        self._running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        logger.info("SemanticCache stopped")
        
    async def _cleanup_loop(self) -> None:
        """后台清理循环."""
        while self._running:
            try:
                await asyncio.sleep(300)  # 每5分钟清理一次
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("Cleanup loop error")
                
    def _generate_key(self, query: str) -> str:
        """生成缓存键."""
        return hashlib.md5(query.encode()).hexdigest()
        
    async def store(
        self,
        query: str,
        response: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """存储缓存项.
        
        Args:
            query: 查询文本
            response: 响应内容
            metadata: 元数据
            
        Returns:
            str: 缓存键
        """
        metadata = metadata or {}
        
        # 生成嵌入
        embedding = await self.embedding_provider.get_embedding(query)
        
        async with self._lock:
            # 检查是否需要淘汰
            if len(self._cache) >= self.max_size:
                await self._evict_entry()
                
            # 创建缓存项
            key = self._generate_key(query)
            entry = SemanticCacheEntry(
                query=query,
                response=response,
                embedding=embedding,
                metadata=metadata,
            )
            
            self._cache[key] = entry
            self._query_to_key[query] = key
            
        logger.debug(f"Stored semantic cache: {query[:50]}...")
        return key
        
    async def retrieve(
        self,
        query: str,
        threshold: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """检索缓存.
        
        Args:
            query: 查询文本
            threshold: 相似度阈值（覆盖默认阈值）
            
        Returns:
            Optional[Dict]: 缓存结果，包含response、similarity、metadata
        """
        threshold = threshold or self.similarity_threshold
        
        # 生成查询嵌入
        query_embedding = await self.embedding_provider.get_embedding(query)
        
        async with self._lock:
            best_match = None
            best_similarity = threshold
            
            # 遍历所有缓存项查找最相似的
            for key, entry in self._cache.items():
                similarity = entry.calculate_similarity(query_embedding)
                
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = entry
                    
            if best_match:
                best_match.record_access()
                self._hit_count += 1
                
                return {
                    "query": best_match.query,
                    "response": best_match.response,
                    "similarity": best_similarity,
                    "metadata": best_match.metadata,
                }
            else:
                self._miss_count += 1
                return None
                
    async def _evict_entry(self) -> None:
        """执行缓存淘汰."""
        if not self._cache:
            return
            
        # 找到访问次数最少且最旧的项
        min_score = float('inf')
        key_to_evict = None
        
        for key, entry in self._cache.items():
            # 热键保护
            if entry.access_count >= 20:
                continue
                
            # 计算淘汰分数（访问次数越少、越久未访问，分数越低）
            time_factor = 1.0
            if entry.last_access_time:
                time_since_access = (datetime.now() - entry.last_access_time).total_seconds()
                time_factor = max(0.1, 1.0 - time_since_access / 3600)
                
            score = entry.access_count * time_factor
            
            if score < min_score:
                min_score = score
                key_to_evict = key
                
        if key_to_evict:
            entry = self._cache.pop(key_to_evict)
            if entry.query in self._query_to_key:
                del self._query_to_key[entry.query]
            self._eviction_count += 1
            logger.debug(f"Evicted semantic cache entry: {entry.query[:50]}...")
            
    async def delete(self, query: str) -> bool:
        """删除缓存项.
        
        Args:
            query: 查询文本
            
        Returns:
            bool: 是否成功删除
        """
        async with self._lock:
            key = self._query_to_key.get(query)
            if key and key in self._cache:
                del self._cache[key]
                del self._query_to_key[query]
                logger.debug(f"Deleted semantic cache: {query[:50]}...")
                return True
            return False
            
    async def clear(self) -> None:
        """清空缓存."""
        async with self._lock:
            self._cache.clear()
            self._query_to_key.clear()
            
        logger.info("SemanticCache cleared")
        
    async def store_batch(
        self,
        items: List[Tuple[str, str, Optional[Dict[str, Any]]]],
    ) -> List[str]:
        """批量存储缓存项.
        
        Args:
            items: (query, response, metadata) 元组列表
            
        Returns:
            List[str]: 缓存键列表
        """
        keys = []
        for item in items:
            query, response, metadata = item
            key = await self.store(query, response, metadata or {})
            keys.append(key)
        return keys
        
    async def get_similar_queries(
        self,
        query: str,
        top_k: int = 5,
        threshold: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """获取相似查询.
        
        Args:
            query: 查询文本
            top_k: 返回的最大结果数
            threshold: 相似度阈值
            
        Returns:
            List[Dict]: 相似查询列表
        """
        threshold = threshold or self.similarity_threshold
        query_embedding = await self.embedding_provider.get_embedding(query)
        
        async with self._lock:
            matches = []
            
            for key, entry in self._cache.items():
                similarity = entry.calculate_similarity(query_embedding)
                
                if similarity >= threshold:
                    matches.append({
                        "query": entry.query,
                        "response": entry.response,
                        "similarity": similarity,
                        "metadata": entry.metadata,
                    })
                    
            # 按相似度排序
            matches.sort(key=lambda x: x["similarity"], reverse=True)
            
            return matches[:top_k]
            
    async def update_metadata(
        self,
        query: str,
        metadata: Dict[str, Any],
    ) -> bool:
        """更新缓存项的元数据.
        
        Args:
            query: 查询文本
            metadata: 新元数据
            
        Returns:
            bool: 是否成功更新
        """
        async with self._lock:
            key = self._query_to_key.get(query)
            if key and key in self._cache:
                self._cache[key].metadata.update(metadata)
                return True
            return False
            
    @property
    def size(self) -> int:
        """获取当前缓存大小."""
        return len(self._cache)
        
    async def get_stats(self) -> Dict[str, Any]:
        """获取统计信息.
        
        Returns:
            Dict[str, Any]: 统计信息
        """
        total_requests = self._hit_count + self._miss_count
        hit_rate = self._hit_count / total_requests if total_requests > 0 else 0.0
        
        # 热键统计
        hot_keys = [k for k, e in self._cache.items() if e.access_count >= 10]
        
        return {
            "size": self.size,
            "max_size": self.max_size,
            "similarity_threshold": self.similarity_threshold,
            "hit_count": self._hit_count,
            "miss_count": self._miss_count,
            "hit_rate": round(hit_rate, 4),
            "eviction_count": self._eviction_count,
            "hot_key_count": len(hot_keys),
        }
        
    async def get_all_entries(self) -> List[SemanticCacheEntry]:
        """获取所有缓存项.
        
        Returns:
            List[SemanticCacheEntry]: 缓存项列表
        """
        async with self._lock:
            return list(self._cache.values())
