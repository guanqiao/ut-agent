"""Prompt 模板加载器模块 - 统一管理外部 Prompt 模板."""

import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import yaml
from jinja2 import Environment, BaseLoader, TemplateSyntaxError, UndefinedError

from ut_agent.utils import get_logger

logger = get_logger("prompt_loader")


class TemplateNotFoundError(Exception):
    """模板未找到错误."""

    def __init__(self, template_name: str):
        self.template_name = template_name
        super().__init__(f"Template not found: {template_name}")


class TemplateRenderError(Exception):
    """模板渲染错误."""

    def __init__(self, template_name: str, message: str):
        self.template_name = template_name
        super().__init__(f"Failed to render template '{template_name}': {message}")


@dataclass
class PromptTemplate:
    """Prompt 模板."""

    name: str
    content: str
    description: str = ""
    language: str = "general"
    version: str = "1.0"
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    _jinja_env: Environment = field(default=None, repr=False, compare=False)

    def __post_init__(self):
        """初始化 Jinja 环境."""
        if self._jinja_env is None:
            self._jinja_env = Environment(
                loader=BaseLoader(),
                autoescape=False,
                keep_trailing_newline=True,
            )

    def render(self, **kwargs: Any) -> str:
        """渲染模板.

        Args:
            **kwargs: 模板变量

        Returns:
            str: 渲染后的内容

        Raises:
            TemplateRenderError: 渲染失败
        """
        try:
            template = self._jinja_env.from_string(self.content)
            return template.render(**kwargs)
        except UndefinedError as e:
            raise TemplateRenderError(self.name, f"Undefined variable: {e}")
        except TemplateSyntaxError as e:
            raise TemplateRenderError(self.name, f"Syntax error: {e}")
        except Exception as e:
            raise TemplateRenderError(self.name, str(e))

    def get_variables(self) -> Set[str]:
        """获取模板变量列表.

        Returns:
            Set[str]: 变量名集合
        """
        pattern = r'\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)'
        variables = set(re.findall(pattern, self.content))

        pattern_block = r'\{%\s*for\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+in'
        variables.update(re.findall(pattern_block, self.content))

        pattern_if = r'\{%\s*if\s+([a-zA-Z_][a-zA-Z0-9_]*)'
        variables.update(re.findall(pattern_if, self.content))

        return variables

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典.

        Returns:
            Dict[str, Any]: 字典表示
        """
        return {
            "name": self.name,
            "content": self.content,
            "description": self.description,
            "language": self.language,
            "version": self.version,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class PromptTemplateLoader:
    """Prompt 模板加载器 - 从文件系统加载模板.

    功能:
    - 从 YAML 文件加载模板
    - 模板缓存
    - 热重载
    - 模板渲染
    """

    def __init__(
        self,
        template_dir: Optional[Path] = None,
        auto_reload: bool = False,
    ):
        """初始化加载器.

        Args:
            template_dir: 模板目录路径
            auto_reload: 是否自动重载
        """
        self._template_dir = template_dir
        self._auto_reload = auto_reload
        self._templates: Dict[str, PromptTemplate] = {}
        self._file_mtimes: Dict[str, float] = {}

        if template_dir and template_dir.exists():
            self.load_all_templates()

    def load_template(self, name: str) -> PromptTemplate:
        """加载指定模板.

        Args:
            name: 模板名称

        Returns:
            PromptTemplate: 模板实例

        Raises:
            TemplateNotFoundError: 模板不存在
        """
        if name in self._templates:
            if self._auto_reload:
                self._check_reload(name)
            return self._templates[name]

        if not self._template_dir:
            raise TemplateNotFoundError(name)

        template_file = self._find_template_file(name)
        if not template_file:
            raise TemplateNotFoundError(name)

        template = self._load_template_from_file(template_file)
        self._templates[name] = template
        self._file_mtimes[name] = template_file.stat().st_mtime

        return template

    def _find_template_file(self, name: str) -> Optional[Path]:
        """查找模板文件.

        Args:
            name: 模板名称

        Returns:
            Optional[Path]: 模板文件路径
        """
        extensions = [".yaml", ".yml", ".jinja", ".jinja2", ".txt"]

        for ext in extensions:
            template_file = self._template_dir / f"{name}{ext}"
            if template_file.exists():
                return template_file

        for template_file in self._template_dir.iterdir():
            if template_file.is_file():
                try:
                    content = template_file.read_text(encoding="utf-8")
                    if content.startswith("---"):
                        frontmatter = self._parse_frontmatter(content)
                        if frontmatter.get("name") == name:
                            return template_file
                except Exception:
                    continue

        return None

    def _load_template_from_file(self, file_path: Path) -> PromptTemplate:
        """从文件加载模板.

        Args:
            file_path: 文件路径

        Returns:
            PromptTemplate: 模板实例
        """
        content = file_path.read_text(encoding="utf-8")

        if content.startswith("---"):
            frontmatter, template_content = self._split_frontmatter(content)
            metadata = self._parse_frontmatter(frontmatter)

            return PromptTemplate(
                name=metadata.get("name", file_path.stem),
                content=template_content,
                description=metadata.get("description", ""),
                language=metadata.get("language", "general"),
                version=metadata.get("version", "1.0"),
                metadata=metadata,
            )

        return PromptTemplate(
            name=file_path.stem,
            content=content,
        )

    def _split_frontmatter(self, content: str) -> tuple:
        """分离 frontmatter 和内容.

        Args:
            content: 原始内容

        Returns:
            tuple: (frontmatter, content)
        """
        parts = content.split("---", 2)
        if len(parts) >= 3:
            return parts[1].strip(), parts[2].strip()
        return "", content

    def _parse_frontmatter(self, content: str) -> Dict[str, Any]:
        """解析 frontmatter.

        Args:
            content: frontmatter 内容

        Returns:
            Dict[str, Any]: 解析结果
        """
        try:
            return yaml.safe_load(content) or {}
        except yaml.YAMLError:
            return {}

    def load_all_templates(self) -> Dict[str, PromptTemplate]:
        """加载所有模板.

        Returns:
            Dict[str, PromptTemplate]: 模板字典
        """
        if not self._template_dir or not self._template_dir.exists():
            return {}

        for template_file in self._template_dir.iterdir():
            if template_file.is_file() and template_file.suffix in [".yaml", ".yml", ".jinja", ".jinja2", ".txt"]:
                try:
                    template = self._load_template_from_file(template_file)
                    self._templates[template.name] = template
                    self._file_mtimes[template.name] = template_file.stat().st_mtime
                except Exception as e:
                    logger.warning(f"Failed to load template {template_file}: {e}")

        return self._templates

    def _check_reload(self, name: str) -> None:
        """检查是否需要重载.

        Args:
            name: 模板名称
        """
        template_file = self._find_template_file(name)
        if not template_file:
            return

        current_mtime = template_file.stat().st_mtime
        if current_mtime > self._file_mtimes.get(name, 0):
            self.reload_template(name)

    def reload_template(self, name: str) -> PromptTemplate:
        """重新加载模板.

        Args:
            name: 模板名称

        Returns:
            PromptTemplate: 模板实例
        """
        if name in self._templates:
            del self._templates[name]

        return self.load_template(name)

    def reload_all_templates(self) -> Dict[str, PromptTemplate]:
        """重新加载所有模板.

        Returns:
            Dict[str, PromptTemplate]: 模板字典
        """
        self._templates.clear()
        self._file_mtimes.clear()
        return self.load_all_templates()

    def render(self, name: str, **kwargs: Any) -> str:
        """渲染模板.

        Args:
            name: 模板名称
            **kwargs: 模板变量

        Returns:
            str: 渲染后的内容
        """
        template = self.load_template(name)
        return template.render(**kwargs)

    def get_template(self, name: str) -> Optional[PromptTemplate]:
        """获取模板.

        Args:
            name: 模板名称

        Returns:
            Optional[PromptTemplate]: 模板实例
        """
        return self._templates.get(name)

    def get_template_names(self) -> List[str]:
        """获取所有模板名称.

        Returns:
            List[str]: 模板名称列表
        """
        return list(self._templates.keys())

    def register_template(self, template: PromptTemplate) -> None:
        """注册模板.

        Args:
            template: 模板实例
        """
        self._templates[template.name] = template


class PromptTemplateRegistry:
    """Prompt 模板注册表 - 内存中管理模板."""

    def __init__(self):
        """初始化注册表."""
        self._templates: Dict[str, PromptTemplate] = {}

    def register(self, template: PromptTemplate) -> None:
        """注册模板.

        Args:
            template: 模板实例
        """
        self._templates[template.name] = template
        logger.debug(f"Registered template: {template.name}")

    def unregister(self, name: str) -> None:
        """注销模板.

        Args:
            name: 模板名称
        """
        if name in self._templates:
            del self._templates[name]

    def get_template(self, name: str) -> PromptTemplate:
        """获取模板.

        Args:
            name: 模板名称

        Returns:
            PromptTemplate: 模板实例

        Raises:
            TemplateNotFoundError: 模板不存在
        """
        if name not in self._templates:
            raise TemplateNotFoundError(name)
        return self._templates[name]

    def get_templates_by_language(self, language: str) -> List[PromptTemplate]:
        """按语言获取模板.

        Args:
            language: 语言

        Returns:
            List[PromptTemplate]: 模板列表
        """
        return [
            t for t in self._templates.values()
            if t.language == language
        ]

    def list_templates(self) -> List[Dict[str, Any]]:
        """列出所有模板.

        Returns:
            List[Dict[str, Any]]: 模板信息列表
        """
        return [t.to_dict() for t in self._templates.values()]

    def clear(self) -> None:
        """清除所有模板."""
        self._templates.clear()


_registry = PromptTemplateRegistry()


def get_registry() -> PromptTemplateRegistry:
    """获取全局注册表.

    Returns:
        PromptTemplateRegistry: 注册表实例
    """
    return _registry
