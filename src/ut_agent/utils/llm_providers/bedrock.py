"""AWS Bedrock LLM 提供商."""

import os
import json
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Dict, List, Optional, Union
import asyncio

try:
    import boto3
    from botocore.exceptions import ClientError
    BEDROCK_AVAILABLE = True
except ImportError:
    BEDROCK_AVAILABLE = False


@dataclass
class BedrockConfig:
    """Bedrock 配置."""
    
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_session_token: Optional[str] = None
    use_iam_role: bool = False
    region: str = "us-east-1"
    model_id: str = "anthropic.claude-3-sonnet-20240229-v1:0"
    max_tokens: int = 4096
    temperature: float = 0.7
    
    @classmethod
    def from_env(cls) -> "BedrockConfig":
        """从环境变量创建配置."""
        return cls(
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            aws_session_token=os.getenv("AWS_SESSION_TOKEN"),
            use_iam_role=os.getenv("BEDROCK_USE_IAM_ROLE", "false").lower() == "true",
            region=os.getenv("AWS_REGION", "us-east-1"),
            model_id=os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-sonnet-20240229-v1:0"),
            max_tokens=int(os.getenv("BEDROCK_MAX_TOKENS", "4096")),
            temperature=float(os.getenv("BEDROCK_TEMPERATURE", "0.7"))
        )


