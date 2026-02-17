"""Anthropic Claude LLM 提供商."""

import os
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Dict, List, Optional, Union
import asyncio

try:
    import anthropic
    from anthropic import AsyncAnthropic, RateLimitError, APIError
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


@dataclass
class ClaudeConfig:
    """Claude 配置."""
    
    api_key: str = ""
    model: str = "claude-3-sonnet-20240229"
    max_tokens: int = 4096
    temperature: float = 0.7
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    
    @classmethod
    def from_env(cls) -> "ClaudeConfig":
        """从环境变量创建配置."""
        return cls(
            api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            model=os.getenv("CLAUDE_MODEL", "claude-3-sonnet-20240229"),
            max_tokens=int(os.getenv("CLAUDE_MAX_TOKENS", "4096")),
            temperature=float(os.getenv("CLAUDE_TEMPERATURE", "0.7"))
        )


class ClaudeProvider:
    """Anthropic Claude LLM 提供商."""
    
    # 模型定价 (每 1K tokens)
    PRICING = {
        "claude-3-opus-20240229": {"input": 0.015, "output": 0.075},
        "claude-3-sonnet-20240229": {"input": 0.003, "output": 0.015},
        "claude-3-haiku-20240307": {"input": 0.00025, "output": 0.00125},
    }
    
    def __init__(self, config: ClaudeConfig):
        """初始化 Claude 提供商.
        
        Args:
            config: Claude 配置
        """
        self.config = config
        self._client: Optional[AsyncAnthropic] = None
        
        if ANTHROPIC_AVAILABLE and config.api_key:
            self._client = AsyncAnthropic(api_key=config.api_key)
    
    @property
    def name(self) -> str:
        """提供商名称."""
        return "claude"
    
    def _format_messages(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """格式化消息为 Claude 格式.
        
        Args:
            messages: 消息列表
            
        Returns:
            Dict[str, Any]: 格式化后的消息
        """
        system_message = ""
        formatted_messages = []
        
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role == "system":
                system_message = content
            else:
                formatted_messages.append({
                    "role": role,
                    "content": content
                })
        
        result = {"messages": formatted_messages}
        if system_message:
            result["system"] = system_message
        
        return result
    
    async def _call_api(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        **kwargs
    ) -> str:
        """调用 Claude API.
        
        Args:
            messages: 消息列表
            temperature: 温度参数
            **kwargs: 其他参数
            
        Returns:
            str: 生成的文本
        """
        if not ANTHROPIC_AVAILABLE:
            raise ImportError("anthropic package is required. Install with: pip install anthropic")
        
        if not self._client:
            raise ValueError("Claude client not initialized. Check API key.")
        
        formatted = self._format_messages(messages)
        
        response = await self._client.messages.create(
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            temperature=temperature or self.config.temperature,
            top_p=self.config.top_p if self.config.top_p else kwargs.get("top_p"),
            top_k=self.config.top_k if self.config.top_k else kwargs.get("top_k"),
            system=formatted.get("system", ""),
            messages=formatted["messages"]
        )
        
        return response.content[0].text
    
    async def _call_api_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """流式调用 Claude API.
        
        Args:
            messages: 消息列表
            temperature: 温度参数
            **kwargs: 其他参数
            
        Yields:
            str: 生成的文本块
        """
        if not ANTHROPIC_AVAILABLE:
            raise ImportError("anthropic package is required. Install with: pip install anthropic")
        
        if not self._client:
            raise ValueError("Claude client not initialized. Check API key.")
        
        formatted = self._format_messages(messages)
        
        async with self._client.messages.stream(
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            temperature=temperature or self.config.temperature,
            top_p=self.config.top_p if self.config.top_p else kwargs.get("top_p"),
            top_k=self.config.top_k if self.config.top_k else kwargs.get("top_k"),
            system=formatted.get("system", ""),
            messages=formatted["messages"]
        ) as stream:
            async for text in stream.text_stream:
                yield text
    
    async def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_retries: int = 3,
        **kwargs
    ) -> Union[str, Dict[str, Any]]:
        """生成文本.
        
        Args:
            messages: 消息列表
            temperature: 温度参数
            max_retries: 最大重试次数
            **kwargs: 其他参数
            
        Returns:
            Union[str, Dict[str, Any]]: 生成的文本或结构化结果
        """
        last_error = None
        
        for attempt in range(max_retries):
            try:
                return await self._call_api(messages, temperature, **kwargs)
            except Exception as e:
                last_error = e
                # 检查是否是速率限制错误
                if "RateLimitError" in type(e).__name__ or "rate limit" in str(e).lower():
                    if attempt < max_retries - 1:
                        delay = 2 ** attempt  # 指数退避
                        await asyncio.sleep(delay)
                    continue
                # 其他 API 错误
                if "APIError" in type(e).__name__ or "api" in str(e).lower():
                    if attempt < max_retries - 1:
                        await asyncio.sleep(1)
                    continue
                # 未知错误，直接抛出
                raise
        
        raise last_error or Exception("Failed to generate after retries")
    
    async def generate_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """流式生成文本.
        
        Args:
            messages: 消息列表
            temperature: 温度参数
            **kwargs: 其他参数
            
        Yields:
            str: 生成的文本块
        """
        async for chunk in self._call_api_stream(messages, temperature, **kwargs):
            yield chunk
    
    def count_tokens(self, text: str) -> int:
        """估算 Token 数量.
        
        Args:
            text: 文本
            
        Returns:
            int: Token 数量
        """
        # 简单估算：平均每 4 个字符一个 token
        return len(text) // 4 + 1
    
    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """估算成本.
        
        Args:
            input_tokens: 输入 token 数
            output_tokens: 输出 token 数
            
        Returns:
            float: 成本（美元）
        """
        pricing = self.PRICING.get(self.config.model, {"input": 0.003, "output": 0.015})
        
        input_cost = (input_tokens / 1000) * pricing["input"]
        output_cost = (output_tokens / 1000) * pricing["output"]
        
        return input_cost + output_cost
    
    @staticmethod
    def validate_config(config: ClaudeConfig) -> bool:
        """验证配置.
        
        Args:
            config: 配置对象
            
        Returns:
            bool: 配置是否有效
        """
        return bool(config.api_key)
