"""LLM 缓存测试"""

import time
from unittest import mock

import pytest
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatResult, ChatGeneration

from ut_agent.utils.llm_cache import (
    LLMCache,
    LLMRetryHandler,
    CachedLLM,
    get_cached_llm,
    clear_llm_cache,
    get_llm_cache_size,
)
from ut_agent.exceptions import LLMRateLimitError, RetryableError


class TestLLMCache:
    """测试 LLM 缓存"""
    
    def test_initialization(self):
        """测试初始化"""
        cache = LLMCache(max_size=100, ttl_seconds=60)
        assert cache._max_size == 100
        assert cache._ttl_seconds == 60
    
    def test_compute_cache_key(self):
        """测试计算缓存键"""
        cache = LLMCache()
        
        key1 = cache._compute_cache_key("test prompt", "openai", "gpt-4", 0.7)
        key2 = cache._compute_cache_key("test prompt", "openai", "gpt-4", 0.7)
        key3 = cache._compute_cache_key("different prompt", "openai", "gpt-4", 0.7)
        
        assert key1 == key2
        assert key1 != key3
        assert len(key1) == 64  # SHA-256 哈希长度
    
    def test_set_and_get(self):
        """测试设置和获取缓存"""
        cache = LLMCache()
        
        result = ChatResult(
            generations=[ChatGeneration(message=AIMessage(content="test response"))],
            llm_output={},
        )
        
        cache.set("test prompt", "openai", "gpt-4", 0.7, result)
        
        cached = cache.get("test prompt", "openai", "gpt-4", 0.7)
        assert cached is not None
        assert cached.generations[0].message.content == "test response"
    
    def test_get_nonexistent(self):
        """测试获取不存在的缓存"""
        cache = LLMCache()
        
        cached = cache.get("nonexistent", "openai", "gpt-4", 0.7)
        assert cached is None
    
    def test_cache_expiration(self):
        """测试缓存过期"""
        cache = LLMCache(ttl_seconds=1)
        
        result = ChatResult(
            generations=[ChatGeneration(message=AIMessage(content="test"))],
            llm_output={},
        )
        
        cache.set("test prompt", "openai", "gpt-4", 0.7, result)
        
        # 手动设置缓存为过期（时间戳设为很久以前）
        key = cache._compute_cache_key("test prompt", "openai", "gpt-4", 0.7)
        cache._cache[key]["timestamp"] = time.time() - 100
        
        cached = cache.get("test prompt", "openai", "gpt-4", 0.7)
        assert cached is None
    
    def test_max_size_eviction(self):
        """测试最大容量驱逐"""
        cache = LLMCache(max_size=2)
        
        result1 = ChatResult(
            generations=[ChatGeneration(message=AIMessage(content="response1"))],
            llm_output={},
        )
        result2 = ChatResult(
            generations=[ChatGeneration(message=AIMessage(content="response2"))],
            llm_output={},
        )
        result3 = ChatResult(
            generations=[ChatGeneration(message=AIMessage(content="response3"))],
            llm_output={},
        )
        
        cache.set("prompt1", "openai", "gpt-4", 0.7, result1)
        cache.set("prompt2", "openai", "gpt-4", 0.7, result2)
        cache.set("prompt3", "openai", "gpt-4", 0.7, result3)
        
        # 第一个缓存应该被驱逐
        assert cache.get("prompt1", "openai", "gpt-4", 0.7) is None
        assert cache.get("prompt2", "openai", "gpt-4", 0.7) is not None
        assert cache.get("prompt3", "openai", "gpt-4", 0.7) is not None
    
    def test_clear(self):
        """测试清空缓存"""
        cache = LLMCache()
        
        result = ChatResult(
            generations=[ChatGeneration(message=AIMessage(content="test"))],
            llm_output={},
        )
        
        cache.set("test", "openai", "gpt-4", 0.7, result)
        assert cache.size() == 1
        
        cache.clear()
        assert cache.size() == 0
    
    def test_size(self):
        """测试获取缓存大小"""
        cache = LLMCache()
        assert cache.size() == 0
        
        result = ChatResult(
            generations=[ChatGeneration(message=AIMessage(content="test"))],
            llm_output={},
        )
        
        cache.set("test1", "openai", "gpt-4", 0.7, result)
        assert cache.size() == 1
        
        cache.set("test2", "openai", "gpt-4", 0.7, result)
        assert cache.size() == 2


