"""缓存模块."""

from ut_agent.cache.adaptive_cache import (
    AdaptiveCache,
    CacheEntry,
    AccessPattern,
    CacheStrategy,
)
from ut_agent.cache.semantic_cache import (
    SemanticCache,
    SemanticCacheEntry,
    EmbeddingProvider,
    SimpleEmbeddingProvider,
    SimilarityConfig,
)

__all__ = [
    "AdaptiveCache",
    "CacheEntry",
    "AccessPattern",
    "CacheStrategy",
    "SemanticCache",
    "SemanticCacheEntry",
    "EmbeddingProvider",
    "SimpleEmbeddingProvider",
    "SimilarityConfig",
]