class BedrockProvider:
    """AWS Bedrock LLM 提供商."""
    
    # 支持的模型列表
    SUPPORTED_MODELS = [
        "anthropic.claude-3-opus-20240229-v1:0",
        "anthropic.claude-3-sonnet-20240229-v1:0",
        "anthropic.claude-3-haiku-20240307-v1:0",
        "meta.llama3-70b-instruct-v1:0",
        "meta.llama3-8b-instruct-v1:0",
        "mistral.mistral-large-2402-v1:0",
        "mistral.mixtral-8x7b-instruct-v0:1",
        "amazon.titan-text-express-v1",
    ]
    
    # 模型定价 (每 1K tokens)
    PRICING = {
        "anthropic.claude-3-opus-20240229-v1:0": {"input": 0.015, "output": 0.075},
        "anthropic.claude-3-sonnet-20240229-v1:0": {"input": 0.003, "output": 0.015},
        "anthropic.claude-3-haiku-20240307-v1:0": {"input": 0.00025, "output": 0.00125},
        "meta.llama3-70b-instruct-v1:0": {"input": 0.00265, "output": 0.0035},
        "meta.llama3-8b-instruct-v1:0": {"input": 0.0003, "output": 0.0006},
        "mistral.mistral-large-2402-v1:0": {"input": 0.004, "output": 0.012},
        "mistral.mixtral-8x7b-instruct-v0:1": {"input": 0.0004, "output": 0.0005},
        "amazon.titan-text-express-v1": {"input": 0.0002, "output": 0.0006},
    }
    
    def __init__(self, config: BedrockConfig):
        """初始化 Bedrock 提供商.
        
        Args:
            config: Bedrock 配置
        """
        self.config = config
        self._client: Optional[Any] = None
        
        if BEDROCK_AVAILABLE:
            self._init_client()
    
    def _init_client(self):
        """初始化 Bedrock 客户端."""
        if self.config.use_iam_role:
            # 使用 IAM 角色
            self._client = boto3.client(
                service_name="bedrock-runtime",
                region_name=self.config.region
            )
        elif self.config.aws_access_key_id and self.config.aws_secret_access_key:
            # 使用访问密钥
            session_kwargs = {
                "aws_access_key_id": self.config.aws_access_key_id,
                "aws_secret_access_key": self.config.aws_secret_access_key,
            }
            if self.config.aws_session_token:
                session_kwargs["aws_session_token"] = self.config.aws_session_token
            
            session = boto3.Session(**session_kwargs)
            self._client = session.client(
                service_name="bedrock-runtime",
                region_name=self.config.region
            )
    
    @property
    def name(self) -> str:
        """提供商名称."""
        return "bedrock"
    
    def _get_model_family(self) -> str:
        """获取模型家族.
        
        Returns:
            str: 模型家族 (claude, llama, mistral, titan)
        """
        model_id = self.config.model_id.lower()
        if "claude" in model_id:
            return "claude"
        elif "llama" in model_id:
            return "llama"
        elif "mistral" in model_id:
            return "mistral"
        elif "titan" in model_id:
            return "titan"
        return "unknown"
    
    def _format_messages(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """格式化消息为 Bedrock 格式.
        
        Args:
            messages: 消息列表
            
        Returns:
            Dict[str, Any]: 格式化后的请求体
        """
        model_family = self._get_model_family()
        
        if model_family == "claude":
            return self._format_claude_messages(messages)
        elif model_family == "llama":
            return self._format_llama_messages(messages)
        elif model_family == "mistral":
            return self._format_mistral_messages(messages)
        elif model_family == "titan":
            return self._format_titan_messages(messages)
        else:
            # 默认使用 Claude 格式
            return self._format_claude_messages(messages)
    
    def _format_claude_messages(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """格式化为 Claude 消息格式."""
        system_message = ""
        formatted_messages = []
        
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role == "system":
                system_message = content
            elif role == "user":
                formatted_messages.append({"role": "user", "content": content})
            elif role == "assistant":
                formatted_messages.append({"role": "assistant", "content": content})
        
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            "messages": formatted_messages
        }
        
        if system_message:
            body["system"] = system_message
        
        return body
    
    def _format_llama_messages(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """格式化为 Llama 消息格式."""
        prompt = ""
        
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role == "system":
                prompt += f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n{content}<|eot_id|>"
            elif role == "user":
                prompt += f"<|start_header_id|>user<|end_header_id|>\n\n{content}<|eot_id|>"
            elif role == "assistant":
                prompt += f"<|start_header_id|>assistant<|end_header_id|>\n\n{content}<|eot_id|>"
        
        prompt += "<|start_header_id|>assistant<|end_header_id|>\n\n"
        
        return {
            "prompt": prompt,
            "max_gen_len": self.config.max_tokens,
            "temperature": self.config.temperature,
        }
    
    def _format_mistral_messages(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """格式化为 Mistral 消息格式."""
        prompt = ""
        
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role == "system":
                prompt += f"<s>[INST] {content} [/INST]"
            elif role == "user":
                prompt += f"[INST] {content} [/INST]"
            elif role == "assistant":
                prompt += f" {content} </s>"
        
        return {
            "prompt": prompt,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
        }
    
    def _format_titan_messages(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """格式化为 Titan 消息格式."""
        input_text = ""
        
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role == "system":
                input_text += f"System: {content}\n"
            elif role == "user":
                input_text += f"User: {content}\n"
            elif role == "assistant":
                input_text += f"Assistant: {content}\n"
        
        input_text += "Assistant:"
        
        return {
            "inputText": input_text,
            "textGenerationConfig": {
                "maxTokenCount": self.config.max_tokens,
                "temperature": self.config.temperature,
            }
        }
    
    def _parse_response(self, response_body: Dict[str, Any]) -> str:
        """解析响应体.
        
        Args:
            response_body: 响应体
            
        Returns:
            str: 生成的文本
        """
        model_family = self._get_model_family()
        
        if model_family == "claude":
            return response_body.get("content", [{}])[0].get("text", "")
        elif model_family == "llama":
            return response_body.get("generation", "")
        elif model_family == "mistral":
            return response_body.get("outputs", [{}])[0].get("text", "")
        elif model_family == "titan":
            return response_body.get("results", [{}])[0].get("outputText", "")
        
        return str(response_body)
    
    async def _call_api(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        **kwargs
    ) -> str:
        """调用 Bedrock API.
        
        Args:
            messages: 消息列表
            temperature: 温度参数
            **kwargs: 其他参数
            
        Returns:
            str: 生成的文本
        """
        if not BEDROCK_AVAILABLE:
            raise ImportError("boto3 package is required. Install with: pip install boto3")
        
        if not self._client:
            raise ValueError("Bedrock client not initialized. Check AWS credentials.")
        
        body = self._format_messages(messages)
        if temperature is not None:
            body["temperature"] = temperature
        
        response = self._client.invoke_model(
            body=json.dumps(body),
            modelId=self.config.model_id,
            accept="application/json",
            contentType="application/json"
        )
        
        response_body = json.loads(response.get("body").read())
        return self._parse_response(response_body)
    
    async def _call_api_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """流式调用 Bedrock API.
        
        Args:
            messages: 消息列表
            temperature: 温度参数
            **kwargs: 其他参数
            
        Yields:
            str: 生成的文本块
        """
        if not BEDROCK_AVAILABLE:
            raise ImportError("boto3 package is required. Install with: pip install boto3")
        
        if not self._client:
            raise ValueError("Bedrock client not initialized. Check AWS credentials.")
        
        body = self._format_messages(messages)
        if temperature is not None:
            body["temperature"] = temperature
        
        response = self._client.invoke_model_with_response_stream(
            body=json.dumps(body),
            modelId=self.config.model_id,
            accept="application/json",
            contentType="application/json"
        )
        
        for event in response.get("body"):
            chunk = json.loads(event["chunk"]["bytes"])
            
            model_family = self._get_model_family()
            text = ""
            
            if model_family == "claude":
                text = chunk.get("delta", {}).get("text", "")
            elif model_family == "llama":
                text = chunk.get("generation", "")
            elif model_family == "mistral":
                text = chunk.get("outputs", [{}])[0].get("text", "")
            
            if text:
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
                error_str = str(e).lower()
                # 检查是否是限流错误
                if "throttling" in error_str or "ratelimit" in error_str or "429" in str(e):
                    if attempt < max_retries - 1:
                        delay = 2 ** attempt  # 指数退避
                        await asyncio.sleep(delay)
                    continue
                # 认证错误不重试
                if "accessdenied" in error_str or "401" in str(e) or "403" in str(e):
                    raise
                # 其他错误
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
                    continue
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
        pricing = self.PRICING.get(
            self.config.model_id,
            {"input": 0.003, "output": 0.015}
        )
        
        input_cost = (input_tokens / 1000) * pricing["input"]
        output_cost = (output_tokens / 1000) * pricing["output"]
        
        return input_cost + output_cost
    
    def get_supported_models(self) -> List[str]:
        """获取支持的模型列表.
        
        Returns:
            List[str]: 模型 ID 列表
        """
        return self.SUPPORTED_MODELS.copy()
    
    @staticmethod
    def validate_config(config: BedrockConfig) -> bool:
        """验证配置.
        
        Args:
            config: 配置对象
            
        Returns:
            bool: 配置是否有效
        """
        # 使用 IAM 角色
        if config.use_iam_role:
            return bool(config.region)
        # 使用访问密钥
        return bool(config.aws_access_key_id) and bool(config.aws_secret_access_key)