class TestLLMRetryHandler:
    """测试 LLM 重试处理器"""
    
    def test_initialization(self):
        """测试初始化"""
        handler = LLMRetryHandler(max_retries=3, base_delay=1.0, max_delay=10.0)
        assert handler._max_retries == 3
        assert handler._base_delay == 1.0
        assert handler._max_delay == 10.0
    
    def test_successful_call(self):
        """测试成功调用"""
        handler = LLMRetryHandler(max_retries=3)
        
        @handler.retry_with_backoff
        def success_func():
            return "success"
        
        result = success_func()
        assert result == "success"
    
    def test_retry_on_rate_limit(self):
        """测试速率限制重试"""
        handler = LLMRetryHandler(max_retries=2, base_delay=0.1, max_delay=1.0)
        
        call_count = 0
        
        @handler.retry_with_backoff
        def rate_limited_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise LLMRateLimitError("Rate limit exceeded")
            return "success"
        
        result = rate_limited_func()
        assert result == "success"
        assert call_count == 3
    
    def test_max_retries_exceeded(self):
        """测试超过最大重试次数"""
        handler = LLMRetryHandler(max_retries=1, base_delay=0.1, max_delay=1.0)
        
        @handler.retry_with_backoff
        def always_fail():
            raise LLMRateLimitError("Rate limit exceeded")
        
        with pytest.raises(LLMRateLimitError):
            always_fail()
    
    def test_non_retryable_error(self):
        """测试不可重试错误"""
        handler = LLMRetryHandler(max_retries=3)
        
        @handler.retry_with_backoff
        def raise_value_error():
            raise ValueError("Not retryable")
        
        with pytest.raises(ValueError):
            raise_value_error()


class TestCachedLLM:
    """测试缓存 LLM 包装器"""
    
    def test_initialization(self):
        """测试初始化"""
        mock_llm = mock.MagicMock()
        cache = LLMCache()
        
        cached_llm = CachedLLM(mock_llm, cache)
        assert cached_llm._llm == mock_llm
        assert cached_llm._cache == cache
    
    def test_invoke_with_cache_hit(self):
        """测试缓存命中调用"""
        mock_llm = mock.MagicMock()
        mock_llm.model_name = "gpt-4"
        mock_llm._provider = "openai"
        
        cache = LLMCache()
        cached_result = ChatResult(
            generations=[ChatGeneration(message=AIMessage(content="cached response"))],
            llm_output={},
        )
        
        cache.set("test prompt", "openai", "gpt-4", 0.7, cached_result)
        
        cached_llm = CachedLLM(mock_llm, cache)
        
        messages = [mock.MagicMock(content="test prompt")]
        result = cached_llm.invoke(messages, temperature=0.7)
        
        # 应该返回缓存的结果，不调用 LLM
        assert result.generations[0].message.content == "cached response"
        mock_llm.invoke.assert_not_called()
    
    def test_invoke_with_cache_miss(self):
        """测试缓存未命中调用"""
        mock_result = ChatResult(
            generations=[ChatGeneration(message=AIMessage(content="new response"))],
            llm_output={},
        )
        
        mock_llm = mock.MagicMock()
        mock_llm.model_name = "gpt-4"
        mock_llm._provider = "openai"
        mock_llm.invoke.return_value = mock_result
        
        cache = LLMCache()
        cached_llm = CachedLLM(mock_llm, cache)
        
        messages = [mock.MagicMock(content="new prompt")]
        result = cached_llm.invoke(messages, temperature=0.7)
        
        assert result.generations[0].message.content == "new response"
        mock_llm.invoke.assert_called_once()
        
        # 验证结果被缓存
        cached = cache.get("new prompt", "openai", "gpt-4", 0.7)
        assert cached is not None
    
    def test_get_cache(self):
        """测试获取缓存实例"""
        mock_llm = mock.MagicMock()
        cache = LLMCache()
        
        cached_llm = CachedLLM(mock_llm, cache)
        assert cached_llm.get_cache() == cache


class TestGlobalFunctions:
    """测试全局函数"""
    
    def test_get_cached_llm(self):
        """测试获取缓存 LLM"""
        mock_llm = mock.MagicMock()
        
        cached_llm = get_cached_llm(mock_llm)
        assert isinstance(cached_llm, CachedLLM)
        assert cached_llm._llm == mock_llm
    
    def test_clear_llm_cache(self):
        """测试清空全局缓存"""
        # 先添加一些缓存
        from ut_agent.utils.llm_cache import _llm_cache
        
        result = ChatResult(
            generations=[ChatGeneration(message=AIMessage(content="test"))],
            llm_output={},
        )
        _llm_cache.set("test", "openai", "gpt-4", 0.7, result)
        
        assert get_llm_cache_size() == 1
        
        clear_llm_cache()
        
        assert get_llm_cache_size() == 0
    
    def test_get_llm_cache_size(self):
        """测试获取全局缓存大小"""
        clear_llm_cache()
        
        assert get_llm_cache_size() == 0
        
        from ut_agent.utils.llm_cache import _llm_cache
        
        result = ChatResult(
            generations=[ChatGeneration(message=AIMessage(content="test"))],
            llm_output={},
        )
        _llm_cache.set("test", "openai", "gpt-4", 0.7, result)
        
        assert get_llm_cache_size() == 1
        
        clear_llm_cache()


if __name__ == "__main__":
    pytest.main([__file__])
