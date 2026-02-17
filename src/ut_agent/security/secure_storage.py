"""密钥安全存储.

提供多种安全存储后端，包括系统密钥环、文件存储、环境变量和加密存储。
"""

import os
import re
import logging
import base64
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class SecretType(Enum):
    """密钥类型枚举."""
    API_KEY = "api_key"
    PASSWORD = "password"
    TOKEN = "token"
    CERTIFICATE = "certificate"
    CUSTOM = "custom"


@dataclass
class SecretKey:
    """密钥数据类.
    
    Attributes:
        name: 密钥名称
        value: 密钥值
        secret_type: 密钥类型
        metadata: 元数据
        created_at: 创建时间
    """
    name: str
    value: str
    secret_type: SecretType
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    
    def get_masked_value(self, visible_chars: int = 4) -> str:
        """获取掩码显示的密钥值.
        
        Args:
            visible_chars: 可见字符数
            
        Returns:
            str: 掩码后的值
        """
        if len(self.value) <= visible_chars * 2:
            return "***"
        return f"{self.value[:visible_chars]}***{self.value[-visible_chars:]}"


class SecureStorageBackend(ABC):
    """安全存储后端抽象基类."""
    
    @abstractmethod
    def store(self, key: str, value: str) -> bool:
        """存储密钥.
        
        Args:
            key: 密钥名称
            value: 密钥值
            
        Returns:
            bool: 是否成功
        """
        pass
        
    @abstractmethod
    def retrieve(self, key: str) -> Optional[str]:
        """检索密钥.
        
        Args:
            key: 密钥名称
            
        Returns:
            Optional[str]: 密钥值
        """
        pass
        
    @abstractmethod
    def delete(self, key: str) -> bool:
        """删除密钥.
        
        Args:
            key: 密钥名称
            
        Returns:
            bool: 是否成功
        """
        pass


class KeyringStorage(SecureStorageBackend):
    """系统密钥环存储.
    
    使用系统密钥环服务存储密钥。
    """
    
    def __init__(self, service_name: str = "ut-agent"):
        """初始化存储.
        
        Args:
            service_name: 服务名称
        """
        self.service_name = service_name
        self._keyring = None
        
    def _get_keyring(self):
        """获取 keyring 模块."""
        if self._keyring is None:
            try:
                import keyring
                self._keyring = keyring
            except ImportError:
                logger.error("keyring module not installed")
                raise
        return self._keyring
        
    def store(self, key: str, value: str) -> bool:
        """存储密钥."""
        try:
            keyring = self._get_keyring()
            keyring.set_password(self.service_name, key, value)
            return True
        except Exception as e:
            logger.exception(f"Failed to store key {key} in keyring")
            return False
            
    def retrieve(self, key: str) -> Optional[str]:
        """检索密钥."""
        try:
            keyring = self._get_keyring()
            return keyring.get_password(self.service_name, key)
        except Exception as e:
            logger.exception(f"Failed to retrieve key {key} from keyring")
            return None
            
    def delete(self, key: str) -> bool:
        """删除密钥."""
        try:
            keyring = self._get_keyring()
            keyring.delete_password(self.service_name, key)
            return True
        except Exception as e:
            logger.exception(f"Failed to delete key {key} from keyring")
            return False


class FileStorage(SecureStorageBackend):
    """文件存储.
    
    将密钥存储在本地文件中。
    """
    
    def __init__(self, base_path: Optional[str] = None):
        """初始化存储.
        
        Args:
            base_path: 基础路径
        """
        if base_path is None:
            base_path = os.path.expanduser("~/.ut-agent/secrets")
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        
    def _get_file_path(self, key: str) -> Path:
        """获取密钥文件路径."""
        # 清理密钥名称，防止路径遍历
        safe_key = re.sub(r'[^a-zA-Z0-9_-]', '_', key)
        return self.base_path / f"{safe_key}.secret"
        
    def store(self, key: str, value: str) -> bool:
        """存储密钥."""
        try:
            file_path = self._get_file_path(key)
            # 设置文件权限为仅用户可读
            with open(file_path, 'w') as f:
                f.write(value)
            os.chmod(file_path, 0o600)
            return True
        except Exception as e:
            logger.exception(f"Failed to store key {key} to file")
            return False
            
    def retrieve(self, key: str) -> Optional[str]:
        """检索密钥."""
        try:
            file_path = self._get_file_path(key)
            if not file_path.exists():
                return None
            with open(file_path, 'r') as f:
                return f.read()
        except Exception as e:
            logger.exception(f"Failed to retrieve key {key} from file")
            return None
            
    def delete(self, key: str) -> bool:
        """删除密钥."""
        try:
            file_path = self._get_file_path(key)
            if file_path.exists():
                file_path.unlink()
            return True
        except Exception as e:
            logger.exception(f"Failed to delete key {key} from file")
            return False
            
    def list_keys(self) -> List[str]:
        """列出所有密钥."""
        keys = []
        for file_path in self.base_path.glob("*.secret"):
            keys.append(file_path.stem)
        return keys


