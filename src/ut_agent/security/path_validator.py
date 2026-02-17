"""路径验证器 - 防止路径遍历攻击.

提供安全的文件路径验证功能，防止目录遍历攻击。
"""

import os
import re
from pathlib import Path
from typing import Optional, Set
from dataclasses import dataclass
from enum import Enum


class PathValidationError(Exception):
    """路径验证错误."""
    
    def __init__(self, message: str, path: str, reason: str):
        super().__init__(message)
        self.path = path
        self.reason = reason


class PathValidationResult(Enum):
    """路径验证结果."""
    VALID = "valid"
    INVALID_TRAVERSAL = "invalid_traversal"
    INVALID_OUTSIDE_BASE = "invalid_outside_base"
    INVALID_SYMLINK = "invalid_symlink"
    INVALID_NULL_BYTE = "invalid_null_byte"
    INVALID_ABSOLUTE = "invalid_absolute"


@dataclass
class PathValidationConfig:
    """路径验证配置."""
    allow_absolute: bool = False
    allow_symlinks: bool = False
    max_path_length: int = 4096
    allowed_extensions: Optional[Set[str]] = None
    blocked_patterns: Optional[Set[str]] = None


class PathValidator:
    """路径验证器.
    
    防止路径遍历攻击，确保文件操作安全。
    """
    
    # 危险模式列表
    DANGEROUS_PATTERNS = [
        r"\.\.",  # 父目录引用
        r"^~",    # 用户主目录
        r"%",     # URL 编码
        r"\x00",  # 空字节
    ]
    
    def __init__(self, base_dir: Optional[Path] = None, config: Optional[PathValidationConfig] = None):
        """初始化路径验证器.
        
        Args:
            base_dir: 基础目录，所有路径必须在此目录下
            config: 验证配置
        """
        self.base_dir = base_dir.resolve() if base_dir else None
        self.config = config or PathValidationConfig()
    
    def validate(self, path: str, check_exists: bool = False) -> Path:
        """验证路径.
        
        Args:
            path: 要验证的路径
            check_exists: 是否检查文件存在
            
        Returns:
            Path: 验证后的路径对象
            
        Raises:
            PathValidationError: 验证失败时抛出
        """
        # 检查空路径
        if not path or not path.strip():
            raise PathValidationError(
                "路径不能为空",
                path,
                PathValidationResult.INVALID_TRAVERSAL.value
            )
        
        # 检查路径长度
        if len(path) > self.config.max_path_length:
            raise PathValidationError(
                f"路径长度超过限制: {len(path)} > {self.config.max_path_length}",
                path,
                PathValidationResult.INVALID_TRAVERSAL.value
            )
        
        # 检查空字节
        if '\x00' in path:
            raise PathValidationError(
                "路径包含空字节",
                path,
                PathValidationResult.INVALID_NULL_BYTE.value
            )
        
        # 检查绝对路径
        input_path = Path(path)
        if input_path.is_absolute() and not self.config.allow_absolute:
            raise PathValidationError(
                "不允许使用绝对路径",
                path,
                PathValidationResult.INVALID_ABSOLUTE.value
            )
        
        # 规范化路径
        try:
            if self.base_dir and not input_path.is_absolute():
                # 相对于 base_dir 解析
                normalized = (self.base_dir / path).resolve()
            else:
                normalized = input_path.resolve()
        except Exception as e:
            raise PathValidationError(
                f"路径规范化失败: {e}",
                path,
                PathValidationResult.INVALID_TRAVERSAL.value
            )
        
        # 检查是否在基础目录内
        if self.base_dir:
            try:
                normalized.relative_to(self.base_dir)
            except ValueError:
                raise PathValidationError(
                    f"路径超出基础目录范围: {normalized} 不在 {self.base_dir} 内",
                    path,
                    PathValidationResult.INVALID_OUTSIDE_BASE.value
                )
        
        # 检查符号链接
        if not self.config.allow_symlinks and normalized.is_symlink():
            raise PathValidationError(
                "不允许使用符号链接",
                path,
                PathValidationResult.INVALID_SYMLINK.value
            )
        
        # 检查文件扩展名
        if self.config.allowed_extensions:
            ext = normalized.suffix.lower()
            if ext not in self.config.allowed_extensions:
                raise PathValidationError(
                    f"不允许的文件扩展名: {ext}",
                    path,
                    PathValidationResult.INVALID_TRAVERSAL.value
                )
        
        # 检查阻止模式
        if self.config.blocked_patterns:
            for pattern in self.config.blocked_patterns:
                if re.search(pattern, str(normalized)):
                    raise PathValidationError(
                        f"路径匹配阻止模式: {pattern}",
                        path,
                        PathValidationResult.INVALID_TRAVERSAL.value
                    )
        
        # 检查文件存在
        if check_exists and not normalized.exists():
            raise PathValidationError(
                f"文件不存在: {normalized}",
                path,
                PathValidationResult.INVALID_TRAVERSAL.value
            )
        
        return normalized
    
    def is_safe(self, path: str) -> bool:
        """检查路径是否安全.
        
        Args:
            path: 要检查的路径
            
        Returns:
            bool: 是否安全
        """
        try:
            self.validate(path)
            return True
        except PathValidationError:
            return False
    
    def sanitize_filename(self, filename: str) -> str:
        """清理文件名.
        
        移除或替换危险的文件名字符。
        
        Args:
            filename: 原始文件名
            
        Returns:
            str: 清理后的文件名
        """
        # 移除路径分隔符
        filename = filename.replace('/', '_').replace('\\', '_')
        
        # 移除空字节
        filename = filename.replace('\x00', '')
        
        # 移除控制字符
        filename = ''.join(char for char in filename if ord(char) >= 32)
        
        # 移除危险的特殊字符
        dangerous_chars = '<>:"|?*'
        for char in dangerous_chars:
            filename = filename.replace(char, '_')
        
        # 移除开头的点和空格
        filename = filename.lstrip('. ')
        
        # 限制长度
        if len(filename) > 255:
            name, ext = os.path.splitext(filename)
            filename = name[:255 - len(ext)] + ext
        
        # 如果文件名为空，使用默认名称
        if not filename:
            filename = "unnamed"
        
        return filename
    
    def join_safe(self, *parts: str) -> Path:
        """安全地拼接路径.
        
        Args:
            *parts: 路径部分
            
        Returns:
            Path: 拼接后的安全路径
        """
        # 清理每个部分
        cleaned_parts = [self.sanitize_filename(part) for part in parts]
        
        # 拼接相对路径
        relative_path = Path(*cleaned_parts)
        
        # 验证相对路径
        return self.validate(str(relative_path))


