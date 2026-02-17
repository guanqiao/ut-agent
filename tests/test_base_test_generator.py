"""基础测试生成器测试模块."""

import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest

from ut_agent.tools.base_test_generator import (
    TestTemplate,
    GeneratedTest,
    BaseTestGenerator,
    SimpleTestGenerator,
)


class TestTestTemplate:
    """TestTemplate 测试."""

    def test_template_creation(self):
        """测试模板创建."""
        template = TestTemplate(
            name="test_template",
            content="Hello, {{ name }}!",
            description="Test template",
        )

        assert template.name == "test_template"
        assert template.content == "Hello, {{ name }}!"
        assert template.description == "Test template"

    def test_template_render(self):
        """测试模板渲染."""
        template = TestTemplate(
            name="test_template",
            content="Hello, {{ name }}! You are {{ age }} years old.",
        )

        result = template.render({"name": "Alice", "age": 30})

        assert result == "Hello, Alice! You are 30 years old."

    def test_template_with_condition(self):
        """测试带条件的模板."""
        template = TestTemplate(
            name="conditional",
            content="{% if is_active %}Active{% else %}Inactive{% endif %}",
        )

        active_result = template.render({"is_active": True})
        inactive_result = template.render({"is_active": False})

        assert active_result == "Active"
        assert inactive_result == "Inactive"

    def test_template_with_loop(self):
        """测试带循环的模板."""
        template = TestTemplate(
            name="loop",
            content="{% for item in items %}{{ item }}{% if not loop.last %}, {% endif %}{% endfor %}",
        )

        result = template.render({"items": ["a", "b", "c"]})

        assert result == "a, b, c"


class TestGeneratedTest:
    """GeneratedTest 测试."""

    def test_generated_test_creation(self):
        """测试生成结果创建."""
        test = GeneratedTest(
            test_name="test_add",
            test_code="def test_add(): pass",
            source_file="/src/calculator.py",
            test_file="/tests/test_calculator.py",
            language="python",
        )

        assert test.test_name == "test_add"
        assert test.language == "python"
        assert test.imports == []
        assert test.dependencies == []

    def test_generated_test_with_imports(self):
        """测试带导入的生成结果."""
        test = GeneratedTest(
            test_name="test_user",
            test_code="def test_user(): pass",
            source_file="/src/user.py",
            test_file="/tests/test_user.py",
            language="python",
            imports=["import pytest", "from unittest.mock import Mock"],
            dependencies=["src.user"],
        )

        assert len(test.imports) == 2
        assert len(test.dependencies) == 1

    def test_generated_test_to_dict(self):
        """测试转换为字典."""
        test = GeneratedTest(
            test_name="test_func",
            test_code="def test_func(): pass",
            source_file="/src/module.py",
            test_file="/tests/test_module.py",
            language="python",
            template_used="default",
        )

        result = test.to_dict()

        assert result["test_name"] == "test_func"
        assert result["language"] == "python"
        assert result["template_used"] == "default"


class TestSimpleTestGenerator:
    """SimpleTestGenerator 测试."""

    @pytest.fixture
    def generator(self):
        """创建生成器实例."""
        return SimpleTestGenerator()

    def test_generator_initialization(self, generator):
        """测试生成器初始化."""
        assert generator.language == "general"
        assert generator.file_extension == ".test"
        assert "default" in generator.list_templates()

    def test_list_templates(self, generator):
        """测试列出模板."""
        templates = generator.list_templates()

        assert len(templates) >= 1
        assert "default" in templates

    def test_register_template(self, generator):
        """测试注册模板."""
        template = TestTemplate(
            name="custom",
            content="Custom: {{ value }}",
        )

        generator.register_template(template)

        assert "custom" in generator.list_templates()
        assert generator.get_template("custom") == template

    def test_get_template(self, generator):
        """测试获取模板."""
        template = generator.get_template("default")

        assert template is not None
        assert template.name == "default"

    def test_get_nonexistent_template(self, generator):
        """测试获取不存在的模板."""
        template = generator.get_template("nonexistent")

        assert template is None

    def test_get_test_file_path(self, generator):
        """测试获取测试文件路径."""
        result = generator.get_test_file_path("/src/calculator.py")

        assert "calculator.test.py" in result

    def test_get_test_name(self, generator):
        """测试生成测试名称."""
        result = generator.get_test_name("add")

        assert result == "Testadd"

    def test_get_test_name_with_prefix(self, generator):
        """测试带前缀的测试名称."""
        result = generator.get_test_name("calculate", prefix="should")

        assert result == "shouldcalculate"

    def test_generate_imports(self, generator):
        """测试生成导入语句."""
        result = generator.generate_imports(["import os"])

        assert result == ["import os"]

    def test_render_template(self, generator):
        """测试渲染模板."""
        result = generator.render_template("default", {
            "test_name": "test_example",
            "function_call": "example()",
        })

        assert "test_example" in result
        assert "example()" in result

    def test_render_nonexistent_template(self, generator):
        """测试渲染不存在的模板."""
        with pytest.raises(ValueError):
            generator.render_template("nonexistent", {})

    def test_analyze_source(self, generator):
        """测试分析源文件."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_file = Path(tmpdir) / "test.py"
            source_file.write_text("def hello(): pass", encoding="utf-8")

            result = generator.analyze_source(str(source_file))

            assert result == "def hello(): pass"

    def test_generate_test(self, generator):
        """测试生成测试."""
        result = generator.generate_test(
            analysis_result="source code",
            template_name="default",
            test_name="test_hello",
            function_call="hello()",
            source_file="/src/hello.py",
            test_file="/tests/test_hello.py",
        )

        assert result.test_name == "test_hello"
        assert "test_hello" in result.test_code
        assert result.language == "general"

    def test_generate_test_class(self, generator):
        """测试生成测试类."""
        result = generator.generate_test_class(
            class_name="TestCalculator",
            test_methods=["def test_add(): pass", "def test_subtract(): pass"],
            imports=["import pytest"],
        )

        assert "TestCalculator" in result
        assert "test_add" in result
        assert "test_subtract" in result
        assert "import pytest" in result


class TestBaseTestGenerator:
    """BaseTestGenerator 测试."""

    def test_abstract_methods(self):
        """测试抽象方法."""
        with pytest.raises(TypeError):
            BaseTestGenerator()

    def test_subclass_must_implement_abstract_methods(self):
        """测试子类必须实现抽象方法."""

        class IncompleteGenerator(BaseTestGenerator):
            pass

        with pytest.raises(TypeError):
            IncompleteGenerator()

    def test_subclass_with_all_methods(self):
        """测试完整实现的子类."""

        class CompleteGenerator(BaseTestGenerator[str]):
            language = "test"
            file_extension = ".spec"
            test_framework = "testframework"

            def _load_default_templates(self) -> None:
                self.register_template(TestTemplate(
                    name="default",
                    content="test template",
                ))

            def analyze_source(self, source_file: str) -> str:
                return "analyzed"

            def generate_test(
                self,
                analysis_result: str,
                template_name: str = "default",
                **kwargs: Any,
            ) -> GeneratedTest:
                return GeneratedTest(
                    test_name="test",
                    test_code="code",
                    source_file="",
                    test_file="",
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
                return f"class {class_name}: pass"

        generator = CompleteGenerator()

        assert generator.language == "test"
        assert generator.file_extension == ".spec"
        assert generator.test_framework == "testframework"
