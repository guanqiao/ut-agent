"""密钥安全存储测试."""

import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, Optional

from ut_agent.security.secure_storage import (
    SecureStorage,
    SecureStorageBackend,
    KeyringStorage,
    FileStorage,
    EnvStorage,
    EncryptedStorage,
    SecretKey,
    SecretType,
)


class TestSecretType:
    """密钥类型测试."""

    def test_secret_type_values(self):
        """测试密钥类型枚举值."""
        assert SecretType.API_KEY.value == "api_key"
        assert SecretType.PASSWORD.value == "password"
        assert SecretType.TOKEN.value == "token"
        assert SecretType.CERTIFICATE.value == "certificate"
        assert SecretType.CUSTOM.value == "custom"


class TestSecretKey:
    """密钥数据类测试."""

    def test_key_creation(self):
        """测试密钥创建."""
        key = SecretKey(
            name="openai_api_key",
            value="sk-test123",
            secret_type=SecretType.API_KEY,
        )
        
        assert key.name == "openai_api_key"
        assert key.value == "sk-test123"
        assert key.secret_type == SecretType.API_KEY
        assert key.metadata == {}
        
    def test_key_with_metadata(self):
        """测试带元数据的密钥."""
        key = SecretKey(
            name="azure_key",
            value="test-value",
            secret_type=SecretType.API_KEY,
            metadata={"provider": "azure", "region": "eastus"},
        )
        
        assert key.metadata["provider"] == "azure"
        assert key.metadata["region"] == "eastus"
        
    def test_key_masking(self):
        """测试密钥掩码显示."""
        key = SecretKey(
            name="test_key",
            value="super-secret-value",
            secret_type=SecretType.API_KEY,
        )
        
        masked = key.get_masked_value()
        
        assert "***" in masked
        assert "super-secret-value" not in masked


class TestSecureStorageBackend:
    """安全存储后端抽象测试."""

    def test_backend_interface(self):
        """测试后端接口定义."""
        # 抽象类不能直接实例化
        with pytest.raises(TypeError):
            SecureStorageBackend()


class TestKeyringStorage:
    """系统密钥环存储测试."""

    @pytest.fixture
    def storage(self):
        """创建密钥环存储实例."""
        # 跳过如果 keyring 未安装
        try:
            import keyring
        except ImportError:
            pytest.skip("keyring module not installed")
            
        with patch('keyring.set_password') as mock_set, \
             patch('keyring.get_password') as mock_get, \
             patch('keyring.delete_password') as mock_delete:
            
            mock_set.return_value = None
            mock_get.return_value = "stored-value"
            mock_delete.return_value = None
            
            yield KeyringStorage(service_name="ut-agent-test")

    def test_storage_initialization(self):
        """测试存储初始化."""
        storage = KeyringStorage(service_name="ut-agent")
        
        assert storage.service_name == "ut-agent"
        
    def test_store_secret(self, storage):
        """测试存储密钥."""
        result = storage.store("api_key", "secret-value")
        
        assert result is True
        
    def test_retrieve_secret(self, storage):
        """测试检索密钥."""
        storage.store("api_key", "secret-value")
        
        value = storage.retrieve("api_key")
        
        assert value == "stored-value"
        
    def test_delete_secret(self, storage):
        """测试删除密钥."""
        storage.store("api_key", "secret-value")
        
        result = storage.delete("api_key")
        
        assert result is True
        
    def test_retrieve_nonexistent(self, storage):
        """测试检索不存在的密钥."""
        with patch('keyring.get_password', return_value=None):
            value = storage.retrieve("nonexistent")
        
        assert value is None