class ProjectPathValidator(PathValidator):
    """项目路径验证器.
    
    专门用于验证项目内的文件路径。
    """
    
    def __init__(self, project_root: Path):
        """初始化项目路径验证器.
        
        Args:
            project_root: 项目根目录
        """
        config = PathValidationConfig(
            allow_absolute=False,
            allow_symlinks=False,
            allowed_extensions={
                '.java', '.kt', '.scala',  # JVM
                '.py', '.pyi',             # Python
                '.js', '.ts', '.tsx', '.jsx', '.vue',  # Frontend
                '.go', '.rs', '.cs',       # Other
                '.json', '.yaml', '.yml', '.xml',  # Config
                '.md', '.txt', '.rst',     # Docs
            }
        )
        super().__init__(project_root, config)


def validate_file_path(
    path: str,
    base_dir: Optional[Path] = None,
    allowed_extensions: Optional[Set[str]] = None,
    check_exists: bool = False
) -> Path:
    """验证文件路径的便捷函数.
    
    Args:
        path: 文件路径
        base_dir: 基础目录
        allowed_extensions: 允许的扩展名
        check_exists: 是否检查文件存在
        
    Returns:
        Path: 验证后的路径
        
    Raises:
        PathValidationError: 验证失败时抛出
    """
    config = PathValidationConfig(
        allowed_extensions=allowed_extensions
    )
    validator = PathValidator(base_dir, config)
    return validator.validate(path, check_exists)


def sanitize_path(path: str) -> str:
    """清理路径的便捷函数.
    
    Args:
        path: 原始路径
        
    Returns:
        str: 清理后的路径
    """
    validator = PathValidator()
    return str(validator.sanitize_filename(path))
