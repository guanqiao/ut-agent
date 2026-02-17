"""基础测试生成器模块 - 提取公共逻辑."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, TypeVar, Generic

from jinja2 import Template, Environment, BaseLoader

from ut_agent.utils import get_logger

logger = get_logger("base_test_generator")

T = TypeVar("T")


@dataclass
class TestTemplate:
    """通用测试模板."""

    name: str
    content: str
    description: Optional[str] = None
    language: str = "general"

    def render(self, context: Dict[str, Any]) -> str:
        """渲染模板.

        Args:
            context: 模板上下文

        Returns:
            str: 渲染后的内容
        """
        env = Environment(loader=BaseLoader(), autoescape=False)
        template = env.from_string(self.content)
        return template.render(**context)


@dataclass
class GeneratedTest:
    """生成的测试结果."""

    test_name: str
    test_code: str
    source_file: str
    test_file: str
    language: str
    template_used: str = "default"
    imports: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "test_name": self.test_name,
            "test_code": self.test_code,
            "source_file": self.source_file,
            "test_file": self.test_file,
            "language": self.language,
            "template_used": self.template_used,
            "imports": self.imports,
            "dependencies": self.dependencies,
        }


class BaseTestGenerator(ABC, Generic[T]):
    """测试生成器基类.

    提供公共功能:
    - 模板管理
    - 测试文件路径生成
    - 导入语句生成
    - 测试命名规范
    """

    language: str = "general"
    file_extension: str = ".test"
    test_framework: str = "default"

    def __init__(self):
        """初始化生成器."""
        self._templates: Dict[str, TestTemplate] = {}
        self._load_default_templates()

    @abstractmethod
    def _load_default_templates(self) -> None:
        """加载默认模板.

        子类必须实现此方法来加载特定语言的模板。
        """
        pass

    @abstractmethod
    def analyze_source(self, source_file: str) -> T:
        """分析源文件.

        Args:
            source_file: 源文件路径

        Returns:
            T: 分析结果
        """
        pass

    @abstractmethod
    def generate_test(
        self,
        analysis_result: T,
        template_name: str = "default",
        **kwargs: Any,
    ) -> GeneratedTest:
        """生成测试代码.

        Args:
            analysis_result: 分析结果
            template_name: 模板名称
            **kwargs: 额外参数

        Returns:
            GeneratedTest: 生成的测试
        """
        pass

    def register_template(self, template: TestTemplate) -> None:
        """注册模板.

        Args:
            template: 测试模板
        """
        self._templates[template.name] = template
        logger.debug(f"Registered template: {template.name}")

    def get_template(self, name: str) -> Optional[TestTemplate]:
        """获取模板.

        Args:
            name: 模板名称

        Returns:
            Optional[TestTemplate]: 模板实例
        """
        return self._templates.get(name)

    def list_templates(self) -> List[str]:
        """列出所有模板名称."""
        return list(self._templates.keys())

    def get_test_file_path(self, source_file: str) -> str:
        """获取测试文件路径.

        Args:
            source_file: 源文件路径

        Returns:
            str: 测试文件路径
        """
        path = Path(source_file)
        return str(path.parent / f"{path.stem}{self.file_extension}{path.suffix}")

    def get_test_name(self, entity_name: str, prefix: str = "Test") -> str:
        """生成测试名称.

        Args:
            entity_name: 实体名称（方法名、函数名等）
            prefix: 测试前缀

        Returns:
            str: 测试名称
        """
        return f"{prefix}{entity_name}"

    def generate_imports(
        self,
        additional_imports: Optional[List[str]] = None,
    ) -> List[str]:
        """生成导入语句.

        Args:
            additional_imports: 额外的导入语句

        Returns:
            List[str]: 导入语句列表
        """
        imports = list(self._get_default_imports())
        if additional_imports:
            imports.extend(additional_imports)
        return imports

    def _get_default_imports(self) -> List[str]:
        """获取默认导入语句.

        子类可以重写此方法来提供特定语言的默认导入。
        """
        return []

    def render_template(
        self,
        template_name: str,
        context: Dict[str, Any],
    ) -> str:
        """渲染模板.

        Args:
            template_name: 模板名称
            context: 模板上下文

        Returns:
            str: 渲染后的内容

        Raises:
            ValueError: 模板不存在
        """
        template = self.get_template(template_name)
        if not template:
            raise ValueError(f"Template not found: {template_name}")
        return template.render(context)

    def generate_test_class(
        self,
        class_name: str,
        test_methods: List[str],
        imports: Optional[List[str]] = None,
        class_setup: Optional[str] = None,
        class_teardown: Optional[str] = None,
    ) -> str:
        """生成测试类.

        Args:
            class_name: 类名
            test_methods: 测试方法列表
            imports: 导入语句
            class_setup: 类初始化代码
            class_teardown: 类清理代码

        Returns:
            str: 完整的测试类代码
        """
        return self._build_test_class(
            class_name=class_name,
            test_methods=test_methods,
            imports=imports or [],
            class_setup=class_setup,
            class_teardown=class_teardown,
        )

    @abstractmethod
    def _build_test_class(
        self,
        class_name: str,
        test_methods: List[str],
        imports: List[str],
        class_setup: Optional[str],
        class_teardown: Optional[str],
    ) -> str:
        """构建测试类代码.

        子类必须实现此方法来生成特定语言的测试类。

        Args:
            class_name: 类名
            test_methods: 测试方法列表
            imports: 导入语句
            class_setup: 类初始化代码
            class_teardown: 类清理代码

        Returns:
            str: 测试类代码
        """
        pass


class SimpleTestGenerator(BaseTestGenerator[str]):
    """简单测试生成器 - 用于演示和测试基类."""

    language = "general"
    file_extension = ".test"
    test_framework = "default"

    def _load_default_templates(self) -> None:
        """加载默认模板."""
        self.register_template(TestTemplate(
            name="default",
            content="""
def {{ test_name }}():
    # Arrange
    pass
    
    # Act
    result = {{ function_call }}
    
    # Assert
    assert result == expected
""",
            description="默认测试模板",
        ))

    def analyze_source(self, source_file: str) -> str:
        """分析源文件."""
        return Path(source_file).read_text(encoding="utf-8")

    def generate_test(
        self,
        analysis_result: str,
        template_name: str = "default",
        **kwargs: Any,
    ) -> GeneratedTest:
        """生成测试代码."""
        test_name = kwargs.get("test_name", "test_function")
        function_call = kwargs.get("function_call", "function()")

        test_code = self.render_template(template_name, {
            "test_name": test_name,
            "function_call": function_call,
        })

        return GeneratedTest(
            test_name=test_name,
            test_code=test_code,
            source_file=kwargs.get("source_file", ""),
            test_file=kwargs.get("test_file", ""),
            language=self.language,
        )

    def _build_test_class(
        self,
        class_name: str,
        test_methods: List[str],
        imports: List[str],
        class_setup: Optional[str],
        class_teardown: Optional[str],
    ) -> str:
        """构建测试类代码."""
        methods_code = "\n".join(test_methods)
        imports_code = "\n".join(imports)

        return f"""
{imports_code}

class {class_name}:
    {class_setup or ''}
    
{methods_code}
"""
