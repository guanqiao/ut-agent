"""Google Gemini LLM 提供商."""

import os
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Dict, List, Optional, Union
import asyncio

try:
    import google.generativeai as genai
    from google.generativeai import GenerativeModel
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False


@dataclass
class GeminiConfig:
    """Gemini 配置."""
    
    api_key: str = ""
    model: str = "gemini-1.5-flash"
    max_output_tokens: int = 2048
    temperature: float = 0.7
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    
    @classmethod
    def from_env(cls) -> "GeminiConfig":
        """从环境变量创建配置."""
        return cls(
            api_key=os.getenv("GOOGLE_API_KEY", ""),
            model=os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
            max_output_tokens=int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", "2048")),
            temperature=float(os.getenv("GEMINI_TEMPERATURE", "0.7"))
        )


class GeminiProvider:
    """Google Gemini LLM 提供商."""
    
    # 模型定价 (每 1K tokens)
    PRICING = {
        "gemini-1.5-pro": {"input": 0.0035, "output": 0.0105},
        "gemini-1.5-flash": {"input": 0.00035, "output": 0.00105},
        "gemini-1.0-pro": {"input": 0.0005, "output": 0.0015},
    }
    
    def __init__(self, config: GeminiConfig):
        """初始化 Gemini 提供商.
        
        Args:
            config: Gemini 配置
        """
        self.config = config
        self._model: Optional[Any] = None
        
        if GEMINI_AVAILABLE and config.api_key:
            genai.configure(api_key=config.api_key)
            self._model = genai.GenerativeModel(config.model)
    
    @property
    def name(self) -> str:
        """提供商名称."""
        return "gemini"
    
    def _format_messages(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """格式化消息为 Gemini 格式.
        
        Args:
            messages: 消息列表
            
        Returns:
            Dict[str, Any]: 格式化后的消息
        """
        contents = []
        system_instruction = None
        
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role == "system":
                system_instruction = content
            elif role == "user":
                contents.append({"role": "user", "parts": [content]})
            elif role == "assistant":
                contents.append({"role": "model", "parts": [content]})
        
        result = {"contents": contents}
        if system_instruction:
            result["system_instruction"] = system_instruction
        
        return result
    
    def _get_generation_config(self) -> Dict[str, Any]:
        """获取生成配置."""
        config = {
            "max_output_tokens": self.config.max_output_tokens,
            "temperature": self.config.temperature,
        }
        
        if self.config.top_p is not None:
            config["top_p"] = self.config.top_p
        if self.config.top_k is not None:
            config["top_k"] = self.config.top_k
        
        return config
    
    async def _call_api(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        **kwargs
    ) -> str:
        """调用 Gemini API.
        
        Args:
            messages: 消息列表
            temperature: 温度参数
            **kwargs: 其他参数
            
        Returns:
            str: 生成的文本
        """
        if not GEMINI_AVAILABLE:
            raise ImportError("google-generativeai package is required. Install with: pip install google-generativeai")
        
        if not self._model:
            raise ValueError("Gemini model not initialized. Check API key.")
        
        formatted = self._format_messages(messages)
        
        # 构建生成配置
        generation_config = self._get_generation_config()
        if temperature is not None:
            generation_config["temperature"] = temperature
        
        # 处理 system instruction
        if "system_instruction" in formatted:
            # Gemini 1.5 支持 system instruction
            response = await self._model.generate_content_async(
                formatted["contents"],
                generation_config=generation_config,
                system_instruction=formatted["system_instruction"]
            )
        else:
            response = await self._model.generate_content_async(
                formatted["contents"],
                generation_config=generation_config
            )
        
        return response.text
    
    async def _call_api_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """流式调用 Gemini API.
        
        Args:
            messages: 消息列表
            temperature: 温度参数
            **kwargs: 其他参数
            
        Yields:
            str: 生成的文本块
        """
        if not GEMINI_AVAILABLE:
            raise ImportError("google-generativeai package is required. Install with: pip install google-generativeai")
        
        if not self._model:
            raise ValueError("Gemini model not initialized. Check API key.")
        
        formatted = self._format_messages(messages)
        
        # 构建生成配置
        generation_config = self._get_generation_config()
        if temperature is not None:
            generation_config["temperature"] = temperature
        
        # 处理 system instruction
        if "system_instruction" in formatted:
            response = await self._model.generate_content_async(
                formatted["contents"],
                generation_config=generation_config,
                system_instruction=formatted["system_instruction"],
                stream=True
            )
        else:
            response = await self._model.generate_content_async(
                formatted["contents"],
                generation_config=generation_config,
                stream=True
            )
        
        async for chunk in response:
            if chunk.text:
                yield chunk.text
    
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
        pricing = self.PRICING.get(self.config.model, {"input": 0.00035, "output": 0.00105})
        
        input_cost = (input_tokens / 1000) * pricing["input"]
        output_cost = (output_tokens / 1000) * pricing["output"]
        
        return input_cost + output_cost
    
    @staticmethod
    def validate_config(config: GeminiConfig) -> bool:
        """验证配置.
        
        Args:
            config: 配置对象
            
        Returns:
            bool: 配置是否有效
        """
        return bool(config.api_key)
