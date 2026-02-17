"""配置管理模块单元测试."""

import os
import tempfile
from pathlib import Path

import pytest

from ut_agent.config import Settings, settings


class TestSettings:
    """Settings 配置类测试."""

    def test_default_values(self):
        """测试默认值."""
        # 创建新的 Settings 实例以获取默认值
        s = Settings()

        assert s.openai_model == "gpt-4o"
        assert s.deepseek_base_url == "https://api.deepseek.com"
        assert s.deepseek_model == "deepseek-chat"
        assert s.ollama_base_url == "http://localhost:11434"
        assert s.ollama_model == "qwen2.5-coder:14b"
        assert s.default_llm_provider == "openai"
        assert s.max_iterations == 10
        assert s.temperature == 0.2
        assert s.default_coverage_target == 80.0

    def test_optional_api_keys(self):
        """测试可选 API 密钥."""
        s = Settings()

        # API 密钥应该是可选的 (None)
        assert s.openai_api_key is None
        assert s.deepseek_api_key is None

    def test_settings_singleton(self):
        """测试 settings 单例."""
        # 验证 settings 是一个 Settings 实例
        assert isinstance(settings, Settings)

    def test_model_config(self):
        """测试模型配置."""
        s = Settings()

        # 验证配置允许额外字段
        assert s.model_config.get("extra") == "ignore"
        assert s.model_config.get("env_file") == ".env"


class TestSettingsFromEnv:
    """从环境变量加载配置测试."""

    def test_load_from_env_vars(self, monkeypatch):
        """测试从环境变量加载配置."""
        # 设置环境变量
        monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
        monkeypatch.setenv("OPENAI_MODEL", "gpt-4")
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek-key")
        monkeypatch.setenv("OLLAMA_MODEL", "codellama")
        monkeypatch.setenv("DEFAULT_LLM_PROVIDER", "deepseek")
        monkeypatch.setenv("MAX_ITERATIONS", "5")
        monkeypatch.setenv("TEMPERATURE", "0.5")
        monkeypatch.setenv("DEFAULT_COVERAGE_TARGET", "90.0")

        # 创建新的 Settings 实例
        s = Settings()

        assert s.openai_api_key == "test-openai-key"
        assert s.openai_model == "gpt-4"
        assert s.deepseek_api_key == "test-deepseek-key"
        assert s.ollama_model == "codellama"
        assert s.default_llm_provider == "deepseek"
        assert s.max_iterations == 5
        assert s.temperature == 0.5
        assert s.default_coverage_target == 90.0

    def test_load_from_env_file(self):
        """测试从 .env 文件加载配置."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建临时的 .env 文件
            env_file = Path(tmpdir) / ".env"
            env_content = """
