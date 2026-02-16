"""LLM 调用缓存和重试机制."""

import hashlib
import json
import time
from functools import wraps
from typing import Any, Dict, Optional, Callable, TypeVar, cast
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatResult
from ut_agent.exceptions import LLMError, LLMRateLimitError, RetryableError
from ut_agent.utils import get_logger

logger = get_logger("llm_cache")


T = TypeVar('T')


class LLMCache:
    """LLM 调用缓存."""

    def __init__(self, max_size: Optional[int] = None, ttl_seconds: Optional[int] = None):
        """初始化 LLM 缓存.

        Args:
            max_size: 最大缓存条目数
            ttl_seconds: 缓存过期时间（秒）
        """
        from ut_agent.config import settings
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._max_size = max_size or settings.llm_cache_max_size
        self._ttl_seconds = ttl_seconds or settings.llm_cache_ttl

    def _compute_cache_key(
        self, prompt: str, provider: str, model: str, temperature: float
    ) -> str:
        """计算缓存键.

        Args:
            prompt: 提示文本
            provider: LLM 提供商
            model: 模型名称
            temperature: 温度参数

        Returns:
            str: 缓存键
        """
        key_data = {
            "prompt": prompt,
            "provider": provider,
            "model": model,
            "temperature": temperature,
        }
        key_str = json.dumps(key_data, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(key_str.encode()).hexdigest()

    def get(
        self, prompt: str, provider: str, model: str, temperature: float
    ) -> Optional[ChatResult]:
        """获取缓存结果.

        Args:
            prompt: 提示文本
            provider: LLM 提供商
            model: 模型名称
            temperature: 温度参数

        Returns:
            Optional[ChatResult]: 缓存的聊天结果
        """
        key = self._compute_cache_key(prompt, provider, model, temperature)
        if key not in self._cache:
            return None

        entry = self._cache[key]
        if time.time() - entry["timestamp"] > self._ttl_seconds:
            del self._cache[key]
            return None

        logger.debug(f"LLM cache hit for prompt: {prompt[:50]}...")
        return cast(ChatResult, entry["result"])

    def set(
        self, 
        prompt: str, 
        provider: str, 
        model: str, 
        temperature: float, 
        result: ChatResult
    ) -> None:
        """设置缓存结果.

        Args:
            prompt: 提示文本
            provider: LLM 提供商
            model: 模型名称
            temperature: 温度参数
            result: 聊天结果
        """
        if len(self._cache) >= self._max_size:
            # 清理最旧的缓存
            oldest_key = min(
                self._cache.keys(),
                key=lambda k: self._cache[k]["timestamp"]
            )
            del self._cache[oldest_key]

        key = self._compute_cache_key(prompt, provider, model, temperature)
        self._cache[key] = {
            "result": result,
            "timestamp": time.time(),
        }
        logger.debug(f"LLM cache set for prompt: {prompt[:50]}...")

    def clear(self) -> None:
        """清空缓存."""
        self._cache.clear()

    def size(self) -> int:
        """获取缓存大小.

        Returns:
            int: 缓存条目数
        """
        return len(self._cache)


class LLMRetryHandler:
    """LLM 调用重试处理器."""

    def __init__(self, max_retries: Optional[int] = None, base_delay: Optional[float] = None, max_delay: Optional[float] = None):
        """初始化重试处理器.

        Args:
            max_retries: 最大重试次数
            base_delay: 基础延迟（秒）
            max_delay: 最大延迟（秒）
        """
        from ut_agent.config import settings
        self._max_retries = max_retries or settings.llm_max_retries
        self._base_delay = base_delay or settings.llm_retry_base_delay
        self._max_delay = max_delay or settings.llm_max_retry_delay

    def retry_with_backoff(self, func: Callable[..., T]) -> Callable[..., T]:
        """带退避策略的重试装饰器.

        Args:
            func: 要装饰的函数

        Returns:
            Callable[..., T]: 装饰后的函数
        """
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Optional[Exception] = None

            for attempt in range(self._max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except LLMRateLimitError as e:
                    last_exception = e
                    retry_after = getattr(e, "details", {}).get("retry_after", None)
                    if retry_after:
                        delay = retry_after
                    else:
                        delay = min(self._base_delay * (2 ** attempt), self._max_delay)

                    if attempt < self._max_retries:
                        logger.warning(
                            f"Rate limit hit, retrying in {delay:.2f}s (attempt {attempt + 1}/{self._max_retries})")
                        time.sleep(delay)
                    else:
                        logger.error(f"Max retries reached for rate limit: {e}")
                        raise
                except RetryableError as e:
                    last_exception = e
                    if e.should_retry():
                        delay = min(self._base_delay * (2 ** attempt), self._max_delay)
                        logger.warning(
                            f"Retryable error, retrying in {delay:.2f}s (attempt {attempt + 1}/{self._max_retries})")
                        time.sleep(delay)
                    else:
                        logger.error(f"Max retries reached: {e}")
                        raise
                except Exception as e:
                    # 其他异常不重试
                    raise

            if last_exception:
                raise last_exception

            raise RuntimeError("Retry wrapper reached unreachable code")

        return wrapper


class CachedLLM:
    """带缓存和重试的 LLM 包装器."""

    def __init__(self, llm: BaseChatModel, cache: Optional[LLMCache] = None):
        """初始化缓存 LLM.

        Args:
            llm: 原始 LLM 实例
            cache: LLM 缓存实例
        """
        self._llm = llm
        self._cache = cache or LLMCache()
        self._retry_handler = LLMRetryHandler()

    def invoke(
        self, 
        messages: list[BaseMessage], 
        **kwargs: Any
    ) -> ChatResult:
        """调用 LLM 并缓存结果.

        Args:
            messages: 消息列表
            **kwargs: 其他参数

        Returns:
            ChatResult: 聊天结果
        """
        from ut_agent.utils.metrics import llm_call, record_cache_operation
        # 构建提示文本
        prompt_parts = []
        for msg in messages:
            if hasattr(msg, "content"):
                content = msg.content
                if isinstance(content, str):
                    prompt_parts.append(content)
                elif isinstance(content, (list, dict)):
                    # 处理复杂类型的content
                    try:
                        import json
                        prompt_parts.append(json.dumps(content, ensure_ascii=False))
                    except:
                        prompt_parts.append(str(content))
                else:
                    prompt_parts.append(str(content))
        prompt = "\n".join(prompt_parts)
        provider = getattr(self._llm, "_provider", "unknown")
        model = getattr(self._llm, "model_name", "unknown")
        temperature = kwargs.get("temperature", 0.7)

        # 检查缓存
        cached_result = self._cache.get(prompt, provider, model, temperature)
        if cached_result:
            record_cache_operation("llm", "get", hit=True)
            return cached_result
        else:
            record_cache_operation("llm", "get", hit=False)

        # 调用 LLM 带重试
        @self._retry_handler.retry_with_backoff
        def call_llm() -> ChatResult:
            with llm_call(provider, model):
                return cast(ChatResult, self._llm.invoke(messages, **kwargs))

        result = call_llm()

        # 缓存结果
        self._cache.set(prompt, provider, model, temperature, result)
        record_cache_operation("llm", "set")

        return result

    def get_cache(self) -> LLMCache:
        """获取缓存实例.

        Returns:
            LLMCache: 缓存实例
        """
        return self._cache


# 全局 LLM 缓存实例
_llm_cache = LLMCache()


def get_cached_llm(llm: BaseChatModel) -> CachedLLM:
    """获取带缓存的 LLM 实例.

    Args:
        llm: 原始 LLM 实例

    Returns:
        CachedLLM: 带缓存的 LLM 实例
    """
    return CachedLLM(llm, _llm_cache)


def clear_llm_cache() -> None:
    """清空全局 LLM 缓存.
    """
    global _llm_cache
    _llm_cache.clear()
    logger.info("LLM cache cleared")


def get_llm_cache_size() -> int:
    """获取全局 LLM 缓存大小.

    Returns:
        int: 缓存条目数
    """
    global _llm_cache
    return _llm_cache.size()
