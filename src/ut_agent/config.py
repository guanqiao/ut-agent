"""配置管理模块."""

import os
import re
from typing import Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: Optional[str] = None
    openai_base_url: Optional[str] = None
    openai_model: str = "gpt-4o"

    deepseek_api_key: Optional[str] = None
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5-coder:14b"

    default_llm_provider: str = "openai"

    max_iterations: int = 10
    temperature: float = 0.2

    default_coverage_target: float = 80.0

    # 缓存配置
    llm_cache_max_size: int = 1000
    llm_cache_ttl: int = 3600
    ast_cache_max_size: int = 100 * 1024 * 1024
    ast_cache_ttl: int = 86400
    ast_cache_max_entries: int = 1000

    # 重试策略配置
    llm_max_retries: int = 3
    llm_retry_base_delay: float = 1.0
    llm_max_retry_delay: float = 30.0

    # 性能配置
    max_concurrent_threads: int = 0
    batch_processing_size: int = 10
    llm_timeout: int = 60

    # SSL/TLS 配置
    ca_cert_path: Optional[str] = None

    @field_validator("temperature")
    @classmethod
    def validate_temperature(cls, v: float) -> float:
        """验证 temperature 范围."""
        if not 0 <= v <= 2:
            raise ValueError("temperature 必须在 0 到 2 之间")
        return v

    @field_validator("default_coverage_target")
    @classmethod
    def validate_coverage_target(cls, v: float) -> float:
        """验证覆盖率目标范围."""
        if not 0 <= v <= 100:
            raise ValueError("覆盖率目标必须在 0 到 100 之间")
        return v

    @field_validator("openai_base_url", "deepseek_base_url", "ollama_base_url")
    @classmethod
    def validate_url(cls, v: Optional[str]) -> Optional[str]:
        """验证 URL 格式."""
        if v is None or v == "":
            return v
        url_pattern = re.compile(
            r"^https?://"
            r"(?:localhost|[\w-]+(?:\.[\w-]+)+)"
            r"(?::\d+)?"
            r"(?:/[\w./-]*)?$"
        )
        if not url_pattern.match(v):
            raise ValueError(f"无效的 URL 格式: {v}")
        return v

    @field_validator("max_iterations")
    @classmethod
    def validate_max_iterations(cls, v: int) -> int:
        """验证最大迭代次数."""
        if v < 1:
            raise ValueError("最大迭代次数必须大于 0")
        if v > 100:
            raise ValueError("最大迭代次数不能超过 100")
        return v

    @field_validator("llm_cache_max_size", "ast_cache_max_entries")
    @classmethod
    def validate_cache_size(cls, v: int) -> int:
        """验证缓存大小."""
        if v < 1:
            raise ValueError("缓存大小必须大于 0")
        return v

    @field_validator("llm_cache_ttl", "ast_cache_ttl", "llm_timeout")
    @classmethod
    def validate_timeout(cls, v: int) -> int:
        """验证超时时间."""
        if v < 0:
            raise ValueError("超时时间不能为负数")
        return v

    @field_validator("llm_retry_base_delay", "llm_max_retry_delay")
    @classmethod
    def validate_delay(cls, v: float) -> float:
        """验证延迟时间."""
        if v < 0:
            raise ValueError("延迟时间不能为负数")
        return v

    @field_validator("batch_processing_size")
    @classmethod
    def validate_batch_size(cls, v: int) -> int:
        """验证批处理大小."""
        if v < 1:
            raise ValueError("批处理大小必须大于 0")
        return v

    @field_validator("ca_cert_path")
    @classmethod
    def validate_ca_cert_path(cls, v: Optional[str]) -> Optional[str]:
        """验证 CA 证书路径."""
        if v is None or v == "":
            return None
        if not os.path.isabs(v):
            raise ValueError(f"CA 证书路径必须是绝对路径: {v}")
        if not os.path.isfile(v):
            raise ValueError(f"CA 证书文件不存在: {v}")
        return v


settings = Settings()