class TestFileStorage:
    """文件存储测试."""

    @pytest.fixture
    def temp_dir(self):
        """创建临时目录."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
            
    @pytest.fixture
    def storage(self, temp_dir):
        """创建文件存储实例."""
        return FileStorage(base_path=temp_dir)

    def test_storage_initialization(self, temp_dir):
        """测试存储初始化."""
        storage = FileStorage(base_path=temp_dir)
        
        assert str(storage.base_path) == str(Path(temp_dir))
        assert os.path.exists(temp_dir)
        
    def test_store_and_retrieve(self, storage):
        """测试存储和检索."""
        storage.store("test_key", "test-value")
        
        value = storage.retrieve("test_key")
        
        assert value == "test-value"
        
    def test_delete(self, storage):
        """测试删除."""
        storage.store("test_key", "test-value")
        
        result = storage.delete("test_key")
        
        assert result is True
        assert storage.retrieve("test_key") is None
        
    def test_list_keys(self, storage):
        """测试列出所有密钥."""
        storage.store("key1", "value1")
        storage.store("key2", "value2")
        
        keys = storage.list_keys()
        
        assert "key1" in keys
        assert "key2" in keys


class TestEnvStorage:
    """环境变量存储测试."""

    @pytest.fixture
    def storage(self):
        """创建环境变量存储实例."""
        return EnvStorage(prefix="UT_AGENT")

    def test_storage_initialization(self):
        """测试存储初始化."""
        storage = EnvStorage(prefix="TEST")
        
        assert storage.prefix == "TEST"
        
    def test_store_and_retrieve(self, storage):
        """测试存储和检索."""
        with patch.dict(os.environ, {}, clear=True):
            storage.store("api_key", "secret123")
            
            value = storage.retrieve("api_key")
            
            assert value == "secret123"
            
    def test_retrieve_from_env(self, storage):
        """测试从环境变量检索."""
        with patch.dict(os.environ, {"UT_AGENT_API_KEY": "from-env"}):
            value = storage.retrieve("api_key")
            
            assert value == "from-env"
            
    def test_delete(self, storage):
        """测试删除."""
        with patch.dict(os.environ, {"UT_AGENT_KEY": "value"}, clear=True):
            result = storage.delete("key")
            
            assert result is True
            assert "UT_AGENT_KEY" not in os.environ


class TestEncryptedStorage:
    """加密存储测试."""

    @pytest.fixture(autouse=True)
    def check_cryptography(self):
        """检查 cryptography 是否安装."""
        try:
            from cryptography.fernet import Fernet
        except ImportError:
            pytest.skip("cryptography module not installed")

    @pytest.fixture
    def temp_dir(self):
        """创建临时目录."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
            
    @pytest.fixture
    def storage(self, temp_dir):
        """创建加密存储实例."""
        return EncryptedStorage(
            base_path=temp_dir,
            master_key="test-master-key-123",
        )

    def test_storage_initialization(self, temp_dir):
        """测试存储初始化."""
        storage = EncryptedStorage(
            base_path=temp_dir,
            master_key="master-key",
        )
        
        assert storage.base_path == temp_dir
        
    def test_store_and_retrieve(self, storage):
        """测试加密存储和检索."""
        storage.store("secret_key", "my-secret-value")
        
        value = storage.retrieve("secret_key")
        
        assert value == "my-secret-value"
        
    def test_encryption(self, storage):
        """测试加密效果."""
        storage.store("key", "value")
        
        # 读取原始文件内容，应该是加密的
        file_path = os.path.join(storage.base_path, "key.enc")
        with open(file_path, "rb") as f:
            encrypted_data = f.read()
            
        # 加密后的数据不应该包含原始值
        assert b"value" not in encrypted_data
        
    def test_delete(self, storage):
        """测试删除."""
        storage.store("key", "value")
        
        result = storage.delete("key")
        
        assert result is True
        assert storage.retrieve("key") is None


