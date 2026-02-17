"""Azure OpenAI LLM 提供商."""

import os
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Dict, List, Optional, Union
import asyncio

try:
    from openai import AsyncAzureOpenAI
    AZURE_OPENAI_AVAILABLE = True
except ImportError:
    AZURE_OPENAI_AVAILABLE = False


@dataclass
class AzureOpenAIConfig:
    """Azure OpenAI 配置."""
    
    api_key: str = ""
    endpoint: str = ""
    model: str = "gpt-4"
    deployment_name: Optional[str] = None
    api_version: str = "2024-02-01"
    max_tokens: int = 4096
    temperature: float = 0.7
    region: Optional[str] = None
    
    @classmethod
    def from_env(cls) -> "AzureOpenAIConfig":
        """从环境变量创建配置."""
        return cls(
            api_key=os.getenv("AZURE_OPENAI_API_KEY", ""),
            endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
            model=os.getenv("AZURE_OPENAI_MODEL", "gpt-4"),
            deployment_name=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01"),
            max_tokens=int(os.getenv("AZURE_OPENAI_MAX_TOKENS", "4096")),
            temperature=float(os.getenv("AZURE_OPENAI_TEMPERATURE", "0.7")),
            region=os.getenv("AZURE_OPENAI_REGION")
        )


class AzureOpenAIProvider:
    """Azure OpenAI LLM 提供商."""
    
    # 模型定价 (每 1K tokens)
    PRICING = {
        "gpt-4": {"input": 0.03, "output": 0.06},
        "gpt-4-turbo": {"input": 0.01, "output": 0.03},
        "gpt-4o": {"input": 0.005, "output": 0.015},
        "gpt-35-turbo": {"input": 0.0005, "output": 0.0015},
    }
    
    def __init__(self, config: AzureOpenAIConfig):
        """初始化 Azure OpenAI 提供商.
        
        Args:
            config: Azure OpenAI 配置
        """
        self.config = config
        self._client: Optional[Any] = None
        
        if AZURE_OPENAI_AVAILABLE and config.api_key and config.endpoint:
            self._client = AsyncAzureOpenAI(
                api_key=config.api_key,
                azure_endpoint=config.endpoint,
                api_version=config.api_version
            )
    
    @property
    def name(self) -> str:
        """提供商名称."""
        return "azure_openai"
    
    def _get_deployment_name(self) -> str:
        """获取部署名称.
        
        Returns:
            str: 部署名称
        """
        return self.config.deployment_name or self.config.model
    
    def _build_url(self) -> str:
        """构建 API URL.
        
        Returns:
            str: API URL
        """
        deployment = self._get_deployment_name()
        base_url = self.config.endpoint.rstrip('/')
        return f"{base_url}/openai/deployments/{deployment}/chat/completions?api-version={self.config.api_version}"
    
    async def _call_api(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        **kwargs
    ) -> str:
        """调用 Azure OpenAI API.
        
        Args:
            messages: 消息列表
            temperature: 温度参数
            **kwargs: 其他参数
            
        Returns:
            str: 生成的文本
        """
        if not AZURE_OPENAI_AVAILABLE:
            raise ImportError("openai package is required. Install with: pip install openai")
        
        if not self._client:
            raise ValueError("Azure OpenAI client not initialized. Check API key and endpoint.")
        
        deployment = self._get_deployment_name()
        
        response = await self._client.chat.completions.create(
            model=deployment,
            messages=messages,
            max_tokens=self.config.max_tokens,
            temperature=temperature or self.config.temperature,
            **kwargs
        )
        
        return response.choices[0].message.content
    
    async def _call_api_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """流式调用 Azure OpenAI API.
        
        Args:
            messages: 消息列表
            temperature: 温度参数
            **kwargs: 其他参数
            
        Yields:
            str: 生成的文本块
        """
        if not AZURE_OPENAI_AVAILABLE:
            raise ImportError("openai package is required. Install with: pip install openai")
        
        if not self._client:
            raise ValueError("Azure OpenAI client not initialized. Check API key and endpoint.")
        
        deployment = self._get_deployment_name()
        
        response = await self._client.chat.completions.create(
            model=deployment,
            messages=messages,
            max_tokens=self.config.max_tokens,
            temperature=temperature or self.config.temperature,
            stream=True,
            **kwargs
        )
        
        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    
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
                if "RateLimitError" in type(e).__name__ or "rate limit" in str(e).lower() or "429" in str(e):
                    if attempt < max_retries - 1:
                        delay = 2 ** attempt  # 指数退避
                        await asyncio.sleep(delay)
                    continue
                # 认证错误不重试
                if "AuthenticationError" in type(e).__name__ or "401" in str(e) or "403" in str(e):
                    raise
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
        pricing = self.PRICING.get(self.config.model, {"input": 0.03, "output": 0.06})
        
        input_cost = (input_tokens / 1000) * pricing["input"]
        output_cost = (output_tokens / 1000) * pricing["output"]
        
        return input_cost + output_cost
    
    @staticmethod
    def validate_config(config: AzureOpenAIConfig) -> bool:
        """验证配置.
        
        Args:
            config: 配置对象
            
        Returns:
            bool: 配置是否有效
        """
        return bool(config.api_key) and bool(config.endpoint)