OPENAI_API_KEY=file-api-key
OPENAI_MODEL=gpt-3.5-turbo
MAX_ITERATIONS=15
TEMPERATURE=0.1
"""
            env_file.write_text(env_content)

            # 创建 Settings 实例，指定 env_file
            original_cwd = Path.cwd()
            try:
                import os

                os.chdir(tmpdir)
                s = Settings(_env_file=str(env_file))

                assert s.openai_api_key == "file-api-key"
                assert s.openai_model == "gpt-3.5-turbo"
                assert s.max_iterations == 15
                assert s.temperature == 0.1
            finally:
                os.chdir(original_cwd)

    def test_env_var_priority_over_defaults(self, monkeypatch):
        """测试环境变量优先于默认值."""
        monkeypatch.setenv("OPENAI_MODEL", "custom-model")
        monkeypatch.setenv("MAX_ITERATIONS", "20")

        s = Settings()

        assert s.openai_model == "custom-model"
        assert s.max_iterations == 20

    def test_temperature_parsing(self, monkeypatch):
        """测试 temperature 浮点数解析."""
        monkeypatch.setenv("TEMPERATURE", "0.75")

        s = Settings()

        assert s.temperature == 0.75

    def test_coverage_target_parsing(self, monkeypatch):
        """测试覆盖率目标浮点数解析."""
        monkeypatch.setenv("DEFAULT_COVERAGE_TARGET", "85.5")

        s = Settings()

        assert s.default_coverage_target == 85.5


class TestSettingsValidation:
    """配置验证测试."""

    def test_max_iterations_type(self, monkeypatch):
        """测试 max_iterations 类型."""
        monkeypatch.setenv("MAX_ITERATIONS", "invalid")

        # pydantic 应该抛出验证错误
        with pytest.raises(Exception):
            Settings()

    def test_temperature_range(self, monkeypatch):
        """测试 temperature 范围."""
        # 测试边界值
        monkeypatch.setenv("TEMPERATURE", "0")
        s = Settings()
        assert s.temperature == 0.0

        monkeypatch.setenv("TEMPERATURE", "2")
        s = Settings()
        assert s.temperature == 2.0

    def test_coverage_target_range(self, monkeypatch):
        """测试覆盖率目标范围."""
        monkeypatch.setenv("DEFAULT_COVERAGE_TARGET", "0")
        s = Settings()
        assert s.default_coverage_target == 0.0

        monkeypatch.setenv("DEFAULT_COVERAGE_TARGET", "100")
        s = Settings()
        assert s.default_coverage_target == 100.0


class TestSettingsEdgeCases:
    """配置边界情况测试."""

    def test_empty_env_values(self, monkeypatch):
        """测试空环境变量值."""
        monkeypatch.setenv("OPENAI_API_KEY", "")

        s = Settings()
        assert s.openai_api_key == ""

    def test_whitespace_in_env_values(self, monkeypatch):
        """测试环境变量值中的空白字符."""
        monkeypatch.setenv("OPENAI_MODEL", "  gpt-4  ")

        s = Settings()
        # pydantic-settings 会保留字符串值
        assert s.openai_model == "  gpt-4  "

    def test_special_characters_in_api_key(self, monkeypatch):
        """测试 API 密钥中的特殊字符."""
        special_key = "sk-test_key.with+special=chars"
        monkeypatch.setenv("OPENAI_API_KEY", special_key)

        s = Settings()
        assert s.openai_api_key == special_key

    def test_url_with_trailing_slash(self, monkeypatch):
        """测试带斜杠的 URL."""
        monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/")

        s = Settings()
        assert s.deepseek_base_url == "https://api.deepseek.com/"

    def test_localhost_url(self, monkeypatch):
        """测试 localhost URL."""
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")

        s = Settings()
        assert s.ollama_base_url == "http://127.0.0.1:11434"


class TestCACertPath:
    """CA 证书路径配置测试."""

    def test_ca_cert_path_default_none(self):
        """测试 CA 证书路径默认为 None."""
        s = Settings()
        assert s.ca_cert_path is None

    def test_ca_cert_path_from_env(self, monkeypatch, tmp_path):
        """测试从环境变量加载 CA 证书路径."""
        cert_file = tmp_path / "ca.pem"
        cert_file.write_text("fake cert content")

        monkeypatch.setenv("CA_CERT_PATH", str(cert_file))
        s = Settings()
        assert s.ca_cert_path == str(cert_file)

    def test_ca_cert_path_empty_string(self, monkeypatch):
        """测试空字符串 CA 证书路径转为 None."""
        monkeypatch.setenv("CA_CERT_PATH", "")
        s = Settings()
        assert s.ca_cert_path is None

    def test_ca_cert_path_relative_path_invalid(self, monkeypatch):
        """测试相对路径 CA 证书无效."""
        monkeypatch.setenv("CA_CERT_PATH", "relative/path/ca.pem")

        with pytest.raises(Exception):
            Settings()

    def test_ca_cert_path_nonexistent_file_invalid(self, monkeypatch):
        """测试不存在的 CA 证书文件无效."""
        monkeypatch.setenv("CA_CERT_PATH", "/nonexistent/path/ca.pem")

        with pytest.raises(Exception):
            Settings()


class TestPrivateLLMConfig:
    """私有 LLM 配置测试."""

    def test_private_llm_default_values(self):
        """测试私有 LLM 默认值."""
        s = Settings()
        assert s.private_llm_base_url is None
        assert s.private_llm_api_key is None
        assert s.private_llm_model == "default"

    def test_private_llm_from_env(self, monkeypatch):
        """测试从环境变量加载私有 LLM 配置."""
        monkeypatch.setenv("PRIVATE_LLM_BASE_URL", "https://internal-llm.company.com/v1")
        monkeypatch.setenv("PRIVATE_LLM_MODEL", "company-model-v1")
        monkeypatch.setenv("PRIVATE_LLM_API_KEY", "test-key")

        s = Settings()
        assert s.private_llm_base_url == "https://internal-llm.company.com/v1"
        assert s.private_llm_model == "company-model-v1"
        assert s.private_llm_api_key == "test-key"

    def test_private_llm_without_api_key(self, monkeypatch):
        """测试私有 LLM 无 API Key 场景."""
        monkeypatch.setenv("PRIVATE_LLM_BASE_URL", "https://internal-llm.company.com/v1")
        monkeypatch.setenv("PRIVATE_LLM_API_KEY", "")

        s = Settings()
        assert s.private_llm_base_url == "https://internal-llm.company.com/v1"
        assert s.private_llm_api_key is None or s.private_llm_api_key == ""

    def test_private_llm_invalid_url(self, monkeypatch):
        """测试私有 LLM 无效 URL."""
        monkeypatch.setenv("PRIVATE_LLM_BASE_URL", "invalid-url")

        with pytest.raises(Exception):
            Settings()