class TestSecureStorage:
    """安全存储管理器测试."""

    @pytest.fixture
    def storage(self):
        """创建安全存储实例."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 不使用 keyring，只用文件存储
            yield SecureStorage(
                keyring_service="ut-agent-test",
                file_path=tmpdir,
                use_keyring=False,
            )

    def test_initialization(self):
        """测试初始化."""
        storage = SecureStorage()
        
        assert storage is not None
        
    def test_store_api_key(self, storage):
        """测试存储 API 密钥."""
        result = storage.store_api_key(
            provider="openai",
            key="sk-test123",
        )
        
        assert result is True
        
    def test_retrieve_api_key(self, storage):
        """测试检索 API 密钥."""
        storage.store_api_key(provider="openai", key="sk-test123")
        
        key = storage.retrieve_api_key(provider="openai")
        
        assert key == "sk-test123"
        
    def test_delete_api_key(self, storage):
        """测试删除 API 密钥."""
        storage.store_api_key(provider="openai", key="sk-test123")
        
        result = storage.delete_api_key(provider="openai")
        
        assert result is True
        
    def test_list_providers(self, storage):
        """测试列出所有提供商."""
        storage.store_api_key(provider="openai", key="key1")
        storage.store_api_key(provider="azure", key="key2")
        
        providers = storage.list_providers()
        
        assert "openai" in providers
        assert "azure" in providers
        
    def test_store_with_metadata(self, storage):
        """测试带元数据存储."""
        result = storage.store_api_key(
            provider="azure",
            key="key123",
            metadata={"region": "eastus", "deployment": "gpt-4"},
        )
        
        assert result is True
        
    def test_rotate_key(self, storage):
        """测试密钥轮换."""
        storage.store_api_key(provider="openai", key="old-key")
        
        result = storage.rotate_key(provider="openai", new_key="new-key")
        
        assert result is True
        assert storage.retrieve_api_key(provider="openai") == "new-key"
        
    def test_validate_key(self, storage):
        """测试密钥验证."""
        # 有效的 OpenAI 密钥格式
        is_valid = storage.validate_key_format(
            key="sk-test1234567890abcdef",
            provider="openai",
        )
        
        assert is_valid is True
        
    def test_validate_key_invalid(self, storage):
        """测试无效密钥验证."""
        # 无效的密钥格式
        is_valid = storage.validate_key_format(
            key="invalid-key",
            provider="openai",
        )
        
        assert is_valid is False
        
    def test_export_keys(self, storage):
        """测试导出密钥."""
        storage.store_api_key(provider="openai", key="key1")
        storage.store_api_key(provider="azure", key="key2")
        
        exported = storage.export_keys()
        
        assert "openai" in exported
        assert "azure" in exported
        # 导出的密钥应该是掩码的
        assert "***" in exported["openai"]
        
    def test_import_keys(self, storage):
        """测试导入密钥."""
        keys = {
            "openai": "sk-imported",
            "azure": "azure-imported",
        }
        
        result = storage.import_keys(keys)
        
        assert result is True
        assert storage.retrieve_api_key("openai") == "sk-imported"


class TestSecureStorageIntegration:
    """安全存储集成测试."""

    def test_full_workflow(self):
        """测试完整工作流."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = SecureStorage(
                keyring_service="ut-agent-integration",
                file_path=tmpdir,
                use_keyring=False,
            )
            
            # 1. 存储多个提供商的密钥
            storage.store_api_key("openai", "sk-openai123", {"model": "gpt-4"})
            storage.store_api_key("azure", "azure-key-456", {"region": "westus"})
            
            # 2. 列出所有提供商
            providers = storage.list_providers()
            assert len(providers) == 2
            
            # 3. 检索密钥
            openai_key = storage.retrieve_api_key("openai")
            assert openai_key is not None
            
            # 4. 轮换密钥
            storage.rotate_key("openai", "sk-new-openai")
            
            # 5. 导出密钥（掩码）
            exported = storage.export_keys()
            assert "openai" in exported
            
            # 6. 删除密钥
            storage.delete_api_key("azure")
                
    def test_fallback_storage(self):
        """测试降级存储."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 不使用 keyring，只用文件存储
            storage = SecureStorage(
                keyring_service="ut-agent",
                file_path=tmpdir,
                use_keyring=False,
            )
            
            # 应该自动降级到文件存储
            result = storage.store_api_key("openai", "test-key")
            
            # 即使 keyring 失败，也应该能存储
            assert storage.retrieve_api_key("openai") == "test-key"