class EnvStorage(SecureStorageBackend):
    """环境变量存储.
    
    使用环境变量存储密钥。
    """
    
    def __init__(self, prefix: str = "UT_AGENT"):
        """初始化存储.
        
        Args:
            prefix: 环境变量前缀
        """
        self.prefix = prefix
        
    def _get_env_name(self, key: str) -> str:
        """获取环境变量名称."""
        safe_key = re.sub(r'[^a-zA-Z0-9_]', '_', key).upper()
        return f"{self.prefix}_{safe_key}"
        
    def store(self, key: str, value: str) -> bool:
        """存储密钥."""
        env_name = self._get_env_name(key)
        os.environ[env_name] = value
        return True
        
    def retrieve(self, key: str) -> Optional[str]:
        """检索密钥."""
        env_name = self._get_env_name(key)
        return os.environ.get(env_name)
        
    def delete(self, key: str) -> bool:
        """删除密钥."""
        env_name = self._get_env_name(key)
        if env_name in os.environ:
            del os.environ[env_name]
        return True


class EncryptedStorage(SecureStorageBackend):
    """加密存储.
    
    使用 Fernet 对称加密存储密钥。
    """
    
    def __init__(self, base_path: Optional[str] = None, master_key: Optional[str] = None):
        """初始化存储.
        
        Args:
            base_path: 基础路径
            master_key: 主密钥
        """
        if base_path is None:
            base_path = os.path.expanduser("~/.ut-agent/encrypted")
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        self._cipher = None
        if master_key:
            self._init_cipher(master_key)
            
    def _init_cipher(self, master_key: str):
        """初始化加密器."""
        try:
            from cryptography.fernet import Fernet
            # 使用主密钥生成 Fernet 密钥
            import hashlib
            key_hash = hashlib.sha256(master_key.encode()).digest()
            fernet_key = base64.urlsafe_b64encode(key_hash)
            self._cipher = Fernet(fernet_key)
        except ImportError:
            logger.error("cryptography module not installed")
            raise
            
    def _get_file_path(self, key: str) -> Path:
        """获取密钥文件路径."""
        safe_key = re.sub(r'[^a-zA-Z0-9_-]', '_', key)
        return self.base_path / f"{safe_key}.enc"
        
    def store(self, key: str, value: str) -> bool:
        """存储密钥."""
        if self._cipher is None:
            logger.error("Cipher not initialized")
            return False
            
        try:
            file_path = self._get_file_path(key)
            encrypted = self._cipher.encrypt(value.encode())
            with open(file_path, 'wb') as f:
                f.write(encrypted)
            os.chmod(file_path, 0o600)
            return True
        except Exception as e:
            logger.exception(f"Failed to store encrypted key {key}")
            return False
            
    def retrieve(self, key: str) -> Optional[str]:
        """检索密钥."""
        if self._cipher is None:
            logger.error("Cipher not initialized")
            return None
            
        try:
            file_path = self._get_file_path(key)
            if not file_path.exists():
                return None
            with open(file_path, 'rb') as f:
                encrypted = f.read()
            return self._cipher.decrypt(encrypted).decode()
        except Exception as e:
            logger.exception(f"Failed to retrieve encrypted key {key}")
            return None
            
    def delete(self, key: str) -> bool:
        """删除密钥."""
        try:
            file_path = self._get_file_path(key)
            if file_path.exists():
                file_path.unlink()
            return True
        except Exception as e:
            logger.exception(f"Failed to delete encrypted key {key}")
            return False


class SecureStorage:
    """安全存储管理器.
    
    统一管理多种存储后端，提供密钥存储、检索、轮换等功能。
    """
    
    def __init__(
        self,
        keyring_service: str = "ut-agent",
        file_path: Optional[str] = None,
        use_keyring: bool = True,
    ):
        """初始化安全存储.
        
        Args:
            keyring_service: 密钥环服务名称
            file_path: 文件存储路径
            use_keyring: 是否使用密钥环
        """
        self.backends: List[SecureStorageBackend] = []
        
        # 尝试使用密钥环
        if use_keyring:
            try:
                keyring = KeyringStorage(service_name=keyring_service)
                self.backends.append(keyring)
            except Exception as e:
                logger.warning(f"Failed to initialize keyring storage: {e}")
                
        # 添加文件存储作为降级方案
        self.file_storage = FileStorage(base_path=file_path)
        self.backends.append(self.file_storage)
        
    def store_api_key(
        self,
        provider: str,
        key: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """存储 API 密钥.
        
        Args:
            provider: 提供商名称
            key: API 密钥
            metadata: 元数据
            
        Returns:
            bool: 是否成功
        """
        key_name = f"api_key_{provider}"
        
        # 尝试所有后端，直到成功
        for backend in self.backends:
            try:
                if backend.store(key_name, key):
                    logger.info(f"Stored API key for {provider}")
                    return True
            except Exception as e:
                logger.warning(f"Failed to store in {backend.__class__.__name__}: {e}")
                continue
                
        return False
        
    def retrieve_api_key(self, provider: str) -> Optional[str]:
        """检索 API 密钥.
        
        Args:
            provider: 提供商名称
            
        Returns:
            Optional[str]: API 密钥
        """
        key_name = f"api_key_{provider}"
        
        # 尝试所有后端
        for backend in self.backends:
            try:
                value = backend.retrieve(key_name)
                if value is not None:
                    return value
            except Exception as e:
                logger.debug(f"Failed to retrieve from {backend.__class__.__name__}: {e}")
                continue
                
        return None
        
    def delete_api_key(self, provider: str) -> bool:
        """删除 API 密钥.
        
        Args:
            provider: 提供商名称
            
        Returns:
            bool: 是否成功
        """
        key_name = f"api_key_{provider}"
        
        # 从所有后端删除
        success = True
        for backend in self.backends:
            try:
                if not backend.delete(key_name):
                    success = False
            except Exception as e:
                logger.warning(f"Failed to delete from {backend.__class__.__name__}: {e}")
                success = False
                
        return success
        
    def list_providers(self) -> List[str]:
        """列出所有已存储密钥的提供商.
        
        Returns:
            List[str]: 提供商列表
        """
        providers = set()
        
        # 从文件存储列出
        for key in self.file_storage.list_keys():
            if key.startswith("api_key_"):
                provider = key[8:]  # 去掉 "api_key_" 前缀
                providers.add(provider)
                
        return sorted(list(providers))
        
    def rotate_key(self, provider: str, new_key: str) -> bool:
        """轮换 API 密钥.
        
        Args:
            provider: 提供商名称
            new_key: 新密钥
            
        Returns:
            bool: 是否成功
        """
        # 直接存储新密钥，覆盖旧密钥
        return self.store_api_key(provider, new_key)
        
    def validate_key_format(self, key: str, provider: str) -> bool:
        """验证密钥格式.
        
        Args:
            key: 密钥
            provider: 提供商
            
        Returns:
            bool: 是否有效
        """
        if not key or len(key) < 10:
            return False
            
        # OpenAI 密钥格式验证
        if provider == "openai":
            return key.startswith("sk-") and len(key) > 20
            
        # Azure OpenAI 密钥格式验证
        if provider == "azure":
            return len(key) == 32  # Azure 密钥通常是 32 字符
            
        # Anthropic 密钥格式验证
        if provider == "anthropic":
            return key.startswith("sk-ant-") and len(key) > 20
            
        # 通用验证
        return True
        
    def export_keys(self) -> Dict[str, str]:
        """导出所有密钥（掩码显示）.
        
        Returns:
            Dict[str, str]: 密钥字典（掩码）
        """
        exported = {}
        
        for provider in self.list_providers():
            key = self.retrieve_api_key(provider)
            if key:
                # 掩码显示
                if len(key) > 8:
                    exported[provider] = f"{key[:4]}***{key[-4:]}"
                else:
                    exported[provider] = "***"
                    
        return exported
        
    def import_keys(self, keys: Dict[str, str]) -> bool:
        """导入密钥.
        
        Args:
            keys: 密钥字典
            
        Returns:
            bool: 是否全部成功
        """
        success = True
        
        for provider, key in keys.items():
            if not self.store_api_key(provider, key):
                success = False
                
        return success
